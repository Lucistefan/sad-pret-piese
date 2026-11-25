"""Aspect comun: stil CSS, antet de pagină, carduri, stil grafice."""
from __future__ import annotations

import io

import pandas as pd
import streamlit as st

PAL = {"Frâne": "#2563eb", "Filtre": "#16a34a", "Suspensie": "#f59e0b", "Ambreiaj": "#dc2626"}

CSS = """
<style>
/* conținut mai aerisit */
.block-container {padding-top: 2.2rem; padding-bottom: 3rem; max-width: 1280px;}
/* antet de pagină */
.ph {display:flex; align-items:center; gap:14px; margin: 0 0 1.1rem 0;}
.ph .ic {font-size: 1.6rem; width: 52px; height: 52px; border-radius: 14px; display:flex; align-items:center;
         justify-content:center; background: linear-gradient(135deg,#2563eb,#1e40af); color:white;
         box-shadow: 0 6px 16px rgba(37,99,235,.25);}
.ph h1 {font-size: 1.85rem !important; margin: 0 !important; padding: 0 !important; line-height: 1.15;}
.ph p {margin: 2px 0 0 0; color: #64748b; font-size: .95rem;}
/* carduri KPI */
div[data-testid="stMetric"] {background: #ffffff; border: 1px solid #e2e8f0; border-radius: 14px;
    padding: 14px 18px; box-shadow: 0 1px 2px rgba(15,23,42,.04), 0 4px 14px rgba(15,23,42,.04);}
div[data-testid="stMetric"] label p {color:#64748b; font-weight:600; font-size:.82rem;}
div[data-testid="stMetricValue"] {font-weight: 800; color:#0f172a;}
/* containere cu bordură = carduri albe */
div[data-testid="stVerticalBlockBorderWrapper"]:has(> div > div[data-testid="stVerticalBlock"]) {
    background: #ffffff; border-radius: 14px;}
/* titluri secțiuni */
h3 {font-size: 1.12rem !important; font-weight: 700 !important; color:#0f172a;}
/* butoane de descărcare mai vizibile */
div[data-testid="stDownloadButton"] button {font-weight: 600;}
/* bara laterală */
section[data-testid="stSidebar"] hr {border-color:#334155;}
</style>
"""


def setup():
    st.markdown(CSS, unsafe_allow_html=True)


def header(icon: str, title: str, subtitle: str = ""):
    sub = f"<p>{subtitle}</p>" if subtitle else ""
    st.markdown(f'<div class="ph"><div class="ic">{icon}</div><div><h1>{title}</h1>{sub}</div></div>',
                unsafe_allow_html=True)


def card(title: str | None = None):
    c = st.container(border=True)
    if title:
        c.markdown(f"### {title}")
    return c


def style_fig(fig, height=380, legend_bottom=False):
    fig.update_layout(height=height, margin=dict(l=8, r=8, t=30 if fig.layout.title.text else 10, b=8),
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      font=dict(size=13), hoverlabel=dict(bgcolor="white"))
    if legend_bottom:
        fig.update_layout(legend=dict(orientation="h", y=-0.18, x=0, title=None))
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(gridcolor="#eef2f7", zeroline=False)
    return fig


def verdict_badge(v: str) -> str:
    return {"Competitiv": "🟢 Competitiv", "Prea scump": "🔴 Prea scump"}.get(v, v)


def pozitie_badge(v: str) -> str:
    return {"cel mai ieftin": "⬇️ cel mai ieftin", "sub medie": "↘️ sub medie",
            "peste medie": "↗️ peste medie", "cel mai scump": "⬆️ cel mai scump"}.get(v, v)


def xlsx_bytes(df: pd.DataFrame, sheet="Date") -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        df.to_excel(w, sheet_name=sheet, index=False)
        ws = w.book[sheet]
        for i, col in enumerate(df.columns, 1):
            width = max(len(str(col)), *(len(str(v)) for v in df[col].head(100))) + 2
            ws.column_dimensions[ws.cell(1, i).column_letter].width = min(width, 40)
    return buf.getvalue()
