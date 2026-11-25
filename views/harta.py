import plotly.express as px
import streamlit as st

from core.db import q
from core.reports import map_plotly, map_png
from core.state import get_con, sql_box
from core.ui import card, header, style_fig, xlsx_bytes

header("🌍", "Hartă comenzi", "Unde se vând piesele: comenzi pe țări")

con, tables, log = get_con()
with card():
    c1, c2 = st.columns([1, 2])
    minim = c1.slider("Minim comenzi", 0, 100, 0)
    tip = c2.segmented_control("Afișare", ["Hartă colorată", "Cercuri proporționale", "Ambele"], default="Ambele") \
        or "Ambele"

sql = """SELECT cod_tara, tara, iso3, comenzi,
       ROUND(100.0 * comenzi / (SELECT SUM(comenzi) FROM comenzi_tari), 1) AS pondere_pct
FROM comenzi_tari
WHERE comenzi >= :minim
ORDER BY comenzi DESC"""
tari = q(con, sql, {"minim": minim})
if tari.empty:
    st.info("Nicio țară cu atâtea comenzi.")
    st.stop()

k = st.columns(4)
k[0].metric("Țări", len(tari))
k[1].metric("Comenzi", int(tari["comenzi"].sum()))
k[2].metric("Piața principală", tari.iloc[0]["tara"], f"{tari.iloc[0]['pondere_pct']:.0f}% din comenzi", delta_color="off", delta_arrow="off")
k[3].metric("Top 3 țări", f"{tari.head(3)['pondere_pct'].sum():.0f}%", "din total comenzi", delta_color="off", delta_arrow="off")

with card():
    fig = map_plotly(tari, choropleth=tip != "Cercuri proporționale", bubbles=tip != "Hartă colorată")
    fig.update_layout(title=None, margin=dict(l=0, r=0, t=0, b=0), paper_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig)
    sql_box(sql, {"minim": minim})
    d1, d2, d3, _ = st.columns([1, 1, 1, 2])
    d1.download_button("⬇️ Hartă PNG", map_png(tari), "harta_comenzi.png", "image/png", width="stretch")
    d2.download_button("⬇️ Hartă HTML", fig.to_html(include_plotlyjs="cdn"), "harta_comenzi.html", "text/html",
                       width="stretch")
    d3.download_button("⬇️ Date Excel", xlsx_bytes(tari, "Comenzi pe tari"), "comenzi_tari.xlsx", width="stretch")

a, b = st.columns([3, 2])
with a:
    with card("Clasament"):
        figb = px.bar(tari.sort_values("comenzi"), x="comenzi", y="tara", orientation="h", text="comenzi",
                      labels={"comenzi": "", "tara": ""})
        figb.update_traces(marker_color="#2563eb")
        st.plotly_chart(style_fig(figb, 430))
with b:
    with card("Detalii"):
        st.dataframe(tari[["tara", "comenzi", "pondere_pct"]], hide_index=True, height=430, column_config={
            "tara": "Țara", "comenzi": "Comenzi",
            "pondere_pct": st.column_config.ProgressColumn("Pondere", format="%.1f%%", min_value=0,
                                                           max_value=float(tari["pondere_pct"].max()))})
