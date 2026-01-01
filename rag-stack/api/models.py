"""
models.py
=========

Merkezi model tanımları.

- Dış API istek/cevap modelleri (Pydantic BaseModel)
- LRS sorgu planı ve domain senaryoları (dataclass / yardımcı modeller)
- 🆕 LLM Provider modelleri (5 provider desteği)

NOT: Canonical Question modelleri (QuestionType, OutputShape, CanonicalQuestion)
     artık canonical_questions.py dosyasında tanımlıdır.
     
     2-Katmanlı Mimari:
       - KATMAN 1 (Intent): QuestionType - Sorunun konusu (NE?)
       - KATMAN 2 (Shape): OutputShape - Verinin sunumu (NASIL?)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional
from datetime import datetime
from enum import Enum

from pydantic import BaseModel


# ============================================================================
# 🆕 LLM Provider Modelleri
# ============================================================================


class LLMProviderType(str, Enum):
    """
    Desteklenen LLM sağlayıcı tipleri.
    
    🆕 v0.5.0: 6 provider desteği
    """
    LOCAL = "local"           # Ollama (yerel)
    GROQ = "groq"             # Groq Cloud (LPU)
    OPENROUTER = "openrouter" # OpenRouter (multi-model gateway)
    GOOGLE = "google"         # Google AI Studio (Gemini)
    CEREBRAS = "cerebras"     # Cerebras (ultra-fast inference)
    MISTRAL = "mistral"       # Mistral AI (Avrupa'nın lideri)


class ProviderModelInfo(BaseModel):
    """Tek bir model hakkında bilgi."""
    value: str           # Model ID (API'ye gönderilecek)
    label: str           # UI'da gösterilecek isim
    description: str     # Kısa açıklama


class ProviderInfo(BaseModel):
    """Bir LLM sağlayıcı hakkında tam bilgi."""
    id: str                              # Provider ID (local, groq, openrouter, google, cerebras)
    name: str                            # Görünen isim
    icon: str                            # Emoji/ikon
    description: Optional[str] = None    # Açıklama
    models: List[ProviderModelInfo]      # Kullanılabilir modeller
    default_model: str                   # Varsayılan model
    pricing: Optional[str] = None        # Fiyatlandırma bilgisi
    latency: Optional[str] = None        # Tipik gecikme süresi


class RoleInfo(BaseModel):
    """LLM rol bilgisi."""
    value: str           # Rol ID
    label: str           # Görünen isim
    description: str     # Açıklama


class BehaviorInfo(BaseModel):
    """LLM davranış bilgisi."""
    value: str           # Davranış ID
    label: str           # Görünen isim
    description: str     # Açıklama


class LLMDefaults(BaseModel):
    """Varsayılan LLM ayarları."""
    provider: str
    model: str
    role: str
    behavior: str


class LLMConfigResponse(BaseModel):
    """
    /llm/config endpoint'inden dönen tam konfigürasyon.
    
    Frontend bu endpoint'i çağırarak tüm LLM ayarlarını dinamik olarak alır.
    """
    providers: List[ProviderInfo]
    roles: List[RoleInfo]
    behaviors: List[BehaviorInfo]
    defaults: LLMDefaults


# ============================================================================
# Dış API Modelleri (FastAPI endpoint'leri için)
# ============================================================================


class ChatRequest(BaseModel):
    """
    /chat endpoint'ine gelen istek modeli.

    Streamlit tarafındaki payload ile bire bir uyumlu olacak şekilde:
      {
        "query": "...",
        "collection": "man_local_service_maintenance",
        "use_llm": true,
        "limit": 100,
        "provider": "groq",        # 🆕 5 provider destekleniyor
        "model": "llama-3.3-70b-versatile",
        "role": "service_analyst",
        "behavior": "balanced"
      }
    """

    query: str
    collection: Optional[str] = None

    # LLM kullanılsın mı?
    use_llm: bool = True

    # LRS / RAG bağlam limiti
    limit: Optional[int] = 100

    # 🆕 LLM provider (local, groq, openrouter, google, cerebras)
    provider: Optional[str] = None

    # LLM modeli
    model: Optional[str] = None

    # Sistem rolü / persona
    role: Optional[str] = None

    # Davranış modu
    behavior: Optional[str] = "balanced"

    # Soru dili
    language: Optional[str] = "tr"

    # Debug modu
    debug: bool = False


class StatsTable(BaseModel):
    """
    UI'de gösterilecek ve LLM'e bağlam olarak gönderilecek tablo yapısı.
    """

    title: str
    description: Optional[str] = None

    columns: List[str]
    rows: List[Dict[str, Any]]

    meta: Optional[Dict[str, Any]] = None


class ExampleStatement(BaseModel):
    """
    Örnek xAPI statement'ları için sadeleştirilmiş model.
    """

    statement_id: Optional[str] = None
    raw: Optional[Dict[str, Any]] = None

    vehicle_id: Optional[str] = None
    vehicle_model: Optional[str] = None
    vehicle_type: Optional[str] = None

    service_location: Optional[str] = None
    customer_id: Optional[str] = None

    operation_date: Optional[str] = None

    verb_type: Optional[str] = None

    material_name: Optional[str] = None
    material_code: Optional[str] = None
    material_family: Optional[str] = None

    fault_code: Optional[str] = None

    odometer_km: Optional[float] = None
    cost: Optional[float] = None
    discount: Optional[float] = None

    text: str


class LLMAnalysis(BaseModel):
    """
    LLM'in nasıl çalıştığını ve ne ürettiğini anlatan model.
    """

    # 🆕 Hangi provider kullanıldı?
    provider: Optional[str] = None

    # Hangi model kullanıldı?
    model: Optional[str] = None

    # Kullanıcıya gösterilecek ana cevap
    answer: Optional[str] = None

    # Zamanlama bilgileri (sn cinsinden)
    latency_sec: Optional[float] = None

    # Token istatistikleri
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None

    # 🆕 Provider spesifik bilgiler
    provider_info: Optional[Dict[str, Any]] = None

    # Reasoning / zincir açıklaması
    reasoning: Optional[str] = None


class ChatResponse(BaseModel):
    """
    /chat endpoint'inin standart cevap modeli.
    """

    intent: str
    scenario: Optional[str] = None
    summary: Optional[str] = None

    data: Optional[Dict[str, Any]] = None

    tables: Optional[List[StatsTable]] = None
    examples: Optional[List[ExampleStatement]] = None
    llm: Optional[LLMAnalysis] = None


class SearchRequest(BaseModel):
    """
    /search endpoint'i için istek modeli.
    """

    query: str
    collection: str
    limit: int = 10


class XAPIIngestRequest(BaseModel):
    """
    /xapi/ingest endpoint'i için istek modeli.
    """

    lrs_endpoint: str
    username: Optional[str] = None
    password: Optional[str] = None
    collection: str
    limit: Optional[int] = 100
    max_pages: Optional[int] = 10
    page_delay_ms: Optional[int] = 0


class DocumentUploadResponse(BaseModel):
    """
    Doküman yükleme cevap şeması.
    """

    filename: str
    chunks: int
    collection: str
    status: str


# ============================================================================
# LRS Sorgu Planı ve Zaman Modeli
# ============================================================================

@dataclass
class TimeRange:
    """
    LRS tarafında tarih aralığı filtresi için model.
    """

    field: str = "operationDate"

    # Eski string tabanlı alanlar
    start: Optional[str] = None
    end: Optional[str] = None

    # Yeni datetime tabanlı alanlar
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None


@dataclass
class QueryPlan:
    """
    LRS'e karşı çalışacak schema-aware istatistiksel sorgu planı.
    """

    mode: Literal["statistical", "semantic", "hybrid"] = "statistical"

    group_by: List[str] = field(default_factory=list)
    filters: Dict[str, Any] = field(default_factory=dict)
    metrics: List[str] = field(default_factory=list)

    time_range: Optional[TimeRange] = None

    sort_by: Optional[str] = None
    limit: Optional[int] = None


# ============================================================================
# Top Entities & Gelecek Dönem Şeması
# ============================================================================


@dataclass
class FuturePeriodSpec:
    """
    Basit öngörü için zaman dilimi tanımı.
    """

    kind: Literal["month", "season", "year", "last_n_months", "last_n_years"]

    year: Optional[int] = None
    month: Optional[int] = None
    season: Optional[str] = None

    value: Optional[int] = None
    anchor_year: Optional[int] = None
    anchor_month: Optional[int] = None


@dataclass
class TopEntitiesQuestion:
    """
    Eski "en çok gelen ..." sorguları için soru modeli.
    """

    entity_type: str

    question_type: Literal["current_top", "future_top"] = "current_top"

    limit: int = 5

    service_filter: Optional[str] = None
    period: Optional[Dict[str, Any]] = None

    material_filter: Optional[str] = None
    model_filter: Optional[str] = None
    vehicle_filter: Optional[str] = None

    future_period: Optional[FuturePeriodSpec] = None


@dataclass
class PeriodSpec:
    """
    İnsan-dili dönem tanımı.
    """

    kind: Literal["year", "season", "range", "relative", "month"]

    year: Optional[int] = None
    season: Optional[str] = None

    month: Optional[int] = None

    start_date: Optional[str] = None
    end_date: Optional[str] = None

    unit: Optional[Literal["year", "month"]] = None
    value: Optional[int] = None


# ============================================================================
# __all__
# ============================================================================

__all__ = [
    # 🆕 LLM Provider Modelleri
    "LLMProviderType",
    "ProviderModelInfo",
    "ProviderInfo",
    "RoleInfo",
    "BehaviorInfo",
    "LLMDefaults",
    "LLMConfigResponse",
    
    # API Modelleri
    "ChatRequest",
    "ChatResponse",
    "StatsTable",
    "ExampleStatement",
    "LLMAnalysis",
    "SearchRequest",
    "XAPIIngestRequest",
    "DocumentUploadResponse",
    
    # LRS Modelleri
    "TimeRange",
    "QueryPlan",
    
    # Domain/Pattern Modelleri
    "FuturePeriodSpec",
    "TopEntitiesQuestion",
    "PeriodSpec",
]
