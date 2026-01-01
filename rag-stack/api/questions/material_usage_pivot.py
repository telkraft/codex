from __future__ import annotations
from typing import Any, Dict, Optional

from services.lrs_service import LRSQueryService


class MaterialUsagePivotQuestion:
    """
    Yıllara + mevsimlere göre malzeme kullanım pivotu sorusu.

    - period: {"kind": "..."} dict (top/trend'te kullandığımız format)
    - limit : kaç satır döneceği
    """

    def __init__(
        self,
        period: Optional[Dict[str, Any]] = None,
        limit: int = 200,
    ) -> None:
        self.period = period
        self.limit = limit

    def run(self, lrs: LRSQueryService) -> Dict[str, Any]:
        return lrs.material_usage_pivot(
            period=self.period,
            limit=self.limit,
        )


def answer_material_usage_pivot(
    lrs: LRSQueryService,
    period: Optional[Dict[str, Any]] = None,
    limit: int = 200,
) -> Dict[str, Any]:
    q = MaterialUsagePivotQuestion(period=period, limit=limit)
    return q.run(lrs)
