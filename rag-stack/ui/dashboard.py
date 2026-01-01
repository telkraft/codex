"""
Genel Bakış Paneli (Dashboard)
==============================

Bu sayfa, LRS üzerindeki verilerden istatistiksel özet grafikler üretir.

- Backend: FastAPI /chat endpoint'i
- LLM: devre dışı (use_llm = False)
- Kaynak: LRS istatistik tabloları (tables[0].rows)

Not:
  - app.py ile aynı RAG_API_URL ve call_rag_api yapısını kullanır.
  - collection, context_limit vb. ayarları st.session_state içinden okur;
    yoksa makul varsayılanlar kullanır.
"""

import time
from typing import Dict, Any, Optional

import pandas as pd
import requests
import streamlit as st

# ============================================================================
# Configuration
# ============================================================================

RAG_API_URL = "http://rag-api:8000"

st.set_page_config(
    page_title="Servis Analitiği - Genel Bakış",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================================
# Helper Functions
# ============================================================================


def call_rag_api(
    endpoint: str,
    method: str = "GET",
    data: Optional[Dict[str, Any]] = None,
    timeout: int = 120,
) -> Optional[Dict[str, Any]]:
    """RAG API endpoint çağrısı (app.py'dekiyle uyumlu)"""
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


def _extract_table_df(response: Dict[str, Any]) -> pd.DataFrame:
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


def _run_stat_query(query: str, limit: int = 100) -> pd.DataFrame:
    """
    /chat endpoint'ine istatistik odaklı bir soru gönderir,
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

    t0 = time.time()
    response = call_rag_api("/chat", method="POST", data=payload, timeout=320)
    elapsed = time.time() - t0

    if response is None:
        st.error("API'den yanıt alınamadı")
        return pd.DataFrame()

    intent = response.get("intent", "statistical")
    scenario = response.get("scenario", "")
    st.caption(
        f"🔗 intent: `{intent}` • scenario: `{scenario}` • ⏱️ {elapsed:.1f}s"
    )

    df = _extract_table_df(response)
    return df


# ============================================================================
# Dashboard Sections
# ============================================================================


def render_summary_cards():
    """LRS genel istatistik kartları (/lrs/stats/general)"""
    st.subheader("📌 LRS Genel Fotoğraf")

    stats = call_rag_api("/lrs/stats/general")
    if not stats or "data" not in stats:
        st.info("Genel istatistik endpoint'i henüz hazır değil veya veri dönmedi.")
        return

    data_stats = stats["data"]

    col1, col2, col3 = st.columns(3)
    col1.metric(
        "Toplam Statement",
        f"{data_stats.get('totalStatements', 0):,}",
    )
    col2.metric(
        "Araç Sayısı",
        f"{data_stats.get('uniqueVehicles', 0):,}",
    )
    col3.metric(
        "Arıza Oranı",
        f"{data_stats.get('faultCodeRatio', 0):.1f}%",
    )


def render_time_tab():
    """Zaman eksenli grafikler (yıl / mevsim bazlı)"""
    st.markdown("### ⏱️ Zaman Ekseni (Yıl & Mevsim)")

    # 1) Yıllara göre bakım + onarım dağılımı
    st.markdown("#### Yıllara göre bakım & onarım dağılımı")
    df_year = _run_stat_query("Yıllara göre bakım ve onarım işlemlerinin dağılımı nedir?")

    if not df_year.empty:
        # Beklenen kolonlar: year, verbType, count
        if {"year", "verbType", "count"}.issubset(df_year.columns):
            pivot = (
                df_year.pivot_table(
                    index="year",
                    columns="verbType",
                    values="count",
                    aggfunc="sum",
                )
                .fillna(0)
                .sort_index()
            )

            st.line_chart(pivot)
            st.dataframe(df_year, use_container_width=True, hide_index=True)
        else:
            st.info("Bu grafik için beklenen kolonlar (year, verbType, count) bulunamadı.")
            st.dataframe(df_year, use_container_width=True, hide_index=True)
    else:
        st.info("Yıllara göre dağılım için veri dönmedi.")

    st.markdown("---")

    # 2) Mevsimlere göre bakım + onarım dağılımı
    st.markdown("#### Mevsimlere göre bakım & onarım dağılımı")
    df_season = _run_stat_query("Mevsimlere göre bakım ve onarım işlemlerinin dağılımı nedir?")

    if not df_season.empty:
        # Beklenen kolonlar: season, verbType, count
        if {"season", "verbType", "count"}.issubset(df_season.columns):
            pivot = (
                df_season.pivot_table(
                    index="season",
                    columns="verbType",
                    values="count",
                    aggfunc="sum",
                )
                .fillna(0)
            )

            # Mevsim sıralaması eldeki veriye göre yapılır
            st.bar_chart(pivot)
            st.dataframe(df_season, use_container_width=True, hide_index=True)
        else:
            st.info(
                "Bu grafik için beklenen kolonlar (season, verbType, count) bulunamadı."
            )
            st.dataframe(df_season, use_container_width=True, hide_index=True)
    else:
        st.info("Mevsimlere göre dağılım için veri dönmedi.")


def render_vehicle_tab():
    """Araç tipi / modeli bazlı grafikler"""
    st.markdown("### 🚚 Araçlar (Tip & Model)")

    # 1) Araç tipine göre bakım & onarım dağılımı
    st.markdown("#### Araç tiplerine göre bakım & onarım dağılımı")
    df_type = _run_stat_query(
        "Araç tiplerine göre bakım ve onarım işlemlerinin dağılımı nedir?"
    )

    if not df_type.empty:
        # Beklenen kolonlar: vehicleType, verbType, count
        if {"vehicleType", "verbType", "count"}.issubset(df_type.columns):
            pivot = (
                df_type.pivot_table(
                    index="vehicleType",
                    columns="verbType",
                    values="count",
                    aggfunc="sum",
                )
                .fillna(0)
                .sort_values(by=pivot.columns.tolist(), ascending=False)
            )
            st.bar_chart(pivot)
            st.dataframe(df_type, use_container_width=True, hide_index=True)
        else:
            st.info(
                "Bu grafik için beklenen kolonlar (vehicleType, verbType, count) bulunamadı."
            )
            st.dataframe(df_type, use_container_width=True, hide_index=True)
    else:
        st.info("Araç tiplerine göre dağılım için veri dönmedi.")

    st.markdown("---")

    # 2) Araç modeline göre en çok gelenler
    st.markdown("#### En çok gelen araç modelleri")
    df_model = _run_stat_query(
        "En çok servise gelen araç modelleri hangileri?"
    )

    if not df_model.empty:
        # İki ihtimal:
        #   a) vehicleModel + count
        #   b) entity + count (top_entities)
        if {"vehicleModel", "count"}.issubset(df_model.columns):
            df_plot = (
                df_model.sort_values("count", ascending=False)
                .head(20)
                .set_index("vehicleModel")
            )
            st.bar_chart(df_plot["count"])
            st.dataframe(df_model, use_container_width=True, hide_index=True)
        elif {"entity", "count"}.issubset(df_model.columns):
            df_plot = (
                df_model.sort_values("count", ascending=False)
                .head(20)
                .set_index("entity")
            )
            st.bar_chart(df_plot["count"])
            st.dataframe(df_model, use_container_width=True, hide_index=True)
        else:
            st.info("Bu grafik için beklenen kolonlar bulunamadı (vehicleModel/entity, count).")
            st.dataframe(df_model, use_container_width=True, hide_index=True)
    else:
        st.info("Araç modeli bazlı istatistik için veri dönmedi.")


def render_material_tab():
    """Malzeme ve malzeme aileleri bazlı grafikler"""
    st.markdown("### 🧩 Malzemeler")

    # 1) Malzeme ailelerine göre kullanım dağılımı
    st.markdown("#### Malzeme ailelerine göre kullanım dağılımı")
    df_family = _run_stat_query(
        "Malzeme ailelerine göre kullanım dağılımı nedir?"
    )

    if not df_family.empty:
        # Beklenen kolonlar: materialFamily, count
        if {"materialFamily", "count"}.issubset(df_family.columns):
            df_plot = (
                df_family.sort_values("count", ascending=False)
                .head(20)
                .set_index("materialFamily")
            )
            st.bar_chart(df_plot["count"])
            st.dataframe(df_family, use_container_width=True, hide_index=True)
        else:
            st.info(
                "Bu grafik için beklenen kolonlar (materialFamily, count) bulunamadı."
            )
            st.dataframe(df_family, use_container_width=True, hide_index=True)
    else:
        st.info("Malzeme aileleri için istatistik dönmedi.")

    st.markdown("---")

    # 2) En çok kullanılan malzemeler
    st.markdown("#### En çok kullanılan malzemeler")
    df_material = _run_stat_query("En çok kullanılan malzemeler hangileri?")

    if not df_material.empty:
        # İki ihtimal:
        #   a) materialName + count
        #   b) entity + count (top_entities)
        if {"materialName", "count"}.issubset(df_material.columns):
            df_plot = (
                df_material.sort_values("count", ascending=False)
                .head(20)
                .set_index("materialName")
            )
            st.bar_chart(df_plot["count"])
            st.dataframe(df_material, use_container_width=True, hide_index=True)
        elif {"entity", "count"}.issubset(df_material.columns):
            df_plot = (
                df_material.sort_values("count", ascending=False)
                .head(20)
                .set_index("entity")
            )
            st.bar_chart(df_plot["count"])
            st.dataframe(df_material, use_container_width=True, hide_index=True)
        else:
            st.info("Bu grafik için beklenen kolonlar bulunamadı (materialName/entity, count).")
            st.dataframe(df_material, use_container_width=True, hide_index=True)
    else:
        st.info("Malzeme bazlı istatistik için veri dönmedi.")


# ============================================================================
# Main
# ============================================================================


def render_dashboard():
    st.title("📊 Servis Bakım & Onarım - Genel Bakış")
    st.markdown(
        "Bu panel, tüm LRS verisi üzerinden **LLM kullanmadan** istatistiksel "
        "özetler üretir. Soru cümleleri backend'deki intent router'a gider, "
        "dönen tablolar grafikleştirilir."
    )

    # collection / context_limit yoksa, minimum varsayılanları ayarla
    if "collection" not in st.session_state:
        st.session_state.collection = "man_local_service_maintenance"
    if "context_limit" not in st.session_state:
        st.session_state.context_limit = 50

    render_summary_cards()

    st.markdown("---")

    tab1, tab2, tab3 = st.tabs(["⏱️ Zaman", "🚚 Araçlar", "🧩 Malzemeler"])

    with tab1:
        render_time_tab()
    with tab2:
        render_vehicle_tab()
    with tab3:
        render_material_tab()


if __name__ == "__main__":
    render_dashboard()
