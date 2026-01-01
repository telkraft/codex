# nlp_utils.py
"""
Türkçe doğal dil sorguları için temel NLP yardımcı fonksiyonları.

- normalize_tr / normalize: Türkçe karakterleri sadeleştirerek lower-case string üretir.
- contains_any: Bir sorguda verilen keyword listesinden en az biri var mı?
- extract_year / extract_season / extract_month: Zaman bilgisini çıkarır.
- extract_relative_period: 'son 12 ay', 'son 3 yıl' gibi rölatif dönemleri yakalar.
"""

from __future__ import annotations

import re
from typing import Optional, List, Any

from services.xapi_nlp.nlp_constants import REPLACEMENTS, MONTH_KEYWORDS
from models import PeriodSpec, QueryPlan

# ----------------------------------------------------------------------
# Normalize
# ----------------------------------------------------------------------

def normalize_tr(text: str | None) -> str:
    if not text:
        return ""

    s = str(text).lower()

    # ✅ Tek kaynak (SSOT)
    for src, dst in REPLACEMENTS.items():
        s = s.replace(src, dst)

    # JS'teki /[^a-z0-9 ]/g karşılığı
    s = re.sub(r"[^a-z0-9 ]+", " ", s)

    # Boşlukları sıkıştır
    s = re.sub(r"\s+", " ", s).strip()

    return s


# Geri uyumluluk için
def normalize(text: str | None) -> str:
    return normalize_tr(text)


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------

def contains_any(qn: str, keywords: List[str]) -> bool:
    """
    qn içinde verilen anahtar kelimelerden en az biri geçiyor mu?
    Not: MVP için substring bazlı; ileride word-boundary ile iyileştirilebilir.
    """
    return any(k in qn for k in keywords)


# ----------------------------------------------------------------------
# Zaman çıkarımı
# ----------------------------------------------------------------------

def extract_year(qn: str) -> Optional[int]:
    """
    Basit yıl yakalama: 4 haneli sayı arar (1900-2100 arası).
    """
    for m in re.finditer(r"\b(19[0-9]{2}|20[0-9]{2}|2100)\b", qn):
        try:
            return int(m.group(1))
        except Exception:
            continue
    return None


def extract_season(qn: str) -> Optional[str]:
    """
    Normalize edilmiş metin içinden mevsim bilgisini çıkarır.
    """
    # Sonbahar önce (içinde 'bahar' geçiyor)
    if "sonbahar" in qn or ("son" in qn and "bahar" in qn):
        return "autumn"

    if "ilkbahar" in qn or ("ilk" in qn and "bahar" in qn) or "bahar" in qn:
        return "spring"

    if "kis" in qn:
        return "winter"

    if "yaz" in qn:
        return "summer"

    return None


def extract_month(qn: str) -> Optional[int]:
    """
    Normalize edilmiş metinden ay bilgisini çıkarır.

    Örnekler:
      - 'aralik aylarinda'     → 12
      - '2022 aralik'          → 12
      - '2022 2. ayinda'       → 2
      - '2022 2 ayinda'        → 2
    """
    # 1) Ay ismi
    for key, month in MONTH_KEYWORDS.items():
        if key in qn:
            return month

    # 2) '2. ay', '2 ay', '2 ayinda' vb.
    m = re.search(r"\b(1[0-2]|[1-9])\s*\.?\s*ay\b", qn)
    if not m:
        m = re.search(
            r"\b(1[0-2]|[1-9])\s*\.?\s*ay(?:i|da|inda|larda|larinda)?\b",
            qn,
        )

    if m:
        try:
            val = int(m.group(1))
            if 1 <= val <= 12:
                return val
        except Exception:
            return None

    return None

def extract_years(qn: str) -> List[int]:
    """
    Metinden geçen tüm yılları yakalar (1900-2100).
    Örn: "2020-2024 arası" -> [2020, 2024]
    """
    if not qn:
        return []
    qn = normalize_tr(qn)
    years = []
    for m in re.finditer(r"\b(19[0-9]{2}|20[0-9]{2}|2100)\b", qn):
        try:
            y = int(m.group(1))
            if y not in years:
                years.append(y)
        except Exception:
            continue
    return years

def extract_top_limit(qn: str, default: int = 10, max_limit: int = 50) -> int:
    """
    "top 5", "ilk 5", "en çok 5", "en fazla 5" gibi kalıplardan limiti çıkarır.
    """
    if not qn:
        return default

    # normalize edilmiş metin üzerinden çalıştığını varsayıyoruz
    patterns = [
        r"\btop\s*(\d{1,3})\b",
        r"\bilk\s*(\d{1,3})\b",
        r"\ben\s+cok\s*(\d{1,3})\b",
        r"\ben\s+fazla\s*(\d{1,3})\b",
        r"\b(\d{1,3})\s*(adet|tane)\b",
    ]

    for pat in patterns:
        m = re.search(pat, qn)
        if m:
            try:
                n = int(m.group(1))
                n = max(1, min(n, max_limit))
                return n
            except Exception:
                pass

    return default

# ----------------------------------------------------------------------
# Rölatif dönemler (KRİTİK FIX)
# ----------------------------------------------------------------------

# ❗️ÖNEMLİ: raw string içinde \\b DEĞİL \b kullanılmalı
_RELATIVE_MONTH_PATTERN = re.compile(
    r"\bson\s+(\d+)\s*ay(?:da|inda|lik)?(?:\s+icinde)?\b"
)
_RELATIVE_YEAR_PATTERN = re.compile(
    r"\bson\s+(\d+)\s*y[ıi]l(?:da|inda|lik)?(?:\s+icinde)?\b"
)


def extract_relative_period(qn: str) -> Optional[tuple[str, int]]:
    """
    'son 12 ay', 'son 3 yıl' gibi rölatif dönemleri yakalar.

    Dönüş:
      ('month', 12) veya ('year', 3)
    """
    if not qn:
        return None

    # Güvenlik: caller normalize etmeyi unutmuş olabilir
    qn = normalize_tr(qn)

    m = _RELATIVE_MONTH_PATTERN.search(qn)
    if m:
        try:
            value = int(m.group(1))
            if value > 0:
                return ("month", value)
        except ValueError:
            pass

    m = _RELATIVE_YEAR_PATTERN.search(qn)
    if m:
        try:
            value = int(m.group(1))
            if value > 0:
                return ("year", value)
        except ValueError:
            pass

    return None

def extract_relative_period_spec(qn: str) -> PeriodSpec | None:
    """
    'son 2 yil', 'son 12 ay' gibi ifadeleri
    domain-agnostic PeriodSpec'e çevirir.
    """
    rel = extract_relative_period(qn)
    if not rel:
        return None

    unit, value = rel
    return PeriodSpec(
        kind="relative",
        unit=unit,    # "year" | "month"
        value=value,  # 2 | 12 | 3 ...
    )

def resolve_period_spec(
    analysis: Any,
    plan: Optional[QueryPlan],
    qn_norm: str,
) -> Optional[PeriodSpec]:
    """
    Period öncelik sırası:
      1) analysis.matched_cq.period
      2) plan.period_spec
      3) NLP fallback (son N yıl/ay)
    """
    # 1) CanonicalQuestion period
    matched_cq = getattr(analysis, "matched_cq", None)
    cq_period = getattr(matched_cq, "period", None) if matched_cq else None
    if cq_period:
        return cq_period

    # 2) QueryPlan period_spec
    plan_period = getattr(plan, "period_spec", None) if plan else None
    if plan_period:
        return plan_period

    # 3) NLP fallback
    return extract_relative_period_spec(qn_norm)

# --- sanity check ---
if "\\\\b" in _RELATIVE_MONTH_PATTERN.pattern or "\\\\s" in _RELATIVE_MONTH_PATTERN.pattern:
    raise RuntimeError(
        "INVALID REGEX: extract_relative_period uses DOUBLE-ESCAPED regex "
        "(e.g. r\"\\\\b...\\\\s+\"). Use r\"\\b...\\s+\" instead."
    )
