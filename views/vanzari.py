import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from core.db import q
from core.models import prognoza
from core.state import get_con, sql_box

PAL = {"Frâne": "#2563eb", "Filtre": "#16a34a", "Suspensie": "#d97706", "Ambreiaj": "#dc2626"}

st.title("📈 Model 2 – vânzări și prognoză")
st.caption("Foaia «Vânzări»: prognoza pe luna următoare = FORECAST(13; vânzări; 1…12), adică un trend liniar.")

con, tables, log = get_con()
c1, c2 = st.columns(2)
metoda = c1.radio("Metoda de prognoză", ["Trend liniar (FORECAST)", "Medie mobilă 3 luni"], horizontal=True,
                  index=0 if st.session_state.get("metoda", "Trend").startswith("Trend") else 1)
orizont = c2.slider("Orizont de prognoză (luni)", 1, 6, st.session_state.get("orizont", 1))
st.session_state["metoda"], st.session_state["orizont"] = metoda, orizont

lun, fc, det, sql = prognoza(con, orizont, metoda)
cats = st.multiselect("Categorii afișate", list(PAL), default=list(PAL))

k = st.columns(5)
dd = det.set_index("categorie")
for col, cat in zip(k, ["Frâne", "Filtre", "Suspensie", "Ambreiaj", "Total"]):
    col.metric(f"{cat} – luna următoare", f"{int(dd.loc[cat, 'prognoza_luna_urm'])} buc",
               f"trend {dd.loc[cat, 'panta_lunara']:+.2f}/lună")

luni = lun.drop_duplicates("nr").sort_values("nr")
fig = go.Figure()
for cat in cats:
    g = lun[lun["categorie"] == cat]
    f = fc[fc["categorie"] == cat]
    fig.add_scatter(x=g["nr"], y=g["bucati"], mode="lines+markers", name=cat, line=dict(color=PAL[cat]))
    fig.add_scatter(x=[g["nr"].iloc[-1], *f["nr"]], y=[g["bucati"].iloc[-1], *f["prognoza"]], mode="lines+markers",
                    line=dict(color=PAL[cat], dash="dash"), name=f"{cat} – prognoză", showlegend=False)
ticks = list(luni["nr"]) + sorted(fc["nr"].unique())
labels = list(luni["luna"]) + [f"Prognoză {i}" for i in range(1, orizont + 1)]
fig.update_xaxes(tickvals=ticks, ticktext=labels)
fig.add_vrect(x0=12.5, x1=12.5 + orizont, fillcolor="#f1f5f9", line_width=0, annotation_text="prognoză")
fig.update_layout(title="Vânzări lunare pe categorii (bucăți)", height=440, legend=dict(orientation="h", y=-0.2))
st.plotly_chart(fig)
sql_box(sql)

st.subheader("Indicatori pe categorie")
st.dataframe(det, hide_index=True, column_config={
    "panta_lunara": "Trend (buc/lună)", "R2": st.column_config.NumberColumn("R²", help="cât de bine explică trendul datele"),
    "luna_max": "Luna cu vânzări maxime", "luna_min": "Luna cu vânzări minime",
    "total_12_luni": "Total 12 luni", "prognoza_luna_urm": "Prognoză luna următoare"})
st.caption("R² mic (ex. Suspensie) înseamnă că vânzările nu urmează un trend clar, deci prognoza e mai nesigură.")

a, b = st.columns(2)
with a:
    tot = lun.pivot_table(index=["nr", "luna"], columns="categorie", values="bucati").reset_index()
    figm = px.bar(lun[lun["categorie"].isin(cats)], x="luna", y="bucati", color="categorie",
                  color_discrete_map=PAL, title="Structura vânzărilor pe luni")
    figm.update_xaxes(categoryorder="array", categoryarray=list(luni["luna"]))
    st.plotly_chart(figm)
with b:
    sqlc = """SELECT tip_client, comenzi, valoare,
       ROUND(valoare * 1.0 / comenzi, 1) AS valoare_medie_comanda,
       ROUND(100.0 * valoare / (SELECT SUM(valoare) FROM clienti), 1) AS pondere_valoare
FROM clienti ORDER BY valoare DESC"""
    cl = q(con, sqlc)
    figc = px.pie(cl, names="tip_client", values="valoare", hole=0.45, title="Valoarea comenzilor pe tip de client")
    st.plotly_chart(figc)
st.success(f"Cel mai valoros tip de client: **{cl.iloc[0]['tip_client']}** "
           f"({cl.iloc[0]['valoare']:,.0f} lei, {cl.iloc[0]['valoare_medie_comanda']:,.0f} lei / comandă în medie).")
st.dataframe(cl, hide_index=True)
sql_box(sqlc)
