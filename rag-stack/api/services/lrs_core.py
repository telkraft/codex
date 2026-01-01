"""
LRS Core
========

LRSQueryService çekirdeği:
- MongoDB'deki statements koleksiyonuna bağlanır
- Schema-aware QueryPlan tabanlı istatistiksel sorgular çalıştırır

🆕 EKLENEN: get_anchor_date() ve get_date_range() metodları
   Rölatif dönem sorguları için LRS'deki tarih aralığını döndürür.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from typing import Any, Dict, List, Optional

from config import lrs_statements
from models import QueryPlan

from services.lrs_schema import MAN_SCHEMA, normalize_tr, _build_time_filter
from services.xapi_nlp.nlp_constants import MONTH_KEYWORDS


class LRSCore:
    """
    Temel LRS çekirdeği.

    - self.statements  → Mongo koleksiyonu
    - _build_mongo_filter / _build_group_stage → QueryPlan'den pipeline üretimi
    - run_query        → aggregate pipeline çalıştırma
    - get_general_statistics → genel LRS istatistikleri
    - get_anchor_date  → 🆕 rölatif sorgular için referans tarih
    - get_date_range   → 🆕 LRS'deki min/max tarih aralığı
    """

    def __init__(self, collection=None):
        # Varsayılan olarak config.lrs_statements kullanılır
        self.statements = collection or lrs_statements

    # ---------- Schema-aware QueryPlan desteği ----------

    def _build_mongo_filter(self, plan: QueryPlan) -> Dict[str, Any]:
        """
        QueryPlan.filters içindeki schema-aware anahtarları
        Mongo filter dict'ine çevirir.

        Desteklenen filtreler (MVP):
        - materialName_contains: object.definition.name.tr-TR regex (normalize + case-insensitive)
        - hasFault            : True → faultCode not null
        - vehicleType_eq      : eşitlik filtresi (schema'dan path)
        - vehicleModel_eq     : eşitlik filtresi (schema'dan path)
        - vehicleId_eq        : 🆕 araç ID filtresi (plaka/numara)
        - season_eq           : mevsim filtresi
        - month_eq            : ay filtresi
        - time_range          : zaman filtresi (operationDate üzerinden)
        """
        f: Dict[str, Any] = {}

        filters = plan.filters or {}

        # 1) Malzeme adı filtreleri (normalize edilmiş sorgu)
        material_sub = filters.get("materialName_contains")
        if isinstance(material_sub, str) and material_sub.strip():
            normalized = normalize_tr(material_sub)
            if normalized:
                # Hem root object, hem de statement.object için fallback
                f["$or"] = [
                    {
                        "object.definition.name.tr-TR": {
                            "$regex": normalized,
                            "$options": "i",
                        }
                    },
                    {
                        "statement.object.definition.name.tr-TR": {
                            "$regex": normalized,
                            "$options": "i",
                        }
                    },
                ]

        # 2) Fault var mı?
        # ⚠️ FIX: URL formatındaki extension key'leri için $getField kullanılmalı.
        #    Eski yöntem (mongo_path + $exists) MongoDB dot notation sorunu yaratıyordu.
        has_fault = filters.get("hasFault")
        if has_fault:
            fault_dim = MAN_SCHEMA["dimensions"].get("faultCode")
            if fault_dim and "mongo_expr" in fault_dim:
                # ✅ $expr + mongo_expr ile URL key'lerine güvenli erişim
                fault_expr = fault_dim["mongo_expr"]
                fault_check = {
                    "$and": [
                        {"$ne": [fault_expr, None]},
                        {"$ne": [fault_expr, ""]},
                        {"$ne": [fault_expr, "0"]},      # "0" string de boş sayılsın
                        {"$ne": [fault_expr, "None"]},   # 🆕 "None" string de boş sayılsın
                        {"$ne": [fault_expr, "none"]},   # 🆕 küçük harfli versiyon
                        {"$ne": [fault_expr, "NULL"]},   # 🆕 büyük harfli NULL
                        {"$ne": [fault_expr, "null"]},   # 🆕 küçük harfli null
                    ]
                }
                if "$expr" in f:
                    f["$expr"] = {"$and": [f["$expr"], fault_check]}
                else:
                    f["$expr"] = fault_check
            else:
                # Fallback: Eski yöntem (mongo_expr yoksa)
                fault_path = (
                    fault_dim["mongo_path"]
                    if fault_dim and "mongo_path" in fault_dim
                    else "result.extensions.https://promptever.com/extensions/faultCode"
                )
                f[fault_path] = {
                    "$exists": True,
                    "$ne": None,
                }

        # 3) Araç tipi eşitlik filtresi (normalize edilmiş sorgu)
        # ⚠️ FIX: URL formatındaki extension key'leri için $getField kullanılmalı.
        vt_eq = filters.get("vehicleType_eq")
        if isinstance(vt_eq, str) and vt_eq.strip():
            dim_conf = MAN_SCHEMA["dimensions"].get("vehicleType")
            normalized_vt = normalize_tr(vt_eq)
            if dim_conf and "mongo_expr" in dim_conf:
                # ✅ $expr + mongo_expr ile URL key'lerine güvenli erişim
                vt_expr = dim_conf["mongo_expr"]
                vt_check = {"$eq": [vt_expr, normalized_vt]}
                if "$expr" in f:
                    f["$expr"] = {"$and": [f["$expr"], vt_check]}
                else:
                    f["$expr"] = vt_check
            elif dim_conf and "mongo_path" in dim_conf:
                # Fallback: Eski yöntem (URL içermeyen path'ler için)
                path = dim_conf["mongo_path"]
                f[path] = normalized_vt

        # 4) Araç modeli eşitlik filtresi (normalize edilmiş sorgu)
        # ⚠️ FIX: URL formatındaki extension key'leri için $getField kullanılmalı.
        vm_eq = filters.get("vehicleModel_eq")
        if isinstance(vm_eq, str) and vm_eq.strip():
            dim_conf = MAN_SCHEMA["dimensions"].get("vehicleModel")
            normalized_vm = normalize_tr(vm_eq)
            if dim_conf and "mongo_expr" in dim_conf:
                # ✅ $expr + mongo_expr ile URL key'lerine güvenli erişim
                vm_expr = dim_conf["mongo_expr"]
                vm_check = {"$eq": [vm_expr, normalized_vm]}
                if "$expr" in f:
                    f["$expr"] = {"$and": [f["$expr"], vm_check]}
                else:
                    f["$expr"] = vm_check
            elif dim_conf and "mongo_path" in dim_conf:
                # Fallback: Eski yöntem (URL içermeyen path'ler için)
                path = dim_conf["mongo_path"]
                f[path] = normalized_vm

        # ═══════════════════════════════════════════════════════════════════════
        # 🆕 5) Araç ID filtresi (vehicleId_eq)
        # ═══════════════════════════════════════════════════════════════════════
        vehicle_id = filters.get("vehicleId_eq")
        if isinstance(vehicle_id, str) and vehicle_id.strip():
            vid = vehicle_id.strip()

            # Ana iki muhtemel actor path
            paths = [
                "actor.account.name",
                "statement.actor.account.name",
            ]

            # Schema'da "vehicle" dimension mongo_path'i varsa onu da ekle
            vehicle_dim = MAN_SCHEMA["dimensions"].get("vehicle", {})
            schema_path = vehicle_dim.get("mongo_path")
            if isinstance(schema_path, str) and schema_path not in paths:
                paths.insert(0, schema_path)

            # vehicleId/plate vs. extension olasılıkları
            ext_paths = [
                "context.extensions.https://promptever.com/extensions/vehicleId",
                "context.extensions.https://promptever.com/extensions/vehicleNo",
                "context.extensions.https://promptever.com/extensions/plate",
                "context.extensions.https://promptever.com/extensions/licensePlate",
                "statement.context.extensions.https://promptever.com/extensions/vehicleId",
                "statement.context.extensions.https://promptever.com/extensions/vehicleNo",
                "statement.context.extensions.https://promptever.com/extensions/plate",
                "statement.context.extensions.https://promptever.com/extensions/licensePlate",
            ]

            # Regex: "70886" veya ".../70886" ile biteni yakala
            regex = {"$regex": f"(^|/)({vid})$", "$options": "i"}
            ors = [{p: regex} for p in paths] + [{p: vid} for p in ext_paths]
            vehicle_filter = {"$or": ors}

            # Mevcut $or (malzeme adı vs.) varsa AND ile bağla
            if "$or" in f:
                existing_or = f.pop("$or")
                f["$and"] = [
                    {"$or": existing_or},
                    vehicle_filter,
                ]
            else:
                if f:
                    f = {"$and": [f, vehicle_filter]}
                else:
                    f.update(vehicle_filter)

        # ═══════════════════════════════════════════════════════════════════════
        # operationDate'i root veya statement.* üzerinden oku (dual-source)
        # ═══════════════════════════════════════════════════════════════════════
        operation_date_raw = {
            "$ifNull": [
                {
                    "$getField": {
                        "field": "https://promptever.com/extensions/operationDate",
                        "input": "$context.extensions",
                    }
                },
                {
                    "$getField": {
                        "field": "https://promptever.com/extensions/operationDate",
                        "input": "$statement.context.extensions",
                    }
                },
            ]
        }

        operation_date_expr = {
            "$cond": {
                "if": {
                    "$or": [
                        {"$eq": [operation_date_raw, None]},
                        {"$eq": [operation_date_raw, ""]},
                    ]
                },
                "then": None,
                "else": {"$toDate": operation_date_raw},
            }
        }

        # 6) Mevsim filtresi (season_eq: winter/spring/summer/autumn)
        season_eq = filters.get("season_eq")
        if isinstance(season_eq, str) and season_eq.strip():
            season = season_eq.lower()

            if season in ("winter", "spring", "summer", "autumn", "fall"):
                if season == "winter":
                    months = [12, 1, 2]
                elif season == "spring":
                    months = [3, 4, 5]
                elif season == "summer":
                    months = [6, 7, 8]
                else:  # autumn / fall
                    months = [9, 10, 11]
            else:
                months = None

            if months:
                season_expr = {
                    "$and": [
                        {"$ne": [operation_date_expr, None]},
                        {"$in": [{"$month": operation_date_expr}, months]},
                    ]
                }

                if "$expr" in f:
                    f["$expr"] = {"$and": [f["$expr"], season_expr]}
                else:
                    f["$expr"] = season_expr

        # 🆕 6b) Ay filtresi (month_eq: 1-12 veya "eylul" gibi)
        month_eq = filters.get("month_eq")
        month_num: Optional[int] = None

        if isinstance(month_eq, int) and 1 <= month_eq <= 12:
            month_num = month_eq
        elif isinstance(month_eq, str) and month_eq.strip():
            m = normalize_tr(month_eq).strip()
            month_num = MONTH_KEYWORDS.get(m)

        if month_num:
            month_expr = {
                "$and": [
                    {"$ne": [operation_date_expr, None]},
                    {"$eq": [{"$month": operation_date_expr}, month_num]},
                ]
            }

            if "$expr" in f:
                f["$expr"] = {"$and": [f["$expr"], month_expr]}
            else:
                f["$expr"] = month_expr

        # ═══════════════════════════════════════════════════════════════════════
        # 🆕 Tarih bazlı grouping varsa operationDate null kayıtları ele
        # (time_range olsa da olmasa da; year/month/season group key bozulmasın)
        # ═══════════════════════════════════════════════════════════════════════
        if any(dim in ("year", "month", "season") for dim in (plan.group_by or [])):
            od_exists_expr = {"$ne": [operation_date_expr, None]}
            if "$expr" in f:
                f["$expr"] = {"$and": [f["$expr"], od_exists_expr]}
            else:
                f["$expr"] = od_exists_expr

        # 7) Zaman filtresi
        time_filter = _build_time_filter(plan.time_range)
        if time_filter:
            if f:
                f = {"$and": [f, time_filter]}
            else:
                f = time_filter

        return f

    def _build_group_stage(self, plan: QueryPlan) -> Dict[str, Any]:
        """
        QueryPlan.group_by ve QueryPlan.metrics üzerinden $group aşamasını kurar.
        - dimensions için hem mongo_path hem mongo_expr desteklenir.
        """
        group_id: Dict[str, Any] = {}

        for dim in plan.group_by:
            dim_conf = MAN_SCHEMA["dimensions"].get(dim)
            if not dim_conf:
                continue

            # Önce mongo_expr varsa onu kullan (ör: verbType)
            mongo_expr = dim_conf.get("mongo_expr")
            if mongo_expr is not None:
                group_id[dim] = mongo_expr
            else:
                # Aksi halde klasik mongo_path → "$path"
                mpath = dim_conf.get("mongo_path")
                if not mpath:
                    continue
                group_id[dim] = f"${mpath}"

        if not group_id:
            # Hiç dimension yoksa tek bir grupla global aggregate
            group_id = None  # Mongo'da "_id": None

        group_stage: Dict[str, Any] = {"_id": group_id}

        # Metrikler
        for metric in plan.metrics:
            metric_conf = MAN_SCHEMA["metrics"].get(metric)
            if not metric_conf:
                continue

            mtype = metric_conf["type"]

            if mtype == "count":
                group_stage[metric] = {"$sum": 1}
                continue

            # Önce mongo_expr varsa onu kullan (extension alanları için)
            mongo_expr = metric_conf.get("mongo_expr")
            if mongo_expr is not None:
                if mtype == "sum":
                    group_stage[metric] = {"$sum": mongo_expr}
                elif mtype == "avg":
                    group_stage[metric] = {"$avg": mongo_expr}
                continue

            # Geriye dönük: sadece mongo_path varsa
            mpath = metric_conf.get("mongo_path")
            if not mpath:
                continue

            if mtype == "sum":
                group_stage[metric] = {"$sum": f"${mpath}"}
            elif mtype == "avg":
                group_stage[metric] = {"$avg": f"${mpath}"}
        # Güvenlik için, count metrik yoksa yine de ekleyelim
        if "count" not in group_stage:
            group_stage["count"] = {"$sum": 1}

        return group_stage

    def _is_empty_fault_code(self, v: Any) -> bool:
        if v is None:
            return True
        if isinstance(v, str):
            s = v.strip().lower()
            return s in ("", "0", "none", "null")
        return False

    def run_query(
        self,
        plan: QueryPlan,
        limit: int = 100,
    ) -> Dict[str, Any]:
        """
        QueryPlan → Mongo aggregate → satırlar.

        Dönen yapı:
          {
            "plan": {...},
            "pipeline": [...],
            "rows": [
              {
                "vehicleType": "...",
                "faultCode": "...",
                "count": 10,
                "sum_cost": 12345.0,
                "avg_km": 85000.0,
              },
              ...
            ],
          }
        """
        mongo_filter = self._build_mongo_filter(plan)
        group_stage = self._build_group_stage(plan)

        pipeline: List[Dict[str, Any]] = [
            {"$match": mongo_filter},
            {"$group": group_stage},
            {"$sort": {"count": -1}},
            {"$limit": limit},
        ]

        cursor = self.statements.aggregate(pipeline)

        rows: List[Dict[str, Any]] = []
        for doc in cursor:
            row: Dict[str, Any] = {}
            _id = doc.get("_id", {}) or {}

            # group_by dimension'larını satıra aç
            if isinstance(_id, dict):
                for dim in plan.group_by:
                    val = _id.get(dim)
                    # 🆕 Vehicle değerlerinden "vehicle/" prefix'ini kaldır
                    if dim == "vehicle" and isinstance(val, str) and val.startswith("vehicle/"):
                        val = val.split("/", 1)[1]
                    row[dim] = val
            else:
                # _id None veya primitif olabilir; pek kullanmayacağız ama dursun
                row["_id"] = _id

            # ✅ faultCode group_by varsa, boş/None olan satırları hiç ekleme
            if plan.group_by and "faultCode" in plan.group_by:
                if self._is_empty_fault_code(row.get("faultCode")):
                    continue

            # metrik alanlarını ekle
            for metric in plan.metrics:
                if metric in doc:
                    row[metric] = doc[metric]
            # count her durumda olsun
            if "count" in doc:
                row["count"] = doc["count"]

            rows.append(row)

        return {
            "plan": asdict(plan),
            "pipeline": pipeline,
            "rows": rows,
        }

    def get_general_statistics(self) -> Dict[str, Any]:
        """
        LRS genel istatistikleri:

        - totalStatements      : Toplam xAPI kaydı
        - uniqueVehicles       : Farklı araç sayısı (actor.account.name'den)
        - statementsWithFaults : Arıza kodu içeren kayıt sayısı
        - faultCodeRatio       : Arızalı kayıt oranı (%)

        NOT:
        FaultCode'u Mongo'da doğrudan path ile filtrelemek yerine
        dokümanları okuyup result.extensions içindeki key'lere bakıyoruz.
        Çünkü extension key'lerinde IRI / encoding farkları olabilir.
        """

        # 1) Toplam statement sayısı
        total_statements = int(self.statements.count_documents({}))

        # 2) Farklı araç sayısı (actor.account.name)
        try:
            # Hem root, hem statement.* olması ihtimaline karşı iki taraftan deneyelim
            names_root = self.statements.distinct("actor.account.name")
            names_nested = self.statements.distinct("statement.actor.account.name")
            all_names = set()
            for name in list(names_root) + list(names_nested):
                if not isinstance(name, str):
                    continue
                s = name.strip()
                if not s:
                    continue
                if s.startswith("vehicle/"):
                    s = s.split("/", 1)[1]
                all_names.add(s)
            unique_vehicles = len(all_names)
        except Exception:
            unique_vehicles = 0

        # 3) Arıza kodu olan kayıt sayısı
        statements_with_faults = 0

        cursor = self.statements.find(
            {},
            {
                "result.extensions": 1,
                "statement.result.extensions": 1,
            },
        )

        for doc in cursor:
            # Hem root hem statement.* yapısını ele al
            ext = None

            res = doc.get("result") or {}
            if isinstance(res, dict):
                ext = res.get("extensions")

            if not isinstance(ext, dict):
                stmt = doc.get("statement") or {}
                if isinstance(stmt, dict):
                    res2 = stmt.get("result") or {}
                    if isinstance(res2, dict):
                        ext = res2.get("extensions")

            if not isinstance(ext, dict):
                continue

            has_fault = False
            for k, v in ext.items():
                # Key içinde "faultCode" geçiyorsa ve değer doluysa arızalı say
                if not isinstance(k, str):
                    continue
                if "faultcode" in k.lower():
                    if v not in (None, "", 0, "0"):
                        has_fault = True
                        break

            if has_fault:
                statements_with_faults += 1

        # 4) Arıza oranı (%)
        if total_statements > 0:
            fault_ratio = (statements_with_faults / total_statements) * 100.0
        else:
            fault_ratio = 0.0

        return {
            "totalStatements": total_statements,
            "uniqueVehicles": int(unique_vehicles),
            "statementsWithFaults": int(statements_with_faults),
            "faultCodeRatio": float(fault_ratio),
        }

    # ═══════════════════════════════════════════════════════════════════════
    # 🆕 ANCHOR DATE: Rölatif dönem sorguları için LRS referans tarihi
    # ═══════════════════════════════════════════════════════════════════════
    def get_anchor_date(self) -> Optional[datetime]:
        """
        Anchor = LRS'deki en son operationDate.
        
        ⚠️ NOT: URL formatındaki extension key'leri (https://...) içinde nokta var.
        MongoDB dot notation bu noktaları yanlış parse eder.
        Bu yüzden $getField operatörü kullanılmalı.
        """
        try:
            # $getField ile URL key'ine güvenli erişim
            op_key = "https://promptever.com/extensions/operationDate"
            
            pipeline = [
                {
                    "$addFields": {
                        "__op_raw": {
                            "$ifNull": [
                                {"$getField": {"field": op_key, "input": "$context.extensions"}},
                                {"$getField": {"field": op_key, "input": "$statement.context.extensions"}},
                            ]
                        }
                    }
                },
                {"$match": {"__op_raw": {"$ne": None, "$ne": ""}}},
                {"$group": {"_id": None, "max_date": {"$max": {"$toDate": "$__op_raw"}}}},
            ]

            result = list(self.statements.aggregate(pipeline))
            return result[0]["max_date"] if result and result[0].get("max_date") else None

        except Exception as e:
            print(f"[LRSCore] get_anchor_date hatası: {e}")
            return None


    def get_date_range(self) -> Optional[Dict[str, datetime]]:
        """
        LRS min/max = operationDate min/max
        
        ⚠️ NOT: URL formatındaki extension key'leri için $getField kullanılıyor.
        """
        try:
            op_key = "https://promptever.com/extensions/operationDate"
            
            pipeline = [
                {
                    "$addFields": {
                        "__op_raw": {
                            "$ifNull": [
                                {"$getField": {"field": op_key, "input": "$context.extensions"}},
                                {"$getField": {"field": op_key, "input": "$statement.context.extensions"}},
                            ]
                        }
                    }
                },
                {"$match": {"__op_raw": {"$ne": None, "$ne": ""}}},
                {"$group": {
                    "_id": None,
                    "min_date": {"$min": {"$toDate": "$__op_raw"}},
                    "max_date": {"$max": {"$toDate": "$__op_raw"}},
                }},
            ]

            result = list(self.statements.aggregate(pipeline))
            if not result:
                return None
            return {"min_date": result[0].get("min_date"), "max_date": result[0].get("max_date")}

        except Exception as e:
            print(f"[LRSCore] get_date_range hatası: {e}")
            return None