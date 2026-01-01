const BASE_URI = "https://promptever.com";
const data = item.json;

// ============================================================================
// HELPER FUNCTIONS
// ============================================================================

function uuidv4() {
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === "x" ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

function toNumber(val) {
  if (val === null || val === undefined) return undefined;
  const s = String(val).trim();
  if (s === "") return undefined;
  const normalized = s.replace(",", ".");
  const n = Number(normalized);
  return isNaN(n) ? undefined : n;
}

function toISO(value) {
  if (!value) return undefined;

  // Try standard Date parsing
  const d1 = new Date(value);
  if (!isNaN(d1.getTime())) {
    return d1.toISOString();
  }

  // Try DD.MM.YYYY HH:MM:SS format
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
    if (!isNaN(d2.getTime())) {
      return d2.toISOString();
    }
  }

  return undefined;
}

function cleanString(val) {
  if (val === null || val === undefined) return undefined;
  const cleaned = String(val).trim();
  return cleaned === "" ? undefined : cleaned;
}

function normalizeturkish(text) {
  if (!text) return "";
  // Convert Turkish characters to ASCII-safe equivalents for MongoDB regex
  return String(text)
    .replace(/ı/g, "i")
    .replace(/İ/g, "I")
    .replace(/ş/g, "s")
    .replace(/Ş/g, "S")
    .replace(/ğ/g, "g")
    .replace(/Ğ/g, "G")
    .replace(/ü/g, "u")
    .replace(/Ü/g, "U")
    .replace(/ö/g, "o")
    .replace(/Ö/g, "O")
    .replace(/ç/g, "c")
    .replace(/Ç/g, "C");
}

// ============================================================================
// VERB MAPPING
// ============================================================================

const VERB_MAP = {
  "BAKIM": {
    id: `${BASE_URI}/verbs/maintained`,
    display: { "tr-TR": "Bakım", "en-US": "Maintained" }
  },
  "ONARIM": {
    id: `${BASE_URI}/verbs/repaired`,
    display: { "tr-TR": "Onarım", "en-US": "Repaired" }
  },
  "ONARIM KAZA": {
    id: `${BASE_URI}/verbs/accident-repaired`,
    display: { "tr-TR": "Kaza Onarımı", "en-US": "Accident Repaired" }
  },
  "KAZA ONARIM": {
    id: `${BASE_URI}/verbs/accident-repaired`,
    display: { "tr-TR": "Kaza Onarımı", "en-US": "Accident Repaired" }
  }
};

function getVerb(islemturu) {
  const normalized = normalizeturkish(String(islemturu || "").trim().toUpperCase());
  
  // Check for accident repair first (more specific)
  if (normalized.includes("ONARIM") && normalized.includes("KAZA")) {
    return VERB_MAP["ONARIM KAZA"];
  }
  if (normalized.includes("KAZA") && normalized.includes("ONARIM")) {
    return VERB_MAP["KAZA ONARIM"];
  }
  
  // Then check for regular operations
  if (normalized.includes("ONARIM")) {
    return VERB_MAP["ONARIM"];
  }
  if (normalized.includes("BAKIM")) {
    return VERB_MAP["BAKIM"];
  }
  
  // Default fallback
  return {
    id: "http://adlnet.gov/expapi/verbs/completed",
    display: { "tr-TR": islemturu || "Tamamlandı", "en-US": "Completed" }
  };
}

// ============================================================================
// EXTRACT IDs
// ============================================================================

function extractVehicleId(aracData) {
  const raw = cleanString(aracData);
  if (!raw) return "UNKNOWN";
  
  // Get first token (vehicle ID)
  const tokens = raw.split(/\s+/);
  return tokens[0] || "UNKNOWN";
}

function extractCustomerId(musteriData) {
  const raw = cleanString(musteriData);
  if (!raw) return "UNKNOWN";
  
  // Get first token (customer ID)
  const tokens = raw.split(/\s+/);
  return tokens[0] || "UNKNOWN";
}

// ============================================================================
// BUILD STATEMENT
// ============================================================================

const vehicleId = extractVehicleId(data.arac);
const customerId = extractCustomerId(data.musteri);
const verb = getVerb(data.islemturu);

// Completion status
const durumUpper = normalizeturkish(String(data.durum || "").toUpperCase());
const isCompleted = durumUpper.includes("TAMAM") || durumUpper.includes("COMPLETED");

// Build statement
const statement = {
  id: uuidv4(),
  timestamp: toISO(data.tamamlanmatarih) || new Date().toISOString(),

  actor: {
    objectType: "Agent",
    name: `Arac ${vehicleId}`, // ASCII-safe for MongoDB regex
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
        "tr-TR": cleanString(data.malzeme_adi) || "Bilinmeyen Malzeme",
        "en-US": cleanString(data.malzeme_adi) || "Unknown Material"
      },
      type: `${BASE_URI}/activitytypes/material`,
    },
  },

  context: {
    contextActivities: {
      parent: [
        {
          id: `${BASE_URI}/activities/workorder/${data.isemirno || "unknown"}`,
          objectType: "Activity",
        },
      ],
      grouping: [
        {
          id: `${BASE_URI}/activities/customer/${customerId}`,
          objectType: "Activity",
          definition: {
            name: { "tr-TR": `Musteri ${customerId}` }
          }
        },
        {
          id: `${BASE_URI}/activities/service-location/${data.servis || "unknown"}`,
          objectType: "Activity",
          definition: {
            name: { "tr-TR": `Servis ${data.servis || "unknown"}` }
          }
        },
      ],
    },
    // Only include extensions with actual values (no undefined)
    extensions: {
      ...(data.arac_tipi && { [`${BASE_URI}/extensions/vehicleType`]: cleanString(data.arac_tipi) }),
      ...(data.modelno && { [`${BASE_URI}/extensions/modelNo`]: cleanString(data.modelno) }),
      ...(toISO(data.trafige_ilk_cikis_tarihi) && { 
        [`${BASE_URI}/extensions/firstRegistrationDate`]: toISO(data.trafige_ilk_cikis_tarihi) 
      }),
      ...(toISO(data.kayittarih) && { 
        [`${BASE_URI}/extensions/recordDate`]: toISO(data.kayittarih) 
      }),
      ...(toISO(data.islemtarihi) && { 
        [`${BASE_URI}/extensions/operationDate`]: toISO(data.islemtarihi) 
      }),
      ...(data.tur && { [`${BASE_URI}/extensions/operationCategory`]: cleanString(data.tur) }),
      ...(data.ayristirmaturu && { [`${BASE_URI}/extensions/separationType`]: cleanString(data.ayristirmaturu) }),
      ...(data.stokturu && { [`${BASE_URI}/extensions/stockType`]: cleanString(data.stokturu) }),
      ...(data.uretici && { [`${BASE_URI}/extensions/manufacturer`]: cleanString(data.uretici) }),
    },
  },

  result: {
    completion: isCompleted,
    success: isCompleted,
    // Only include extensions with actual values
    extensions: {
      ...(toNumber(data.km) !== undefined && { 
        [`${BASE_URI}/extensions/odometerReading`]: toNumber(data.km) 
      }),
      ...(toNumber(data.miktar) !== undefined && { 
        [`${BASE_URI}/extensions/materialQuantity`]: toNumber(data.miktar) 
      }),
      ...(toNumber(data.tutar) !== undefined && { 
        [`${BASE_URI}/extensions/materialCost`]: toNumber(data.tutar) 
      }),
      ...(toNumber(data.indirimlitutar) !== undefined && { 
        [`${BASE_URI}/extensions/discountAmount`]: toNumber(data.indirimlitutar) 
      }),
      ...(data.arizakodu && { [`${BASE_URI}/extensions/faultCode`]: cleanString(data.arizakodu) }),
    },
  },
};

// ============================================================================
// VALIDATION & RETURN
// ============================================================================

// Log for debugging (optional - remove in production)
console.log("Statement created:", {
  vehicleId,
  customerId,
  verb: verb.display["tr-TR"],
  timestamp: statement.timestamp,
  hasExtensions: Object.keys(statement.context.extensions).length > 0
});

return { json: statement };
