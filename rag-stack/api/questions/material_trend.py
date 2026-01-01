"""
Material Price Trend Question
=============================

Malzeme bazlı fiyat artışı sorularını tek bir yerde toplar.

Bu handler:
- LRSQueryService.material_price_trend(...) fonksiyonunu kullanır
- Orchestrator / IntentRouter tarafı ise sadece bu handler'ı çağırır.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from services.lrs_service import LRSQueryService


class MaterialPriceTrendQuestion:
    """
    Basit bir soru modeli:

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

        Dönen yapı, LRSQueryService.material_price_trend(...) çıktısını
        aynen forward eder. (scenario, period, rows ...)
        """
        return lrs.material_price_trend(
            period=self.period,
            limit=self.limit,
        )


# Orchestrator için şeker fonksiyon (daha yalın kullanım istersek):

def answer_material_price_trend(
    lrs: LRSQueryService,
    period: Optional[Dict[str, Any]] = None,
    limit: int = 15,
) -> Dict[str, Any]:
    """
    Fonksiyonel API tercih eden kodlar için kısayol.
    """
    q = MaterialPriceTrendQuestion(period=period, limit=limit)
    return q.run(lrs)
