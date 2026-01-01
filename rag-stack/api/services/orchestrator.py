# orchestrator.py
"""
orchestrator.py
===============

LRS Orkestratörü (2-Katmanlı AdvancedIntentRouter tabanlı)

Akış:

  ChatRequest
    → AdvancedIntentRouter.analyze_question(...)
         → IntentAnalysisResult
            - question_type (QuestionType - Intent)
            - output_shape (OutputShape - Shape)
            - entities (ExtractedEntities)
            - suggested_plan (QueryPlan)
    → QueryPlan'e göre LRS çağrıları
    → StatsTable + ExampleStatement + (opsiyonel) LLMAnalysis
    → ChatResponse

Bu orkestratör:
- RAG (Qdrant) tarafını kullanmaz, tamamen LRS odaklıdır.
- Tüm soru tiplerini Intent + Shape + QueryPlan üzerinden yürütür.
"""

from __future__ import annotations

import time
import uuid
import requests
from dataclasses import asdict
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta

from config import (
    MAX_EXAMPLE_STATEMENTS,
    OLLAMA_HOST,
    LLM_MODEL_NAME,
    DEFAULT_LLM_PROVIDER,
    STATS_TABLE_LIMIT,
    LLM_CONTEXT_MAX_ROWS,
    DEBUG,
)

from models import (
    ChatRequest,
    ChatResponse,
    StatsTable,
    ExampleStatement,
    LLMAnalysis,
    QueryPlan,
    TopEntitiesQuestion,
)

from services.lrs_service import LRSQueryService
from services.llm_providers import LLMProviderFactory

# ============================================================================
# 2-KATMANLI MİMARİ IMPORT'LARI
# ============================================================================
from services.xapi_nlp.advanced_intent_router import (
    AdvancedIntentRouter,
    IntentAnalysisResult,
    _period_to_time_range
)

from services.xapi_nlp.canonical_questions import (
    QuestionType,
    OutputShape,
)

from services.xapi_nlp.nlp_constants import (
    NEXT_MAINTENANCE_KEYWORDS,
    SEASONAL_SHAPE_KEYWORDS,
    MONTH_NAMES_TR,
    SEASON_NAMES,

    # ✅ General chat / general QA gate için
    MAINTENANCE_KEYWORDS,
    REPAIR_KEYWORDS,
    MATERIAL_BASE_WORDS,
    FAULT_KEYWORDS,
    COST_KEYWORDS,
    VEHICLE_KEYWORDS,
    HISTORY_KEYWORDS,
    TOP_LIST_KEYWORDS,
    TIME_SERIES_KEYWORDS,
    DISTRIBUTION_KEYWORDS,
    TREND_KEYWORDS,
    COMPARISON_KEYWORDS,
)

from services.xapi_nlp.nlp_utils import (
    normalize_tr,
    resolve_period_spec,
    contains_any,   # ✅ eklendi
    extract_top_limit,  # ✅ eklendi
)

from services.prompt_builder import build_stats_prompt, COLUMN_LABEL_MAP_TR
from services.prompt_ontology import get_table_context_from_analysis


# ============================================================================
# GLOBAL INSTANCES
# ============================================================================

_ROUTER = AdvancedIntentRouter()
_LRS = LRSQueryService()

# ============================================================================
# ANCHOR DATE CACHE
# ============================================================================
# LRS'den anchor date'i her sorguda çekmek yerine cache'leriz.
# Cache: Uygulama yeniden başlatılana kadar geçerli.

_ANCHOR_DATE_CACHE: Optional[datetime] = None
_ANCHOR_DATE_RANGE_CACHE: Optional[dict] = None

def _ensure_stats_raw(stats_raw, *, default_error: str | None = None) -> dict:
    # stats_raw dict değilse düzelt
    if not isinstance(stats_raw, dict):
        return {"rows": [], "meta": {"error": default_error or "stats_raw dict değil (fallback)."}}

    # rows yoksa / yanlış tipteyse düzelt
    rows = stats_raw.get("rows", None)
    if not isinstance(rows, list):
        stats_raw["rows"] = []
        stats_raw.setdefault("meta", {})["error"] = "rows list değil (normalize edildi)."
    else:
        stats_raw.setdefault("meta", {})

    # “hiç veri yok + error yok” durumunda default error yaz
    if default_error and not stats_raw["rows"] and not stats_raw["meta"].get("error"):
        stats_raw["meta"]["error"] = default_error

    return stats_raw

def _get_anchor_date() -> Optional[datetime]:
    """
    LRS'deki en son operasyon tarihini döndürür (cached).

    Bu tarih, rölatif dönem sorgularında referans noktası olarak kullanılır.
    Örnek:
      - LRS'de 2019-2022 arası veri var
      - "Son 2 yıl" = 2020-2022 (datetime.now() değil!)
    """
    global _ANCHOR_DATE_CACHE

    if _ANCHOR_DATE_CACHE is not None:
        return _ANCHOR_DATE_CACHE

    try:
        from services.lrs_core import LRSCore
        lrs_core = LRSCore()
        anchor = lrs_core.get_anchor_date()

        if anchor:
            _ANCHOR_DATE_CACHE = anchor
            print(f"[Orchestrator] ✓ Anchor date cached: {anchor.strftime('%Y-%m-%d')}")
            return anchor
        else:
            # ❗️datetime.now() fallback yok: Rölatif dönemler sadece LRS operationDate'e göre hesaplanır.
            print("[Orchestrator] ⚠ Anchor date bulunamadı (LRS operationDate yok veya parse edilemedi)")

    except Exception as e:
        print(f"[Orchestrator] ⚠ Anchor date hatası: {e}")

    return None


def _get_date_range() -> Optional[dict]:
    """
    LRS'deki min/max tarih aralığını döndürür (cached).

    Returns:
        {"min_date": datetime, "max_date": datetime} veya None
    """
    global _ANCHOR_DATE_RANGE_CACHE

    if _ANCHOR_DATE_RANGE_CACHE is not None:
        return _ANCHOR_DATE_RANGE_CACHE

    try:
        from services.lrs_core import LRSCore
        lrs_core = LRSCore()
        date_range = lrs_core.get_date_range()

        if date_range:
            _ANCHOR_DATE_RANGE_CACHE = date_range
            min_d = date_range.get('min_date')
            max_d = date_range.get('max_date')
            if min_d and max_d:
                print(f"[Orchestrator] ✓ Date range cached: "
                      f"{min_d.strftime('%Y-%m-%d')} → {max_d.strftime('%Y-%m-%d')}")
            return date_range

    except Exception as e:
        print(f"[Orchestrator] ⚠ Date range hatası: {e}")

    return None


def clear_anchor_date_cache():
    """
    Anchor date cache'ini temizler.
    Yeni veri yüklendiğinde veya test için kullanılabilir.
    """
    global _ANCHOR_DATE_CACHE, _ANCHOR_DATE_RANGE_CACHE
    _ANCHOR_DATE_CACHE = None
    _ANCHOR_DATE_RANGE_CACHE = None
    print("[Orchestrator] Anchor date cache temizlendi")
# ============================================================================
# PERIOD HELPERS
# ============================================================================

def _periodspec_to_price_trend_period(period) -> Optional[Dict[str, Any]]:
    """
    CanonicalQuestion'daki PeriodSpec'i material_price_trend'in
    beklediği dict formatına dönüştürür.
    """
    if not period:
        return None
    
    # Relative period: "son N ay/yıl"
    if period.kind == "relative" and period.unit and period.value:
        if period.unit == "year":
            return {"kind": "last_n_years", "years": period.value}
        elif period.unit == "month":
            return {"kind": "last_n_months", "months": period.value}
    
    # Belirli yıl: "2023 yılında"
    if period.kind == "year" and period.year:
        return {"kind": "specific_year", "year": period.year}
    
    # Mevsim: "2023 kışında"
    if period.kind == "season" and period.season:
        return {
            "kind": "season",
            "season": period.season,
            "year": period.year,
        }
    
    return None


def _canonical_period_to_top_entities_period(period: Any) -> Optional[Dict[str, Any]]:
    """
    CanonicalQuestion.period → TopEntitiesQuestion.period mapping.
    """
    if period is None:
        return None

    kind = getattr(period, "kind", None)

    # Rölatif dönemler
    if kind == "relative":
        unit = getattr(period, "unit", None)
        value = getattr(period, "value", None)
        if not value:
            return None

        try:
            value_int = int(value)
        except (TypeError, ValueError):
            return None

        if unit == "month":
            return {"kind": "last_n_months", "months": value_int}
        if unit == "year":
            return {"kind": "last_n_years", "years": value_int}
        return None

    # Yıl bazlı
    if kind == "year" and getattr(period, "year", None):
        try:
            year_int = int(period.year)
        except (TypeError, ValueError):
            year_int = period.year
        return {"kind": "year", "year": year_int}

    # Ay bazlı
    if kind == "month" and getattr(period, "month", None):
        data: Dict[str, Any] = {"kind": "month"}
        try:
            data["month"] = int(period.month)
        except (TypeError, ValueError):
            data["month"] = period.month

        if getattr(period, "year", None):
            try:
                data["year"] = int(period.year)
            except (TypeError, ValueError):
                data["year"] = period.year
        return data

    # Mevsim bazlı
    if kind == "season" and getattr(period, "season", None):
        data = {"kind": "season", "season": str(period.season)}
        if getattr(period, "year", None):
            try:
                data["year"] = int(period.year)
            except (TypeError, ValueError):
                data["year"] = period.year
        return data

    return None


# ============================================================================
# INTENT DETECTION (Legacy Compatibility)
# ============================================================================

def _detect_intent_from_question_type(qtype: QuestionType) -> str:
    """
    Eski "intent" alanını (statistical / hybrid / unknown)
    yeni QuestionType üzerinden türetir.
    """
    # İlişkisel/pattern sorularda hybrid
    if qtype in {
        QuestionType.PATTERN_ANALYSIS,
        QuestionType.NEXT_MAINTENANCE,
        QuestionType.COMPARISON_ANALYSIS,
    }:
        return "hybrid"

    # Diğer her şey: LRS istatistiklerine dayalı "statistical"
    return "statistical"


# ============================================================================
# EXAMPLE STATEMENT BUILDER
# ============================================================================

def _build_examples_from_docs(
    lrs: LRSQueryService,
    docs: List[Dict[str, Any]],
) -> List[ExampleStatement]:
    """
    LRS'ten dönen ham dokümanları ExampleStatement modeline çevirir.
    """
    examples: List[ExampleStatement] = []
    for doc in docs:
        statement_id = str(doc.get("_id") or doc.get("id") or "")
        try:
            text = lrs.render_statement_human(doc)
        except Exception:
            text = f"LRS kaydı (id={statement_id})"

        ex = ExampleStatement(
            statement_id=statement_id or None,
            raw=doc,
            text=text,
        )
        examples.append(ex)
    return examples


# ============================================================================
# STATS TABLE BUILDER
# ============================================================================

def _build_stats_table(
    stats_raw: Dict[str, Any],
    analysis: IntentAnalysisResult,
    plan: Optional[QueryPlan],
) -> StatsTable:
    """
    Ham LRS istatistik çıktısından StatsTable üretir.
    """
    rows = stats_raw.get("rows", []) or []

    # --- Display mapping (SSOT: services.xapi_nlp.nlp_constants) ---
    # month: 9 -> "09-Eylül"
    # season: "winter"/"kis"/... -> (SEASON_NAMES ne tanımlıyorsa)
    if rows and isinstance(rows, list) and isinstance(rows[0], dict):

        def _fmt_year(v: Any) -> Any:
            """Yılı string olarak formatla (binlik ayracı olmadan)."""
            if v is None:
                return v
            try:
                return str(int(v))  # "2,017" yerine "2017"
            except Exception:
                return v

        def _fmt_month(v: Any) -> Any:
            if v is None:
                return v
            try:
                m = int(v)
                if 1 <= m <= 12:
                    name = MONTH_NAMES_TR.get(m)
                    return f"{m:02d}-{name}" if name else m
            except Exception:
                pass
            return v

        def _fmt_season(v: Any) -> Any:
            if v is None:
                return v
            if isinstance(v, str):
                key = v.strip()
                return SEASON_NAMES.get(key, v)
            return v

        for r in rows:
            if "year" in r:
                r["year"] = _fmt_year(r.get("year"))
            if "month" in r:
                r["month"] = _fmt_month(r.get("month"))
            if "season" in r:
                r["season"] = _fmt_season(r.get("season"))

        columns = list(rows[0].keys())
    else:
        columns = []

    # 2-Katmanlı bilgi
    intent = analysis.question_type
    shape = analysis.output_shape

    # Başlık / açıklama
    title = f"İstatistiksel Tablo • {intent.value} • {shape.value}"
    desc = f"Intent: {intent.value}, Shape: {shape.value}"

    # Meta
    meta_from_lrs = stats_raw.get("meta") if isinstance(stats_raw, dict) else None

    meta: Dict[str, Any] = {
        "question_type": intent.value,
        "output_shape": shape.value,
        "intent_confidence": analysis.intent_confidence,
        "shape_confidence": analysis.shape_confidence,
        "entities": asdict(analysis.entities),
    }

    if analysis.matched_cq:
        meta["canonical_question"] = {
            "question_type": analysis.matched_cq.question_type.value,
            "output_shape": analysis.matched_cq.output_shape.value,
            "primary_dimension": analysis.matched_cq.primary_dimension,
            "description": analysis.matched_cq.description,
        }

    if plan is not None:
        meta["query_plan"] = asdict(plan)

    if analysis.analysis_details:
        meta["analysis_details"] = analysis.analysis_details

    if isinstance(meta_from_lrs, dict):
        meta.update(meta_from_lrs)

    # Anchor date bilgisini meta'ya ekle (UI için)
    anchor = _get_anchor_date()
    if anchor:
        meta["anchor_date"] = anchor.isoformat()
        meta["anchor_date_display"] = anchor.strftime("%d.%m.%Y")
    else:
        meta["anchor_date_missing"] = True

    date_range = _get_date_range()
    if date_range:
        min_d = date_range.get("min_date")
        max_d = date_range.get("max_date")
        meta["lrs_date_range"] = {
            "min": min_d.isoformat() if min_d else None,
            "max": max_d.isoformat() if max_d else None,
            "min_display": min_d.strftime("%d.%m.%Y") if min_d else None,
            "max_display": max_d.strftime("%d.%m.%Y") if max_d else None,
        }

    table = StatsTable(
        title=title,
        description=desc,
        columns=columns,
        rows=rows,
        meta=meta,
    )
    return table

# ============================================================================
# LLM INTEGRATION
# ============================================================================

def _call_llm_general(request: ChatRequest) -> LLMAnalysis:
    """
    LRS/istatistik olmadan, genel sohbet ve genel bilgi soruları için LLM çağrısı.
    
    🆕 Güncelleme: Artık LLMProviderFactory kullanılıyor.
    Provider seçimi request.provider'dan veya DEFAULT_LLM_PROVIDER'dan gelir.
    """
    from services.llm_providers import LLMProviderFactory
    from config import DEFAULT_LLM_PROVIDER
    
    # Provider ve model seçimi
    provider_id = request.provider or DEFAULT_LLM_PROVIDER
    provider = LLMProviderFactory.get_provider(provider_id)
    model_name = request.model or provider.get_default_model()

    system_prompt = (
        "Sen yardımcı, genel amaçlı bir asistansın. "
        "Kısa, net ve doğal cevap ver. "
        "Bilmediğin yerde bunu açıkça belirt. "
        "Veri/istatistik uydurma."
    )

    user_text = (request.query or "").strip() or "Merhaba"

    # Provider Factory ile LLM çağrısı
    result = provider.generate(
        prompt=user_text,
        model=model_name,
        system_prompt=system_prompt,
        temperature=0.7,
        max_tokens=1024,
    )
    
    # Provider bilgisi
    if result.provider is None:
        result.provider = provider_id
    
    return result


def is_general_chat(qn_norm: str, analysis: IntentAnalysisResult) -> bool:
    """
    1) Selamlaşma / small talk
    2) Domain kelimesi olsa bile 'genel bilgi / tanım' isteyen sorular
    3) Router confidence düşük + domain sinyali yoksa → genel LLM
    """

    # (1) Selam / small talk
    greetings = [
        "merhaba", "selam", "hey", "hello", "hi",
        "nasilsin", "naber", "iyi misin", "gunaydin", "iyi aksamlar", "iyi geceler",
    ]
    if contains_any(qn_norm, greetings):
        return True

    # Domain sinyalleri (LRS'e gitmeye değer mi?)
    domain_signals = (
        MAINTENANCE_KEYWORDS
        + REPAIR_KEYWORDS
        + MATERIAL_BASE_WORDS
        + FAULT_KEYWORDS
        + COST_KEYWORDS
        + VEHICLE_KEYWORDS
        + HISTORY_KEYWORDS
        + NEXT_MAINTENANCE_KEYWORDS
    )

    # Analitik sinyaller (istatistik/dağılım/top/trend vb.)
    analytic_signals = (
        TOP_LIST_KEYWORDS
        + TIME_SERIES_KEYWORDS
        + DISTRIBUTION_KEYWORDS
        + TREND_KEYWORDS
        + COMPARISON_KEYWORDS
        + [
            "dagilim", "dağılım", "kac", "kaç", "en cok", "en çok",
            "yillara", "yıllara", "aylara", "aylara gore", "mevsim", "sezon",
            "son", "gecen", "geçen", "trend", "top", "siralama", "karsilastir", "karşılaştır",
        ]
    )

    # (2) Domain kelimesi var ama "tanım / genel bilgi" istiyor → LRS'e gitme
    general_info_signals = ["genel bilgi", "nedir", "ne demek", "acikla", "açıkla", "tanim", "tanım", "ozet", "özet"]
    if contains_any(qn_norm, general_info_signals) and (not contains_any(qn_norm, analytic_signals)):
        return True

    # (3) Confidence düşük + domain sinyali yok → genel dünya bilgisi
    # canonical_questions.detect_intent default'u genelde 0.3 döndürüyor; bunu yakalıyoruz.
    low_intent = (analysis.intent_confidence <= 0.31)
    no_domain = (not contains_any(qn_norm, domain_signals))
    if low_intent and no_domain:
        return True

    # Ek güvenlik: çok kısa ve domain yoksa
    if len((qn_norm or "").split()) <= 3 and no_domain:
        return True

    return False

# orchestrator.py içine (ör. _call_llm üstüne) ekle

def _as_float(x):
    try:
        if x is None: 
            return None
        return float(x)
    except Exception:
        return None

def _sort_key_desc(row, key):
    v = _as_float(row.get(key))
    # None en sona gitsin
    return (v is None, -(v or 0.0))

def _pick_sort_metric(rows):
    """Rows içindeki kolonlara göre en mantıklı sıralama metriğini seç."""
    if not rows:
        return None
    keys = set(rows[0].keys())
    for k in ("changePct", "count", "sum_cost", "observations", "ratio"):
        if k in keys:
            return k
    return None

def _balanced_take_by_group(rows, group_key, n):
    """Gruplar arası dengeli örnekleme: her gruptan sırayla al."""
    if not rows or not group_key or n <= 0:
        return rows[:n]

    # gruplara ayır
    groups = {}
    for r in rows:
        g = r.get(group_key, "—")
        groups.setdefault(g, []).append(r)

    # grupların kendi iç sırası korunur
    group_names = list(groups.keys())
    out = []
    i = 0
    while len(out) < n:
        progressed = False
        for g in group_names:
            if i < len(groups[g]):
                out.append(groups[g][i])
                progressed = True
                if len(out) >= n:
                    break
        if not progressed:
            break
        i += 1
    return out


def _call_llm(
    request: ChatRequest,
    analysis,  # IntentAnalysisResult
    table: Optional[StatsTable],
    examples: List[ExampleStatement],
) -> LLMAnalysis:
    """
    LLM entegrasyonu - 2 Katmanlı bilgiyle zenginleştirilmiş.
    
    🆕 Güncelleme: Artık LLMProviderFactory kullanılıyor.
    Provider seçimi request.provider'dan veya DEFAULT_LLM_PROVIDER'dan gelir.
    """
    
    # 🆕 Provider ve model seçimi
    provider_id = request.provider or DEFAULT_LLM_PROVIDER
    provider = LLMProviderFactory.get_provider(provider_id)
    
    # Model: request'ten gelen veya provider'ın default'u
    model_name = request.model or provider.get_default_model()
    
    role = request.role or "servis_analisti"
    behavior = request.behavior or "balanced"

    # LLM'e gidecek tabloyu sınırla
    table_for_llm: Optional[StatsTable] = table
    if isinstance(table, StatsTable):
        max_rows = min(request.limit or LLM_CONTEXT_MAX_ROWS, LLM_CONTEXT_MAX_ROWS)
        all_rows = table.rows or []

        # 1) Önce "en anlamlı sıra" oluştur
        metric = _pick_sort_metric(all_rows)

        rows_for_llm = all_rows

        # TOP / PRICE_TREND gibi metrik varsa desc sırala
        if metric in ("changePct", "count", "sum_cost", "observations", "ratio"):
            rows_for_llm = sorted(all_rows, key=lambda r: _sort_key_desc(r, metric))

        # 2) Eğer hem seri hem grup varsa dengeli örnekle (ör. verbType)
        if isinstance(table.meta, dict):
            shape = (table.meta.get("output_shape") or "").lower()
            if shape in ("distribution", "time_series", "trend"):
                if all_rows and isinstance(all_rows[0], dict) and "verbType" in all_rows[0]:
                    rows_for_llm = _balanced_take_by_group(rows_for_llm, "verbType", max_rows)

        limited_rows = rows_for_llm[:max_rows]

        table_for_llm = StatsTable(
            title=table.title,
            description=table.description,
            columns=table.columns,
            rows=limited_rows,
            meta=table.meta,
        )

    period_meta = table_for_llm.meta if isinstance(table_for_llm, StatsTable) else None

    # 2-Katmanlı bilgiyi meta'ya ekle
    qtype = analysis.question_type.value
    qshape = analysis.output_shape.value
    
    # =========================================================================
    # Tablo bağlam bloğu oluştur
    # =========================================================================
    context_block = None
    if isinstance(table_for_llm, StatsTable) and table_for_llm.rows:
        try:
            context_block = get_table_context_from_analysis(
                user_query=request.query,
                table_rows=table_for_llm.rows,
                question_type=qtype,
                output_shape=qshape,
                meta={
                    **(period_meta or {}),
                    "question_type": qtype,
                    "output_shape": qshape,
                    "entities": asdict(analysis.entities),
                },
                label_map=COLUMN_LABEL_MAP_TR,
            )
            
            if DEBUG:
                print(f"[DEBUG] Context block oluşturuldu: {len(context_block)} karakter")
                
        except Exception as e:
            if DEBUG:
                print(f"[DEBUG] Context block oluşturulamadı: {e}")
            context_block = None
    # =========================================================================

    # Bu import orchestrator.py'de zaten var
    from services.prompt_builder import build_stats_prompt
    
    prompt = build_stats_prompt(
        user_query=request.query,
        plan=None,
        table=table_for_llm,
        meta={
            **(period_meta or {}),
            "question_type": qtype,
            "output_shape": qshape,
            "entities": asdict(analysis.entities),
        },
        role=role,
        behavior=behavior,
        context_block=context_block,
    )

    system_prompt = (
        "Sen MAN Türkiye servis bakım verisi üzerinde çalışan bir domain uzmanı yapay zekasın. "
        "Cevaplarında veri dışı sayı uydurma; LRS'ten gelen tablo ve örnek kayıtlara dayanarak "
        "patern ve anlam üret. Emin olmadığın yerlerde varsayım olduğunu belirt."
    )

    # =========================================================================
    # 🆕 Provider Factory ile LLM çağrısı
    # =========================================================================
    
    if DEBUG:
        print(f"[DEBUG] LLM çağrısı: provider={provider_id}, model={model_name}")
    
    # Provider.generate() çağrısı
    result = provider.generate(
        prompt=prompt,
        model=model_name,
        system_prompt=system_prompt,
    )
    
    # Provider bilgisi zaten result'ta var (provider.generate içinde set ediliyor)
    # Ama emin olmak için tekrar set edelim
    if result.provider is None:
        result.provider = provider_id
    
    return result

# ============================================================================
# DOMAIN-SPECIFIC QUESTION DETECTORS
# ============================================================================

def _is_price_trend_question(qn: str) -> bool:
    """
    Basit fiyat trend sorusu mu? (mevsim boyutu olmadan)
    """
    # Dimension pattern'leri varsa → bu fonksiyon handle etmemeli
    dimension_patterns = (
        "mevsimlere gore", "mevsime gore", "mevsimsel", "mevsim bazinda",
        "yillara gore", "yil bazinda",
        "aylara gore", "ay bazinda",
    )
    if any(p in qn for p in dimension_patterns):
        return False
    
    return (
        "fiyat" in qn
        and any(p in qn for p in ("art", "yuks", "trend", "zam"))
    )


def _is_seasonal_price_trend_question(qn: str) -> bool:
    """
    Mevsimsel fiyat trend sorusu mu?
    """
    has_season = any(p in qn for p in SEASONAL_SHAPE_KEYWORDS)
    has_price = "fiyat" in qn
    has_increase = any(p in qn for p in ("art", "yuks", "zam"))
    
    return has_season and has_price and has_increase


def _is_next_maintenance_question(qn: str) -> bool:
    """
    Next maintenance pattern sorusu mu?
    """
    has_next_signal = any(sig in qn for sig in NEXT_MAINTENANCE_KEYWORDS)
    has_conditional = any(
        word in qn
        for word in ["kullanildiginda", "degistirildiginde"]
    )
    return has_next_signal and has_conditional


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def answer_with_lrs_and_llm(request: ChatRequest) -> ChatResponse:
    """
    /chat endpoint'i için ana fonksiyon (2-Katmanlı AdvancedIntentRouter tabanlı).

    1) AdvancedIntentRouter ile:
         soru → IntentAnalysisResult
               (question_type + output_shape + entities + suggested_plan)
    2) suggested_plan (QueryPlan) ile LRS istatistik + örnekleri al
    3) StatsTable + ExampleStatement üret
    4) İsteğe bağlı olarak LLM yorumu ekle
    5) ChatResponse ile döndür
    """
    trace_id = str(uuid.uuid4())[:8]
    analysis = None
    plan = None
    try:
        t0 = time.time()

        # 1) Intent + Shape analizi
        analysis: IntentAnalysisResult = _ROUTER.analyze_question(request.query)

        intent = analysis.question_type
        shape = analysis.output_shape
        plan: Optional[QueryPlan] = analysis.suggested_plan

        # 2) Legacy intent string
        legacy_intent = _detect_intent_from_question_type(intent)

        # 3) LRS sorgu limiti
        if not request.limit:
            request.limit = LLM_CONTEXT_MAX_ROWS

        stats_limit = STATS_TABLE_LIMIT

        # 4) Normalize edilmiş sorgu
        qn_raw = (request.query or "").lower()
        qn_norm = normalize_tr(qn_raw)

        # ✅ DISTRIBUTION + canonical secondary_dimension fix:
        # "Araç modellerine göre işlem tiplerinin dağılımı" gibi sorularda
        # group_by mutlaka [secondary_dimension, primary_dimension] olmalı.
        if (
            analysis.matched_cq is not None
            and shape == OutputShape.DISTRIBUTION
            and plan is not None
        ):
            cq = analysis.matched_cq
            gb = []
            if getattr(cq, "secondary_dimension", None):
                gb.append(cq.secondary_dimension)
            if getattr(cq, "primary_dimension", None):
                gb.append(cq.primary_dimension)

            # group_by boş kalmasın; sadece gerçekten bir şey ürettiysek override et
            if gb:
                plan.group_by = gb

            # metrics canonical'dan geliyorsa eşitle (yoksa mevcut kalsın)
            if getattr(cq, "metrics", None):
                plan.metrics = cq.metrics


        # ✅ Fallback: Router top_limit yakalayamadıysa orchestrator yakalasın
        # "en fazla 5 malzeme", "top 7", "ilk 3" vb.
        if getattr(analysis.entities, "has_top_signal", False):
            n = extract_top_limit(qn_norm, default=getattr(analysis.entities, "top_limit", 10) or 10)
            analysis.entities.top_limit = n
            # plan varsa limit'i de eşitle (TOP_LIST gibi yerlerde kullanılıyor)
            if plan is not None:
                plan.limit = n

        # ✅ Genel sohbet / genel bilgi: LRS'e hiç girme, direkt LLM
        if is_general_chat(qn_norm, analysis):
            # Bu tip sorularda LLM kapalı gelmiş olsa bile anlamlı cevap üretelim
            if not request.use_llm:
                # LLM kapalıysa general soruya cevap veremeyiz; net mesaj dön.
                table = StatsTable(
                    title="Genel Yanıt",
                    description="Dil modeli kapalı. Genel sohbet / genel bilgi soruları için LLM gerekir.",
                    columns=[],
                    rows=[],
                    meta={"general_chat": True, "query_executed": False, "llm_enabled": False},
                )
                return ChatResponse(
                    intent="general",
                    scenario="general_chat",
                    summary=f"Soru: {request.query}",
                    data={"rows": [], "meta": table.meta},
                    tables=[table],
                    examples=[],
                    llm=None,
                )

            llm_analysis = _call_llm_general(request)

            table = StatsTable(
                title="Genel Yanıt",
                description="Bu soru LRS istatistiği gerektirmeyen genel bir sorudur.",
                columns=[],
                rows=[],
                meta={
                    "general_chat": True,
                    "query_executed": False,
                },
            )

            response = ChatResponse(
                intent="general",
                scenario="general_chat",
                summary=f"Soru: {request.query}",
                data={"rows": [], "meta": {"general_chat": True, "query_executed": False}},
                tables=[table],
                examples=[],
                llm=llm_analysis,
            )
            return response

        # ✅ Başlangıç durumu: henüz hiçbir sorgu çalışmadı
        stats_raw: Dict[str, Any] = {}
        examples: List[ExampleStatement] = []

        # Bu flag ile UI’da “sorgu çalıştı mı?” netleşir
        query_executed = False

        # ========================================================================
        # Domain-specific kısa yollar
        # ========================================================================

        # ─────────────────────────────────────────────────────────────────────────
        # NEXT MAINTENANCE SORULARI
        # ─────────────────────────────────────────────────────────────────────────
        if intent == QuestionType.NEXT_MAINTENANCE or _is_next_maintenance_question(qn_norm):
            try:
                entities = analysis.entities

                # Vehicle model
                model_filter = None
                if entities.vehicle_models:
                    model_filter = entities.vehicle_models[0]
                elif plan and "vehicleModel_eq" in (plan.filters or {}):
                    model_filter = plan.filters["vehicleModel_eq"]

                # Conditional material
                conditional_material = entities.conditional_material
                if not conditional_material and plan:
                    conditional_material = (plan.filters or {}).get("_conditional_material")

                stats_raw = _LRS.next_maintenance_materials(
                    model=model_filter or "rhc 404 400",
                    material_name=conditional_material or "SENSÖR",
                    limit=stats_limit,
                ) or {}
                query_executed = True

            except Exception as exc:
                stats_raw = {
                    "rows": [],
                    "meta": {"error": f"next_maintenance_materials hatası: {exc}"},
                }
                query_executed = True

            examples = []

        # ─────────────────────────────────────────────────────────────────────────
        # MAINTENANCE_HISTORY: Araç bakım geçmişi (malzeme detaylı)
        # ─────────────────────────────────────────────────────────────────────────
        elif intent == QuestionType.MAINTENANCE_HISTORY and shape == OutputShape.DETAIL_LIST:
            try:
                vehicle_id = None
                if analysis.entities.vehicle_ids:
                    vehicle_id = analysis.entities.vehicle_ids[0]
                elif plan and "vehicleId_eq" in (plan.filters or {}):
                    vehicle_id = plan.filters["vehicleId_eq"]

                if vehicle_id:
                    stats_raw = _LRS.vehicle_maintenance_history(
                        vehicle_id=vehicle_id,
                        limit=stats_limit,
                    ) or {}
                    query_executed = True
                else:
                    stats_raw = {
                        "rows": [],
                        "meta": {"error": "Araç ID bulunamadı. Lütfen araç numarası belirtin."},
                    }
                    query_executed = False  # query çalışmadı, input eksik

            except Exception as exc:
                stats_raw = {
                    "rows": [],
                    "meta": {"error": f"vehicle_maintenance_history hatası: {exc}"},
                }
                query_executed = True

            examples = []

        # ─────────────────────────────────────────────────────────────────────────
        # MEVSİMSEL FİYAT TREND SORULARI
        # ─────────────────────────────────────────────────────────────────────────
        elif (
            intent == QuestionType.COST_ANALYSIS
            and shape == OutputShape.SEASONAL
            and _is_seasonal_price_trend_question(qn_norm)
        ):
            period = resolve_period_spec(analysis, plan, qn_norm)
            price_trend_period = _periodspec_to_price_trend_period(period)

            try:
                stats_raw = _LRS.material_price_trend_by_season(
                    period=price_trend_period,
                    limit=stats_limit,
                ) or {}
                query_executed = True
            except Exception as exc:
                stats_raw = {
                    "rows": [],
                    "meta": {"error": f"material_price_trend_by_season hatası: {exc}"},
                }
                query_executed = True

            examples = []

        # ─────────────────────────────────────────────────────────────────────────
        # MEVSİMSEL + MALZEME AİLESİ FİYAT TRENDİ
        # ─────────────────────────────────────────────────────────────────────────
        elif (
            "fiyat" in qn_norm
            and any(p in qn_norm for p in ("art", "yuks", "zam"))
            and "mevsim" in qn_norm
            and any(p in qn_norm for p in ("aile", "ailesi"))
        ):
            period = resolve_period_spec(analysis, plan, qn_norm)
            price_trend_period = _periodspec_to_price_trend_period(period)

            try:
                stats_raw = _LRS.material_family_price_trend_by_season(
                    period=price_trend_period,
                    limit_per_season=stats_limit,
                ) or {}
                query_executed = True
            except Exception as exc:
                stats_raw = {
                    "rows": [],
                    "meta": {"error": f"material_family_price_trend_by_season hatası: {exc}"},
                }
                query_executed = True

            examples = []

        # ─────────────────────────────────────────────────────────────────────────
        # 🆕 MALZEME AİLESİ FİYAT TRENDİ (Mevsimsiz)
        # ─────────────────────────────────────────────────────────────────────────
        elif (
            "fiyat" in qn_norm
            and any(p in qn_norm for p in ("art", "yuks", "zam"))
            and any(p in qn_norm for p in ("aile", "ailesi", "aileleri"))
            and "mevsim" not in qn_norm
        ):
            period = resolve_period_spec(analysis, plan, qn_norm)
            price_trend_period = _periodspec_to_price_trend_period(period)

            try:
                stats_raw = _LRS.material_family_price_trend(
                    period=price_trend_period,
                    limit=stats_limit,
                ) or {}
                query_executed = True
            except Exception as exc:
                stats_raw = {
                    "rows": [],
                    "meta": {"error": f"material_family_price_trend hatası: {exc}"},
                }
                query_executed = True

            examples = []

        # ─────────────────────────────────────────────────────────────────────────
        # FİYAT TREND SORULARI (Basit)
        # ─────────────────────────────────────────────────────────────────────────
        elif (intent == QuestionType.COST_ANALYSIS and shape == OutputShape.TREND) or _is_price_trend_question(qn_norm):
            period = resolve_period_spec(analysis, plan, qn_norm)
            price_trend_period = _periodspec_to_price_trend_period(period)

            try:
                stats_raw = _LRS.material_price_trend(
                    period=price_trend_period,
                    limit=stats_limit,
                ) or {}
                query_executed = True
            except Exception as exc:
                stats_raw = {
                    "rows": [],
                    "meta": {"error": f"material_price_trend hatası: {exc}"},
                }
                query_executed = True

            examples = []

        # ─────────────────────────────────────────────────────────────────────────
        # 🆕 MEVSİMSEL MALZEME KULLANIMI - YIL × MEVSİM × TOP N
        # ─────────────────────────────────────────────────────────────────────────
        elif intent == QuestionType.MATERIAL_USAGE and shape == OutputShape.TOP_PER_GROUP and "mevsim" in qn_norm:
            period = resolve_period_spec(analysis, plan, qn_norm)

            seasonal_period = None
            if period:
                if period.kind == "relative":
                    if period.unit == "year" and period.value:
                        seasonal_period = {"kind": "last_n_years", "years": period.value}
                    elif period.unit == "month" and period.value:
                        seasonal_period = {"kind": "last_n_months", "months": period.value}
                elif period.kind == "year" and period.year:
                    seasonal_period = {"kind": "year", "year": period.year}

            limit_per_group = 5
            if analysis.entities.has_top_signal:
                limit_per_group = analysis.entities.top_limit
            elif plan and plan.limit:
                limit_per_group = plan.limit
            elif analysis.matched_cq and analysis.matched_cq.default_limit:
                limit_per_group = analysis.matched_cq.default_limit

            try:
                stats_raw = _LRS.material_usage_top_per_year_season(
                    period=seasonal_period,
                    limit_per_group=limit_per_group,
                    limit=stats_limit,
                ) or {}
                query_executed = True
            except Exception as exc:
                stats_raw = {
                    "rows": [],
                    "meta": {"error": f"material_usage_top_per_year_season hatası: {exc}"},
                }
                query_executed = True

            examples = []

        # ─────────────────────────────────────────────────────────────────────────
        # TOP ENTITIES: Malzeme listeleri (tek dimension)
        # ─────────────────────────────────────────────────────────────────────────
        elif (
            intent == QuestionType.MATERIAL_USAGE
            and shape == OutputShape.TOP_LIST
            and plan is not None
            and isinstance(plan.group_by, list)
            and "materialName" in plan.group_by
            and "year" not in plan.group_by
            and "season" not in plan.group_by
            and "month" not in plan.group_by
            and "vehicleType" not in plan.group_by
            and "manufacturer" not in plan.group_by
        ):
            try:
                period = resolve_period_spec(analysis, plan, qn_norm)

                top_period = _canonical_period_to_top_entities_period(period)
                top_limit = plan.limit or stats_limit

                vehicle_filter = None
                if analysis.entities.vehicle_ids:
                    vehicle_filter = analysis.entities.vehicle_ids[0]

                top_question = TopEntitiesQuestion(
                    entity_type="material",
                    limit=top_limit,
                    service_filter=None,
                    period=top_period,
                    material_filter=None,
                    model_filter=None,
                    vehicle_filter=vehicle_filter,
                )

                stats_raw = _LRS.answer_top_entities_question(top_question) or {}
                query_executed = True
            except Exception as exc:
                stats_raw = {
                    "rows": [],
                    "meta": {"error": f"answer_top_entities_question hatası: {exc}"},
                }
                query_executed = True

            examples = []

        # ─────────────────────────────────────────────────────────────────────────
        # 🆕 DIMENSION BAZLI TOP_PER_GROUP (vehicleModel, vehicleType için)
        # ─────────────────────────────────────────────────────────────────────────
        elif (
            intent == QuestionType.MATERIAL_USAGE
            and shape == OutputShape.TOP_PER_GROUP
            and plan is not None
            and isinstance(plan.group_by, list)
            and len(plan.group_by) > 0
            and plan.group_by[0] in ("vehicleModel", "vehicleType")
            and "mevsim" not in qn_norm  # Mevsimsel sorular yukarıda handle edildi
        ):
            group_dimension = plan.group_by[0]
            period = resolve_period_spec(analysis, plan, qn_norm)

            # Period'u LRS'in beklediği formata çevir
            dimension_period = None
            if period:
                if period.kind == "relative":
                    if period.unit == "year" and period.value:
                        dimension_period = {"kind": "last_n_years", "years": period.value}
                    elif period.unit == "month" and period.value:
                        dimension_period = {"kind": "last_n_months", "months": period.value}
                elif period.kind == "year" and period.year:
                    dimension_period = {"kind": "year", "year": period.year}

            # Limit per group belirleme
            limit_per_group = 5
            if analysis.entities.has_top_signal:
                limit_per_group = analysis.entities.top_limit
            elif plan and plan.limit:
                limit_per_group = plan.limit
            elif analysis.matched_cq and analysis.matched_cq.default_limit:
                limit_per_group = analysis.matched_cq.default_limit

            try:
                stats_raw = _LRS.material_usage_top_per_dimension(
                    group_dimension=group_dimension,
                    period=dimension_period,
                    limit_per_group=limit_per_group,
                    limit=stats_limit,
                ) or {}
                query_executed = True
            except Exception as exc:
                stats_raw = {
                    "rows": [],
                    "meta": {"error": f"material_usage_top_per_dimension hatası: {exc}"},
                }
                query_executed = True

            examples = []

        # ─────────────────────────────────────────────────────────────────────────
        # NORMAL YOL: QueryPlan + run_query
        # ─────────────────────────────────────────────────────────────────────────
        elif plan is None:
            stats_raw = {
                "rows": [],
                "meta": {
                    "empty_reason": "query_plan_missing",
                    "message": "Bu soru için QueryPlan üretilemedi.",
                },
            }
            examples = []
            query_executed = False

        else:
            # Period hesaplama
            try:
                period = resolve_period_spec(analysis, plan, qn_norm)
            except Exception:
                period = None

            # Rölatif dönemlerde anchor şart: datetime.now() fallback YOK.
            anchor = _get_anchor_date() if period is not None else None
            if period is not None and getattr(period, "kind", None) == "relative" and anchor is None:
                stats_raw = {
                    "rows": [],
                    "meta": {
                        "empty_reason": "anchor_date_missing",
                        "message": "Rölatif dönem (son N ay/yıl) çözülemedi: LRS içinde operationDate tabanlı anchor date bulunamadı.",
                    },
                }
                examples = []
                query_executed = False  # sorgu koşmadı (ön koşul sağlanmadı)

            else:
                # time_range enjekte et
                if plan.time_range is None and period is not None:
                    try:
                        tr = _period_to_time_range(period, anchor_date=anchor)
                        if tr is not None:
                            plan.time_range = tr
                    except Exception as exc:
                        if getattr(period, "kind", None) == "relative":
                            stats_raw = {
                                "rows": [],
                                "meta": {
                                    "empty_reason": "period_unresolvable",
                                    "message": f"Rölatif dönem çözümlenirken hata oluştu: {exc}",
                                },
                            }
                            examples = []
                            query_executed = False
                        else:
                            stats_raw = {}

                # Generic LRS query fallback (domain branch yoksa burası koşar)
                if (not isinstance(stats_raw, dict)) or ("rows" not in stats_raw):
                    try:
                        stats_raw = _LRS.run_query(plan, limit=stats_limit) or {}
                        query_executed = True
                    except Exception as exc:
                        stats_raw = {"rows": [], "meta": {"error": f"LRS.run_query hatası: {exc}"}}
                        query_executed = True

                # Normalize et (rows her zaman list olsun)
                stats_raw = _ensure_stats_raw(stats_raw, default_error=None)

                # Örnek xAPI kayıtları
                try:
                    example_docs = _LRS.get_example_statements(plan, limit=MAX_EXAMPLE_STATEMENTS)
                except Exception:
                    example_docs = []
                examples = _build_examples_from_docs(_LRS, example_docs)

                # ─────────────────────────────────────────────────────────────────────
                # 🧠 Self-healing retry:
                # Eğer rows boşsa ve materialName_contains gibi "daraltıcı" bir filtre varsa,
                # (özellikle fallback keyword kaynaklı) filtreyi kaldırıp 1 kez daha dene.
                # ─────────────────────────────────────────────────────────────────────
                try:
                    if (
                        query_executed
                        and isinstance(stats_raw, dict)
                        and isinstance(plan, QueryPlan)
                        and isinstance(getattr(plan, "filters", None), dict)
                    ):
                        rows0 = stats_raw.get("rows") or []
                        has_material_filter = "materialName_contains" in plan.filters

                        # quoted kaynaklı keyword'e dokunma (kullanıcı özellikle istemiş olabilir)
                        kw_source = getattr(getattr(analysis, "entities", None), "material_keywords_source", None)
                        allow_retry = (kw_source != "quoted")

                        if (not rows0) and has_material_filter and allow_retry:
                            removed_kw = plan.filters.pop("materialName_contains", None)
                            stats_retry = _LRS.run_query(plan, limit=stats_limit) or {}

                            # retry daha iyi ise onu al
                            rows1 = (stats_retry.get("rows") or []) if isinstance(stats_retry, dict) else []
                            if rows1:
                                stats_raw = _ensure_stats_raw(stats_retry, default_error=None)

                            # meta'ya self-heal bilgisi yaz
                            if isinstance(stats_raw, dict):
                                stats_raw.setdefault("meta", {})
                                if isinstance(stats_raw["meta"], dict):
                                    stats_raw["meta"]["self_heal"] = {
                                        "attempted": True,
                                        "action": "removed materialName_contains",
                                        "removed_keyword": removed_kw,
                                        "rows_before": len(rows0),
                                        "rows_after": len(rows1),
                                        "successful": bool(rows1),
                                    }
                except Exception:
                    pass

            # Satır dönmediyse: sadece sorgu gerçekten çalıştıysa "no_matching_rows" koy
            try:
                if isinstance(stats_raw, dict):
                    rows = stats_raw.get("rows") or []
                    meta = stats_raw.get("meta")
                    if (not rows) and query_executed and (not isinstance(meta, dict) or not meta.get("empty_reason")):
                        stats_raw.setdefault("meta", {})
                        stats_raw["meta"]["empty_reason"] = "no_matching_rows"
                        stats_raw["meta"]["message"] = "Sorgu çalıştı ama filtrelerle eşleşen kayıt bulunamadı. Filtreler çok dar olabilir."
                        stats_raw["meta"]["applied_filters"] = asdict(plan) if plan is not None else None
            except Exception:
                pass

        # Her durumda meta’ya “query_executed” yaz (UI debug için altın değer)
        if isinstance(stats_raw, dict):
            stats_raw.setdefault("meta", {})
            if isinstance(stats_raw["meta"], dict):
                stats_raw["meta"]["query_executed"] = bool(query_executed)

        # 5) StatsTable üret
        table = _build_stats_table(stats_raw, analysis, plan)

        # 6) LLM yorumu (isteğe bağlı)
        llm_analysis: Optional[LLMAnalysis] = None
        if request.use_llm:
            llm_analysis = _call_llm(
                request=request,
                analysis=analysis,
                table=table,
                examples=examples,
            )

        # 7) ChatResponse
        stats_with_meta = dict(stats_raw or {})
        if isinstance(table.meta, dict):
            stats_with_meta.setdefault("meta", table.meta)

        scenario = f"intent:{intent.value}|shape:{shape.value}"

        analysis_details = analysis.analysis_details or {}
        normalized_query = analysis_details.get("normalized_query")
        original_query = analysis_details.get("original_query")

        if normalized_query:
            summary = f"Normalize: {normalized_query} | Intent: {intent.value} | Shape: {shape.value}"
        elif original_query:
            summary = f"Soru: {original_query}"
        else:
            summary = f"Intent: {intent.value}, Shape: {shape.value}"

        response = ChatResponse(
            intent=legacy_intent,
            scenario=scenario,
            summary=summary,
            data=stats_with_meta,
            tables=[table],
            examples=examples,
            llm=llm_analysis,
        )

        return response

    except Exception as exc:
        tb = traceback.format_exc()

        logger.error(
            f"[CHAT_ERROR][{trace_id}][ENV={ENV}] {exc}\n{tb}"
        )

        safe_message = "Sorgu işlenirken beklenmeyen bir hata oluştu."
        debug_message = str(exc)
        debug_enabled = DEBUG or getattr(request, "debug", False)

        error_payload = {
            "error": {
                "type": exc.__class__.__name__,
                "message": debug_message if debug_enabled else safe_message,
                "trace_id": trace_id,
                "stage": "orchestrator",
                "env": ENV,
            },
            "meta": {
                "normalized_query": getattr(
                    analysis.analysis_details if analysis else {}, "normalized_query", None
                ),
                "query_plan": asdict(plan) if plan else None,
            },
        }

        return ChatResponse(
            intent="error",
            scenario="internal_error",
            summary=f"⚠️ Sistem hatası (trace_id={trace_id})",
            data=error_payload,
            tables=[],
            examples=[],
            llm=None,
        )
