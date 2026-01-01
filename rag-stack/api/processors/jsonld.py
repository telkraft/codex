from typing import List, Dict, Any
from qdrant_client.models import PointStruct, Distance, VectorParams
from qdrant_client.http.exceptions import UnexpectedResponse
import uuid

# Servis / Bakım / Onarım için JSON-LD context
XAPI_JSONLD_CONTEXT: Dict[str, Any] = {
    "id": "@id",
    "type": "@type",

    # xAPI temel sınıflar
    "Statement": "https://w3id.org/xapi/ontology#Statement",
    "Agent": "https://w3id.org/xapi/ontology#Agent",
    "Activity": "https://w3id.org/xapi/ontology#Activity",

    # Promptever prefix'leri
    "pe": "https://promptever.com/",
    "ex": "https://promptever.com/extensions/",
    "act": "https://promptever.com/activities/",
    "verb": "https://promptever.com/verbs/",

    # Varlık kısaltmaları
    "material": "act:material/",
    "vehicle": "act:vehicle/",
    "customer": "act:customer/",
    "workorder": "act:workorder/",
    "serviceLocation": "act:service-location/",

    # Extension alias'ları
    "vehicleType": "ex:vehicleType",
    "modelNo": "ex:modelNo",
    "firstRegistrationDate": "ex:firstRegistrationDate",
    "recordDate": "ex:recordDate",
    "operationDate": "ex:operationDate",
    "operationCategory": "ex:operationCategory",
    "separationType": "ex:separationType",
    "stockType": "ex:stockType",
    "manufacturer": "ex:manufacturer",
    "odometerReading": "ex:odometerReading",
    "materialQuantity": "ex:materialQuantity",
    "materialCost": "ex:materialCost",
    "discountAmount": "ex:discountAmount",
    "faultCode": "ex:faultCode",

    # xAPI temel alan kısaltmaları
    "actor": "https://w3id.org/xapi/ontology#actor",
    "verbProp": "https://w3id.org/xapi/ontology#verb",
    "object": "https://w3id.org/xapi/ontology#object",
    "context": "https://w3id.org/xapi/ontology#context",
    "result": "https://w3id.org/xapi/ontology#result",
    "timestamp": "https://w3id.org/xapi/ontology#timestamp",
}


def _extract_ids(stmt: Dict[str, Any]) -> Dict[str, Any]:
    """
    Statement içinden workorder / vehicle / customer / service-location ID'lerini ve isimlerini çıkarır.
    
    Yeni modelde:
      - Araç: actor.account.name = "vehicle/70685"
      - Müşteri: grouping'de activity + definition.name = "Musteri 159463"
      - Servis: grouping'de activity + definition.name = "Servis R540"
    """
    context = stmt.get("context", {}) or {}
    ctx_acts = context.get("contextActivities", {}) or {}

    workorder_id = None
    vehicle_id = None
    customer_id = None
    customer_name = None
    service_location_id = None
    service_name = None

    # parent → workorder
    for parent in ctx_acts.get("parent", []) or []:
        pid = parent.get("id", "")
        if "workorder" in pid:
            workorder_id = pid

    # grouping → vehicle / customer / service-location (with names)
    for grp in ctx_acts.get("grouping", []) or []:
        gid = grp.get("id", "")
        
        # Extract name from definition
        grp_def = grp.get("definition", {}) or {}
        grp_name = (grp_def.get("name", {}) or {}).get("tr-TR")
        
        if "vehicle" in gid:
            vehicle_id = gid
        elif "customer" in gid:
            customer_id = gid
            customer_name = grp_name  # "Musteri 159463"
        elif "service-location" in gid:
            service_location_id = gid
            service_name = grp_name  # "Servis R540"

    # Actor içinden vehicle fallback'i
    actor = stmt.get("actor", {}) or {}
    account = actor.get("account", {}) or {}
    acc_name = account.get("name")
    if not vehicle_id and isinstance(acc_name, str) and acc_name.startswith("vehicle/"):
        vehicle_id = acc_name

    return {
        "workorder_id": workorder_id,
        "vehicle_id": vehicle_id,
        "customer_id": customer_id,
        "customer_name": customer_name,
        "service_location_id": service_location_id,
        "service_name": service_name,
    }


def _build_human_readable_text(stmt: Dict[str, Any]) -> str:
    """
    xAPI statement'ı kısa, temiz, URL'siz Türkçe metne çevir.
    RAG embedding için optimize edilmiş format - LLM'e daha az token, daha anlamlı.

    Özellikler:
    - URL'ler → sadece ID (son segment)
    - Yapılandırılmış, satır satır format
    - LLM-dostu, kolay parse edilir
    - ASCII-consistent (aracta, not araçta)
    """
    ids = _extract_ids(stmt)

    # Actor
    actor = stmt.get("actor", {}) or {}
    actor_name = actor.get("name", "")  # "Arac 70685"

    # Verb
    verb = stmt.get("verb", {}) or {}
    verb_tr = verb.get("display", {}).get("tr-TR", "")

    # Object (Material)
    obj = stmt.get("object", {}) or {}
    obj_def = obj.get("definition", {}) or {}
    material_name = obj_def.get("name", {}).get("tr-TR", "")
    material_id = obj.get("id", "").split("/")[-1] if obj.get("id") else ""

    # Context extensions
    context = stmt.get("context", {}) or {}
    ctx_ext = context.get("extensions", {}) or {}
    vehicle_type = ctx_ext.get("https://promptever.com/extensions/vehicleType", "")
    model_no = ctx_ext.get("https://promptever.com/extensions/modelNo", "")
    first_reg = ctx_ext.get("https://promptever.com/extensions/firstRegistrationDate", "")
    record_date = ctx_ext.get("https://promptever.com/extensions/recordDate", "")
    operation_date = ctx_ext.get("https://promptever.com/extensions/operationDate", "")
    stock_type = ctx_ext.get("https://promptever.com/extensions/stockType", "")
    manufacturer = ctx_ext.get("https://promptever.com/extensions/manufacturer", "")
    operation_category = ctx_ext.get("https://promptever.com/extensions/operationCategory", "")
    separation_type = ctx_ext.get("https://promptever.com/extensions/separationType", "")

    # Result extensions
    result = stmt.get("result", {}) or {}
    res_ext = result.get("extensions", {}) or {}
    odometer = res_ext.get("https://promptever.com/extensions/odometerReading")
    qty = res_ext.get("https://promptever.com/extensions/materialQuantity")
    cost = res_ext.get("https://promptever.com/extensions/materialCost")
    discount = res_ext.get("https://promptever.com/extensions/discountAmount")
    fault = res_ext.get("https://promptever.com/extensions/faultCode")

    # Extract clean IDs (no URLs)
    workorder_id = ids["workorder_id"].split("/")[-1] if ids["workorder_id"] else ""
    service_id = ids["service_location_id"].split("/")[-1] if ids["service_location_id"] else ""
    customer_id = ids["customer_id"].split("/")[-1] if ids["customer_id"] else ""

    parts = []

    # Line 1: Actor + Vehicle + Operation
    line1 = f"{actor_name}"
    if model_no or vehicle_type:
        vehicle_desc = f"{model_no} {vehicle_type}" if model_no else vehicle_type
        line1 += f", {vehicle_desc} tipi aracta"  # ASCII-consistent
    if verb_tr:
        line1 += f" {verb_tr.lower()} islemi yapti."  # ASCII-consistent
    parts.append(line1)

    # Line 2: Material
    if material_name:
        mat_line = f"Malzeme: {material_name}"
        if material_id:
            mat_line += f" ({material_id})"
        parts.append(mat_line)

    # Line 3: Work order
    if workorder_id:
        parts.append(f"Is emri: {workorder_id}")

    # Line 4: Metrics (maliyet, km, miktar, arıza, indirim)
    metrics = []
    if odometer is not None:
        formatted_km = f"{odometer:,}".replace(",", ".")
        metrics.append(f"kilometre: {formatted_km} km")
    if cost is not None:
        metrics.append(f"maliyet: {cost} TL")
    if discount is not None:
        metrics.append(f"indirimli tutar: {discount} TL")
    if qty is not None:
        metrics.append(f"miktar: {qty}")
    if fault:
        metrics.append(f"ariza: {fault}")  # ASCII-consistent

    if metrics:
        parts.append(", ".join(metrics))

    # Line 5: Context (tarihler, servis, müşteri, stok, üretici, kategori)
    context_parts = []
    if record_date:
        context_parts.append(f"kayit: {record_date}")
    if operation_date:
        context_parts.append(f"islem: {operation_date}")
    if first_reg:
        context_parts.append(f"tescil: {first_reg}")
    if service_id:
        context_parts.append(f"servis: {service_id}")
    if customer_id:
        context_parts.append(f"musteri: {customer_id}")
    if stock_type:
        context_parts.append(f"stok turu: {stock_type}")
    if manufacturer:
        context_parts.append(f"uretici: {manufacturer}")
    if operation_category:
        context_parts.append(f"is turu: {operation_category}")
    if separation_type:
        context_parts.append(f"ayristirma: {separation_type}")

    if context_parts:
        parts.append(", ".join(context_parts))

    return ". ".join(parts)


async def process_xapi_statements(
    statements: Dict[str, Any],
    collection: str,
    qdrant_client,
    embedding_model,
) -> int:
    """
    MAN servis / bakım / onarım xAPI statement'larını:
      - JSON-LD context ile zenginleştirir,
      - İnsan okuyabilir, URL'siz Türkçe metne çevirir,
      - Embed eder ve Qdrant'a yazar.

    Vektör tarafında SADECE özet cümle (searchable_text) kullanılır;
    ham xAPI ve JSON-LD payload içinde saklanır.
    """
    # Koleksiyon var mı, yoksa oluştur
    try:
        qdrant_client.get_collection(collection)
    except UnexpectedResponse:
        qdrant_client.create_collection(
            collection_name=collection,
            vectors_config=VectorParams(size=384, distance=Distance.COSINE),
        )
    except Exception:
        pass

    # Statement listesini çıkar
    statement_list = statements.get("statements")
    if statement_list is None:
        statement_list = [statements]
    elif not isinstance(statement_list, list):
        statement_list = [statement_list]

    points: List[PointStruct] = []

    for stmt in statement_list:
        if not isinstance(stmt, dict):
            continue

        # JSON-LD enrich
        jsonld_stmt: Dict[str, Any] = {"@context": XAPI_JSONLD_CONTEXT, **stmt}

        # İnsan okuyabilir metin (URL'siz, temiz)
        searchable_text = _build_human_readable_text(stmt)
        if not searchable_text.strip():
            continue

        # Embedding üret (SADECE bu cümle için)
        embedding = embedding_model.encode(searchable_text).tolist()

        # Metadata çıkarımı
        ids = _extract_ids(stmt)
        context = stmt.get("context", {}) or {}
        ctx_ext = context.get("extensions", {}) or {}

        result = stmt.get("result", {}) or {}
        res_ext = result.get("extensions", {}) or {}

        obj = stmt.get("object", {}) or {}
        obj_def = obj.get("definition", {}) or {}
        obj_name_tr = (obj_def.get("name", {}) or {}).get("tr-TR")
        obj_name_en = (obj_def.get("name", {}) or {}).get("en-US")

        verb_id = (stmt.get("verb", {}) or {}).get("id", "")

        if "maintained" in verb_id:
            operation_type = "maintenance"
        elif "accident-repaired" in verb_id:
            operation_type = "accident-repair"
        elif "repaired" in verb_id:
            operation_type = "repair"
        else:
            operation_type = "other"

        fault_code = res_ext.get("https://promptever.com/extensions/faultCode")
        has_fault = bool(fault_code)

        metadata: Dict[str, Any] = {
            "type": "service_maintenance_statement",
            "statement_id": stmt.get("id", ""),
            "timestamp": stmt.get("timestamp", ""),
            "verb_id": (stmt.get("verb", {}) or {}).get("id"),
            "verb_tr": (stmt.get("verb", {}) or {}).get("display", {}).get("tr-TR"),
            "operationType": operation_type,
            "hasFault": has_fault,
            "actor_name": (stmt.get("actor", {}) or {}).get("name")
                or (stmt.get("actor", {}) or {}).get("mbox"),

            "material_id": obj.get("id"),
            "material_name_tr": obj_name_tr,
            "material_name_en": obj_name_en,

            "workorder_id": ids["workorder_id"],
            "vehicle_id": ids["vehicle_id"],
            "customer_id": ids["customer_id"],
            "customer_name": ids["customer_name"],  # NEW
            "service_location_id": ids["service_location_id"],
            "service_name": ids["service_name"],  # NEW

            "vehicleType": ctx_ext.get("https://promptever.com/extensions/vehicleType"),
            "modelNo": ctx_ext.get("https://promptever.com/extensions/modelNo"),
            "firstRegistrationDate": ctx_ext.get(
                "https://promptever.com/extensions/firstRegistrationDate"
            ),
            "recordDate": ctx_ext.get(
                "https://promptever.com/extensions/recordDate"
            ),
            "operationDate": ctx_ext.get(
                "https://promptever.com/extensions/operationDate"
            ),
            "stockType": ctx_ext.get(
                "https://promptever.com/extensions/stockType"
            ),
            "manufacturer": ctx_ext.get(
                "https://promptever.com/extensions/manufacturer"
            ),
            "operationCategory": ctx_ext.get(
                "https://promptever.com/extensions/operationCategory"
            ),
            "separationType": ctx_ext.get(
                "https://promptever.com/extensions/separationType"
            ),

            "odometerReading": res_ext.get(
                "https://promptever.com/extensions/odometerReading"
            ),
            "materialQuantity": res_ext.get(
                "https://promptever.com/extensions/materialQuantity"
            ),
            "materialCost": res_ext.get(
                "https://promptever.com/extensions/materialCost"
            ),
            "discountAmount": res_ext.get(
                "https://promptever.com/extensions/discountAmount"
            ),
            "faultCode": res_ext.get(
                "https://promptever.com/extensions/faultCode"
            ),

            # Tam statement'ı da saklayalım (ama embed etmiyoruz)
            "raw_statement": stmt,
        }

        point = PointStruct(
            id=str(uuid.uuid4()),
            vector=embedding,
            payload={
                "text": searchable_text,
                "jsonld": jsonld_stmt,
                "metadata": metadata,
            },
        )
        points.append(point)

    if points:
        qdrant_client.upsert(
            collection_name=collection,
            points=points,
        )

    return len(points)