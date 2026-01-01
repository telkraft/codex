# advanced_intent_router.py
"""
Advanced Intent Router (Facade)
===============================

2-Katmanlı Algoritmik Soru Analizi için ana orkestratör.

Bu modül, tüm NLP bileşenlerini bir araya getirir:
- EntityExtractor: Varlık çıkarma
- IntentShapeRefiner: Heuristic-based refinement
- QueryPlanBuilder: LRS sorgu planı oluşturma

LLM KULLANILMAZ - Tamamen kural tabanlı çalışır.

2-Katmanlı Mimari:
------------------
- KATMAN 1 (Intent): Sorunun KONUSU (NE soruluyor?)
- KATMAN 2 (Shape): Verinin SUNUMU (NASIL gösterilecek?)

Kullanım:
---------
>>> router = AdvancedIntentRouter()
>>> result = router.analyze_question("2023 yılında en çok kullanılan malzemeler neler?")
>>> print(result.question_type)
QuestionType.MATERIAL_USAGE
>>> print(result.output_shape)
OutputShape.TOP_LIST
"""

from __future__ import annotations

from typing import List, Tuple

# ============================================================================
# MODULAR COMPONENTS
# ============================================================================
from .router_models import ExtractedEntities, IntentAnalysisResult
from .period_utils import build_period_from_entities, period_to_time_range
from .entity_extractor import EntityExtractor
from .intent_shape_refiner import IntentShapeRefiner
from .query_plan_builder import QueryPlanBuilder

# ============================================================================
# CANONICAL QUESTIONS
# ============================================================================
from services.xapi_nlp.canonical_questions import (
    QuestionType,
    OutputShape,
    CanonicalQuestion,
    detect_intent,
    detect_shape,
    find_best_matching_cq,
    get_cq_by_type_and_shape,
)

# ============================================================================
# NLP UTILS
# ============================================================================
from services.xapi_nlp.nlp_utils import (
    normalize_tr,
    contains_any,
    extract_month,
    extract_season,
)


# ============================================================================
# ADVANCED INTENT ROUTER (FACADE)
# ============================================================================

class AdvancedIntentRouter:
    """
    2-Katmanlı Gelişmiş Algoritmik Intent Router.
    
    Facade pattern kullanarak tüm NLP bileşenlerini orkestre eder.
    
    Analiz Aşamaları:
    -----------------
    1. Soru Normalizasyonu (normalize_tr)
    2. Entity Extraction (EntityExtractor)
    3. Intent Detection (QuestionType) - KATMAN 1
    4. Shape Detection (OutputShape) - KATMAN 2
    5. Heuristic Refinement (IntentShapeRefiner)
    6. Canonical Question Matching
    7. QueryPlan Construction (QueryPlanBuilder)
    
    Attributes:
        entity_extractor: Varlık çıkarma motoru
        intent_refiner: Heuristic-based refinement
        plan_builder: QueryPlan oluşturucu
    """
    
    def __init__(self):
        """Modüler bileşenleri başlatır"""
        self.entity_extractor = EntityExtractor()
        self.intent_refiner = IntentShapeRefiner()
        self.plan_builder = QueryPlanBuilder()
    
    # ========================================================================
    # MAIN ENTRY POINT
    # ========================================================================
    
    def analyze_question(self, question: str) -> IntentAnalysisResult:
        """
        Ana analiz fonksiyonu - 2 Katmanlı.
        
        Args:
            question: Kullanıcının sorduğu soru (Türkçe)
        
        Returns:
            IntentAnalysisResult with intent + shape + entities + plan
        """
        # 1. Normalize et
        qn = normalize_tr(question)
        
        # 2. Entity extraction
        entities = self.entity_extractor.extract(question)
        
        # 3. Intent detection (KATMAN 1)
        intent, intent_conf = detect_intent(qn)
        
        # 4. Shape detection (KATMAN 2)
        shape, shape_conf = detect_shape(qn, intent)
        
        # 5. Intent refinement (heuristics ile)
        intent, shape, intent_conf, shape_conf = self.intent_refiner.refine(
            intent, shape, intent_conf, shape_conf, qn, entities
        )

        # 6. PIVOT override (FINAL): aynı soruda 2 farklı zaman kırılımı varsa PIVOT'a zorla
        intent, shape, shape_conf = self._apply_pivot_override(
            intent, shape, shape_conf, qn
        )

        # 7. En iyi eşleşen CQ'yu bul (intent+shape filtreli)
        matched_cq = self._find_matching_cq(qn, intent, shape)
        
        # 8. Alternatif CQ'ları bul
        alt_cqs = self._find_alternative_cqs(qn, matched_cq)
        
        # 9. QueryPlan oluştur
        suggested_plan = self.plan_builder.build(intent, shape, matched_cq, entities, qn)
        
        # 10. Sonuç
        result = IntentAnalysisResult(
            question_type=intent,
            output_shape=shape,
            intent_confidence=intent_conf,
            shape_confidence=shape_conf,
            matched_cq=matched_cq,
            alternative_cqs=alt_cqs,
            entities=entities,
            suggested_plan=suggested_plan,
            analysis_details={
                "normalized_query": qn,
                "original_query": question,
            },
        )
        
        return result
    
    # ========================================================================
    # HELPER METHODS
    # ========================================================================
    
    def _apply_pivot_override(
        self,
        intent: QuestionType,
        shape: OutputShape,
        shape_conf: float,
        qn: str,
    ) -> Tuple[QuestionType, OutputShape, float]:
        """
        Aynı soruda 2 farklı zaman kırılımı varsa PIVOT'a zorla.
        
        Örnek: "Yıllara ve mevsimlere göre malzeme kullanımı"
        """
        if intent == QuestionType.MATERIAL_USAGE:
            has_year = contains_any(qn, ["yillara", "yillara gore", "yillik", "yil bazinda", "yil bazli"])
            has_month = contains_any(qn, ["aylara", "aylara gore", "aylik", "ay bazinda", "ay bazli"]) or extract_month(qn) is not None
            has_season = contains_any(qn, ["mevsim", "mevsimlere gore", "mevsimsel", "sezon", "kis", "yaz", "bahar", "sonbahar"]) or extract_season(qn) is not None

            if sum([has_year, has_month, has_season]) >= 2:
                shape = OutputShape.PIVOT
                shape_conf = max(shape_conf, 0.90)
        
        return intent, shape, shape_conf
    
    def _find_matching_cq(
        self,
        qn: str,
        intent: QuestionType,
        shape: OutputShape,
    ) -> CanonicalQuestion:
        """En iyi eşleşen canonical question'ı bulur"""
        candidates = [
            (cq, conf)
            for cq, conf in find_best_matching_cq(qn, min_confidence=0.2)
            if cq.question_type == intent and cq.output_shape == shape
        ]

        if candidates:
            return candidates[0][0]
        return get_cq_by_type_and_shape(intent, shape)
    
    def _find_alternative_cqs(
        self,
        qn: str,
        matched_cq: CanonicalQuestion,
    ) -> List[Tuple[CanonicalQuestion, float]]:
        """Alternatif canonical question'ları bulur"""
        alternatives = find_best_matching_cq(qn, min_confidence=0.2)
        return [(cq, conf) for cq, conf in alternatives if cq != matched_cq][:3]
    
    # ========================================================================
    # EXPLAIN / DEBUG
    # ========================================================================
    
    def explain_analysis(self, result: IntentAnalysisResult) -> str:
        """
        Analiz sonucunu Türkçe açıklar (debugging için).
        
        Args:
            result: IntentAnalysisResult instance
            
        Returns:
            İnsan tarafından okunabilir açıklama
        """
        lines = [
            "=" * 60,
            "SORU ANALİZİ",
            "=" * 60,
            "",
            f"Orijinal Soru: {result.analysis_details.get('original_query', 'N/A')}",
            f"Normalize: {result.analysis_details.get('normalized_query', 'N/A')}",
            "",
            "─" * 40,
            "KATMAN 1: INTENT (Konu)",
            "─" * 40,
            f"Tespit: {result.question_type.value}",
            f"Güven: {result.intent_confidence:.2f}",
            "",
            "─" * 40,
            "KATMAN 2: SHAPE (Sunum)",
            "─" * 40,
            f"Tespit: {result.output_shape.value}",
            f"Güven: {result.shape_confidence:.2f}",
            "",
        ]
        
        # Entities
        lines.extend([
            "─" * 40,
            "ÇIKARILAN VARLIKLAR",
            "─" * 40,
        ])
        
        entities = result.entities
        if entities.years:
            lines.append(f"  Yıllar: {entities.years}")
        if entities.months:
            lines.append(f"  Aylar: {entities.months}")
        if entities.seasons:
            lines.append(f"  Mevsimler: {entities.seasons}")
        if entities.relative_unit:
            lines.append(f"  Rölatif: son {entities.relative_value} {entities.relative_unit}")
        if entities.vehicle_ids:
            lines.append(f"  Araç ID'leri: {entities.vehicle_ids}")
        if entities.vehicle_models:
            lines.append(f"  Araç Modelleri: {entities.vehicle_models}")
        if entities.vehicle_types:
            lines.append(f"  Araç Tipleri: {entities.vehicle_types}")
        if entities.material_keywords:
            lines.append(f"  Malzeme Keywords: {entities.material_keywords} (kaynak: {entities.material_keywords_source})")
        if entities.has_top_signal:
            lines.append(f"  Top Limit: {entities.top_limit}")
        if entities.fault_codes:
            lines.append(f"  Arıza Kodları: {entities.fault_codes}")
        
        # Matched CQ
        if result.matched_cq:
            lines.extend([
                "",
                "─" * 40,
                "EŞLEŞTİRİLEN CANONICAL QUESTION",
                "─" * 40,
                f"  ID: {result.matched_cq.id}",
                f"  Açıklama: {result.matched_cq.description}",
            ])
        
        # QueryPlan
        if result.suggested_plan:
            plan = result.suggested_plan
            lines.extend([
                "",
                "─" * 40,
                "QUERY PLAN",
                "─" * 40,
                f"  Group By: {plan.group_by}",
                f"  Metrics: {plan.metrics}",
                f"  Filters: {plan.filters}",
                f"  Sort By: {plan.sort_by}",
                f"  Limit: {plan.limit}",
            ])
            if plan.time_range:
                lines.append(f"  Time Range: {plan.time_range.start_date} → {plan.time_range.end_date}")
        
        lines.append("")
        lines.append("=" * 60)
        
        return "\n".join(lines)


# ============================================================================
# PUBLIC API EXPORTS (Backward Compatibility)
# ============================================================================
# Dışarıdan import edenler için aynı API korunuyor

__all__ = [
    # Main class
    "AdvancedIntentRouter",
    
    # Data models
    "IntentAnalysisResult",
    "ExtractedEntities",
    
    # Period utilities (orchestrator.py kullanıyor)
    "period_to_time_range",
    "build_period_from_entities",
    
    # Sub-modules (gerektiğinde erişim için)
    "EntityExtractor",
    "IntentShapeRefiner",
    "QueryPlanBuilder",
]

# Re-export for backward compatibility
_period_to_time_range = period_to_time_range
_build_period_from_entities = build_period_from_entities
