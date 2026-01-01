"""
api/routes_email.py
===================

Basitleştirilmiş Email API - Mevcut n8n workflow'unu kullanır.

İlk etap: Sadece anlık email gönderimi
Sonraki etaplar: Schedule ve Alert eklenecek
"""

from __future__ import annotations
from typing import Optional, List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr

router = APIRouter(prefix="/email", tags=["email"])


# ============================================================================
# MODELS
# ============================================================================

class InstantEmailRequest(BaseModel):
    """Anlık email gönderimi için request"""
    recipients: List[EmailStr]
    subject: Optional[str] = None
    chat_response: dict  # ChatResponse objesi
    query_text: str
    include_tables: bool = True
    include_llm_answer: bool = True
    include_statistics: bool = True


class InstantEmailResponse(BaseModel):
    """Email gönderim yanıtı"""
    success: bool
    message: str
    sent_to: List[str] = []
    errors: List[str] = []


class PreviewRequest(BaseModel):
    """Email önizleme için request"""
    chat_response: dict
    query_text: str
    include_tables: bool = True
    include_llm_answer: bool = True
    include_statistics: bool = True


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.post("/send", response_model=InstantEmailResponse)
async def send_instant_email(request: InstantEmailRequest):
    """
    Chat sonucunu anlık olarak email gönder.
    
    Mevcut n8n workflow'unu (telkraft-contact benzeri) kullanır.
    
    Request body:
    ```json
    {
        "recipients": ["user@example.com"],
        "subject": "Opsiyonel konu",
        "query_text": "Orijinal sorgu metni",
        "chat_response": { ... },
        "include_tables": true,
        "include_llm_answer": true,
        "include_statistics": true
    }
    ```
    """
    from services.email_service import email_service
    
    result = await email_service.send_instant_email(
        recipients=[str(r) for r in request.recipients],
        query_text=request.query_text,
        chat_response=request.chat_response,
        subject=request.subject,
        include_tables=request.include_tables,
        include_llm_answer=request.include_llm_answer,
        include_statistics=request.include_statistics,
    )
    
    return InstantEmailResponse(**result)


@router.post("/preview")
async def preview_email(request: PreviewRequest):
    """
    Email içeriğini önizle (göndermeden).
    
    HTML içeriğini döndürür - tarayıcıda veya modal'da gösterilebilir.
    """
    from services.email_service import email_service
    
    html_content = email_service.preview_email_html(
        query_text=request.query_text,
        chat_response=request.chat_response,
        include_tables=request.include_tables,
        include_llm_answer=request.include_llm_answer,
        include_statistics=request.include_statistics,
    )
    
    return {
        "html": html_content,
        "query_text": request.query_text,
    }


@router.get("/health")
async def email_health():
    """Email service sağlık kontrolü"""
    import os
    
    webhook_url = os.getenv("N8N_EMAIL_WEBHOOK", "http://localhost:5678/webhook/promptever-email")
    
    return {
        "status": "ok",
        "webhook_configured": bool(webhook_url),
        "webhook_url": webhook_url.split("/webhook/")[0] + "/webhook/***" if "/webhook/" in webhook_url else "not set",
    }
