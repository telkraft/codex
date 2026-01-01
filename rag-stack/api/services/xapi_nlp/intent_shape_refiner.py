# intent_shape_refiner.py
"""
Intent & Shape Refiner
======================

Intent ve shape'i heuristiklerle rafine eden modül.

Temel mantık:
- canonical_questions'dan gelen ilk tahminler heuristiklerle iyileştirilir
- Entity bilgileri kullanılarak daha doğru intent/shape belirlenir
- Confidence skorları güncellenir
"""

from __future__ import annotations

from typing import Tuple

from .router_models import ExtractedEntities

from services.xapi_nlp.canonical_questions import (
    QuestionType,
    OutputShape,
    is_compatible,
)

from services.xapi_nlp.nlp_utils import contains_any

from services.xapi_nlp.nlp_constants import (
    MATERIAL_USAGE_SIGNALS,
    MAINTENANCE_KEYWORDS,
    REPAIR_KEYWORDS,
    DISTRIBUTION_KEYWORDS,
    FAULT_KEYWORDS,
    COST_KEYWORDS,
    HISTORY_KEYWORDS,
    NEXT_MAINTENANCE_KEYWORDS,
    SEASONAL_SHAPE_KEYWORDS,
    TIME_SERIES_KEYWORDS,
    TREND_KEYWORDS,
    COMPARISON_KEYWORDS,
    TOP_LIST_KEYWORDS,
)


# ============================================================================
# INTENT SHAPE REFINER CLASS
# ============================================================================

class IntentShapeRefiner:
    """
    Intent ve shape'i heuristiklerle rafine eder.
    
    12 farklı heuristic kuralı içerir:
        0. NEXT_MAINTENANCE - En yüksek öncelik
        1. Zaman + "en çok" + Malzeme → MATERIAL_USAGE + TIME_SERIES
        2. Araç ID + Malzeme → MATERIAL_USAGE
        3. Araç ID + History → MAINTENANCE_HISTORY
        3B. [Grup] göre en çok + Malzeme → TOP_PER_GROUP
        4. Mevsim + Malzeme → MATERIAL_USAGE + SEASONAL
        5. "En çok" + Malzeme → MATERIAL_USAGE + TOP_LIST
        6. Bakım + Onarım + Dağılım → MAINTENANCE_HISTORY
        7. Arıza sinyali → FAULT_ANALYSIS
        8. Maliyet sinyali → COST_ANALYSIS
        9. Mevsim shape → SEASONAL
        10. Karşılaştırma → COMPARISON_ANALYSIS
        11. Müşteri ID → CUSTOMER_ANALYSIS
        12. Servis lokasyonu → SERVICE_ANALYSIS
    """
    
    def refine(
        self,
        intent: QuestionType,
        shape: OutputShape,
        intent_conf: float,
        shape_conf: float,
        qn: str,
        entities: ExtractedEntities,
    ) -> Tuple[QuestionType, OutputShape, float, float]:
        """
        Intent ve shape'i heuristiklerle rafine eder.
        
        Args:
            intent: İlk tespit edilen intent
            shape: İlk tespit edilen shape
            intent_conf: Intent confidence skoru
            shape_conf: Shape confidence skoru
            qn: Normalize edilmiş sorgu
            entities: Çıkarılmış varlıklar
            
        Returns:
            Tuple[QuestionType, OutputShape, float, float]: 
                Rafine edilmiş (intent, shape, intent_conf, shape_conf)
        """
        
        # ═══════════════════════════════════════════════════════════════════
        # Heuristic 0: NEXT_MAINTENANCE - En yüksek öncelik
        # ═══════════════════════════════════════════════════════════════════
        result = self._check_next_maintenance(qn)
        if result:
            return result

        # ═══════════════════════════════════════════════════════════════════
        # Heuristic 0B: Fiyat artışı
        # ═══════════════════════════════════════════════════════════════════
        result = self._check_price_increase(qn, intent_conf)
        if result:
            return result
        
        # Ortak sinyaller
        has_material_signal = contains_any(qn, MATERIAL_USAGE_SIGNALS) or "malzeme" in qn

        # ═══════════════════════════════════════════════════════════════════
        # Heuristic 1: Zaman + "en çok" + Malzeme → MATERIAL_USAGE + TIME_SERIES
        # ═══════════════════════════════════════════════════════════════════
        result = self._check_material_time_series(qn, entities, has_material_signal, intent_conf, shape_conf)
        if result:
            return result
        
        # ═══════════════════════════════════════════════════════════════════
        # Heuristic 2: Araç ID + Malzeme → MATERIAL_USAGE
        # ═══════════════════════════════════════════════════════════════════
        if entities.vehicle_ids and has_material_signal:
            return (
                QuestionType.MATERIAL_USAGE,
                shape,
                min(intent_conf + 0.4, 1.0),
                shape_conf,
            )
        
        # ═══════════════════════════════════════════════════════════════════
        # Heuristic 3: Araç ID + History → MAINTENANCE_HISTORY + DETAIL_LIST
        # ═══════════════════════════════════════════════════════════════════
        if entities.vehicle_ids and contains_any(qn, HISTORY_KEYWORDS):
            if not has_material_signal:
                return (
                    QuestionType.MAINTENANCE_HISTORY,
                    OutputShape.DETAIL_LIST,
                    min(intent_conf + 0.4, 1.0),
                    0.9,
                )
        
        # ═══════════════════════════════════════════════════════════════════
        # Heuristic 3B: [Grup] göre en çok + Malzeme → TOP_PER_GROUP
        # ═══════════════════════════════════════════════════════════════════
        result = self._check_top_per_group(qn, entities, has_material_signal, intent_conf)
        if result:
            return result
        
        # ═══════════════════════════════════════════════════════════════════
        # Heuristic 4: Mevsim + Malzeme → MATERIAL_USAGE + SEASONAL
        # ═══════════════════════════════════════════════════════════════════
        if entities.seasons and contains_any(qn, MATERIAL_USAGE_SIGNALS):
            return (
                QuestionType.MATERIAL_USAGE,
                OutputShape.SEASONAL,
                min(intent_conf + 0.3, 1.0),
                0.9,
            )
        
        # ═══════════════════════════════════════════════════════════════════
        # Heuristic 5: "En çok" + Malzeme → MATERIAL_USAGE + TOP_LIST
        # ═══════════════════════════════════════════════════════════════════
        if entities.has_top_signal and has_material_signal:
            return (
                QuestionType.MATERIAL_USAGE,
                OutputShape.TOP_LIST,
                min(intent_conf + 0.3, 1.0),
                0.9,
            )
        
        # ═══════════════════════════════════════════════════════════════════
        # Heuristic 6: Bakım + Onarım + Dağılım → MAINTENANCE_HISTORY
        # ═══════════════════════════════════════════════════════════════════
        result = self._check_maintenance_distribution(qn, intent_conf)
        if result:
            return result
        
        # ═══════════════════════════════════════════════════════════════════
        # Heuristic 7: Arıza Sinyali → FAULT_ANALYSIS
        # ═══════════════════════════════════════════════════════════════════
        if contains_any(qn, FAULT_KEYWORDS) or entities.fault_codes:
            return (
                QuestionType.FAULT_ANALYSIS,
                shape if is_compatible(QuestionType.FAULT_ANALYSIS, shape) else OutputShape.TOP_LIST,
                min(intent_conf + 0.3, 1.0),
                shape_conf,
            )
        
        # ═══════════════════════════════════════════════════════════════════
        # Heuristic 8: Maliyet Sinyali → COST_ANALYSIS
        # ═══════════════════════════════════════════════════════════════════
        if contains_any(qn, COST_KEYWORDS):
            # Trend sinyali varsa TREND, yoksa SUMMARY
            if contains_any(qn, TREND_KEYWORDS):
                return (
                    QuestionType.COST_ANALYSIS,
                    OutputShape.TREND,
                    min(intent_conf + 0.3, 1.0),
                    0.9,
                )
            return (
                QuestionType.COST_ANALYSIS,
                shape if is_compatible(QuestionType.COST_ANALYSIS, shape) else OutputShape.SUMMARY,
                min(intent_conf + 0.3, 1.0),
                shape_conf,
            )
        
        # ═══════════════════════════════════════════════════════════════════
        # Heuristic 9: Mevsim Shape → SEASONAL
        # ═══════════════════════════════════════════════════════════════════
        if entities.seasons or contains_any(qn, SEASONAL_SHAPE_KEYWORDS):
            return (
                intent,
                OutputShape.SEASONAL,
                intent_conf,
                0.8,
            )
        
        # ═══════════════════════════════════════════════════════════════════
        # Heuristic 10: Karşılaştırma → COMPARISON_ANALYSIS + COMPARISON
        # ═══════════════════════════════════════════════════════════════════
        if entities.comparison_entities or contains_any(qn, COMPARISON_KEYWORDS):
            return (
                QuestionType.COMPARISON_ANALYSIS,
                OutputShape.COMPARISON,
                min(intent_conf + 0.3, 1.0),
                0.9,
            )
        
        # ═══════════════════════════════════════════════════════════════════
        # Heuristic 11: Müşteri ID → CUSTOMER_ANALYSIS
        # ═══════════════════════════════════════════════════════════════════
        if entities.customer_ids:
            return (
                QuestionType.CUSTOMER_ANALYSIS,
                shape if is_compatible(QuestionType.CUSTOMER_ANALYSIS, shape) else OutputShape.TOP_LIST,
                min(intent_conf + 0.3, 1.0),
                shape_conf,
            )

        # ═══════════════════════════════════════════════════════════════════
        # Heuristic 12: Servis Lokasyonu → SERVICE_ANALYSIS
        # ═══════════════════════════════════════════════════════════════════
        if entities.service_locations:
            return (
                QuestionType.SERVICE_ANALYSIS,
                shape if is_compatible(QuestionType.SERVICE_ANALYSIS, shape) else OutputShape.TOP_LIST,
                min(intent_conf + 0.3, 1.0),
                shape_conf,
            )

        # Varsayılan: olduğu gibi döner
        return (intent, shape, intent_conf, shape_conf)
    
    # ========================================================================
    # PRIVATE HELPER METHODS
    # ========================================================================
    
    def _check_next_maintenance(self, qn: str):
        """NEXT_MAINTENANCE heuristic'i"""
        if contains_any(qn, NEXT_MAINTENANCE_KEYWORDS):
            return (
                QuestionType.NEXT_MAINTENANCE,
                OutputShape.SEQUENCE,
                1.0,
                1.0,
            )
        return None
    
    def _check_price_increase(self, qn: str, intent_conf: float):
        """Fiyat artışı heuristic'i"""
        has_price = contains_any(qn, COST_KEYWORDS) or "fiyat" in qn or "fiyati" in qn
        has_increase = "artan" in qn or "artis" in qn or "artisi" in qn or contains_any(qn, TREND_KEYWORDS)

        if has_price and has_increase:
            # Mevsim kırılımı varsa: her mevsimde top aile
            if contains_any(qn, SEASONAL_SHAPE_KEYWORDS) or "mevsimlere gore" in qn or "mevsimlere" in qn:
                return (
                    QuestionType.COST_ANALYSIS,
                    OutputShape.TOP_PER_GROUP,
                    min(intent_conf + 0.4, 1.0),
                    0.9,
                )
            return (
                QuestionType.COST_ANALYSIS,
                OutputShape.TOP_LIST,
                min(intent_conf + 0.4, 1.0),
                0.9,
            )
        return None
    
    def _check_material_time_series(
        self, 
        qn: str, 
        entities: ExtractedEntities, 
        has_material_signal: bool,
        intent_conf: float,
        shape_conf: float
    ):
        """Zaman + en çok + malzeme heuristic'i"""
        has_time_dimension = any(p in qn for p in TIME_SERIES_KEYWORDS)
        
        if has_time_dimension and entities.has_top_signal and has_material_signal:
            return (
                QuestionType.MATERIAL_USAGE,
                OutputShape.TIME_SERIES,
                min(intent_conf + 0.3, 1.0),
                min(shape_conf + 0.3, 1.0),
            )
        return None
    
    def _check_top_per_group(
        self, 
        qn: str, 
        entities: ExtractedEntities, 
        has_material_signal: bool,
        intent_conf: float
    ):
        """Grup bazlı top listesi heuristic'i"""
        
        # Mevsim bazlı grup
        has_seasonal_group = any(p in qn for p in [
            "mevsimlere gore", "mevsime gore", "her mevsim",
            "mevsimde", "mevsimlerde", "mevsim bazinda"
        ])
        
        if has_seasonal_group and entities.has_top_signal and has_material_signal:
            return (
                QuestionType.MATERIAL_USAGE,
                OutputShape.TOP_PER_GROUP,
                min(intent_conf + 0.4, 1.0),
                0.95,
            )
        
        # Model bazlı grup
        has_model_group = any(p in qn for p in [
            "modellere gore",
            "modellerine gore",
            "modeline gore",
            "her model",
            "modellerde",
            "model bazinda",
            "arac modellerine gore",
            "arac modeline gore",
            "arac modeli",
            "model no",
            "model numarasi",
        ])
        
        if has_model_group and entities.has_top_signal and has_material_signal:
            return (
                QuestionType.MATERIAL_USAGE,
                OutputShape.TOP_PER_GROUP,
                min(intent_conf + 0.4, 1.0),
                0.95,
            )
        
        # Tip bazlı grup
        has_type_group = any(p in qn for p in [
            "tiplere gore",
            "tiplerine gore",
            "tipine gore",
            "her tip",
            "tip bazinda",
            "arac tipi",
            "arac tipleri",
            "arac tipine gore",
            "arac tiplerine gore",
            "arac tipi icin",
        ])
        
        if has_type_group and entities.has_top_signal and has_material_signal:
            return (
                QuestionType.MATERIAL_USAGE,
                OutputShape.TOP_PER_GROUP,
                min(intent_conf + 0.4, 1.0),
                0.95,
            )
        
        return None
    
    def _check_maintenance_distribution(self, qn: str, intent_conf: float):
        """Bakım/onarım dağılımı heuristic'i"""
        has_maintenance = any(k in qn for k in MAINTENANCE_KEYWORDS)
        has_repair = any(k in qn for k in REPAIR_KEYWORDS)
        has_distribution = any(k in qn for k in DISTRIBUTION_KEYWORDS)

        if has_maintenance and has_repair and has_distribution:
            # Zaman/grup ifadelerine göre shape belirle
            if any(p in qn for p in ["yillara gore", "yil bazinda", "yillik"]):
                return (
                    QuestionType.MAINTENANCE_HISTORY,
                    OutputShape.TIME_SERIES,
                    0.9,
                    0.9,
                )
            if any(p in qn for p in ["mevsimlere gore", "mevsim bazinda", "mevsimsel"]):
                return (
                    QuestionType.MAINTENANCE_HISTORY,
                    OutputShape.SEASONAL,
                    0.9,
                    0.9,
                )
            # Model bazında → PIVOT (vehicleModel x verbType)
            if any(p in qn for p in [
                "model bazinda", "modele gore", "modellere gore",
                "arac modeli", "arac modelleri", "arac modellerinin",
                "her model", "model icin",
            ]):
                return (
                    QuestionType.MAINTENANCE_HISTORY,
                    OutputShape.PIVOT,
                    0.9,
                    0.9,
                )
            if any(p in qn for p in ["arac tiplerine gore", "tip bazinda", "arac tipi"]):
                return (
                    QuestionType.MAINTENANCE_HISTORY,
                    OutputShape.PIVOT,
                    0.9,
                    0.9,
                )
            # Default: sadece verbType dağılımı
            return (
                QuestionType.MAINTENANCE_HISTORY,
                OutputShape.DISTRIBUTION,
                0.9,
                0.9,
            )
        
        return None


# ============================================================================
# PUBLIC API
# ============================================================================

__all__ = [
    "IntentShapeRefiner",
]
