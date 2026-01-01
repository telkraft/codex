# xapi_statement_schema.py
"""
xAPI Statement Schema
=====================

Bu modül, xAPI statement yapısını tam olarak dokümante eder ve
query yapılabilecek tüm dimensions ve metrics'i tanımlar.

Statement Yapısı (Örnek):
-------------------------
{
    "id": "49cbf971-40f8-4341-9e46-787e3180fa44",
    "actor": {
        "name": "Arac 70886",
        "objectType": "Agent",
        "account": {
            "name": "vehicle/70886",
            "homePage": "https://promptever.com"
        }
    },
    "verb": {
        "id": "https://promptever.com/verbs/maintained",
        "display": {
            "tr-TR": "Bakım",
            "en-US": "Maintained"
        }
    },
    "object": {
        "id": "https://promptever.com/activities/material/ZU.FUCHS-SE55",
        "definition": {
            "name": {
                "tr-TR": "fuchs reniso triton se 55 1lt",
                "en-US": "fuchs reniso triton se 55 1lt"
            },
            "type": "https://promptever.com/activitytypes/material"
        },
        "objectType": "Activity"
    },
    "result": {
        "extensions": {
            "https://promptever.com/extensions/odometerReading": 278796,
            "https://promptever.com/extensions/faultCode": "wd1a2000000zw",
            "https://promptever.com/extensions/materialCost": 260.43,
            "https://promptever.com/extensions/discountAmount": 260.43,
            "https://promptever.com/extensions/materialQuantity": 3
        },
        "success": true,
        "completion": true
    },
    "context": {
        "extensions": {
            "https://promptever.com/extensions/vehicleType": "bus",
            "https://promptever.com/extensions/manufacturer": "man",
            "https://promptever.com/extensions/operationDate": "2017-11-24T00:00:00.000Z",
            "https://promptever.com/extensions/stockType": "yedekparca man",
            "https://promptever.com/extensions/firstRegistrationDate": "2016-04-12T00:00:00.000Z",
            "https://promptever.com/extensions/modelNo": "rhc 444 440",
            "https://promptever.com/extensions/recordDate": "2017-07-04T12:59:22.000Z",
            "https://promptever.com/extensions/operationCategory": "malzeme",
            "https://promptever.com/extensions/separationType": "bakimpaketi"
        },
        "contextActivities": {
            "parent": [
                {
                    "id": "https://promptever.com/activities/workorder/04072017208",
                    "objectType": "Activity"
                }
            ],
            "grouping": [
                {
                    "id": "https://promptever.com/activities/customer/159485",
                    "definition": {
                        "name": {
                            "tr-TR": "Musteri 159485"
                        }
                    },
                    "objectType": "Activity"
                },
                {
                    "id": "https://promptever.com/activities/service-location/r540",
                    "definition": {
                        "name": {
                            "tr-TR": "Servis r540"
                        }
                    },
                    "objectType": "Activity"
                }
            ]
        }
    },
    "timestamp": "2017-07-05T15:25:11.000Z",
    "stored": "2025-11-24T01:48:51.760Z"
}
"""

from typing import Dict, Any, Optional, List, Callable


# ============================================================================
# DIMENSION TANIMLARI
# ============================================================================

DIMENSIONS = {
    
    # ------------------------------------------------------------------------
    # ACTOR (Araç) Dimensions
    # ------------------------------------------------------------------------
    
    "vehicleId": {
        "display_name": "Araç ID",
        "description": "Aracın benzersiz kimlik numarası (örn: 70886)",
        "mongo_path": "actor.account.name",
        "data_type": "string",
        "extraction_method": "extract_vehicle_id",
        "example_values": ["70886", "70123", "71234"],
        "cardinality": "high",  # Çok sayıda farklı değer
        "queryable": True,
        "filterable": True,
    },
    
    # ------------------------------------------------------------------------
    # VERB (İşlem Tipi) Dimensions
    # ------------------------------------------------------------------------
    
    "verbType": {
        "display_name": "İşlem Tipi",
        "description": "Gerçekleştirilen işlem türü (bakım, tamir, kontrol)",
        "mongo_expr": {
            "$switch": {
                "branches": [
                    {
                        "case": {
                            "$regexMatch": {
                                "input": {"$ifNull": ["$verb.id", ""]},
                                "regex": "maintained",
                                "options": "i",
                            }
                        },
                        "then": "maintained",
                    },
                    {
                        "case": {
                            "$regexMatch": {
                                "input": {"$ifNull": ["$verb.id", ""]},
                                "regex": "repaired",
                                "options": "i",
                            }
                        },
                        "then": "repaired",
                    },
                    {
                        "case": {
                            "$regexMatch": {
                                "input": {"$ifNull": ["$verb.id", ""]},
                                "regex": "inspected",
                                "options": "i",
                            }
                        },
                        "then": "inspected",
                    },
                ],
                "default": "unknown",
            }
        },
        "data_type": "enum",
        "example_values": ["maintained", "repaired", "inspected"],
        "cardinality": "low",  # Az sayıda farklı değer
        "queryable": True,
        "filterable": True,
    },
    
    # ------------------------------------------------------------------------
    # OBJECT (Malzeme/Parça) Dimensions
    # ------------------------------------------------------------------------
    
    "materialName": {
        "display_name": "Malzeme Adı",
        "description": "Kullanılan malzeme veya parçanın adı",
        "mongo_path": "object.definition.name.tr-TR",
        "data_type": "string",
        "normalization": "turkish_lowercase",
        "example_values": [
            "fuchs reniso triton se 55 1lt",
            "fren diski",
            "hava filtresi",
        ],
        "cardinality": "high",
        "queryable": True,
        "filterable": True,
        "searchable": True,  # Text search destekler
    },
    
    "materialId": {
        "display_name": "Malzeme ID",
        "description": "Malzemenin benzersiz kodu (örn: ZU.FUCHS-SE55)",
        "mongo_path": "object.id",
        "extraction_method": "extract_material_id",
        "data_type": "string",
        "example_values": ["ZU.FUCHS-SE55", "BR.12345", "FT.AB-123"],
        "cardinality": "high",
        "queryable": True,
        "filterable": True,
    },
    
    "materialType": {
        "display_name": "Malzeme Tipi",
        "description": "Malzeme kategorisi",
        "mongo_path": "object.definition.type",
        "data_type": "string",
        "example_values": ["material", "part", "consumable"],
        "cardinality": "low",
        "queryable": True,
        "filterable": True,
    },
    
    # ------------------------------------------------------------------------
    # RESULT Extensions Dimensions
    # ------------------------------------------------------------------------
    
    "faultCode": {
        "display_name": "Arıza Kodu",
        "description": "Tespit edilen arıza kodu",
        "mongo_path": "result.extensions.https://promptever.com/extensions/faultCode",
        "data_type": "string",
        "example_values": ["wd1a2000000zw", "ABC12345", "XYZ98765"],
        "cardinality": "medium",
        "queryable": True,
        "filterable": True,
        "nullable": True,  # Her kayıtta olmayabilir
    },
    
    # ------------------------------------------------------------------------
    # CONTEXT Extensions Dimensions
    # ------------------------------------------------------------------------
    
    "vehicleType": {
        "display_name": "Araç Tipi",
        "description": "Aracın tipi (otobüs, kamyon, minibüs)",
        "mongo_path": "context.extensions.https://promptever.com/extensions/vehicleType",
        "data_type": "enum",
        "normalization": "english_lowercase",
        "example_values": ["bus", "truck", "minibus"],
        "cardinality": "low",
        "queryable": True,
        "filterable": True,
    },
    
    "manufacturer": {
        "display_name": "Üretici",
        "description": "Aracın üreticisi",
        "mongo_path": "context.extensions.https://promptever.com/extensions/manufacturer",
        "data_type": "enum",
        "normalization": "english_lowercase",
        "example_values": ["man", "mercedes", "iveco", "ford"],
        "cardinality": "low",
        "queryable": True,
        "filterable": True,
    },
    
    "modelNo": {
        "display_name": "Model Numarası",
        "description": "Araç model numarası",
        "mongo_path": "context.extensions.https://promptever.com/extensions/modelNo",
        "data_type": "string",
        "normalization": "turkish_lowercase",
        "example_values": ["rhc 444 440", "actros 1840", "daily 35s"],
        "cardinality": "medium",
        "queryable": True,
        "filterable": True,
    },
    
    "stockType": {
        "display_name": "Stok Tipi",
        "description": "Malzeme stok kategorisi",
        "mongo_path": "context.extensions.https://promptever.com/extensions/stockType",
        "data_type": "string",
        "example_values": ["yedekparca man", "yedekparca mercedes", "sarf malzeme"],
        "cardinality": "low",
        "queryable": True,
        "filterable": True,
    },
    
    "operationCategory": {
        "display_name": "İşlem Kategorisi",
        "description": "İşlemin kategorisi",
        "mongo_path": "context.extensions.https://promptever.com/extensions/operationCategory",
        "data_type": "enum",
        "example_values": ["malzeme", "iscilik", "dis_hizmet"],
        "cardinality": "low",
        "queryable": True,
        "filterable": True,
    },
    
    "separationType": {
        "display_name": "Ayrım Tipi",
        "description": "İşlemin ayrım kategorisi",
        "mongo_path": "context.extensions.https://promptever.com/extensions/separationType",
        "data_type": "string",
        "example_values": ["bakimpaketi", "onarim", "periyodik"],
        "cardinality": "low",
        "queryable": True,
        "filterable": True,
    },
    
    # ------------------------------------------------------------------------
    # CONTEXT Activities Dimensions
    # ------------------------------------------------------------------------
    
    "workOrderId": {
        "display_name": "İş Emri No",
        "description": "İş emri numarası",
        "mongo_path": "context.contextActivities.parent",
        "extraction_method": "extract_workorder_id",
        "data_type": "string",
        "example_values": ["04072017208", "15082022345", "23092023111"],
        "cardinality": "high",
        "queryable": True,
        "filterable": True,
    },
    
    "customerId": {
        "display_name": "Müşteri ID",
        "description": "Müşteri kimlik numarası",
        "mongo_path": "context.contextActivities.grouping",
        "extraction_method": "extract_customer_id",
        "data_type": "string",
        "example_values": ["159485", "123456", "789012"],
        "cardinality": "high",
        "queryable": True,
        "filterable": True,
    },
    
    "serviceLocation": {
        "display_name": "Servis Lokasyonu",
        "description": "İşlemin yapıldığı servis lokasyonu",
        "mongo_path": "context.contextActivities.grouping",
        "extraction_method": "extract_service_location",
        "data_type": "string",
        "example_values": ["r540", "r600", "r755"],
        "cardinality": "low",
        "queryable": True,
        "filterable": True,
    },
    
    # ------------------------------------------------------------------------
    # ZAMAN Dimensions (Derived)
    # ------------------------------------------------------------------------
    
    "year": {
        "display_name": "Yıl",
        "description": "İşlem yılı",
        "mongo_expr": {"$year": "$context.extensions.https://promptever.com/extensions/operationDate"},
        "data_type": "integer",
        "example_values": [2017, 2018, 2019, 2020, 2021, 2022, 2023],
        "cardinality": "low",
        "queryable": True,
        "filterable": True,
    },
    
    "month": {
        "display_name": "Ay",
        "description": "İşlem ayı (1-12)",
        "mongo_expr": {"$month": "$context.extensions.https://promptever.com/extensions/operationDate"},
        "data_type": "integer",
        "example_values": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
        "cardinality": "low",
        "queryable": True,
        "filterable": True,
    },
    
    "quarter": {
        "display_name": "Çeyrek",
        "description": "İşlem çeyreği (Q1-Q4)",
        "mongo_expr": {
            "$ceil": {
                "$divide": [
                    {"$month": "$context.extensions.https://promptever.com/extensions/operationDate"},
                    3
                ]
            }
        },
        "data_type": "integer",
        "example_values": [1, 2, 3, 4],
        "cardinality": "low",
        "queryable": True,
        "filterable": True,
    },
    
    "dayOfWeek": {
        "display_name": "Haftanın Günü",
        "description": "İşlemin yapıldığı günün haftanın kaçıncı günü olduğu (1=Pazar, 7=Cumartesi)",
        "mongo_expr": {"$dayOfWeek": "$context.extensions.https://promptever.com/extensions/operationDate"},
        "data_type": "integer",
        "example_values": [1, 2, 3, 4, 5, 6, 7],
        "cardinality": "low",
        "queryable": True,
        "filterable": False,
    },
    
    "season": {
        "display_name": "Mevsim",
        "description": "İşlemin yapıldığı mevsim",
        "mongo_expr": {
            "$switch": {
                "branches": [
                    {
                        "case": {
                            "$in": [
                                {"$month": "$context.extensions.https://promptever.com/extensions/operationDate"},
                                [12, 1, 2]
                            ]
                        },
                        "then": "winter"
                    },
                    {
                        "case": {
                            "$in": [
                                {"$month": "$context.extensions.https://promptever.com/extensions/operationDate"},
                                [3, 4, 5]
                            ]
                        },
                        "then": "spring"
                    },
                    {
                        "case": {
                            "$in": [
                                {"$month": "$context.extensions.https://promptever.com/extensions/operationDate"},
                                [6, 7, 8]
                            ]
                        },
                        "then": "summer"
                    },
                ],
                "default": "autumn"
            }
        },
        "data_type": "enum",
        "example_values": ["winter", "spring", "summer", "autumn"],
        "cardinality": "low",
        "queryable": True,
        "filterable": True,
    },
    
    "operationDate": {
        "display_name": "İşlem Tarihi",
        "description": "İşlemin yapıldığı tarih",
        "mongo_path": "context.extensions.https://promptever.com/extensions/operationDate",
        "data_type": "date",
        "queryable": True,
        "filterable": True,
        "sortable": True,
    },
}


# ============================================================================
# METRIC TANIMLARI
# ============================================================================

METRICS = {
    
    # ------------------------------------------------------------------------
    # COUNT Metrics
    # ------------------------------------------------------------------------
    
    "count": {
        "display_name": "İşlem Sayısı",
        "description": "Toplam işlem/kayıt sayısı",
        "type": "count",
        "aggregation": "sum",
        "data_type": "integer",
        "unit": "adet",
        "queryable": True,
    },
    
    # ------------------------------------------------------------------------
    # RESULT Extensions Metrics
    # ------------------------------------------------------------------------
    
    "sum_quantity": {
        "display_name": "Toplam Miktar",
        "description": "Kullanılan toplam malzeme miktarı",
        "type": "sum",
        "mongo_expr": {
            "$ifNull": [
                "$result.extensions.https://promptever.com/extensions/materialQuantity",
                0
            ]
        },
        "data_type": "numeric",
        "unit": "adet",
        "queryable": True,
    },
    
    "avg_quantity": {
        "display_name": "Ortalama Miktar",
        "description": "İşlem başına ortalama malzeme miktarı",
        "type": "avg",
        "mongo_expr": {
            "$ifNull": [
                "$result.extensions.https://promptever.com/extensions/materialQuantity",
                0
            ]
        },
        "data_type": "numeric",
        "unit": "adet",
        "queryable": True,
    },
    
    "sum_cost": {
        "display_name": "Toplam Maliyet",
        "description": "Toplam malzeme maliyeti",
        "type": "sum",
        "mongo_expr": {
            "$ifNull": [
                "$result.extensions.https://promptever.com/extensions/materialCost",
                0
            ]
        },
        "data_type": "numeric",
        "unit": "TL",
        "queryable": True,
    },
    
    "avg_cost": {
        "display_name": "Ortalama Maliyet",
        "description": "İşlem başına ortalama maliyet",
        "type": "avg",
        "mongo_expr": {
            "$ifNull": [
                "$result.extensions.https://promptever.com/extensions/materialCost",
                0
            ]
        },
        "data_type": "numeric",
        "unit": "TL",
        "queryable": True,
    },
    
    "sum_discount": {
        "display_name": "Toplam İndirim",
        "description": "Uygulanan toplam indirim tutarı",
        "type": "sum",
        "mongo_expr": {
            "$ifNull": [
                "$result.extensions.https://promptever.com/extensions/discountAmount",
                0
            ]
        },
        "data_type": "numeric",
        "unit": "TL",
        "queryable": True,
    },
    
    "avg_km": {
        "display_name": "Ortalama Kilometre",
        "description": "İşlem sırasındaki ortalama araç kilometresi",
        "type": "avg",
        "mongo_expr": {
            "$ifNull": [
                "$result.extensions.https://promptever.com/extensions/odometerReading",
                0
            ]
        },
        "data_type": "numeric",
        "unit": "km",
        "queryable": True,
    },
    
    "min_km": {
        "display_name": "Minimum Kilometre",
        "description": "En düşük kilometre değeri",
        "type": "min",
        "mongo_expr": {
            "$ifNull": [
                "$result.extensions.https://promptever.com/extensions/odometerReading",
                0
            ]
        },
        "data_type": "numeric",
        "unit": "km",
        "queryable": True,
    },
    
    "max_km": {
        "display_name": "Maximum Kilometre",
        "description": "En yüksek kilometre değeri",
        "type": "max",
        "mongo_expr": {
            "$ifNull": [
                "$result.extensions.https://promptever.com/extensions/odometerReading",
                0
            ]
        },
        "data_type": "numeric",
        "unit": "km",
        "queryable": True,
    },
}


# ============================================================================
# SCHEMA METADATA
# ============================================================================

SCHEMA_METADATA = {
    "version": "1.0.0",
    "last_updated": "2024-12-05",
    "description": "Promptever Araç Bakım xAPI Statement Şeması",
    "statement_count_estimate": 1000000,  # Örnek
    "date_range": {
        "start": "2015-01-01",
        "end": "2024-12-31",
    },
    "supported_verbs": [
        "maintained",
        "repaired",
        "inspected",
    ],
    "supported_object_types": [
        "material",
        "part",
        "service",
    ],
}


# ============================================================================
# EXTRACTION FONKS İYONLARI
# ============================================================================

def extract_vehicle_id(doc: Dict[str, Any]) -> Optional[str]:
    """
    Statement'tan araç ID'sini çıkarır.
    
    actor.account.name formatı: "vehicle/70886"
    """
    try:
        name = doc.get("actor", {}).get("account", {}).get("name", "")
        if isinstance(name, str) and name.startswith("vehicle/"):
            return name.split("/", 1)[1]
        return name if name else None
    except Exception:
        return None


def extract_material_id(doc: Dict[str, Any]) -> Optional[str]:
    """
    Statement'tan malzeme ID'sini çıkarır.
    
    object.id formatı: "https://promptever.com/activities/material/ZU.FUCHS-SE55"
    """
    try:
        obj_id = doc.get("object", {}).get("id", "")
        if isinstance(obj_id, str) and "/material/" in obj_id:
            return obj_id.split("/material/", 1)[1]
        return None
    except Exception:
        return None


def extract_workorder_id(doc: Dict[str, Any]) -> Optional[str]:
    """
    Statement'tan iş emri ID'sini çıkarır.
    
    context.contextActivities.parent[0].id formatı:
    "https://promptever.com/activities/workorder/04072017208"
    """
    try:
        parent = doc.get("context", {}).get("contextActivities", {}).get("parent", [])
        if parent and isinstance(parent, list):
            parent_id = parent[0].get("id", "")
            if "/workorder/" in parent_id:
                return parent_id.split("/workorder/", 1)[1]
        return None
    except Exception:
        return None


def extract_customer_id(doc: Dict[str, Any]) -> Optional[str]:
    """
    Statement'tan müşteri ID'sini çıkarır.
    
    context.contextActivities.grouping içinde customer activity'sini arar.
    """
    try:
        grouping = doc.get("context", {}).get("contextActivities", {}).get("grouping", [])
        for activity in grouping:
            act_id = activity.get("id", "")
            if "/customer/" in act_id:
                return act_id.split("/customer/", 1)[1]
        return None
    except Exception:
        return None


def extract_service_location(doc: Dict[str, Any]) -> Optional[str]:
    """
    Statement'tan servis lokasyonunu çıkarır.
    
    context.contextActivities.grouping içinde service-location activity'sini arar.
    """
    try:
        grouping = doc.get("context", {}).get("contextActivities", {}).get("grouping", [])
        for activity in grouping:
            act_id = activity.get("id", "")
            if "/service-location/" in act_id:
                loc_code = act_id.split("/service-location/", 1)[1]
                return loc_code.upper()
        return None
    except Exception:
        return None


# ============================================================================
# SCHEMA DOĞRULAMA
# ============================================================================

def validate_statement(doc: Dict[str, Any]) -> List[str]:
    """
    xAPI statement'ın şemaya uygunluğunu kontrol eder.
    
    Returns:
        Liste of validation errors (boşsa geçerli)
    """
    errors = []
    
    # 1. Zorunlu alanlar
    if "id" not in doc:
        errors.append("Missing required field: id")
    
    if "actor" not in doc or not isinstance(doc["actor"], dict):
        errors.append("Missing or invalid required field: actor")
    
    if "verb" not in doc or not isinstance(doc["verb"], dict):
        errors.append("Missing or invalid required field: verb")
    
    if "object" not in doc or not isinstance(doc["object"], dict):
        errors.append("Missing or invalid required field: object")
    
    # 2. Actor validation
    if "actor" in doc:
        actor = doc["actor"]
        if "account" not in actor:
            errors.append("Missing actor.account")
        elif not isinstance(actor["account"], dict):
            errors.append("Invalid actor.account (must be object)")
        else:
            if "name" not in actor["account"]:
                errors.append("Missing actor.account.name")
    
    # 3. Verb validation
    if "verb" in doc:
        verb = doc["verb"]
        if "id" not in verb:
            errors.append("Missing verb.id")
    
    # 4. Object validation
    if "object" in doc:
        obj = doc["object"]
        if "id" not in obj:
            errors.append("Missing object.id")
        if "definition" not in obj:
            errors.append("Missing object.definition")
    
    return errors


# ============================================================================
# ANA SCHEMA OBJESİ
# ============================================================================

XAPI_STATEMENT_SCHEMA = {
    "dimensions": DIMENSIONS,
    "metrics": METRICS,
    "metadata": SCHEMA_METADATA,
    "extractors": {
        "vehicle_id": extract_vehicle_id,
        "material_id": extract_material_id,
        "workorder_id": extract_workorder_id,
        "customer_id": extract_customer_id,
        "service_location": extract_service_location,
    },
    "validators": {
        "statement": validate_statement,
    },
}


if __name__ == "__main__":
    # Schema bilgilerini yazdır
    print("=" * 70)
    print("xAPI STATEMENT SCHEMA")
    print("=" * 70)
    print(f"Version: {SCHEMA_METADATA['version']}")
    print(f"Last Updated: {SCHEMA_METADATA['last_updated']}")
    print(f"\nTotal Dimensions: {len(DIMENSIONS)}")
    print(f"Total Metrics: {len(METRICS)}")
    print("\nDimensions:")
    for dim_key, dim_config in DIMENSIONS.items():
        print(f"  - {dim_key}: {dim_config['display_name']}")
    print("\nMetrics:")
    for metric_key, metric_config in METRICS.items():
        print(f"  - {metric_key}: {metric_config['display_name']}")
