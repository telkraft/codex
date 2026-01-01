# quick_queries_api.py
"""
Hızlı Sorgu Yönetimi API
========================

Bu modül, UI tarafından kullanılan hızlı sorguların CRUD işlemlerini yönetir.
Veriler quick_queries.json dosyasında saklanır.

Endpoints:
- GET /api/quick-queries - Tüm sorguları listele
- GET /api/quick-queries/categories - Kategorileri listele
- GET /api/quick-queries/{query_id} - Tek sorgu getir
- POST /api/quick-queries - Yeni sorgu ekle
- PUT /api/quick-queries/{query_id} - Sorgu güncelle
- DELETE /api/quick-queries/{query_id} - Sorgu sil
- PUT /api/quick-queries/{query_id}/toggle - Aktif/Pasif değiştir
- PUT /api/quick-queries/reorder - Sıralama güncelle
"""

import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

# ============================================================================
# CONFIG
# ============================================================================

# JSON dosyasının konumu - promptever-app klasörü içinde
QUICK_QUERIES_FILE = Path(__file__).parent / "data" / "quick_queries.json"

# Fallback: Eğer data klasörü yoksa ana dizinde ara
if not QUICK_QUERIES_FILE.parent.exists():
    QUICK_QUERIES_FILE = Path(__file__).parent / "quick_queries.json"


# ============================================================================
# PYDANTIC MODELS
# ============================================================================

class CategoryBase(BaseModel):
    """Kategori temel modeli"""
    name: str = Field(..., min_length=1, max_length=100)
    icon: str = Field(default="📁", max_length=10)
    order: int = Field(default=0, ge=0)


class CategoryCreate(CategoryBase):
    """Yeni kategori oluşturma"""
    id: Optional[str] = None


class Category(CategoryBase):
    """Kategori tam modeli"""
    id: str


class QueryBase(BaseModel):
    """Sorgu temel modeli"""
    text: str = Field(..., min_length=5, max_length=500)
    description: Optional[str] = Field(default="", max_length=500)
    tags: List[str] = Field(default_factory=list)
    is_active: bool = Field(default=True)
    order: int = Field(default=0, ge=0)


class QueryCreate(QueryBase):
    """Yeni sorgu oluşturma"""
    category_id: str


class QueryUpdate(BaseModel):
    """Sorgu güncelleme (partial)"""
    text: Optional[str] = Field(None, min_length=5, max_length=500)
    description: Optional[str] = Field(None, max_length=500)
    category_id: Optional[str] = None
    tags: Optional[List[str]] = None
    is_active: Optional[bool] = None
    order: Optional[int] = Field(None, ge=0)


class Query(QueryBase):
    """Sorgu tam modeli"""
    id: str
    category_id: str


class ReorderRequest(BaseModel):
    """Sıralama güncelleme isteği"""
    items: List[dict]  # [{"id": "q001", "order": 1}, ...]


class QuickQueriesData(BaseModel):
    """Tüm veri modeli"""
    version: str = "1.0"
    last_updated: str
    categories: List[Category]
    queries: List[Query]


# ============================================================================
# DATA ACCESS LAYER
# ============================================================================

def _ensure_file_exists():
    """JSON dosyasının varlığını kontrol et, yoksa varsayılan oluştur"""
    if not QUICK_QUERIES_FILE.exists():
        # Klasör yoksa oluştur
        QUICK_QUERIES_FILE.parent.mkdir(parents=True, exist_ok=True)
        
        # Varsayılan veri
        default_data = {
            "version": "1.0",
            "last_updated": datetime.utcnow().isoformat() + "Z",
            "categories": [
                {"id": "general", "name": "Genel", "icon": "📊", "order": 1}
            ],
            "queries": []
        }
        
        with open(QUICK_QUERIES_FILE, 'w', encoding='utf-8') as f:
            json.dump(default_data, f, ensure_ascii=False, indent=2)


def _load_data() -> dict:
    """JSON dosyasından veri yükle"""
    _ensure_file_exists()
    
    try:
        with open(QUICK_QUERIES_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"JSON parse hatası: {str(e)}"
        )


def _save_data(data: dict):
    """Veriyi JSON dosyasına kaydet"""
    data["last_updated"] = datetime.utcnow().isoformat() + "Z"
    
    try:
        # Atomic write - önce temp dosyaya yaz, sonra rename
        temp_file = QUICK_QUERIES_FILE.with_suffix('.tmp')
        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        # Rename (atomic on most filesystems)
        temp_file.replace(QUICK_QUERIES_FILE)
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Kaydetme hatası: {str(e)}"
        )


def _generate_id(prefix: str = "q") -> str:
    """Unique ID oluştur"""
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


# ============================================================================
# ROUTER
# ============================================================================

router = APIRouter(prefix="/api/quick-queries", tags=["Quick Queries"])


# ─────────────────────────────────────────────────────────────
# GET ENDPOINTS
# ─────────────────────────────────────────────────────────────

@router.get("", response_model=QuickQueriesData)
async def get_all_queries():
    """
    Tüm sorguları ve kategorileri getir.
    
    Returns:
        QuickQueriesData: Kategoriler ve sorgular
    """
    data = _load_data()
    return data


@router.get("/categories", response_model=List[Category])
async def get_categories():
    """
    Sadece kategorileri getir.
    
    Returns:
        List[Category]: Kategori listesi
    """
    data = _load_data()
    categories = sorted(data.get("categories", []), key=lambda x: x.get("order", 0))
    return categories


@router.get("/active", response_model=List[Query])
async def get_active_queries():
    """
    Sadece aktif sorguları getir (chat sidebar için).
    
    Returns:
        List[Query]: Aktif sorgu listesi
    """
    data = _load_data()
    queries = [q for q in data.get("queries", []) if q.get("is_active", True)]
    queries = sorted(queries, key=lambda x: (x.get("category_id", ""), x.get("order", 0)))
    return queries


@router.get("/{query_id}", response_model=Query)
async def get_query(query_id: str):
    """
    Belirli bir sorguyu getir.
    
    Args:
        query_id: Sorgu ID
        
    Returns:
        Query: Sorgu detayları
    """
    data = _load_data()
    
    for query in data.get("queries", []):
        if query.get("id") == query_id:
            return query
    
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Sorgu bulunamadı: {query_id}"
    )


# ─────────────────────────────────────────────────────────────
# CREATE ENDPOINTS
# ─────────────────────────────────────────────────────────────

@router.post("", response_model=Query, status_code=status.HTTP_201_CREATED)
async def create_query(query: QueryCreate):
    """
    Yeni sorgu oluştur.
    
    Args:
        query: Sorgu bilgileri
        
    Returns:
        Query: Oluşturulan sorgu
    """
    data = _load_data()
    
    # Kategori kontrolü
    category_ids = [c.get("id") for c in data.get("categories", [])]
    if query.category_id not in category_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Geçersiz kategori: {query.category_id}"
        )
    
    # Yeni sorgu oluştur
    new_query = {
        "id": _generate_id("q"),
        "category_id": query.category_id,
        "text": query.text,
        "description": query.description or "",
        "tags": query.tags,
        "is_active": query.is_active,
        "order": query.order
    }
    
    data["queries"].append(new_query)
    _save_data(data)
    
    return new_query


@router.post("/categories", response_model=Category, status_code=status.HTTP_201_CREATED)
async def create_category(category: CategoryCreate):
    """
    Yeni kategori oluştur.
    
    Args:
        category: Kategori bilgileri
        
    Returns:
        Category: Oluşturulan kategori
    """
    data = _load_data()
    
    # ID kontrolü
    category_id = category.id or _generate_id("cat")
    existing_ids = [c.get("id") for c in data.get("categories", [])]
    if category_id in existing_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Kategori ID zaten var: {category_id}"
        )
    
    # Yeni kategori oluştur
    new_category = {
        "id": category_id,
        "name": category.name,
        "icon": category.icon,
        "order": category.order
    }
    
    data["categories"].append(new_category)
    _save_data(data)
    
    return new_category


# ─────────────────────────────────────────────────────────────
# UPDATE ENDPOINTS
# ─────────────────────────────────────────────────────────────

@router.put("/{query_id}", response_model=Query)
async def update_query(query_id: str, query_update: QueryUpdate):
    """
    Sorgu güncelle.
    
    Args:
        query_id: Sorgu ID
        query_update: Güncellenecek alanlar
        
    Returns:
        Query: Güncellenmiş sorgu
    """
    data = _load_data()
    
    for i, query in enumerate(data.get("queries", [])):
        if query.get("id") == query_id:
            # Kategori kontrolü
            if query_update.category_id:
                category_ids = [c.get("id") for c in data.get("categories", [])]
                if query_update.category_id not in category_ids:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Geçersiz kategori: {query_update.category_id}"
                    )
            
            # Güncelleme
            update_data = query_update.model_dump(exclude_unset=True)
            data["queries"][i].update(update_data)
            _save_data(data)
            
            return data["queries"][i]
    
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Sorgu bulunamadı: {query_id}"
    )


@router.put("/{query_id}/toggle", response_model=Query)
async def toggle_query(query_id: str):
    """
    Sorgunun aktif/pasif durumunu değiştir.
    
    Args:
        query_id: Sorgu ID
        
    Returns:
        Query: Güncellenmiş sorgu
    """
    data = _load_data()
    
    for i, query in enumerate(data.get("queries", [])):
        if query.get("id") == query_id:
            data["queries"][i]["is_active"] = not query.get("is_active", True)
            _save_data(data)
            return data["queries"][i]
    
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Sorgu bulunamadı: {query_id}"
    )


@router.put("/reorder", response_model=dict)
async def reorder_queries(request: ReorderRequest):
    """
    Sorguların sıralamasını güncelle.
    
    Args:
        request: Sıralama bilgileri
        
    Returns:
        dict: Başarı mesajı
    """
    data = _load_data()
    
    # ID -> order mapping oluştur
    order_map = {item["id"]: item["order"] for item in request.items}
    
    # Sorguları güncelle
    for query in data.get("queries", []):
        if query.get("id") in order_map:
            query["order"] = order_map[query["id"]]
    
    _save_data(data)
    
    return {"message": f"{len(order_map)} sorgu sıralandı"}


# ─────────────────────────────────────────────────────────────
# DELETE ENDPOINTS
# ─────────────────────────────────────────────────────────────

@router.delete("/{query_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_query(query_id: str):
    """
    Sorgu sil.
    
    Args:
        query_id: Sorgu ID
    """
    data = _load_data()
    
    initial_count = len(data.get("queries", []))
    data["queries"] = [q for q in data.get("queries", []) if q.get("id") != query_id]
    
    if len(data["queries"]) == initial_count:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sorgu bulunamadı: {query_id}"
        )
    
    _save_data(data)


@router.delete("/categories/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category(category_id: str, force: bool = False):
    """
    Kategori sil.
    
    Args:
        category_id: Kategori ID
        force: True ise kategorideki sorgular da silinir
    """
    data = _load_data()
    
    # Kategori var mı kontrol et
    category_exists = any(c.get("id") == category_id for c in data.get("categories", []))
    if not category_exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Kategori bulunamadı: {category_id}"
        )
    
    # Bu kategorideki sorguları kontrol et
    queries_in_category = [q for q in data.get("queries", []) if q.get("category_id") == category_id]
    
    if queries_in_category and not force:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Kategoride {len(queries_in_category)} sorgu var. Silmek için force=true kullanın."
        )
    
    # Kategori ve sorgularını sil
    data["categories"] = [c for c in data.get("categories", []) if c.get("id") != category_id]
    if force:
        data["queries"] = [q for q in data.get("queries", []) if q.get("category_id") != category_id]
    
    _save_data(data)


# ============================================================================
# MAIN ROUTER REGISTRATION (main.py'ye eklenecek)
# ============================================================================

"""
# main.py'ye ekle:

from quick_queries_api import router as quick_queries_router

app.include_router(quick_queries_router)
"""
