import plotly.express as px
import streamlit as st

from core.db import q
from core.reports import map_plotly, map_png
from core.state import get_con, sql_box

st.title("🗺️ Cartodiagramă – comenzi pe țări")
st.caption("Sursa 3 (Vânzări), tabelul de comenzi pe țări. Harta e desenată din contururile țărilor (GeoJSON), fără serviciu extern de hărți.")

con, tables, log = get_con()
c1, c2 = st.columns([1, 2])
minim = c1.slider("Afișează țările cu minim … comenzi", 0, 100, 0)
tip = c2.radio("Tip de reprezentare", ["Hartă colorată (choropleth)", "Cercuri proporționale", "Ambele"],
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
                  title="Clasament țări")
    st.plotly_chart(figb)
with b:
    st.dataframe(tari, hide_index=True, height=420)
    top = tari.head(2)
    st.info(f"Primele 2 piețe ({' și '.join(top['tara'])}) aduc {top['pondere_pct'].sum():.0f}% din comenzi.")

st.subheader("Export hartă")
d1, d2 = st.columns(2)
d1.download_button("⬇️ Hartă PNG (pentru PDF / prezentare)", map_png(tari), "harta_comenzi.png", "image/png")
d2.download_button("⬇️ Hartă interactivă HTML", fig.to_html(include_plotlyjs="cdn"), "harta_comenzi.html", "text/html")
