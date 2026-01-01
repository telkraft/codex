# period_utils.py
"""
Period Utility Fonksiyonları
============================

Tarih/dönem hesaplamaları için yardımcı fonksiyonlar.

- build_period_from_entities: ExtractedEntities → PeriodSpec
- period_to_time_range: PeriodSpec → TimeRange
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from models import PeriodSpec, TimeRange

# Type hint için import (circular import'u önlemek için TYPE_CHECKING)
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .router_models import ExtractedEntities


# ============================================================================
# PERIOD BUILDERS
# ============================================================================

def build_period_from_entities(entities: "ExtractedEntities") -> Optional[PeriodSpec]:
    """
    ExtractedEntities'den PeriodSpec oluşturur.
    
    Mevsim/ay/yıl bilgisini tek noktada toplayan period-engine.
    
    Öncelik sırası:
        1. Rölatif dönem (son N ay/yıl)
        2. Yıl + Ay → spesifik ay
        3. Yıl + Mevsim → spesifik mevsim
        4. Sadece yıl(lar)
        5. Sadece ay
        6. Sadece mevsim
    
    Args:
        entities: Çıkarılmış varlıklar
        
    Returns:
        PeriodSpec veya None
    """
    years = entities.years
    months = entities.months
    seasons = entities.seasons

    # ─────────────────────────────────────────────────────────────────────────
    # 0) Rölatif dönem öncelikli: "son 12 ay", "son 3 yıl" vb.
    # ─────────────────────────────────────────────────────────────────────────
    if entities.relative_unit and entities.relative_value:
        return PeriodSpec(
            kind="relative",
            unit=entities.relative_unit,
            value=entities.relative_value,
        )

    # ─────────────────────────────────────────────────────────────────────────
    # 1) Yıl + Ay → spesifik ay
    # ─────────────────────────────────────────────────────────────────────────
    if years and months:
        return PeriodSpec(
            kind="month",
            year=years[0],
            month=months[0],
        )

    # ─────────────────────────────────────────────────────────────────────────
    # 2) Yıl + Mevsim → spesifik mevsim
    # ─────────────────────────────────────────────────────────────────────────
    if years and seasons:
        return PeriodSpec(
            kind="season",
            year=years[0],
            season=seasons[0],
        )

    # ─────────────────────────────────────────────────────────────────────────
    # 3) Sadece yıl(lar)
    # ─────────────────────────────────────────────────────────────────────────
    if years:
        years_sorted = sorted(set(years))
        if len(years_sorted) == 1:
            return PeriodSpec(kind="year", year=years_sorted[0])
        return PeriodSpec(
            kind="range",
            start_date=f"{years_sorted[0]}-01-01",
            end_date=f"{years_sorted[-1] + 1}-01-01",
        )

    # ─────────────────────────────────────────────────────────────────────────
    # 4) Sadece ay → tüm yılların o ayı
    # ─────────────────────────────────────────────────────────────────────────
    if months:
        return PeriodSpec(
            kind="month",
            month=months[0],
            year=None,
        )

    # ─────────────────────────────────────────────────────────────────────────
    # 5) Sadece mevsim → tüm yılların o mevsimi
    # ─────────────────────────────────────────────────────────────────────────
    if seasons:
        return PeriodSpec(
            kind="season",
            season=seasons[0],
            year=None,
        )

    return None


# ============================================================================
# TIME RANGE CONVERTER
# ============================================================================

def period_to_time_range(
    period: Optional[PeriodSpec],
    anchor_date: Optional[datetime] = None,
) -> Optional[TimeRange]:
    """
    PeriodSpec → TimeRange dönüşümü.

    Args:
        period: Dönem spesifikasyonu
        anchor_date: Rölatif hesaplamalar için referans tarih.
            Not: Anchor date yoksa "son N ay/yıl" gibi rölatif dönemler
            güvenle çözülemez. Bu durumda None döndürürüz (datetime.now() yok).
            
    Returns:
        TimeRange veya None
        
    Rölatif dönemlerde (son 2 yıl, son 12 ay) anchor_date'e göre
    geriye doğru hesaplama yapılır.
    
    ÖNEMLİ: Yıl bazlı rölatif dönemlerde TAKVİM YILI kullanılır.
    "Son 2 yıl" = anchor yılı + önceki yıl (toplam 2 tam takvim yılı)
    """
    if not period:
        return None

    # ─────────────────────────────────────────────────────────────────────────
    # Helper: "YYYY-MM-DD" / ISO string -> datetime
    # ─────────────────────────────────────────────────────────────────────────
    def _parse_dt(s: str) -> Optional[datetime]:
        if not s or not isinstance(s, str):
            return None
        s = s.strip()
        if not s:
            return None
        try:
            # "YYYY-MM-DD" veya "YYYY-MM-DDTHH:MM:SS" gibi formatlar
            dt = datetime.fromisoformat(s)
            return dt.replace(microsecond=0)
        except Exception:
            # Bazen "YYYY-MM-DDZ" gibi gelebilir; Z'yi kırpıp tekrar dene
            try:
                if s.endswith("Z"):
                    dt = datetime.fromisoformat(s[:-1])
                    return dt.replace(microsecond=0)
            except Exception:
                return None
        return None

    # ─────────────────────────────────────────────────────────────────────────
    # Rölatif Dönem Desteği
    # ─────────────────────────────────────────────────────────────────────────
    # ❗️datetime.now() fallback YOK: LRS operationDate üstünden anchor gelmediyse
    # rölatif dönem çözümlenemez.
    if period.kind == "relative" and period.value and period.unit:
        # ❌ datetime.now() fallback yok.
        # ✅ Tüm rölatif dönemler LRS operasyon tarihlerine göre anchor'lanmalı.
        if anchor_date is None:
            return None

        ref_date = anchor_date.replace(microsecond=0)

        # ✅ YIL bazlı: Takvim yılı kullan (kullanıcı "son 2 yıl" dediğinde 2 tam yıl bekler)
        # Örnek: Anchor=24.03.2022, "son 2 yıl" → 2021-01-01 ile 2022-12-31 arası
        if period.unit == "year":
            anchor_year = ref_date.year
            start_year = anchor_year - period.value + 1  # +1: anchor yılı dahil
            start = datetime(start_year, 1, 1)
            # Anchor yılının sonuna kadar (anchor date'e değil, yıl sonuna kadar)
            end = datetime(anchor_year, 12, 31, 23, 59, 59)
            return TimeRange(start_date=start, end_date=end)

        # AY bazlı: Gün hesabı (30 gün/ay yaklaşımı)
        if period.unit == "month":
            delta_days = 30 * period.value
            start = ref_date - timedelta(days=delta_days)
            end = ref_date
            return TimeRange(start_date=start, end_date=end)

    # ─────────────────────────────────────────────────────────────────────────
    # RANGE Desteği (ör. 2020..2023 → 2020-01-01..2024-01-01)
    # ─────────────────────────────────────────────────────────────────────────
    if period.kind == "range" and period.start_date and period.end_date:
        start = _parse_dt(period.start_date)
        end = _parse_dt(period.end_date)
        if start and end:
            return TimeRange(start_date=start, end_date=end)

    # ─────────────────────────────────────────────────────────────────────────
    # Yıl Bazlı
    # ─────────────────────────────────────────────────────────────────────────
    if period.kind == "year" and period.year:
        year = int(period.year)
        return TimeRange(
            start_date=datetime(year, 1, 1),
            end_date=datetime(year + 1, 1, 1),
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Ay Bazlı (yıl zorunlu)
    # ─────────────────────────────────────────────────────────────────────────
    if period.kind == "month" and period.year and period.month:
        year = int(period.year)
        month = int(period.month)
        start = datetime(year, month, 1)
        if month == 12:
            end = datetime(year + 1, 1, 1)
        else:
            end = datetime(year, month + 1, 1)
        return TimeRange(start_date=start, end_date=end)

    return None


# ============================================================================
# PUBLIC API
# ============================================================================

__all__ = [
    "build_period_from_entities",
    "period_to_time_range",
]
