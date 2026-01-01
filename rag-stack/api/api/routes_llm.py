"""
api/routes_llm.py
=================

LLM Konfigürasyon API Endpoint'leri

Bu modül, frontend'in LLM ayarlarını dinamik olarak almasını sağlar:
- Provider listesi ve modelleri (5 provider)
- Rol listesi
- Davranış listesi
- Varsayılan değerler
- Provider sağlık durumları

🆕 v0.5.0: 6 Provider Desteği
    - Local (Ollama)
    - Groq Cloud
    - OpenRouter
    - Google AI Studio (Gemini)
    - Cerebras
    - Mistral AI

Endpoint'ler:
- GET /llm/config - Tüm LLM konfigürasyonu
- GET /llm/providers - Provider listesi
- GET /llm/providers/{provider_id}/models - Belirli provider'ın modelleri
- GET /llm/health - Provider sağlık durumları
- POST /llm/test - Provider test endpoint'i
"""

from __future__ import annotations

from typing import List, Dict, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from models import (
    LLMConfigResponse,
    ProviderInfo,
    ProviderModelInfo,
    RoleInfo,
    BehaviorInfo,
    LLMDefaults,
    LLMAnalysis,
)

from config import (
    LLM_ROLES,
    LLM_BEHAVIORS,
    DEFAULT_LLM_PROVIDER,
    DEFAULT_LLM_MODEL,
    DEFAULT_LLM_ROLE,
    DEFAULT_LLM_BEHAVIOR,
    PROVIDERS_CONFIG,
)

from services.llm_providers import LLMProviderFactory

router = APIRouter(prefix="/llm", tags=["llm"])


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================


class LLMTestRequest(BaseModel):
    """LLM test isteği."""
    provider: str
    model: str
    prompt: str = "Merhaba, bu bir test mesajıdır. Kısaca yanıt ver."
    system_prompt: Optional[str] = None


class LLMTestResponse(BaseModel):
    """LLM test yanıtı."""
    success: bool
    provider: str
    model: str
    answer: Optional[str] = None
    latency_sec: Optional[float] = None
    error: Optional[str] = None


class ProviderHealthResponse(BaseModel):
    """Provider sağlık yanıtı."""
    provider_id: str
    healthy: bool
    latency_ms: Optional[float] = None


# ============================================================================
# ENDPOINTS
# ============================================================================


@router.get("/config", response_model=LLMConfigResponse)
async def get_llm_config() -> LLMConfigResponse:
    """
    Tüm LLM konfigürasyonunu döndür.

    Frontend bu endpoint'i chat sayfası yüklenirken çağırır ve
    tüm dropdown'ları bu verilerle doldurur.

    Response:
    {
        "providers": [...],  // 5 provider
        "roles": [...],
        "behaviors": [...],
        "defaults": {
            "provider": "groq",
            "model": "llama-3.3-70b-versatile",
            "role": "servis_analisti",
            "behavior": "balanced"
        }
    }
    """

    # Provider listesi (modelleriyle birlikte)
    providers = LLMProviderFactory.list_providers()

    # Roller
    roles = [RoleInfo(**r) for r in LLM_ROLES]

    # Davranışlar
    behaviors = [BehaviorInfo(**b) for b in LLM_BEHAVIORS]

    # Varsayılan değerler
    defaults = LLMDefaults(
        provider=DEFAULT_LLM_PROVIDER,
        model=DEFAULT_LLM_MODEL,
        role=DEFAULT_LLM_ROLE,
        behavior=DEFAULT_LLM_BEHAVIOR,
    )

    return LLMConfigResponse(
        providers=providers,
        roles=roles,
        behaviors=behaviors,
        defaults=defaults,
    )


@router.get("/providers", response_model=List[ProviderInfo])
async def list_providers() -> List[ProviderInfo]:
    """
    Kullanılabilir tüm LLM provider'ların listesi.

    Her provider için:
    - id, name, icon, description
    - models listesi
    - default_model
    - pricing, latency bilgileri
    
    🆕 6 Provider:
    - local: Ollama (yerel)
    - groq: Groq Cloud (LPU, ultra hızlı)
    - openrouter: OpenRouter (200+ model)
    - google: Google AI Studio (Gemini)
    - cerebras: Cerebras (2100 token/sn)
    - mistral: Mistral AI (Codestral dahil)
    """
    return LLMProviderFactory.list_providers()


@router.get("/providers/{provider_id}", response_model=ProviderInfo)
async def get_provider(provider_id: str) -> ProviderInfo:
    """
    Belirli bir provider'ın detaylı bilgisi.

    Args:
        provider_id: "local", "groq", "openrouter", "google", "cerebras", "mistral"

    Returns:
        Provider bilgisi (modeller dahil)

    Raises:
        404: Provider bulunamazsa
    """
    if provider_id not in PROVIDERS_CONFIG:
        raise HTTPException(
            status_code=404,
            detail=f"Provider bulunamadı: {provider_id}. Geçerli değerler: {list(PROVIDERS_CONFIG.keys())}",
        )

    provider = LLMProviderFactory.get_provider(provider_id)
    return provider.get_info()


@router.get("/providers/{provider_id}/models", response_model=List[ProviderModelInfo])
async def get_provider_models(provider_id: str) -> List[ProviderModelInfo]:
    """
    Belirli bir provider'ın kullanılabilir model listesi.

    Args:
        provider_id: "local", "groq", "openrouter", "google", "cerebras", "mistral"

    Returns:
        Model listesi (value, label, description)

    Raises:
        404: Provider bulunamazsa
    """
    if provider_id not in PROVIDERS_CONFIG:
        raise HTTPException(
            status_code=404,
            detail=f"Provider bulunamadı: {provider_id}. Geçerli değerler: {list(PROVIDERS_CONFIG.keys())}",
        )

    return LLMProviderFactory.get_provider_models(provider_id)


@router.get("/health", response_model=Dict[str, bool])
async def check_providers_health() -> Dict[str, bool]:
    """
    Tüm LLM provider'ların sağlık durumu.

    Returns:
        {
            "local": true,
            "groq": true,
            "openrouter": true,
            "google": true,
            "cerebras": false
        }
    """
    return LLMProviderFactory.health_check_all()


@router.get("/health/{provider_id}", response_model=ProviderHealthResponse)
async def check_provider_health(provider_id: str) -> ProviderHealthResponse:
    """
    Belirli bir provider'ın sağlık durumu.

    Args:
        provider_id: Provider ID

    Returns:
        Sağlık durumu ve latency

    Raises:
        404: Provider bulunamazsa
    """
    if provider_id not in PROVIDERS_CONFIG:
        raise HTTPException(
            status_code=404,
            detail=f"Provider bulunamadı: {provider_id}",
        )

    import time
    t0 = time.time()
    
    try:
        provider = LLMProviderFactory.get_provider(provider_id)
        healthy = provider.health_check()
        latency_ms = (time.time() - t0) * 1000
    except Exception:
        healthy = False
        latency_ms = None

    return ProviderHealthResponse(
        provider_id=provider_id,
        healthy=healthy,
        latency_ms=latency_ms,
    )


@router.post("/test", response_model=LLMTestResponse)
async def test_provider(request: LLMTestRequest) -> LLMTestResponse:
    """
    Belirli bir provider/model kombinasyonunu test et.

    Bu endpoint, frontend'den provider ayarlarını test etmek için kullanılır.
    Kısa bir prompt gönderir ve yanıt alır.

    Args:
        request: Test isteği (provider, model, prompt)

    Returns:
        Test sonucu (success, answer, latency, error)
    """
    if request.provider not in PROVIDERS_CONFIG:
        return LLMTestResponse(
            success=False,
            provider=request.provider,
            model=request.model,
            error=f"Geçersiz provider: {request.provider}",
        )

    try:
        provider = LLMProviderFactory.get_provider(request.provider)
        
        result = provider.generate(
            prompt=request.prompt,
            model=request.model,
            system_prompt=request.system_prompt,
            temperature=0.7,
            max_tokens=256,  # Test için kısa
        )

        # Hata kontrolü
        if result.answer and result.answer.startswith("[") and "Hata" in result.answer:
            return LLMTestResponse(
                success=False,
                provider=request.provider,
                model=request.model,
                error=result.answer,
            )

        return LLMTestResponse(
            success=True,
            provider=request.provider,
            model=request.model,
            answer=result.answer,
            latency_sec=result.latency_sec,
        )

    except Exception as exc:
        return LLMTestResponse(
            success=False,
            provider=request.provider,
            model=request.model,
            error=str(exc),
        )


@router.get("/roles", response_model=List[RoleInfo])
async def list_roles() -> List[RoleInfo]:
    """
    Kullanılabilir LLM rolleri.

    Bu roller, LLM'in hangi perspektiften yanıt vereceğini belirler.
    """
    return [RoleInfo(**r) for r in LLM_ROLES]


@router.get("/behaviors", response_model=List[BehaviorInfo])
async def list_behaviors() -> List[BehaviorInfo]:
    """
    Kullanılabilir LLM davranışları.

    Bu davranışlar, LLM'in nasıl yanıt vereceğini belirler
    (analitik, yorumlayıcı, öngörüsel, rapor).
    """
    return [BehaviorInfo(**b) for b in LLM_BEHAVIORS]


@router.get("/available", response_model=List[str])
async def get_available_providers() -> List[str]:
    """
    Şu an erişilebilir (sağlıklı) provider'ların listesi.

    Returns:
        Sağlıklı provider ID'leri
    """
    return LLMProviderFactory.get_available_providers()


# ============================================================================
# __all__
# ============================================================================

__all__ = ["router"]
