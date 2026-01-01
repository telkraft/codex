# nlp_constants.py
"""
Türkçe doğal dil sorularında kullanılan sabit sözlükler ve keyword listeleri.

Bu modül:
- intent_router
- mvp_orchestrator
- advanced_intent_router
- canonical_questions (v1 ve v2)

tarafından ORTAK kullanılmak üzere tasarlanmıştır.

2-Katmanlı Mimari (v2):
- INTENT_TRIGGERS: Sorunun KONUSUNU belirler (NE?)
- SHAPE_TRIGGERS: Verinin SUNUMUNU belirler (NASIL?)

Not: Tüm keyword'ler normalize edilmiş formda (ş→s, ı→i, vb.) tutulmalıdır.
     Orijinal Türkçe karakterli versiyonlar da alternatif olarak eklenebilir.
"""

from typing import Dict, List


# ============================================================================
# HARF NORMALİZASYONU
# ============================================================================

REPLACEMENTS = {
    "ı": "i",
    "İ": "i",
    "ş": "s",
    "Ş": "s",
    "ğ": "g",
    "Ğ": "g",
    "ç": "c",
    "Ç": "c",
    "ö": "o",
    "Ö": "o",
    "ü": "u",
    "Ü": "u",
}


# ============================================================================
# TÜRKÇE AY İSİMLERİ
# ============================================================================

MONTH_KEYWORDS = {
    "ocak": 1,
    "subat": 2,
    "mart": 3,
    "nisan": 4,
    "mayis": 5,
    "haziran": 6,
    "temmuz": 7,
    "agustos": 8,
    "eylul": 9,
    "ekim": 10,
    "kasim": 11,
    "aralik": 12,
}

MONTH_NAMES_TR = {
    1: "Ocak",
    2: "Şubat",
    3: "Mart",
    4: "Nisan",
    5: "Mayıs",
    6: "Haziran",
    7: "Temmuz",
    8: "Ağustos",
    9: "Eylül",
    10: "Ekim",
    11: "Kasım",
    12: "Aralık",
}

# Mevsim isimleri (normalize edilmiş)
# ⚠️ Hem İngilizce hem Türkçe normalize key'ler desteklenmeli
#    - lrs_schema.py + lrs_patterns.py → Türkçe key döndürür: "kis", "ilkbahar", "yaz", "sonbahar"
#    - nlp_utils.extract_season() → İngilizce key döndürür: "winter", "spring", "summer", "autumn"
SEASON_NAMES = {
    # İngilizce key'ler (nlp_utils.extract_season çıktısı)
    "winter": "Kış",
    "spring": "İlkbahar",
    "summer": "Yaz",
    "autumn": "Sonbahar",
    # Türkçe normalize key'ler (lrs_schema.py / lrs_patterns.py çıktısı)
    "kis": "Kış",
    "ilkbahar": "İlkbahar",
    "yaz": "Yaz",
    "sonbahar": "Sonbahar",
}


# ============================================================================
# TEMEL DOMAIN KELİME GRUPLARI (Atomic Lists)
# ============================================================================
# Bu listeler diğer composed listeler tarafından kullanılır.
# Tüm kelimeler NORMALIZE edilmiş formda (Türkçe karakterler ASCII'ye çevrilmiş).

# ─────────────────────────────────────────────────────────────────────────────
# MALZEME / PARÇA
# ─────────────────────────────────────────────────────────────────────────────
MATERIAL_BASE_WORDS = [
    "malzeme",
    "parca",
    "malzemeler",
    "parcalar",
    "yedek parca",
]

MATERIAL_NOISE_WORDS = [
    "trend", "trendler", "trendleri",
    "degisim", "degisti", "degisimi",
    "nasil", "nasil degisti", "kullanimi nasil",
    "kullanim", "kullanimi", "kullanimi nasil degisti",
]


MATERIAL_USAGE_SIGNALS = [
    "malzeme kullanim",
    "kullanilan malzemeler",
    "malzeme tuketimi",
    "parca kullanim",
    "malzeme kullanimi",
    "kullanim dagilimi",
    "malzeme dagilimi",
    "hangi malzemeler",
    "hangi malzeme",
    "hangi parcalar",
    "degisen",
    "degistirilen",
    "kullanilan",
]

# ─────────────────────────────────────────────────────────────────────────────
# BAKIM / ONARIM / KONTROL
# ─────────────────────────────────────────────────────────────────────────────
MAINTENANCE_KEYWORDS = [
    "bakim",
    "bakim islemi",
    "bakim sayisi",
    "periyodik bakim",
]

REPAIR_KEYWORDS = [
    "onarim",
    "tamir",
    "tamiri",
]

INSPECTION_KEYWORDS = [
    "kontrol",
    "muayene",
    "inceleme",
]

HISTORY_KEYWORDS = [
    "gecmis",
    "gecmisi",
    "gecmisleri",
    "servis gecmisi",
    "bakim gecmisi",
    "bakim gecmisini",
    "bakim kaydi",
    "bakim kayitlari",
    "kayit",
    "kayitlar",
    "kayitlari",
]

# ─────────────────────────────────────────────────────────────────────────────
# MALİYET / HARCAMA
# ─────────────────────────────────────────────────────────────────────────────
COST_KEYWORDS = [
    "maliyet",
    "harcama",
    "tutar",
    "ucret",
    "fiyat",
    "para",
    "butce",
]

COST_SIGNALS = [
    "toplam maliyet",
    "toplam tutar",
    "toplam harcama",
    "bakim maliyeti",
    "bakim ucreti",
    "ne kadar",
    "kac lira",
    "kac tl",
]

# ─────────────────────────────────────────────────────────────────────────────
# ARIZA / HATA
# ─────────────────────────────────────────────────────────────────────────────
FAULT_KEYWORDS = [
    "ariza",
    "fault",
    "hata",
    "sorun",
    "problem",
    "ariza kodu",
    "hangi arizalar",
    "en sik ariza",
    "ariza dagilim",
    "tekrar eden",
    "tekrarlayan",
]

# ─────────────────────────────────────────────────────────────────────────────
# ARAÇ
# ─────────────────────────────────────────────────────────────────────────────
VEHICLE_KEYWORDS = [
    "arac",
    "araclar",
    "kamyon",
    "otobus",
    "bus",
    "vehicle",
    "plaka",
]

VEHICLE_TYPE_KEYWORDS = [
    "arac tipi",
    "arac tipleri",
    "hangi arac tipi",
    "tip bazinda",
    "tipe gore",
]

VEHICLE_MODEL_KEYWORDS = [
    "arac modeli",
    "arac modelleri",
    "arac modellerinin",  # 🆕 Possessive
    "hangi model",
    "model bazinda",
    "modele gore",
    "modellere gore",  # 🆕 Plural
    "modellerinin",    # 🆕 Possessive
    "modeli",
]

# Backward compatibility için
VEHICLE_PHRASES = VEHICLE_KEYWORDS
VEHICLE_TYPE_PHRASES = VEHICLE_TYPE_KEYWORDS
VEHICLE_MODEL_PHRASES = VEHICLE_MODEL_KEYWORDS
VEHICLE_LIKE_KEYWORDS = VEHICLE_KEYWORDS + ["musteri"]

# ─────────────────────────────────────────────────────────────────────────────
# MÜŞTERİ
# ─────────────────────────────────────────────────────────────────────────────
CUSTOMER_KEYWORDS = [
    "musteri",
    "musteriler",
    "musterinin",
    "customer",
    "firma",
    "sirket",
]

# Backward compatibility
CUSTOMER_PHRASES = CUSTOMER_KEYWORDS

# ─────────────────────────────────────────────────────────────────────────────
# SERVİS / LOKASYON
# ─────────────────────────────────────────────────────────────────────────────
SERVICE_KEYWORDS = [
    "servis",
    "lokasyon",
    "location",
    "sube",
    "servis noktasi",
]

# Backward compatibility
SERVICE_PHRASES = SERVICE_KEYWORDS

# ─────────────────────────────────────────────────────────────────────────────
# ZAMAN / TARİH
# ─────────────────────────────────────────────────────────────────────────────
TIME_KEYWORDS = [
    "yil",
    "yillik",
    "ay",
    "aylik",
    "hafta",
    "haftalik",
    "gun",
    "gunluk",
    "tarih",
    "donem",
    "periyod",
]

TIME_RANGE_KEYWORDS = [
    "son",
    "son 12 ay",
    "son 1 yil",
    "son 3 yil",
    "gecen yil",
    "bu yil",
    "bu ay",
]

# ─────────────────────────────────────────────────────────────────────────────
# MEVSİM
# ─────────────────────────────────────────────────────────────────────────────
SEASON_KEYWORDS = [
    "mevsim",
    "sezon",
    "kis",
    "yaz",
    "bahar",
    "ilkbahar",
    "sonbahar",
    "mevsimsel",
    "seasonal",
]

# Backward compatibility
SEASONAL_SIGNALS = SEASON_KEYWORDS

# ─────────────────────────────────────────────────────────────────────────────
# SONRAKİ BAKIM / PATTERN
# ─────────────────────────────────────────────────────────────────────────────
NEXT_MAINTENANCE_KEYWORDS = [
    "bir sonraki bakimda",
    "sonraki bakimda",
    "bir sonraki serviste",
    "sonraki serviste",
    "siradaki",
    "sonrasinda",
    "ardindan",
    "ne degisiyor",
    "ne geliyor",
]

# Backward compatibility
NEXT_MAINTENANCE_SIGNALS = NEXT_MAINTENANCE_KEYWORDS


# ============================================================================
# SHAPE TETİKLEYİCİLERİ (NASIL?)
# ============================================================================
# Bu listeler çıktı formatını / sunum şeklini belirler.

# ─────────────────────────────────────────────────────────────────────────────
# TOP_LIST: En çok/en az N tane
# ─────────────────────────────────────────────────────────────────────────────
TOP_LIST_KEYWORDS = [
    "en cok",
    "en fazla",
    "en sik",
    "en yuksek",
    "en dusuk",
    "en az",
    "ilk",
    "top",
    "sirala",
    "siralama",
    "listele",
]

# Backward compatibility
TOP_SIGNALS = [
    "en cok",
    "en fazla",
    "en sik",
    "top ",
]

TOP_ENTITY_EXTRA_SIGNALS = [
    "ilk",
    "en yuksek",
    "en dusuk",
    "en az",
]

TOP_ENTITY_SIGNALS = TOP_SIGNALS + TOP_ENTITY_EXTRA_SIGNALS

# ─────────────────────────────────────────────────────────────────────────────
# TIME_SERIES: Zaman serisi (yıl/ay/hafta bazında)
# ─────────────────────────────────────────────────────────────────────────────
TIME_SERIES_KEYWORDS = [
    "yillara",
    "aylara",
    "haftalara",
    "gunlere",
    "yillara gore",
    "aylara gore",
    "zamana gore",
    "zaman icinde",
    "nasil degisti",
    "nasil degisiyor",
    "degisim",
    "trend",
    "gunlere gore",
    "gun bazinda",
    "gunluk dagilim",
    "haftanin gunleri",
    "haftanin gunlerine gore",
    # 🆕 Possessive suffix variants (günlerine)
    "gunlerine gore",
    "gunlerine",
    "gunlerinde",
]

# Backward compatibility
TIME_SERIES_SIGNALS = TIME_SERIES_KEYWORDS
TIME_SIGNALS = TIME_SERIES_KEYWORDS + SEASON_KEYWORDS

# ─────────────────────────────────────────────────────────────────────────────
# SEASONAL: Mevsimsel gruplandırma
# ─────────────────────────────────────────────────────────────────────────────
SEASONAL_SHAPE_KEYWORDS = [
    "mevsim",
    "sezon",
    "kis",
    "yaz",
    "bahar",
    "sonbahar",
    "mevsime gore",
    "mevsimlere gore",
    "mevsimsel",
    "hangi mevsim",
]

# ─────────────────────────────────────────────────────────────────────────────
# DISTRIBUTION: Dağılım / oran
# ─────────────────────────────────────────────────────────────────────────────
DISTRIBUTION_KEYWORDS = [
    "dagilim",
    "dagilimi",
    "dagiliyor",
    "oran",
    "orani",
    "yuzde",
    "yuzdesi",
    "distribution",
    "nasil dagiliyor",
    # 🆕 Count/quantity sinyalleri de dağılım sorusu olabilir
    "sayilari", "sayisi", "sayi",
    "adetleri", "adeti", "adet",
]

# Backward compatibility
DISTRIBUTION_SIGNALS = DISTRIBUTION_KEYWORDS

# ─────────────────────────────────────────────────────────────────────────────
# PIVOT: İki boyutlu çapraz tablo
# ─────────────────────────────────────────────────────────────────────────────
PIVOT_KEYWORDS = [
    "gore dagilimi",
    "bazinda dagilimi",
    "capraz",
    "pivot",
    "matris",
    "tablo",
    "ve gore",
    "x ve y",
]

# ─────────────────────────────────────────────────────────────────────────────
# TOP_PER_GROUP: Her grup için en çok N
# ─────────────────────────────────────────────────────────────────────────────
TOP_PER_GROUP_KEYWORDS = [
    # Genel pattern'ler
    "her bir",
    "her biri icin",
    "bazinda en",
    "gore en",
    
    # Mevsim pattern'leri (YENİ)
    "her mevsim icin",
    "mevsimlere gore en",
    "mevsime gore en",
    "mevsimde en",
    "mevsimlerde en",
    
    # Model pattern'leri (GENİŞLETİLDİ)
    "her model icin",
    "modellere gore en",
    "modellerine gore en",
    "modellerde en",
    
    # Tip pattern'leri (GENİŞLETİLDİ)
    "her tip icin",
    "tiplere gore en",
    "tiplerine gore en",
    
    # Araç pattern'leri
    "her arac icin",
]

# ─────────────────────────────────────────────────────────────────────────────
# DETAIL_LIST: Detaylı kayıt listesi
# ─────────────────────────────────────────────────────────────────────────────
DETAIL_LIST_KEYWORDS = [
    "listele",
    "goster",
    "kayitlar",
    "kayitlari",
    "detay",
    "detayli",
    "tum",
    "hepsi",
    "tamamini",
]

# ─────────────────────────────────────────────────────────────────────────────
# COMPARISON: Karşılaştırma
# ─────────────────────────────────────────────────────────────────────────────
COMPARISON_KEYWORDS = [
    "karsilastir",
    "compare",
    "fark",
    "farki",
    "arasinda",
    "mi daha",
    "ile karsilastir",
    "vs",
    "versus",
]

# Backward compatibility
COMPARISON_SIGNALS = COMPARISON_KEYWORDS

# ─────────────────────────────────────────────────────────────────────────────
# TREND: Artış/azalış analizi
# ─────────────────────────────────────────────────────────────────────────────
TREND_KEYWORDS = [
    "trend",
    "artis",
    "dusus",
    "azalis",
    "yukselis",
    "gerileme",
    "artan",
    "azalan",
    "degisim",
    "fiyat artisi",
    "maliyet artisi",
]

# ─────────────────────────────────────────────────────────────────────────────
# SEQUENCE: Ardışık ilişki
# ─────────────────────────────────────────────────────────────────────────────
SEQUENCE_KEYWORDS = [
    "sonra",
    "ardindan",
    "onu takiben",
    "sonrasinda",
    "akabinde",
    "ne geliyor",
    "ne degisiyor",
]

# ─────────────────────────────────────────────────────────────────────────────
# SUMMARY: Özet / aggregation
# ─────────────────────────────────────────────────────────────────────────────
SUMMARY_KEYWORDS = [
    "toplam",
    "ortalama",
    "kac tane",
    "ne kadar",
    "ozet",
    "genel",
    "butun",
]


# ============================================================================
# 2-KATMANLI TETİKLEYİCİ HARİTALARI
# ============================================================================

# ─────────────────────────────────────────────────────────────────────────────
# INTENT_TRIGGERS: Sorunun KONUSUNU belirler (NE?)
# ─────────────────────────────────────────────────────────────────────────────
INTENT_TRIGGERS: Dict[str, List[str]] = {
    
    # Operasyonel Analiz
    "material_usage": (
        MATERIAL_BASE_WORDS 
        + MATERIAL_USAGE_SIGNALS
    ),
    
    "cost_analysis": (
        COST_KEYWORDS 
        + COST_SIGNALS
    ),
    
    "fault_analysis": FAULT_KEYWORDS,
    
    "maintenance_history": (
        HISTORY_KEYWORDS 
        + MAINTENANCE_KEYWORDS
    ),
    
    # Varlık Bazlı Analiz
    "vehicle_analysis": (
        VEHICLE_KEYWORDS 
        + VEHICLE_TYPE_KEYWORDS 
        + VEHICLE_MODEL_KEYWORDS
    ),
    
    "customer_analysis": CUSTOMER_KEYWORDS,
    
    "service_analysis": SERVICE_KEYWORDS,
    
    # İlişkisel Analiz
    "next_maintenance": NEXT_MAINTENANCE_KEYWORDS,
    
    "pattern_analysis": (
        NEXT_MAINTENANCE_KEYWORDS 
        + SEQUENCE_KEYWORDS
    ),
    
    # Karşılaştırma
    "comparison_analysis": COMPARISON_KEYWORDS,
}

# ─────────────────────────────────────────────────────────────────────────────
# SHAPE_TRIGGERS: Verinin SUNUMUNU belirler (NASIL?)
# ─────────────────────────────────────────────────────────────────────────────
SHAPE_TRIGGERS: Dict[str, List[str]] = {
    
    # Liste Bazlı
    "top_list": TOP_LIST_KEYWORDS,
    "detail_list": DETAIL_LIST_KEYWORDS,
    
    # Zaman Bazlı
    "time_series": TIME_SERIES_KEYWORDS,
    "seasonal": SEASONAL_SHAPE_KEYWORDS,
    
    # Dağılım / Oran
    "distribution": DISTRIBUTION_KEYWORDS,
    "pivot": PIVOT_KEYWORDS,
    
    # Grup İçi
    "top_per_group": TOP_PER_GROUP_KEYWORDS,
    
    # Karşılaştırma
    "comparison": COMPARISON_KEYWORDS,
    
    # Pattern
    "sequence": SEQUENCE_KEYWORDS,
    "trend": TREND_KEYWORDS,
    
    # Aggregation
    "summary": SUMMARY_KEYWORDS,
}


# ============================================================================
# DIMENSION TETİKLEYİCİLERİ
# ============================================================================
# Hangi boyutun sorgulandığını anlamak için

DIMENSION_TRIGGERS: Dict[str, List[str]] = {
    "materialName": MATERIAL_BASE_WORDS + ["malzeme", "parca", "hangi malzeme"],
    "faultCode": ["ariza", "ariza kodu", "hata kodu", "fault"],
    "vehicle": ["plaka", "arac", "aracin", "bu arac"],
    "vehicleType": VEHICLE_TYPE_KEYWORDS,
    "vehicleModel": VEHICLE_MODEL_KEYWORDS,
    "customer": CUSTOMER_KEYWORDS,
    "serviceLocation": SERVICE_KEYWORDS,
    "verbType": ["bakim", "onarim", "kontrol", "islem", "islem tipi"],
    "year": ["yil", "yilda", "yilinda", "yili"],
    "month": ["ay", "ayda", "ayinda", "ayi"],
    "season": SEASON_KEYWORDS,
    "dayOfWeek": [
        "gunlere gore", "gunlere", "gun bazinda", "gunluk",
        # 🆕 Possessive suffix variants (günlerine, günlerinde)
        "gunlerine gore", "gunlerine", "gunlerinde",
        "haftanin gunu", "haftanin gunleri", 
        "hafta ici", "hafta sonu",
        "pazartesi", "sali", "carsamba", "persembe", "cuma", "cumartesi", "pazar",
    ],
}


# ============================================================================
# BACKWARD COMPATIBILITY: ESKİ QUESTION_SIGNALS
# ============================================================================
# v1 canonical_questions.py ile uyumluluk için korunuyor.
# Yeni kodlarda INTENT_TRIGGERS ve SHAPE_TRIGGERS kullanılmalı.

QUESTION_SIGNALS: Dict[str, List[str]] = {
    "material_usage": MATERIAL_USAGE_SIGNALS,
    "cost_analysis": COST_KEYWORDS + COST_SIGNALS,
    "maintenance_history": HISTORY_KEYWORDS + MAINTENANCE_KEYWORDS,
    "fault_analysis": FAULT_KEYWORDS,
    "vehicle_based": VEHICLE_KEYWORDS,
    "customer_based": CUSTOMER_KEYWORDS,
    "service_based": SERVICE_KEYWORDS,
    "time_series": TIME_SERIES_KEYWORDS,
    "seasonal": SEASON_KEYWORDS,
    "top_entities": TOP_LIST_KEYWORDS,
    "distribution": DISTRIBUTION_KEYWORDS,
    "comparison": COMPARISON_KEYWORDS,
    "pattern": NEXT_MAINTENANCE_KEYWORDS,
    "next_maintenance": NEXT_MAINTENANCE_KEYWORDS,
}


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_intent_triggers(intent_name: str) -> List[str]:
    """Belirli bir intent için trigger listesini döner."""
    return INTENT_TRIGGERS.get(intent_name, [])


def get_shape_triggers(shape_name: str) -> List[str]:
    """Belirli bir shape için trigger listesini döner."""
    return SHAPE_TRIGGERS.get(shape_name, [])


def get_dimension_triggers(dimension_name: str) -> List[str]:
    """Belirli bir dimension için trigger listesini döner."""
    return DIMENSION_TRIGGERS.get(dimension_name, [])


def get_all_intent_names() -> List[str]:
    """Tüm intent isimlerini döner."""
    return list(INTENT_TRIGGERS.keys())


def get_all_shape_names() -> List[str]:
    """Tüm shape isimlerini döner."""
    return list(SHAPE_TRIGGERS.keys())


# ============================================================================
# MODULE TEST
# ============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("NLP CONSTANTS - 2-Katmanlı Mimari")
    print("=" * 70)
    
    print("\n📌 INTENT TRIGGERS:")
    for intent, triggers in INTENT_TRIGGERS.items():
        print(f"  {intent}: {len(triggers)} keyword")
    
    print("\n📌 SHAPE TRIGGERS:")
    for shape, triggers in SHAPE_TRIGGERS.items():
        print(f"  {shape}: {len(triggers)} keyword")
    
    print("\n📌 DIMENSION TRIGGERS:")
    for dim, triggers in DIMENSION_TRIGGERS.items():
        print(f"  {dim}: {len(triggers)} keyword")
    
    # Toplam unique keyword sayısı
    all_intent_kw = set()
    for kws in INTENT_TRIGGERS.values():
        all_intent_kw.update(kws)
    
    all_shape_kw = set()
    for kws in SHAPE_TRIGGERS.values():
        all_shape_kw.update(kws)
    
    print(f"\n📊 ÖZET:")
    print(f"  Toplam Intent: {len(INTENT_TRIGGERS)}")
    print(f"  Toplam Shape: {len(SHAPE_TRIGGERS)}")
    print(f"  Unique Intent Keywords: {len(all_intent_kw)}")
    print(f"  Unique Shape Keywords: {len(all_shape_kw)}")