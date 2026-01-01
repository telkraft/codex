# query_plan_builder.py
"""
Query Plan Builder
==================

Intent, Shape ve Entities'ten QueryPlan oluşturan modül.

QueryPlan, LRS'e gidecek sorguyu tanımlar:
- group_by: Hangi boyutlara göre gruplama yapılacak
- metrics: Hangi metrikler hesaplanacak
- filters: Hangi filtreler uygulanacak
- time_range: Zaman aralığı
- sort_by: Sıralama kriteri
- limit: Maksimum sonuç sayısı
"""

from __future__ import annotations

from typing import Dict, List, Optional, Any

from .router_models import ExtractedEntities
from .period_utils import build_period_from_entities, period_to_time_range

from services.xapi_nlp.canonical_questions import (
    QuestionType,
    OutputShape,
    CanonicalQuestion,
    DEFAULT_DIMENSION_FOR_INTENT,
)

from services.xapi_nlp.nlp_constants import (
    VEHICLE_TYPE_KEYWORDS,
    VEHICLE_MODEL_KEYWORDS,
    VEHICLE_KEYWORDS,
    MATERIAL_BASE_WORDS,
    MATERIAL_NOISE_WORDS,
)

from services.xapi_nlp.nlp_utils import normalize_tr

from models import QueryPlan


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _has_vehicle_list_intent(qn: str) -> bool:
    """
    Soru, araç listesi mi istiyor?
    
    "araclar" kelimesi tek başına geçsin; "araclarda" tetiklememeli.
    """
    import re
    from services.xapi_nlp.nlp_utils import contains_any
    from services.xapi_nlp.nlp_constants import TOP_LIST_KEYWORDS
    
    if re.search(r"\baraclar\b", qn) is None and "plaka" not in qn:
        return False
    # Liste niyeti: "hangi", "listele", "en cok/top" vb.
    return ("hangi" in qn) or contains_any(qn, TOP_LIST_KEYWORDS) or ("listele" in qn)


# ============================================================================
# QUERY PLAN BUILDER CLASS
# ============================================================================

class QueryPlanBuilder:
    """
    Intent + Shape + Entities → QueryPlan dönüşümünü yapar.
    
    Kullanım:
        >>> builder = QueryPlanBuilder()
        >>> plan = builder.build(
        ...     intent=QuestionType.MATERIAL_USAGE,
        ...     shape=OutputShape.TOP_LIST,
        ...     cq=matched_canonical_question,
        ...     entities=extracted_entities,
        ...     qn="son 2 yilda en cok kullanilan malzemeler"
        ... )
    """
    
    def build(
        self,
        intent: QuestionType,
        shape: OutputShape,
        cq: Optional[CanonicalQuestion],
        entities: ExtractedEntities,
        qn: str,
    ) -> QueryPlan:
        """
        Intent, Shape ve entities'ten QueryPlan oluşturur.
        
        Args:
            intent: Tespit edilen soru tipi
            shape: Tespit edilen çıktı şekli
            cq: Eşleşen canonical question (varsa)
            entities: Çıkarılmış varlıklar
            qn: Normalize edilmiş sorgu
            
        Returns:
            QueryPlan instance
        """
        
        # ═══════════════════════════════════════════════════════════════════
        # NEXT_MAINTENANCE için özel handling
        # ═══════════════════════════════════════════════════════════════════
        if intent == QuestionType.NEXT_MAINTENANCE:
            return self._build_next_maintenance_plan(entities)
        
        # ═══════════════════════════════════════════════════════════════════
        # Standart QueryPlan oluşturma
        # ═══════════════════════════════════════════════════════════════════
        
        # 1. Primary Dimension
        primary_dim = self._infer_primary_dimension(intent, shape, cq, qn, entities)
        
        # 2. Dimensions (group_by)
        dimensions = self._build_dimensions(primary_dim, shape, cq, qn, entities)
        
        # 3. Metrics
        metrics = self._infer_metrics(intent, cq)
        
        # 4. Filters
        filters = self._build_filters(intent, cq, entities, qn)
        
        # 5. Time Range
        time_range = self._build_time_range(entities)
        
        # 6. Sort
        sort_by = self._infer_sort(cq, entities, dimensions)
        
        # 7. Limit
        limit = self._infer_limit(shape, cq, entities)
        
        return QueryPlan(
            group_by=dimensions,
            metrics=metrics,
            filters=filters,
            time_range=time_range,
            sort_by=sort_by,
            limit=limit,
        )
    
    # ========================================================================
    # NEXT_MAINTENANCE SPECIAL CASE
    # ========================================================================
    
    def _build_next_maintenance_plan(self, entities: ExtractedEntities) -> QueryPlan:
        """NEXT_MAINTENANCE için özel QueryPlan"""
        dimensions = ["materialName"]
        
        if entities.vehicle_models:
            dimensions.append("vehicleModel")
        
        metrics = ["count"]
        filters = {}
        
        if entities.vehicle_models:
            filters["vehicleModel_eq"] = entities.vehicle_models[0]
        
        if entities.conditional_material:
            filters["_conditional_material"] = entities.conditional_material
        
        return QueryPlan(
            group_by=dimensions,
            metrics=metrics,
            filters=filters,
            time_range=None,
            sort_by="count",
            limit=10,
        )
    
    # ========================================================================
    # PRIMARY DIMENSION INFERENCE
    # ========================================================================
    
    def _infer_primary_dimension(
        self,
        intent: QuestionType,
        shape: OutputShape,
        cq: Optional[CanonicalQuestion],
        qn: str,
        entities: ExtractedEntities,
    ) -> str:
        """Primary dimension'ı belirler"""
        
        # Default: intent'e göre
        primary_dim = DEFAULT_DIMENSION_FOR_INTENT.get(intent, "materialName")
        if cq:
            primary_dim = cq.primary_dimension
        
        # ═══════════════════════════════════════════════════════════════════
        # SORU BAZLI DIMENSION OVERRIDE
        # ═══════════════════════════════════════════════════════════════════
        
        # Gün dağılımı soruları için dayOfWeek'i primary dimension yap
        if shape == OutputShape.DISTRIBUTION:
            day_patterns = [
                "gunlere gore", "gunlere", "gun bazinda", "gunluk",
                "gunlerine gore", "gunlerine", "gunlerinde",
                "haftanin gun", "haftanin gunleri",
            ]
            if any(p in qn for p in day_patterns):
                return "dayOfWeek"

        # Araç tipi soruları
        if any(p in qn for p in VEHICLE_TYPE_KEYWORDS):
            if intent != QuestionType.FAULT_ANALYSIS and shape != OutputShape.TOP_PER_GROUP:
                primary_dim = "vehicleType"
        
        # Araç modeli soruları
        if any(p in qn for p in VEHICLE_MODEL_KEYWORDS):
            if intent != QuestionType.FAULT_ANALYSIS and shape != OutputShape.TOP_PER_GROUP:
                primary_dim = "vehicleModel"

        # Araç listesi soruları
        has_vehicle_context = any(k in qn for k in VEHICLE_KEYWORDS)
        if intent == QuestionType.VEHICLE_ANALYSIS and has_vehicle_context and _has_vehicle_list_intent(qn):
            primary_dim = "vehicle"
        
        # Malzeme ailesi soruları
        material_family_patterns = [
            "malzeme aileleri", "malzeme ailesi", "hangi aile", "hangi aileler",
            "aile bazinda", "ailelere gore", "ailelerine gore",
        ]
        if any(p in qn for p in material_family_patterns):
            primary_dim = "materialFamily"

        # Emniyet kemeri: FAULT_ANALYSIS'te primary dimension CQ'dan gelsin
        if intent == QuestionType.FAULT_ANALYSIS and cq:
            primary_dim = cq.primary_dimension

        # Gün pattern'leri - TÜM SHAPES için kontrol
        day_patterns = [
            "gunlere gore", "gunlere", "gun bazinda", "gunluk",
            "gunlerine gore", "gunlerine", "gunlerinde",
            "haftanin gun", "haftanin gunleri",
        ]
        has_day_pattern = any(p in qn for p in day_patterns)
        
        if has_day_pattern:
            primary_dim = "dayOfWeek"
        elif shape == OutputShape.DISTRIBUTION and cq:
            primary_dim = cq.primary_dimension
        elif shape == OutputShape.PIVOT and cq:
            primary_dim = cq.primary_dimension
        
        return primary_dim
    
    # ========================================================================
    # DIMENSIONS (GROUP_BY)
    # ========================================================================
    
    def _build_dimensions(
        self,
        primary_dim: str,
        shape: OutputShape,
        cq: Optional[CanonicalQuestion],
        qn: str,
        entities: ExtractedEntities,
    ) -> List[str]:
        """group_by dimensions listesini oluşturur"""
        
        dimensions = [primary_dim]
        
        # Shape'e göre ek dimension'lar
        dimensions = self._add_shape_dimensions(dimensions, shape, cq, qn, entities)
        
        # Entity'lere göre ek dimension'lar
        dimensions = self._add_entity_dimensions(dimensions, qn, entities)
        
        # Zaman pattern'leri
        dimensions = self._add_time_dimensions(dimensions, qn)
        
        # Duplicate'leri temizle
        dimensions = list(dict.fromkeys(dimensions))
        
        return dimensions
    
    def _add_shape_dimensions(
        self,
        dimensions: List[str],
        shape: OutputShape,
        cq: Optional[CanonicalQuestion],
        qn: str,
        entities: ExtractedEntities,
    ) -> List[str]:
        """Shape'e göre ek dimension'lar ekler"""
        
        # Gün pattern kontrolü
        day_patterns = [
            "gunlere gore", "gunlere", "gun bazinda", "gunluk",
            "gunlerine gore", "gunlerine", "gunlerinde",
            "haftanin gun", "haftanin gunleri",
        ]
        has_day_pattern = any(p in qn for p in day_patterns)
        
        if shape == OutputShape.TIME_SERIES:
            if has_day_pattern:
                dimensions.append("dayOfWeek")
            elif entities.years or any(p in qn for p in ["yillara", "yil bazinda"]):
                dimensions.append("year")
            elif entities.months or any(p in qn for p in ["aylara", "ay bazinda"]):
                dimensions.append("month")
            else:
                dimensions.append("year")  # Default
        
        elif shape == OutputShape.SEASONAL:
            dimensions.append("season")
        
        elif shape == OutputShape.PIVOT:
            if cq and cq.secondary_dimension:
                dimensions.append(cq.secondary_dimension)
        
        elif shape == OutputShape.TOP_PER_GROUP:
            dimensions = self._handle_top_per_group_dimensions(dimensions, cq, qn)
        
        return dimensions
    
    def _handle_top_per_group_dimensions(
        self,
        dimensions: List[str],
        cq: Optional[CanonicalQuestion],
        qn: str,
    ) -> List[str]:
        """TOP_PER_GROUP için grup dimension'ını belirler"""
        
        group_dim = None
        
        # Mevsim pattern'leri
        season_patterns = [
            "mevsimlere gore", "mevsime gore", "her mevsim", 
            "mevsimde", "mevsimlerde", "mevsim bazinda"
        ]
        if any(p in qn for p in season_patterns):
            group_dim = "season"
        
        # Model pattern'leri
        model_patterns = [
            "modellere gore", "modellerine gore", "her model",
            "modellerde", "model bazinda",
            "arac modellere gore", "arac modellerine gore",
            "arac modeli bazinda", "arac modeli icin",
        ]
        if not group_dim and any(p in qn for p in model_patterns):
            group_dim = "vehicleModel"
        
        # Tip pattern'leri
        type_patterns = [
            "tiplere gore", "tiplerine gore", "her tip",
            "tip bazinda",
            "arac tiplere gore", "arac tiplerine gore",
            "arac tipi bazinda", "arac tipi icin",
        ]
        if not group_dim and any(p in qn for p in type_patterns):
            group_dim = "vehicleType"
        
        # CQ'dan group_dimension al (fallback)
        if not group_dim and cq and cq.group_dimension:
            group_dim = cq.group_dimension
        
        # CQ varsa primary_dimension'ı CQ'dan al
        if cq and cq.primary_dimension:
            primary_dim = cq.primary_dimension
            dimensions = [primary_dim]
        
        # Dimension listesine group_dim'i başa ekle
        if group_dim and group_dim not in dimensions:
            dimensions.insert(0, group_dim)
        
        return dimensions
    
    def _add_entity_dimensions(
        self,
        dimensions: List[str],
        qn: str,
        entities: ExtractedEntities,
    ) -> List[str]:
        """Entity'lere göre ek dimension'lar ekler"""
        
        if entities.vehicle_types and "vehicleType" not in dimensions:
            if any(p in qn for p in VEHICLE_TYPE_KEYWORDS):
                dimensions.append("vehicleType")
        
        if entities.vehicle_models and "vehicleModel" not in dimensions:
            if any(p in qn for p in VEHICLE_MODEL_KEYWORDS):
                dimensions.append("vehicleModel")
        
        return dimensions
    
    def _add_time_dimensions(self, dimensions: List[str], qn: str) -> List[str]:
        """Zaman pattern'lerine göre dimension ekler"""
        
        if any(p in qn for p in ["yillara", "yillara gore", "yil bazinda"]):
            if "year" not in dimensions:
                dimensions.append("year")
        
        if any(p in qn for p in ["mevsimlere", "mevsime gore", "mevsimsel"]):
            if "season" not in dimensions:
                dimensions.append("season")
        
        if any(p in qn for p in ["aylara", "aylara gore", "ay bazinda"]):
            if "month" not in dimensions:
                dimensions.append("month")

        # Gün pattern'leri
        day_patterns = [
            "gunlere gore", "gunlere", "gun bazinda", "gunluk",
            "gunlerine gore", "gunlerine", "gunlerinde",
            "haftanin gun", "haftanin gunleri",
        ]
        if any(p in qn for p in day_patterns):
            if "dayOfWeek" not in dimensions:
                dimensions.append("dayOfWeek")
        
        return dimensions
    
    # ========================================================================
    # METRICS
    # ========================================================================
    
    def _infer_metrics(
        self,
        intent: QuestionType,
        cq: Optional[CanonicalQuestion],
    ) -> List[str]:
        """Metrik listesini oluşturur"""
        
        if cq:
            return list(cq.metrics)
        
        metrics = ["count"]
        if intent == QuestionType.MATERIAL_USAGE:
            metrics.extend(["sum_quantity", "sum_cost"])
        elif intent == QuestionType.COST_ANALYSIS:
            metrics.extend(["sum_cost", "avg_cost"])
        
        return metrics
    
    # ========================================================================
    # FILTERS
    # ========================================================================
    
    def _build_filters(
        self,
        intent: QuestionType,
        cq: Optional[CanonicalQuestion],
        entities: ExtractedEntities,
        qn: str,
    ) -> Dict[str, Any]:
        """Filtre dictionary'si oluşturur"""
        
        filters = {}
        
        # CQ default filtreleri
        if cq and cq.default_filters:
            filters.update(cq.default_filters)
        
        # Entity-based filtreler
        if entities.vehicle_types:
            filters["vehicleType_eq"] = entities.vehicle_types[0]
        
        if entities.manufacturers:
            filters["manufacturer_eq"] = entities.manufacturers[0]
        
        # Malzeme filtreleri
        self._add_material_filters(filters, entities, qn)
        
        if entities.fault_codes:
            filters["faultCode_eq"] = entities.fault_codes[0]
        
        if entities.vehicle_ids:
            filters["vehicleId_eq"] = entities.vehicle_ids[0]
        
        if entities.customer_ids:
            filters["customerId_eq"] = entities.customer_ids[0]
        
        if entities.service_locations:
            filters["serviceLocation_eq"] = entities.service_locations[0]

        if entities.seasons:
            filters["season_eq"] = entities.seasons[0]
        
        # Ay filtresi (yıl olmadan)
        if entities.months and not entities.years:
            filters["month_eq"] = entities.months[0]
        
        return filters
    
    def _add_material_filters(
        self,
        filters: Dict[str, Any],
        entities: ExtractedEntities,
        qn: str,
    ) -> None:
        """Malzeme filtrelerini ekler"""
        
        # Genel malzeme sorularında filtre koyma
        generic_patterns = [
            # "hangi X" pattern'leri
            "hangi malzemeler", "hangi parcalar",
            "hangi malzeme", "hangi parca",
            
            # "X hangileri/neler/nedir" pattern'leri
            "malzemeler hangileri", "malzemeler neler", "malzemeler nelerdir",
            "parcalar hangileri", "parcalar neler", "parcalar nelerdir",
            "malzemeler nedir", "parcalar nedir",
            
            # "kullanılan/değişen X" pattern'leri
            "kullanilan malzemeler", "kullanilan parcalar",
            "degisen malzemeler", "degisen parcalar",
            "degistirilen malzemeler", "degistirilen parcalar",
            
            # "en çok X" pattern'leri
            "en cok kullanilan", "en cok degisen",
            "en fazla kullanilan", "en fazla degisen",
        ]
        is_generic = any(p in qn for p in generic_patterns)

        if entities.material_keywords and not is_generic:
            longest = max(entities.material_keywords, key=len).strip()
            
            # Noise guard
            if longest and not self._is_noise_material_keyword(longest):
                filters["materialName_contains"] = longest
    
    def _is_noise_material_keyword(self, kw: str) -> bool:
        """Malzeme keyword'ünün noise olup olmadığını kontrol eder"""
        k = normalize_tr(kw)
        if not k:
            return True
        if k in MATERIAL_BASE_WORDS:
            return True
        if any(n in k for n in MATERIAL_NOISE_WORDS):
            return True
        # Tek kelime ve çok genel ise
        if k in {"nasil", "trend", "trendleri", "kullanim"}:
            return True
        return False
    
    # ========================================================================
    # TIME RANGE
    # ========================================================================
    
    def _build_time_range(self, entities: ExtractedEntities):
        """Time range oluşturur"""
        
        period = build_period_from_entities(entities)

        # KRİTİK: relative period'u burada time_range'a ÇEVİRME.
        # Orchestrator, LRS get_anchor_date() ile doğru anchor'ı bulup time_range enjekte ediyor.
        if period and period.kind == "relative":
            return None
        
        return period_to_time_range(period)
    
    # ========================================================================
    # SORT
    # ========================================================================
    
    def _infer_sort(
        self,
        cq: Optional[CanonicalQuestion],
        entities: ExtractedEntities,
        dimensions: List[str],
    ) -> str:
        """Sıralama kriterini belirler"""
        
        if cq:
            return cq.sort_metric
        
        sort_by = "count"
        if entities.has_top_signal and "materialName" in dimensions:
            sort_by = "sum_quantity"
        
        return sort_by
    
    # ========================================================================
    # LIMIT
    # ========================================================================
    
    def _infer_limit(
        self,
        shape: OutputShape,
        cq: Optional[CanonicalQuestion],
        entities: ExtractedEntities,
    ) -> int:
        """Limit değerini belirler"""
        
        if shape in [OutputShape.TOP_LIST, OutputShape.TOP_PER_GROUP]:
            limit = entities.top_limit if entities.has_top_signal else 10
        else:
            limit = 100
        
        if cq:
            limit = cq.default_limit if not entities.has_top_signal else entities.top_limit
        
        return limit


# ============================================================================
# PUBLIC API
# ============================================================================

__all__ = [
    "QueryPlanBuilder",
]
