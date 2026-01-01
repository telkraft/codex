"""
prompt_builder_archive.py
=========================

Bu dosya, prompt_builder.py'dan kaldırılan ancak ileride kullanılabilecek
eski fonksiyonları içerir.

TARİH: 2024
NEDEN: orchestrator.py sadece build_stats_prompt kullanıyor.
       Diğer fonksiyonlar ölü kod durumundaydı.

KULLANIM: İhtiyaç halinde buradan kopyalayıp aktif dosyaya eklenebilir.
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional
from collections import defaultdict

# Not: Bu fonksiyonları kullanmak için aşağıdaki import'lar gerekli:
# from models import StatsTable, ExampleStatement, QueryPlan
# from prompt_builder import (
#     _build_role_block, _build_period_block, 
#     stats_table_to_markdown, COLUMN_LABEL_MAP_TR, STYLE_STATS
# )


# ============================================================================
# KULLANILMAYAN STYLE DICT'LER
# ============================================================================

STYLE_TOP_ENTITIES = {
    "balanced": """
Cevap KESİNLİKLE aşağıdaki 3 başlık altında sunulmalıdır:

## 1. Veri Fotoğrafı
- Listeyi aynen kullan (isim + adet).
- Sayısal değerleri UYDURMA, YUVARLAMA veya YENİDEN HESAPLAMA.

## 2. Rolün Yorumu
- Yalnızca seçilen rolün perspektifinden yorum yap.
- Rol tanımına ve KPI'lara dayandır.

## 3. Rol Bazlı Öneriler
- En az 3 somut öneri yaz.
- Her öneri listedeki varlıklardan en az birini ismen referans alsın.

Genel:
- Cevap sadece Türkçe olacak.
""",
    "commentary": """
Cevabı aşağıdaki 2 başlık altında sun:

## 1. Kısa Veri Özeti
- En baskın 3–5 varlığı isim + adet ile özetle.

## 2. Yorum ve Hızlı Öneriler
- Seçilen rolün bakış açısından en önemli 2–3 bulguyu anlat.
- En az 2 somut öneri yaz.
""",
    "predictive": """
## 1. Mevcut Durum Özeti
## 2. Olası Senaryolar
## 3. Riskler ve Fırsatlar
""",
    "report": """
## 1. Yönetici Özeti
## 2. Veri Analizi
## 3. Bulgular
## 4. Öneriler ve Önceliklendirme
"""
}


STYLE_PRICE_TREND = {
    "balanced": """
## 1. Fiyat Değişim Özeti
## 2. Yorum
## 3. Öneriler
""",
    "commentary": "...",
    "predictive": "...",
    "report": "..."
}


STYLE_FAMILY_TREND = {
    "balanced": """
## 1. Aile Bazlı Fiyat Trend Özeti
## 2. Yorum
## 3. Öneriler
""",
}


STYLE_NEXT_MAINTENANCE = {
    "balanced": """
## 1. Sonraki Bakım Paternleri
## 2. Yorum
## 3. Öneriler
""",
}


STYLE_VEHICLE_HISTORY = {
    "balanced": """
## 1. Araç Bakım Geçmişi Özeti
## 2. Yorum
## 3. Öneriler
""",
}


STYLE_PIVOT = {
    "balanced": """
## 1. Pivot Tablo Özeti
## 2. Yorum
## 3. Öneriler
""",
}


STYLE_SEASONAL = {
    "balanced": """
## 1. Mevsimsel Kullanım Özeti
## 2. Patern Analizi
## 3. Öneriler
""",
}


# ============================================================================
# KULLANILMAYAN PROMPT FONKSİYONLARI
# ============================================================================

def build_top_entities_prompt(
    user_query: str,
    plan,  # QueryPlan
    table,  # StatsTable
    meta=None,
    role: Optional[str] = None,
    behavior: Optional[str] = None,
) -> str:
    """
    'En çok gelen ...' tipi sorular için LLM prompt'unu üretir.
    
    DURUM: KULLANILMIYOR (orchestrator.py build_stats_prompt kullanıyor)
    """
    # Bu fonksiyonun implementasyonu için eski prompt_builder.py'a bakın
    raise NotImplementedError("Bu fonksiyon arşivlenmiştir. build_stats_prompt kullanın.")


def build_material_price_trend_prompt(
    user_query: str,
    plan,
    table,
    meta=None,
    role: Optional[str] = None,
    behavior: Optional[str] = None,
) -> str:
    """
    Tekil malzeme fiyat trend soruları için prompt.
    
    DURUM: KULLANILMIYOR
    """
    raise NotImplementedError("Bu fonksiyon arşivlenmiştir. build_stats_prompt kullanın.")


def build_material_family_price_trend_prompt(
    user_query: str,
    plan,
    table,
    meta=None,
    role: Optional[str] = None,
    behavior: Optional[str] = None,
) -> str:
    """
    Malzeme ailesi bazında fiyat trend soruları için prompt.
    
    DURUM: KULLANILMIYOR
    """
    raise NotImplementedError("Bu fonksiyon arşivlenmiştir. build_stats_prompt kullanın.")


def build_next_maintenance_prompt(
    user_query: str,
    plan,
    table,
    meta=None,
    role: Optional[str] = None,
    behavior: Optional[str] = None,
) -> str:
    """
    Sonraki bakım tahmini soruları için prompt.
    
    DURUM: KULLANILMIYOR
    """
    raise NotImplementedError("Bu fonksiyon arşivlenmiştir. build_stats_prompt kullanın.")


def build_vehicle_history_prompt(
    user_query: str,
    plan,
    table,
    examples,  # List[ExampleStatement]
    meta=None,
    role: Optional[str] = None,
    behavior: Optional[str] = None,
) -> str:
    """
    Araç geçmişi soruları için prompt.
    
    DURUM: KULLANILMIYOR
    """
    raise NotImplementedError("Bu fonksiyon arşivlenmiştir. build_stats_prompt kullanın.")


def build_pivot_material_usage_prompt(
    user_query: str,
    plan,
    table,
    meta=None,
    role: Optional[str] = None,
    behavior: Optional[str] = None,
) -> str:
    """
    Pivot tablo formatında malzeme kullanımı soruları için prompt.
    
    DURUM: KULLANILMIYOR
    """
    raise NotImplementedError("Bu fonksiyon arşivlenmiştir. build_stats_prompt kullanın.")


def build_generic_qa_prompt(
    user_query: str,
    plan,
    table,
    examples,
    meta=None,
    role: Optional[str] = None,
    behavior: Optional[str] = None,
) -> str:
    """
    Genel soru-cevap promptu.
    
    DURUM: KULLANILMIYOR
    """
    raise NotImplementedError("Bu fonksiyon arşivlenmiştir. build_stats_prompt kullanın.")


# ============================================================================
# KULLANILMAYAN YARDIMCI FONKSİYONLAR
# ============================================================================

def examples_to_markdown(examples) -> str:
    """
    ExampleStatement listesini markdown'a çevirir.
    
    DURUM: KULLANILMIYOR
    """
    if not examples:
        return "_Örnek yok_"
    return "\n".join(f"- {e.text}" for e in examples)


def vehicle_history_to_summary(
    rows: List[Dict[str, Any]],
    max_lines: int = 10,
    max_materials: int = 10,
) -> str:
    """
    Araç geçmişi satırlarını özetler ve malzeme bazında frekans bilgisi üretir.
    
    DURUM: KULLANILMIYOR (orchestrator.py bu fonksiyonu çağırmıyor)
    """
    if not rows:
        return "_Kayıt bulunamadı_"

    total_rows = len(rows)

    # Malzeme frekans analizi
    material_stats = defaultdict(
        lambda: {
            "count": 0,
            "total_qty": 0.0,
            "total_cost": 0.0,
            "last_date": None,
            "last_km": None,
            "verb_types": set(),
        }
    )

    for r in rows:
        name = r.get("materialName") or "Bilinmeyen Malzeme"
        stat = material_stats[name]

        stat["count"] += 1

        qty = r.get("quantity")
        if isinstance(qty, (int, float)):
            stat["total_qty"] += qty

        cost = r.get("cost")
        if isinstance(cost, (int, float)):
            stat["total_cost"] += cost

        date = r.get("date")
        if isinstance(date, str):
            if stat["last_date"] is None or date > stat["last_date"]:
                stat["last_date"] = date

        km = r.get("km")
        if isinstance(km, (int, float)):
            stat["last_km"] = km

        verb = r.get("verbType")
        if isinstance(verb, str):
            stat["verb_types"].add(verb)

    # En sık kullanılan malzemeleri sırala
    material_items = sorted(
        material_stats.items(),
        key=lambda kv: (-kv[1]["count"], kv[0].lower()),
    )
    material_items = material_items[:max_materials]

    # Örnek kayıtları seç
    if total_rows > max_lines:
        head = rows[: max_lines // 2]
        tail = rows[-(max_lines // 2):]
        summary_rows = head + tail
    else:
        summary_rows = rows

    # Metni oluştur
    lines: List[str] = []
    lines.append(f"Toplam Kayıt Sayısı: {total_rows}")
    lines.append("")
    lines.append("--- Malzeme Frekans Özeti (en sık görülenler) ---")

    for name, stat in material_items:
        count = stat["count"]
        total_qty = stat["total_qty"]
        total_cost = stat["total_cost"]
        last_date = stat["last_date"] or "bilinmiyor"
        last_km = stat["last_km"]
        verb_types = ", ".join(sorted(stat["verb_types"])) if stat["verb_types"] else "bilinmiyor"

        extra_parts = [f"{count} kayıt"]
        if total_qty:
            extra_parts.append(f"toplam adet: {int(total_qty) if total_qty.is_integer() else total_qty}")
        if total_cost:
            extra_parts.append(f"toplam maliyet: {round(total_cost, 2)}")

        meta_parts = [f"son tarih: {last_date}", f"işlem türleri: {verb_types}"]
        if last_km is not None:
            meta_parts.append(f"son km: {last_km}")

        lines.append(
            f"- {name}: " +
            ", ".join(extra_parts) +
            f" ({'; '.join(meta_parts)})"
        )

    lines.append("")
    lines.append("--- Örnek Kayıtlar ---")

    for r in summary_rows:
        date = str(r.get("date") or "Tarih Yok")
        material = r.get("materialName", "Malzeme Yok")
        cost = r.get("cost", "Maliyet Yok")
        km = r.get("km")
        verb = r.get("verbType")

        extra = []
        if km is not None:
            extra.append(f"km: {km}")
        if verb:
            extra.append(f"işlem: {verb}")

        extra_str = f" ({', '.join(extra)})" if extra else ""
        lines.append(f"- Tarih: {date}, Malzeme: {material}, Maliyet: {cost}{extra_str}")

    if total_rows > max_lines:
        lines.insert(
            len(lines) - len(summary_rows),
            f"... {total_rows - max_lines} adet kayıt özet dışında bırakıldı ..."
        )

    return "\n".join(lines)


# ============================================================================
# ARŞİV NOTU
# ============================================================================
"""
Bu fonksiyonların neden arşivlendiği:

1. build_top_entities_prompt: orchestrator.py artık tüm sorgular için 
   build_stats_prompt kullanıyor. 2-katmanlı mimari (intent + shape) 
   sayesinde tek bir genel fonksiyon yeterli.

2. build_material_price_trend_prompt: Aynı sebep.

3. build_next_maintenance_prompt: Aynı sebep.

4. build_vehicle_history_prompt: Aynı sebep.

5. build_pivot_material_usage_prompt: Aynı sebep.

6. build_generic_qa_prompt: Aynı sebep.

7. vehicle_history_to_summary: Bu fonksiyon hiçbir zaman orchestrator'dan 
   çağrılmadı. Muhtemelen eski bir prototipten kalmış.

8. examples_to_markdown: ExampleStatement'lar artık farklı şekilde işleniyor.

Eğer bu fonksiyonlardan birini tekrar aktif etmek gerekirse:
1. Bu dosyadan kopyalayın
2. prompt_builder.py'a yapıştırın
3. Gerekli import'ları ekleyin
4. orchestrator.py'da kullanın
"""