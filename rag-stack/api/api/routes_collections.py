# api/routes_collections.py

from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter
from config import qdrant_client

router = APIRouter(
    prefix="",
    tags=["collections"],
)


@router.get("/collections")
async def list_collections() -> Dict[str, Any]:
    """
    Qdrant'taki koleksiyonları listeleyen basit endpoint.

    Streamlit arayüzü, buradan dönen "collections" alanını kullanıyor.
    Eğer Qdrant erişilemezse, MAN MVP için varsayılan bir liste döner.
    """
    # UI'de fallback ile uyumlu bir başlangıç listesi
    collections: List[str] = [
        "man_local_service_maintenance",
        "default",
    ]

    qdrant_collections: List[str] = []

    if qdrant_client is not None:
        try:
            resp = qdrant_client.get_collections()
            qdrant_collections = [c.name for c in resp.collections]

            # Eğer Qdrant'tan en az bir koleksiyon geldiyse, onu esas al
            if qdrant_collections:
                collections = qdrant_collections
        except Exception:
            # Qdrant'ta bir hata olursa, sadece varsayılan listeyi döneriz
            pass

    return {
        "collections": collections,
        "qdrant_collections": qdrant_collections,
    }
