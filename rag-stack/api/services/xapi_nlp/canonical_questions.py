# canonical_questions_v2.py
"""
2-Katmanlı Canonical Questions Mimarisi
========================================

Bu modül, xAPI statement'lardan çıkarılabilecek tüm soru tiplerini
2 katmanlı bir yapıda tanımlar:

KATMAN 1 - Intent (QuestionType): Sorunun KONUSU (NE soruluyor?)
KATMAN 2 - Shape (OutputShape): Verinin SUNUMU (NASIL gösterilecek?)

Bu separation of concerns yaklaşımı:
- M intent × N shape = M×N kombinasyon tek codebase'de
- MongoDB pipeline'ları shape'e göre genelleştirilir
- Yeni soru tipleri kolayca eklenir

Trigger keyword'ler nlp_constants.py'den alınır (Single Source of Truth).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from services.xapi_nlp.nlp_utils import (
    normalize,
    normalize_tr,
    extract_year,
    extract_month,
    extract_season,
    extract_relative_period,
)
from services.xapi_nlp.nlp_constants import (
    INTENT_TRIGGERS,
    SHAPE_TRIGGERS,
    DIMENSION_TRIGGERS,
    # Backward compatibility
    QUESTION_SIGNALS,
)


# ============================================================================
# KATMAN 1: INTENT (NE?)
# ============================================================================

class QuestionType(str, Enum):
    """
    Sorunun KONUSUNU belirler.
    
    Her intent için:
    - Hangi domain'den veri çekilecek?
    - Hangi base dimension'lar geçerli?
    - Hangi metric'ler anlamlı?
    """
    
    # Operasyonel Analiz
    MATERIAL_USAGE = "material_usage"
    COST_ANALYSIS = "cost_analysis"
    FAULT_ANALYSIS = "fault_analysis"
    MAINTENANCE_HISTORY = "maintenance_history"
    
    # Varlık Bazlı Analiz
    VEHICLE_ANALYSIS = "vehicle_analysis"
    CUSTOMER_ANALYSIS = "customer_analysis"
    SERVICE_ANALYSIS = "service_analysis"
    
    # İlişkisel Analiz
    PATTERN_ANALYSIS = "pattern_analysis"
    NEXT_MAINTENANCE = "next_maintenance"
    
    # Karşılaştırma
    COMPARISON_ANALYSIS = "comparison_analysis"


# ============================================================================
# KATMAN 2: SHAPE (NASIL?)
# ============================================================================

class OutputShape(str, Enum):
    """
    Verinin SUNUM ŞEKLİNİ belirler.
    
    Her shape için:
    - Nasıl gruplandırılacak?
    - Nasıl sıralanacak?
    - Nasıl formatlanacak?
    """
    
    # Liste Bazlı
    TOP_LIST = "top_list"           # En çok/en az N tane
    DETAIL_LIST = "detail_list"     # Detaylı kayıt listesi
    
    # Zaman Bazlı
    TIME_SERIES = "time_series"     # Yıl/ay/hafta bazında
    SEASONAL = "seasonal"           # Mevsimsel gruplandırma
    
    # Dağılım / Oran
    DISTRIBUTION = "distribution"   # Yüzdesel dağılım
    PIVOT = "pivot"                 # İki boyutlu çapraz tablo
    
    # Grup İçi
    TOP_PER_GROUP = "top_per_group" # Her grup için en çok N
    
    # Karşılaştırma
    COMPARISON = "comparison"       # Entity karşılaştırması
    
    # Pattern
    SEQUENCE = "sequence"           # Ardışık ilişki
    TREND = "trend"                 # Yükseliş/düşüş analizi
    
    # Aggregation
    SUMMARY = "summary"             # Tek değerli özet


# ============================================================================
# CANONICAL QUESTION DATACLASS
# ============================================================================

@dataclass
class CanonicalQuestion:
    """
    2-Katmanlı Canonical Question Tanımı
    
    Intent + Shape kombinasyonu ile query'nin tam karakteristiğini belirler.
    """
    
    # ─────────────────────────────────────────────────────────────
    # KATMAN 1 & 2
    # ─────────────────────────────────────────────────────────────
    question_type: QuestionType
    output_shape: OutputShape
    
    # ─────────────────────────────────────────────────────────────
    # DIMENSION KONFİGÜRASYONU
    # ─────────────────────────────────────────────────────────────
    primary_dimension: str
    """Ana gruplama alanı (TOP_LIST için: materialName, faultCode, vehicle, etc.)"""
    
    secondary_dimension: Optional[str] = None
    """PIVOT için ikinci boyut (vehicleType × materialName)"""
    
    time_dimension: Optional[str] = None
    """TIME_SERIES/SEASONAL için: 'year', 'month', 'season', 'year_month'"""
    
    group_dimension: Optional[str] = None
    """TOP_PER_GROUP için gruplama alanı"""
    
    # ─────────────────────────────────────────────────────────────
    # METRİK KONFİGÜRASYONU
    # ─────────────────────────────────────────────────────────────
    metrics: List[str] = field(default_factory=lambda: ["count"])
    """Hesaplanacak metrikler: count, sum_quantity, sum_cost, avg_cost, etc."""
    
    sort_metric: str = "count"
    """Sıralama için kullanılacak metrik"""
    
    sort_order: str = "desc"
    """'desc' (büyükten küçüğe) veya 'asc' (küçükten büyüğe)"""
    
    # ─────────────────────────────────────────────────────────────
    # LİMİT VE FİLTRE
    # ─────────────────────────────────────────────────────────────
    default_limit: int = 10
    """TOP_LIST, TOP_PER_GROUP için varsayılan limit"""
    
    default_filters: Optional[Dict[str, Any]] = None
    """Otomatik uygulanan filtreler (örn: hasFault: True for FAULT_ANALYSIS)"""
    
    # ─────────────────────────────────────────────────────────────
    # TETİKLEYİCİ VE METADATA
    # ─────────────────────────────────────────────────────────────
    extra_triggers: List[str] = field(default_factory=list)
    """Ekstra tetikleyiciler (nlp_constants'taki listelere ek olarak)"""
    
    description: str = ""
    examples: List[str] = field(default_factory=list)
    
    # ─────────────────────────────────────────────────────────────
    # HELPER METHODS
    # ─────────────────────────────────────────────────────────────
    
    def get_intent_triggers(self) -> List[str]:
        """Intent için trigger listesini döner (nlp_constants'tan)"""
        return INTENT_TRIGGERS.get(self.question_type.value, [])
    
    def get_shape_triggers(self) -> List[str]:
        """Shape için trigger listesini döner (nlp_constants'tan)"""
        return SHAPE_TRIGGERS.get(self.output_shape.value, [])
    
    def get_all_triggers(self) -> List[str]:
        """Tüm tetikleyicileri birleştir"""
        triggers = []
        triggers.extend(self.get_intent_triggers())
        triggers.extend(self.get_shape_triggers())
        triggers.extend(self.extra_triggers)
        return triggers
    
    def matches_query(self, normalized_query: str) -> Tuple[bool, float]:
        """
        Query'nin bu canonical question ile eşleşip eşleşmediğini kontrol et.
        
        Returns:
            (matches: bool, confidence: float)
        """
        triggers = self.get_all_triggers()
        if not triggers:
            return False, 0.0
        
        matched = sum(1 for t in triggers if t in normalized_query)
        if matched == 0:
            return False, 0.0
        
        # Confidence: matched / min(4, total_triggers)
        confidence = matched / min(4, len(triggers))
        return True, min(confidence, 1.0)


# ============================================================================
# INTENT × SHAPE UYUMLULUK MATRİSİ
# ============================================================================

INTENT_SHAPE_COMPATIBILITY: Dict[QuestionType, List[OutputShape]] = {
    QuestionType.MATERIAL_USAGE: [
        OutputShape.TOP_LIST,
        OutputShape.DETAIL_LIST,
        OutputShape.TIME_SERIES,
        OutputShape.SEASONAL,
        OutputShape.DISTRIBUTION,
        OutputShape.PIVOT,
        OutputShape.TOP_PER_GROUP,
        OutputShape.TREND,
    ],
    QuestionType.COST_ANALYSIS: [
        OutputShape.TOP_LIST,
        OutputShape.TIME_SERIES,
        OutputShape.SEASONAL,
        OutputShape.DISTRIBUTION,
        OutputShape.PIVOT,
        OutputShape.TREND,
        OutputShape.SUMMARY,
        OutputShape.COMPARISON,
    ],
    QuestionType.FAULT_ANALYSIS: [
        OutputShape.TOP_LIST,
        OutputShape.TIME_SERIES,
        OutputShape.SEASONAL,
        OutputShape.DISTRIBUTION,
        OutputShape.TOP_PER_GROUP,
    ],
    QuestionType.MAINTENANCE_HISTORY: [
        OutputShape.DETAIL_LIST,
        OutputShape.TIME_SERIES,
        OutputShape.SEASONAL,
        OutputShape.DISTRIBUTION,
        OutputShape.SUMMARY,
        OutputShape.PIVOT,  # 🆕 Model/tip bazında bakım-onarım dağılımı
    ],
    QuestionType.VEHICLE_ANALYSIS: [
        OutputShape.TOP_LIST,
        OutputShape.DETAIL_LIST,
        OutputShape.TIME_SERIES,
        OutputShape.DISTRIBUTION,
    ],
    QuestionType.CUSTOMER_ANALYSIS: [
        OutputShape.TOP_LIST,
        OutputShape.DETAIL_LIST,
        OutputShape.DISTRIBUTION,
    ],
    QuestionType.SERVICE_ANALYSIS: [
        OutputShape.TOP_LIST,
        OutputShape.TIME_SERIES,
        OutputShape.DISTRIBUTION,
    ],
    QuestionType.NEXT_MAINTENANCE: [
        OutputShape.SEQUENCE,
        OutputShape.TOP_LIST,
    ],
    QuestionType.PATTERN_ANALYSIS: [
        OutputShape.SEQUENCE,
        OutputShape.TOP_LIST,
    ],
    QuestionType.COMPARISON_ANALYSIS: [
        OutputShape.COMPARISON,
    ],
}


def is_compatible(intent: QuestionType, shape: OutputShape) -> bool:
    """Intent ve shape uyumlu mu?"""
    compatible_shapes = INTENT_SHAPE_COMPATIBILITY.get(intent, [])
    return shape in compatible_shapes


# ============================================================================
# DEFAULT SHAPE PER INTENT
# ============================================================================

DEFAULT_SHAPE_FOR_INTENT: Dict[QuestionType, OutputShape] = {
    QuestionType.MATERIAL_USAGE: OutputShape.TOP_LIST,
    QuestionType.COST_ANALYSIS: OutputShape.SUMMARY,
    QuestionType.FAULT_ANALYSIS: OutputShape.TOP_LIST,
    QuestionType.MAINTENANCE_HISTORY: OutputShape.DETAIL_LIST,
    QuestionType.VEHICLE_ANALYSIS: OutputShape.TOP_LIST,
    QuestionType.CUSTOMER_ANALYSIS: OutputShape.TOP_LIST,
    QuestionType.SERVICE_ANALYSIS: OutputShape.TOP_LIST,
    QuestionType.NEXT_MAINTENANCE: OutputShape.SEQUENCE,
    QuestionType.PATTERN_ANALYSIS: OutputShape.SEQUENCE,
    QuestionType.COMPARISON_ANALYSIS: OutputShape.COMPARISON,
}


# ============================================================================
# DEFAULT PRIMARY DIMENSION PER INTENT
# ============================================================================

DEFAULT_DIMENSION_FOR_INTENT: Dict[QuestionType, str] = {
    QuestionType.MATERIAL_USAGE: "materialName",
    QuestionType.COST_ANALYSIS: "materialName",
    QuestionType.FAULT_ANALYSIS: "faultCode",
    QuestionType.MAINTENANCE_HISTORY: "operationDate",
    QuestionType.VEHICLE_ANALYSIS: "vehicle",
    QuestionType.CUSTOMER_ANALYSIS: "customer",
    QuestionType.SERVICE_ANALYSIS: "serviceLocation",
    QuestionType.NEXT_MAINTENANCE: "materialName",
    QuestionType.PATTERN_ANALYSIS: "materialName",
    QuestionType.COMPARISON_ANALYSIS: "vehicleType",
}


# ============================================================================
# CANONICAL QUESTION REGISTRY
# ============================================================================

CANONICAL_QUESTIONS_V2: List[CanonicalQuestion] = [
    
    # ════════════════════════════════════════════════════════════════════════
    # MATERIAL_USAGE KOMBINASYONLARI
    # ════════════════════════════════════════════════════════════════════════
    
    CanonicalQuestion(
        question_type=QuestionType.MATERIAL_USAGE,
        output_shape=OutputShape.TOP_LIST,
        primary_dimension="materialName",
        metrics=["count", "sum_quantity", "sum_cost"],
        sort_metric="sum_quantity",
        default_limit=10,
        description="En çok kullanılan malzemeler listesi",
        examples=[
            "En çok kullanılan malzemeler hangileri?",
            "Son 12 ayda en çok değişen parçalar neler?",
            "En fazla tüketilen 5 malzeme",
        ],
    ),
    
    CanonicalQuestion(
        question_type=QuestionType.MATERIAL_USAGE,
        output_shape=OutputShape.SEASONAL,
        primary_dimension="materialName",
        time_dimension="season",
        metrics=["count", "sum_quantity"],
        sort_metric="count",
        default_limit=10,
        description="Mevsimlere göre malzeme kullanımı",
        examples=[
            "Kış mevsiminde en çok kullanılan malzemeler",
            "Mevsimlere göre malzeme dağılımı",
            "Yaz aylarında hangi parçalar değişiyor?",
        ],
    ),
    
    CanonicalQuestion(
        question_type=QuestionType.MATERIAL_USAGE,
        output_shape=OutputShape.TOP_PER_GROUP,
        primary_dimension="materialName",
        group_dimension="vehicleType",
        metrics=["count", "sum_quantity"],
        sort_metric="count",
        default_limit=5,
        extra_triggers=["arac tipi", "her tip"],
        description="Her araç tipi için en çok kullanılan malzemeler",
        examples=[
            "Araç tiplerine göre en çok kullanılan malzemeler",
            "Her araç tipi için top 5 malzeme",
        ],
    ),

    CanonicalQuestion(
        question_type=QuestionType.MATERIAL_USAGE,
        output_shape=OutputShape.TOP_PER_GROUP,
        primary_dimension="materialName",
        group_dimension="vehicleModel",
        metrics=["count", "sum_quantity"],
        sort_metric="count",
        default_limit=5,
        extra_triggers=["model", "her model", "modele gore"],
        description="Her araç modeli için en çok kullanılan malzemeler",
        examples=[
            "Araç modellerine göre en çok kullanılan malzemeler nedir?",
            "Her model için en çok değişen parçalar",
        ],
    ),
    
    # 🆕 Mevsimlere göre en çok kullanılan malzemeler (yıl × mevsim × top N)
    CanonicalQuestion(
        question_type=QuestionType.MATERIAL_USAGE,
        output_shape=OutputShape.TOP_PER_GROUP,
        primary_dimension="materialName",
        group_dimension="season",
        time_dimension="year",  # 🆕 Yıl bazında gruplama desteği
        metrics=["count", "sum_quantity"],
        sort_metric="count",
        default_limit=5,
        extra_triggers=[
            "mevsim", "mevsimlere gore", "mevsime gore", 
            "her mevsim", "mevsimde", "mevsimlerde",
            "yillara ve mevsimlere", "yillar ve mevsimler",
        ],
        description="Her yıl ve mevsim için en çok kullanılan malzemeler (year × season × top N)",
        examples=[
            "Son 2 yılda mevsimlere göre en çok kullanılan malzemeler nedir?",
            "Son 3 yılda mevsimlere göre en çok hangi malzemeler kullanıldı?",
            "Mevsimlere göre en çok kullanılan malzemeler nedir?",
            "Her mevsimde en çok değişen parçalar",
            "Yıllara ve mevsimlere göre en çok kullanılan malzemeler",
        ],
    ),

    CanonicalQuestion(
        question_type=QuestionType.MATERIAL_USAGE,
        output_shape=OutputShape.TIME_SERIES,
        primary_dimension="materialName",
        time_dimension="year",
        metrics=["count", "sum_quantity", "sum_cost"],
        sort_metric="count",
        sort_order="asc",
        description="yıllara göre en çok kullanılan malzemeler",
        examples=[
            "Yıllara göre malzeme kullanımı nasıl değişti?",
            "2020-2024 arası malzeme trendleri",
        ],
    ),
    
    CanonicalQuestion(
        question_type=QuestionType.MATERIAL_USAGE,
        output_shape=OutputShape.PIVOT,
        primary_dimension="materialName",
        secondary_dimension="season",
        time_dimension="year",
        metrics=["count", "sum_quantity"],
        extra_triggers=["yillara ve mevsimlere", "capraz"],
        description="Yıllara ve mevsimlere göre malzeme pivot tablosu",
        examples=[
            "Yıllara ve mevsimlere göre en çok kullanılan malzemeler hangileri?",
        ],
    ),
    
    # ════════════════════════════════════════════════════════════════════════
    # FAULT_ANALYSIS KOMBINASYONLARI
    # ════════════════════════════════════════════════════════════════════════
    
    CanonicalQuestion(
        question_type=QuestionType.FAULT_ANALYSIS,
        output_shape=OutputShape.TOP_LIST,
        primary_dimension="faultCode",
        metrics=["count"],
        sort_metric="count",
        default_limit=10,
        default_filters={"hasFault": True},
        description="En sık görülen arızalar",
        examples=[
            "En sık görülen arızalar hangileri?",
            "En çok tekrar eden 10 arıza kodu",
            "Hangi arızalar en yaygın?",
        ],
    ),
    
    CanonicalQuestion(
        question_type=QuestionType.FAULT_ANALYSIS,
        output_shape=OutputShape.SEASONAL,
        primary_dimension="faultCode",
        time_dimension="season",
        metrics=["count"],
        sort_metric="count",
        default_filters={"hasFault": True},
        description="Mevsimsel olarak artan arızalar",
        examples=[
            "Mevsimsel olarak artan spesifik arızalar hangileri?",
            "Kış aylarında hangi arızalar artıyor?",
        ],
    ),
    
    CanonicalQuestion(
        question_type=QuestionType.FAULT_ANALYSIS,
        output_shape=OutputShape.TOP_PER_GROUP,
        primary_dimension="faultCode",
        group_dimension="vehicleModel",
        metrics=["count"],
        sort_metric="count",
        default_limit=5,
        default_filters={"hasFault": True},
        extra_triggers=["model", "modelde", "belirli model"],
        description="Her araç modelinde en çok görülen arızalar",
        examples=[
            "Belirli bir modelde en çok tekrar eden arızalar hangileri?",
            "Model bazında arıza dağılımı",
        ],
    ),

    CanonicalQuestion(
        question_type=QuestionType.FAULT_ANALYSIS,
        output_shape=OutputShape.TREND,
        primary_dimension="faultCode",
        time_dimension="auto",  # year | month | season router belirler
        metrics=["count"],
        default_filters={"hasFault": True},
        extra_triggers=[
            "artan",
            "artis",
            "yukselen",
            "trend",
            "zamanla",
        ],
        description="Zaman içinde frekansı artan arızalar",
        examples=[
            "Yıllara göre artan arızalar hangileri?",
            "Mevsimsel olarak artan arızalar hangileri?",
            "Son 2 yılda artan arızalar hangileri?",
        ],
    ),

    # 🆕 Günlere göre arıza dağılımı
    CanonicalQuestion(
        question_type=QuestionType.FAULT_ANALYSIS,
        output_shape=OutputShape.DISTRIBUTION,
        primary_dimension="dayOfWeek",
        metrics=["count"],
        sort_metric="count",
        default_filters={"hasFault": True},
        extra_triggers=[
            "gunlere gore", "gunlerine gore",
            "gun bazinda", "gunlere",
            "haftanin gunleri", "hangi gunlerde",
        ],
        description="Haftanın günlerine göre arıza dağılımı",
        examples=[
            "Günlerine göre arıza dağılımı nedir?",
            "Hangi günlerde daha çok arıza görülüyor?",
            "Arızaların günlere göre dağılımı",
            "Haftanın hangi gününde en çok arıza oluyor?",
        ],
    ),

    # ════════════════════════════════════════════════════════════════════════
    # VEHICLE_ANALYSIS KOMBINASYONLARI
    # ════════════════════════════════════════════════════════════════════════
    
    CanonicalQuestion(
        question_type=QuestionType.VEHICLE_ANALYSIS,
        output_shape=OutputShape.TOP_LIST,
        primary_dimension="vehicleModel",
        metrics=["count", "sum_cost"],
        sort_metric="count",
        default_limit=10,
        extra_triggers=["model", "modeli", "modelleri"],
        description="Servise en çok gelen araç modelleri",
        examples=[
            "Servise en çok gelen araç modeli hangisi?",
            "En çok işlem yapılan 10 araç modeli",
        ],
    ),
    
    CanonicalQuestion(
        question_type=QuestionType.VEHICLE_ANALYSIS,
        output_shape=OutputShape.TOP_LIST,
        primary_dimension="vehicle",
        metrics=["count", "sum_cost"],
        sort_metric="count",
        default_limit=10,
        extra_triggers=["plaka", "araclar"],
        description="Servise en çok gelen araçlar (plaka bazlı)",
        examples=[
            "Servise en çok gelen araçlar hangileri?",
            "En sık gelen 10 araç",
        ],
    ),
    
    CanonicalQuestion(
        question_type=QuestionType.VEHICLE_ANALYSIS,
        output_shape=OutputShape.TOP_LIST,
        primary_dimension="vehicleType",
        metrics=["count", "sum_cost"],
        sort_metric="count",
        default_limit=10,
        extra_triggers=["tip", "tipi", "tipleri"],
        description="Servise en çok gelen araç tipleri",
        examples=[
            "Kış mevsiminde servise en çok hangi araç tipleri geliyor?",
            "Araç tipi bazında servis girişleri",
        ],
    ),
    
    CanonicalQuestion(
        question_type=QuestionType.VEHICLE_ANALYSIS,
        output_shape=OutputShape.TOP_LIST,
        primary_dimension="vehicleModel",
        metrics=["repeat_rate", "count"],
        sort_metric="repeat_rate",
        default_limit=10,
        extra_triggers=["tekrar", "yeniden", "giris orani"],
        description="Tekrar giriş oranı en yüksek araç modelleri",
        examples=[
            "Tekrar giriş oranı en yüksek araç modeli hangisi?",
        ],
    ),
    
    # ════════════════════════════════════════════════════════════════════════
    # CUSTOMER_ANALYSIS KOMBINASYONLARI
    # ════════════════════════════════════════════════════════════════════════
    
    CanonicalQuestion(
        question_type=QuestionType.CUSTOMER_ANALYSIS,
        output_shape=OutputShape.TOP_LIST,
        primary_dimension="customer",
        metrics=["count", "sum_cost"],
        sort_metric="count",
        default_limit=10,
        description="Servise en çok gelen müşteriler",
        examples=[
            "Servise en çok gelen müşteriler hangileri?",
            "En aktif 10 müşteri",
        ],
    ),
    
    # ════════════════════════════════════════════════════════════════════════
    # MAINTENANCE_HISTORY KOMBINASYONLARI
    # ════════════════════════════════════════════════════════════════════════
    
    CanonicalQuestion(
        question_type=QuestionType.MAINTENANCE_HISTORY,
        output_shape=OutputShape.DETAIL_LIST,
        primary_dimension="operationDate",
        metrics=["count", "sum_cost"],
        sort_metric="operationDate",
        sort_order="desc",
        default_limit=50,
        extra_triggers=["gecmis", "kayit", "kayitlar"],
        description="Araç bakım geçmişi detay listesi",
        examples=[
            "Araç 39001'in bakım geçmişi nasıl?",
            "70886 aracının tüm kayıtları",
        ],
    ),
    
    CanonicalQuestion(
        question_type=QuestionType.MAINTENANCE_HISTORY,
        output_shape=OutputShape.TIME_SERIES,
        primary_dimension="verbType",
        time_dimension="month",
        metrics=["count"],
        sort_metric="period",
        sort_order="asc",
        extra_triggers=["ay bazinda", "aylik", "aylara"],
        description="Ay bazında bakım/onarım sayıları",
        examples=[
            "Ay bazında yapılan bakım/onarım sayıları nasıl değişiyor?",
            "Aylık işlem sayıları",
        ],
    ),
    
    # 🆕 DASHBOARD: Yıllara göre bakım/onarım dağılımı
    CanonicalQuestion(
        question_type=QuestionType.MAINTENANCE_HISTORY,
        output_shape=OutputShape.TIME_SERIES,
        primary_dimension="verbType",
        time_dimension="year",
        metrics=["count"],
        sort_metric="period",
        sort_order="asc",
        extra_triggers=["yillara gore", "yil bazinda", "yillik"],
        description="Yıllara göre bakım/onarım dağılımı",
        examples=[
            "Yıllara göre bakım ve onarım işlemlerinin dağılımı nedir?",
            "Yıl bazında bakım-onarım sayıları",
        ],
    ),
    
    # 🆕 DASHBOARD: Mevsimlere göre bakım/onarım dağılımı
    CanonicalQuestion(
        question_type=QuestionType.MAINTENANCE_HISTORY,
        output_shape=OutputShape.SEASONAL,
        primary_dimension="verbType",
        time_dimension="season",
        metrics=["count"],
        sort_metric="count",
        extra_triggers=["mevsimlere gore bakim", "mevsim bazinda bakim", "mevsimsel bakim"],
        description="Mevsimlere göre bakım/onarım dağılımı",
        examples=[
            "Mevsimlere göre bakım ve onarım işlemlerinin dağılımı nedir?",
            "Mevsimsel bakım-onarım analizi",
        ],
    ),
    
    # 🆕 DASHBOARD: Araç tiplerine göre bakım/onarım dağılımı
    CanonicalQuestion(
        question_type=QuestionType.MAINTENANCE_HISTORY,
        output_shape=OutputShape.PIVOT,
        primary_dimension="verbType",
        secondary_dimension="vehicleType",
        metrics=["count"],
        sort_metric="count",
        extra_triggers=["arac tiplerine gore bakim", "tip bazinda bakim", "arac tipi bakim"],
        description="Araç tiplerine göre bakım/onarım dağılımı (pivot)",
        examples=[
            "Araç tiplerine göre bakım ve onarım işlemlerinin dağılımı nedir?",
            "Araç tipi bazında bakım-onarım analizi",
        ],
    ),
    
    CanonicalQuestion(
        question_type=QuestionType.MAINTENANCE_HISTORY,
        output_shape=OutputShape.DISTRIBUTION,
        primary_dimension="verbType",
        # secondary_dimension kaldırıldı - DISTRIBUTION sadece verbType üzerinden gruplama yapmalı
        metrics=["count"],
        description="Bakım ve onarım işlemlerinin dağılımı",
        examples=[
            "Bakım ve onarım işlemlerinin dağılımı nedir?",
        ],
    ),
    
    # 🆕 Araç modeli bazlı bakım/onarım için ayrı PIVOT CQ
    CanonicalQuestion(
        question_type=QuestionType.MAINTENANCE_HISTORY,
        output_shape=OutputShape.PIVOT,
        primary_dimension="verbType",
        secondary_dimension="vehicleModel",
        metrics=["count"],
        extra_triggers=["arac modeli", "model bazinda", "modellere gore bakim", "modellere gore onarim"],
        description="Araç modellerine göre bakım/onarım dağılımı (pivot)",
        examples=[
            "Araç modellerinin işlem tiplerinin yüzdesel oranı nedir?",
            "Model bazında bakım-onarım dağılımı",
        ],
    ),
    
    CanonicalQuestion(
        question_type=QuestionType.MAINTENANCE_HISTORY,
        output_shape=OutputShape.TIME_SERIES,
        primary_dimension="count",
        time_dimension="dayOfWeek",
        metrics=["count"],
        sort_metric="count",
        sort_order="desc",
        extra_triggers=["gun", "hangi gun", "gunler", "zirve"],
        description="Hangi günlerde servis girişleri zirve yapıyor",
        examples=[
            "Hangi günlerde servis girişleri zirve yapıyor?",
            "Haftanın en yoğun günleri",
        ],
    ),

    CanonicalQuestion(
        question_type=QuestionType.MAINTENANCE_HISTORY,
        output_shape=OutputShape.DISTRIBUTION,
        primary_dimension="dayOfWeek",
        metrics=["count"],
        sort_metric="count",
        extra_triggers=["gunlere gore", "haftanin gunleri", "gun bazinda", "gunlere"],
        description="Haftanın günlerine göre bakım/onarım dağılımı",
        examples=[
            "Bakım ve onarımın günlere göre dağılımı nedir?",
            "Günlere göre arıza dağılımı nedir?",
            "Haftanın günlerine göre malzeme kullanımı dağılımı",
        ],
    ),
    
    CanonicalQuestion(
        question_type=QuestionType.MAINTENANCE_HISTORY,
        output_shape=OutputShape.PIVOT,
        primary_dimension="dayOfWeek",
        secondary_dimension="verbType",
        metrics=["count"],
        sort_metric="count",
        extra_triggers=["gunlere gore bakim onarim", "haftanin gunleri bakim"],
        description="Haftanın günlerine ve işlem tipine göre pivot tablo",
        examples=[
            "Günlere göre bakım ve onarım işlemlerinin dağılımı",
            "Haftanın hangi gününde hangi araç modellerine işlem yapılıyor?",
        ],
    ),
    
    CanonicalQuestion(
        question_type=QuestionType.MAINTENANCE_HISTORY,
        output_shape=OutputShape.TIME_SERIES,
        primary_dimension="dayOfWeek",
        time_dimension="dayOfWeek",
        metrics=["count"],
        sort_metric="count",
        extra_triggers=["gunlere gore trend", "gunluk seyir"],
        description="Günlere göre işlem trendi",
        examples=[
            "Günlere göre servis girişleri nasıl değişiyor?",
        ],
    ),

    # 🆕 PIVOT - Model bazında bakım-onarım dağılımı
    CanonicalQuestion(
        question_type=QuestionType.MAINTENANCE_HISTORY,
        output_shape=OutputShape.PIVOT,
        primary_dimension="vehicleModel",
        secondary_dimension="verbType",
        metrics=["count"],
        sort_metric="count",
        extra_triggers=[
            "model bazinda", "modele gore", "modellere gore",
            "arac modeli", "arac modelleri", "arac modellerinin",
            "her model icin", "model icin",
        ],
        description="Araç modeli bazında bakım-onarım dağılımı (pivot)",
        examples=[
            "Model bazında bakım-onarım dağılımı",
            "Araç modellerinin bakım-onarım dağılımı",
            "Her model için bakım ve onarım sayıları",
            "Modellere göre işlem dağılımı",
        ],
    ),

    # 🆕 PIVOT - Tip bazında bakım-onarım dağılımı
    CanonicalQuestion(
        question_type=QuestionType.MAINTENANCE_HISTORY,
        output_shape=OutputShape.PIVOT,
        primary_dimension="vehicleType",
        secondary_dimension="verbType",
        metrics=["count"],
        sort_metric="count",
        extra_triggers=[
            "tip bazinda", "tipe gore", "tiplere gore",
            "arac tipi", "arac tipleri", "arac tiplerinin",
            "her tip icin", "tip icin",
        ],
        description="Araç tipi bazında bakım-onarım dağılımı (pivot)",
        examples=[
            "Bakım ve onarımın araç tiplerine göre dağılımı",
            "Araç tiplerine göre bakım-onarım dağılımı",
            "Her araç tipi için bakım ve onarım sayıları",
            "Araç tiplerine göre bakım ve onarım dağılımı",
        ],
    ),

    # ════════════════════════════════════════════════════════════════════════
    # COST_ANALYSIS KOMBINASYONLARI
    # ════════════════════════════════════════════════════════════════════════
    
    CanonicalQuestion(
        question_type=QuestionType.COST_ANALYSIS,
        output_shape=OutputShape.TREND,
        primary_dimension="materialName",
        time_dimension="year",
        metrics=["avg_cost", "change_rate"],
        sort_metric="change_rate",
        sort_order="desc",
        default_limit=10,
        extra_triggers=["fiyat", "artis", "artan"],
        description="Fiyatı en çok artan malzemeler",
        examples=[
            "Son 3 yılda fiyatı en çok artan malzemeler hangileri?",
            "Maliyet artış trendi",
        ],
    ),
    
    CanonicalQuestion(
        question_type=QuestionType.COST_ANALYSIS,
        output_shape=OutputShape.TREND,
        primary_dimension="materialFamily",
        time_dimension="season",
        metrics=["avg_cost", "change_rate"],
        sort_metric="change_rate",
        sort_order="desc",
        extra_triggers=["malzeme ailesi", "aile", "kategori"],
        description="Mevsimlere göre fiyatı en çok artan malzeme aileleri",
        examples=[
            "Son 4 yılda mevsimlere göre fiyatı en çok artan malzeme aileleri hangileri?",
        ],
    ),
    
    CanonicalQuestion(
        question_type=QuestionType.COST_ANALYSIS,
        output_shape=OutputShape.SUMMARY,
        primary_dimension="total",
        metrics=["sum_cost", "avg_cost", "count"],
        description="Toplam maliyet özeti",
        examples=[
            "Toplam bakım maliyeti ne kadar?",
            "2020 yılı toplam harcama",
        ],
    ),
    
    # ════════════════════════════════════════════════════════════════════════
    # NEXT_MAINTENANCE KOMBINASYONLARI
    # ════════════════════════════════════════════════════════════════════════
    
    CanonicalQuestion(
        question_type=QuestionType.NEXT_MAINTENANCE,
        output_shape=OutputShape.SEQUENCE,
        primary_dimension="materialName",
        metrics=["count", "probability"],
        sort_metric="count",
        default_limit=10,
        description="Bir malzeme kullanıldığında sonraki bakımda ne değişir",
        examples=[
            "RHC 404 (400) model araçlarda, SENSÖR malzemesi kullanıldığında bir sonraki bakımda hangi malzemeler daha sık değişiyor?",
            "Araç 48640'ın bakım geçmişine göre hangi malzemeler sık değişmiş?",
        ],
    ),
    
    # ════════════════════════════════════════════════════════════════════════
    # SERVICE_ANALYSIS KOMBINASYONLARI
    # ════════════════════════════════════════════════════════════════════════
    
    CanonicalQuestion(
        question_type=QuestionType.SERVICE_ANALYSIS,
        output_shape=OutputShape.TIME_SERIES,
        primary_dimension="serviceLocation",
        time_dimension="week",
        metrics=["count"],
        sort_metric="period",
        extra_triggers=["hafta", "haftalik"],
        description="Haftalık servis girişleri",
        examples=[
            "Ay içinde hangi haftalarda ani artışlar var?",
            "Haftalık servis yoğunluğu",
        ],
    ),
    
    CanonicalQuestion(
        question_type=QuestionType.SERVICE_ANALYSIS,
        output_shape=OutputShape.TOP_LIST,
        primary_dimension="serviceLocation",
        metrics=["count", "sum_cost"],
        sort_metric="count",
        default_limit=10,
        description="En yoğun servisler",
        examples=[
            "Hangi servisler en yoğun?",
            "Servis bazında işlem sayıları",
        ],
    ),
]


# ============================================================================
# YARDIMCI FONKSİYONLAR
# ============================================================================

def get_cq_by_type_and_shape(
    question_type: QuestionType,
    output_shape: OutputShape,
) -> Optional[CanonicalQuestion]:
    """Belirli bir intent + shape kombinasyonu için CQ döner"""
    for cq in CANONICAL_QUESTIONS_V2:
        if cq.question_type == question_type and cq.output_shape == output_shape:
            return cq
    return None


def find_best_matching_cq(
    normalized_query: str,
    min_confidence: float = 0.3,
) -> List[Tuple[CanonicalQuestion, float]]:
    """
    Query için en uygun canonical question'ları bul.
    
    Returns:
        List of (cq, confidence) tuples, sorted by confidence descending
    """
    matches = []
    
    for cq in CANONICAL_QUESTIONS_V2:
        is_match, confidence = cq.matches_query(normalized_query)
        if is_match and confidence >= min_confidence:
            matches.append((cq, confidence))
    
    # Sort by confidence
    matches.sort(key=lambda x: x[1], reverse=True)
    
    return matches


def detect_intent(normalized_query: str) -> Tuple[QuestionType, float]:
    """
    Query'den intent tespit et.
    
    Returns:
        (QuestionType, confidence)
    """
    scores: Dict[str, float] = {}
    
    for intent_name, triggers in INTENT_TRIGGERS.items():
        matched = sum(1 for t in triggers if t in normalized_query)
        if matched > 0:
            scores[intent_name] = matched / min(3, len(triggers))
    
    if not scores:
        return QuestionType.MAINTENANCE_HISTORY, 0.3
    
    best = max(scores, key=scores.get)
    return QuestionType(best), min(scores[best], 1.0)


def detect_shape(
    normalized_query: str,
    intent: Optional[QuestionType] = None,
) -> Tuple[OutputShape, float]:
    """
    Query'den shape tespit et.
    
    Args:
        normalized_query: Normalize edilmiş sorgu
        intent: Tespit edilmiş intent (default shape belirlemek için)
    
    Returns:
        (OutputShape, confidence)
    """
    scores: Dict[str, float] = {}
    
    for shape_name, triggers in SHAPE_TRIGGERS.items():
        matched = sum(1 for t in triggers if t in normalized_query)
        if matched > 0:
            scores[shape_name] = matched / min(3, len(triggers))
    
    if not scores:
        # Default shape based on intent
        default_shape = DEFAULT_SHAPE_FOR_INTENT.get(
            intent, OutputShape.TOP_LIST
        ) if intent else OutputShape.TOP_LIST
        return default_shape, 0.5
    
    best = max(scores, key=scores.get)
    return OutputShape(best), min(scores[best], 1.0)


def detect_dimension(normalized_query: str) -> Tuple[Optional[str], float]:
    """
    Query'den primary dimension tespit et.
    
    Returns:
        (dimension_name, confidence) veya (None, 0) if not found
    """
    scores: Dict[str, float] = {}
    
    for dim_name, triggers in DIMENSION_TRIGGERS.items():
        matched = sum(1 for t in triggers if t in normalized_query)
        if matched > 0:
            scores[dim_name] = matched / min(2, len(triggers))
    
    if not scores:
        return None, 0.0
    
    best = max(scores, key=scores.get)
    return best, min(scores[best], 1.0)


# ============================================================================
# BACKWARD COMPATIBILITY
# ============================================================================

# Eski QuestionType değerlerini yeni yapıya map et
LEGACY_QUESTION_TYPE_MAPPING = {
    "top_entities": (None, OutputShape.TOP_LIST),
    "time_series": (None, OutputShape.TIME_SERIES),
    "distribution": (None, OutputShape.DISTRIBUTION),
    "seasonal": (None, OutputShape.SEASONAL),
    "comparison": (None, OutputShape.COMPARISON),
    "trend": (None, OutputShape.TREND),
    "pattern": (QuestionType.NEXT_MAINTENANCE, OutputShape.SEQUENCE),
    "vehicle_based": (QuestionType.VEHICLE_ANALYSIS, None),
    "customer_based": (QuestionType.CUSTOMER_ANALYSIS, None),
    "service_based": (QuestionType.SERVICE_ANALYSIS, None),
}


# ============================================================================
# MODULE TEST
# ============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("CANONICAL QUESTIONS V2 - 2-Katmanlı Mimari")
    print("=" * 70)
    print(f"\nToplam CQ Tanımı: {len(CANONICAL_QUESTIONS_V2)}")
    
    print("\nIntent Türleri:")
    for qt in QuestionType:
        count = sum(1 for cq in CANONICAL_QUESTIONS_V2 if cq.question_type == qt)
        print(f"  - {qt.value}: {count} kombinasyon")
    
    print("\nShape Türleri:")
    for os in OutputShape:
        count = sum(1 for cq in CANONICAL_QUESTIONS_V2 if cq.output_shape == os)
        print(f"  - {os.value}: {count} kullanım")
    
    # Test query
    test_queries = [
        "En çok kullanılan malzemeler hangileri?",
        "Kış mevsiminde en çok hangi malzemeler kullanılıyor?",
        "Araç modellerine göre en çok kullanılan malzemeler nedir?",
        "70886 aracının bakım geçmişi nasıl?",
        "Ay bazında yapılan bakım sayıları nasıl değişiyor?",
    ]
    
    print("\nTest Sorguları:")
    for q in test_queries:
        qn = normalize_tr(q)
        intent, intent_conf = detect_intent(qn)
        shape, shape_conf = detect_shape(qn, intent)
        print(f"\n  Q: {q}")
        print(f"  → Intent: {intent.value} ({intent_conf:.0%})")
        print(f"  → Shape: {shape.value} ({shape_conf:.0%})")