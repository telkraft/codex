"""
routes_chat.py
==============

/chat endpoint'ini tanımlar.

Bu endpoint, gelen sohbet/analiz isteğini doğrudan
MVP orkestratörüne (answer_with_lrs_and_llm) iletir.

Akış:
/chat → answer_with_lrs_and_llm(ChatRequest)
      → IntentRouter
      → LRSQueryService (istatistik + örnek deneyimler)
      → LLMService (UI'den gelen modele göre yorum/öngörü)
"""

from fastapi import APIRouter

from models import ChatRequest, ChatResponse
# ESKİ:
# from services.mvp_orchestrator import answer_with_lrs_and_llm
# YENİ:
from services.orchestrator import answer_with_lrs_and_llm

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    """
    MAN servis verisi için ana sohbet/analiz endpoint'i.

    Yeni akış:
    /chat → orchestrator.answer_with_lrs_and_llm(ChatRequest)
          → AdvancedIntentRouter
          → LRSQueryService (istatistik + örnek deneyimler)
          → (opsiyonel) LLM yorum / öngörü
    """
    return answer_with_lrs_and_llm(request)
