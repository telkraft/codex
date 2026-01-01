# api/routes_schema.py

from fastapi import APIRouter
from typing import Dict, Any

router = APIRouter(
    prefix="/schema",
    tags=["schema"],
)

# Simplified schema for frontend display
SCHEMA_INFO = {
    "version": "1.0.0",
    "description": "Promptever MAN Türkiye Araç Bakım xAPI Şeması",
    
    "dimensions": [
        # Actor
        {"key": "vehicleId", "name": "Araç ID", "category": "Araç", "type": "string", "examples": ["70886", "70123"]},
        {"key": "vehicleType", "name": "Araç Tipi", "category": "Araç", "type": "enum", "examples": ["bus", "lkw"]},
        {"key": "manufacturer", "name": "Üretici", "category": "Araç", "type": "enum", "examples": ["man", "mercedes"]},
        {"key": "modelNo", "name": "Model No", "category": "Araç", "type": "string", "examples": ["rhc 444 440"]},
        
        # İşlem
        {"key": "verbType", "name": "İşlem Tipi", "category": "İşlem", "type": "enum", "examples": ["BAKIM", "ONARIM"]},
        {"key": "operationCategory", "name": "İşlem Kategorisi", "category": "İşlem", "type": "enum", "examples": ["malzeme", "iscilik"]},
        {"key": "separationType", "name": "Ayrım Tipi", "category": "İşlem", "type": "string", "examples": ["bakimpaketi", "onarim"]},
        
        # Malzeme
        {"key": "materialName", "name": "Malzeme Adı", "category": "Malzeme", "type": "string", "examples": ["fren diski", "yağ filtresi"]},
        {"key": "materialId", "name": "Malzeme ID", "category": "Malzeme", "type": "string", "examples": ["ZU.FUCHS-SE55"]},
        {"key": "stockType", "name": "Stok Tipi", "category": "Malzeme", "type": "string", "examples": ["yedekparca man"]},
        {"key": "faultCode", "name": "Arıza Kodu", "category": "Malzeme", "type": "string", "examples": ["wd1a2000000zw"]},
        
        # Lokasyon & Müşteri
        {"key": "serviceLocation", "name": "Servis Lokasyonu", "category": "Lokasyon", "type": "string", "examples": ["R540", "R600"]},
        {"key": "customerId", "name": "Müşteri ID", "category": "Müşteri", "type": "string", "examples": ["159485"]},
        {"key": "workOrderId", "name": "İş Emri No", "category": "İş Emri", "type": "string", "examples": ["04072017208"]},
        
        # Zaman
        {"key": "year", "name": "Yıl", "category": "Zaman", "type": "integer", "examples": [2017, 2022]},
        {"key": "month", "name": "Ay", "category": "Zaman", "type": "integer", "examples": [1, 6, 12]},
        {"key": "quarter", "name": "Çeyrek", "category": "Zaman", "type": "integer", "examples": [1, 2, 3, 4]},
        {"key": "season", "name": "Mevsim", "category": "Zaman", "type": "enum", "examples": ["winter", "spring", "summer", "autumn"]},
        {"key": "operationDate", "name": "İşlem Tarihi", "category": "Zaman", "type": "date", "examples": ["2022-01-15"]},
    ],
    
    "metrics": [
        {"key": "count", "name": "İşlem Sayısı", "unit": "adet", "type": "count"},
        {"key": "sum_cost", "name": "Toplam Maliyet", "unit": "TL", "type": "sum"},
        {"key": "avg_cost", "name": "Ortalama Maliyet", "unit": "TL", "type": "avg"},
        {"key": "sum_quantity", "name": "Toplam Miktar", "unit": "adet", "type": "sum"},
        {"key": "avg_quantity", "name": "Ortalama Miktar", "unit": "adet", "type": "avg"},
        {"key": "avg_km", "name": "Ortalama Kilometre", "unit": "km", "type": "avg"},
        {"key": "min_km", "name": "Minimum Kilometre", "unit": "km", "type": "min"},
        {"key": "max_km", "name": "Maximum Kilometre", "unit": "km", "type": "max"},
        {"key": "sum_discount", "name": "Toplam İndirim", "unit": "TL", "type": "sum"},
    ],
    
    "verbs": [
        {"id": "maintained", "display": "Bakım", "description": "Periyodik bakım işlemi"},
        {"id": "repaired", "display": "Onarım", "description": "Arıza onarım işlemi"},
        {"id": "inspected", "display": "Kontrol", "description": "Araç kontrol işlemi"},
    ],
    
    "example_queries": [
        "En çok bakım yapılan araç tipleri nelerdir?",
        "2022 yılında hangi malzemeler en çok kullanıldı?",
        "Kış aylarında arıza oranı nedir?",
        "R540 servisinde toplam maliyet ne kadar?",
        "Otobüslerin ortalama bakım maliyeti nedir?",
    ],
}


@router.get("")
async def get_schema() -> Dict[str, Any]:
    """
    xAPI statement şemasını döndürür.
    Frontend ontoloji sayfası için kullanılır.
    """
    return SCHEMA_INFO


@router.get("/dimensions")
async def get_dimensions() -> Dict[str, Any]:
    """Sadece dimension listesini döndürür."""
    return {"dimensions": SCHEMA_INFO["dimensions"]}


@router.get("/metrics")
async def get_metrics() -> Dict[str, Any]:
    """Sadece metric listesini döndürür."""
    return {"metrics": SCHEMA_INFO["metrics"]}