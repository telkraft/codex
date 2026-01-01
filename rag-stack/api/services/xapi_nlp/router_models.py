# router_models.py
"""
NLP Router Veri Modelleri
=========================

Intent analizi için kullanılan dataclass'lar.
Diğer tüm NLP modülleri bu modellere bağımlıdır.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from services.xapi_nlp.canonical_questions import (
    QuestionType,
    OutputShape,
    CanonicalQuestion,
)
from models import QueryPlan


# ============================================================================
# EXTRACTED ENTITIES
# ============================================================================

@dataclass
class ExtractedEntities:
    """
    Sorudan çıkarılan varlıklar.
    
    EntityExtractor tarafından doldurulur ve diğer modüller tarafından kullanılır.
    """
    
    # ─────────────────────────────────────────────────────────────────────────
    # Zaman Varlıkları
    # ─────────────────────────────────────────────────────────────────────────
    years: List[int] = field(default_factory=list)
    months: List[int] = field(default_factory=list)
    seasons: List[str] = field(default_factory=list)

    # Rölatif dönem (son 12 ay / son 3 yıl vb.)
    relative_unit: Optional[str] = None   # 'month' veya 'year'
    relative_value: Optional[int] = None  # 12, 3 gibi sayı
    
    # ─────────────────────────────────────────────────────────────────────────
    # Araç Varlıkları
    # ─────────────────────────────────────────────────────────────────────────
    vehicle_ids: List[str] = field(default_factory=list)
    vehicle_types: List[str] = field(default_factory=list)
    vehicle_models: List[str] = field(default_factory=list)
    manufacturers: List[str] = field(default_factory=list)
    
    # ─────────────────────────────────────────────────────────────────────────
    # Diğer ID'ler
    # ─────────────────────────────────────────────────────────────────────────
    customer_ids: List[str] = field(default_factory=list)
    service_locations: List[str] = field(default_factory=list)
    fault_codes: List[str] = field(default_factory=list)
    
    # ─────────────────────────────────────────────────────────────────────────
    # Malzeme Varlıkları
    # ─────────────────────────────────────────────────────────────────────────
    material_keywords: List[str] = field(default_factory=list)
    material_keywords_source: Optional[str] = None  # "quoted" | "fallback"
    conditional_material: Optional[str] = None  # next_maintenance için
    
    # ─────────────────────────────────────────────────────────────────────────
    # Metrik/Aggregation Belirleyiciler
    # ─────────────────────────────────────────────────────────────────────────
    has_top_signal: bool = False
    top_limit: int = 10
    
    # ─────────────────────────────────────────────────────────────────────────
    # Karşılaştırma Sinyalleri
    # ─────────────────────────────────────────────────────────────────────────
    comparison_entities: List[str] = field(default_factory=list)


# ============================================================================
# INTENT ANALYSIS RESULT
# ============================================================================

@dataclass
class IntentAnalysisResult:
    """
    Intent analiz sonucu - 2 Katmanlı.
    
    AdvancedIntentRouter.analyze_question() tarafından döndürülür.
    """
    
    # ─────────────────────────────────────────────────────────────────────────
    # Tespit Edilen Intent ve Shape
    # ─────────────────────────────────────────────────────────────────────────
    question_type: QuestionType
    output_shape: OutputShape
    
    # ─────────────────────────────────────────────────────────────────────────
    # Güven Skorları
    # ─────────────────────────────────────────────────────────────────────────
    intent_confidence: float = 0.0
    shape_confidence: float = 0.0
    
    # ─────────────────────────────────────────────────────────────────────────
    # Eşleşen Canonical Question
    # ─────────────────────────────────────────────────────────────────────────
    matched_cq: Optional[CanonicalQuestion] = None
    
    # Alternatif question'lar (belirsizlik varsa)
    alternative_cqs: List[Tuple[CanonicalQuestion, float]] = field(default_factory=list)
    
    # ─────────────────────────────────────────────────────────────────────────
    # Çıkarılan Varlıklar
    # ─────────────────────────────────────────────────────────────────────────
    entities: ExtractedEntities = field(default_factory=ExtractedEntities)
    
    # ─────────────────────────────────────────────────────────────────────────
    # Önerilen QueryPlan
    # ─────────────────────────────────────────────────────────────────────────
    suggested_plan: Optional[QueryPlan] = None
    
    # ─────────────────────────────────────────────────────────────────────────
    # Analiz Detayları (debugging için)
    # ─────────────────────────────────────────────────────────────────────────
    analysis_details: Dict[str, Any] = field(default_factory=dict)
    
    # ─────────────────────────────────────────────────────────────────────────
    # Backward Compatibility Properties
    # ─────────────────────────────────────────────────────────────────────────
    @property
    def primary_question(self) -> Optional[CanonicalQuestion]:
        """Eski API uyumluluğu için"""
        return self.matched_cq
    
    @property
    def primary_score(self) -> float:
        """Eski API uyumluluğu için"""
        return (self.intent_confidence + self.shape_confidence) / 2


# ============================================================================
# PUBLIC API
# ============================================================================

__all__ = [
    "ExtractedEntities",
    "IntentAnalysisResult",
]
