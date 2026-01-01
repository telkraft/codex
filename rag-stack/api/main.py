"""
main.py
=======

RAG-Stack API giriş noktası.

Bu dosya:
- FastAPI uygulamasını oluşturur,
- CORS ayarlarını yapar,
- route modüllerini uygulamaya ekler,
- basit sağlık ve bilgi endpoint'leri sağlar.

🆕 v0.5.0: 5 LLM Provider Desteği
    - Local (Ollama)
    - Groq Cloud
    - OpenRouter
    - Google AI Studio (Gemini)
    - Cerebras
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes_chat import router as chat_router
from api.routes_ingest import router as ingest_router
from api.routes_search import router as search_router
from api.routes_collections import router as collections_router
from api.routes_lrs_stats import router as lrs_stats_router
from api.routes_schema import router as schema_router
from api.routes_quick_queries import router as quick_queries_router
from api.routes_email import router as email_router
from api.routes_llm import router as llm_router

# ============================================================================
# Uygulama Kurulumu
# ============================================================================

app = FastAPI(
    title="Promptever RAG Stack API",
    description=(
        "MAN Türkiye servis verileri için LRS tabanlı istatistik, "
        "örnek deneyim ve LLM analiz/öngörü hizmeti. "
        "RAG altyapısı hazır, MVP'de LRS → LLM zinciri aktif. "
        "6 LLM Provider desteği: Local, Groq, OpenRouter, Google, Cerebras, Mistral."
    ),
    version="0.5.0-multi-provider",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# Router Kayıtları
# ============================================================================

app.include_router(chat_router)
app.include_router(ingest_router)
app.include_router(search_router)
app.include_router(collections_router)
app.include_router(lrs_stats_router)
app.include_router(schema_router)
app.include_router(quick_queries_router)
app.include_router(email_router)
app.include_router(llm_router)


# ============================================================================
# Basit Bilgi / Sağlık Endpoint'leri
# ============================================================================


@app.get("/")
async def root():
    """
    Basit karşılama endpoint'i.
    """
    return {
        "name": "Promptever RAG Stack API",
        "version": "0.5.0-multi-provider",
        "endpoints": [
            "/chat",
            "/xapi/ingest",
            "/search",
            "/collections",
            "/lrs/stats/general",
            "/quick-queries",
            "/llm/config",
            "/llm/providers",
            "/llm/health",
            "/llm/test",
            "/health",
            "/models",
        ],
        "llm_providers": [
            "local (Ollama)",
            "groq (Groq Cloud)",
            "openrouter (200+ models)",
            "google (Gemini)",
            "cerebras (Ultra-fast)",
            "mistral (Mistral AI)",
        ],
        "description": (
            "LRS tabanlı istatistik + örnek xAPI deneyim + LLM yorumu sağlayan API. "
            "Bu sürümde 6 LLM provider desteği: Local, Groq, OpenRouter, Google, Cerebras, Mistral."
        ),
    }


@app.get("/health")
async def health():
    """
    Sağlık kontrolü için tüm servisleri kontrol eden endpoint.
    """
    details = {
        "api": "alive",
    }

    # MongoDB LRS kontrolü
    try:
        from config import mongo_client
        mongo_client.admin.command('ping')
        details["mongodb"] = "alive"
    except Exception:
        details["mongodb"] = "dead"

    # Qdrant kontrolü
    try:
        from config import qdrant_client
        if qdrant_client:
            qdrant_client.get_collections()
            details["qdrant"] = "alive"
        else:
            details["qdrant"] = "not_configured"
    except Exception:
        details["qdrant"] = "dead"

    # 🆕 LLM Provider kontrolü (5 provider)
    try:
        from services.llm_providers import LLMProviderFactory
        provider_health = LLMProviderFactory.health_check_all()
        details["llm_providers"] = provider_health

        # Eski ollama alanı için geriye dönük uyumluluk
        details["ollama"] = "alive" if provider_health.get("local", False) else "dead"
        
        # Kaç provider çalışıyor?
        active_providers = sum(1 for v in provider_health.values() if v)
        details["active_llm_providers"] = active_providers
        
    except Exception:
        details["ollama"] = "dead"
        details["llm_providers"] = {
            "local": False,
            "groq": False,
            "openrouter": False,
            "google": False,
            "cerebras": False,
            "mistral": False,
        }
        details["active_llm_providers"] = 0

    # Genel durum
    core_services = [details.get("api"), details.get("mongodb")]
    all_core_alive = all(v == "alive" for v in core_services)

    # En az bir LLM provider çalışıyorsa OK
    has_llm = details.get("active_llm_providers", 0) > 0

    return {
        "status": "ok" if (all_core_alive and has_llm) else "degraded",
        "details": details,
    }


@app.get("/models")
async def get_models():
    """
    Geriye dönük uyumluluk: Eski /models endpoint'i.

    Yeni yapıda /llm/providers/{provider_id}/models kullanılmalı.
    Bu endpoint sadece local (Ollama) modelleri döndürür.
    """
    try:
        from services.llm_providers import LLMProviderFactory
        models = LLMProviderFactory.get_provider_models("local")
        return {"models": [m.value for m in models]}
    except Exception:
        return {"models": ["gemma2:2b", "llama3.1:8b", "qwen2.5:0.5b"]}


@app.get("/llm-summary")
async def llm_summary():
    """
    LLM provider özet bilgisi.
    
    Tüm provider'ların durumunu ve model sayılarını gösterir.
    """
    try:
        from services.llm_providers import LLMProviderFactory
        from config import PROVIDERS_CONFIG
        
        health = LLMProviderFactory.health_check_all()
        
        summary = []
        for provider_id, config in PROVIDERS_CONFIG.items():
            models = LLMProviderFactory.get_provider_models(provider_id)
            summary.append({
                "id": provider_id,
                "name": config.get("name"),
                "icon": config.get("icon"),
                "healthy": health.get(provider_id, False),
                "model_count": len(models),
                "pricing": config.get("pricing"),
                "latency": config.get("latency"),
            })
        
        return {
            "providers": summary,
            "total_providers": len(summary),
            "active_providers": sum(1 for p in summary if p["healthy"]),
            "total_models": sum(p["model_count"] for p in summary),
        }
        
    except Exception as exc:
        return {"error": str(exc)}
