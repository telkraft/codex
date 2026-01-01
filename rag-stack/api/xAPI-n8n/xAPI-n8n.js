const BASE_URI = "https://promptever.com";
const data = item.json;

// ---- Yardımcı Fonksiyonlar ----

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

  const d1 = new Date(value);
  if (!isNaN(d1.getTime())) {
    return d1.toISOString();
  }

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

// ---- Verb Eşleştirme ----
const islemturuUpper = (data.islemturu || "").toUpperCase();
let verbId;

if (islemturuUpper.includes("ONARIM KAZA")) {
  verbId = `${BASE_URI}/verbs/accident-repaired`;
} else if (islemturuUpper.includes("ONARIM")) {
  verbId = `${BASE_URI}/verbs/repaired`;
} else if (islemturuUpper.includes("BAKIM")) {
  verbId = `${BASE_URI}/verbs/maintained`;
} else {
  verbId = "http://adlnet.gov/expapi/verbs/completed";
}

// ---- Araç ve müşteri ID'leri ----
const vehicleRaw = (data.arac || "").trim();
const vehicleId = vehicleRaw ? vehicleRaw.split(" ")[0] : "UNKNOWN";

const musteriRaw = (data.musteri || "").trim();
const musteriId = musteriRaw ? musteriRaw.split(" ")[0] : "UNKNOWN";

// Durumdan completion/success çıkar
const durumUpper = (data.durum || "").toUpperCase();
const isCompleted = durumUpper.includes("TAMAM");

// ---- Statement ----
const statement = {
  id: uuidv4(),

  timestamp: toISO(data.tamamlanmatarih),

  actor: {
    objectType: "Agent",
    name: `Araç ${vehicleId}`,
    account: {
      homePage: BASE_URI,
      name: `vehicle/${vehicleId}`,
    },
  },

  verb: {
    id: verbId,
    display: {
      "tr-TR": data.islemturu || "",
    },
  },

  object: {
    id: `${BASE_URI}/activities/material/${data.malzeme_kodu}`,
    objectType: "Activity",
    definition: {
      name: { "tr-TR": data.malzeme_adi || "" },
      type: `${BASE_URI}/activitytypes/material`,
    },
  },

  context: {
    contextActivities: {
      parent: [
        {
          id: `${BASE_URI}/activities/workorder/${data.isemirno}`,
          objectType: "Activity",
        },
      ],
      grouping: [
        {
          id: `${BASE_URI}/activities/customer/${musteriId}`,
          objectType: "Activity",
        },
        {
          id: `${BASE_URI}/activities/service-location/${data.servis}`,
          objectType: "Activity",
        },
      ],
    },
    extensions: {
      [`${BASE_URI}/extensions/vehicleType`]: data.arac_tipi || undefined,
      [`${BASE_URI}/extensions/modelNo`]: data.modelno || undefined,
      [`${BASE_URI}/extensions/firstRegistrationDate`]: toISO(
        data.trafige_ilk_cikis_tarihi
      ),
      [`${BASE_URI}/extensions/recordDate`]: toISO(data.kayittarih),
      [`${BASE_URI}/extensions/operationDate`]: toISO(data.islemtarihi),

      [`${BASE_URI}/extensions/operationCategory`]: data.tur || undefined,
      [`${BASE_URI}/extensions/separationType`]: data.ayristirmaturu || undefined,
      [`${BASE_URI}/extensions/stockType`]: data.stokturu || undefined,
      [`${BASE_URI}/extensions/manufacturer`]: data.uretici || undefined,
    },
  },

  result: {
    completion: isCompleted,
    success: isCompleted,
    extensions: {
      [`${BASE_URI}/extensions/odometerReading`]: toNumber(data.km),
      [`${BASE_URI}/extensions/materialQuantity`]: toNumber(data.miktar),
      [`${BASE_URI}/extensions/materialCost`]: toNumber(data.tutar),
      [`${BASE_URI}/extensions/discountAmount`]: toNumber(data.indirimlitutar),
      [`${BASE_URI}/extensions/faultCode`]: data.arizakodu || undefined,
    },
  },
};

return { json: statement };
