"""
prompt_builder.py (Temizlenmiş Versiyon)
========================================

Bu modül, LLM promptlarını üretir.
- Rol (ROLE_DEFS) = KİM konuşuyor?
- Stil blokları (STYLE_STATS) = NASIL konuşuyor?

Semantik metadata (kolon açıklamaları, intent/shape tanımları) için:
→ services.prompt_ontology modülüne bakın.

ÖNEMLİ: Bu dosya sadece aktif olarak kullanılan fonksiyonları içerir.
Eski fonksiyonlar prompt_builder_archive.py dosyasına taşınmıştır.
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional

from models import StatsTable, QueryPlan

# Ontology modülünden import
from services.prompt_ontology import (
    COLUMN_DEFS_EXTENDED,
    get_table_context_from_analysis,
)


# ============================================================================
# TABLO KOLON SÖZLÜĞÜ (Label Mapping)
# ============================================================================

COLUMN_DEFS = [
    {"key": "vehicleType", "label_tr": "Araç Tipi"},
    {"key": "vehicleModel", "label_tr": "Araç Modeli"},
    {"key": "vehicle", "label_tr": "Araç"},
    {"key": "vehicleId", "label_tr": "Araç ID"},
    {"key": "customerId", "label_tr": "Müşteri"},
    {"key": "serviceLocation", "label_tr": "Servis Lokasyonu"},

    {"key": "materialName", "label_tr": "Malzeme"},
    {"key": "materialFamily", "label_tr": "Malzeme Ailesi"},
    {"key": "materialCode", "label_tr": "Malzeme Kodu"},

    {"key": "faultCode", "label_tr": "Arıza Kodu"},
    {"key": "verbType", "label_tr": "İşlem Tipi"},

    {"key": "year", "label_tr": "Yıl"},
    {"key": "month", "label_tr": "Ay"},
    {"key": "season", "label_tr": "Mevsim"},
    {"key": "date", "label_tr": "Tarih"},
    {"key": "week", "label_tr": "Hafta"},
    {"key": "service", "label_tr": "Servis"},

    {"key": "km", "label_tr": "Km"},
    {"key": "quantity", "label_tr": "Miktar"},
    {"key": "cost", "label_tr": "Maliyet"},

    # Trend tabloları
    {"key": "firstDate", "label_tr": "İlk Tarih"},
    {"key": "lastDate", "label_tr": "Son Tarih"},
    {"key": "firstPrice", "label_tr": "İlk Fiyat"},
    {"key": "lastPrice", "label_tr": "Son Fiyat"},
    {"key": "changeAbs", "label_tr": "Fark"},
    {"key": "changePct", "label_tr": "Değişim (%)"},
    {"key": "observations", "label_tr": "Gözlem Sayısı"},
    {"key": "avgChangePct", "label_tr": "Ort. Değişim (%)"},
    {"key": "materialsCount", "label_tr": "Malzeme Sayısı"},

    # Top / aggregate
    {"key": "entity", "label_tr": "Varlık"},
    {"key": "entity_type", "label_tr": "Varlık Tipi"},
    {"key": "count", "label_tr": "Adet"},
    {"key": "sum_cost", "label_tr": "Toplam Maliyet"},
    {"key": "avg_km", "label_tr": "Ortalama Km"},
    {"key": "avg_cost", "label_tr": "Ortalama Maliyet"},
    {"key": "sum_quantity", "label_tr": "Toplam Miktar"},

    # Pattern / sequence
    {"key": "material", "label_tr": "Malzeme"},
    {"key": "ratio", "label_tr": "Oran (%)"},
    {"key": "probability", "label_tr": "Olasılık (%)"},
    {"key": "percentage", "label_tr": "Yüzde (%)"},
]

COLUMN_LABEL_MAP_TR = {c["key"]: c["label_tr"] for c in COLUMN_DEFS}


# ============================================================================
# ROL TANIMLARI (Kimin perspektifinden konuşuluyor?)
# ============================================================================

ROLE_DEFS = {
    "servis_analisti": {
        "title": "Servis Analisti",
        "perspective": "operasyonel verimlilik ve bakım kalitesi",
        "focus": [
            "Bakım sürelerini ve sıklıklarını optimize etme",
            "Parça kullanım paternlerini analiz etme",
            "Servis kapasitesini planlama",
        ],
    },
    "filo_yoneticisi": {
        "title": "Filo Yöneticisi",
        "perspective": "araç kullanılabilirliği ve maliyet kontrolü",
        "focus": [
            "Araç downtime'ını minimize etme",
            "Bakım maliyetlerini izleme",
            "Filo performansını karşılaştırma",
        ],
    },
    "teknik_uzman": {
        "title": "Teknik Uzman",
        "perspective": "teknik arıza analizi ve kök neden tespiti",
        "focus": [
            "Arıza paternlerini tespit etme",
            "Tekrar eden sorunları analiz etme",
            "Önleyici bakım önerileri geliştirme",
        ],
    },
    "musteri_temsilcisi": {
        "title": "Müşteri Temsilcisi",
        "perspective": "müşteri memnuniyeti ve iletişim",
        "focus": [
            "Müşteriye anlaşılır bilgi sunma",
            "Bakım geçmişini özetleme",
            "Maliyet ve süre beklentilerini yönetme",
        ],
    },
    "egitmen": {
        "title": "Teknik Eğitmen",
        "perspective": "bilgi aktarımı, yetkinlik geliştirme ve eğitim ihtiyaç analizi",
        "focus": [
            "Sık karşılaşılan arıza ve bakım konularında eğitim ihtiyacı belirleme",
            "Teknisyen yetkinlik açıklarını tespit etme",
            "Pratik eğitim içeriği ve vaka çalışması önerileri geliştirme",
            "Mevsimsel veya dönemsel eğitim planlaması yapma",
        ],
    },
    "tedarik_zinciri_uzmani": {
        "title": "Tedarik Zinciri Uzmanı",
        "perspective": "parça bulunabilirliği, tedarik riski ve maliyet sürekliliği",
        "focus": [
            "Sık kullanılan ve kritik malzemeleri tespit etme",
            "Mevsimsel ve dönemsel talep dalgalanmalarını analiz etme",
            "Stok-outs ve aşırı stok risklerini değerlendirme",
            "Fiyat artış trendlerine göre tedarik stratejisi önerme",
            "Alternatif parça veya tedarikçi ihtiyacını işaretleme",
        ],
    },
    "cto": {
        "title": "CTO",
        "perspective": "sistem mimarisi, veri tutarlılığı ve ölçeklenebilirlik",
        "focus": [
            "Veri kalitesi ve tutarlılığına dair riskleri işaretleme",
            "Sistemler arası entegrasyon sorunlarını ortaya koyma",
            "Mevcut analizlerin otomasyon ve standardizasyon potansiyelini değerlendirme",
            "Teknik borç ve sürdürülebilirlik açısından uyarılar üretme",
            "AI / analitik yatırımlarının mimari etkisini özetleme",
        ],
    },
}


# ============================================================================
# DAVRANIŞ TANIMLARI (Cevap formatı ve derinliği)
# ============================================================================

BEHAVIOR_DEFS = {
    "balanced": {
        "name": "Analitik Yaklaşım",
        "description": "Hem özet hem detay içeren standart analiz",
        "output_style": "structured",
    },
    "commentary": {
        "name": "Yorumlayıcı",
        "description": "Kısa ve öz, yoruma ağırlık veren",
        "output_style": "concise",
    },
    "predictive": {
        "name": "Hipotez Üreten",
        "description": "Senaryolar ve gelecek projeksiyonları",
        "output_style": "scenario-based",
    },
    "report": {
        "name": "Rapor Oluşturan",
        "description": "Yönetici özeti formatında detaylı analiz",
        "output_style": "executive",
    },
}


# ============================================================================
# YARDIMCI FONKSİYONLAR
# ============================================================================

def _get_role_def(role: Optional[str]) -> Dict[str, Any]:
    """Rol tanımını getirir, yoksa default döner."""
    if not role:
        return ROLE_DEFS.get("servis_analisti", {})
    return ROLE_DEFS.get(role.lower(), ROLE_DEFS.get("servis_analisti", {}))


def _get_behavior_def(behavior: Optional[str]) -> Dict[str, Any]:
    """Davranış tanımını getirir, yoksa default döner."""
    if not behavior:
        return BEHAVIOR_DEFS.get("balanced", {})
    return BEHAVIOR_DEFS.get(behavior.lower(), BEHAVIOR_DEFS.get("balanced", {}))


def _build_role_block(role: Optional[str], behavior: Optional[str] = None) -> str:
    """
    Rol + davranış açıklamasını içeren prompt bloğu oluşturur.
    """
    role_def = _get_role_def(role)
    behavior_def = _get_behavior_def(behavior)

    title = role_def.get("title", "Analist")
    perspective = role_def.get("perspective", "genel analiz")
    focus_list = role_def.get("focus", [])
    
    behavior_name = behavior_def.get("name", "Dengeli")
    behavior_desc = behavior_def.get("description", "")

    focus_text = ""
    if focus_list:
        focus_items = "\n".join(f"  - {f}" for f in focus_list)
        focus_text = f"\nOdak alanların:\n{focus_items}"

    return f"""Rolün:
Sen MAN Türkiye servis bakım verisi üzerinde çalışan bir {title.upper()} yapay zekâsın.
Perspektifin: {perspective}.
{focus_text}

Davranış modu: {behavior_name}
{behavior_desc}
""".strip()


def _build_period_block(meta: Optional[Dict[str, Any]]) -> str:
    """Analiz dönemi bilgisini döner."""
    if not meta:
        return ""
    txt = meta.get("effective_period_text")
    if not txt:
        return ""
    return f"Analiz dönemi: {txt}."


# ============================================================================
# MARKDOWN YARDIMCILARI
# ============================================================================

def rows_to_markdown_table(
    rows: List[Dict[str, Any]],
    label_map: Optional[Dict[str, str]] = None,
) -> str:
    """Dict listesini Markdown tablosuna çevirir."""
    if not rows:
        return "_Tablo boş_"
    
    raw_headers = list(rows[0].keys())
    headers = [label_map.get(h, h) for h in raw_headers] if label_map else raw_headers

    lines = []
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("| " + " | ".join(["---"] * len(headers)) + " |")

    for r in rows:
        values = [str(r.get(h, "")) for h in raw_headers]
        lines.append("| " + " | ".join(values) + " |")

    return "\n".join(lines)


def stats_table_to_markdown(
    table: StatsTable,
    label_map: Optional[Dict[str, str]] = None,
) -> str:
    """StatsTable'ı Markdown tablosuna çevirir."""
    rows = table.rows or []
    return rows_to_markdown_table(rows, label_map=label_map)


# ============================================================================
# STİL BLOKLARI (Sadece STATS için - aktif olarak kullanılan)
# ============================================================================

STYLE_STATS = {
    "balanced": """
Cevabı aşağıdaki 3 başlık altında sun:

## 1. Özet
- Verideki en önemli 2-3 bulguyu kısaca özetle.
- Sayıları veride gördüğün gibi kullan; yeni değer üretme.

## 2. Detaylı Analiz
- Verideki paternleri ve dikkate değer noktaları açıkla.
- Gerekirse karşılaştırmalar yap.

## 3. Öneriler
- En az 2 somut aksiyon önerisi ver.
- Önerileri verideki bulgulara dayandır.

Genel:
- Veri dışında yeni sayı, oran veya tarih üretme.
- Cevap Türkçe ve kurumsal olacak.
""",

    "commentary": """
Cevabı aşağıdaki 2 başlık altında sun:

## 1. Anahtar Bulgular
- En önemli 2-3 bulguyu tek cümleyle özetle.
- Sayıları veride gördüğün gibi kullan.

## 2. Yorum ve Hızlı Öneriler
- Kısa bir yorum ekle.
- 1-2 pratik öneri ver.

Genel:
- Kısa, net ve veri odaklı yaz.
- Gereksiz detaydan kaçın.
""",

    "predictive": """
Cevabı aşağıdaki 3 başlık altında sun:

## 1. Mevcut Durum
- Verideki temel paternleri özetle.
- Yalnızca verideki değerleri referans al.

## 2. Olası Senaryolar
- Bu patern devam ederse en az 2 olası senaryo yaz.
- Senaryolarda somut varlık isimlerini kullan.

## 3. Riskler ve Fırsatlar
- Her senaryo için en az bir risk ve bir fırsat tanımla.

Genel:
- Tahminleri kesinlik olarak değil, senaryo olarak anlat.
- Yeni rakam üretme; nitel ifadelerle konuş.
""",

    "report": """
Cevabı aşağıdaki 4 başlık altında rapor formatında sun:

## 1. Yönetici Özeti
- 3-5 cümleyle temel bulguları özetle.

## 2. Detaylı Analiz
- Verideki paternleri ve kritik noktaları anlat.
- Gerekirse karşılaştırmalar yap.

## 3. Bulgular
- En az 3 madde halinde önemli paternleri yaz.
- Her bulguyu veriye dayandır.

## 4. Öneriler ve Önceliklendirme
- En az 3 somut aksiyon önerisi yaz.
- Her öneriye Yüksek / Orta / Düşük öncelik etiketi ekle.

Genel:
- Resmi ama okunabilir Türkçe kullan.
- Yeni sayı veya tarih üretme.
"""
}


# ============================================================================
# ANA PROMPT FONKSİYONU
# ============================================================================

def build_stats_prompt(
    user_query: str,
    plan: QueryPlan,
    table: StatsTable,
    meta: Optional[Dict[str, Any]] = None,
    role: Optional[str] = None,
    behavior: Optional[str] = None,
    context_block: Optional[str] = None,
) -> str:
    """
    İstatistik soruları için LLM prompt'unu üretir.
    
    Args:
        user_query: Kullanıcının orijinal sorusu
        plan: QueryPlan (şu an kullanılmıyor ama API uyumluluğu için tutuluyor)
        table: StatsTable - LLM'e gönderilecek tablo
        meta: Ek metadata (question_type, output_shape, entities, period vb.)
        role: Rol tanımı (servis_analisti, filo_yoneticisi, vb.)
        behavior: Davranış modu (balanced, commentary, predictive, report)
        context_block: Önceden oluşturulmuş tablo bağlam bloğu (opsiyonel)
    
    Returns:
        LLM'e gönderilecek tam prompt metni
    """
    # Rol + davranış bloğu
    role_block = _build_role_block(role, behavior)

    # Davranışa göre uygun stil bloğunu seç
    behavior_key = (behavior or "balanced").lower()
    style_block = STYLE_STATS.get(behavior_key, STYLE_STATS["balanced"])

    # Tablo markdown
    table_md = stats_table_to_markdown(table, label_map=COLUMN_LABEL_MAP_TR)
    
    # Dönem bilgisi
    period_block = _build_period_block(meta)
    
    # Context block yoksa ve meta varsa otomatik üret
    if context_block is None and meta:
        qtype = meta.get("question_type", "maintenance_history")
        qshape = meta.get("output_shape", "top_list")
        table_rows = table.rows if isinstance(table, StatsTable) else []
        
        if table_rows:
            context_block = get_table_context_from_analysis(
                user_query=user_query,
                table_rows=table_rows,
                question_type=qtype,
                output_shape=qshape,
                meta=meta,
                label_map=COLUMN_LABEL_MAP_TR,
            )
    
    # Context section
    context_section = ""
    if context_block:
        context_section = f"""
{context_block}

---
"""

    return f"""
{role_block}

{style_block}

{context_section}Aşağıda MAN Türkiye bakım & onarım verilerinden oluşan özet veri bulunuyor.

Kullanıcının sorusu:
\"\"\"{user_query}\"\"\"

{period_block}

İstatistik verisi:
{table_md}

Lütfen yukarıdaki tablo bağlamını ve kolon açıklamalarını dikkate alarak,
format ve davranış moduna uygun şekilde cevapla.
""".strip()


# ============================================================================
# BACKWARD COMPATIBILITY EXPORTS
# ============================================================================

# Eski kodlarla uyumluluk için export edilen isimler
# (orchestrator.py sadece build_stats_prompt kullanıyor)

__all__ = [
    "build_stats_prompt",
    "stats_table_to_markdown",
    "rows_to_markdown_table",
    "COLUMN_LABEL_MAP_TR",
    "COLUMN_DEFS",
    "ROLE_DEFS",
    "BEHAVIOR_DEFS",
]