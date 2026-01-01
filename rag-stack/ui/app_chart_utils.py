# app_chart_utils.py
"""
LRS sorgu sonuçları için otomatik grafik çıkarım ve render sistemi.

Tablonun kolonlarına ve scenario'ya bakarak en uygun grafik türünü seçer.
"""

from __future__ import annotations
import pandas as pd
import streamlit as st
from typing import Optional, Literal

# ============================================================================
# Grafik Türleri
# ============================================================================

ChartType = Literal["bar", "line", "area", "pie", "none"]


# ============================================================================
# Kolon Kategorizasyonu
# ============================================================================

# Kategorik kolonlar (X ekseni / index için)
CATEGORICAL_COLUMNS = {
    "vehicleType", "vehicleModel", "vehicle", "model",
    "materialName", "materialFamily", "materialCode", "material",
    "faultCode", "verbType",
    "customerId", "serviceLocation", "service",
    "entity", "entity_type",
    "season",
}

# Zaman kolonları (trend / time-series için)
TIME_COLUMNS = {"year", "date", "firstDate", "lastDate"}

# Sayısal kolonlar (Y ekseni / değer için)
NUMERIC_COLUMNS = {
    "count", "quantity", "cost", "sum_cost", "avg_km", "km",
    "firstPrice", "lastPrice", "changeAbs", "changePct", "avgChangePct",
    "observations", "materialsCount", "ratio",
    "totalFaults", "totalOccurrences",
}


def detect_chart_type(
    df: pd.DataFrame,
    scenario: Optional[str] = None,
) -> tuple[ChartType, Optional[str], Optional[str]]:
    """
    DataFrame kolonlarına ve scenario'ya bakarak en uygun grafik türünü belirler.
    
    Returns:
        (chart_type, x_column, y_column)
        
    Örnek:
        ("bar", "vehicleType", "count")
        ("line", "year", "cost")
        ("none", None, None)  # Grafik için uygun değil
    """
    if df.empty:
        return ("none", None, None)
    
    cols = set(df.columns)
    
    # --- Scenario-based hints ---
    if scenario:
        # Trend senaryoları → Line chart
        if "trend" in scenario.lower() or "time_series" in scenario.lower():
            # year veya date varsa
            time_col = next((c for c in ["year", "date"] if c in cols), None)
            value_col = _find_best_numeric(cols)
            if time_col and value_col:
                return ("line", time_col, value_col)
        
        # Next maintenance pattern → Bar chart (ratio)
        if "next_maintenance" in scenario.lower():
            if "material" in cols and "ratio" in cols:
                return ("bar", "material", "ratio")
        
        # Top entities → Horizontal bar
        if "top" in scenario.lower():
            cat_col = _find_best_categorical(cols)
            value_col = _find_best_numeric(cols)
            if cat_col and value_col:
                return ("bar", cat_col, value_col)
    
    # --- Column-based detection ---
    
    # 1) Pivot tablo: verbType ile year/season kombinasyonu
    if "verbType" in cols and ("year" in cols or "season" in cols):
        time_col = "year" if "year" in cols else "season"
        if "count" in cols:
            return ("bar", time_col, "count")
    
    # 2) Year + numeric → Line chart (trend)
    if "year" in cols:
        value_col = _find_best_numeric(cols - {"year"})
        if value_col:
            return ("line", "year", value_col)
    
    # 3) Season + numeric → Bar chart
    if "season" in cols:
        value_col = _find_best_numeric(cols - {"season"})
        if value_col:
            return ("bar", "season", value_col)
    
    # 4) Categorical + numeric → Bar chart
    cat_col = _find_best_categorical(cols)
    value_col = _find_best_numeric(cols)
    
    if cat_col and value_col:
        return ("bar", cat_col, value_col)
    
    # 5) Sadece numeric kolonlar varsa (aggregation sonuçları)
    if len(cols) <= 3 and all(_is_numeric_col(c) or c in TIME_COLUMNS for c in cols):
        return ("none", None, None)  # Tek satır aggregate için grafik anlamsız
    
    return ("none", None, None)


def _find_best_categorical(cols: set) -> Optional[str]:
    """En uygun kategorik kolonu seç (öncelik sırasıyla)"""
    priority = [
        "vehicleType", "materialName", "material", "faultCode",
        "verbType", "entity", "vehicleModel", "serviceLocation",
        "customerId", "service", "materialFamily",
    ]
    for col in priority:
        if col in cols:
            return col
    return None


def _find_best_numeric(cols: set) -> Optional[str]:
    """En uygun sayısal kolonu seç (öncelik sırasıyla)"""
    priority = [
        "count", "quantity", "cost", "sum_cost", "ratio",
        "changePct", "avgChangePct", "observations",
        "totalFaults", "totalOccurrences", "avg_km", "km",
    ]
    for col in priority:
        if col in cols:
            return col
    return None


def _is_numeric_col(col: str) -> bool:
    return col in NUMERIC_COLUMNS


# ============================================================================
# Grafik Render
# ============================================================================

def render_auto_chart(
    df: pd.DataFrame,
    scenario: Optional[str] = None,
    title: Optional[str] = None,
    chart_type_override: Optional[ChartType] = None,
) -> bool:
    """
    DataFrame için otomatik grafik render eder.
    
    Args:
        df: Veri
        scenario: LRS scenario string (opsiyonel hint)
        title: Grafik başlığı
        chart_type_override: Manuel grafik türü seçimi
    
    Returns:
        True eğer grafik çizildiyse, False aksi halde
    """
    if df.empty or len(df) < 2:
        return False  # Tek satır için grafik anlamsız
    
    # Grafik türünü belirle
    if chart_type_override:
        chart_type = chart_type_override
        # Override durumunda kolonları yeniden tespit et
        _, x_col, y_col = detect_chart_type(df, scenario)
    else:
        chart_type, x_col, y_col = detect_chart_type(df, scenario)
    
    if chart_type == "none" or not x_col or not y_col:
        return False
    
    # Başlık
    if title:
        st.markdown(f"#### 📈 {title}")
    
    # Veriyi hazırla
    try:
        chart_df = df[[x_col, y_col]].copy()
        
        # Pivot gerekiyor mu? (verbType gibi breakdown varsa)
        if "verbType" in df.columns and x_col != "verbType" and y_col == "count":
            # Pivot tablo oluştur
            pivot_df = df.pivot_table(
                index=x_col,
                columns="verbType",
                values=y_col,
                aggfunc="sum",
            ).fillna(0)
            
            if chart_type == "line":
                st.line_chart(pivot_df)
            elif chart_type == "area":
                st.area_chart(pivot_df)
            else:
                st.bar_chart(pivot_df)
        else:
            # Basit X-Y chart
            chart_df = chart_df.set_index(x_col)
            
            if chart_type == "line":
                st.line_chart(chart_df)
            elif chart_type == "area":
                st.area_chart(chart_df)
            else:
                st.bar_chart(chart_df)
        
        return True
        
    except Exception as e:
        st.caption(f"⚠️ Grafik oluşturulamadı: {e}")
        return False


def render_chart_with_toggle(
    df: pd.DataFrame,
    scenario: Optional[str] = None,
    default_show: bool = True,
    key_suffix: str = "",
) -> None:
    """
    Kullanıcıya grafik gösterme seçeneği sunar.
    
    Args:
        df: Veri
        scenario: LRS scenario
        default_show: Varsayılan olarak grafik gösterilsin mi
        key_suffix: Streamlit widget key için suffix
    """
    chart_type, x_col, y_col = detect_chart_type(df, scenario)
    
    if chart_type == "none":
        return  # Grafik için uygun değil
    
    # Grafik tipi seçici (opsiyonel)
    col1, col2 = st.columns([3, 1])
    
    with col2:
        show_chart = st.checkbox(
            "📊 Grafik",
            value=default_show,
            key=f"show_chart_{key_suffix}",
        )
    
    if show_chart:
        with col1:
            # Grafik türü seçimi
            chart_options = {
                "bar": "📊 Çubuk",
                "line": "📈 Çizgi",
                "area": "📉 Alan",
            }
            selected_type = st.radio(
                "Grafik Türü",
                options=list(chart_options.keys()),
                format_func=lambda x: chart_options[x],
                index=0 if chart_type == "bar" else (1 if chart_type == "line" else 0),
                horizontal=True,
                key=f"chart_type_{key_suffix}",
                label_visibility="collapsed",
            )
        
        render_auto_chart(df, scenario, chart_type_override=selected_type)


# ============================================================================
# Trend Grafiği (Özel)
# ============================================================================

def render_trend_chart(
    df: pd.DataFrame,
    title: str = "Trend Analizi",
) -> bool:
    """
    Fiyat/değişim trend grafiği için özel render.
    changePct, avgChangePct veya price kolonları için optimize edilmiş.
    """
    if df.empty:
        return False
    
    cols = set(df.columns)
    
    # Malzeme bazlı trend
    if "materialName" in cols and "changePct" in cols:
        st.markdown(f"#### 📈 {title}")
        
        # Top 10 en çok değişen
        df_sorted = df.nlargest(10, "changePct")
        chart_df = df_sorted.set_index("materialName")[["changePct"]]
        st.bar_chart(chart_df)
        return True
    
    # Zaman bazlı trend
    if "year" in cols:
        value_col = next(
            (c for c in ["avgChangePct", "changePct", "cost", "quantity"] if c in cols),
            None
        )
        if value_col:
            st.markdown(f"#### 📈 {title}")
            chart_df = df.set_index("year")[[value_col]]
            st.line_chart(chart_df)
            return True
    
    return False


# ============================================================================
# Pie Chart (Dağılım için)
# ============================================================================

def render_distribution_pie(
    df: pd.DataFrame,
    label_col: str,
    value_col: str,
    title: str = "Dağılım",
) -> bool:
    """
    Pasta grafik render eder (Streamlit native pie yok, plotly ile).
    
    Not: Streamlit'in native chart'larında pie yok.
    Alternatif olarak bar chart kullanılabilir veya plotly eklenebilir.
    """
    if df.empty or label_col not in df.columns or value_col not in df.columns:
        return False
    
    # Streamlit'te native pie chart yok, horizontal bar ile göster
    st.markdown(f"#### 🥧 {title}")
    
    chart_df = df[[label_col, value_col]].copy()
    chart_df = chart_df.set_index(label_col)
    
    # Yüzde hesapla
    total = chart_df[value_col].sum()
    if total > 0:
        chart_df["Yüzde"] = (chart_df[value_col] / total * 100).round(1)
        st.bar_chart(chart_df[["Yüzde"]])
        return True
    
    return False