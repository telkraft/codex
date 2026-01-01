"""
RAG Stack - Streamlit UI with LRS Integration
==============================================
v3.5 - Clean UI + Settings at bottom

Features:
- Chat interface with intent routing
- Settings at bottom of sidebar
- LLM model selection & latency measurement
- Quick action buttons with pricing queries
"""

import streamlit as st
import requests
import json
import pandas as pd
import time
from datetime import datetime
from typing import Optional, Literal

# Plotly for interactive charts
import plotly.graph_objects as go

# =====================================================================
# Grafik Otomatik Çıkarım Sistemi
# =====================================================================

ChartType = Literal["bar", "line", "area", "pie", "none"]

_CATEGORICAL_COLUMNS = {
    # İngilizce
    "vehicleType", "vehicleModel", "vehicle", "model",
    "materialName", "materialFamily", "materialCode", "material",
    "faultCode", "verbType",
    "customerId", "customer", "serviceLocation", "service",
    "entity", "entity_type", "season", "dayOfWeek",
    # Türkçe
    "İşlem Tipi", "Araç Tipi", "Araç Modeli", "Malzeme Adı", 
    "Malzeme Kodu", "Arıza Kodu", "Müşteri", "Servis",
    "Mevsim", "Gün",
}

_TIME_COLUMNS = {"year", "date", "firstDate", "lastDate", "month"}

_NUMERIC_COLUMNS = {
    "count", "quantity", "cost", "sum_cost", "avg_km", "km",
    "firstPrice", "lastPrice", "changeAbs", "changePct", "avgChangePct",
    "observations", "materialsCount", "ratio",
    "totalFaults", "totalOccurrences",
}


def _find_best_categorical(cols: set) -> Optional[str]:
    priority = [
        # İngilizce
        "vehicleType", "materialName", "material", "materialCode",
        "faultCode", "verbType", "entity", "vehicleModel", 
        "customer", "customerId", "serviceLocation", "service", 
        "materialFamily", "dayOfWeek", "season",
        # Türkçe
        "Araç Tipi", "Malzeme Adı", "Malzeme Kodu", "Arıza Kodu",
        "İşlem Tipi", "Araç Modeli", "Müşteri", "Servis",
        "Mevsim", "Gün",
    ]
    for col in priority:
        if col in cols:
            return col
    return None


def _find_best_numeric(cols: set) -> Optional[str]:
    priority = [
        # İngilizce
        "count", "quantity", "cost", "sum_cost", "ratio",
        "changePct", "avgChangePct", "changeAbs", "observations",
        "totalFaults", "totalOccurrences", "avg_km", "km",
        "firstPrice", "lastPrice",
        # Türkçe
        "Adet", "Miktar", "Maliyet", "Toplam Maliyet", "Oran",
        "Değişim (%)", "Gözlem Sayısı", "Toplam Maliyet",
    ]
    for col in priority:
        if col in cols:
            return col
    return None


def detect_chart_type(
    df: pd.DataFrame,
    scenario: Optional[str] = None,
) -> tuple[ChartType, Optional[str], Optional[str]]:
    """DataFrame kolonlarına bakarak en uygun grafik türünü belirler."""
    if df.empty:
        return ("none", None, None)
    
    cols = set(df.columns)
    
    # Günlere göre dağılım → dayOfWeek + count bar chart
    if "dayOfWeek" in cols:
        value_col = _find_best_numeric(cols)
        if value_col:
            return ("bar", "dayOfWeek", value_col)
    
    if scenario:
        # Cost analysis (fiyat değişimi) → materialCode + changePct
        if "cost_analysis" in scenario.lower():
            if "materialCode" in cols and "changePct" in cols:
                return ("bar", "materialCode", "changePct")
            if "materialName" in cols and "changePct" in cols:
                return ("bar", "materialName", "changePct")
            if "materialFamily" in cols and "avgChangePct" in cols:
                return ("bar", "materialFamily", "avgChangePct")
        
        # Customer analysis → customer + count
        if "customer" in scenario.lower():
            if "customer" in cols:
                value_col = _find_best_numeric(cols)
                if value_col:
                    return ("bar", "customer", value_col)
        
        if "trend" in scenario.lower() or "time_series" in scenario.lower():
            time_col = next((c for c in ["year", "date", "month"] if c in cols), None)
            value_col = _find_best_numeric(cols)
            if time_col and value_col:
                return ("line", time_col, value_col)
        
        if "next_maintenance" in scenario.lower():
            if "material" in cols and "ratio" in cols:
                return ("bar", "material", "ratio")
        
        if "top" in scenario.lower():
            cat_col = _find_best_categorical(cols)
            value_col = _find_best_numeric(cols)
            if cat_col and value_col:
                return ("bar", cat_col, value_col)
    
    if "verbType" in cols and any(c in cols for c in ["year", "season", "month"]):
        time_col = next((c for c in ["year", "month", "season"] if c in cols), None)
        if "count" in cols and time_col:
            return ("bar", time_col, "count")
    
    if "year" in cols:
        value_col = _find_best_numeric(cols - {"year"})
        if value_col:
            return ("line", "year", value_col)
    
    if "month" in cols:
        value_col = _find_best_numeric(cols - {"month"})
        if value_col:
            return ("line", "month", value_col)
    
    if "season" in cols:
        value_col = _find_best_numeric(cols - {"season"})
        if value_col:
            return ("bar", "season", value_col)
    
    cat_col = _find_best_categorical(cols)
    value_col = _find_best_numeric(cols)
    
    if cat_col and value_col:
        return ("bar", cat_col, value_col)
    
    return ("none", None, None)


def render_auto_chart(
    df: pd.DataFrame,
    scenario: Optional[str] = None,
    title: Optional[str] = None,
    chart_type_override: Optional[ChartType] = None,
) -> bool:
    """DataFrame için otomatik grafik render eder."""
    if df.empty or len(df) < 2:
        return False
    
    if chart_type_override:
        chart_type = chart_type_override
        _, x_col, y_col = detect_chart_type(df, scenario)
    else:
        chart_type, x_col, y_col = detect_chart_type(df, scenario)
    
    if chart_type == "none" or not x_col or not y_col:
        return False
    
    if title:
        st.markdown(f"#### 📈 {title}")
    
    try:
        if "verbType" in df.columns and x_col != "verbType" and y_col == "count":
            pivot_df = df.pivot_table(
                index=x_col,
                columns="verbType",
                values=y_col,
                aggfunc="sum",
            ).fillna(0)
            
            try:
                pivot_df = pivot_df.sort_index()
            except:
                pass
            
            if chart_type == "line":
                st.line_chart(pivot_df)
            elif chart_type == "area":
                st.area_chart(pivot_df)
            else:
                st.bar_chart(pivot_df)
        else:
            chart_df = df[[x_col, y_col]].copy()
            
            # Kategorik kolonları string'e çevir (sayısal ID'ler için)
            if x_col in _CATEGORICAL_COLUMNS:
                chart_df[x_col] = chart_df[x_col].astype(str)
            
            # Sıralama
            if x_col in ["year", "month"]:
                chart_df = chart_df.sort_values(x_col)
            elif x_col == "dayOfWeek":
                # Haftanın günlerini doğru sırala
                day_order = ["Pazartesi", "Sali", "Carsamba", "Persembe", "Cuma", "Cumartesi", "Pazar"]
                chart_df[x_col] = pd.Categorical(chart_df[x_col], categories=day_order, ordered=True)
                chart_df = chart_df.sort_values(x_col)
                chart_df[x_col] = chart_df[x_col].astype(str)
            elif x_col == "season":
                # Mevsimleri doğru sırala
                season_order = ["ilkbahar", "yaz", "sonbahar", "kis"]
                if chart_df[x_col].str.lower().isin(season_order).any():
                    chart_df["_sort"] = chart_df[x_col].str.lower().map({s: i for i, s in enumerate(season_order)})
                    chart_df = chart_df.sort_values("_sort").drop(columns=["_sort"])
            
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


# =====================================================================
# 🆕 İnteraktif Grafik-Tablo Senkronizasyon Sistemi (Plotly)
# =====================================================================

def render_interactive_chart_and_table(
    df: pd.DataFrame,
    df_display: pd.DataFrame,
    scenario: Optional[str] = None,
    msg_index: int = 0,
    chart_type_override: Optional[ChartType] = None,
) -> None:
    """
    Grafik ve tablo arasında interaktif senkronizasyon sağlar.
    Selectbox'tan satır seçildiğinde grafikte ve tabloda highlight edilir.
    """
    if df.empty or len(df) < 2:
        st.dataframe(df_display, use_container_width=True, hide_index=True)
        return
    
    # Chart type ve kolonları belirle
    if chart_type_override:
        chart_type = chart_type_override
        _, x_col, y_col = detect_chart_type(df, scenario)
    else:
        chart_type, x_col, y_col = detect_chart_type(df, scenario)
    
    if chart_type == "none" or not x_col or not y_col:
        st.dataframe(df_display, use_container_width=True, hide_index=True)
        return
    
    # Session state key
    selection_key = f"sel_{msg_index}_{x_col}"
    
    # ════════════════════════════════════════════════════════════════
    # CHART İÇİN VERİ HAZIRLA
    # ════════════════════════════════════════════════════════════════
    
    # Sadece gerekli kolonları al
    x_data = df[x_col].astype(str).tolist()
    y_data = df[y_col].tolist()
    
    # Sıralama için temp df
    temp_df = pd.DataFrame({'x': x_data, 'y': y_data})
    
    # Sıralama
    if x_col in ["year", "month"]:
        temp_df = temp_df.sort_values('x')
    elif x_col == "dayOfWeek":
        day_order = {"Pazartesi": 0, "Sali": 1, "Carsamba": 2, "Persembe": 3, "Cuma": 4, "Cumartesi": 5, "Pazar": 6}
        temp_df["_sort"] = temp_df['x'].map(day_order)
        temp_df = temp_df.sort_values("_sort").drop(columns=["_sort"])
    elif x_col == "season":
        season_order = {"ilkbahar": 0, "yaz": 1, "sonbahar": 2, "kis": 3}
        temp_df["_sort"] = temp_df['x'].str.lower().map(season_order)
        temp_df = temp_df.sort_values("_sort").drop(columns=["_sort"])
    else:
        # Değere göre azalan sırala
        temp_df = temp_df.sort_values('y', ascending=False)
    
    temp_df = temp_df.reset_index(drop=True)
    
    # Sıralanmış veriler
    x_sorted = temp_df['x'].tolist()
    y_sorted = temp_df['y'].tolist()
    
    # X ve Y etiketleri
    x_label = COLUMN_LABEL_MAP.get(x_col, x_col)
    y_label = COLUMN_LABEL_MAP.get(y_col, y_col)
    
    # ════════════════════════════════════════════════════════════════
    # SEÇİM KONTROLÜ - ÜST KISIM
    # ════════════════════════════════════════════════════════════════
    
    col1, col2 = st.columns([3, 1])
    
    with col2:
        options = ["— Tümü —"] + x_sorted
        
        selected_value = st.selectbox(
            "🔍 Highlight",
            options=options,
            index=0,
            key=selection_key,
        )
    
    # Seçili index'i bul
    selected_idx = None
    if selected_value != "— Tümü —":
        try:
            selected_idx = x_sorted.index(selected_value)
        except ValueError:
            selected_idx = None
    
    with col1:
        if selected_idx is not None:
            selected_y = y_sorted[selected_idx]
            st.info(f"📍 **{selected_value}** → {y_label}: **{selected_y:,.0f}**")
    
    # ════════════════════════════════════════════════════════════════
    # PLOTLY GRAFİK
    # ════════════════════════════════════════════════════════════════
    
    # Renk listesi oluştur
    colors = []
    for i in range(len(x_sorted)):
        if selected_idx is not None and i == selected_idx:
            colors.append("#ff6b6b")  # Seçili: Kırmızı
        else:
            colors.append("#4dabf7")  # Normal: Mavi
    
    try:
        if chart_type == "bar":
            fig = go.Figure(data=[
                go.Bar(
                    x=x_sorted,
                    y=y_sorted,
                    marker_color=colors,
                    text=[f"{v:,.0f}" for v in y_sorted],
                    textposition='outside',
                    hovertemplate=f"<b>{x_label}</b>: %{{x}}<br><b>{y_label}</b>: %{{y:,.0f}}<extra></extra>",
                )
            ])
        elif chart_type == "line":
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=x_sorted,
                y=y_sorted,
                mode='lines+markers',
                line=dict(color="#4dabf7", width=2),
                marker=dict(color=colors, size=10),
                hovertemplate=f"<b>{x_label}</b>: %{{x}}<br><b>{y_label}</b>: %{{y:,.0f}}<extra></extra>",
            ))
        elif chart_type == "area":
            fig = go.Figure(data=[
                go.Scatter(
                    x=x_sorted,
                    y=y_sorted,
                    mode='lines',
                    fill='tozeroy',
                    fillcolor='rgba(77, 171, 247, 0.3)',
                    line=dict(color="#4dabf7", width=2),
                    hovertemplate=f"<b>{x_label}</b>: %{{x}}<br><b>{y_label}</b>: %{{y:,.0f}}<extra></extra>",
                )
            ])
        else:
            fig = None
        
        if fig:
            fig.update_layout(
                xaxis_title=x_label,
                yaxis_title=y_label,
                showlegend=False,
                margin=dict(l=60, r=30, t=40, b=60),
                height=400,
                hovermode='x unified',
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)',
                xaxis=dict(
                    categoryorder='array',
                    categoryarray=x_sorted,
                ),
            )
            fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='rgba(128,128,128,0.2)')
            fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='rgba(128,128,128,0.2)')
            
            st.plotly_chart(fig, use_container_width=True)
            
    except Exception as e:
        st.error(f"⚠️ Grafik oluşturulamadı: {e}")
    
    # ════════════════════════════════════════════════════════════════
    # TABLO (Seçili satır highlight)
    # ════════════════════════════════════════════════════════════════
    
    # Tablo için sıralanmış df oluştur
    table_df = pd.DataFrame({x_col: x_sorted, y_col: y_sorted})
    display_table = translate_columns(table_df)
    
    def highlight_row(row):
        if selected_idx is not None and row.name == selected_idx:
            return ['background-color: #fff3cd; font-weight: bold'] * len(row)
        return [''] * len(row)
    
    styled_df = display_table.style.apply(highlight_row, axis=1)
    
    st.dataframe(
        styled_df,
        use_container_width=True,
        hide_index=True,
        height=min(400, 35 * len(display_table) + 40),
    )

# =====================================================================
# Tablo kolonları için TR başlık sözlüğü
# =====================================================================
COLUMN_LABELS = [
    {"key": "vehicleType", "label": "Araç Tipi"},
    {"key": "vehicleModel", "label": "Araç Modeli"},
    {"key": "vehicle", "label": "Araç"},
    {"key": "model", "label": "Araç Modeli"},
    {"key": "vehicleId", "label": "Araç ID"},
    {"key": "customerId", "label": "Müşteri"},
    {"key": "serviceLocation", "label": "Servis Lokasyonu"},

    {"key": "materialName", "label": "Malzeme"},
    {"key": "materialFamily", "label": "Malzeme Ailesi"},
    {"key": "materialCode", "label": "Malzeme Kodu"},

    {"key": "faultCode", "label": "Arıza Kodu"},
    {"key": "verbType", "label": "İşlem Tipi"},

    {"key": "year", "label": "Yıl"},
    {"key": "season", "label": "Mevsim"},
    {"key": "date", "label": "Tarih"},
    {"key": "service", "label": "Servis"},

    {"key": "km", "label": "Km"},
    {"key": "quantity", "label": "Adet"},
    {"key": "cost", "label": "Maliyet"},

    # Trend tabloları
    {"key": "firstDate", "label": "İlk Tarih"},
    {"key": "lastDate", "label": "Son Tarih"},
    {"key": "firstPrice", "label": "İlk Fiyat"},
    {"key": "lastPrice", "label": "Son Fiyat"},
    {"key": "changeAbs", "label": "Fark"},
    {"key": "changePct", "label": "Değişim (%)"},
    {"key": "observations", "label": "Gözlem Sayısı"},
    {"key": "avgChangePct", "label": "Ort. Değişim (%)"},
    {"key": "materialsCount", "label": "Malzeme Sayısı"},

    # Top / pivot
    {"key": "entity", "label": "Varlık"},
    {"key": "entity_type", "label": "Varlık Tipi"},
    {"key": "count", "label": "Adet"},
    {"key": "sum_cost", "label": "Toplam Maliyet"},
    {"key": "avg_km", "label": "Ortalama Km"},

    # Next maintenance pattern
    {"key": "material", "label": "Malzeme"},
    {"key": "ratio", "label": "Oran (%)"},
]

COLUMN_LABEL_MAP = {c["key"]: c["label"] for c in COLUMN_LABELS}


def translate_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    DataFrame kolonlarını COLUMN_LABEL_MAP'e göre Türkçeleştirir.
    Bilinmeyen kolon isimlerini olduğu gibi bırakır.
    """
    return df.rename(columns=COLUMN_LABEL_MAP)

# ============================================================================
# // Configuration
# ============================================================================

RAG_API_URL = "http://rag-api:8000"

st.set_page_config(
    page_title="Promptever Chat",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for dark theme
st.markdown("""
    <style>

    /* -------------------------------------------
       LIGHT THEME
       ------------------------------------------- */
    body[data-theme="light"] .main {
        background-color: #f5f5f5 !important;
        color: #000 !important;
    }

    /* Light mode alert */
    body[data-theme="light"] .stAlert {
        background-color: #ffffff !important;
        color: #333 !important;
    }

    /* -------------------------------------------
       DARK THEME
       ------------------------------------------- */
    body[data-theme="dark"] .main {
        background-color: #000000 !important;
        color: #ffffff !important;
    }

    /* Dark mode alert */
    body[data-theme="dark"] .stAlert {
        background-color: #1a1a1a !important;
        color: #fafafa !important;
    }

    /* Intent badges (her iki temada aynı kalabilir) */
    .intent-badge {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 12px;
        font-size: 12px;
        font-weight: 600;
        margin-right: 8px;
    }
    .statistical { background-color: #1f77b4; color: white; }
    .semantic { background-color: #2ca02c; color: white; }
    .hybrid { background-color: #ff7f0e; color: white; }

    /* Quick action button hover */
    .stButton > button {
        width: 100%;
        border-radius: 6px;
        transition: all 0.2s ease;
    }
    .stButton > button:hover {
        transform: translateX(4px);
    }

    </style>
""", unsafe_allow_html=True)

# ============================================================================
# Helper Functions
# ============================================================================

def call_rag_api(endpoint: str, method: str = "GET", data: dict = None, timeout: int = 120) -> dict:
    """Call RAG API endpoint"""
    try:
        url = f"{RAG_API_URL}{endpoint}"
        if method == "GET":
            response = requests.get(url, timeout=timeout)
        elif method == "POST":
            response = requests.post(url, json=data, timeout=timeout)
        else:
            raise ValueError(f"Unsupported method: {method}")

        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"API Error: {str(e)}")
        return None

def _extract_table_df(response: dict) -> pd.DataFrame:
    """
    ChatResponse sözlüğünden ilk tabloyu DataFrame'e çevirir.

    Beklenen şema:
      {
        "tables": [
          {
            "title": "...",
            "description": "...",
            "rows": [ {...}, {...}, ... ]
          }
        ],
        "data": { "rows": [...] }  # fallback
      }
    """
    if not response:
        return pd.DataFrame()

    tables = response.get("tables") or []
    if tables:
        table = tables[0]
        rows = table.get("rows") or []
        if rows:
            return pd.DataFrame(rows)

    data = response.get("data")
    if isinstance(data, dict) and "rows" in data:
        return pd.DataFrame(data["rows"])

    return pd.DataFrame()


def _run_stat_query_for_dashboard(query: str, limit: int = 5000) -> pd.DataFrame:
    """
    Dashboard için /chat endpoint'ine istatistik odaklı bir soru gönderir.
    LLM'i kapalı tutar ve tabloyu DataFrame olarak döner.
    """
    collection = st.session_state.get("collection", "man_local_service_maintenance")
    context_limit = st.session_state.get("context_limit", limit)

    payload = {
        "query": query,
        "collection": collection,
        "use_llm": False,           # 🔴 Dashboard tamamen LRS istatistiğine dayanıyor
        "limit": context_limit,
        "model": None,              # LLM kapalı olduğu için model yok
        "role": "servis_analisti",  # Backend parametreleri için default
        "behavior": "balanced",
    }

    response = call_rag_api("/chat", method="POST", data=payload, timeout=320)

    if response is None:
        st.warning(f"'{query}' için API'den yanıt alınamadı.")
        return pd.DataFrame()

    return _extract_table_df(response)

def render_overview_dashboard():
    """
    Ana ekranda, chat'in üzerinde gösterilecek 'Genel Bakış' paneli.
    LRS istatistiklerinden hızlı grafikler üretir (LLM kullanmadan).
    """
    st.markdown("### 📊 Genel Bakış (LRS İstatistikleri)")

    # --- 1) Yıllara göre bakım & onarım dağılımı ---
    st.markdown("#### ⏱️ Yıllara göre bakım & onarım dağılımı")

    df_year = _run_stat_query_for_dashboard(
        "Yıllara göre bakım ve onarım işlemlerinin dağılımı nedir?"
    )

    if not df_year.empty and {"year", "verbType", "count"}.issubset(df_year.columns):
        pivot_year = (
            df_year.pivot_table(
                index="year",
                columns="verbType",
                values="count",
                aggfunc="sum",
            )
            .fillna(0)
            .sort_index()
        )
        st.line_chart(pivot_year)
        st.dataframe(translate_columns(df_year), use_container_width=True, hide_index=True)
    else:
        st.info("Yıllara göre bakım & onarım için uygun veri bulunamadı.")

    st.markdown("---")

    # --- 2) Mevsimlere göre bakım & onarım dağılımı ---
    st.markdown("#### 🌦️ Mevsimlere göre bakım & onarım dağılımı")

    df_season = _run_stat_query_for_dashboard(
        "Mevsimlere göre bakım ve onarım işlemlerinin dağılımı nedir?"
    )

    if not df_season.empty and {"season", "verbType", "count"}.issubset(df_season.columns):
        pivot_season = (
            df_season.pivot_table(
                index="season",
                columns="verbType",
                values="count",
                aggfunc="sum",
            )
            .fillna(0)
        )
        st.bar_chart(pivot_season)
        st.dataframe(translate_columns(df_season), use_container_width=True, hide_index=True)
    else:
        st.info("Mevsimlere göre bakım & onarım için uygun veri bulunamadı.")

    st.markdown("---")

    # --- 3) Araç tiplerine göre bakım & onarım dağılımı ---
    st.markdown("#### 🚚 Araç tiplerine göre bakım & onarım dağılımı")

    df_type = _run_stat_query_for_dashboard(
        "Araç tiplerine göre bakım ve onarım işlemlerinin dağılımı nedir?"
    )

    if not df_type.empty and {"vehicleType", "verbType", "count"}.issubset(df_type.columns):
        pivot_type = (
            df_type.pivot_table(
                index="vehicleType",
                columns="verbType",
                values="count",
                aggfunc="sum",
            )
            .fillna(0)
        )
        st.bar_chart(pivot_type)
        st.dataframe(translate_columns(df_type), use_container_width=True, hide_index=True)
    else:
        st.info("Araç tipleri için uygun veri bulunamadı.")

def display_intent_badge(intent: str):
    """Display intent badge"""
    badge_class = intent.lower()
    badge_text = {
        "statistical": "📊 İstatistiksel",
        "semantic": "🧠 Anlamsal",
        "hybrid": "🔀 Hibrit"
    }.get(intent, intent)

    st.markdown(
        f'<span class="intent-badge {badge_class}">{badge_text}</span>',
        unsafe_allow_html=True
    )

def get_chain_label(intent: str, scenario: str | None, llm_used: bool | None = None) -> str:
    base = "hafıza"

    if intent == "semantic":
        return base + " → doküman arama → LLM yorumu"
    if intent == "hybrid":
        return base + " → istatistik + doküman arama → LLM yorumu"

    if not scenario:
        return base + " → istatistik"

    family, _, subject = scenario.partition(":")

    # Yeni orchestrator: "question_type:XYZ"
    if family == "question_type":
        qt_labels = {
            "MATERIAL_USAGE": "malzeme kullanımı analizi",
            "COST_ANALYSIS": "maliyet analizi",
            "MAINTENANCE_HISTORY": "bakım geçmişi analizi",
            "FAULT_ANALYSIS": "arıza analizi",
            "VEHICLE_BASED": "araç bazlı istatistik",
            "CUSTOMER_BASED": "müşteri bazlı istatistik",
            "SERVICE_BASED": "servis bazlı istatistik",
            "TIME_SERIES": "zaman serisi analizi",
            "SEASONAL": "mevsimsel analiz",
            "TOP_ENTITIES": "en çok / en az listeleri",
            "DISTRIBUTION": "dağılım analizi",
            "COMPARISON": "karşılaştırma analizi",
        }
        qt_part = qt_labels.get(subject, subject.lower())
        chain = base + f" → {qt_part}"
    else:
        family_labels = {
            "aggregate": "genel istatistik",
            "top": "en çok gelenler",
            "trend": "trend analizi",
            "pivot": "pivot tablo",
            "history": "geçmiş analizi",
            "next_maintenance": "sonraki bakım paterni",
        }
        subject_labels = {
            "operation_distribution": "işlem tipi dağılımı",
            "service_volume": "servis hacmi",
            "material_price_trend": "malzeme fiyat trendi",
            "material_family_price_trend": "malzeme ailesi fiyat trendi",
            "material_usage": "mevsimsel malzeme kullanımı",
            "maintenance_history": "araç bakım geçmişi",
            "next_maintenance_materials": "bir sonraki bakım paternleri",
        }

        family_part = family_labels.get(family, family)
        subject_part = subject_labels.get(subject, subject) if subject else None

        chain = base + f" → {family_part}"
        if subject_part:
            chain += f" → {subject_part}"

    if llm_used is None:
        llm_used = st.session_state.get("use_llm", True)

    if llm_used:
        chain += " → LLM yorumu"

    return chain

def display_statistical_results(data: dict):
    """Display generic statistical query results"""
    st.markdown("### 📊 İstatistiksel Sonuçlar")

    if isinstance(data, dict):
        if "totalStatements" in data:
            cols = st.columns(4)
            with cols[0]:
                st.markdown(f"""
                <div class="stat-card">
                    <div class="stat-number">{data.get('totalStatements', 0):,}</div>
                    <div class="stat-label">Toplam Statement</div>
                </div>
                """, unsafe_allow_html=True)

            with cols[1]:
                st.markdown(f"""
                <div class="stat-card">
                    <div class="stat-number">{data.get('uniqueVehicles', 0):,}</div>
                    <div class="stat-label">Araç Sayısı</div>
                </div>
                """, unsafe_allow_html=True)

            with cols[2]:
                st.markdown(f"""
                <div class="stat-card">
                    <div class="stat-number">{data.get('statementsWithFaults', 0):,}</div>
                    <div class="stat-label">Arızalı Statement</div>
                </div>
                """, unsafe_allow_html=True)

            with cols[3]:
                st.markdown(f"""
                <div class="stat-card">
                    <div class="stat-number">{data.get('faultCodeRatio', 0):.1f}%</div>
                    <div class="stat-label">Arıza Oranı</div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.json(data)

    elif isinstance(data, list) and len(data) > 0:
        df = pd.DataFrame(data)

        if "verbType" in df.columns and "count" in df.columns:
            st.markdown("#### İşlem Tipi Dağılımı")
            df_display = translate_columns(df)
            st.dataframe(df_display, use_container_width=True, hide_index=True)
            st.bar_chart(df.set_index("verbType")["count"])

        elif "vehicleType" in df.columns and "totalFaults" in df.columns:
            st.markdown("#### En Çok Arıza Olan Araç Tipleri")
            df_display = translate_columns(df)
            st.dataframe(df_display, use_container_width=True, hide_index=True)
            st.bar_chart(df.set_index("vehicleType")["totalFaults"])

        elif "faultCode" in df.columns and "totalOccurrences" in df.columns:
            st.markdown("#### Arıza Kodu Dağılımı")
            df_display = translate_columns(df)
            st.dataframe(df_display, use_container_width=True, hide_index=True)
            st.bar_chart(df.set_index("faultCode")["totalOccurrences"])

        else:
            df_display = translate_columns(df)
            st.dataframe(df_display, use_container_width=True, hide_index=True)
    else:
        st.json(data)


def display_semantic_results(answer: str, sources: list):
    """Display semantic query results"""
    st.markdown("### 🧠 Anlamsal Analiz")
    st.markdown("#### Yanıt")
    st.write(answer)

    if sources:
        with st.expander(f"📚 Kaynaklar ({len(sources)} kayıt)", expanded=False):
            for i, source in enumerate(sources[:5]):
                score = source.get("score", 0)
                payload = source.get("payload", {})

                st.markdown(f"**Kaynak {i+1}** (Benzerlik: {score:.2f})")

                if "verb" in payload:
                    verb = payload["verb"].get("display", {}).get("tr-TR", "N/A")
                    st.write(f"- **İşlem**: {verb}")

                if "context" in payload and "extensions" in payload["context"]:
                    ext = payload["context"]["extensions"]
                    vehicle_type = ext.get("https://promptever.com/extensions/vehicleType", "N/A")
                    st.write(f"- **Araç Tipi**: {vehicle_type}")

                if "result" in payload and "extensions" in payload["result"]:
                    ext = payload["result"]["extensions"]
                    fault_code = ext.get("https://promptever.com/extensions/faultCode", "N/A")
                    if fault_code != "N/A":
                        st.write(f"- **Arıza Kodu**: {fault_code}")

                st.markdown("---")


def display_hybrid_results(answer: str, statistics: dict, sources: list):
    """Display hybrid query results"""
    st.markdown("### 🔀 Hibrit Analiz")

    st.markdown("#### 📊 İstatistiksel Veriler")

    if isinstance(statistics, dict) and statistics.get("type") == "query_plan":
        plan = statistics.get("plan", {})
        rows = statistics.get("rows", [])

        st.info("LRS üzerinde schema-aware bir sorgu planı çalıştırıldı.")

        with st.expander("📐 Sorgu Planı (QueryPlan)", expanded=False):
            st.json(plan)

        if rows:
            df = pd.DataFrame(rows)
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.warning("Bu sorgu planı için LRS'den satır dönmedi.")
    else:
        display_statistical_results(statistics)

    st.markdown("---")
    st.markdown("#### 🧠 Anlamsal Yorumlama")
    st.write(answer)

    if sources:
        with st.expander(f"📚 Kaynaklar ({len(sources)} kayıt)", expanded=False):
            for i, source in enumerate(sources[:3]):
                score = source.get("score", 0)
                st.markdown(f"**Kaynak {i+1}** (Benzerlik: {score:.2f})")
                st.json(source.get("payload", {}))

def render_debug_panel(meta):
    if not meta or not isinstance(meta, dict):
        st.info("Debug meta bulunamadı.")
        return

    with st.expander("🪲 Debug (plan / meta)", expanded=False):
        applied_filters = meta.get("applied_filters")
        if applied_filters is not None:
            st.markdown("**Uygulanan filtreler / plan**")
            st.json(applied_filters)

        reason_code = meta.get("empty_reason") or meta.get("empty_reason_code")
        reason_msg = meta.get("message") or meta.get("error")

        if reason_code:
            st.markdown(f"**Kod**: `{reason_code}`")
        if reason_msg:
            st.markdown(f"**Açıklama**: {reason_msg}")

        st.markdown("**Meta (tam)**")
        st.json(meta)

def display_mvp_response(response: dict, msg_index: int = 0):
    """Display new ChatResponse schema (statistics + examples + LLM) + AUTO CHARTS"""
    intent = response.get("intent", "statistical")
    scenario = response.get("scenario")
    summary = response.get("summary")

    tables = response.get("tables") or []
    examples = response.get("examples") or []
    llm = response.get("llm") or {}
    data = response.get("data", {})

    # ==============================================================
    # 🔴 LLM-ONLY FALLBACK: Domain-dışı sorular
    # ==============================================================
    if intent == "llm_only":
        answer = ""
        if isinstance(llm, dict):
            answer = llm.get("answer") or ""

        st.markdown("### 🧠 LLM Yanıtı")
        if answer:
            st.write(answer)
        else:
            st.info("Bu soru domain-dışı ve LLM tarafından bir yanıt üretilemedi.")

        if summary:
            st.caption(summary)
        return

    # ------------------------------------------------------------------
    # Time/period metadata
    # ------------------------------------------------------------------
    meta = None
    if tables:
        first_table = tables[0]
        if isinstance(first_table, dict):
            meta = first_table.get("meta")

    if meta is None and isinstance(data, dict):
        meta = data.get("meta")

    if meta and isinstance(meta, dict):
        period_text = meta.get("effective_period_text")
        anchor = meta.get("effective_anchor_date")
        threshold = meta.get("effective_threshold_date")

        if period_text:
            st.markdown("#### ⏱️ Analiz Dönemi")
            st.info(period_text)

        if anchor or threshold:
            pieces = []
            if threshold:
                pieces.append(f"Başlangıç: `{threshold}`")
            if anchor:
                pieces.append(f"Bitiş: `{anchor}`")
            if pieces:
                st.caption(" • ".join(pieces))

    # ------------------------------------------------------------------
    # Statistical table + AUTO CHART
    # ------------------------------------------------------------------
    if tables:
        table = tables[0]
        rows = table.get("rows", [])
        title = table.get("title", "İstatistiksel Tablo")
        desc = table.get("description")

        st.markdown(f"### 📊 {title}")
        if desc:
            st.caption(desc)

        if rows:
            df = pd.DataFrame(rows)
            df_display = translate_columns(df)
            
            # ════════════════════════════════════════════════════════════
            # 🆕 İNTERAKTİF CHART + TABLO SİSTEMİ
            # ════════════════════════════════════════════════════════════
            chart_type, x_col, y_col = detect_chart_type(df, scenario)
            
            if chart_type != "none" and len(df) >= 2:
                # Unique key: mesaj index + kolon bilgisi
                key_suffix = f"{msg_index}_{x_col}_{y_col}"
                
                # Kontrol satırı
                ctrl_col1, ctrl_col2, ctrl_col3 = st.columns([2, 2, 1])
                
                with ctrl_col3:
                    show_chart = st.checkbox(
                        "📈 Grafik",
                        value=True,
                        key=f"chart_toggle_{key_suffix}",
                        help="Veriyi grafik olarak göster/gizle"
                    )
                
                with ctrl_col2:
                    interactive_mode = st.checkbox(
                        "🔗 İnteraktif",
                        value=False,
                        key=f"interactive_{key_suffix}",
                        help="Grafik ve tablo arasında senkronizasyon"
                    )
                
                if show_chart:
                    with ctrl_col1:
                        chart_options = ["bar", "line", "area"]
                        chart_labels = {
                            "bar": "📊 Çubuk",
                            "line": "📈 Çizgi",
                            "area": "📉 Alan"
                        }
                        
                        default_idx = (
                            1 if chart_type == "line" else
                            2 if chart_type == "area" else 0
                        )
                        
                        selected_chart = st.radio(
                            "Grafik Türü",
                            options=chart_options,
                            format_func=lambda x: chart_labels.get(x, x),
                            index=default_idx,
                            horizontal=True,
                            key=f"chart_type_{key_suffix}",
                            label_visibility="collapsed",
                        )
                    
                    if interactive_mode:
                        # 🆕 İnteraktif mod: Grafik + Tablo senkronize
                        render_interactive_chart_and_table(
                            df=df,
                            df_display=df_display,
                            scenario=scenario,
                            msg_index=msg_index,
                            chart_type_override=selected_chart,
                        )
                    else:
                        # Normal mod: Sadece grafik
                        render_auto_chart(
                            df=df,
                            scenario=scenario,
                            chart_type_override=selected_chart,
                        )
                        st.dataframe(df_display, use_container_width=True, hide_index=True)
                else:
                    # Grafik kapalı, sadece tablo
                    st.dataframe(df_display, use_container_width=True, hide_index=True)
            else:
                # Grafik uygun değil, sadece tablo
                st.dataframe(df_display, use_container_width=True, hide_index=True)
            # ════════════════════════════════════════════════════════════
            
            # 🆕 Debug – rows varken de
            if st.session_state.get("show_debug"):
                render_debug_panel(meta)
            
        else:
            # --- Empty result diagnostics ---
            reason_code = None
            reason_msg = None
            applied_filters = None

            if meta and isinstance(meta, dict):
                reason_code = meta.get("empty_reason") or meta.get("empty_reason_code")
                reason_msg = meta.get("message") or meta.get("error")
                applied_filters = meta.get("applied_filters")

            if reason_code == "anchor_date_missing":
                st.warning("Rölatif dönem için anchor date bulunamadı.")
            elif reason_code == "period_unresolvable":
                st.warning("Rölatif dönem çözümlenemedi.")
            elif reason_code == "query_plan_missing":
                st.warning("QueryPlan üretilemedi.")
            elif reason_code == "no_matching_rows":
                st.info("Filtrelerle eşleşen kayıt bulunamadı.")
            elif reason_msg:
                st.warning(reason_msg)
            else:
                st.info("Bu sorgu için satır dönmedi.")

            if st.session_state.get("show_debug"):
                render_debug_panel(meta)
    else:
        rows = data.get("rows", []) if isinstance(data, dict) else []
        if rows:
            st.markdown("### 📊 İstatistiksel Tablo")
            df = pd.DataFrame(rows)
            df_display = translate_columns(df)
            
            # Fallback data için de grafik
            chart_type, x_col, y_col = detect_chart_type(df, scenario)
            if chart_type != "none" and len(df) >= 2:
                render_auto_chart(df, scenario)
            
            st.dataframe(df_display, use_container_width=True, hide_index=True)

    # Example experiences
    if examples:
        st.markdown("### 🧪 Kayıt Örnekleri")
        for ex in examples:
            if isinstance(ex, dict):
                text = ex.get("text")
            else:
                text = getattr(ex, "text", None)

            if text:
                st.markdown(f"- {text}")
        st.markdown("---")

    # LLM response
    if llm:
        answer = llm.get("answer", "")
        if answer:
            st.markdown("### 🧠 LLM Yorumu")
            st.write(answer)

    # Summary
    if summary:
        st.info(summary)

# ============================================================================
# Sidebar
# ============================================================================

with st.sidebar:
    st.title("🤖 Promptever")
    st.markdown("---")
    # ============================
    # 💬 Dil Modeli Kullanımı
    # ============================
    use_llm = st.checkbox(
        "Dil Modelini Kullan",
        value=False,
        disabled=True,
        help="Seçili değilse cevaplar sadece LRS verisiyle üretilir; dil modeli devre dışı kalır.",
    )

    st.session_state["use_llm"] = use_llm  # 👈 snapshot

    # Bu flag'i bütün aşağıdaki seçimlerde kullanacağız
    disabled_llm_controls = not use_llm

    # ============================
    # 🧠 Dil Modeli
    # ============================

    MODEL_LABELS = {
        "llama3.1:8b": "Llama 3.1 (8B) • Genel Amaçlı",
        "llama3.2:3b": "Llama 3.2 (3B) • Hızlı Yanıt",
        "gemma2:2b": "Gemma 2 (2B) • Ultra Hafif",
        "qwen2.5:0.5b": "Qwen 2.5 (0.5B) • Minimal",
        "RefinedNeuro/RN_TR_R2:latest": "TR-R2 (8B) • Türkçe Muhakeme",
        "RefinedNeuro/Turkcell-LLM-7b-v1:latest": "Turkcell (7B) • Türkçe Uzman",
        "aya-expanse:8b": "Aya (8B) • Çok Dilli",
    }

    MODEL_KEYS = list(MODEL_LABELS.keys())
    default_index = MODEL_KEYS.index("gemma2:2b") if "gemma2:2b" in MODEL_KEYS else 0

    selected_model = st.selectbox(
        "Dil Modeli",
        options=MODEL_KEYS,
        index=default_index,
        help="Model seçimi: Parametre sayısı ve uzmanlık alanı",
        format_func=lambda k: MODEL_LABELS.get(k, k),
        disabled=disabled_llm_controls,
    )

    # ============================
    # 🎭 Dil Modeli Rolü
    # ============================

    ROLE_LABELS = {
        "servis_analisti": "Servis Analisti",
        "cto": "CTO",
        "servis_muduru": "Servis Müdürü",
        "tedarik_zinciri_uzmani": "Tedarik Zinciri Uzmanı",
        "egitmen": "Eğitmen (Bakım-Onarım)",
    }
    ROLE_KEYS = list(ROLE_LABELS.keys())

    selected_role = st.selectbox(
        "Dil Modeli Rolü",
        options=ROLE_KEYS,
        index=0,
        help="Aynı veriyi hangi uzmanın bakış açısından yorumlayacağını belirler.",
        format_func=lambda k: ROLE_LABELS.get(k, k),
        disabled=disabled_llm_controls,
    )

    # ============================
    # ✨ Dil Modeli Davranışı
    # ============================

    BEHAVIOR_LABELS = {
        "balanced": "Dengeli / Analitik",
        "commentary": "Yorumlayıcı",
        "predictive": "Öngörüsel / Senaryo",
        "report": "Rapor Üret (Yapılandırılmış)",
    }
    BEHAVIOR_KEYS = list(BEHAVIOR_LABELS.keys())

    selected_behavior = st.selectbox(
        "Dil Modeli Davranışı",
        options=BEHAVIOR_KEYS,
        index=0,
        help="Cevabın formatını ve tonunu belirler (kısa yorum, rapor, senaryo vb.).",
        format_func=lambda key: BEHAVIOR_LABELS.get(key, key),
        disabled=disabled_llm_controls,
    )

    st.markdown("---")
    st.markdown("### 🧭 Soru Kütüphanesi")

    # ==========================================================
    # ⚡ ROI Hızlı Kazançlar (sadece OK)
    # ==========================================================
    with st.expander("⚡ ROI Hızlı Kazançlar", expanded=True):
        if st.button("📊 İşlem Tipi Dağılımı", use_container_width=True, key="q_roi_ops_dist"):
            st.session_state.quick_query = "Bakım ve onarım işlemlerinin dağılımı nedir?"

        if st.button("📆 Son 2 Yılda Aylara Göre İş Yükü", use_container_width=True, key="q_roi_ops_2y_month"):
            st.session_state.quick_query = "Son 2 yılda bakım ve onarım işlemlerinin aylara göre dağılımı nedir?"

        if st.button("🌦️ Son 2 Yılda Mevsimlere Göre İş Yükü", use_container_width=True, key="q_roi_ops_2y_season"):
            st.session_state.quick_query = "Son 2 yılda bakım ve onarım işlemlerinin mevsimlere göre dağılımı nedir?"

        if st.button("❄️ Kışın En Çok Kullanılan Malzemeler", use_container_width=True, key="q_roi_winter_materials"):
            st.session_state.quick_query = "Kış mevsiminde en çok hangi malzemeler kullanılıyor?"

        if st.button("🚚 Kışın En Çok Gelen Araç Tipleri", use_container_width=True, key="q_roi_winter_vehicle_types"):
            st.session_state.quick_query = "Kış mevsiminde servise en çok hangi araç tipleri geliyor?"

        if st.button("👥 Servise En Çok Gelen Müşteriler", use_container_width=True, key="q_roi_top_customers"):
            st.session_state.quick_query = "Servise en çok gelen müşteriler hangileri?"

        if st.button("💰 Son X Yılda Fiyatı En Çok Artan Malzemeler (Örnek: 3)", use_container_width=True, key="q_roi_price_top"):
            st.session_state.quick_query = "Son 3 yılda fiyatı en çok artan malzemeler hangileri?"

        if st.button("📈 Son X Yılda Mevsimlere Göre Fiyatı En Çok Artan Malzeme Aileleri (Örnek: 2)", use_container_width=True, key="q_roi_season_price_family"):
            st.session_state.quick_query = "Son 2 yılda mevsimlere göre fiyatı en çok artan malzeme aileleri hangileri?"

        if st.button("📈 Son 3 Yılda Fiyatı En Çok Artan Malzeme Aileleri", use_container_width=True, key="q_roi_price_family_top"):
            st.session_state.quick_query = "Son 3 yılda fiyatı en çok artan malzeme aileleri hangileri?"


    # ==========================================================
    # 🧱 Operasyon & Kapasite (sadece OK)
    # ==========================================================
    with st.expander("🧱 Operasyon & Kapasite", expanded=False):
        if st.button("📊 Dağılım (Genel)", use_container_width=True, key="q_ops_all"):
            st.session_state.quick_query = "Bakım ve onarım işlemlerinin dağılımı nedir?"

        if st.button("📅 Yıllara Göre Dağılım", use_container_width=True, key="q_ops_year"):
            st.session_state.quick_query = "Bakım ve onarım işlemlerinin yıllara göre dağılımı nedir?"

        if st.button("🗓️ Yıllara ve Aylara Göre Dağılım", use_container_width=True, key="q_ops_year_month"):
            st.session_state.quick_query = "Bakım ve onarım işlemlerinin yıllara ve aylara göre dağılımı nedir?"

        if st.button("🌦️ Yıllara ve Mevsimlere Göre Dağılım", use_container_width=True, key="q_ops_year_season"):
            st.session_state.quick_query = "Bakım ve onarım işlemlerinin yıllara ve mevsimlere göre dağılımı nedir?"

        if st.button("🍂 Mevsimlere Göre Dağılım", use_container_width=True, key="q_ops_season"):
            st.session_state.quick_query = "Bakım ve onarım işlemlerinin mevsimlere göre dağılımı nedir?"

        if st.button("⏳ Son 2 Yılda Mevsimlere Göre Dağılım", use_container_width=True, key="q_ops_2y_season"):
            st.session_state.quick_query = "Son 2 yılda bakım ve onarım işlemlerinin mevsimlere göre dağılımı nedir?"

        if st.button("⏳ Son 2 Yılda Aylara Göre Dağılım", use_container_width=True, key="q_ops_2y_month"):
            st.session_state.quick_query = "Son 2 yılda bakım ve onarım işlemlerinin aylara göre dağılımı nedir?"

        if st.button("📆 2021 Yılında Aylara Göre Dağılım", use_container_width=True, key="q_ops_2021_month"):
            st.session_state.quick_query = "2021 yılında bakım ve onarım işlemlerinin aylara göre dağılımı nedir?"

        if st.button("🧾 2021 Aralık Dağılım", use_container_width=True, key="q_ops_2021_dec"):
            st.session_state.quick_query = "2021 yılının aralık ayında bakım ve onarım işlemlerinin dağılımı nedir?"

        if st.button("📈 Ay Bazında Trend", use_container_width=True, key="q_ops_month_trend"):
            st.session_state.quick_query = "Ay bazında yapılan bakım/onarım sayıları nasıl değişiyor?"

        if st.button("📅 Günlere Göre Dağılım (Genel)", use_container_width=True, key="q_ops_day_all"):
            st.session_state.quick_query = "Bakım ve onarımın günlere göre dağılımı?"

        if st.button("📅 2022 Yılında Günlere Göre Dağılım", use_container_width=True, key="q_ops_day_2022"):
            st.session_state.quick_query = "2022 yılında bakım ve onarımın günlere göre dağılımı?"

        if st.button("⏳ Son 2 Yılda Günlere Göre Dağılım", use_container_width=True, key="q_ops_day_2y"):
            st.session_state.quick_query = "Son 2 yılda bakım ve onarımın günlere göre dağılımı?"

    # ==========================================================
    # 📦 Stok & Malzeme Kullanımı (sadece OK)
    # ==========================================================
    with st.expander("📦 Stok & Malzeme Kullanımı", expanded=False):
        if st.button("❄️ Kışın En Çok Hangi Malzemeler Kullanılıyor?", use_container_width=True, key="q_stock_winter_materials"):
            st.session_state.quick_query = "Kışın en çok hangi malzemeler kullanılıyor?"

        if st.button("⏳ Son 2 Yılda Kışın En Çok Hangi Malzemeler Kullanılıyor?", use_container_width=True, key="q_stock_winter_2y"):
            st.session_state.quick_query = "Son 2 yılda kışın en çok hangi malzemeler kullanılıyor?"

        if st.button("🗓️ Kışın En Çok Kullanılan Malzemelerin Aylara Göre Dağılımı", use_container_width=True, key="q_stock_winter_month_dist"):
            st.session_state.quick_query = "Kışın en çok kullanılan malzemelerin aylara göre dağılımı?"

        if st.button("🌦️ Mevsimlere Göre En Çok Kullanılan Malzemeler", use_container_width=True, key="q_stock_season_top"):
            st.session_state.quick_query = "Mevsimlere göre en çok kullanılan malzemeler nedir?"

        if st.button("⏳ Son 2 Yılda Mevsimlere Göre En Çok Kullanılan Malzemeler", use_container_width=True, key="q_stock_season_top_2y"):
            st.session_state.quick_query = "Son 2 yılda mevsimlere göre en çok kullanılan malzemeler nedir?"

        if st.button("⏳ Son 2 Yılda Mevsimlere Göre İlk 10 Malzeme", use_container_width=True, key="q_stock_season_top10_2y"):
            st.session_state.quick_query = "Son 2 yılda mevsimlere göre en çok kullanılan ilk 10 malzeme nedir?"

        if st.button("📆 2022'de Mevsimlere Göre İlk 5 Malzeme", use_container_width=True, key="q_stock_season_top5_2022"):
            st.session_state.quick_query = "2022 yılında mevsimlere göre en çok kullanılan ilk 5 malzeme nedir?"

        if st.button("🚛 Araç Modellerine Göre En Çok Kullanılan Malzemeler", use_container_width=True, key="q_stock_by_model"):
            st.session_state.quick_query = "Araç modellerine göre en çok kullanılan malzemeler nedir?"

        if st.button("⏳ Son 2 Yılda Araç Modellerine Göre En Çok Kullanılan Malzemeler", use_container_width=True, key="q_stock_by_model_2y"):
            st.session_state.quick_query = "Son 2 yılda Araç modellerine göre en çok kullanılan malzemeler nedir?"

        if st.button("🧭 Yıllara ve Mevsimlere Göre En Çok Kullanılan Malzemeler (Pivot)", use_container_width=True, key="q_stock_year_season_pivot"):
            st.session_state.quick_query = "Yıllara ve mevsimlere göre en çok kullanılan malzemeler hangileri?"

        if st.button("📈 Son 3 Yılda Fiyatı En Çok Artan Malzeme Aileleri", use_container_width=True, key="q_stock_price_family_top"):
            st.session_state.quick_query = "Son 3 yılda fiyatı en çok artan malzeme aileleri hangileri?"

    # ==========================================================
    # 🚚 Talep Profili (Araç Tipi/Modeli) (sadece OK)
    # ==========================================================
    with st.expander("🚚 Talep Profili (Araç Tipi/Modeli)", expanded=False):
        if st.button("❄️ Kışın En Çok Gelen Araç Tipleri", use_container_width=True, key="q_demand_winter_types"):
            st.session_state.quick_query = "Kışın en çok hangi araç tipleri geliyor?"

        if st.button("📆 2022'de Kışın En Çok Gelen Araç Modelleri", use_container_width=True, key="q_demand_2022_winter_models"):
            st.session_state.quick_query = "2022 yılında kışın en çok hangi araç modelleri geldi?"

        if st.button("❄️ Kışın En Çok Gelen Araç Modelleri", use_container_width=True, key="q_demand_winter_models"):
            st.session_state.quick_query = "Kışın en çok hangi araç modelleri geliyor?"

        if st.button("❄️ Kışın En Çok Gelen Araçlar", use_container_width=True, key="q_demand_winter_vehicles"):
            st.session_state.quick_query = "Kışın en çok hangi araçlar geliyor?"

        if st.button("🗓️ Kışın En Çok Gelen Araç Modellerinin Aylara Göre Dağılımı", use_container_width=True, key="q_demand_winter_models_month"):
            st.session_state.quick_query = "Kışın an çok gelen araç modellerinin aylara göre dağılımı?"

        if st.button("📅 Eylül Ayında En Çok Gelen Araç Modelleri", use_container_width=True, key="q_demand_sep_models"):
            st.session_state.quick_query = "Eylül ayında en çok hangi araç modelleri geliyor?"

        if st.button("🏆 Bakıma En Çok Gelen Araç Modeli", use_container_width=True, key="q_demand_top_model_maint"):
            st.session_state.quick_query = "Bakıma en çok gelen araç modeli hangisi?"

        if st.button("🏆 Servise En Çok Gelen Araç Modeli", use_container_width=True, key="q_demand_top_model_service"):
            st.session_state.quick_query = "Servise en çok gelen araç modeli hangisi?"

        if st.button("🚗 Servise En Çok Gelen Araçlar", use_container_width=True, key="q_demand_top_vehicles"):
            st.session_state.quick_query = "Servise en çok gelen araçlar hangileri?"

        if st.button("🚘 Servise En Çok Gelen Araç Modelleri", use_container_width=True, key="q_demand_top_models"):
            st.session_state.quick_query = "Servise en çok gelen araç modelleri hangileri?"

    # ==========================================================
    # 👥 Müşteri Profili (sadece OK)
    # ==========================================================
    with st.expander("👥 Müşteri Profili", expanded=False):
        if st.button("👥 Servise En Çok Gelen Müşteriler", use_container_width=True, key="q_cust_top"):
            st.session_state.quick_query = "Servise en çok gelen müşteriler hangileri?"

        if st.button("❄️ Kışın Servise En Çok Gelen Müşteriler", use_container_width=True, key="q_cust_winter_top"):
            st.session_state.quick_query = "Kışın servise en çok gelen müşteriler hangileri?"

        if st.button("⏳ Son 2 Yılda Kışın Servise En Çok Gelen Müşteriler", use_container_width=True, key="q_cust_winter_top_2y"):
            st.session_state.quick_query = "son 2 yılda kışın servise en çok gelen müşteriler hangileri?"

        if st.button("🗓️ Aralık Ayında Servise En Çok Gelen Müşteriler", use_container_width=True, key="q_cust_dec_top"):
            st.session_state.quick_query = "Aralık ayında servise en çok gelen müşteriler hangileri?"

    # ==========================================================
    # 🧠 Araç Bazlı İçgörü (değişkenli – sadece OK olan family’ler)
    # ==========================================================
    with st.expander("🧠 Araç Bazlı İçgörü (Şablonlar)", expanded=False):
        st.caption("Metni al → X/Y’yi değiştir → sorgula.")

        if st.button("🧩 Şablon: Son X yılda fiyatı en çok artan malzemeler (Örnek: 3)", use_container_width=True, key="q_tpl_price_x_year"):
            st.session_state.quick_query = "Son 3 yılda fiyatı en çok artan malzemeler hangileri?"

        if st.button("🧩 Şablon: X model + Y malzeme → bir sonraki bakım (Örnek)", use_container_width=True, key="q_tpl_next_maint_xy"):
            st.session_state.quick_query = "RHC 404 (400) model araçlarda, SENSÖR malzemesi kullanıldığında bir sonraki bakımda hangi malzemeler daha sık değişiyor?"

        if st.button("🧩 Şablon: Araç X’in geçmişine göre sık değişen malzemeler (Örnek)", use_container_width=True, key="q_tpl_vehicle_parts"):
            st.session_state.quick_query = "Araç 70886’ın bakım geçmişine göre hangi malzemeler sık değişmiş?"

        if st.button("🧩 Şablon: Araç X'in bakım geçmişi nasıl? (Örnek)", use_container_width=True, key="q_tpl_vehicle_history"):
            st.session_state.quick_query = "Araç 48640'ın bakım geçmişi nasıl?"
    
    st.markdown("---")
    
    # Settings at bottom - in expander
    with st.expander("⚙️ Ayarlar", expanded=False):
        # Collection selection
        st.markdown("#### 📚 Collection Seçimi")
        collections_response = call_rag_api("/collections")
        if collections_response and isinstance(collections_response, dict):
            collections = collections_response.get("collections", ["man_local_service_maintenance", "default"])
        else:
            collections = ["man_local_service_maintenance", "default"]
        
        current_collection = st.session_state.get('collection', 'man_local_service_maintenance')
        selected_collection = st.selectbox(
            "Aktif Collection",
            options=collections,
            index=collections.index(current_collection) if current_collection in collections else 0,
            help="Sorgulanacak vektör veritabanı koleksiyonu",
            key="settings_collection"
        )
        st.session_state['collection'] = selected_collection
        
        st.divider()
        
        # Query settings
        st.markdown("#### 🔍 Sorgu Ayarları")
        
        context_limit = st.slider(
            "Bağlam Limiti",
            min_value=1,
            max_value=20,
            value=st.session_state.get('context_limit', 5),
            help="LRS istatistik sorgularında dönecek satır sayısı",
            key="settings_context_limit"
        )
        st.session_state['context_limit'] = context_limit
        
        score_threshold = st.slider(
            "Minimum Benzerlik Skoru",
            min_value=0.0,
            max_value=1.0,
            value=st.session_state.get('score_threshold', 0.3),
            step=0.05,
            help="Semantic search için minimum skor eşiği",
            key="settings_score_threshold"
        )
        st.session_state['score_threshold'] = score_threshold
        
        st.divider()
        
        # LRS Statistics
        st.markdown("#### 📊 LRS İstatistikleri")
        
        if st.button("🔄 Genel İstatistikleri Yenile", use_container_width=True, key="settings_refresh_stats"):
            with st.spinner("Yükleniyor..."):
                stats = call_rag_api("/lrs/stats/general")
                if stats and "data" in stats:
                    data_stats = stats["data"]
                    
                    st.metric("Toplam Statement", f"{data_stats.get('totalStatements', 0):,}")
                    st.metric("Araç Sayısı", f"{data_stats.get('uniqueVehicles', 0):,}")
                    st.metric("Arıza Oranı", f"{data_stats.get('faultCodeRatio', 0):.1f}%")
                else:
                    st.info("Genel istatistik endpoint'i henüz hazır değil.")
        
        st.divider()
        st.session_state["show_debug"] = st.checkbox("🪲 Debug panelini göster", value=False)
        # API Status
        st.markdown("#### 🏥 API Durumu")
        
        health = call_rag_api("/health")
        if health:
            status = health.get("status", "unknown")
            
            if status in ("ok", "healthy"):
                st.success("✅ RAG API: Çalışıyor")
            else:
                st.error(f"❌ RAG API: {status}")
            
            details = health.get("details", {})
            for name, val in details.items():
                status_text = str(val).lower()
                if status_text in ("alive", "ok", "healthy", "true"):
                    st.caption(f"✅ {name}: Çalışıyor")
                else:
                    st.caption(f"❌ {name}: {val}")
        else:
            st.error("❌ API'ye bağlanılamıyor")

# ============================================================================
# Main Content
# ============================================================================

st.title("🤖 Promptever RAG Chat")
st.markdown("**Servis Bakım & Onarım Analitiği** • v3.5")

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []

if "quick_query" not in st.session_state:
    st.session_state.quick_query = None

if "collection" not in st.session_state:
    st.session_state.collection = "man_local_service_maintenance"

if "context_limit" not in st.session_state:
    st.session_state.context_limit = 5

if "score_threshold" not in st.session_state:
    st.session_state.score_threshold = 0.3

# 📊 Genel Bakış Paneli (isteğe bağlı açılır)
with st.expander("📊 Genel Bakış (LRS üzerinden hızlı grafikler)", expanded=False):
    render_overview_dashboard()

# Display chat messages (history)
for msg_idx, message in enumerate(st.session_state.messages):
    with st.chat_message(message["role"]):
        if message["role"] == "assistant":
            intent = message.get("intent", "statistical")
            display_intent_badge(intent)

            # 1) Cevabı çiz
            if "response" in message:
                # Yeni MVP schema
                display_mvp_response(message["response"], msg_index=msg_idx)
            else:
                # Eski fallback şema
                if intent == "statistical":
                    data = message.get("data", {})
                    display_statistical_results(data)
                    if "summary" in message and message["summary"]:
                        st.info(message["summary"])
                elif intent == "semantic":
                    answer = message.get("answer", "")
                    sources = message.get("sources", [])
                    display_semantic_results(answer, sources)
                elif intent == "hybrid":
                    answer = message.get("answer", "")
                    statistics = message.get("statistics", {})
                    sources = message.get("semantic_sources", [])
                    display_hybrid_results(answer, statistics, sources)

            # 2) Caption HER ZAMAN burada çizilsin
            if "model" in message and "elapsed" in message:
                # intent/scenario snapshot
                intent = message.get("intent", intent)
                scenario = message.get("scenario")

                # LLM kullanımı: mesajdaki snapshot
                llm_used = message.get("use_llm", True)
                chain = get_chain_label(intent, scenario, llm_used)

                # Rol → mesajdan oku
                role_key = message.get("llm_role")
                role_label = ROLE_LABELS.get(role_key, role_key)
                role_part = f" • 🎭 Rol: {role_label}" if llm_used else ""

                # Davranış → mesajdan oku
                behavior_key = message.get("behavior")
                behavior_label = BEHAVIOR_LABELS.get(behavior_key, behavior_key)
                behavior_part = f" • ✨ Davranış: {behavior_label}" if llm_used else ""

                st.caption(
                    f"🧠 `{message['model']}`"
                    f" • ⏱️ {message['elapsed']:.1f}s"
                    f" • 🔗 {chain}"
                    f"{role_part}"
                    f"{behavior_part}"
                )

        else:
            st.write(message["content"])

# Chat input - ALWAYS SHOW
query = st.chat_input("Sorunuzu yazın...")

# Check if we have a quick query to process
if not query and st.session_state.quick_query:
    query = st.session_state.quick_query
    st.session_state.quick_query = None

# Process query
if query:
    # Add user message
    st.session_state.messages.append({
        "role": "user",
        "content": query
    })

    # Display user message
    with st.chat_message("user"):
        st.write(query)

    # Get response from API
    with st.chat_message("assistant"):
        with st.spinner("Düşünüyorum..."):
            payload = {
                "query": query,
                "collection": st.session_state.collection,
                "use_llm": use_llm,
                "limit": st.session_state.context_limit,
                "model": selected_model if use_llm else None,
                "role": selected_role,  # 🔴 BUNU EKLE
                "behavior": selected_behavior,  # 👈 BUNU EKLE
            }

            t0 = time.time()
            response = call_rag_api(
                "/chat",
                method="POST",
                data=payload,
                timeout=320,
            )
            elapsed = time.time() - t0

            if response:
                intent = response.get("intent", "statistical")
                scenario = response.get("scenario")

                display_intent_badge(intent)
                # Yeni mesaj için index = mevcut mesaj sayısı (henüz append edilmedi)
                display_mvp_response(response, msg_index=len(st.session_state.messages))

                chain = get_chain_label(intent, scenario, use_llm)

                if use_llm:
                    role_part = f" • 🎭 Rol: {ROLE_LABELS.get(selected_role, selected_role)}"
                    behavior_part = f" • ✨ Davranış: {BEHAVIOR_LABELS.get(selected_behavior, selected_behavior)}"
                else:
                    role_part = ""
                    behavior_part = ""

                st.caption(
                    f"🧠 `{selected_model}`"
                    f" • ⏱️ {elapsed:.1f}s"
                    f" • 🔗 {chain}"
                    f"{role_part}"
                    f"{behavior_part}"
                )

                st.session_state.messages.append({
                    "role": "assistant",
                    "intent": intent,
                    "scenario": scenario,
                    "response": response,
                    "model": selected_model,
                    "elapsed": elapsed,
                    "llm_role": selected_role,      # rol key
                    "behavior": selected_behavior,  # davranış key
                    "use_llm": use_llm,             # 👈 bunu ekle
                })

            else:
                st.error("API'den yanıt alınamadı")

# ============================================================================
# Footer
# ============================================================================

st.markdown("---")
st.markdown("""
<div style="text-align: center; color: #888; font-size: 12px;">
    Promptever RAG Stack v3.5 • Service Analytics & LRS → LLM Insights<br>
    Powered by Qdrant, Ollama & FastAPI
</div>
""", unsafe_allow_html=True)