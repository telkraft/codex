"""
LRS Examples & Period Filtering
===============================

Örnek xAPI statement'ları çekme, dönem filtreleri ve
insan-dili açıklama cümleleri için mixin.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from bson import ObjectId

from models import TopEntitiesQuestion
from services.lrs_schema import (
    _get_context,
    _get_nested,
    _extract_vehicle_id_from_actor,
    _extract_service_code_from_context,
    _extract_customer_id_from_context,
    _get_attr,
)


class LRSExamplesMixin:
    """
    LRSCore ile birlikte kullanıldığında:

    - self.statements           : Mongo koleksiyonu (LRSCore'dan)
    - self._build_mongo_filter  : QueryPlan → Mongo filter (LRSCore'dan)

    Bu mixin:
    - Örnek statement çekme
    - Dönem filtresi (mevsim / son N ay / son N yıl)
    - İnsan-dili açıklama cümleleri
    - "top entities" için örnek kayıtlar
    gibi işleri üstlenir.
    """

    # ---------- Örnek xAPI Statement Çekme ----------

    def get_example_statements(
        self,
        plan,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Aynı QueryPlan filtresine uyan ham xAPI statement'ları döndürür.
        En son kayıtlardan başlayarak limit kadar döner.
        """
        mongo_filter = self._build_mongo_filter(plan)

        cursor = (
            self.statements.find(mongo_filter)
            .sort("timestamp", -1)
            .limit(limit)
        )

        examples: List[Dict[str, Any]] = []
        for doc in cursor:
            # _id'yi string'e çevirip ekleyelim (UI'de gerekebilir)
            if isinstance(doc.get("_id"), ObjectId):
                doc["_id"] = str(doc["_id"])
            examples.append(doc)

        return examples

    # ---------- İş günü anchor tarihi ----------

    def _compute_latest_business_date(self) -> Optional[datetime]:
        """
        LRS içindeki tüm kayıtlar arasında operationDate / recordDate'e göre
        EN SON tarihi bulur ve döner.

        - Sadece context/statement.context.extensions içindeki:
          * https://promptever.com/extensions/operationDate
          * https://promptever.com/extensions/recordDate
          alanlarına bakar.
        - Bulamazsa None döner.
        """
        latest: Optional[datetime] = None

        def _parse_iso(value: Any) -> Optional[datetime]:
            if isinstance(value, datetime):
                return value
            if isinstance(value, str):
                try:
                    return datetime.fromisoformat(value.replace("Z", "+00:00"))
                except Exception:
                    return None
            return None

        # Sadece context alanlarını projekte edelim; diğer alanlara ihtiyacımız yok
        cursor = self.statements.find(
            {},
            {
                "context": 1,
                "statement.context": 1,
            },
        )

        for doc in cursor:
            ctx = _get_context(doc)
            exts = ctx.get("extensions") or {}

            op_raw = None
            rec_raw = None
            if isinstance(exts, dict):
                op_raw = exts.get("https://promptever.com/extensions/operationDate")
                rec_raw = exts.get("https://promptever.com/extensions/recordDate")

            dt = _parse_iso(op_raw) or _parse_iso(rec_raw)
            if dt and (latest is None or dt > latest):
                latest = dt

        # Sonucu cache'leyelim (aynı process içinde tekrar tekrar hesaplamayalım)
        self._latest_business_date = latest
        return latest

    # ---------- Dönem filtresi ----------

    def _doc_matches_period(self, doc: Dict[str, Any], period) -> bool:
        """
        Dönem filtresi:

        - FuturePeriodSpec veya dict içindeki "kind" alanına göre çalışır.
        - Şu an desteklenenler:
            * kind == "season"         → mevsime göre (kış = 12,1,2 vb.)
              - year verilmişse: o yıla göre
              - year verilmemişse: tüm yıllarda o mevsim
            * kind == "month"          → belirli ay (opsiyonel year ile)
            * kind == "year"           → belirli yıl
            * kind == "last_n_months"  → son N ay (operationDate / recordDate üzerinden)
            * kind == "last_n_years"   → son N yıl (operationDate / recordDate üzerinden)

        Yalnızca operationDate ve recordDate'e bakar.
        timestamp / stored gibi LRS sistem tarihlerini KULLANMAZ.
        """
        if not period:
            return True

        def _parse_iso(value: Any) -> Optional[datetime]:
            if isinstance(value, datetime):
                return value
            if isinstance(value, str):
                try:
                    return datetime.fromisoformat(value.replace("Z", "+00:00"))
                except Exception:
                    return None
            return None

        def _get_business_datetime(doc: Dict[str, Any]) -> Optional[datetime]:
            ctx = _get_context(doc)
            exts = ctx.get("extensions") or {}
            if not isinstance(exts, dict):
                return None

            op_raw = exts.get("https://promptever.com/extensions/operationDate")
            rec_raw = exts.get("https://promptever.com/extensions/recordDate")

            return _parse_iso(op_raw) or _parse_iso(rec_raw)

        dt = _get_business_datetime(doc)
        if not dt:
            # Gerçek operasyon/record tarihi yoksa dönemli soruda dışarı atalım
            return False

        kind = _get_attr(period, "kind", None)

        # ------------------------------------------------------------------
        # ÖZEL: son N ay
        # ------------------------------------------------------------------
        if kind == "last_n_months":
            months = _get_attr(period, "months", None)
            try:
                months = int(months)
            except (TypeError, ValueError):
                months = None

            if not months or months <= 0:
                # Dönemi anlayamazsak filtre uygulamayalım
                return True

            # Anchor tarihi: LRS'teki EN SON operationDate/recordDate
            anchor = getattr(self, "_latest_business_date", None)
            if anchor is None:
                anchor = self._compute_latest_business_date()

            if not anchor:
                # LRS'te hiç tarih yakalayamazsak, filtreyi devre dışı bırak
                return True

            threshold = anchor - timedelta(days=months * 30)  # kabaca
            return dt >= threshold

        # ------------------------------------------------------------------
        # ÖZEL: son N yıl
        # ------------------------------------------------------------------
        if kind == "last_n_years":
            years = _get_attr(period, "years", None)
            try:
                years = int(years)
            except (TypeError, ValueError):
                years = None

            if not years or years <= 0:
                return True

            anchor = getattr(self, "_latest_business_date", None)
            if anchor is None:
                anchor = self._compute_latest_business_date()

            if not anchor:
                return True

            threshold = anchor - timedelta(days=years * 365)  # kabaca
            return dt >= threshold

        # ------------------------------------------------------------------
        # Mevsim / ay / yıl mantığı
        # ------------------------------------------------------------------
        year = dt.year
        month = dt.month

        # YEAR
        if kind == "year":
            p_year = _get_attr(period, "year", None)
            if not p_year:
                # Yıl verilmemişse aslında filtre yok
                return True
            try:
                p_year = int(p_year)
            except (TypeError, ValueError):
                return True
            return year == p_year

        # MONTH (opsiyonel year ile)
        if kind == "month":
            p_month = _get_attr(period, "month", None)
            if not p_month:
                return True
            try:
                p_month = int(p_month)
            except (TypeError, ValueError):
                return True

            if month != p_month:
                return False

            p_year = _get_attr(period, "year", None)
            if p_year is None:
                return True
            try:
                p_year = int(p_year)
            except (TypeError, ValueError):
                return True
            return year == p_year

        # SEASON
        if kind == "season":
            season = (_get_attr(period, "season", "") or "").lower()
            p_year = _get_attr(period, "year", None)
            try:
                p_year = int(p_year) if p_year is not None else None
            except (TypeError, ValueError):
                p_year = None

            if season == "winter":
                season_months = {12, 1, 2}
            elif season == "spring":
                season_months = {3, 4, 5}
            elif season == "summer":
                season_months = {6, 7, 8}
            elif season in ("autumn", "fall"):
                season_months = {9, 10, 11}
            else:
                # tanımsız mevsim → filtre yok
                return True

            if month not in season_months:
                return False

            # Yıl belirtilmemişse: tüm yıllarda bu mevsim kabul
            if p_year is None:
                return True

            # Kış için yıl kayması (Aralık bir önceki yıl)
            if season == "winter":
                if month == 12:
                    return year == (p_year - 1)
                else:
                    return year == p_year

            # Diğer mevsimler: normal aynı yıl
            return year == p_year

        # ------------------------------------------------------------------
        # Dönemi çözemiyorsak filtre uygulamayalım
        # ------------------------------------------------------------------
        return True

    # ---------- "En çok gelen..." tipi sorular için örnekler ----------

    def get_examples_for_top_entities(
        self,
        question: TopEntitiesQuestion,
        rows: List[Dict[str, Any]],
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        En çok gelen varlıklar tablosundaki entity'lere karşılık gelen
        örnek xAPI kayıtlarını döndürür.
        """
        if not rows:
            return []

        # Top listeden entity id'lerini topla (biraz sınır koyarak)
        target_ids: set[str] = set()
        for r in rows:
            eid = r.get("entity")
            if isinstance(eid, (str, int)):
                target_ids.add(str(eid))
            if len(target_ids) >= limit * 3:
                break

        if not target_ids:
            return []

        examples: List[Dict[str, Any]] = []

        cursor = (
            self.statements.find(
                {},
                {
                    "actor": 1,
                    "context": 1,
                    "statement.actor": 1,
                    "statement.context": 1,
                    "result": 1,
                    "statement.result": 1,
                    "object": 1,
                    "verb": 1,
                    "timestamp": 1,
                    "stored": 1,
                },
            )
            .sort("timestamp", -1)
        )

        for doc in cursor:
            if not self._doc_matches_service_filter(doc, question.service_filter):
                continue
            if not self._doc_matches_period(doc, question.period):
                continue

            ids_in_doc = self._extract_entity_ids(doc, question.entity_type)
            if any(str(eid) in target_ids for eid in ids_in_doc):
                if isinstance(doc.get("_id"), ObjectId):
                    doc["_id"] = str(doc["_id"])
                examples.append(doc)
                if len(examples) >= limit:
                    break

        return examples

    # ---------- İnsan-dili açıklama ----------

    def render_statement_human(self, stmt: Dict[str, Any]) -> str:
        """
        xAPI statement'ı daha kapsayıcı ve bağlamsal bir Türkçe cümle hâline getirir.
        """
        # ------------------------------
        # Tarih (önce operationDate, sonra recordDate)
        # ------------------------------
        raw_ts = (
            _get_nested(
                stmt,
                "context.extensions.https://promptever.com/extensions/operationDate",
            )
            or _get_nested(
                stmt,
                "context.extensions.https://promptever.com/extensions/recordDate",
            )
            or stmt.get("timestamp")
            or _get_nested(stmt, "statement.timestamp")
            or stmt.get("stored")
            or _get_nested(stmt, "statement.stored")
        )

        date_str = None
        if isinstance(raw_ts, datetime):
            date_str = raw_ts.date().isoformat()
        elif isinstance(raw_ts, str):
            try:
                dt = datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
                date_str = dt.date().isoformat()
            except Exception:
                date_str = raw_ts

        date_part = f"{date_str} tarihinde" if date_str else "Belirsiz tarihte"

        # ------------------------------
        # Servis, araç, müşteri
        # ------------------------------
        service_code = _extract_service_code_from_context(stmt)
        service_part = f"{service_code} servisinde" if service_code else "bir serviste"

        customer_id = _extract_customer_id_from_context(stmt)
        customer_part = (
            f"{customer_id} numaralı müşterinin" if customer_id else "bir müşterinin"
        )

        vehicle_id = _extract_vehicle_id_from_actor(stmt)
        vehicle_part = f"{vehicle_id} numaralı aracı" if vehicle_id else "aracı"

        # ------------------------------
        # Araç detayları (context.extensions + km)
        # ------------------------------
        ctx = _get_context(stmt)
        exts = ctx.get("extensions") or {}

        vehicle_type = exts.get("https://promptever.com/extensions/vehicleType")
        model_no = exts.get("https://promptever.com/extensions/modelNo")
        manufacturer = exts.get("https://promptever.com/extensions/manufacturer")

        result_ext = _get_nested(stmt, "result.extensions", {}) or {}
        km = result_ext.get("https://promptever.com/extensions/odometerReading")

        vehicle_details = []
        if manufacturer:
            vehicle_details.append(f"üretici: {manufacturer}")
        if vehicle_type:
            vehicle_details.append(f"tipi: {vehicle_type}")
        if model_no:
            vehicle_details.append(f"modeli: {model_no}")
        if km is not None:
            vehicle_details.append(f"km: {km}")

        vehicle_details_str = (
            " (" + ", ".join(vehicle_details) + ")" if vehicle_details else ""
        )

        # ------------------------------
        # Verb
        # ------------------------------
        verb = stmt.get("verb") or {}
        vdisp = verb.get("display") or {}
        verb_tr = vdisp.get("tr-TR") or vdisp.get("en-US") or "işlem"
        verb_part = verb_tr.upper()

        # ------------------------------
        # Malzeme bilgileri
        # ------------------------------
        obj = stmt.get("object") or {}
        definition = obj.get("definition") or {}
        mat_name = (
            definition.get("name", {}).get("tr-TR")
            or definition.get("name", {}).get("en-US")
            or "malzeme"
        )

        cost = result_ext.get("https://promptever.com/extensions/materialCost")
        qty = result_ext.get("https://promptever.com/extensions/materialQuantity")
        discount = result_ext.get("https://promptever.com/extensions/discountAmount")

        mat_details = []
        mat_details.append(f"malzeme: {mat_name}")
        if qty is not None:
            mat_details.append(f"adet: {qty}")
        if cost is not None:
            mat_details.append(f"tutar: {cost} TL")
        if discount is not None:
            mat_details.append(f"indirimli tutar: {discount} TL")

        mat_details_str = ", ".join(mat_details)

        # ------------------------------
        # Son cümle
        # ------------------------------
        sentence = (
            f"{date_part} {service_part}, "
            f"{customer_part} {vehicle_part}{vehicle_details_str} için "
            f"{verb_part} ({mat_details_str}) işlemi yapıldı."
        )

        return sentence

    # ---------- "En çok gelen..." tipi sorular için yardımcılar ----------

    def _extract_entity_ids(
        self,
        doc: Dict[str, Any],
        entity_type: str,
    ) -> List[str]:
        """
        entity_type:
          - "vehicle"    : actor.account.name (vehicle/XYZ → XYZ)
          - "customer"   : contextActivities.grouping → /activities/customer/...
          - "vehicleType": context.extensions.vehicleType
          - "vehicleModel" : context.extensions.modelNo
          - "material"   : object.definition.name.tr-TR (malzeme adı)
        """
        ids: List[str] = []

        # 1) Araç (vehicle)
        if entity_type == "vehicle":
            vid = _extract_vehicle_id_from_actor(doc)
            if vid:
                ids.append(str(vid))
            return ids

        # 2) Müşteri (customer)
        if entity_type == "customer":
            ctx = _get_context(doc)
            ctx_acts = ctx.get("contextActivities") or {}
            grouping = ctx_acts.get("grouping") or []
            if isinstance(grouping, dict):
                grouping = [grouping]

            for g in grouping:
                if not isinstance(g, dict):
                    continue
                gid = g.get("id")
                if not isinstance(gid, str):
                    continue
                # .../activities/customer/XYZ → XYZ
                if "/activities/customer/" in gid:
                    cid = gid.rsplit("/", 1)[-1]
                    if cid:
                        ids.append(cid)
            return ids

        # 3) Araç tipi (vehicleType)
        if entity_type == "vehicleType":
            ctx = _get_context(doc)
            exts = ctx.get("extensions") or {}
            vt = None

            if isinstance(exts, dict):
                # Önce bizim MAN extension IRI'sini dene
                vt = exts.get(
                    "https://promptever.com/extensions/vehicleType"
                )

                # Olmazsa, key içinde "vehicletype" geçen herhangi bir extension'a düş
                if vt is None:
                    for k, v in exts.items():
                        if isinstance(k, str) and "vehicletype" in k.lower():
                            vt = v
                            break

            if vt not in (None, "", 0, "0"):
                ids.append(str(vt))
            return ids

        # 4) Malzeme (material)
        if entity_type == "material":
            # Önce root-level object
            name = _get_nested(doc, "object.definition.name.tr-TR")
            if not isinstance(name, str) or not name.strip():
                # LRS bazı durumlarda statement.* altında tutuyor olabilir
                name = _get_nested(doc, "statement.object.definition.name.tr-TR")

            if isinstance(name, str) and name.strip():
                ids.append(name.strip())

            return ids
        
        # 5) Araç modeli (vehicleModel)
        if entity_type == "vehicleModel":
            ctx = _get_context(doc)
            exts = ctx.get("extensions") or {}

            model_no = exts.get("https://promptever.com/extensions/modelNo")

            if isinstance(model_no, (str, int, float)):
                model_str = str(model_no).strip()
                if model_str:
                    ids.append(model_str)

            return ids

        # Tanımadığımız entity_type için boş liste
        return ids

    def _doc_matches_service_filter(
        self,
        doc: Dict[str, Any],
        service_filter: Optional[str],
    ) -> bool:
        """
        Eğer service_filter verilmişse, contextActivities.grouping içindeki
        service-location activity'lerinin ID'lerinde bu kodun geçip geçmediğine bakar.
        Örn:
          - service_filter = "540"
          - id = ".../activities/service-location/R540" veya ".../service-location/540"
        """
        if not service_filter:
            return True

        ctx = _get_context(doc)
        ca = ctx.get("contextActivities") or {}
        grouping = ca.get("grouping") or []
        if not isinstance(grouping, list):
            return False

        for g in grouping:
            if not isinstance(g, dict):
                continue
            gid = g.get("id")
            if not isinstance(gid, str):
                continue
            if "/activities/service-location/" in gid and service_filter in gid:
                return True

        return False
