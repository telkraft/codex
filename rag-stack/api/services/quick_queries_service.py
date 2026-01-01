"""
quick_queries_service.py
========================

Hızlı sorgu yönetimi servisi.

İki kaynak:
1. canonical_questions.py'deki CANONICAL_QUESTIONS_V2 → Otomatik türetilen sorgular
2. data/quick_queries.json (veya MongoDB) → Kullanıcı tarafından eklenen sorgular

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ÖNEMLİ: MongoDB'ye geçiş için sadece _load_custom_data() ve _save_custom_data()
        fonksiyonlarını değiştirmek yeterli. config.py'deki mongo_client kullanılır.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Literal
from enum import Enum

# Canonical questions import
from services.xapi_nlp.canonical_questions import (
    CANONICAL_QUESTIONS_V2,
    CanonicalQuestion,
    QuestionType,
    OutputShape,
)

# Config (MongoDB ileride burada kullanılacak)
# from config import mongo_client, lrs_db


# ============================================================================
# CONFIG
# ============================================================================

# Data dizini - proje kökünde
DATA_DIR = Path(__file__).parent.parent / "data"
CUSTOM_QUERIES_FILE = DATA_DIR / "quick_queries.json"

# MongoDB koleksiyonu (ileride)
# QUICK_QUERIES_COLLECTION = "quick_queries"


# ============================================================================
# MODELS
# ============================================================================

class QuerySource(str, Enum):
    """Sorgunun kaynağı"""
    CANONICAL = "canonical"  # canonical_questions.py'den türetildi
    CUSTOM = "custom"        # Kullanıcı tarafından eklendi


@dataclass
class QuickQueryCategory:
    """Kategori modeli"""
    id: str
    name: str
    icon: str = "📁"
    order: int = 0
    is_default: bool = False  # Varsayılan kategoriler silinemez
    created_at: Optional[str] = None  # Custom kategoriler için
    
    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        # None olan timestamp'ları response'dan çıkar
        if d.get("created_at") is None:
            d.pop("created_at", None)
        return d


@dataclass
class QuickQuery:
    """Hızlı sorgu modeli"""
    id: str
    category_id: str
    text: str
    description: str = ""
    tags: List[str] = field(default_factory=list)
    is_active: bool = True
    order: int = 0
    source: QuerySource = QuerySource.CUSTOM
    
    # Canonical question referansı (varsa)
    canonical_ref: Optional[str] = None  # "intent:material_usage|shape:top_list"
    
    # Timestamp alanları (custom sorgular için)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["source"] = self.source.value
        # None olan timestamp'ları response'dan çıkar
        if d.get("created_at") is None:
            d.pop("created_at", None)
        if d.get("updated_at") is None:
            d.pop("updated_at", None)
        return d


@dataclass
class QuickQueriesData:
    """Tüm veri modeli"""
    version: str = "1.0"
    last_updated: str = ""
    categories: List[QuickQueryCategory] = field(default_factory=list)
    queries: List[QuickQuery] = field(default_factory=list)
    
    # İstatistikler
    canonical_count: int = 0
    custom_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "last_updated": self.last_updated,
            "categories": [c.to_dict() for c in self.categories],
            "queries": [q.to_dict() for q in self.queries],
            "stats": {
                "canonical_count": self.canonical_count,
                "custom_count": self.custom_count,
                "total": self.canonical_count + self.custom_count,
            }
        }


# ============================================================================
# DEFAULT CATEGORIES - QuestionType'a göre (canonical_questions.py ile uyumlu)
# ============================================================================

DEFAULT_CATEGORIES: List[QuickQueryCategory] = [
    QuickQueryCategory(
        id="material_usage", 
        name="Malzeme Analizi", 
        icon="🔧", 
        order=1,
        is_default=True,
    ),
    QuickQueryCategory(
        id="cost_analysis", 
        name="Maliyet Analizi", 
        icon="💰", 
        order=2,
        is_default=True,
    ),
    QuickQueryCategory(
        id="fault_analysis", 
        name="Arıza Analizi", 
        icon="⚠️", 
        order=3,
        is_default=True,
    ),
    QuickQueryCategory(
        id="vehicle_analysis", 
        name="Araç Analizi", 
        icon="🚛", 
        order=4,
        is_default=True,
    ),
    QuickQueryCategory(
        id="customer_analysis", 
        name="Müşteri Analizi", 
        icon="👥", 
        order=5,
        is_default=True,
    ),
    QuickQueryCategory(
        id="service_analysis", 
        name="Servis Analizi", 
        icon="🏭", 
        order=6,
        is_default=True,
    ),
    QuickQueryCategory(
        id="maintenance_history", 
        name="Bakım Geçmişi", 
        icon="📋", 
        order=7,
        is_default=True,
    ),
    QuickQueryCategory(
        id="pattern_analysis", 
        name="Örüntü Analizi", 
        icon="🔍", 
        order=8,
        is_default=True,
    ),
    QuickQueryCategory(
        id="custom", 
        name="Özel Sorgular", 
        icon="⭐", 
        order=99,
        is_default=True,
    ),
]

# ID → Category lookup
DEFAULT_CATEGORY_MAP = {c.id: c for c in DEFAULT_CATEGORIES}


# ============================================================================
# CANONICAL → QUICK QUERY MAPPING
# ============================================================================

def _intent_to_category_id(intent: QuestionType) -> str:
    """Intent'i kategori ID'sine çevir"""
    mapping = {
        QuestionType.MATERIAL_USAGE: "material_usage",
        QuestionType.COST_ANALYSIS: "cost_analysis",
        QuestionType.FAULT_ANALYSIS: "fault_analysis",
        QuestionType.VEHICLE_ANALYSIS: "vehicle_analysis",
        QuestionType.CUSTOMER_ANALYSIS: "customer_analysis",
        QuestionType.SERVICE_ANALYSIS: "service_analysis",
        QuestionType.MAINTENANCE_HISTORY: "maintenance_history",
        QuestionType.PATTERN_ANALYSIS: "pattern_analysis",
        QuestionType.NEXT_MAINTENANCE: "pattern_analysis",
        QuestionType.COMPARISON_ANALYSIS: "custom",
    }
    return mapping.get(intent, "custom")


def _generate_canonical_ref(cq: CanonicalQuestion) -> str:
    """Canonical question için benzersiz referans string oluştur"""
    return f"intent:{cq.question_type.value}|shape:{cq.output_shape.value}"


def _extract_tags_from_cq(cq: CanonicalQuestion) -> List[str]:
    """Canonical question'dan etiketler çıkar"""
    tags = []
    
    # Intent ve shape (Türkçe)
    intent_names = {
        "material_usage": "malzeme",
        "cost_analysis": "maliyet",
        "fault_analysis": "arıza",
        "vehicle_analysis": "araç",
        "customer_analysis": "müşteri",
        "service_analysis": "servis",
        "maintenance_history": "bakım",
        "pattern_analysis": "örüntü",
        "next_maintenance": "sonraki bakım",
        "comparison_analysis": "karşılaştırma",
    }
    
    shape_names = {
        "top_list": "sıralama",
        "time_series": "zaman serisi",
        "seasonal": "mevsimsel",
        "distribution": "dağılım",
        "pivot": "pivot",
        "top_per_group": "grup bazlı",
        "trend": "trend",
        "comparison": "karşılaştırma",
        "summary": "özet",
    }
    
    intent_tag = intent_names.get(cq.question_type.value)
    if intent_tag:
        tags.append(intent_tag)
    
    shape_tag = shape_names.get(cq.output_shape.value)
    if shape_tag:
        tags.append(shape_tag)
    
    # Primary dimension
    if cq.primary_dimension:
        dim_names = {
            "materialName": "malzeme",
            "faultCode": "arıza kodu",
            "vehicleModel": "model",
            "vehicleType": "araç tipi",
            "customer": "müşteri",
            "serviceLocation": "servis",
        }
        dim_tag = dim_names.get(cq.primary_dimension, cq.primary_dimension)
        if dim_tag not in tags:
            tags.append(dim_tag)
    
    return tags[:5]  # Maksimum 5 tag


def derive_queries_from_canonical() -> List[QuickQuery]:
    """
    Canonical questions'tan QuickQuery listesi türet.
    
    Her canonical question'ın examples listesinden sorgular oluşturulur.
    Bu fonksiyon her çağrıda CANONICAL_QUESTIONS_V2'den güncel veriyi okur.
    """
    queries: List[QuickQuery] = []
    seen_texts: set = set()  # Duplicate kontrolü
    
    for cq_idx, cq in enumerate(CANONICAL_QUESTIONS_V2):
        category_id = _intent_to_category_id(cq.question_type)
        canonical_ref = _generate_canonical_ref(cq)
        tags = _extract_tags_from_cq(cq)
        
        # Her example için bir QuickQuery oluştur
        for ex_idx, example_text in enumerate(cq.examples):
            # Normalize et ve duplicate kontrolü
            normalized = example_text.strip()
            normalized_lower = normalized.lower()
            
            if normalized_lower in seen_texts:
                continue
            seen_texts.add(normalized_lower)
            
            query_id = f"cq_{cq_idx:03d}_{ex_idx:02d}"
            
            queries.append(QuickQuery(
                id=query_id,
                category_id=category_id,
                text=normalized,
                description=cq.description,
                tags=tags,
                is_active=True,
                order=ex_idx,
                source=QuerySource.CANONICAL,
                canonical_ref=canonical_ref,
            ))
    
    return queries


# ============================================================================
# DATA ACCESS LAYER
# ============================================================================
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# MongoDB'ye geçiş için SADECE bu bölümü değiştir!
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _ensure_data_file() -> None:
    """JSON dosyasının varlığını kontrol et, yoksa varsayılan oluştur"""
    if not CUSTOM_QUERIES_FILE.exists():
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        
        default_data = {
            "version": "1.0",
            "last_updated": datetime.utcnow().isoformat() + "Z",
            "categories": [],  # Custom kategoriler
            "queries": [],     # Custom sorgular
        }
        
        with open(CUSTOM_QUERIES_FILE, "w", encoding="utf-8") as f:
            json.dump(default_data, f, ensure_ascii=False, indent=2)


def _load_custom_data() -> Dict[str, Any]:
    """
    Custom sorguları yükle.
    
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    MongoDB GEÇİŞİ İÇİN:
    
    from config import lrs_db
    
    def _load_custom_data() -> Dict[str, Any]:
        collection = lrs_db["quick_queries"]
        doc = collection.find_one({"_id": "quick_queries_data"})
        if not doc:
            return {"version": "1.0", "categories": [], "queries": []}
        del doc["_id"]
        return doc
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    """
    _ensure_data_file()
    
    try:
        with open(CUSTOM_QUERIES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return {"version": "1.0", "categories": [], "queries": []}


def _save_custom_data(data: Dict[str, Any]) -> None:
    """
    Custom sorguları kaydet.
    
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    MongoDB GEÇİŞİ İÇİN:
    
    from config import lrs_db
    
    def _save_custom_data(data: Dict[str, Any]) -> None:
        data["last_updated"] = datetime.utcnow().isoformat() + "Z"
        collection = lrs_db["quick_queries"]
        collection.replace_one(
            {"_id": "quick_queries_data"},
            {**data, "_id": "quick_queries_data"},
            upsert=True
        )
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    """
    data["last_updated"] = datetime.utcnow().isoformat() + "Z"
    
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    # Atomic write
    temp_file = CUSTOM_QUERIES_FILE.with_suffix(".tmp")
    with open(temp_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    temp_file.replace(CUSTOM_QUERIES_FILE)


def _generate_id(prefix: str = "q") -> str:
    """Unique ID oluştur"""
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


# ============================================================================
# SERVICE FUNCTIONS
# ============================================================================

def get_all_queries(
    include_canonical: bool = True,
    include_custom: bool = True,
    active_only: bool = False,
    category_id: Optional[str] = None,
) -> QuickQueriesData:
    """
    Tüm sorguları getir.
    
    Args:
        include_canonical: Canonical'dan türetilen sorguları dahil et
        include_custom: Kullanıcının eklediği sorguları dahil et
        active_only: Sadece aktif sorguları getir
        category_id: Belirli bir kategoriye filtrele
    
    Returns:
        QuickQueriesData: Kategoriler ve sorgular
    """
    all_queries: List[QuickQuery] = []
    canonical_count = 0
    custom_count = 0
    
    # 1) Canonical'dan türet
    if include_canonical:
        canonical_queries = derive_queries_from_canonical()
        canonical_count = len(canonical_queries)
        all_queries.extend(canonical_queries)
    
    # 2) Custom sorguları yükle
    if include_custom:
        custom_data = _load_custom_data()
        for q_dict in custom_data.get("queries", []):
            custom_count += 1
            all_queries.append(QuickQuery(
                id=q_dict["id"],
                category_id=q_dict.get("category_id", "custom"),
                text=q_dict["text"],
                description=q_dict.get("description", ""),
                tags=q_dict.get("tags", []),
                is_active=q_dict.get("is_active", True),
                order=q_dict.get("order", 0),
                source=QuerySource.CUSTOM,
                canonical_ref=None,
            ))
    
    # 3) Filtreler
    if active_only:
        all_queries = [q for q in all_queries if q.is_active]
    
    if category_id:
        all_queries = [q for q in all_queries if q.category_id == category_id]
    
    # 4) Sırala: kategori → order → text
    all_queries.sort(key=lambda q: (q.category_id, q.order, q.text))
    
    # 5) Kategorileri hazırla
    custom_data = _load_custom_data()
    custom_categories = [
        QuickQueryCategory(**{**c, "is_default": False}) 
        for c in custom_data.get("categories", [])
    ]
    
    # Varsayılan + custom kategoriler
    all_category_ids = {c.id for c in DEFAULT_CATEGORIES}
    final_categories = list(DEFAULT_CATEGORIES)
    
    for cc in custom_categories:
        if cc.id not in all_category_ids:
            final_categories.append(cc)
            all_category_ids.add(cc.id)
    
    final_categories.sort(key=lambda c: c.order)
    
    return QuickQueriesData(
        version="1.0",
        last_updated=datetime.utcnow().isoformat() + "Z",
        categories=final_categories,
        queries=all_queries,
        canonical_count=canonical_count,
        custom_count=custom_count,
    )


def get_active_queries() -> List[Dict[str, Any]]:
    """
    Sadece aktif sorguları getir (chat dropdown için).
    
    Returns:
        List[Dict]: Kategoriye göre gruplandırılmış sorgular
    """
    data = get_all_queries(active_only=True)
    return [q.to_dict() for q in data.queries]


def get_categories() -> List[QuickQueryCategory]:
    """Kategorileri getir"""
    data = get_all_queries(include_canonical=False, include_custom=True)
    return data.categories


def get_query_by_id(query_id: str) -> Optional[QuickQuery]:
    """ID ile sorgu getir"""
    data = get_all_queries()
    for q in data.queries:
        if q.id == query_id:
            return q
    return None


def create_custom_query(
    text: str,
    category_id: str,
    description: str = "",
    tags: Optional[List[str]] = None,
    is_active: bool = True,
    order: int = 0,
) -> QuickQuery:
    """
    Yeni custom sorgu oluştur.
    
    Returns:
        QuickQuery: Oluşturulan sorgu
    """
    data = _load_custom_data()
    
    # Kategori kontrolü
    valid_categories = {c.id for c in DEFAULT_CATEGORIES}
    valid_categories.update(c["id"] for c in data.get("categories", []))
    
    if category_id not in valid_categories:
        raise ValueError(f"Geçersiz kategori: {category_id}")
    
    new_query = {
        "id": _generate_id("custom"),
        "category_id": category_id,
        "text": text,
        "description": description,
        "tags": tags or [],
        "is_active": is_active,
        "order": order,
        "source": QuerySource.CUSTOM.value,
        "created_at": datetime.utcnow().isoformat() + "Z",
    }
    
    if "queries" not in data:
        data["queries"] = []
    
    data["queries"].append(new_query)
    _save_custom_data(data)
    
    return QuickQuery(**{**new_query, "source": QuerySource.CUSTOM})


def update_custom_query(
    query_id: str,
    text: Optional[str] = None,
    category_id: Optional[str] = None,
    description: Optional[str] = None,
    tags: Optional[List[str]] = None,
    is_active: Optional[bool] = None,
    order: Optional[int] = None,
) -> Optional[QuickQuery]:
    """
    Custom sorgu güncelle.
    
    NOT: Canonical sorgular güncellenemez (source=canonical).
    """
    # Canonical kontrolü
    if query_id.startswith("cq_"):
        raise ValueError("Referans sorgular güncellenemez")
    
    data = _load_custom_data()
    
    for i, q in enumerate(data.get("queries", [])):
        if q["id"] == query_id:
            if text is not None:
                q["text"] = text
            if category_id is not None:
                q["category_id"] = category_id
            if description is not None:
                q["description"] = description
            if tags is not None:
                q["tags"] = tags
            if is_active is not None:
                q["is_active"] = is_active
            if order is not None:
                q["order"] = order
            
            q["updated_at"] = datetime.utcnow().isoformat() + "Z"
            data["queries"][i] = q
            _save_custom_data(data)
            
            return QuickQuery(**{**q, "source": QuerySource.CUSTOM})
    
    return None


def toggle_custom_query(query_id: str) -> Optional[QuickQuery]:
    """Custom sorgunun aktif/pasif durumunu değiştir"""
    if query_id.startswith("cq_"):
        raise ValueError("Referans sorgular değiştirilemez")
    
    data = _load_custom_data()
    
    for i, q in enumerate(data.get("queries", [])):
        if q["id"] == query_id:
            q["is_active"] = not q.get("is_active", True)
            q["updated_at"] = datetime.utcnow().isoformat() + "Z"
            data["queries"][i] = q
            _save_custom_data(data)
            return QuickQuery(**{**q, "source": QuerySource.CUSTOM})
    
    return None


def delete_custom_query(query_id: str) -> bool:
    """
    Custom sorgu sil.
    
    NOT: Referans sorgular silinemez.
    """
    if query_id.startswith("cq_"):
        raise ValueError("Canonical sorgular silinemez")
    
    data = _load_custom_data()
    
    initial_len = len(data.get("queries", []))
    data["queries"] = [q for q in data.get("queries", []) if q["id"] != query_id]
    
    if len(data["queries"]) < initial_len:
        _save_custom_data(data)
        return True
    
    return False


def create_custom_category(
    name: str,
    icon: str = "📁",
    category_id: Optional[str] = None,
    order: int = 0,
) -> QuickQueryCategory:
    """Yeni custom kategori oluştur"""
    data = _load_custom_data()
    
    # ID kontrolü
    new_id = category_id or _generate_id("cat")
    
    # Varsayılan kategorilerle çakışma kontrolü
    if new_id in DEFAULT_CATEGORY_MAP:
        raise ValueError(f"Varsayılan kategori ID'si kullanılamaz: {new_id}")
    
    # Mevcut custom kategorilerle çakışma
    existing_ids = {c["id"] for c in data.get("categories", [])}
    if new_id in existing_ids:
        raise ValueError(f"Kategori ID zaten var: {new_id}")
    
    new_category = {
        "id": new_id,
        "name": name,
        "icon": icon,
        "order": order or len(data.get("categories", [])) + 50,
        "is_default": False,
        "created_at": datetime.utcnow().isoformat() + "Z",
    }
    
    if "categories" not in data:
        data["categories"] = []
    
    data["categories"].append(new_category)
    _save_custom_data(data)
    
    return QuickQueryCategory(**new_category)


def delete_custom_category(category_id: str, force: bool = False) -> bool:
    """
    Custom kategori sil.
    
    Args:
        category_id: Kategori ID
        force: True ise kategorideki sorgular da silinir
    
    NOT: Varsayılan kategoriler silinemez.
    """
    # Varsayılan kategori kontrolü
    if category_id in DEFAULT_CATEGORY_MAP:
        raise ValueError("Varsayılan kategoriler silinemez")
    
    data = _load_custom_data()
    
    # Kategorideki sorgular
    queries_in_cat = [q for q in data.get("queries", []) if q.get("category_id") == category_id]
    
    if queries_in_cat and not force:
        raise ValueError(f"Kategoride {len(queries_in_cat)} sorgu var. force=True kullanın.")
    
    # Kategori ve sorgularını sil
    initial_cat_len = len(data.get("categories", []))
    data["categories"] = [c for c in data.get("categories", []) if c["id"] != category_id]
    
    if force:
        data["queries"] = [q for q in data.get("queries", []) if q.get("category_id") != category_id]
    
    if len(data.get("categories", [])) < initial_cat_len:
        _save_custom_data(data)
        return True
    
    return False


def get_stats() -> Dict[str, Any]:
    """
    Senkronizasyon istatistikleri.
    
    Returns:
        Dict: Referans ve özel sorgu sayıları
    """
    canonical_queries = derive_queries_from_canonical()
    custom_data = _load_custom_data()
    
    return {
        "canonical_count": len(canonical_queries),
        "custom_count": len(custom_data.get("queries", [])),
        "custom_categories_count": len(custom_data.get("categories", [])),
        "default_categories_count": len(DEFAULT_CATEGORIES),
        "last_updated": custom_data.get("last_updated"),
    }


# ============================================================================
# EXPORT
# ============================================================================

__all__ = [
    # Enums & Models
    "QuerySource",
    "QuickQueryCategory",
    "QuickQuery",
    "QuickQueriesData",
    
    # Service Functions
    "get_all_queries",
    "get_active_queries",
    "get_categories",
    "get_query_by_id",
    "create_custom_query",
    "update_custom_query",
    "toggle_custom_query",
    "delete_custom_query",
    "create_custom_category",
    "delete_custom_category",
    "get_stats",
    
    # For testing
    "derive_queries_from_canonical",
    "DEFAULT_CATEGORIES",
]