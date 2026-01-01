# entity_extractor.py
"""
Entity Extractor
================

Doğal dil sorgularından varlık çıkarma motoru.

Çıkarılan varlık türleri:
- Zaman: yıl, ay, mevsim, rölatif dönem
- Araç: ID, model, tip, üretici
- Malzeme: keyword'ler, conditional material
- Diğer: müşteri ID, servis lokasyonu, arıza kodu
"""

from __future__ import annotations

import re
from typing import List, Optional

from .router_models import ExtractedEntities

from services.xapi_nlp.nlp_utils import (
    normalize_tr,
    contains_any,
    extract_years,
    extract_month,
    extract_season,
    extract_relative_period,
)

from services.xapi_nlp.nlp_constants import (
    MATERIAL_BASE_WORDS,
    NEXT_MAINTENANCE_KEYWORDS,
    TOP_LIST_KEYWORDS,
    COMPARISON_KEYWORDS,
)


# ============================================================================
# ENTITY EXTRACTOR CLASS
# ============================================================================

class EntityExtractor:
    """
    Sorudan varlık çıkarma motoru.
    
    Kullanım:
        >>> extractor = EntityExtractor()
        >>> entities = extractor.extract("2023 yılında RHC 404 araçlarda en çok kullanılan malzemeler")
        >>> print(entities.years)  # [2023]
        >>> print(entities.vehicle_models)  # ['rhc 404']
        >>> print(entities.has_top_signal)  # True
    """
    
    def __init__(self):
        # Araç tipi sözlüğü (normalize → canonical)
        self.vehicle_types = {
            "otobus": "bus",
            "bus": "bus",
            "kamyon": "truck",
            "truck": "truck",
            "minibus": "minibus",
        }
        
        # Üretici sözlüğü
        self.manufacturers = {
            "man": "man",
            "mercedes": "mercedes",
            "benz": "mercedes",
            "iveco": "iveco",
            "ford": "ford",
            "temsa": "temsa",
        }
    
    # ========================================================================
    # MAIN ENTRY POINT
    # ========================================================================
    
    def extract(self, question: str) -> ExtractedEntities:
        """
        Sorudan tüm varlıkları çıkarır.
        
        Args:
            question: Orijinal kullanıcı sorusu
            
        Returns:
            ExtractedEntities dataclass instance
        """
        qn = normalize_tr(question)
        original = question
        entities = ExtractedEntities()
        
        # Her kategoriyi ayrı metodlarla çıkar
        self._extract_time_entities(qn, entities)
        self._extract_vehicle_entities(qn, original, entities)
        self._extract_location_entities(qn, entities)
        self._extract_material_entities(qn, entities)
        self._extract_aggregation_signals(qn, entities)
        self._extract_comparison_entities(qn, entities)
        self._extract_fault_codes(original, entities)
        
        # NEXT_MAINTENANCE için conditional material
        if any(sig in qn for sig in NEXT_MAINTENANCE_KEYWORDS):
            entities.conditional_material = self._extract_conditional_material(qn)
        
        return entities
    
    # ========================================================================
    # TIME ENTITIES
    # ========================================================================
    
    def _extract_time_entities(self, qn: str, entities: ExtractedEntities) -> None:
        """Zaman varlıklarını çıkarır: yıl, ay, mevsim, rölatif dönem"""
        
        # Yıllar
        years = extract_years(qn)
        if years:
            entities.years.extend(years)
        
        # Ay
        month = extract_month(qn)
        if month:
            entities.months.append(month)
        
        # Mevsim
        season = extract_season(qn)
        if season:
            entities.seasons.append(season)

        # Rölatif dönem (son N ay/yıl)
        rel = extract_relative_period(qn)
        if rel:
            unit, value = rel
            entities.relative_unit = unit
            entities.relative_value = value
    
    # ========================================================================
    # VEHICLE ENTITIES
    # ========================================================================
    
    def _extract_vehicle_entities(
        self, 
        qn: str, 
        original: str, 
        entities: ExtractedEntities
    ) -> None:
        """Araç varlıklarını çıkarır: ID, model, tip, üretici"""
        
        # 1. Araç ID'leri (5-6 haneli sayılar)
        # NOT: normalize sonrası "70886'in" -> "70886in" olabildiği için \b çalışmayabilir.
        vehicle_id_pattern = r'(?<!\d)(\d{5,6})(?!\d)'
        for match in re.finditer(vehicle_id_pattern, qn):
            vid = match.group(1)
            if vid not in entities.vehicle_ids:
                entities.vehicle_ids.append(vid)
        
        # 2. Araç tipleri
        for norm_type, canon_type in self.vehicle_types.items():
            if norm_type in qn:
                if canon_type not in entities.vehicle_types:
                    entities.vehicle_types.append(canon_type)
        
        # 3. Araç modelleri
        entities.vehicle_models = self._extract_vehicle_models(qn)
        
        # 4. Üreticiler
        for norm_manu, canon_manu in self.manufacturers.items():
            if norm_manu in qn:
                if canon_manu not in entities.manufacturers:
                    entities.manufacturers.append(canon_manu)
    
    def _extract_vehicle_models(self, qn: str) -> List[str]:
        """
        Araç model numaralarını çıkarır.
        
        Desteklenen formatlar:
            - "rhc 404 400" → ['rhc 404 400', 'rhc 404', '400']
            - "rhc 404 (400)" → ['rhc 404 400', 'rhc 404', '400']
            - "RHC 404" → ['rhc 404']
        """
        models = []
        
        # Pattern 1: "rhc 404 400" format
        pattern_normalized = r'\b(rhc\s+\d+\s+\d+)\b'
        matches = re.findall(pattern_normalized, qn, re.IGNORECASE)
        for match in matches:
            normalized = match.strip().lower()
            if normalized not in models:
                models.append(normalized)
            
            parts = normalized.split()
            if len(parts) >= 3:
                base_model = f"{parts[0]} {parts[1]}"
                alt_model = parts[2]
                if base_model not in models:
                    models.append(base_model)
                if alt_model not in models:
                    models.append(alt_model)
        
        # Pattern 2: "rhc 404 (400)" format
        if not models:
            pattern_parens = r'(rhc\s+\d+\s*\(\d+\))'
            matches = re.findall(pattern_parens, qn, re.IGNORECASE)
            for match in matches:
                inner = re.search(r'\((\d+)\)', match)
                if inner:
                    base = re.sub(r'\s*\(\d+\)', '', match).strip().lower()
                    alt_model = inner.group(1)
                    combined = f"{base} {alt_model}"
                    
                    if combined not in models:
                        models.append(combined)
                    if base not in models:
                        models.append(base)
                    if alt_model not in models:
                        models.append(alt_model)
        
        # Pattern 3: "RHC 404" tek başına
        if not models:
            pattern_simple = r'\b(rhc\s+\d+)\b'
            matches = re.findall(pattern_simple, qn, re.IGNORECASE)
            for match in matches:
                normalized = match.strip().lower()
                if normalized not in models:
                    models.append(normalized)
        
        return models
    
    # ========================================================================
    # LOCATION ENTITIES
    # ========================================================================
    
    def _extract_location_entities(self, qn: str, entities: ExtractedEntities) -> None:
        """Lokasyon varlıklarını çıkarır: müşteri ID, servis lokasyonu"""
        
        # 1. Müşteri ID'leri
        customer_pattern = r'musteri[^\d]*(\d+)'
        for match in re.finditer(customer_pattern, qn):
            cid = match.group(1)
            if cid not in entities.customer_ids:
                entities.customer_ids.append(cid)
        
        # 2. Servis lokasyonları (R001, R123 formatında)
        service_pattern = r'\b(r\d{3,4})\b'
        for match in re.finditer(service_pattern, qn):
            loc = match.group(1).upper()
            if loc not in entities.service_locations:
                entities.service_locations.append(loc)
    
    # ========================================================================
    # MATERIAL ENTITIES
    # ========================================================================
    
    def _extract_material_entities(self, qn: str, entities: ExtractedEntities) -> None:
        """Malzeme varlıklarını çıkarır: keyword'ler"""
        
        # 1. Tırnak içi malzeme isimleri (yüksek güvenilirlik)
        material_pattern = r'["\']([^"\']+)["\']'
        for match in re.finditer(material_pattern, qn):
            keyword = match.group(1).strip()
            if len(keyword) > 2:
                entities.material_keywords.append(keyword)
                entities.material_keywords_source = "quoted"
        
        # 2. Fallback: "malzeme" kelimesinden sonraki sözcükler
        if not entities.material_keywords:
            for signal in MATERIAL_BASE_WORDS:
                idx = qn.find(signal)
                if idx != -1:
                    after = qn[idx:idx+50]
                    words = after.split()
                    if len(words) > 1:
                        potential = " ".join(words[1:3]).strip()
                        potential_tokens = potential.split()

                        # Soru kelimeleri ve jenerik ifadeleri keyword yapma
                        exclude_words = [
                            # Soru kelimeleri
                            "hangileri", "neler", "nelerdir", "nedir",
                            "hangisi", "hangisidir", "ne", "nasil",
                            # Jenerik fiiller (normalize edilmiş)
                            "kullanildi", "kullanilmis", "kullanilan",
                            "degisti", "degismis", "degisen",
                            "yapildi", "yapilmis", "yapilan",
                            "kullanimi", "kullanimi nasil", "kullanim nasil",
                            "kullanim", "degisim", "degisimi", "trend", "trendi",
                            "yillara gore", "yillara", "yillik", "yil bazinda",
                            "trend", "trendler", "trendleri", "trendi",
                            "kullanim", "kullanimi", "degisim", "degisimi",
                        ]

                        is_noise = (
                            (potential in exclude_words) or
                            any(tok in exclude_words for tok in potential_tokens)
                        )
                        if potential and not is_noise:
                            entities.material_keywords.append(potential)
                            entities.material_keywords_source = "fallback"
    
    def _extract_conditional_material(self, qn: str) -> Optional[str]:
        """
        "SENSÖR kullanıldığında" gibi ifadelerden koşul malzemesini çıkarır.
        
        NEXT_MAINTENANCE sorularında kullanılır.
        """
        verb_pattern = r'(?:kullanildiginda|kullanilirsa|degistirildiginde)'
        
        # "X malzemesi kullanildiginda" → X
        pattern_with_malzemesi = rf'(\w+)\s+malzemesi\s+{verb_pattern}'
        match = re.search(pattern_with_malzemesi, qn, re.IGNORECASE)
        if match:
            material = match.group(1).strip()
            if material not in ['bir', 'bu', 'o', 'hangi']:
                return material
        
        # "X kullanildiginda" → X
        pattern_without_malzemesi = rf'(\w+)\s+{verb_pattern}'
        match = re.search(pattern_without_malzemesi, qn, re.IGNORECASE)
        if match:
            material = match.group(1).strip()
            if material not in ['bir', 'bu', 'o', 'hangi', 'malzemesi']:
                return material
        
        return None
    
    # ========================================================================
    # AGGREGATION SIGNALS
    # ========================================================================
    
    def _extract_aggregation_signals(self, qn: str, entities: ExtractedEntities) -> None:
        """Top/limit sinyallerini çıkarır"""
        
        if contains_any(qn, TOP_LIST_KEYWORDS):
            entities.has_top_signal = True
            
            limit_pattern = r'(?:ilk|en\s+cok|en\s+fazla|top)\s+(\d+)'
            match = re.search(limit_pattern, qn)
            if match:
                entities.top_limit = int(match.group(1))
    
    # ========================================================================
    # COMPARISON ENTITIES
    # ========================================================================
    
    def _extract_comparison_entities(self, qn: str, entities: ExtractedEntities) -> None:
        """Karşılaştırma varlıklarını çıkarır"""
        
        # ⚠️ "bakım ve onarım" gibi birleşik kavramları comparison olarak algılama
        compound_concepts = [
            "bakim ve onarim", "bakim onarim",  # maintenance operations
            "yuk ve yolcu", "yolcu ve yuk",      # load types
            "satis ve servis", "servis ve satis",
            "giris ve cikis", "cikis ve giris",
        ]
        is_compound = any(cc in qn for cc in compound_concepts)
        
        if not is_compound:
            comparison_pattern = r"(.+?)\s+(?:ile|ve)\s+(.+)"
            match = re.search(comparison_pattern, qn)
            if match:
                left = match.group(1).strip()
                right = match.group(2).strip()
                # Ek güvenlik: comparison keyword'ü olmadan sadece "ve" ile karşılaştırma yapma
                has_comparison_signal = contains_any(qn, COMPARISON_KEYWORDS)
                if len(left.split()) <= 3 and len(right.split()) <= 3 and has_comparison_signal:
                    entities.comparison_entities = [left, right]
    
    # ========================================================================
    # FAULT CODES
    # ========================================================================
    
    def _extract_fault_codes(self, original: str, entities: ExtractedEntities) -> None:
        """Arıza kodlarını çıkarır (orijinal metinden, normalize edilmemiş)"""
        
        fault_pattern = r'\b([A-Z]{2,}\d+[A-Z\d]*)\b'
        for match in re.finditer(fault_pattern, original):
            code = match.group(1)
            if code not in entities.fault_codes:
                entities.fault_codes.append(code)


# ============================================================================
# PUBLIC API
# ============================================================================

__all__ = [
    "EntityExtractor",
]
