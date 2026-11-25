import plotly.express as px
import streamlit as st

from core.db import q
from core.reports import map_plotly, map_png
from core.state import get_con, sql_box

st.title("🗺️ Comenzi pe țări")

con, tables, log = get_con()
c1, c2 = st.columns([1, 2])
minim = c1.slider("Minim comenzi", 0, 100, 0)
tip = c2.radio("Afișare", ["Hartă colorată (choropleth)", "Cercuri proporționale", "Ambele"],
               horizontal=True, index=2)

sql = """SELECT cod_tara, tara, iso3, comenzi,
       ROUND(100.0 * comenzi / (SELECT SUM(comenzi) FROM comenzi_tari), 1) AS pondere_pct
FROM comenzi_tari
WHERE comenzi >= :minim
ORDER BY comenzi DESC"""
tari = q(con, sql, {"minim": minim})
sql_box(sql, {"minim": minim})

fig = map_plotly(tari, choropleth=tip != "Cercuri proporționale", bubbles=tip != "Hartă colorată (choropleth)")
st.plotly_chart(fig)

a, b = st.columns([3, 2])
with a:
    figb = px.bar(tari.sort_values("comenzi"), x="comenzi", y="tara", orientation="h", text="comenzi",
                  title="Clasament")
    st.plotly_chart(figb)
with b:
    st.dataframe(tari[["tara", "comenzi", "pondere_pct"]], hide_index=True, height=420,
                 column_config={"tara": "Țara", "comenzi": "Comenzi", "pondere_pct": "Pondere %"})

d1, d2, _ = st.columns([1, 1, 2])
d1.download_button("⬇️ Hartă PNG", map_png(tari), "harta_comenzi.png", "image/png")
d2.download_button("⬇️ Hartă HTML", fig.to_html(include_plotlyjs="cdn"), "harta_comenzi.html", "text/html")
