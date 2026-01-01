"""
prompt_ontology.py
==================

LLM'e gönderilen tabloların semantik bağlamını yöneten modül.

Bu modül şunları içerir:
- Kolon tanımları ve açıklamaları (COLUMN_DEFS_EXTENDED)
- Intent açıklamaları (INTENT_DESCRIPTIONS)
- Shape açıklamaları (SHAPE_DESCRIPTIONS)
- Tablo bağlam bloğu oluşturma fonksiyonları

Promptever felsefesi: "Veri değil, deneyim. Tablo değil, bağlam."
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional


# ============================================================================
# KOLON TANIMLARI (Genişletilmiş Semantik Metadata)
# ============================================================================

COLUMN_DEFS_EXTENDED: Dict[str, Dict[str, Any]] = {
    # ─────────────────────────────────────────────────────────────────────────
    # ARAÇ BOYUTLARI
    # ─────────────────────────────────────────────────────────────────────────
    "vehicleType": {
        "label_tr": "Araç Tipi",
        "description": "Aracın kategorisi (TGS, TGX, TGE vb.)",
        "semantic_type": "dimension",
        "example": "TGS",
    },
    "vehicleModel": {
        "label_tr": "Araç Modeli",
        "description": "Araç tipi + motor/şasi kombinasyonu",
        "semantic_type": "dimension",
        "example": "TGS 18.420",
    },
    "vehicle": {
        "label_tr": "Araç",
        "description": "Tekil araç tanımlayıcısı (plaka veya ID)",
        "semantic_type": "identifier",
        "example": "34ABC123",
    },
    "vehicleId": {
        "label_tr": "Araç ID",
        "description": "Araç için benzersiz sistem kimliği",
        "semantic_type": "identifier",
        "example": "70886",
    },
    
    # ─────────────────────────────────────────────────────────────────────────
    # MÜŞTERİ VE SERVİS BOYUTLARI
    # ─────────────────────────────────────────────────────────────────────────
    "customerId": {
        "label_tr": "Müşteri",
        "description": "Araç sahibi veya filo operatörü",
        "semantic_type": "dimension",
        "example": "ABC Lojistik",
    },
    "serviceLocation": {
        "label_tr": "Servis Lokasyonu",
        "description": "Bakımın yapıldığı MAN yetkili servis noktası",
        "semantic_type": "dimension",
        "example": "İstanbul Anadolu",
    },
    
    # ─────────────────────────────────────────────────────────────────────────
    # MALZEME BOYUTLARI
    # ─────────────────────────────────────────────────────────────────────────
    "materialName": {
        "label_tr": "Malzeme",
        "description": "Bakımda kullanılan yedek parça veya sarf malzeme adı",
        "semantic_type": "dimension",
        "example": "YAKIT FILTRE ELEMANI CONTALI",
    },
    "materialFamily": {
        "label_tr": "Malzeme Ailesi",
        "description": "Malzemelerin gruplandığı kategori (Motor, Fren, Elektrik vb.)",
        "semantic_type": "dimension",
        "example": "MOTOR",
    },
    "materialCode": {
        "label_tr": "Malzeme Kodu",
        "description": "Malzemenin benzersiz parça numarası",
        "semantic_type": "identifier",
        "example": "51.12503-0081",
    },
    "material": {
        "label_tr": "Malzeme",
        "description": "Bakımda kullanılan yedek parça (pattern analizi için)",
        "semantic_type": "dimension",
        "example": "MOTOR YAGI",
    },
    
    # ─────────────────────────────────────────────────────────────────────────
    # ARIZA VE İŞLEM BOYUTLARI
    # ─────────────────────────────────────────────────────────────────────────
    "faultCode": {
        "label_tr": "Arıza Kodu",
        "description": "Standart arıza tanımlama kodu",
        "semantic_type": "dimension",
        "example": "P0420",
    },
    "verbType": {
        "label_tr": "İşlem Tipi",
        "description": "Yapılan bakım/onarım türü (bakım, arıza, değişim vb.)",
        "semantic_type": "dimension",
        "example": "bakim",
    },
    
    # ─────────────────────────────────────────────────────────────────────────
    # ZAMAN BOYUTLARI
    # ─────────────────────────────────────────────────────────────────────────
    "year": {
        "label_tr": "Yıl",
        "description": "İşlemin yapıldığı yıl",
        "semantic_type": "time_dimension",
        "example": "2023",
    },
    "month": {
        "label_tr": "Ay",
        "description": "İşlemin yapıldığı ay (1-12)",
        "semantic_type": "time_dimension",
        "example": "6",
    },
    "season": {
        "label_tr": "Mevsim",
        "description": "İşlemin yapıldığı mevsim (ilkbahar, yaz, sonbahar, kış)",
        "semantic_type": "time_dimension",
        "example": "kis",
    },
    "date": {
        "label_tr": "Tarih",
        "description": "İşlem tarihi (YYYY-MM-DD formatında)",
        "semantic_type": "time_dimension",
        "example": "2023-12-15",
    },
    "week": {
        "label_tr": "Hafta",
        "description": "Yılın kaçıncı haftası",
        "semantic_type": "time_dimension",
        "example": "42",
    },
    
    # ─────────────────────────────────────────────────────────────────────────
    # TEMEL METRİKLER
    # ─────────────────────────────────────────────────────────────────────────
    "count": {
        "label_tr": "Adet",
        "description": "İşlem veya kayıt sayısı",
        "semantic_type": "metric",
        "aggregation": "SUM",
        "interpretation": "Toplam tekrar sayısını gösterir",
    },
    "quantity": {
        "label_tr": "Miktar",
        "description": "Kullanılan malzeme miktarı (adet veya birim)",
        "semantic_type": "metric",
        "aggregation": "SUM",
    },
    "cost": {
        "label_tr": "Maliyet",
        "description": "TL cinsinden işlem maliyeti",
        "semantic_type": "metric",
        "aggregation": "SUM",
        "unit": "TL",
    },
    "km": {
        "label_tr": "Km",
        "description": "Araç kilometre değeri",
        "semantic_type": "metric",
        "unit": "km",
    },
    
    # ─────────────────────────────────────────────────────────────────────────
    # AGGREGE METRİKLER
    # ─────────────────────────────────────────────────────────────────────────
    "sum_cost": {
        "label_tr": "Toplam Maliyet",
        "description": "Grup için toplam maliyet",
        "semantic_type": "metric",
        "aggregation": "SUM",
        "unit": "TL",
    },
    "avg_cost": {
        "label_tr": "Ortalama Maliyet",
        "description": "Grup için ortalama maliyet",
        "semantic_type": "metric",
        "aggregation": "AVG",
        "unit": "TL",
    },
    "avg_km": {
        "label_tr": "Ortalama Km",
        "description": "Grup için ortalama kilometre",
        "semantic_type": "metric",
        "aggregation": "AVG",
        "unit": "km",
    },
    "sum_quantity": {
        "label_tr": "Toplam Miktar",
        "description": "Grup için toplam kullanım miktarı",
        "semantic_type": "metric",
        "aggregation": "SUM",
    },
    
    # ─────────────────────────────────────────────────────────────────────────
    # TREND METRİKLERİ
    # ─────────────────────────────────────────────────────────────────────────
    "firstDate": {
        "label_tr": "İlk Tarih",
        "description": "Trend döneminin başlangıç tarihi",
        "semantic_type": "time_dimension",
    },
    "lastDate": {
        "label_tr": "Son Tarih",
        "description": "Trend döneminin bitiş tarihi",
        "semantic_type": "time_dimension",
    },
    "firstPrice": {
        "label_tr": "İlk Fiyat",
        "description": "Dönem başındaki birim fiyat",
        "semantic_type": "metric",
        "unit": "TL",
    },
    "lastPrice": {
        "label_tr": "Son Fiyat",
        "description": "Dönem sonundaki birim fiyat",
        "semantic_type": "metric",
        "unit": "TL",
    },
    "changeAbs": {
        "label_tr": "Fark",
        "description": "İlk ve son değer arasındaki mutlak fark",
        "semantic_type": "metric",
        "interpretation": "Pozitif = artış, Negatif = azalış",
    },
    "changePct": {
        "label_tr": "Değişim (%)",
        "description": "İlk ve son değer arasındaki yüzdelik değişim",
        "semantic_type": "metric",
        "unit": "%",
        "interpretation": "Pozitif = fiyat artışı, Negatif = fiyat düşüşü",
    },
    "observations": {
        "label_tr": "Gözlem Sayısı",
        "description": "Trend hesaplamasında kullanılan veri noktası sayısı",
        "semantic_type": "metric",
        "interpretation": "Düşük değer (< 5) = trend güvenilirliği düşük",
    },
    "avgChangePct": {
        "label_tr": "Ort. Değişim (%)",
        "description": "Grup için ortalama yüzdelik değişim",
        "semantic_type": "metric",
        "unit": "%",
    },
    "materialsCount": {
        "label_tr": "Malzeme Sayısı",
        "description": "Gruptaki benzersiz malzeme sayısı",
        "semantic_type": "metric",
    },
    
    # ─────────────────────────────────────────────────────────────────────────
    # PATTERN / İLİŞKİ METRİKLERİ
    # ─────────────────────────────────────────────────────────────────────────
    "ratio": {
        "label_tr": "Oran (%)",
        "description": "Birlikte görülme oranı veya yüzdesel pay",
        "semantic_type": "metric",
        "unit": "%",
        "interpretation": "Referans malzemeden sonra bu malzemenin görülme sıklığı",
    },
    "probability": {
        "label_tr": "Olasılık (%)",
        "description": "Tahmin edilen görülme olasılığı",
        "semantic_type": "metric",
        "unit": "%",
    },
    "percentage": {
        "label_tr": "Yüzde (%)",
        "description": "Toplam içindeki yüzdesel pay",
        "semantic_type": "metric",
        "unit": "%",
    },
    
    # ─────────────────────────────────────────────────────────────────────────
    # GENERIC ALANLAR
    # ─────────────────────────────────────────────────────────────────────────
    "entity": {
        "label_tr": "Varlık",
        "description": "Analiz edilen nesne (araç, malzeme, müşteri vb.)",
        "semantic_type": "dimension",
    },
    "entity_type": {
        "label_tr": "Varlık Tipi",
        "description": "Varlığın kategorisi",
        "semantic_type": "dimension",
    },
    "service": {
        "label_tr": "Servis",
        "description": "Servis noktası veya servis kaydı",
        "semantic_type": "dimension",
    },
}


# ============================================================================
# INTENT AÇIKLAMALARI (Sorunun KONUSU - NE soruluyor?)
# ============================================================================

INTENT_DESCRIPTIONS: Dict[str, Dict[str, Any]] = {
    "material_usage": {
        "label_tr": "Malzeme Kullanım Analizi",
        "purpose": "Bakım/onarımda kullanılan malzemelerin analizi",
        "key_questions": [
            "Hangi malzemeler kullanılıyor?",
            "Tüketim miktarları ve sıklıkları nedir?",
        ],
    },
    "cost_analysis": {
        "label_tr": "Maliyet Analizi",
        "purpose": "Bakım maliyetlerinin boyutlar üzerinden incelenmesi",
        "key_questions": [
            "Maliyet nereye gidiyor?",
            "En pahalı kalemler ve trendler neler?",
        ],
    },
    "fault_analysis": {
        "label_tr": "Arıza Analizi",
        "purpose": "Arıza kodları ve dağılımlarının incelenmesi",
        "key_questions": [
            "Hangi arızalar sık görülüyor?",
            "Arıza paternleri ve tekrar oranları neler?",
        ],
    },
    "maintenance_history": {
        "label_tr": "Bakım Geçmişi",
        "purpose": "Genel bakım/onarım kayıtlarının analizi",
        "key_questions": [
            "Bakım geçmişi nasıl?",
            "Zaman içinde değişim var mı?",
        ],
    },
    "vehicle_analysis": {
        "label_tr": "Araç Analizi",
        "purpose": "Tekil veya grup araç bazında bakım geçmişi",
        "key_questions": [
            "Aracın durumu nasıl?",
            "Model bazında farklar neler?",
        ],
    },
    "customer_analysis": {
        "label_tr": "Müşteri Analizi",
        "purpose": "Müşteri bazında bakım paternlerinin incelenmesi",
        "key_questions": [
            "Hangi müşteriler daha yoğun?",
            "Müşteri segmentleri arası farklar neler?",
        ],
    },
    "service_analysis": {
        "label_tr": "Servis Analizi",
        "purpose": "Servis lokasyonları bazında performans analizi",
        "key_questions": [
            "Hangi servisler daha yoğun?",
            "Servis verimliliği nasıl?",
        ],
    },
    "pattern_analysis": {
        "label_tr": "Patern Analizi",
        "purpose": "Tekrar eden kalıpların ve ilişkilerin tespiti",
        "key_questions": [
            "Hangi paternler var?",
            "Birlikte görülen durumlar neler?",
        ],
    },
    "next_maintenance": {
        "label_tr": "Sonraki Bakım Tahmini",
        "purpose": "Ardışık bakım paternlerinin analizi",
        "key_questions": [
            "Bu malzemeden sonra ne değişiyor?",
            "Birlikte değişen parçalar hangileri?",
        ],
    },
    "comparison_analysis": {
        "label_tr": "Karşılaştırma Analizi",
        "purpose": "İki veya daha fazla varlığın karşılaştırılması",
        "key_questions": [
            "Aralarındaki fark nedir?",
            "Hangisi daha iyi/kötü performans gösteriyor?",
        ],
    },
}


# ============================================================================
# SHAPE AÇIKLAMALARI (Verinin SUNUMU - NASIL gösterilecek?)
# ============================================================================

SHAPE_DESCRIPTIONS: Dict[str, Dict[str, str]] = {
    "top_list": {
        "label_tr": "Sıralı Liste",
        "format": "En yüksek/düşük N kayıt",
        "interpretation": (
            "Sıralama metriğine göre yorumlanır. "
            "İlk sıradakiler en baskın/yoğun olanları temsil eder."
        ),
    },
    "detail_list": {
        "label_tr": "Detay Listesi",
        "format": "Tekil kayıtların detaylı listesi",
        "interpretation": (
            "Her satır bir tekil olayı/kaydı temsil eder. "
            "Kronolojik veya önem sırasına göre sıralanmış olabilir."
        ),
    },
    "time_series": {
        "label_tr": "Zaman Serisi",
        "format": "Dönem bazında (yıl/ay/hafta) gruplandırılmış",
        "interpretation": (
            "Trend yönü ve mevsimsellik analiz edilebilir. "
            "Ardışık dönemler arası farklar önemlidir."
        ),
    },
    "seasonal": {
        "label_tr": "Mevsimsel Dağılım",
        "format": "Mevsim bazında gruplandırılmış",
        "interpretation": (
            "Mevsimler arası farklar ve yoğunlaşma dönemleri. "
            "Kış/yaz gibi mevsimsel paternleri gösterir."
        ),
    },
    "distribution": {
        "label_tr": "Dağılım",
        "format": "Yüzdesel pay tablosu",
        "interpretation": (
            "Toplamın nasıl bölündüğünü gösterir. "
            "Yüzdeler 100'e tamamlanır."
        ),
    },
    "pivot": {
        "label_tr": "Pivot Tablo",
        "format": "İki boyutlu çapraz tablo",
        "interpretation": (
            "Satır ve sütun boyutlarının kesişimindeki değerler. "
            "İki boyut arasındaki ilişkiyi gösterir."
        ),
    },
    "top_per_group": {
        "label_tr": "Grup Başına En Çok",
        "format": "Her grup için en yüksek N kayıt",
        "interpretation": (
            "Her grup kendi içinde sıralanmıştır. "
            "Gruplar arası karşılaştırma yapılabilir."
        ),
    },
    "comparison": {
        "label_tr": "Karşılaştırma",
        "format": "Varlıklar arası metrik karşılaştırması",
        "interpretation": (
            "Aynı metrikler farklı varlıklar için yan yana gösterilir. "
            "Farklar ve oranlar değerlendirilebilir."
        ),
    },
    "sequence": {
        "label_tr": "Ardışık İlişki",
        "format": "Referans → Sonraki ilişki tablosu",
        "interpretation": (
            "ratio/probability değeri birlikte görülme sıklığını gösterir. "
            "Yüksek oran = güçlü ardışık ilişki."
        ),
    },
    "trend": {
        "label_tr": "Trend Analizi",
        "format": "Değişim oranları tablosu (ilk→son)",
        "interpretation": (
            "changePct pozitif = artış, negatif = azalış. "
            "observations düşükse trend güvenilirliği düşüktür."
        ),
    },
    "summary": {
        "label_tr": "Özet",
        "format": "Tek veya birkaç aggrege değer",
        "interpretation": (
            "Genel durum özeti. "
            "Detay görmek için daha spesifik sorgu gerekir."
        ),
    },
}


# ============================================================================
# TABLO BAĞLAM FONKSİYONLARI
# ============================================================================

def get_column_label(column_key: str, label_map: Optional[Dict[str, str]] = None) -> str:
    """Kolon key'ini Türkçe label'a çevirir."""
    if label_map and column_key in label_map:
        return label_map[column_key]
    
    col_def = COLUMN_DEFS_EXTENDED.get(column_key, {})
    return col_def.get("label_tr", column_key)


def get_column_description(column_key: str) -> Dict[str, Any]:
    """Kolon için tam açıklama bilgisi döner."""
    return COLUMN_DEFS_EXTENDED.get(column_key, {
        "label_tr": column_key,
        "description": "Veri alanı",
        "semantic_type": "unknown",
    })


def build_table_context_block(
    question_type: str,
    output_shape: str,
    user_query: str,
    columns_in_table: List[str],
    label_map: Optional[Dict[str, str]] = None,
    cq_description: Optional[str] = None,
    cq_examples: Optional[List[str]] = None,
    applied_filters: Optional[Dict[str, Any]] = None,
    period_info: Optional[str] = None,
) -> str:
    """
    LLM'e gönderilecek tablo bağlam bloğunu oluşturur.
    
    Bu fonksiyon, tablonun:
    - Neden hazırlandığını (intent + shape)
    - Her kolonun ne anlama geldiğini
    - Nasıl yorumlanması gerektiğini
    açıklayan bir metin bloğu üretir.
    
    Args:
        question_type: Intent enum değeri (örn: "material_usage")
        output_shape: Shape enum değeri (örn: "top_list")
        user_query: Kullanıcının orijinal sorusu
        columns_in_table: Tablodaki kolon isimleri
        label_map: Kolon key → Türkçe label mapping (opsiyonel)
        cq_description: CanonicalQuestion'dan gelen açıklama (opsiyonel)
        cq_examples: CanonicalQuestion'dan gelen örnek sorular (opsiyonel)
        applied_filters: Uygulanan filtreler (opsiyonel)
        period_info: Dönem bilgisi (opsiyonel)
    
    Returns:
        LLM prompt'una eklenecek bağlam bloğu (markdown formatında)
    """
    
    # 1. Intent açıklaması
    intent_info = INTENT_DESCRIPTIONS.get(question_type, {})
    intent_label = intent_info.get("label_tr", question_type)
    intent_purpose = intent_info.get("purpose", "Genel analiz")
    
    # 2. Shape açıklaması
    shape_info = SHAPE_DESCRIPTIONS.get(output_shape, {})
    shape_label = shape_info.get("label_tr", output_shape)
    shape_format = shape_info.get("format", "Tablo formatı")
    shape_interpretation = shape_info.get("interpretation", "")
    
    # 3. Tablo amacı
    if cq_description:
        table_purpose = cq_description
    else:
        table_purpose = f"{intent_label} - {shape_label}"
    
    # 4. Kolon açıklamaları
    col_descriptions = []
    dimensions = []
    metrics = []
    
    for col in columns_in_table:
        col_def = COLUMN_DEFS_EXTENDED.get(col, {})
        
        # Label belirle
        if label_map and col in label_map:
            label = label_map[col]
        else:
            label = col_def.get("label_tr", col)
        
        desc = col_def.get("description", "Veri alanı")
        sem_type = col_def.get("semantic_type", "")
        unit = col_def.get("unit", "")
        interp = col_def.get("interpretation", "")
        
        # Kolon satırı oluştur
        col_line = f"- **{label}** (`{col}`): {desc}"
        
        # Ek bilgiler
        extras = []
        if unit:
            extras.append(f"Birim: {unit}")
        if sem_type == "metric":
            extras.append("METRİK")
            metrics.append(label)
        elif sem_type == "dimension":
            extras.append("BOYUT")
            dimensions.append(label)
        elif sem_type == "time_dimension":
            extras.append("ZAMAN")
            dimensions.append(label)
        elif sem_type == "identifier":
            extras.append("KİMLİK")
            dimensions.append(label)
        
        if extras:
            col_line += f" [{', '.join(extras)}]"
        
        if interp:
            col_line += f" → _{interp}_"
        
        col_descriptions.append(col_line)
    
    # 5. Filtre özeti
    filter_text = ""
    if applied_filters:
        filter_items = []
        for k, v in applied_filters.items():
            if v is not None and v != "":
                # Filtre key'ini label'a çevir
                clean_key = k.replace("_contains", "").replace("_eq", "").replace("_gte", "").replace("_lte", "")
                if label_map and clean_key in label_map:
                    flabel = label_map[clean_key]
                else:
                    flabel = get_column_label(clean_key)
                filter_items.append(f"{flabel}={v}")
        if filter_items:
            filter_text = f"\n**Uygulanan Filtreler:** {', '.join(filter_items)}"
    
    # 6. Dönem bilgisi
    period_text = ""
    if period_info:
        period_text = f"\n**Analiz Dönemi:** {period_info}"
    
    # 7. Gruplandırma özeti
    grouping_text = ""
    if dimensions:
        grouping_text = f"\n**Gruplama Boyutları:** {', '.join(dimensions)}"
    if metrics:
        grouping_text += f"\n**Hesaplanan Metrikler:** {', '.join(metrics)}"
    
    # 8. Örnek sorular
    examples_text = ""
    if cq_examples and len(cq_examples) > 0:
        examples_list = "\n".join(f"  - {ex}" for ex in cq_examples[:2])
        examples_text = f"\n\n**Bu tablo şu tür sorulara cevap verir:**\n{examples_list}"
    
    # Final block
    context_block = f"""
## Tablo Bağlamı

**Analiz Tipi:** {intent_label}
**Sunum Şekli:** {shape_label} ({shape_format})

**Bu tablonun amacı:** {table_purpose}
{filter_text}{period_text}{grouping_text}

**Kullanıcının orijinal sorusu:** \"{user_query}\"{examples_text}

**Kolon Açıklamaları:**
{chr(10).join(col_descriptions)}

**Yorumlama Rehberi:**
{shape_interpretation}
""".strip()
    
    return context_block


def get_table_context_from_analysis(
    user_query: str,
    table_rows: List[Dict[str, Any]],
    question_type: str,
    output_shape: str,
    meta: Optional[Dict[str, Any]] = None,
    label_map: Optional[Dict[str, str]] = None,
) -> str:
    """
    IntentAnalysisResult ve tablo satırlarından bağlam bloğu üretir.
    
    Bu fonksiyon, CanonicalQuestion yoksa bile çalışır.
    orchestrator.py'dan doğrudan çağrılabilir.
    
    Args:
        user_query: Kullanıcının orijinal sorusu
        table_rows: Tablo satırları (dict listesi)
        question_type: Intent string değeri
        output_shape: Shape string değeri
        meta: Ek metadata (entities, period, vb.)
        label_map: Kolon label mapping
    
    Returns:
        LLM için bağlam bloğu
    """
    # Tablodaki kolonları tespit et
    columns = list(table_rows[0].keys()) if table_rows else []
    
    # Meta'dan bilgi çıkar
    cq_desc = None
    cq_examples = None
    filters = None
    period_info = None
    
    if meta:
        # Entities'den filtre bilgisi
        entities = meta.get("entities", {})
        if entities and isinstance(entities, dict):
            filters = {}
            if entities.get("vehicle_type"):
                filters["vehicleType"] = entities.get("vehicle_type")
            if entities.get("vehicle_model"):
                filters["vehicleModel"] = entities.get("vehicle_model")
            if entities.get("vehicle_id"):
                filters["vehicleId"] = entities.get("vehicle_id")
            if entities.get("material_keywords"):
                kws = entities.get("material_keywords", [])
                if kws:
                    filters["materialName_contains"] = ", ".join(kws)
            if entities.get("customer_id"):
                filters["customerId"] = entities.get("customer_id")
            if entities.get("service_location"):
                filters["serviceLocation"] = entities.get("service_location")
        
        # Period bilgisi
        period_info = meta.get("effective_period_text")
    
    # CanonicalQuestion'dan description ve examples almayı dene
    try:
        from services.xapi_nlp.canonical_questions import (
            get_cq_by_type_and_shape,
            QuestionType,
            OutputShape,
        )
        cq = get_cq_by_type_and_shape(
            QuestionType(question_type),
            OutputShape(output_shape)
        )
        if cq:
            cq_desc = cq.description
            cq_examples = cq.examples
    except Exception:
        pass  # CQ bulunamazsa veya import hata verirse devam et
    
    return build_table_context_block(
        question_type=question_type,
        output_shape=output_shape,
        user_query=user_query,
        columns_in_table=columns,
        label_map=label_map,
        cq_description=cq_desc,
        cq_examples=cq_examples,
        applied_filters=filters,
        period_info=period_info,
    )


# ============================================================================
# YARDIMCI FONKSİYONLAR
# ============================================================================

def get_semantic_type(column_key: str) -> str:
    """Kolonun semantik tipini döner (metric, dimension, time_dimension, identifier)."""
    col_def = COLUMN_DEFS_EXTENDED.get(column_key, {})
    return col_def.get("semantic_type", "unknown")


def is_metric_column(column_key: str) -> bool:
    """Kolonun metrik olup olmadığını kontrol eder."""
    return get_semantic_type(column_key) == "metric"


def is_dimension_column(column_key: str) -> bool:
    """Kolonun boyut (gruplama) olup olmadığını kontrol eder."""
    return get_semantic_type(column_key) in ("dimension", "time_dimension", "identifier")


def get_column_unit(column_key: str) -> Optional[str]:
    """Kolonun birimini döner (varsa)."""
    col_def = COLUMN_DEFS_EXTENDED.get(column_key, {})
    return col_def.get("unit")


def get_interpretation_hint(column_key: str) -> Optional[str]:
    """Kolon için yorumlama ipucu döner (varsa)."""
    col_def = COLUMN_DEFS_EXTENDED.get(column_key, {})
    return col_def.get("interpretation")


# ============================================================================
# MODULE TEST
# ============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("PROMPT ONTOLOGY - Semantik Metadata Modülü")
    print("=" * 70)
    
    print(f"\nTanımlı Kolon Sayısı: {len(COLUMN_DEFS_EXTENDED)}")
    print(f"Tanımlı Intent Sayısı: {len(INTENT_DESCRIPTIONS)}")
    print(f"Tanımlı Shape Sayısı: {len(SHAPE_DESCRIPTIONS)}")
    
    # Örnek context block
    print("\n" + "=" * 70)
    print("ÖRNEK CONTEXT BLOCK:")
    print("=" * 70)
    
    sample_context = build_table_context_block(
        question_type="material_usage",
        output_shape="top_list",
        user_query="En çok kullanılan malzemeler hangileri?",
        columns_in_table=["materialName", "count", "sum_cost"],
        applied_filters={"vehicleType": "TGS"},
        period_info="2023-01-01 - 2023-12-31",
    )
    
    print(sample_context)