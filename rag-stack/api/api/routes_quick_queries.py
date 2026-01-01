"""
routes_quick_queries.py
=======================

Hızlı sorgu yönetimi için API endpoint'leri.

Endpoint'ler:
- GET  /quick-queries              → Tüm sorguları getir
- GET  /quick-queries/active       → Aktif sorguları getir (chat için)
- GET  /quick-queries/categories   → Kategorileri getir
- GET  /quick-queries/stats        → İstatistikleri getir
- GET  /quick-queries/{id}         → Tek sorgu getir
- POST /quick-queries              → Custom sorgu ekle
- POST /quick-queries/categories   → Custom kategori ekle
- PUT  /quick-queries/{id}         → Custom sorgu güncelle
- PUT  /quick-queries/{id}/toggle  → Aktif/pasif değiştir
- DELETE /quick-queries/{id}       → Custom sorgu sil
- DELETE /quick-queries/categories/{id} → Custom kategori sil
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import BaseModel, Field

from services.quick_queries_service import (
    get_all_queries,
    get_active_queries,
    get_categories,
    get_query_by_id,
    create_custom_query,
    update_custom_query,
    toggle_custom_query,
    delete_custom_query,
    create_custom_category,
    delete_custom_category,
    get_stats,
)


router = APIRouter(prefix="/quick-queries", tags=["quick-queries"])


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class CreateQueryRequest(BaseModel):
    """Sorgu oluşturma isteği"""
    text: str = Field(..., min_length=5, max_length=500, description="Sorgu metni")
    category_id: str = Field(..., description="Kategori ID")
    description: str = Field("", max_length=200, description="Açıklama")
    tags: List[str] = Field(default_factory=list, description="Etiketler")
    is_active: bool = Field(True, description="Aktif mi")
    order: int = Field(0, ge=0, description="Sıralama")


class UpdateQueryRequest(BaseModel):
    """Sorgu güncelleme isteği"""
    text: Optional[str] = Field(None, min_length=5, max_length=500)
    category_id: Optional[str] = None
    description: Optional[str] = Field(None, max_length=200)
    tags: Optional[List[str]] = None
    is_active: Optional[bool] = None
    order: Optional[int] = Field(None, ge=0)


class CreateCategoryRequest(BaseModel):
    """Kategori oluşturma isteği"""
    id: Optional[str] = Field(None, min_length=2, max_length=50, description="Kategori ID (opsiyonel)")
    name: str = Field(..., min_length=2, max_length=50, description="Kategori adı")
    icon: str = Field("📁", max_length=10, description="Emoji ikon")
    order: int = Field(0, ge=0, description="Sıralama")


class QueryResponse(BaseModel):
    """Sorgu yanıtı"""
    id: str
    category_id: str
    text: str
    description: str
    tags: List[str]
    is_active: bool
    order: int
    source: str
    canonical_ref: Optional[str] = None


class CategoryResponse(BaseModel):
    """Kategori yanıtı"""
    id: str
    name: str
    icon: str
    order: int
    is_default: bool


class StatsResponse(BaseModel):
    """İstatistik yanıtı"""
    canonical_count: int
    custom_count: int
    custom_categories_count: int
    default_categories_count: int
    last_updated: Optional[str]


# ============================================================================
# GET ENDPOINTS
# ============================================================================

@router.get("")
def list_queries(
    active_only: bool = Query(False, description="Sadece aktif sorguları getir"),
    category_id: Optional[str] = Query(None, description="Kategoriye filtrele"),
    include_canonical: bool = Query(True, description="Referans sorguları dahil et"),
    include_custom: bool = Query(True, description="Özel sorguları dahil et"),
) -> Dict[str, Any]:
    """
    Tüm sorguları getir.
    
    Referans sorguları ve özel eklenen tüm sorgular döner.
    """
    data = get_all_queries(
        include_canonical=include_canonical,
        include_custom=include_custom,
        active_only=active_only,
        category_id=category_id,
    )
    return data.to_dict()


@router.get("/active")
def list_active_queries() -> List[Dict[str, Any]]:
    """
    Aktif sorguları getir (chat dropdown için).
    
    Sadece is_active=True olan sorgular döner.
    """
    return get_active_queries()


@router.get("/categories")
def list_categories() -> List[CategoryResponse]:
    """
    Kategorileri getir.
    
    Varsayılan ve custom kategoriler döner.
    """
    categories = get_categories()
    return [
        CategoryResponse(
            id=c.id,
            name=c.name,
            icon=c.icon,
            order=c.order,
            is_default=c.is_default,
        )
        for c in categories
    ]


@router.get("/stats")
def get_query_stats() -> StatsResponse:
    """
    İstatistikleri getir.
    
    Referans ve özel sorgu sayıları döner.
    """
    stats = get_stats()
    return StatsResponse(**stats)


@router.get("/{query_id}")
def get_query(query_id: str) -> QueryResponse:
    """
    Tek sorgu getir.
    """
    query = get_query_by_id(query_id)
    
    if not query:
        raise HTTPException(status_code=404, detail=f"Sorgu bulunamadı: {query_id}")
    
    return QueryResponse(
        id=query.id,
        category_id=query.category_id,
        text=query.text,
        description=query.description,
        tags=query.tags,
        is_active=query.is_active,
        order=query.order,
        source=query.source.value,
        canonical_ref=query.canonical_ref,
    )


# ============================================================================
# CREATE ENDPOINTS
# ============================================================================

@router.post("", status_code=201)
def create_query(request: CreateQueryRequest) -> QueryResponse:
    """
    Yeni custom sorgu oluştur.
    
    NOT: Referans sorgular bu endpoint ile oluşturulamaz.
    """
    try:
        query = create_custom_query(
            text=request.text,
            category_id=request.category_id,
            description=request.description,
            tags=request.tags,
            is_active=request.is_active,
            order=request.order,
        )
        
        return QueryResponse(
            id=query.id,
            category_id=query.category_id,
            text=query.text,
            description=query.description,
            tags=query.tags,
            is_active=query.is_active,
            order=query.order,
            source=query.source.value,
            canonical_ref=query.canonical_ref,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/categories", status_code=201)
def create_category(request: CreateCategoryRequest) -> CategoryResponse:
    """
    Yeni custom kategori oluştur.
    
    NOT: Varsayılan kategori ID'leri kullanılamaz.
    """
    try:
        category = create_custom_category(
            name=request.name,
            icon=request.icon,
            category_id=request.id,
            order=request.order,
        )
        
        return CategoryResponse(
            id=category.id,
            name=category.name,
            icon=category.icon,
            order=category.order,
            is_default=category.is_default,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ============================================================================
# UPDATE ENDPOINTS
# ============================================================================

@router.put("/{query_id}")
def update_query(query_id: str, request: UpdateQueryRequest) -> QueryResponse:
    """
    Custom sorgu güncelle.
    
    NOT: Referans sorgular (cq_ prefix) güncellenemez.
    """
    try:
        query = update_custom_query(
            query_id=query_id,
            text=request.text,
            category_id=request.category_id,
            description=request.description,
            tags=request.tags,
            is_active=request.is_active,
            order=request.order,
        )
        
        if not query:
            raise HTTPException(status_code=404, detail=f"Sorgu bulunamadı: {query_id}")
        
        return QueryResponse(
            id=query.id,
            category_id=query.category_id,
            text=query.text,
            description=query.description,
            tags=query.tags,
            is_active=query.is_active,
            order=query.order,
            source=query.source.value,
            canonical_ref=query.canonical_ref,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{query_id}/toggle")
def toggle_query(query_id: str) -> QueryResponse:
    """
    Sorgunun aktif/pasif durumunu değiştir.
    
    NOT: Referans sorgular değiştirilemez.
    """
    try:
        query = toggle_custom_query(query_id)
        
        if not query:
            raise HTTPException(status_code=404, detail=f"Sorgu bulunamadı: {query_id}")
        
        return QueryResponse(
            id=query.id,
            category_id=query.category_id,
            text=query.text,
            description=query.description,
            tags=query.tags,
            is_active=query.is_active,
            order=query.order,
            source=query.source.value,
            canonical_ref=query.canonical_ref,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ============================================================================
# DELETE ENDPOINTS
# ============================================================================

@router.delete("/{query_id}")
def delete_query(query_id: str) -> Response:
    """
    Custom sorgu sil.
    
    NOT: Referans sorgular (cq_ prefix) silinemez.
    """
    try:
        deleted = delete_custom_query(query_id)
        
        if not deleted:
            raise HTTPException(status_code=404, detail=f"Sorgu bulunamadı: {query_id}")
        
        return Response(status_code=204)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/categories/{category_id}")
def delete_category(
    category_id: str,
    force: bool = Query(False, description="Kategorideki sorguları da sil"),
) -> Response:
    """
    Custom kategori sil.
    
    NOT: Varsayılan kategoriler silinemez.
    """
    try:
        deleted = delete_custom_category(category_id, force=force)
        
        if not deleted:
            raise HTTPException(status_code=404, detail=f"Kategori bulunamadı: {category_id}")
        
        return Response(status_code=204)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))