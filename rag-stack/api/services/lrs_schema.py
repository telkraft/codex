"""
LRS Schema & Helpers
====================

MAN servis verisi için schema tanımı ve LRS genelinde kullanılan
yardımcı fonksiyonlar.

🔧 DÜZELTME:
- operationDate TEK GERÇEK tarih ekseni (root + statement fallback)
- year/month/day/season tamamen operationDate üzerinden
- _build_time_filter: $convert ile Date kıyas + end EXCLUSIVE ($lt)
- _extract_operation_date: SADECE operationDate (recordDate/timestamp fallback YOK)
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, Optional

from models import TimeRange
from services.xapi_nlp.nlp_utils import (
    normalize,
    normalize_tr,
    extract_year,
    extract_month,
    extract_season,
    extract_relative_period,
)


# ======================================================================
# MAN Servis Verisi İçin Şema Tanımı
# ======================================================================

def _opdate_raw_expr():
    """
    operationDate extension'ını güvenli şekilde çeker.
    
    ⚠️ URL formatındaki key'ler (https://...) içinde nokta var.
    MongoDB dot notation bu noktaları yanlış parse eder.
    Bu yüzden $getField operatörü kullanılmalı.
    """
    op_key = "https://promptever.com/extensions/operationDate"
    return {
        "$ifNull": [
            {"$getField": {"field": op_key, "input": "$context.extensions"}},
            {
                "$ifNull": [
                    {"$getField": {"field": op_key, "input": "$statement.context.extensions"}},
                    {
                        "$ifNull": [
                            {"$getField": {"field": "operationDate", "input": "$context.extensions"}},
                            {"$getField": {"field": "operationDate", "input": "$statement.context.extensions"}},
                        ]
                    },
                ]
            },
        ]
    }


def _opdate_date_expr():
    # Güvenli string->date dönüşüm (bozuk formatlarda null)
    return {
        "$convert": {
            "input": _opdate_raw_expr(),
            "to": "date",
            "onError": None,
            "onNull": None,
        }
    }


def _ext_expr(ext_key: str):
    # context.extensions içindeki IRI key’ini root + statement üzerinden oku
    return {
        "$ifNull": [
            {
                "$getField": {
                    "field": ext_key,
                    "input": "$context.extensions",
                }
            },
            {
                "$getField": {
                    "field": ext_key,
                    "input": "$statement.context.extensions",
                }
            },
        ]
    }


def _result_ext_expr(ext_key: str):
    # result.extensions içindeki IRI key’ini root + statement üzerinden oku
    return {
        "$ifNull": [
            {
                "$getField": {
                    "field": ext_key,
                    "input": "$result.extensions",
                }
            },
            {
                "$getField": {
                    "field": ext_key,
                    "input": "$statement.result.extensions",
                }
            },
        ]
    }


def _grouping0_expr():
    # context.contextActivities.grouping[0] root + statement fallback
    return {
        "$ifNull": [
            {"$arrayElemAt": ["$context.contextActivities.grouping", 0]},
            {"$arrayElemAt": ["$statement.context.contextActivities.grouping", 0]},
        ]
    }


MAN_SCHEMA: Dict[str, Any] = {
    "dimensions": {
        # --------------------------------------------------
        # Araç (tek tek araçlar) - root + statement fallback
        # --------------------------------------------------
        "vehicle": {
            "mongo_path": "actor.account.name",
            "mongo_expr": {
                "$ifNull": [
                    "$actor.account.name",
                    "$statement.actor.account.name",
                ]
            },
        },

        # --------------------------------------------------
        # Araç tipi (extension)
        # --------------------------------------------------
        "vehicleType": {
            "mongo_path": "context.extensions.https://promptever.com/extensions/vehicleType",
            "mongo_expr": _ext_expr("https://promptever.com/extensions/vehicleType"),
        },

        # --------------------------------------------------
        # Araç modeli (extension)
        # --------------------------------------------------
        "vehicleModel": {
            "mongo_path": "context.extensions.https://promptever.com/extensions/modelNo",
            "mongo_expr": {
                "$ifNull": [
                    _ext_expr("https://promptever.com/extensions/modelNo"),
                    None,
                ]
            },
        },

        # --------------------------------------------------
        # Malzeme adı
        # --------------------------------------------------
        "materialName": {
            "mongo_path": "object.definition.name.tr-TR",
            "mongo_expr": {
                "$ifNull": [
                    "$object.definition.name.tr-TR",
                    "$statement.object.definition.name.tr-TR",
                ]
            },
        },

        # --------------------------------------------------
        # Arıza kodu (extension)
        # --------------------------------------------------
        "faultCode": {
            "mongo_path": "result.extensions.https://promptever.com/extensions/faultCode",
            "mongo_expr": _result_ext_expr("https://promptever.com/extensions/faultCode"),
        },

        # --------------------------------------------------
        # Müşteri (contextActivities.grouping → customer)
        # root + statement fallback
        # --------------------------------------------------
        "customer": {
            "mongo_expr": {
                "$let": {
                    "vars": {"g": _grouping0_expr()},
                    "in": {
                        "$let": {
                            "vars": {
                                "fullId": {
                                    "$cond": [
                                        {"$and": [{"$ne": ["$$g", None]}, {"$ne": ["$$g.id", None]}]},
                                        "$$g.id",
                                        None,
                                    ]
                                }
                            },
                            "in": {
                                "$cond": [
                                    {"$eq": ["$$fullId", None]},
                                    None,
                                    {
                                        "$arrayElemAt": [
                                            {"$split": ["$$fullId", "/"]},
                                            {"$subtract": [{"$size": {"$split": ["$$fullId", "/"]}}, 1]},
                                        ]
                                    },
                                ]
                            },
                        }
                    },
                }
            },
        },

        # --------------------------------------------------
        # İşlem tipi (BAKIM / ONARIM / DİĞER)
        # --------------------------------------------------
        "verbType": {
            "mongo_expr": {
                "$let": {
                    "vars": {"verbId": {"$ifNull": ["$verb.id", "$statement.verb.id"]}},
                    "in": {
                        "$cond": [
                            {"$regexMatch": {"input": "$$verbId", "regex": "maintained$"}},
                            "BAKIM",
                            {
                                "$cond": [
                                    {"$regexMatch": {"input": "$$verbId", "regex": "repaired$"}},
                                    "ONARIM",
                                    "DİĞER",
                                ]
                            },
                        ]
                    },
                }
            },
        },

        # ===========================
        # operationDate tabanlı zaman boyutları (TEK GERÇEK)
        # ===========================

        "year": {
            "mongo_expr": {
                "$let": {
                    "vars": {"d": _opdate_date_expr()},
                    "in": {
                        "$cond": [
                            {"$eq": ["$$d", None]},
                            None,
                            {"$year": "$$d"},
                        ]
                    },
                }
            }
        },

        "month": {
            "mongo_expr": {
                "$let": {
                    "vars": {"d": _opdate_date_expr()},
                    "in": {
                        "$cond": [
                            {"$eq": ["$$d", None]},
                            None,
                            {"$month": "$$d"},
                        ]
                    },
                }
            }
        },

        "day": {
            "mongo_expr": {
                "$let": {
                    "vars": {"d": _opdate_date_expr()},
                    "in": {
                        "$cond": [
                            {"$eq": ["$$d", None]},
                            None,
                            {"$dayOfMonth": "$$d"},
                        ]
                    },
                }
            }
        },

        "season": {
            "mongo_expr": {
                "$let": {
                    "vars": {"d": _opdate_date_expr()},
                    "in": {
                        "$cond": [
                            {"$eq": ["$$d", None]},
                            None,
                            {
                                "$switch": {
                                    "branches": [
                                        {"case": {"$in": [{"$month": "$$d"}, [12, 1, 2]]}, "then": "kis"},
                                        {"case": {"$in": [{"$month": "$$d"}, [3, 4, 5]]}, "then": "ilkbahar"},
                                        {"case": {"$in": [{"$month": "$$d"}, [6, 7, 8]]}, "then": "yaz"},
                                        {"case": {"$in": [{"$month": "$$d"}, [9, 10, 11]]}, "then": "sonbahar"},
                                    ],
                                    "default": None,
                                }
                            },
                        ]
                    },
                }
            }
        },
        # Haftanın günü (Pazartesi, Salı, ...)
        "dayOfWeek": {
            "mongo_expr": {
                "$let": {
                    "vars": {"d": _opdate_date_expr()},
                    "in": {
                        "$cond": [
                            {"$eq": ["$$d", None]},
                            None,
                            {
                                "$switch": {
                                    "branches": [
                                        {"case": {"$eq": [{"$dayOfWeek": "$$d"}, 2]}, "then": "Pazartesi"},
                                        {"case": {"$eq": [{"$dayOfWeek": "$$d"}, 3]}, "then": "Sali"},
                                        {"case": {"$eq": [{"$dayOfWeek": "$$d"}, 4]}, "then": "Carsamba"},
                                        {"case": {"$eq": [{"$dayOfWeek": "$$d"}, 5]}, "then": "Persembe"},
                                        {"case": {"$eq": [{"$dayOfWeek": "$$d"}, 6]}, "then": "Cuma"},
                                        {"case": {"$eq": [{"$dayOfWeek": "$$d"}, 7]}, "then": "Cumartesi"},
                                        {"case": {"$eq": [{"$dayOfWeek": "$$d"}, 1]}, "then": "Pazar"},
                                    ],
                                    "default": None,
                                }
                            },
                        ]
                    },
                }
            }
        },
    },
    "metrics": {
        "count": {"type": "count"},

        "sum_cost": {
            "type": "sum",
            "mongo_path": "result.extensions.https://promptever.com/extensions/materialCost",
            "mongo_expr": _result_ext_expr("https://promptever.com/extensions/materialCost"),
        },

        "avg_km": {
            "type": "avg",
            "mongo_path": "result.extensions.https://promptever.com/extensions/odometerReading",
            "mongo_expr": _result_ext_expr("https://promptever.com/extensions/odometerReading"),
        },
    },
}


# ======================================================================
# Normalize Fonksiyonları
# ======================================================================

def normalize_model(text: str | None) -> str:
    return normalize_tr(text)


# ======================================================================
# Nested Access Helpers
# ======================================================================

def _get_nested(doc: Dict[str, Any], path: str, default: Any = None) -> Any:
    parts = path.split(".")
    current: Any = doc
    for p in parts:
        if not isinstance(current, dict):
            return default
        current = current.get(p)
        if current is None:
            return default
    return current


def _get_attr(obj: Any, name: str, default=None):
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


# ======================================================================
# TimeRange → Mongo Filter
# ======================================================================

def _build_time_filter(time_range: Optional[TimeRange]) -> Dict[str, Any]:
    """
    TimeRange → Mongo filter dict.

    - datetime (start_date/end_date) veya string (start/end) destekler
    - operationDate için hem root hem statement.context path'lerini kapsar
    - string kıyas yerine $convert ile Date kıyas yapar (kritik)
    - end sınırı EXCLUSIVE: $lt
    
    ⚠️ NOT: URL formatındaki extension key'leri için $getField kullanılıyor.
    """
    if not time_range:
        return {}

    op_key = "https://promptever.com/extensions/operationDate"
    
    start_val = time_range.start_date if getattr(time_range, "start_date", None) else getattr(time_range, "start", None)
    end_val = time_range.end_date if getattr(time_range, "end_date", None) else getattr(time_range, "end", None)

    if start_val is None and end_val is None:
        return {}

    def _build_opdate_expr():
        """operationDate için $getField tabanlı güvenli expression."""
        return {
            "$ifNull": [
                {"$getField": {"field": op_key, "input": "$context.extensions"}},
                {
                    "$ifNull": [
                        {"$getField": {"field": op_key, "input": "$statement.context.extensions"}},
                        {
                            "$ifNull": [
                                {"$getField": {"field": "operationDate", "input": "$context.extensions"}},
                                {"$getField": {"field": "operationDate", "input": "$statement.context.extensions"}},
                            ]
                        },
                    ]
                },
            ]
        }

    def _build_timestamp_expr():
        """timestamp için expression."""
        return {"$ifNull": ["$timestamp", "$statement.timestamp"]}

    # field seçimi
    field_name = getattr(time_range, "field", None) or "operationDate"
    raw_expr = _build_opdate_expr() if field_name == "operationDate" else _build_timestamp_expr()
    
    # Date'e convert
    field_date = {
        "$convert": {
            "input": raw_expr,
            "to": "date",
            "onError": None,
            "onNull": None,
        }
    }

    clauses = [
        {"$ne": [raw_expr, None]},
        {"$ne": [raw_expr, ""]},
        {"$ne": [field_date, None]},
    ]

    if start_val is not None:
        start_expr = {"$toDate": start_val} if isinstance(start_val, str) else start_val
        clauses.append({"$gte": [field_date, start_expr]})

    if end_val is not None:
        end_expr = {"$toDate": end_val} if isinstance(end_val, str) else end_val
        clauses.append({"$lt": [field_date, end_expr]})  # EXCLUSIVE end

    return {"$expr": {"$and": clauses}}


# ======================================================================
# Context Helpers
# ======================================================================

def _get_context(doc: Dict[str, Any]) -> Dict[str, Any]:
    ctx = doc.get("context")
    if isinstance(ctx, dict):
        return ctx

    stmt = doc.get("statement")
    if isinstance(stmt, dict):
        ctx2 = stmt.get("context")
        if isinstance(ctx2, dict):
            return ctx2

    return {}


def _extract_vehicle_id_from_actor(doc: Dict[str, Any]) -> Optional[str]:
    actor = doc.get("actor") or {}
    acc = actor.get("account") or {}
    name = acc.get("name")

    if not isinstance(name, str):
        stmt = doc.get("statement") or {}
        if isinstance(stmt, dict):
            actor2 = stmt.get("actor") or {}
            acc2 = actor2.get("account") or {}
            name = acc2.get("name")

    ctx = _get_context(doc)
    exts = ctx.get("extensions") or {}
    if not isinstance(name, str) and isinstance(exts, dict):
        for key in [
            "https://promptever.com/extensions/vehicleId",
            "https://promptever.com/extensions/vehicleNo",
            "https://promptever.com/extensions/plate",
            "https://promptever.com/extensions/licensePlate",
        ]:
            val = exts.get(key)
            if isinstance(val, str) and val.strip():
                name = val.strip()
                break

    if not isinstance(name, str):
        return None

    if name.startswith("vehicle/"):
        return name.split("/", 1)[1]

    return name


def _extract_operation_date(doc: Dict[str, Any]) -> Optional[datetime]:
    """
    Dokümandan operationDate çıkarır.
    
    Öncelik sırası:
    1. context.extensions.operationDate
    2. statement.context.extensions.operationDate
    3. timestamp (fallback - operationDate yoksa)
    4. stored (son fallback)
    """
    # 1) root context.extensions
    exts_root = (doc.get("context") or {}).get("extensions") or {}
    raw = None
    if isinstance(exts_root, dict):
        raw = (
            exts_root.get("https://promptever.com/extensions/operationDate")
            or exts_root.get("operationDate")
        )

    # 2) statement.context.extensions fallback
    if not raw:
        exts_stmt = _get_nested(doc, "statement.context.extensions", default={})
        if isinstance(exts_stmt, dict):
            raw = (
                exts_stmt.get("https://promptever.com/extensions/operationDate")
                or exts_stmt.get("operationDate")
            )

    # 3) timestamp fallback (operationDate yoksa)
    if not raw:
        raw = doc.get("timestamp") or _get_nested(doc, "statement.timestamp")
    
    # 4) stored fallback (son çare)
    if not raw:
        raw = doc.get("stored") or _get_nested(doc, "statement.stored")

    if not raw:
        return None

    if isinstance(raw, datetime):
        return raw

    if isinstance(raw, str):
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except Exception:
            return None

    return None


def _extract_service_code_from_context(doc: Dict[str, Any]) -> Optional[str]:
    ctx = _get_context(doc)
    ca = ctx.get("contextActivities") or {}
    grouping = ca.get("grouping") or []
    if not isinstance(grouping, list):
        return None

    for g in grouping:
        if not isinstance(g, dict):
            continue
        gid = g.get("id")
        if isinstance(gid, str) and "/activities/service-location/" in gid:
            return gid.rsplit("/", 1)[-1]

    return None


def _extract_customer_id_from_context(doc: Dict[str, Any]) -> Optional[str]:
    ctx = _get_context(doc)
    ca = ctx.get("contextActivities") or {}
    grouping = ca.get("grouping") or []
    if not isinstance(grouping, list):
        return None

    for g in grouping:
        if not isinstance(g, dict):
            continue
        gid = g.get("id")
        if isinstance(gid, str) and "/activities/customer/" in gid:
            return gid.rsplit("/", 1)[-1]

    return None