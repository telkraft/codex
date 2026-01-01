"""
LRS Domain Patterns
===================

"En çok gelen ..." istatistikleri, malzeme fiyat trendleri ve
"bir sonraki bakımda değişen malzemeler" gibi domain odaklı analizler
için mixin.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional


def _to_naive(dt: datetime) -> datetime:
    """
    Aware datetime (tzinfo'lu) gelirse tz bilgisini atıp naive'e çevirir.
    Zaten naive ise aynen döner.
    """
    if not isinstance(dt, datetime):
        return dt
    if dt.tzinfo is None:
        return dt
    return dt.replace(tzinfo=None)


from models import TopEntitiesQuestion

from services.lrs_schema import (
    normalize_tr,
    normalize_model,
    _get_context,
    _get_nested,
    _extract_operation_date,
    _extract_service_code_from_context,  # ← BUNU EKLE
)

class LRSPatternsMixin:
    """
    LRSCore + LRSExamplesMixin ile birlikte kullanıldığında:

    - self.statements                : Mongo koleksiyonu (LRSCore'dan)
    - self._doc_matches_period(...)  : dönem filtresi (LRSExamplesMixin'den)
    - self._doc_matches_service_filter(...) : servis filtresi (LRSExamplesMixin'den)
    - self._compute_latest_business_date()  : anchor tarih (LRSExamplesMixin'den)

    Bu mixin:
    - top_entities_overall
    - answer_top_entities_question
    - material_price_trend
    - material_family_price_trend
    - next_maintenance_materials
    gibi domain fonksiyonlarını sağlar.
    """

    def material_usage_pivot(self, period: Optional[dict] = None, limit: int = 200) -> Dict[str, Any]:
        """
        Yıllara ve mevsimlere (veya ay bazında) göre malzeme kullanım pivotu.

        Eğer period.kind == "month" ise:
        - year + month + materialName bazında sayım yapar.
        Aksi hâlde:
        - year + season + materialName bazında sayım yapar.
        """

        # period dict'inden kind'i çekelim (None da olabilir)
        kind = (period or {}).get("kind")
        group_by_month = (kind == "month")

        # Ay modunda: (year, month, material)
        # Mevsim modunda: (year, season, material)
        counter: Counter = Counter()

        mongo_query: Dict[str, Any] = {
            "$or": [
                {"verb.id": {"$regex": "/verbs/(maintained|repaired)$"}},
                {"statement.verb.id": {"$regex": "/verbs/(maintained|repaired)$"}},
            ]
        }

        cursor = self.statements.find(
            mongo_query,
            {
                "context": 1,
                "statement.context": 1,
                "object": 1,
                "statement.object": 1,
                "result": 1,
                "statement.result": 1,
                "timestamp": 1,
                "stored": 1,
                "verb": 1,
                "statement.verb": 1,
            },
        )

        for doc in cursor:
            # Dönem filtresi (son X yıl, kış 2020 vb.) varsa uygula
            if not self._doc_matches_period(doc, period):
                continue

            op_date = _extract_operation_date(doc)
            if not isinstance(op_date, datetime):
                continue

            year = op_date.year
            month = op_date.month

            pivot_year = year  # ← KRİTİK: ayrı değişken

            if group_by_month:
                second_dim = month  # 1–12
            else:
                if month in (12, 1, 2):
                    second_dim = "kis"
                    # Aralık ayını bir sonraki yılın kışı olarak say
                    if month == 12:
                        pivot_year = year + 1
                elif month in (3, 4, 5):
                    second_dim = "ilkbahar"
                elif month in (6, 7, 8):
                    second_dim = "yaz"
                else:
                    second_dim = "sonbahar"

            mat_name = (
                _get_nested(doc, "object.definition.name.tr-TR")
                or _get_nested(doc, "statement.object.definition.name.tr-TR")
            )
            if not isinstance(mat_name, str) or not mat_name.strip():
                continue

            key = (pivot_year, second_dim, mat_name.strip())
            counter[key] += 1


        # Sayaçtan tablo satırlarını üret
        rows: List[Dict[str, Any]] = []
        for (year, second_dim, mat_name), cnt in sorted(
            counter.items(),
            key=lambda kv: kv[1],
            reverse=True,
        ):
            if group_by_month:
                row = {
                    "year": year,
                    "month": second_dim,      # 1–12
                    "materialName": mat_name,
                    "count": cnt,
                }
            else:
                row = {
                    "year": year,
                    "season": second_dim,     # kis / ilkbahar / yaz / sonbahar
                    "materialName": mat_name,
                    "count": cnt,
                }

            rows.append(row)
            if limit and len(rows) >= limit:
                break

        return {
            "scenario": "material_usage_pivot",
            "period": period,
            "rows": rows,
        }

    def material_usage_top_per_year_season(
        self,
        period: Optional[dict] = None,
        limit_per_group: int = 5,
        limit: int = 200,
    ) -> Dict[str, Any]:
        """
        Yıllara ve mevsimlere göre en çok kullanılan malzemeler.
        
        Her (yıl, mevsim) kombinasyonu için ayrı ayrı top N malzeme döndürür.
        
        Args:
            period: Dönem filtresi (son N yıl, son N ay vb.)
                    Örnek: {"kind": "last_n_years", "years": 2}
            limit_per_group: Her (yıl, mevsim) için kaç malzeme (varsayılan: 5)
            limit: Toplam maksimum satır sayısı (varsayılan: 200)
            
        Returns:
            {
                "scenario": "material_usage_top_per_year_season",
                "period": {...},
                "limit_per_group": 5,
                "rows": [
                    {"year": 2024, "season": "kis", "materialName": "X", "count": 100, "rank": 1},
                    ...
                ]
            }
            
        Örnek Kullanım:
            # Son 2 yılda mevsimlere göre top 10 malzeme
            result = lrs.material_usage_top_per_year_season(
                period={"kind": "last_n_years", "years": 2},
                limit_per_group=10
            )
        """
        from collections import defaultdict
        
        # Veri toplama: (year, season) -> {materialName: count}
        group_data: Dict[tuple, Counter] = defaultdict(Counter)
        
        mongo_query: Dict[str, Any] = {
            "$or": [
                {"verb.id": {"$regex": "/verbs/(maintained|repaired)$"}},
                {"statement.verb.id": {"$regex": "/verbs/(maintained|repaired)$"}},
            ]
        }
        
        cursor = self.statements.find(
            mongo_query,
            {
                "context": 1,
                "statement.context": 1,
                "object": 1,
                "statement.object": 1,
                "result": 1,
                "statement.result": 1,
                "timestamp": 1,
                "stored": 1,
                "verb": 1,
                "statement.verb": 1,
            },
        )
        
        for doc in cursor:
            # Dönem filtresi uygula
            if not self._doc_matches_period(doc, period):
                continue
            
            op_date = _extract_operation_date(doc)
            if not isinstance(op_date, datetime):
                continue
            
            year = op_date.year
            month = op_date.month
            
            # Mevsim ve pivot_year hesapla
            pivot_year = year
            if month in (12, 1, 2):
                season = "kis"
                # Aralık ayını bir sonraki yılın kışı olarak say
                if month == 12:
                    pivot_year = year + 1
            elif month in (3, 4, 5):
                season = "ilkbahar"
            elif month in (6, 7, 8):
                season = "yaz"
            else:
                season = "sonbahar"
            
            # Malzeme adını çıkar
            mat_name = (
                _get_nested(doc, "object.definition.name.tr-TR")
                or _get_nested(doc, "statement.object.definition.name.tr-TR")
            )
            if not isinstance(mat_name, str) or not mat_name.strip():
                continue
            
            # Gruba ekle
            group_key = (pivot_year, season)
            group_data[group_key][mat_name.strip()] += 1
        
        # Her grup için top N malzemeyi hesapla
        rows: List[Dict[str, Any]] = []
        
        # Mevsim sıralama düzeni
        season_order = {"kis": 0, "ilkbahar": 1, "yaz": 2, "sonbahar": 3}
        
        # Grupları sırala: yıl (desc) -> mevsim (doğal sıra)
        sorted_groups = sorted(
            group_data.keys(),
            key=lambda g: (-g[0], season_order.get(g[1], 99))
        )
        
        for group_key in sorted_groups:
            year, season = group_key
            counter = group_data[group_key]
            
            # Bu grup için en çok kullanılan malzemeleri al
            top_materials = counter.most_common(limit_per_group)
            
            for rank, (mat_name, count) in enumerate(top_materials, start=1):
                row = {
                    "year": year,
                    "season": season,
                    "materialName": mat_name,
                    "count": count,
                    "rank": rank,
                }
                rows.append(row)
                
                # Toplam satır limiti kontrolü
                if len(rows) >= limit:
                    break
            
            if len(rows) >= limit:
                break
        
        return {
            "scenario": "material_usage_top_per_year_season",
            "period": period,
            "limit_per_group": limit_per_group,
            "rows": rows,
        }

    def material_usage_top_per_dimension(
        self,
        group_dimension: str = "vehicleModel",
        period: Optional[dict] = None,
        limit_per_group: int = 5,
        limit: int = 200,
    ) -> Dict[str, Any]:
        """
        Belirli bir dimension'a göre gruplandırılmış en çok kullanılan malzemeler.
        
        Her grup (vehicleModel, vehicleType vb.) için ayrı ayrı top N malzeme döndürür.
        
        Args:
            group_dimension: Gruplama boyutu ("vehicleModel", "vehicleType", "customer")
            period: Dönem filtresi (son N yıl, son N ay vb.)
                    Örnek: {"kind": "last_n_years", "years": 2}
            limit_per_group: Her grup için kaç malzeme (varsayılan: 5)
            limit: Toplam maksimum satır sayısı (varsayılan: 200)
            
        Returns:
            {
                "scenario": "material_usage_top_per_dimension",
                "group_dimension": "vehicleModel",
                "period": {...},
                "limit_per_group": 5,
                "rows": [
                    {"vehicleModel": "TGS 18.440", "materialName": "X", "count": 100, "rank": 1},
                    {"vehicleModel": "TGS 18.440", "materialName": "Y", "count": 80, "rank": 2},
                    {"vehicleModel": "TGX 18.480", "materialName": "Z", "count": 120, "rank": 1},
                    ...
                ]
            }
            
        Örnek Kullanım:
            # Son 2 yılda araç modellerine göre top 10 malzeme
            result = lrs.material_usage_top_per_dimension(
                group_dimension="vehicleModel",
                period={"kind": "last_n_years", "years": 2},
                limit_per_group=10
            )
        """
        from collections import defaultdict
        
        # Veri toplama: group_key -> {materialName: count}
        group_data: Dict[str, Counter] = defaultdict(Counter)
        
        mongo_query: Dict[str, Any] = {
            "$or": [
                {"verb.id": {"$regex": "/verbs/(maintained|repaired)$"}},
                {"statement.verb.id": {"$regex": "/verbs/(maintained|repaired)$"}},
            ]
        }
        
        cursor = self.statements.find(
            mongo_query,
            {
                "actor": 1,
                "statement.actor": 1,
                "context": 1,
                "statement.context": 1,
                "object": 1,
                "statement.object": 1,
                "result": 1,
                "statement.result": 1,
                "timestamp": 1,
                "stored": 1,
                "verb": 1,
                "statement.verb": 1,
            },
        )
        
        for doc in cursor:
            # Dönem filtresi uygula
            if not self._doc_matches_period(doc, period):
                continue
            
            # Group dimension değerini çıkar
            group_ids = self._extract_entity_ids(doc, group_dimension)
            if not group_ids:
                continue
            
            group_key = group_ids[0]  # İlk değeri al (genellikle tek değer olur)
            
            # Malzeme adını çıkar
            mat_name = (
                _get_nested(doc, "object.definition.name.tr-TR")
                or _get_nested(doc, "statement.object.definition.name.tr-TR")
            )
            if not isinstance(mat_name, str) or not mat_name.strip():
                continue
            
            # Gruba ekle
            group_data[group_key][mat_name.strip()] += 1
        
        # Her grup için top N malzemeyi hesapla
        rows: List[Dict[str, Any]] = []
        
        # Grupları toplam kullanıma göre sırala (en çok kullanılan grup önce)
        sorted_groups = sorted(
            group_data.keys(),
            key=lambda g: sum(group_data[g].values()),
            reverse=True
        )
        
        for group_key in sorted_groups:
            counter = group_data[group_key]
            
            # Bu grup için en çok kullanılan malzemeleri al
            top_materials = counter.most_common(limit_per_group)
            
            for rank, (mat_name, count) in enumerate(top_materials, start=1):
                row = {
                    group_dimension: group_key,
                    "materialName": mat_name,
                    "count": count,
                    "rank": rank,
                }
                rows.append(row)
                
                # Toplam satır limiti kontrolü
                if len(rows) >= limit:
                    break
            
            if len(rows) >= limit:
                break
        
        return {
            "scenario": "material_usage_top_per_dimension",
            "group_dimension": group_dimension,
            "period": period,
            "limit_per_group": limit_per_group,
            "rows": rows,
        }

    def top_entities_overall(
        self,
        entity_type: str,
        limit: int = 5,
        service_filter: Optional[str] = None,
        period=None,
        material_filter: Optional[str] = None,
        model_filter: Optional[str] = None,
        vehicle_filter: Optional[str] = None,  # 🆕 Araç ID filtresi
    ) -> List[Dict[str, Any]]:
        """
        Servise bugüne kadar (veya verilen dönemde) en çok gelen:
        - araç (entity_type="vehicle")
        - müşteri (entity_type="customer")
        - araç tipi (entity_type="vehicleType")
        - malzeme (entity_type="material")
        """

        counter: Counter = Counter()

        # Kullanıcı girdilerini normalize et
        material_filter_norm = normalize_tr(material_filter) if material_filter else None
        model_filter_norm = normalize_tr(model_filter) if model_filter else None
        vehicle_filter_val = vehicle_filter.strip() if vehicle_filter else None  # 🆕

        # 🔧 FIX: vehicle_filter varsa verb filtresini kaldır
        # Neden: Bazı araçların verb.id formatı regex'e uymuyor olabilir.
        # vehicle_maintenance_history fonksiyonu verb filtresi kullanmıyor
        # ve çalışıyor, bu yüzden aynı yaklaşımı burada da uyguluyoruz.
        if vehicle_filter_val:
            # Araç bazlı sorgularda TÜM kayıtlara bak (verb filtresi yok)
            mongo_query: Dict[str, Any] = {}
        else:
            # Genel sorgularda verb filtresini uygula
            mongo_query: Dict[str, Any] = {
                "$or": [
                    {"verb.id": {"$regex": "/verbs/(maintained|repaired)$"}},
                    {"statement.verb.id": {"$regex": "/verbs/(maintained|repaired)$"}},
                ]
            }

        # Malzeme filtresi varsa ekle (normalize edilmiş sorgu ile)
        if material_filter_norm:
            if "$and" not in mongo_query:
                mongo_query["$and"] = []

            mongo_query["$and"].append(
                {
                    "$or": [
                        {
                            "object.definition.name.tr-TR": {
                                "$regex": material_filter_norm,
                                "$options": "i",
                            }
                        },
                        {
                            "statement.object.definition.name.tr-TR": {
                                "$regex": material_filter_norm,
                                "$options": "i",
                            }
                        },
                    ]
                }
            )

        # 🆕 Vehicle filtresi varsa ekle
        if vehicle_filter_val:
            vehicle_condition = {
                "$or": [
                    # actor.account.name: "vehicle/70886" veya "70886"
                    {
                        "actor.account.name": {
                            "$regex": f"(^|/)({vehicle_filter_val})$",
                            "$options": "i",
                        }
                    },
                    {
                        "statement.actor.account.name": {
                            "$regex": f"(^|/)({vehicle_filter_val})$",
                            "$options": "i",
                        }
                    },
                    # context.extensions içindeki vehicle ID alanları
                    {
                        "context.extensions.https://promptever.com/extensions/vehicleId": 
                            vehicle_filter_val
                    },
                    {
                        "context.extensions.https://promptever.com/extensions/vehicleNo": 
                            vehicle_filter_val
                    },
                    {
                        "statement.context.extensions.https://promptever.com/extensions/vehicleId": 
                            vehicle_filter_val
                    },
                    {
                        "statement.context.extensions.https://promptever.com/extensions/vehicleNo": 
                            vehicle_filter_val
                    },
                ]
            }
            
            if "$and" not in mongo_query:
                mongo_query["$and"] = []
            mongo_query["$and"].append(vehicle_condition)

        cursor = self.statements.find(
            mongo_query,
            {
                "actor": 1,
                "verb": 1,
                "statement.actor": 1,
                "statement.verb": 1,
                "context": 1,
                "statement.context": 1,
                "object": 1,
                "statement.object": 1,
                "result": 1,
                "statement.result": 1,
            },
        )

        for doc in cursor:
            # Servis filtresi
            if not self._doc_matches_service_filter(doc, service_filter):
                continue

            # Dönem filtresi
            if not self._doc_matches_period(doc, period):
                continue

            # Model filtresi (normalize edilmiş karşılaştırma)
            if model_filter_norm:
                ctx = _get_context(doc)
                exts = ctx.get("extensions") or {}
                doc_model = exts.get("https://promptever.com/extensions/modelNo")

                if not doc_model:
                    continue

                doc_model_norm = normalize_tr(str(doc_model))
                if model_filter_norm not in doc_model_norm:
                    continue

            # Entity ID'lerini çıkar ve say
            ids = self._extract_entity_ids(doc, entity_type)
            for eid in ids:
                counter[eid] += 1

        results: List[Dict[str, Any]] = []
        for eid, cnt in counter.most_common(limit):
            results.append(
                {
                    "entity": eid,
                    "count": cnt,
                    "entity_type": entity_type,
                }
            )

        return results

    def answer_top_entities_question(self, question: TopEntitiesQuestion) -> Dict[str, Any]:
        """
        TopEntitiesQuestion için:
        - LRS tarafında sayımı yapar
        - Zaman filtresini uygular (son N ay / yıl, kış mevsimi vb.)
        - UI ve LLM için meta bilgileri hazırlar
        """
        entity_type = question.entity_type
        period = question.period or {}

        # ------------------------------------------------------
        # 1) Anchor (referans) tarihi belirle
        # ------------------------------------------------------
        anchor_date = self._compute_latest_business_date()

        if anchor_date is None:
            # LRS'te hiç tarih bulunamadı
            effective_anchor_date = None
            effective_period_text = "Tarih bilgisi bulunamadı"
            effective_threshold_date = None
        else:
            effective_anchor_date = anchor_date.date().isoformat()

            # ------------------------------------------------------
            # 2) Dönem metni ve threshold tarihi
            # ------------------------------------------------------
            effective_period_text: Optional[str] = None
            effective_threshold_date: Optional[str] = None

            kind = None
            if isinstance(period, dict):
                kind = period.get("kind")

            if kind == "last_n_months":
                months = int(period.get("months") or 0)
                if months > 0:
                    try:
                        from dateutil.relativedelta import relativedelta

                        threshold = anchor_date - relativedelta(months=months)
                        effective_threshold_date = threshold.date().isoformat()
                        effective_period_text = (
                            f"Son {months} ay ({threshold.date().isoformat()} "
                            f"- {anchor_date.date().isoformat()} arası)"
                        )
                    except ImportError:
                        # dateutil yoksa fallback
                        threshold = anchor_date - timedelta(days=months * 30)
                        effective_threshold_date = threshold.date().isoformat()
                        effective_period_text = (
                            f"Son {months} ay (yaklaşık {threshold.date().isoformat()} "
                            f"- {anchor_date.date().isoformat()} arası)"
                        )

            elif kind == "last_n_years":
                years = int(period.get("years") or 0)
                if years > 0:
                    try:
                        from dateutil.relativedelta import relativedelta

                        threshold = anchor_date - relativedelta(years=years)
                        effective_threshold_date = threshold.date().isoformat()
                        effective_period_text = (
                            f"Son {years} yıl ({threshold.date().isoformat()} "
                            f"- {anchor_date.date().isoformat()} arası)"
                        )
                    except ImportError:
                        # dateutil yoksa fallback
                        threshold = anchor_date - timedelta(days=years * 365)
                        effective_threshold_date = threshold.date().isoformat()
                        effective_period_text = (
                            f"Son {years} yıl (yaklaşık {threshold.date().isoformat()} "
                            f"- {anchor_date.date().isoformat()} arası)"
                        )

            elif kind == "season":
                season = (period.get("season") or "").lower()
                season_names = {
                    "winter": "Kış mevsimi (Aralık-Ocak-Şubat)",
                    "spring": "İlkbahar mevsimi (Mart-Nisan-Mayıs)",
                    "summer": "Yaz mevsimi (Haziran-Temmuz-Ağustos)",
                    "autumn": "Sonbahar mevsimi (Eylül-Ekim-Kasım)",
                    "fall": "Sonbahar mevsimi (Eylül-Ekim-Kasım)",
                }
                effective_period_text = season_names.get(
                    season,
                    "Belirtilen mevsim için servis kayıtları",
                )

        # ------------------------------------------------------
        # 3) Asıl sayım: top_entities_overall
        # ------------------------------------------------------
        rows = self.top_entities_overall(
            entity_type=entity_type,
            limit=question.limit or 5,
            service_filter=question.service_filter,
            period=period,
            material_filter=question.material_filter,
            model_filter=question.model_filter,
            vehicle_filter=question.vehicle_filter,  # 🆕
        )

        # ------------------------------------------------------
        # 4) UI + LLM için zengin response
        # ------------------------------------------------------
        return {
            "scenario": "top_entities_overall",
            "question": {
                "entity_type": entity_type,
                "limit": question.limit,
                "service_filter": question.service_filter,
                "period": period,
                "material_filter": question.material_filter,
                "model_filter": question.model_filter,
                "vehicle_filter": question.vehicle_filter,  # 🆕
            },
            "rows": rows,
            "effective_period_text": effective_period_text,
            "effective_anchor_date": effective_anchor_date,
            "effective_threshold_date": effective_threshold_date,
            "period_raw": period,
        }

    def material_price_trend(
        self,
        period: Optional[dict] = None,
        limit: int = 15,
    ) -> Dict[str, Any]:
        """
        CSV üzerinde çalışan gerçek fiyat trend analizinin Mongo versiyonu.
        Malzeme kodu bazında ilk ve son fiyat farkını hesaplar.
        """
        # ------------------------
        # 1) Zaman penceresi
        # ------------------------
        anchor_date = self._compute_latest_business_date()
        if not anchor_date:
            return {"scenario": "material_price_trend", "rows": []}

        if period is None:
            period = {"kind": "last_n_years", "years": 3}

        kind = period.get("kind")
        if kind == "last_n_years":
            years = int(period.get("years", 3))
            threshold = anchor_date - timedelta(days=years * 365)
        elif kind == "last_n_months":
            months = int(period.get("months", 36))
            threshold = anchor_date - timedelta(days=months * 30)
        else:
            threshold = datetime.min

        # 🔧 aware/naive karışmasın
        threshold_dt = _to_naive(threshold)
        anchor_dt = _to_naive(anchor_date)

        # ------------------------
        # 2) Mongo'dan kayıtları çek
        # ------------------------
        mongo_query: Dict[str, Any] = {
            "$or": [
                {"result.extensions": {"$exists": True}},
                {"statement.result.extensions": {"$exists": True}},
            ]
        }

        cursor = self.statements.find(
            mongo_query,
            {
                "context": 1,
                "statement.context": 1,
                "object": 1,
                "statement.object": 1,
                "result": 1,
                "statement.result": 1,
                "timestamp": 1,
                "stored": 1,
            },
        )

        # ------------------------
        # 3) Malzeme başına fiyat serisi hesapla
        # ------------------------
        materials: Dict[str, Dict[str, Any]] = {}

        for doc in cursor:
            # Tarih
            op_date = _extract_operation_date(doc)
            if not isinstance(op_date, datetime):
                continue

            op_date = _to_naive(op_date)

            if not (threshold_dt <= op_date <= anchor_dt):
                continue

            # Malzeme kodu
            obj_id = (
                _get_nested(doc, "object.id")
                or _get_nested(doc, "statement.object.id")
            )
            if not obj_id or "/activities/material/" not in str(obj_id):
                continue

            material_code = str(obj_id).split("/activities/material/")[-1]

            # Fiyat
            res = _get_nested(doc, "result.extensions") or _get_nested(
                doc,
                "statement.result.extensions",
            )
            if not isinstance(res, dict):
                continue

            cost = res.get("https://promptever.com/extensions/materialCost")
            if cost is None:
                continue

            try:
                price_val = float(cost)
            except (TypeError, ValueError):
                continue

            bucket = materials.setdefault(
                material_code,
                {"prices": []},
            )
            bucket["prices"].append((op_date, price_val))

        # ------------------------
        # 4) İlk-son fiyat değişimini hesapla
        # ------------------------
        rows: List[Dict[str, Any]] = []

        for code, info in materials.items():
            prices = sorted(info["prices"], key=lambda x: x[0])
            if len(prices) < 2:
                continue

            first_date, first_price = prices[0]
            last_date, last_price = prices[-1]

            if first_price <= 0:
                continue

            change_abs = last_price - first_price
            if change_abs <= 0:
                continue

            change_pct = (change_abs / first_price) * 100.0

            rows.append(
                {
                    "materialCode": code,
                    "firstDate": first_date.date().isoformat(),
                    "lastDate": last_date.date().isoformat(),
                    "firstPrice": round(first_price, 2),
                    "lastPrice": round(last_price, 2),
                    "changeAbs": round(change_abs, 2),
                    "changePct": round(change_pct, 1),
                    "observations": len(prices),
                }
            )

        rows = sorted(rows, key=lambda r: r["changePct"], reverse=True)[:limit]

        return {
            "scenario": "material_price_trend",
            "period": period,
            "rows": rows,
        }

    def material_price_trend_by_season(
        self,
        period: Optional[dict] = None,
        limit: int = 15,
    ) -> Dict[str, Any]:
        """
        Mevsim bazında malzeme fiyat değişimi analizi.
        
        Her malzeme için mevsim bazında:
        - O mevsimde yapılan işlemlerin ortalama fiyatı
        - Dönem başı ve dönem sonu fiyat karşılaştırması
        - Fiyat değişim yüzdesi
        
        Örnek soru: "Son 1 yılda mevsimlere göre fiyatı en çok artan malzemeler"
        """
        # ------------------------
        # 1) Zaman penceresi
        # ------------------------
        anchor_date = self._compute_latest_business_date()
        if not anchor_date:
            return {"scenario": "material_price_trend_by_season", "rows": []}

        if period is None:
            period = {"kind": "last_n_years", "years": 2}

        kind = period.get("kind")
        if kind == "last_n_years":
            years = int(period.get("years", 2))
            threshold = anchor_date - timedelta(days=years * 365)
        elif kind == "last_n_months":
            months = int(period.get("months", 24))
            threshold = anchor_date - timedelta(days=months * 30)
        else:
            threshold = datetime.min

        threshold_dt = _to_naive(threshold)
        anchor_dt = _to_naive(anchor_date)

        # ------------------------
        # 2) Mongo'dan kayıtları çek
        # ------------------------
        mongo_query: Dict[str, Any] = {
            "$or": [
                {"result.extensions": {"$exists": True}},
                {"statement.result.extensions": {"$exists": True}},
            ]
        }

        cursor = self.statements.find(
            mongo_query,
            {
                "context": 1,
                "statement.context": 1,
                "object": 1,
                "statement.object": 1,
                "result": 1,
                "statement.result": 1,
                "timestamp": 1,
                "stored": 1,
            },
        )

        # ------------------------
        # 3) Malzeme + Mevsim bazında fiyat serisi topla
        # ------------------------
        buckets: Dict[tuple, Dict[str, Any]] = defaultdict(lambda: {"prices": []})

        def _get_season_name(month: int) -> str:
            """Ay numarasından mevsim döndür"""
            if month in (12, 1, 2):
                return "kis"
            elif month in (3, 4, 5):
                return "ilkbahar"
            elif month in (6, 7, 8):
                return "yaz"
            else:
                return "sonbahar"

        for doc in cursor:
            # Tarih
            op_date = _extract_operation_date(doc)
            if not isinstance(op_date, datetime):
                continue

            op_date = _to_naive(op_date)

            if not (threshold_dt <= op_date <= anchor_dt):
                continue

            # Mevsim hesapla
            season = _get_season_name(op_date.month)

            # Malzeme kodu
            obj_id = (
                _get_nested(doc, "object.id")
                or _get_nested(doc, "statement.object.id")
            )
            if not obj_id or "/activities/material/" not in str(obj_id):
                continue

            material_code = str(obj_id).split("/activities/material/")[-1]

            # Fiyat
            res = _get_nested(doc, "result.extensions") or _get_nested(
                doc,
                "statement.result.extensions",
            )
            if not isinstance(res, dict):
                continue

            cost = res.get("https://promptever.com/extensions/materialCost")
            if cost is None:
                continue

            try:
                price_val = float(cost)
            except (TypeError, ValueError):
                continue

            # Bucket'a ekle
            key = (material_code, season)
            buckets[key]["prices"].append((op_date, price_val))

        # ------------------------
        # 4) Her bucket için istatistik hesapla
        # ------------------------
        rows: List[Dict[str, Any]] = []

        for (material_code, season), info in buckets.items():
            prices = sorted(info["prices"], key=lambda x: x[0])
            
            if len(prices) < 2:
                continue

            price_values = [p[1] for p in prices]
            
            first_date, first_price = prices[0]
            last_date, last_price = prices[-1]

            if first_price <= 0:
                continue

            change_abs = last_price - first_price
            change_pct = (change_abs / first_price) * 100.0

            # Sadece artanları al
            if change_abs <= 0:
                continue

            rows.append({
                "materialCode": material_code,
                "season": season,
                "avgPrice": round(sum(price_values) / len(price_values), 2),
                "minPrice": round(min(price_values), 2),
                "maxPrice": round(max(price_values), 2),
                "priceRange": round(max(price_values) - min(price_values), 2),
                "observations": len(prices),
                "firstDate": first_date.date().isoformat(),
                "lastDate": last_date.date().isoformat(),
                "firstPrice": round(first_price, 2),
                "lastPrice": round(last_price, 2),
                "changeAbs": round(change_abs, 2),
                "changePct": round(change_pct, 1),
            })

        rows = sorted(rows, key=lambda r: r["changePct"], reverse=True)[:limit]

        return {
            "scenario": "material_price_trend_by_season",
            "period": period,
            "rows": rows,
        }

    def material_family_price_trend(
        self,
        period: Optional[dict] = None,
        limit: int = 15,
        min_materials: int = 2,
    ) -> Dict[str, Any]:
        """
        Malzeme aileleri bazında fiyat artış trendi analizi.

        Örnek aile:
          81.12501-6101
          81.12501-6102
          81.12501-xxxx
        → aile kodu: 81.12501
        """
        # ------------------------
        # 1) Zaman penceresi
        # ------------------------
        anchor_date = self._compute_latest_business_date()
        if not anchor_date:
            return {
                "scenario": "material_family_price_trend",
                "period": period,
                "rows": [],
            }

        if period is None:
            period = {"kind": "last_n_years", "years": 3}

        kind = period.get("kind")
        if kind == "last_n_years":
            years = int(period.get("years") or 3)
            threshold = anchor_date - timedelta(days=years * 365)
        elif kind == "last_n_months":
            months = int(period.get("months") or 36)
            threshold = anchor_date - timedelta(days=months * 30)
        else:
            # Tanımlı değilse tüm zaman
            threshold = datetime.min

        threshold_dt = _to_naive(threshold)
        anchor_dt = _to_naive(anchor_date)

        # ------------------------
        # 2) Mongo'dan fiyat verisi olan kayıtları çek
        # ------------------------
        mongo_query: Dict[str, Any] = {
            "$or": [
                {"result.extensions": {"$exists": True}},
                {"statement.result.extensions": {"$exists": True}},
            ]
        }

        cursor = self.statements.find(
            mongo_query,
            {
                "context": 1,
                "statement.context": 1,
                "object": 1,
                "statement.object": 1,
                "result": 1,
                "statement.result": 1,
                "timestamp": 1,
                "stored": 1,
            },
        )

        # ------------------------
        # 3) Aile kodu → malzeme kodu → fiyat serisi
        # ------------------------
        families: Dict[str, Dict[str, Any]] = {}

        for doc in cursor:
            op_date = _extract_operation_date(doc)
            if not isinstance(op_date, datetime):
                continue

            op_date = _to_naive(op_date)

            if not (threshold_dt <= op_date <= anchor_dt):
                continue

            obj_id = (
                _get_nested(doc, "object.id")
                or _get_nested(doc, "statement.object.id")
            )
            if not obj_id or "/activities/material/" not in str(obj_id):
                continue

            material_code = str(obj_id).split("/activities/material/")[-1]
            # Aile: '-' öncesi prefix (örn 81.12501-6101 -> 81.12501)
            family_code = material_code.split("-")[0]

            res = _get_nested(doc, "result.extensions") or _get_nested(
                doc,
                "statement.result.extensions",
            )
            if not isinstance(res, dict):
                continue

            cost = res.get("https://promptever.com/extensions/materialCost")
            if cost is None:
                continue

            qty = res.get("https://promptever.com/extensions/materialQuantity")
            try:
                qty_val = float(qty) if qty is not None else None
            except (TypeError, ValueError):
                qty_val = None

            try:
                price_val = float(cost)
            except (TypeError, ValueError):
                continue

            if qty_val and qty_val > 0:
                price_val = price_val / qty_val

            fam = families.setdefault(
                family_code,
                {"materials": defaultdict(list)},
            )
            fam["materials"][material_code].append((op_date, price_val))

        # ------------------------
        # 4) Her aile için ortalama fiyat değişimi
        # ------------------------
        rows: List[Dict[str, Any]] = []

        for family_code, info in families.items():
            material_prices = info["materials"]
            if len(material_prices) < min_materials:
                continue

            family_changes: List[float] = []

            for material_code, prices in material_prices.items():
                prices_sorted = sorted(prices, key=lambda x: x[0])
                if len(prices_sorted) < 2:
                    continue

                first_date, first_price = prices_sorted[0]
                last_date, last_price = prices_sorted[-1]

                if first_price <= 0:
                    continue

                change_abs = last_price - first_price
                if change_abs <= 0:
                    continue

                change_pct = (change_abs / first_price) * 100.0
                family_changes.append(change_pct)

            if not family_changes:
                continue

            avg_change_pct = sum(family_changes) / len(family_changes)

            rows.append(
                {
                    "materialFamily": family_code,
                    "avgChangePct": round(avg_change_pct, 1),
                    "materialsCount": len(material_prices),
                }
            )

        rows = sorted(rows, key=lambda r: r["avgChangePct"], reverse=True)[:limit]

        return {
            "scenario": "material_family_price_trend",
            "period": period,
            "rows": rows,
        }

    def material_family_price_trend_by_season(
        self,
        period: Optional[dict] = None,
        limit_per_season: int = 10,
        min_materials: int = 2,
    ) -> Dict[str, Any]:
        """
        Mevsimlere göre fiyatı en çok artan malzeme aileleri.

        Her mevsim için (kis/ilkbahar/yaz/sonbahar) ayrı top N döner.
        """

        # ------------------------
        # 1) Zaman penceresi (material_family_price_trend ile aynı)
        # ------------------------
        anchor_date = self._compute_latest_business_date()
        if not anchor_date:
            return {
                "scenario": "material_family_price_trend_by_season",
                "period": period,
                "rows": [],
            }

        if period is None:
            period = {"kind": "last_n_years", "years": 2}

        kind = period.get("kind")
        if kind == "last_n_years":
            years = int(period.get("years") or 2)
            threshold = anchor_date - timedelta(days=years * 365)
        elif kind == "last_n_months":
            months = int(period.get("months") or 24)
            threshold = anchor_date - timedelta(days=months * 30)
        else:
            threshold = datetime.min

        threshold_dt = _to_naive(threshold)
        anchor_dt = _to_naive(anchor_date)

        # ------------------------
        # 2) Mongo query (fiyat verisi olan kayıtlar)
        # ------------------------
        mongo_query: Dict[str, Any] = {
            "$or": [
                {"result.extensions": {"$exists": True}},
                {"statement.result.extensions": {"$exists": True}},
            ]
        }

        cursor = self.statements.find(
            mongo_query,
            {
                "context": 1,
                "statement.context": 1,
                "object": 1,
                "statement.object": 1,
                "result": 1,
                "statement.result": 1,
                "timestamp": 1,
                "stored": 1,
            },
        )

        def _get_season_name(month: int) -> str:
            if month in (12, 1, 2):
                return "kis"
            elif month in (3, 4, 5):
                return "ilkbahar"
            elif month in (6, 7, 8):
                return "yaz"
            return "sonbahar"

        # ------------------------
        # 3) (season, family) -> material_code -> [(date, price)]
        # ------------------------
        buckets: Dict[tuple, Dict[str, Any]] = defaultdict(lambda: {"materials": defaultdict(list)})

        for doc in cursor:
            op_date = _extract_operation_date(doc)
            if not isinstance(op_date, datetime):
                continue

            op_date = _to_naive(op_date)

            if not (threshold_dt <= op_date <= anchor_dt):
                continue

            obj_id = (
                _get_nested(doc, "object.id")
                or _get_nested(doc, "statement.object.id")
            )
            if not obj_id or "/activities/material/" not in str(obj_id):
                continue

            material_code = str(obj_id).split("/activities/material/")[-1]
            family_code = material_code.split("-")[0]

            res = _get_nested(doc, "result.extensions") or _get_nested(
                doc,
                "statement.result.extensions",
            )
            if not isinstance(res, dict):
                continue

            cost = res.get("https://promptever.com/extensions/materialCost")
            if cost is None:
                continue

            qty = res.get("https://promptever.com/extensions/materialQuantity")
            try:
                qty_val = float(qty) if qty is not None else None
            except (TypeError, ValueError):
                qty_val = None

            try:
                price_val = float(cost)
            except (TypeError, ValueError):
                continue

            if qty_val and qty_val > 0:
                price_val = price_val / qty_val


            season = _get_season_name(op_date.month)

            bucket = buckets[(season, family_code)]
            bucket["materials"][material_code].append((op_date, price_val))

        # ------------------------
        # 4) Her (mevsim, aile) için ortalama fiyat değişimi
        # ------------------------
        rows: List[Dict[str, Any]] = []

        for (season, family_code), info in buckets.items():
            material_prices = info["materials"]
            if len(material_prices) < min_materials:
                continue

            family_changes: List[float] = []

            for material_code, prices in material_prices.items():
                prices_sorted = sorted(prices, key=lambda x: x[0])
                if len(prices_sorted) < 2:
                    continue

                first_price = prices_sorted[0][1]
                last_price = prices_sorted[-1][1]

                if first_price <= 0:
                    continue

                change_abs = last_price - first_price
                if change_abs <= 0:
                    continue

                change_pct = (change_abs / first_price) * 100.0
                family_changes.append(change_pct)

            if not family_changes:
                continue

            avg_change_pct = sum(family_changes) / len(family_changes)

            rows.append(
                {
                    "season": season,
                    "materialFamily": family_code,
                    "avgChangePct": round(avg_change_pct, 1),
                    "materialsCount": len(material_prices),
                }
            )

        # ------------------------
        # 5) Her mevsim için top N
        # ------------------------
        by_season: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for r in rows:
            by_season[r["season"]].append(r)

        out: List[Dict[str, Any]] = []
        for season, items in by_season.items():
            items.sort(key=lambda r: r["avgChangePct"], reverse=True)
            out.extend(items[:limit_per_season])

        season_order = {"kis": 0, "ilkbahar": 1, "yaz": 2, "sonbahar": 3}
        out.sort(key=lambda r: (season_order.get(r["season"], 99), -r["avgChangePct"], r["materialFamily"]))

        return {
            "scenario": "material_family_price_trend_by_season",
            "period": period,
            "rows": out,
        }

    def next_maintenance_materials(
        self,
        model: str,
        material_name: str,
        limit: int = 20,
    ) -> Dict[str, Any]:
        """
        Pattern: Belirli bir modelde, X malzemesi kullanıldıktan sonraki
        ilk bakımda hangi malzemeler daha sık değişiyor?
        """

        # -----------------------------------------
        # 0) Parametre kontrolü
        # -----------------------------------------
        if not model:
            return {"rows": [], "note": "model parametresi zorunludur."}

        if not material_name:
            return {"rows": [], "note": "material_name parametresi zorunludur."}

        target_model_norm = normalize_model(model)
        target_material_norm = normalize_tr(material_name)

        # -----------------------------------------
        # 1) MODELE göre Mongo'dan kayıt çek
        # -----------------------------------------
        model_ext = "https://promptever.com/extensions/modelNo"

        # Burada sadece extensions objesinin varlığına bakıyoruz,
        # model filtresini Python tarafında yapacağız.
        query: Dict[str, Any] = {
            "$and": [
                {
                    "$or": [
                        {"verb.id": {"$regex": "/verbs/(maintained|repaired)$"}},
                        {"statement.verb.id": {"$regex": "/verbs/(maintained|repaired)$"}},
                    ]
                },
                {
                    "$or": [
                        {"context.extensions": {"$exists": True}},
                        {"statement.context.extensions": {"$exists": True}},
                    ]
                },
            ]
        }

        cursor = self.statements.find(
            query,
            {
                "actor": 1,
                "statement.actor": 1,
                "verb": 1,
                "statement.verb": 1,
                "context": 1,
                "statement.context": 1,
                "object": 1,
                "statement.object": 1,
                "timestamp": 1,
                "stored": 1,
            },
        )

        # -----------------------------------------
        # 2) Araç bazında operasyon gruplama
        # -----------------------------------------
        operations_by_vehicle: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        from services.lrs_schema import _extract_vehicle_id_from_actor

        for doc in cursor:
            # Araç ID

            vehicle_id = _extract_vehicle_id_from_actor(doc)
            if not vehicle_id:
                continue

            # Tarih
            op_date = _extract_operation_date(doc)
            if not isinstance(op_date, datetime):
                continue

            # Model savunmacı kontrol
            exts = (
                _get_nested(doc, "context.extensions")
                or _get_nested(doc, "statement.context.extensions")
                or {}
            )
            model_raw = exts.get(model_ext)

            # Artık Mongo'da model filtrelemediğimiz için,
            # modelNo alanı yoksa veya uyuşmuyorsa dokümanı atıyoruz.
            if not model_raw:
                continue

            model_norm = normalize_model(str(model_raw))

            # 1) Basit alt string kontrolü (senin istediğin mantık)
            ok = target_model_norm in model_norm

            # 2) Boşlukları kaldırarak ikinci bir kontrol (rhc404 vs rhc 404)
            if not ok:
                t_comp = target_model_norm.replace(" ", "")
                m_comp = model_norm.replace(" ", "")
                if t_comp in m_comp or m_comp in t_comp:
                    ok = True

            # 3) (İstersen) token bazlı daha semantik kontrol
            #    Örn. hedefteki her kelime dokümanda geçsin:
            if not ok:
                target_tokens = target_model_norm.split()
                doc_tokens = model_norm.split()
                if all(tok in doc_tokens for tok in target_tokens):
                    ok = True

            if not ok:
                continue


            # Malzeme al
            mat_name = (
                _get_nested(doc, "object.definition.name.tr-TR")
                or _get_nested(doc, "statement.object.definition.name.tr-TR")
            )
            if not mat_name:
                continue

            mat_norm = normalize_tr(str(mat_name))

            # Operasyon nesnesi
            ops = operations_by_vehicle[vehicle_id]
            op_day = op_date.date()
            op = next((o for o in ops if o["date"] == op_day), None)
            if op is None:
                op = {"date": op_day, "materials": set()}
                ops.append(op)

            op["materials"].add(mat_norm)

        # -----------------------------------------
        # 3) Operasyonları tarihe göre sırala
        # -----------------------------------------
        for vid, ops in operations_by_vehicle.items():
            ops.sort(key=lambda o: o["date"])

        # -----------------------------------------
        # 4) Pattern oluşturma:
        #    X malzemesi → bir sonraki bakım
        # -----------------------------------------
        counter: Counter[str] = Counter()
        matched_pairs = 0

        for vid, ops in operations_by_vehicle.items():
            for idx, op in enumerate(ops):
                materials = op["materials"]  # zaten normalize_tr ile kaydedildi

                # Bu bakımda hedef malzeme kullanılmış mı?
                toks = set(target_material_norm.split())
                has_target = any(toks.issubset(set(m.split())) for m in materials)
                
                if not has_target:
                    continue

                # Bu araç için bir sonraki bakım yoksa geç
                if idx + 1 >= len(ops):
                    continue

                next_op = ops[idx + 1]
                counter.update(next_op["materials"])
                matched_pairs += 1

        # -----------------------------------------
        # 5) Hiç eşleşme yoksa erken dönüş
        # -----------------------------------------
        if not counter:
            return {
                "rows": [],
                "note": (
                    f"{model} için '{material_name}' kullanılan bakımdan sonra "
                    f"ikinci bir bakım kaydı bulunamadı veya veri çok seyrek."
                ),
            }

        # -----------------------------------------
        # 6) Sonuçları tabloya dönüştür
        # -----------------------------------------
        total = sum(counter.values())
        top_materials = counter.most_common(limit)

        rows: List[Dict[str, Any]] = []
        for mat, cnt in top_materials:
            ratio = (cnt / total) * 100 if total > 0 else 0.0
            rows.append(
                {
                    "material": mat,
                    "count": cnt,
                    "ratio": round(ratio, 1),
                }
            )

        # -----------------------------------------
        # 7) Her durumda dict döndür
        # -----------------------------------------
        return {
            "model": model,
            "material": material_name,
            "rows": rows,
            "matched_pairs": matched_pairs,
            "note": (
                f"Bu analizde {matched_pairs} adet 'malzemeden sonraki ilk bakım' "
                f"çifti bulundu. Değerlendirme model='{model}', "
                f"malzeme='{material_name}' için yapılmıştır."
            ),
        }
    def vehicle_maintenance_history(
        self,
        vehicle_id: str,
        limit: int = 300,
    ) -> Dict[str, Any]:
        """
        Belirli bir aracın (vehicle_id) bakım/onarım geçmişini malzeme bazında döndürür.

        Her satır:
          - date        : operasyon tarihi (YYYY-MM-DD)
          - service     : servis kodu (R540 vb.)
          - model       : modelNo (ör: rhc 404 400)
          - km          : odometer
          - verbType    : BAKIM / ONARIM / DİĞER
          - materialName: malzeme adı
          - quantity    : kullanılan adet
          - cost        : malzeme tutarı
          - faultCode   : arıza kodu (varsa)

        NOT:
        URL içeren extension key'leri (örn.
        "https://promptever.com/extensions/odometerReading") doğrudan
        `_get_nested(doc, "result.extensions.https://...")` ile okunamaz;
        `_get_nested` path'i '.' ile böldüğü için "https://promptever"
        kısmında takılır. Bu yüzden önce `result.extensions` dict'ini
        alıp, URL key'lerine normal `dict.get(...)` ile erişiyoruz.
        """
        if not vehicle_id:
            return {
                "scenario": "vehicle_maintenance_history",
                "vehicle_id": vehicle_id,
                "rows": [],
                "note": "vehicle_id parametresi zorunludur.",
            }

        mongo_query = {
            "$or": [
                {"actor.account.name": f"vehicle/{vehicle_id}"},
                {"statement.actor.account.name": f"vehicle/{vehicle_id}"},
            ]
        }

        cursor = self.statements.find(
            mongo_query,
            {
                "actor": 1,
                "statement.actor": 1,
                "context": 1,
                "statement.context": 1,
                "verb": 1,
                "statement.verb": 1,
                "object": 1,
                "statement.object": 1,
                "result": 1,
                "statement.result": 1,
                "timestamp": 1,
                "stored": 1,
            },
        )

        rows: List[Dict[str, Any]] = []

        for doc in cursor:
            op_date = _extract_operation_date(doc)
            if not op_date:
                continue

            service_code = _extract_service_code_from_context(doc)

            # Context içinden model bilgisi
            ctx = _get_context(doc)
            exts_ctx = ctx.get("extensions") or {}
            model_no = exts_ctx.get("https://promptever.com/extensions/modelNo")

            # --- ÖNEMLİ: result.extensions'ı tek yerde topla ---
            exts_result = (
                _get_nested(doc, "result.extensions")
                or _get_nested(doc, "statement.result.extensions")
                or {}
            )

            # URL key'lere normal .get ile eriş
            km = exts_result.get("https://promptever.com/extensions/odometerReading")
            fault_code = exts_result.get("https://promptever.com/extensions/faultCode")

            verb_id = (
                _get_nested(doc, "verb.id")
                or _get_nested(doc, "statement.verb.id")
                or ""
            )
            verb_type = "DİĞER"
            if isinstance(verb_id, str):
                if verb_id.endswith("maintained"):
                    verb_type = "BAKIM"
                elif verb_id.endswith("repaired"):
                    verb_type = "ONARIM"

            mat_name = (
                _get_nested(doc, "object.definition.name.tr-TR")
                or _get_nested(doc, "statement.object.definition.name.tr-TR")
            )
            if not mat_name:
                continue

            qty = exts_result.get(
                "https://promptever.com/extensions/materialQuantity"
            )
            cost = exts_result.get(
                "https://promptever.com/extensions/materialCost"
            )

            rows.append(
                {
                    "date": op_date.date().isoformat(),
                    "service": service_code,
                    "model": model_no,
                    "km": km,
                    "verbType": verb_type,
                    "materialName": mat_name,
                    "quantity": qty,
                    "cost": cost,
                    "faultCode": fault_code,
                }
            )

        rows.sort(key=lambda r: r["date"])
        if limit:
            rows = rows[:limit]

        return {
            "scenario": "vehicle_maintenance_history",
            "vehicle_id": vehicle_id,
            "rows": rows,
        }