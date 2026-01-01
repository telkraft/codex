# api/routes_lrs_stats.py

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter
from services.lrs_service import LRSQueryService

router = APIRouter(
    prefix="/lrs",
    tags=["lrs-stats"],
)


@router.get("/stats/general")
async def get_lrs_general_stats() -> Dict[str, Any]:
    """
    LRS için genel istatistik endpoint'i.

    LRSQueryService.get_general_statistics ile Mongo'dan gerçek
    değerleri okur ve Streamlit arayüzünün beklediği formatta döner.
    """
    service = LRSQueryService()
    stats = service.get_general_statistics()

    return {
        "status": "ok",
        "data": stats,
    }

@router.get("/statements")
async def get_lrs_statements(
    limit: int = 20,
    skip: int = 0
) -> Dict[str, Any]:
    """
    LRS'ten statement'ları pagination ile döndürür.
    """
    from config import lrs_statements
    
    try:
        total = lrs_statements.count_documents({})
        
        cursor = lrs_statements.find({}).sort("stored", -1).skip(skip).limit(limit)
        
        statements = []
        for doc in cursor:
            # MongoDB _id'yi string'e çevir
            doc['id'] = str(doc.get('_id', ''))
            if '_id' in doc:
                del doc['_id']
            statements.append(doc)
        
        return {
            "status": "ok",
            "statements": statements,
            "total": total,
            "limit": limit,
            "skip": skip,
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "statements": [],
            "total": 0,
        }
