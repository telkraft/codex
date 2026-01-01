import time
import requests
from typing import Optional
from models import LLMAnalysis
from config import OLLAMA_HOST, LLM_MODEL_NAME


class LLMService:
    """
    Promptever LLM Servisi (Ollama tabanlı)
    - UI üzerinden model seçimini destekler.
    - LLM_MODEL_NAME sadece 'default model' olarak kullanılır.
    """

    def __init__(self, base_url: str = OLLAMA_HOST, default_model: str = LLM_MODEL_NAME):
        self.base_url = base_url.rstrip("/")
        self.default_model = default_model

    def generate(self, prompt: str, model: Optional[str] = None) -> LLMAnalysis:
        """
        Ollama ile metin üretimi:
        - model: UI'den gelen model
        - model None ise default_model (config'ten)
        """
        selected_model = model or self.default_model

        url = f"{self.base_url}/api/generate"

        try:
            t0 = time.time()

            response = requests.post(
                url,
                json={
                    "model": selected_model,
                    "prompt": prompt,
                    "stream": False,
                },
                timeout=(10, 300),  # connect, read
            )

            latency = time.time() - t0

            response.raise_for_status()
            data = response.json()

            answer_text = data.get("response", "")

            return LLMAnalysis(
                model=selected_model,
                answer=answer_text,
                latency_sec=latency,
            )

        except Exception as e:
            # LLM hatasını zarifçe dönelim, zincir bozulmasın
            return LLMAnalysis(
                model=selected_model,
                answer=f"LLM bağlantı hatası: {str(e)}",
                latency_sec=0.0,
            )


# Global servis
llm_service = LLMService()
