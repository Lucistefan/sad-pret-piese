"""Aspect comun: stil CSS, antet de pagină, carduri, filtre, comutator de grafic, explicații."""
from __future__ import annotations

import io

import pandas as pd
import plotly.express as px
import streamlit as st

PAL = {"Frâne": "#2563eb", "Filtre": "#16a34a", "Suspensie": "#f59e0b", "Ambreiaj": "#dc2626"}

CSS = """
<style>
.block-container {padding-top: 4.2rem; padding-bottom: 3rem; max-width: 1280px;}
/* antet de pagină */
.ph {display:flex; align-items:center; gap:14px; margin: 0 0 .4rem 0;}
.ph .ic {font-size: 1.6rem; min-width: 52px; height: 52px; border-radius: 14px; display:flex; align-items:center;
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
h3 {font-size: 1.12rem !important; font-weight: 700 !important; color:#0f172a;}
div[data-testid="stDownloadButton"] button {font-weight: 600;}
section[data-testid="stSidebar"] hr {border-color:#334155;}
/* filtre active */
.chips {display:flex; flex-wrap:wrap; gap:6px; margin:.2rem 0 .6rem 0;}
.chip {background:#eff6ff; color:#1d4ed8; border:1px solid #bfdbfe; border-radius:999px; padding:2px 10px;
       font-size:.8rem; font-weight:600;}
.chip.muted {background:#f8fafc; color:#64748b; border-color:#e2e8f0; font-weight:500;}

/* ===== ecran mic (telefon / tabletă) ===== */
@media (max-width: 820px) {
  .block-container {padding: 4rem .7rem 2rem .7rem;}
  .ph {gap:10px;}
  .ph .ic {min-width: 40px; height: 40px; font-size: 1.2rem; border-radius: 11px;}
  .ph h1 {font-size: 1.35rem !important;}
  .ph p {font-size: .82rem;}
  div[data-testid="stMetric"] {padding: 10px 12px;}
  div[data-testid="stMetricValue"] {font-size: 1.45rem !important;}
  /* coloanele se așază una sub alta */
  div[data-testid="stHorizontalBlock"] {flex-wrap: wrap !important; gap: .6rem !important;}
  div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"] {min-width: calc(50% - .6rem) !important;
      flex: 1 1 calc(50% - .6rem) !important;}
}
@media (max-width: 520px) {
  div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"] {min-width: 100% !important;
      flex: 1 1 100% !important;}
}
</style>
"""


def setup():
    st.markdown(CSS, unsafe_allow_html=True)


# ------------------------------------------------------------------ antet + explicații
def header(icon: str, title: str, subtitle: str = "", explicatie: str | None = None):
    """Antetul paginii; dacă există explicație, apare un buton „Cum funcționează?” lângă titlu."""
    sub = f"<p>{subtitle}</p>" if subtitle else ""
    a, b = st.columns([5, 1.3], vertical_alignment="center")
    a.markdown(f'<div class="ph"><div class="ic">{icon}</div><div><h1>{title}</h1>{sub}</div></div>',
               unsafe_allow_html=True)
    if explicatie and st.session_state.get("explicatii", True):
        with b.popover("Cum funcționează?", icon=":material/help:", width="stretch"):
            st.markdown(explicatie)


def card(title: str | None = None):
    c = st.container(border=True)
    if title:
        c.markdown(f"### {title}")
    return c


# ------------------------------------------------------------------ filtre
def filtre_active(selectii: dict):
    """Arată doar filtrele care sunt efectiv selectate; altfel scrie „toate datele”."""
    chips = []
    for nume, val in selectii.items():
        if val is None or val == [] or val == "" or val is False:
            continue
        txt = ", ".join(map(str, val)) if isinstance(val, (list, tuple)) else str(val)
        chips.append(f'<span class="chip">{nume}: {txt}</span>')
    html = "".join(chips) if chips else '<span class="chip muted">Fără filtre: se afișează toate datele</span>'
    st.markdown(f'<div class="chips">{html}</div>', unsafe_allow_html=True)
    return bool(chips)


def filtru_multi(container, label, optiuni, key):
    """Multiselect care pornește GOL (= toate). Nu pre-bifează nimic."""
    return container.multiselect(label, optiuni, default=[], key=key, placeholder="Toate")


def reset_filtre(prefix: str):
    """Șterge valorile filtrelor unei pagini → widget-urile revin la starea inițială (fără filtre)."""
    for k in [k for k in st.session_state.keys() if str(k).startswith(prefix)]:
        del st.session_state[k]


def sau_toate(selectie, toate):
    """Filtru gol → toate valorile."""
    return list(selectie) if selectie else list(toate)


# ------------------------------------------------------------------ comutator tip grafic
def tip_grafic(key: str, optiuni: list[str], default: str | None = None):
    return st.segmented_control("Tip grafic", optiuni, default=default or optiuni[0], key=key,
                                label_visibility="collapsed") or (default or optiuni[0])


def grafic(df, x, y, tip, color=None, color_map=None, labels=None, barmode="group", height=380, order=None):
    """Același set de date desenat ca: Coloane / Coloane stivuite / Linii / Arie / Plăcintă / Bare orizontale."""
    labels = labels or {}
    kw = dict(color=color, color_discrete_map=color_map, labels=labels)
    if tip == "Linii":
        fig = px.line(df, x=x, y=y, markers=True, **kw)
    elif tip == "Arie":
        fig = px.area(df, x=x, y=y, **kw)
    elif tip == "Plăcintă":
        g = df.groupby(color or x, as_index=False)[y].sum() if color else df
        fig = px.pie(g, names=color or x, values=y, hole=0.55, color=color or x,
                     color_discrete_map=color_map)
    elif tip == "Bare orizontale":
        fig = px.bar(df, y=x, x=y, orientation="h", text_auto=True, **kw)
    elif tip == "Coloane stivuite":
        fig = px.bar(df, x=x, y=y, barmode="stack", **kw)
    else:  # Coloane
        fig = px.bar(df, x=x, y=y, barmode=barmode, text_auto=True, **kw)
    if order is not None and tip != "Plăcintă":
        axis = "yaxis" if tip == "Bare orizontale" else "xaxis"
        fig.update_layout(**{axis: dict(categoryorder="array", categoryarray=order)})
    return style_fig(fig, height, legend_bottom=True)


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
