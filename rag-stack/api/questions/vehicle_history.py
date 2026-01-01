from __future__ import annotations

from typing import Any, Dict

from services.lrs_service import LRSQueryService


def answer_vehicle_history(
    lrs: LRSQueryService,
    vehicle_id: str,
    limit: int = 300,
) -> Dict[str, Any]:
    """
    Belirli bir araç için bakım/onarım geçmişini döndürür.
    LRS tarafında vehicle_maintenance_history(...) fonksiyonunu çağırır.
    """
    return lrs.vehicle_maintenance_history(
        vehicle_id=vehicle_id,
        limit=limit,
    )
