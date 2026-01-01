const BASE_URI = "https://promptever.com";
const data = item.json;

// ============================================================================
// HELPER FUNCTIONS
// ============================================================================

// UUID üreticisi
function uuidv4() {
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === "x" ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

// Sayı çevirme
function toNumber(val) {
  if (val === null || val === undefined) return undefined;
  const s = String(val).trim();
  if (s === "") return undefined;
  const normalized = s.replace(",", ".");
  const n = Number(normalized);
  return isNaN(n) ? undefined : n;
}

// Tarih normalize
function toISO(value) {
  if (!value) return undefined;

  const d1 = new Date(value);
  if (!isNaN(d1.getTime())) return d1.toISOString();

  const m = String(value).match(
    /^(\d{2})\.(\d{2})\.(\d{4})[ T](\d{2}):(\d{2}):(\d{2})$/
  );
  if (m) {
    const [, dd, MM, yyyy, hh, mm, ss] = m;
    const d2 = new Date(
      Date.UTC(
        Number(yyyy),
        Number(MM) - 1,
        Number(dd),
        Number(hh),
        Number(mm),
        Number(ss)
      )
    );
    if (!isNaN(d2.getTime())) return d2.toISOString();
  }

  return undefined;
}

// Basit trim
function cleanString(val) {
  if (val === null || val === undefined) return undefined;
  const cleaned = String(val).trim();
  return cleaned === "" ? undefined : cleaned;
}

// Türkçe karakter ve format normalizasyonu (Python ile birebir uyumlu)
function normalizeFull(text) {
  if (!text) return "";
  return String(text)
    .toLowerCase()
    .replace(/ı/g, "i").replace(/İ/g, "i")
    .replace(/ş/g, "s").replace(/Ş/g, "s")
    .replace(/ğ/g, "g").replace(/Ğ/g, "g")
    .replace(/ü/g, "u").replace(/Ü/g, "u")
    .replace(/ö/g, "o").replace(/Ö/g, "o")
    .replace(/ç/g, "c").replace(/Ç/g, "c")
    .replace(/[^a-z0-9 ]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

// ============================================================================
// VERB MAPPING
// ============================================================================

const VERB_MAP = {
  BAKIM: {
    id: `${BASE_URI}/verbs/maintained`,
    display: { "tr-TR": "Bakım", "en-US": "Maintained" },
  },
  ONARIM: {
    id: `${BASE_URI}/verbs/repaired`,
    display: { "tr-TR": "Onarım", "en-US": "Repaired" },
  },
  "ONARIM KAZA": {
    id: `${BASE_URI}/verbs/accident-repaired`,
    display: { "tr-TR": "Kaza Onarımı", "en-US": "Accident Repaired" },
  },
  "KAZA ONARIM": {
    id: `${BASE_URI}/verbs/accident-repaired`,
    display: { "tr-TR": "Kaza Onarımı", "en-US": "Accident Repaired" },
  },
  AKSIYON: {
    id: `${BASE_URI}/verbs/action`,
    display: { "tr-TR": "Aksiyon", "en-US": "Action" },
  },
};

// İşlem türü → xAPI verb
function getVerb(islemturu) {
  const n = normalizeFull(islemturu || "");

  // 1) En spesifik: Kaza onarımı
  if (n.includes("onarim") && n.includes("kaza")) {
    return VERB_MAP["ONARIM KAZA"];
  }

  // 2) Aksiyon
  if (n.includes("aksiyon")) {
    return VERB_MAP["AKSIYON"];
  }

  // 3) 2.EL ONARIM
  if (n.includes("2") && n.includes("el") && n.includes("onarim")) {
    return VERB_MAP["ONARIM"];
  }

  // 4) Genel onarım
  if (n.includes("onarim")) {
    return VERB_MAP["ONARIM"];
  }

  // 5) Genel bakım (EURO6 C-D-E BAKIM dahil)
  if (n.includes("bakim")) {
    return VERB_MAP["BAKIM"];
  }

  // 6) Fallback
  return {
    id: "http://adlnet.gov/expapi/verbs/completed",
    display: { "tr-TR": islemturu || "Tamamlandı", "en-US": "Completed" },
  };
}

// ============================================================================
// ID HELPERS
// ============================================================================

// Araç ID
function extractVehicleId(aracData) {
  const raw = cleanString(aracData);
  if (!raw) return "UNKNOWN";
  const tokens = normalizeFull(raw).split(" ");
  return tokens[0] || "UNKNOWN";
}

// Müşteri ID
function extractCustomerId(musteriData) {
  const raw = cleanString(musteriData);
  if (!raw) return "UNKNOWN";
  const tokens = normalizeFull(raw).split(" ");
  return tokens[0] || "UNKNOWN";
}

// EURO6 bakım paketi etiketi
function detectMaintenancePackage(islemturu) {
  const n = normalizeFull(islemturu || "");
  if (n.includes("euro6") && n.includes("bakim")) {
    return "euro6_cde_maintenance";
  }
  return undefined;
}

// ============================================================================
// BUILD STATEMENT
// ============================================================================

const vehicleId = extractVehicleId(data.arac);
const customerId = extractCustomerId(data.musteri);
const verb = getVerb(data.islemturu);
const maintenancePackage = detectMaintenancePackage(data.islemturu);

const statement = {
  id: uuidv4(),
  timestamp: toISO(data.tamamlanmatarih) || new Date().toISOString(),

  actor: {
    objectType: "Agent",
    name: `Arac ${vehicleId}`,
    account: {
      homePage: BASE_URI,
      name: `vehicle/${vehicleId}`,
    },
  },

  verb: verb,

  object: {
    id: `${BASE_URI}/activities/material/${data.malzeme_kodu || "unknown"}`,
    objectType: "Activity",
    definition: {
      name: {
        "tr-TR": normalizeFull(data.malzeme_adi) || "bilinmeyen malzeme",
        "en-US": normalizeFull(data.malzeme_adi) || "unknown material",
      },
      type: `${BASE_URI}/activitytypes/material`,
    },
  },

  context: {
    contextActivities: {
      parent: [
        {
          id: `${BASE_URI}/activities/workorder/${normalizeFull(data.isemirno) || "unknown"}`,
          objectType: "Activity",
        },
      ],
      grouping: [
        {
          id: `${BASE_URI}/activities/customer/${customerId}`,
          objectType: "Activity",
          definition: { name: { "tr-TR": `Musteri ${customerId}` } },
        },
        {
          id: `${BASE_URI}/activities/service-location/${normalizeFull(data.servis) || "unknown"}`,
          objectType: "Activity",
          definition: { name: { "tr-TR": `Servis ${normalizeFull(data.servis)}` } },
        },
      ],
    },
    extensions: {
      ...(data.arac_tipi && { [`${BASE_URI}/extensions/vehicleType`]: normalizeFull(data.arac_tipi) }),
      ...(data.modelno && { [`${BASE_URI}/extensions/modelNo`]: normalizeFull(data.modelno) }),
      ...(toISO(data.trafige_ilk_cikis_tarihi) && {
        [`${BASE_URI}/extensions/firstRegistrationDate`]: toISO(data.trafige_ilk_cikis_tarihi),
      }),
      ...(toISO(data.kayittarih) && {
        [`${BASE_URI}/extensions/recordDate`]: toISO(data.kayittarih),
      }),
      ...(toISO(data.islemtarihi) && {
        [`${BASE_URI}/extensions/operationDate`]: toISO(data.islemtarihi),
      }),
      ...(data.tur && { [`${BASE_URI}/extensions/operationCategory`]: normalizeFull(data.tur) }),
      ...(data.ayristirmaturu && { [`${BASE_URI}/extensions/separationType`]: normalizeFull(data.ayristirmaturu) }),
      ...(data.stokturu && { [`${BASE_URI}/extensions/stockType`]: normalizeFull(data.stokturu) }),
      ...(data.uretici && { [`${BASE_URI}/extensions/manufacturer`]: normalizeFull(data.uretici) }),
      ...(maintenancePackage && {
        [`${BASE_URI}/extensions/maintenancePackage`]: maintenancePackage,
      }),
    },
  },

  result: {
    completion: true,
    success: true,
    extensions: {
      ...(toNumber(data.km) !== undefined && { [`${BASE_URI}/extensions/odometerReading`]: toNumber(data.km) }),
      ...(toNumber(data.miktar) !== undefined && { [`${BASE_URI}/extensions/materialQuantity`]: toNumber(data.miktar) }),
      ...(toNumber(data.tutar) !== undefined && { [`${BASE_URI}/extensions/materialCost`]: toNumber(data.tutar) }),
      ...(toNumber(data.indirimlitutar) !== undefined && { [`${BASE_URI}/extensions/discountAmount`]: toNumber(data.indirimlitutar) }),
      ...(data.arizakodu && { [`${BASE_URI}/extensions/faultCode`]: normalizeFull(data.arizakodu) }),
    },
  },
};

console.log("Statement created:", {
  vehicleId,
  customerId,
  verb: verb.display["tr-TR"],
  maintenancePackage,
  timestamp: statement.timestamp,
  hasExtensions: Object.keys(statement.context.extensions).length > 0,
});

return { json: statement };
