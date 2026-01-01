"""
services/llm_providers.py
=========================

LLM Provider Factory ve Provider Implementasyonları.

🆕 v0.5.0: 5 Provider Desteği
    - Local (Ollama)
    - Groq Cloud
    - OpenRouter
    - Google AI Studio (Gemini)
    - Cerebras

Her provider için:
    - API endpoint ve auth
    - Request/Response format dönüşümü
    - Health check
    - Model listesi

Kullanım:
    from services.llm_providers import LLMProviderFactory
    
    provider = LLMProviderFactory.get_provider("groq")
    result = provider.generate(prompt="...", model="llama-3.3-70b-versatile")
"""

from __future__ import annotations

import time
import requests
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Type

from models import LLMAnalysis, ProviderInfo, ProviderModelInfo

from config import (
    # Ollama
    OLLAMA_HOST,
    # API Keys
    GROQ_API_KEY,
    OPENROUTER_API_KEY,
    GOOGLE_API_KEY,
    CEREBRAS_API_KEY,
    MISTRAL_API_KEY,
    # API Endpoints
    GROQ_API_BASE,
    OPENROUTER_API_BASE,
    GOOGLE_API_BASE,
    CEREBRAS_API_BASE,
    MISTRAL_API_BASE,
    # Provider Config
    PROVIDER_MODELS,
    PROVIDER_DEFAULTS,
    PROVIDERS_CONFIG,
    DEBUG,
)


# ============================================================================
# ABSTRACT BASE PROVIDER
# ============================================================================


class BaseLLMProvider(ABC):
    """
    Tüm LLM provider'ların base class'ı.
    
    Her provider bu class'tan türemeli ve şu metodları implement etmeli:
    - generate(): LLM çağrısı
    - health_check(): Sağlık kontrolü
    - get_models(): Model listesi
    - get_default_model(): Varsayılan model
    """
    
    provider_id: str = ""
    
    @abstractmethod
    def generate(
        self,
        prompt: str,
        model: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs,
    ) -> LLMAnalysis:
        """
        LLM'e istek gönder ve yanıt al.
        
        Args:
            prompt: Kullanıcı promptu
            model: Model adı
            system_prompt: Sistem promptu (opsiyonel)
            temperature: Yaratıcılık (0.0-2.0)
            max_tokens: Maksimum token sayısı
            
        Returns:
            LLMAnalysis: Yanıt ve metadata
        """
        pass
    
    @abstractmethod
    def health_check(self) -> bool:
        """
        Provider'ın erişilebilir olup olmadığını kontrol et.
        
        Returns:
            bool: Erişilebilir ise True
        """
        pass
    
    def get_models(self) -> List[ProviderModelInfo]:
        """
        Bu provider için kullanılabilir modellerin listesi.
        
        Returns:
            List[ProviderModelInfo]: Model listesi
        """
        models = PROVIDER_MODELS.get(self.provider_id, [])
        return [ProviderModelInfo(**m) for m in models]
    
    def get_default_model(self) -> str:
        """
        Bu provider için varsayılan model.
        
        Returns:
            str: Model ID
        """
        return PROVIDER_DEFAULTS.get(self.provider_id, "")
    
    def get_info(self) -> ProviderInfo:
        """
        Bu provider hakkında tam bilgi.
        
        Returns:
            ProviderInfo: Provider bilgisi
        """
        config = PROVIDERS_CONFIG.get(self.provider_id, {})
        return ProviderInfo(
            id=self.provider_id,
            name=config.get("name", self.provider_id),
            icon=config.get("icon", "🤖"),
            description=config.get("description"),
            models=self.get_models(),
            default_model=self.get_default_model(),
            pricing=config.get("pricing"),
            latency=config.get("latency"),
        )


# ============================================================================
# LOCAL (OLLAMA) PROVIDER
# ============================================================================


class OllamaProvider(BaseLLMProvider):
    """
    Yerel Ollama sunucusu provider'ı.
    
    Endpoint: http://{OLLAMA_HOST}/api/chat
    Auth: Yok (yerel sunucu)
    """
    
    provider_id = "local"
    
    def generate(
        self,
        prompt: str,
        model: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs,
    ) -> LLMAnalysis:
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        t0 = time.time()
        
        try:
            response = requests.post(
                f"{OLLAMA_HOST}/api/chat",
                json={
                    "model": model,
                    "messages": messages,
                    "stream": False,
                    "options": {
                        "temperature": temperature,
                        "num_predict": max_tokens,
                    },
                },
                timeout=300,
            )
            response.raise_for_status()
            data = response.json()
            
            answer = data.get("message", {}).get("content", "")
            
            # Token istatistikleri (Ollama formatı)
            prompt_tokens = data.get("prompt_eval_count")
            completion_tokens = data.get("eval_count")
            total_tokens = None
            if prompt_tokens and completion_tokens:
                total_tokens = prompt_tokens + completion_tokens
            
        except Exception as exc:
            answer = f"[Ollama Hatası] {exc}"
            prompt_tokens = None
            completion_tokens = None
            total_tokens = None
        
        latency = time.time() - t0
        
        return LLMAnalysis(
            provider=self.provider_id,
            model=model,
            answer=answer,
            latency_sec=latency,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
        )
    
    def health_check(self) -> bool:
        try:
            response = requests.get(
                f"{OLLAMA_HOST}/api/tags",
                timeout=5,
            )
            return response.status_code == 200
        except Exception:
            return False


# ============================================================================
# GROQ PROVIDER
# ============================================================================


class GroqProvider(BaseLLMProvider):
    """
    Groq Cloud provider'ı.
    
    Endpoint: https://api.groq.com/openai/v1/chat/completions
    Auth: Bearer token
    Format: OpenAI uyumlu
    """
    
    provider_id = "groq"
    
    def generate(
        self,
        prompt: str,
        model: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs,
    ) -> LLMAnalysis:
        
        if not GROQ_API_KEY:
            return LLMAnalysis(
                provider=self.provider_id,
                model=model,
                answer="[Hata] GROQ_API_KEY tanımlı değil.",
                latency_sec=0,
            )
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        t0 = time.time()
        
        try:
            response = requests.post(
                f"{GROQ_API_BASE}/chat/completions",
                headers={
                    "Authorization": f"Bearer {GROQ_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                },
                timeout=120,
            )
            response.raise_for_status()
            data = response.json()
            
            answer = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            
            usage = data.get("usage", {})
            prompt_tokens = usage.get("prompt_tokens")
            completion_tokens = usage.get("completion_tokens")
            total_tokens = usage.get("total_tokens")
            
        except requests.exceptions.HTTPError as exc:
            error_detail = ""
            try:
                error_detail = exc.response.json().get("error", {}).get("message", str(exc))
            except Exception:
                error_detail = str(exc)
            answer = f"[Groq API Hatası] {error_detail}"
            prompt_tokens = None
            completion_tokens = None
            total_tokens = None
            
        except Exception as exc:
            answer = f"[Groq Hatası] {exc}"
            prompt_tokens = None
            completion_tokens = None
            total_tokens = None
        
        latency = time.time() - t0
        
        return LLMAnalysis(
            provider=self.provider_id,
            model=model,
            answer=answer,
            latency_sec=latency,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
        )
    
    def health_check(self) -> bool:
        if not GROQ_API_KEY:
            return False
        try:
            response = requests.get(
                f"{GROQ_API_BASE}/models",
                headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
                timeout=10,
            )
            return response.status_code == 200
        except Exception:
            return False


# ============================================================================
# OPENROUTER PROVIDER
# ============================================================================


class OpenRouterProvider(BaseLLMProvider):
    """
    OpenRouter provider'ı.
    
    Endpoint: https://openrouter.ai/api/v1/chat/completions
    Auth: Bearer token
    Format: OpenAI uyumlu
    
    Özellikler:
    - 200+ model desteği (Claude, GPT-4, Gemini, Llama, vb.)
    - Otomatik fallback
    - Kullandıkça öde
    """
    
    provider_id = "openrouter"
    
    def generate(
        self,
        prompt: str,
        model: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs,
    ) -> LLMAnalysis:
        
        if not OPENROUTER_API_KEY:
            return LLMAnalysis(
                provider=self.provider_id,
                model=model,
                answer="[Hata] OPENROUTER_API_KEY tanımlı değil.",
                latency_sec=0,
            )
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        t0 = time.time()
        
        try:
            response = requests.post(
                f"{OPENROUTER_API_BASE}/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://promptever.com",  # OpenRouter için gerekli
                    "X-Title": "Promptever RAG Stack",
                },
                json={
                    "model": model,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                },
                timeout=120,
            )
            response.raise_for_status()
            data = response.json()
            
            answer = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            
            usage = data.get("usage", {})
            prompt_tokens = usage.get("prompt_tokens")
            completion_tokens = usage.get("completion_tokens")
            total_tokens = usage.get("total_tokens")
            
            # OpenRouter ekstra bilgileri
            provider_info = {
                "id": data.get("id"),
                "model_used": data.get("model"),  # Gerçekte kullanılan model
            }
            
        except requests.exceptions.HTTPError as exc:
            error_detail = ""
            try:
                error_detail = exc.response.json().get("error", {}).get("message", str(exc))
            except Exception:
                error_detail = str(exc)
            answer = f"[OpenRouter API Hatası] {error_detail}"
            prompt_tokens = None
            completion_tokens = None
            total_tokens = None
            provider_info = None
            
        except Exception as exc:
            answer = f"[OpenRouter Hatası] {exc}"
            prompt_tokens = None
            completion_tokens = None
            total_tokens = None
            provider_info = None
        
        latency = time.time() - t0
        
        return LLMAnalysis(
            provider=self.provider_id,
            model=model,
            answer=answer,
            latency_sec=latency,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            provider_info=provider_info,
        )
    
    def health_check(self) -> bool:
        if not OPENROUTER_API_KEY:
            return False
        try:
            response = requests.get(
                f"{OPENROUTER_API_BASE}/models",
                headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}"},
                timeout=10,
            )
            return response.status_code == 200
        except Exception:
            return False


# ============================================================================
# GOOGLE AI STUDIO (GEMINI) PROVIDER
# ============================================================================


class GoogleProvider(BaseLLMProvider):
    """
    Google AI Studio (Gemini) provider'ı.
    
    Endpoint: https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent
    Auth: API Key (query param)
    Format: Google özel format
    
    Özellikler:
    - Gemini 1.5/2.0 modelleri
    - 1M+ token context window
    - Multimodal destek
    """
    
    provider_id = "google"
    
    def generate(
        self,
        prompt: str,
        model: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 8192,
        **kwargs,
    ) -> LLMAnalysis:
        
        if not GOOGLE_API_KEY:
            return LLMAnalysis(
                provider=self.provider_id,
                model=model,
                answer="[Hata] GOOGLE_API_KEY tanımlı değil.",
                latency_sec=0,
            )
        
        # Google formatında içerik oluştur
        contents = []
        
        # System instruction (Gemini'de ayrı bir alan)
        system_instruction = None
        if system_prompt:
            system_instruction = {"parts": [{"text": system_prompt}]}
        
        # User message
        contents.append({
            "role": "user",
            "parts": [{"text": prompt}]
        })
        
        t0 = time.time()
        
        try:
            request_body = {
                "contents": contents,
                "generationConfig": {
                    "temperature": temperature,
                    "maxOutputTokens": max_tokens,
                },
            }
            
            if system_instruction:
                request_body["systemInstruction"] = system_instruction
            
            response = requests.post(
                f"{GOOGLE_API_BASE}/models/{model}:generateContent",
                params={"key": GOOGLE_API_KEY},
                headers={"Content-Type": "application/json"},
                json=request_body,
                timeout=120,
            )
            response.raise_for_status()
            data = response.json()
            
            # Gemini response parsing
            candidates = data.get("candidates", [])
            if candidates:
                content = candidates[0].get("content", {})
                parts = content.get("parts", [])
                answer = parts[0].get("text", "") if parts else ""
            else:
                answer = ""
            
            # Token istatistikleri
            usage_metadata = data.get("usageMetadata", {})
            prompt_tokens = usage_metadata.get("promptTokenCount")
            completion_tokens = usage_metadata.get("candidatesTokenCount")
            total_tokens = usage_metadata.get("totalTokenCount")
            
        except requests.exceptions.HTTPError as exc:
            error_detail = ""
            try:
                error_data = exc.response.json()
                error_detail = error_data.get("error", {}).get("message", str(exc))
            except Exception:
                error_detail = str(exc)
            answer = f"[Google AI Hatası] {error_detail}"
            prompt_tokens = None
            completion_tokens = None
            total_tokens = None
            
        except Exception as exc:
            answer = f"[Google AI Hatası] {exc}"
            prompt_tokens = None
            completion_tokens = None
            total_tokens = None
        
        latency = time.time() - t0
        
        return LLMAnalysis(
            provider=self.provider_id,
            model=model,
            answer=answer,
            latency_sec=latency,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
        )
    
    def health_check(self) -> bool:
        if not GOOGLE_API_KEY:
            return False
        try:
            response = requests.get(
                f"{GOOGLE_API_BASE}/models",
                params={"key": GOOGLE_API_KEY},
                timeout=10,
            )
            return response.status_code == 200
        except Exception:
            return False


# ============================================================================
# CEREBRAS PROVIDER
# ============================================================================


class CerebrasProvider(BaseLLMProvider):
    """
    Cerebras Cloud provider'ı.
    
    Endpoint: https://api.cerebras.ai/v1/chat/completions
    Auth: Bearer token
    Format: OpenAI uyumlu
    
    Özellikler:
    - Dünyanın en hızlı inference (2100 token/sn Llama 8B)
    - Wafer-Scale Engine teknolojisi
    - Çok düşük latency
    """
    
    provider_id = "cerebras"
    
    def generate(
        self,
        prompt: str,
        model: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs,
    ) -> LLMAnalysis:
        
        if not CEREBRAS_API_KEY:
            return LLMAnalysis(
                provider=self.provider_id,
                model=model,
                answer="[Hata] CEREBRAS_API_KEY tanımlı değil.",
                latency_sec=0,
            )
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        t0 = time.time()
        
        try:
            response = requests.post(
                f"{CEREBRAS_API_BASE}/chat/completions",
                headers={
                    "Authorization": f"Bearer {CEREBRAS_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                },
                timeout=60,  # Cerebras çok hızlı, kısa timeout yeterli
            )
            response.raise_for_status()
            data = response.json()
            
            answer = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            
            usage = data.get("usage", {})
            prompt_tokens = usage.get("prompt_tokens")
            completion_tokens = usage.get("completion_tokens")
            total_tokens = usage.get("total_tokens")
            
            # Cerebras performans metrikleri
            provider_info = {
                "time_info": data.get("time_info", {}),  # Cerebras'ın detaylı timing bilgisi
            }
            
        except requests.exceptions.HTTPError as exc:
            error_detail = ""
            try:
                error_detail = exc.response.json().get("error", {}).get("message", str(exc))
            except Exception:
                error_detail = str(exc)
            answer = f"[Cerebras API Hatası] {error_detail}"
            prompt_tokens = None
            completion_tokens = None
            total_tokens = None
            provider_info = None
            
        except Exception as exc:
            answer = f"[Cerebras Hatası] {exc}"
            prompt_tokens = None
            completion_tokens = None
            total_tokens = None
            provider_info = None
        
        latency = time.time() - t0
        
        return LLMAnalysis(
            provider=self.provider_id,
            model=model,
            answer=answer,
            latency_sec=latency,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            provider_info=provider_info,
        )
    
    def health_check(self) -> bool:
        if not CEREBRAS_API_KEY:
            return False
        try:
            response = requests.get(
                f"{CEREBRAS_API_BASE}/models",
                headers={"Authorization": f"Bearer {CEREBRAS_API_KEY}"},
                timeout=10,
            )
            return response.status_code == 200
        except Exception:
            return False


# ============================================================================
# MISTRAL AI PROVIDER
# ============================================================================


class MistralProvider(BaseLLMProvider):
    """
    Mistral AI provider'ı.
    
    Endpoint: https://api.mistral.ai/v1/chat/completions
    Auth: Bearer token
    Format: OpenAI uyumlu
    
    Özellikler:
    - Avrupa merkezli AI şirketi
    - Güçlü açık kaynak modeller (Mixtral)
    - Codestral (kod üretimi için optimize)
    - Rekabetçi fiyatlandırma
    """
    
    provider_id = "mistral"
    
    def generate(
        self,
        prompt: str,
        model: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs,
    ) -> LLMAnalysis:
        
        if not MISTRAL_API_KEY:
            return LLMAnalysis(
                provider=self.provider_id,
                model=model,
                answer="[Hata] MISTRAL_API_KEY tanımlı değil.",
                latency_sec=0,
            )
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        t0 = time.time()
        
        try:
            response = requests.post(
                f"{MISTRAL_API_BASE}/chat/completions",
                headers={
                    "Authorization": f"Bearer {MISTRAL_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                },
                timeout=120,
            )
            response.raise_for_status()
            data = response.json()
            
            answer = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            
            usage = data.get("usage", {})
            prompt_tokens = usage.get("prompt_tokens")
            completion_tokens = usage.get("completion_tokens")
            total_tokens = usage.get("total_tokens")
            
        except requests.exceptions.HTTPError as exc:
            error_detail = ""
            try:
                error_detail = exc.response.json().get("message", str(exc))
            except Exception:
                error_detail = str(exc)
            answer = f"[Mistral API Hatası] {error_detail}"
            prompt_tokens = None
            completion_tokens = None
            total_tokens = None
            
        except Exception as exc:
            answer = f"[Mistral Hatası] {exc}"
            prompt_tokens = None
            completion_tokens = None
            total_tokens = None
        
        latency = time.time() - t0
        
        return LLMAnalysis(
            provider=self.provider_id,
            model=model,
            answer=answer,
            latency_sec=latency,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
        )
    
    def health_check(self) -> bool:
        if not MISTRAL_API_KEY:
            return False
        try:
            response = requests.get(
                f"{MISTRAL_API_BASE}/models",
                headers={"Authorization": f"Bearer {MISTRAL_API_KEY}"},
                timeout=10,
            )
            return response.status_code == 200
        except Exception:
            return False


# ============================================================================
# PROVIDER FACTORY
# ============================================================================


class LLMProviderFactory:
    """
    LLM Provider Factory.
    
    Kullanım:
        # Belirli provider al
        provider = LLMProviderFactory.get_provider("groq")
        result = provider.generate(prompt="...", model="llama-3.3-70b-versatile")
        
        # Tüm provider'ları listele
        providers = LLMProviderFactory.list_providers()
        
        # Sağlık kontrolü
        health = LLMProviderFactory.health_check_all()
    """
    
    _providers: Dict[str, Type[BaseLLMProvider]] = {
        "local": OllamaProvider,
        "groq": GroqProvider,
        "openrouter": OpenRouterProvider,
        "google": GoogleProvider,
        "cerebras": CerebrasProvider,
        "mistral": MistralProvider,
    }
    
    _instances: Dict[str, BaseLLMProvider] = {}
    
    @classmethod
    def get_provider(cls, provider_id: str) -> BaseLLMProvider:
        """
        Belirtilen provider'ın singleton instance'ını döndür.
        
        Args:
            provider_id: Provider ID (local, groq, openrouter, google, cerebras)
            
        Returns:
            BaseLLMProvider: Provider instance
            
        Raises:
            ValueError: Geçersiz provider ID
        """
        if provider_id not in cls._providers:
            valid = list(cls._providers.keys())
            raise ValueError(f"Geçersiz provider: {provider_id}. Geçerli değerler: {valid}")
        
        if provider_id not in cls._instances:
            cls._instances[provider_id] = cls._providers[provider_id]()
        
        return cls._instances[provider_id]
    
    @classmethod
    def list_providers(cls) -> List[ProviderInfo]:
        """
        Tüm provider'ların bilgilerini döndür.
        
        Returns:
            List[ProviderInfo]: Provider listesi
        """
        providers = []
        for provider_id in cls._providers.keys():
            provider = cls.get_provider(provider_id)
            providers.append(provider.get_info())
        return providers
    
    @classmethod
    def get_provider_models(cls, provider_id: str) -> List[ProviderModelInfo]:
        """
        Belirtilen provider'ın model listesini döndür.
        
        Args:
            provider_id: Provider ID
            
        Returns:
            List[ProviderModelInfo]: Model listesi
        """
        provider = cls.get_provider(provider_id)
        return provider.get_models()
    
    @classmethod
    def health_check_all(cls) -> Dict[str, bool]:
        """
        Tüm provider'ların sağlık durumunu kontrol et.
        
        Returns:
            Dict[str, bool]: Provider ID -> sağlık durumu
        """
        results = {}
        for provider_id in cls._providers.keys():
            try:
                provider = cls.get_provider(provider_id)
                results[provider_id] = provider.health_check()
            except Exception:
                results[provider_id] = False
        return results
    
    @classmethod
    def get_available_providers(cls) -> List[str]:
        """
        Kullanılabilir (sağlıklı) provider ID'lerini döndür.
        
        Returns:
            List[str]: Sağlıklı provider ID'leri
        """
        health = cls.health_check_all()
        return [pid for pid, healthy in health.items() if healthy]


# ============================================================================
# __all__
# ============================================================================

__all__ = [
    "BaseLLMProvider",
    "OllamaProvider",
    "GroqProvider",
    "OpenRouterProvider",
    "GoogleProvider",
    "CerebrasProvider",
    "MistralProvider",
    "LLMProviderFactory",
]
