"""
routes_search.py
================

Qdrant üzerinde vektör benzerlik araması yapan /search endpoint'ini tanımlar.

Bu endpoint şu akışı takip eder:
- Kullanıcının metin sorgusu embedding_model ile vektöre çevrilir.
- Qdrant'ta ilgili koleksiyonda vektör benzerlik araması yapılır.
- Her sonuç için skor ve payload döndürülür.

MVP'de RAG'dan cevap üretmiyoruz ama bu endpoint,
koleksiyonları test etmek veya ilerideki RAG senaryoları için hazır duruyor.
"""

from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException

from config import qdrant_client, embedding_model
from models import SearchRequest

router = APIRouter(
    prefix="",
    tags=["search"],
)


def _encode_text(text: str) -> List[float]:
    """
    Metni sentence-transformers embedding model ile vektöre çevirir.
    """
    # embedding_model, config.py içinde global olarak yüklenmiş durumda.
    return embedding_model.encode(text).tolist()


@router.post("/search")
async def vector_search(request: SearchRequest) -> Dict[str, Any]:
    """
    Qdrant üzerinde vektör benzerlik araması.

    Beklenen gövde (örnek):

    {
      "query": "şanzıman ile ilgili onarım kayıtları",
      "collection": "man_local_service_maintenance",
      "limit": 5
    }

    Dönen cevap:

    {
      "query": "...",
      "collection": "...",
      "results": [
        {
          "score": 0.87,
          "payload": { ... }   # Qdrant'a indexlediğin metadata
        },
        ...
      ]
    }
    """
    if qdrant_client is None or embedding_model is None:
        raise HTTPException(
            status_code=503,
            detail="Service not ready (Qdrant or embedding model missing)",
        )

    try:
        query_vector = _encode_text(request.query)

        results = qdrant_client.search(
            collection_name=request.collection,
            query_vector=query_vector,
            limit=request.limit,
        )

        return {
            "query": request.query,
            "collection": request.collection,
            "results": [
                {
                    "score": hit.score,
                    "payload": hit.payload,
                }
                for hit in results
            ],
        }
    except Exception as e:
        # Herhangi bir hata durumunda 500 döndür ve detay mesajını ilet
        raise HTTPException(
            status_code=500,
            detail=f"Vector search failed: {repr(e)}",
        )
