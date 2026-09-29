# app.py — Monitor de Bolsa TAG (ETFs · Ecossistema AI)
# App Streamlit independente do Monitor Offshore de Crédito.
# Rodar:  streamlit run app.py
# =============================================================================
import os
import sys

import streamlit as st

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
from views import (load_data, render_header_note, render_overview, render_strategy,  # noqa: E402
                   render_top10, render_lookthrough, ETF_COLORS, _br_date, _pct)

_IMG_DIR = os.path.join(_HERE, "img")


def main():
    st.set_page_config(
        page_title="Monitor Bolsa - TAG Investimentos",
        page_icon=os.path.join(_IMG_DIR, "Logo_Site.png"),
        layout="wide",
        initial_sidebar_state="expanded",
    )

    st.markdown("""<style>
        header[data-testid="stHeader"] { display: none !important; height: 0 !important; min-height: 0 !important; }
        #MainMenu, footer, #stDecoration { display: none !important; }
        .stApp { margin-top: -4rem !important; }
        div[data-testid="stAppViewBlockContainer"] { padding-top: 0 !important; margin-top: -2rem !important; }

        :root { --tag-vinho: #630d24; --tag-laranja: #FF8853; }
        [data-testid="stSidebar"] { background-color: var(--tag-vinho); }
        [data-testid="stSidebar"] * { color: white !important; }
        [data-testid="stSidebar"] > div:first-child { padding-top: 1rem !important; }
        .banner-tag h1 { color: #fff !important; margin: 0; font-size: 1.6rem; font-weight: 700; }
        .banner-sub { font-size: .92rem; font-weight: 400; color: rgba(255,255,255,.8); margin-top: .3rem; }
        .main label { color: #630d24 !important; font-size: 0.85rem !important; font-weight: 600 !important; }
        .section-title::before { content: ''; display: inline-block; width: 5px; height: 22px; background: #FF8853;
                                 border-radius: 2px; margin-right: 10px; vertical-align: middle; }
        div[data-baseweb="select"] > div { background: #fff !important; border: 1.5px solid #d4d4d4 !important; border-radius: 8px !important; }
        li[role="option"][aria-selected="true"] { background: #630d24 !important; color: #fff !important; }
        @media print {
            [data-testid="stSidebar"], header, [data-testid="stToolbar"] { display: none !important; }
            [data-testid="stAppViewBlockContainer"] { max-width: 100% !important; padding: 0 !important; }
        }
    </style>""", unsafe_allow_html=True)

    data = load_data()

    # ── Sidebar ──
    with st.sidebar:
        try:
            st.image(os.path.join(_IMG_DIR, "logo.png"), width=180)
        except FileNotFoundError:
            st.markdown("<p style='font-size:1.2rem;font-weight:700'>TAG</p>", unsafe_allow_html=True)
        st.markdown("<div style='margin:0.8rem 0 0.3rem 0;font-size:0.75rem;font-weight:600;"
                    "letter-spacing:.5px;opacity:.85'>CARTEIRA DE BOLSA</div>", unsafe_allow_html=True)
        rows = "".join(
            f"<div style='display:flex;justify-content:space-between;align-items:center;padding:3px 0;"
            f"font-size:0.85rem;border-bottom:1px solid rgba(255,255,255,.12)'>"
            f"<span><span style='display:inline-block;width:9px;height:9px;border-radius:2px;"
            f"background:{ETF_COLORS[e['key']]};border:1px solid rgba(255,255,255,.7);margin-right:7px'></span>{e['key']}</span>"
            f"<span>{_pct(e['weight'], 1)}</span></div>"
            for e in data["etfs"])
        st.markdown(rows, unsafe_allow_html=True)
        st.markdown(
            f"<div style='margin-top:1rem;font-size:0.75rem;opacity:.8;line-height:1.5'>"
            f"Dados até {_br_date(data['reference_date'])}<br>Fonte: Morningstar (MCP)</div>",
            unsafe_allow_html=True)

    # ── Banner ──
    st.markdown("""
    <div class='banner-tag' style='background: linear-gradient(135deg, #630d24 0%, #7a2a45 60%, #630d24 100%);
                padding: 1.5rem 2.5rem; border-radius: 10px; margin-bottom: 1.5rem;
                box-shadow: 0 4px 12px rgba(92,31,51,0.3);'>
        <h1>Monitor de Bolsa — ETFs TAG</h1>
        <p class='banner-sub'>Ecossistema AI · CSPX · CIBR · BKCH · BRIJ · SOXQ · DRAM · GRDU</p>
    </div>
    """, unsafe_allow_html=True)

    render_header_note()

    tab_geral, tab_estrategia, tab_top10, tab_carteira = st.tabs(
        ["📊 Visão Geral", "🧭 Estratégia & Ecossistema", "🔟 Top 10 por ETF", "🏆 Carteira TAG (look-through)"]
    )
    with tab_geral:
        render_overview()
    with tab_estrategia:
        render_strategy()
    with tab_top10:
        render_top10()
    with tab_carteira:
        render_lookthrough()


if __name__ == "__main__":
    main()
