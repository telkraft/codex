"""
Material Family Price Trend Question
====================================

Malzeme aileleri bazında fiyat artışı sorularını yöneten handler.

LRS tarafında:
- LRSQueryService.material_family_price_trend(...) fonksiyonunu kullanır.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from services.lrs_service import LRSQueryService


class MaterialFamilyPriceTrendQuestion:
    """
    Basit soru modeli:

    - period:  {"kind": "last_n_years", "years": 3} gibi bir dict
    - limit :  kaç satır döneceği
    """

    def __init__(
        self,
        period: Optional[Dict[str, Any]] = None,
        limit: int = 15,
    ) -> None:
        self.period = period
        self.limit = limit

    def run(self, lrs: LRSQueryService) -> Dict[str, Any]:
        """
        LRS üzerinde gerçek analizi çalıştırır.
        """
        return lrs.material_family_price_trend(
            period=self.period,
            limit=self.limit,
        )


def answer_material_family_price_trend(
    lrs: LRSQueryService,
    period: Optional[Dict[str, Any]] = None,
    limit: int = 15,
) -> Dict[str, Any]:
    """
    Fonksiyonel API tercih eden kodlar için kısayol.
    """
    q = MaterialFamilyPriceTrendQuestion(period=period, limit=limit)
    return q.run(lrs)
