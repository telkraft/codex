"""
LRS Service
===========

LRS MongoDB üzerinde schema-aware istatistiksel sorgular ve
örnek xAPI statement'lar üreten birleşik servis.

MVP akışında:
- Soru → Intent/QueryPlan
- QueryPlan → LRSQueryService.run_query(...) ile istatistik
- Aynı QueryPlan → LRSQueryService.get_example_statements(...) ile örnek olaylar
- Bu çıktıların hepsi LLM'e bağlam olarak gönderilir.
"""

from __future__ import annotations

# Bu modül, eski lrs_service.py'nin dış API'sini korumak için
# schema helper'larını yeniden dışa açar.
from services.lrs_schema import (
    MAN_SCHEMA,
    normalize_tr,
    normalize_model,
    _get_nested,
    _get_attr,
    _build_time_filter,
    _extract_vehicle_id_from_actor,
    _extract_operation_date,
    _get_context,
    _extract_service_code_from_context,
    _extract_customer_id_from_context,
)

from models import QueryPlan, TimeRange, TopEntitiesQuestion

from services.lrs_core import LRSCore
from services.lrs_examples import LRSExamplesMixin
from services.lrs_patterns import LRSPatternsMixin


class LRSQueryService(LRSCore, LRSExamplesMixin, LRSPatternsMixin):
    """
    Eski LRSQueryService'in tüm davranışını koruyan birleşik servis sınıfı.

    - LRSCore          → QueryPlan tabanlı istatistiksel sorgular
    - LRSExamplesMixin → örnek xAPI kayıtları, dönem filtreleri, insan-dili açıklama
    - LRSPatternsMixin → top entities, fiyat trendleri, pattern analizleri
    """
    pass


__all__ = [
    "LRSQueryService",
    "MAN_SCHEMA",
    "normalize_tr",
    "normalize_model",
    "_get_nested",
    "_get_attr",
    "_build_time_filter",
    "_extract_vehicle_id_from_actor",
    "_extract_operation_date",
    "_get_context",
    "_extract_service_code_from_context",
    "_extract_customer_id_from_context",
    "QueryPlan",
    "TimeRange",
    "TopEntitiesQuestion",
]
