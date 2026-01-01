"""
Next Maintenance Pattern Question
=================================

Belirli bir modelde, X malzemesi kullanıldıktan sonraki
ilk bakımda hangi malzemeler daha sık değişiyor? sorusunun
handler'ı.
"""

from __future__ import annotations

from typing import Any, Dict

from services.lrs_service import LRSQueryService


class NextMaintenancePatternQuestion:
    """
    Basit soru modeli:

    - model         : araç modeli (ör: "RHC 404 (400)")
    - material_name : bakımda kullanılan malzeme adı (ör: "SENSÖR")
    - limit         : kaç malzeme döndürülecek
    """

    def __init__(self, model: str, material_name: str, limit: int = 20) -> None:
        self.model = model
        self.material_name = material_name
        self.limit = limit

    def run(self, lrs: LRSQueryService) -> Dict[str, Any]:
        """
        LRS üzerinde gerçek pattern analizini çalıştırır.
        """
        return lrs.next_maintenance_materials(
            model=self.model,
            material_name=self.material_name,
            limit=self.limit,
        )


def answer_next_maintenance_pattern(
    lrs: LRSQueryService,
    model: str,
    material_name: str,
    limit: int = 20,
) -> Dict[str, Any]:
    """
    Fonksiyonel API tercih eden kodlar için kısayol.
    """
    q = NextMaintenancePatternQuestion(model=model, material_name=material_name, limit=limit)
    return q.run(lrs)
