"""
routes_ingest.py
================

LRS'ten xAPI statement'ları çekip:
- JSON-LD'ye çeviren,
- embed eden,
- Qdrant koleksiyonuna yazan

/xapi/ingest endpoint'ini tanımlar.

MVP'de RAG'tan cevap üretilmiyor ama bu endpoint ile
koleksiyonlar hazır bir şekilde doldurulmaya devam edebilir.
"""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from config import qdrant_client, embedding_model
from models import XAPIIngestRequest

router = APIRouter(
    prefix="",
    tags=["xapi-ingest"],
)


@router.post("/xapi/ingest")
async def ingest_xapi(request: XAPIIngestRequest) -> Dict[str, Any]:
    """
    LRS'ten xAPI statement'ları çek, JSON-LD'ye çevir, embed et,
    Qdrant koleksiyonuna yaz.

    Gövde örneği (n8n'den):

    {
      "lrs_endpoint": "http://lrs-app:3000",
      "username": "lrs_admin",
      "password": "ChangeThisPassword123!",
      "collection": "man_local_service_maintenance",
      "limit": 100,
      "max_pages": 10,
      "page_delay_ms": 300
    }
    """
    if not qdrant_client or not embedding_model:
        raise HTTPException(
            status_code=503,
            detail="Service not ready (Qdrant or embedding model missing)",
        )

    try:
        import httpx
        import asyncio
        from urllib.parse import urljoin
        from processors.jsonld import process_xapi_statements

        # ------------------------------------------------------------------ #
        # LRS Auth & URL Hazırlığı
        # ------------------------------------------------------------------ #
        auth = None
        if request.username and request.password:
            auth = (request.username, request.password)

        base_url = f"{request.lrs_endpoint}/xapi/statements"
        next_url = base_url
        params: Dict[str, Any] = {"limit": request.limit or 100}

        total_indexed = 0
        pages = 0
        delay = (request.page_delay_ms or 0) / 1000.0

        # ------------------------------------------------------------------ #
        # Sayfa sayfa LRS'ten statement çekme
        # ------------------------------------------------------------------ #
        async with httpx.AsyncClient(timeout=30.0, verify=False) as client:
            while next_url:
                resp = await client.get(
                    next_url,
                    params=params,
                    auth=auth,
                    headers={
                        "X-Experience-API-Version": "1.0.3",
                    },
                )

                # Rate limit → bekle & tekrar dene
                if resp.status_code == 429:
                    retry_after = resp.headers.get("Retry-After")
                    wait_sec = float(retry_after) if retry_after else 2.0
                    await asyncio.sleep(wait_sec)
                    continue

                # Diğer hatalar → 502
                if resp.status_code != 200:
                    raise HTTPException(
                        status_code=502,
                        detail=(
                            f"LRS returned status "
                            f"{resp.status_code}"
                        ),
                    )

                data = resp.json()

                # ------------------------------------------------------------------ #
                # JSON-LD + Embedding + Qdrant (process_xapi_statements)
                # ------------------------------------------------------------------ #
                # DİKKAT: process_xapi_statements senkron bir fonksiyon, await YOK.
                indexed = await process_xapi_statements(
                    data,
                    request.collection,
                    qdrant_client,
                    embedding_model,
                )
                total_indexed += indexed  # Artık int + int ✅
                pages += 1

                # Sayfalar arasında gecikme
                if delay > 0:
                    await asyncio.sleep(delay)

                # max_pages sınırı
                if request.max_pages and pages >= request.max_pages:
                    break

                # xAPI "more" mekanizması
                more = data.get("more")
                if more:
                    next_url = (
                        more
                        if isinstance(more, str) and more.startswith("http")
                        else urljoin(base_url, more)
                    )
                    # LRS next URL'i zaten limit içeriyorsa tekrar params göndermeyiz
                    params = None
                else:
                    next_url = None

        return {
            "status": "success",
            "message": "xAPI ingest completed",
            "total_indexed": total_indexed,
            "collection": request.collection,
            "lrs_endpoint": request.lrs_endpoint,
            "pages": pages,
        }

    except Exception:
        import traceback

        error_detail = traceback.format_exc()
        raise HTTPException(
            status_code=500,
            detail=f"xAPI ingest failed: {error_detail}",
        )
