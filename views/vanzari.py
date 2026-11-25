import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from core.db import q
from core.models import prognoza
from core.state import get_con, sql_box
from core.ui import PAL, card, header, style_fig, xlsx_bytes

header("📈", "Vânzări și prognoză", "Istoricul pe 12 luni și estimarea pentru lunile următoare")

con, tables, log = get_con()
with card():
    c1, c2 = st.columns(2)
    metoda = c1.segmented_control("Metodă de prognoză", ["Trend liniar (FORECAST)", "Medie mobilă 3 luni"],
                                  default=st.session_state.get("metoda", "Trend liniar (FORECAST)"))
    metoda = metoda or "Trend liniar (FORECAST)"
    orizont = c2.slider("Orizont (luni)", 1, 6, st.session_state.get("orizont", 1))
    st.session_state["metoda"], st.session_state["orizont"] = metoda, orizont

lun, fc, det, sql = prognoza(con, orizont, metoda)
cats = list(PAL)
dd = det.set_index("categorie")

k = st.columns(5)
for col, cat in zip(k, ["Total", *cats]):
    col.metric(f"{cat} – luna viitoare", f"{int(dd.loc[cat, 'prognoza_luna_urm'])} buc",
               f"{dd.loc[cat, 'panta_lunara']:+.1f} buc/lună")

with card("Vânzări lunare și prognoză"):
    luni = lun.drop_duplicates("nr").sort_values("nr")
    fig = go.Figure()
    for cat in cats:
        g = lun[lun["categorie"] == cat]
        f = fc[fc["categorie"] == cat]
        fig.add_scatter(x=g["nr"], y=g["bucati"], mode="lines+markers", name=cat, line=dict(color=PAL[cat], width=2.5))
        fig.add_scatter(x=[g["nr"].iloc[-1], *f["nr"]], y=[g["bucati"].iloc[-1], *f["prognoza"]],
                        mode="lines+markers", line=dict(color=PAL[cat], dash="dash"), showlegend=False,
                        marker=dict(symbol="circle-open", size=9))
    ticks = list(luni["nr"]) + sorted(fc["nr"].unique())
    labels = [x[:3] for x in luni["luna"]] + [f"P{i}" for i in range(1, orizont + 1)]
    fig.update_xaxes(tickvals=ticks, ticktext=labels)
    fig.add_vrect(x0=12.5, x1=12.5 + orizont, fillcolor="#eff6ff", line_width=0, layer="below",
                  annotation_text="prognoză", annotation_position="top left")
    fig.update_yaxes(title="bucăți")
    st.plotly_chart(style_fig(fig, 420, legend_bottom=True))
    sql_box(sql)

with card("Indicatori pe categorie"):
    st.dataframe(det, hide_index=True, column_config={
        "categorie": "Categorie", "panta_lunara": st.column_config.NumberColumn("Trend", format="%+.2f buc/lună"),
        "R2": st.column_config.ProgressColumn("Siguranța trendului (R²)", format="%.2f", min_value=0, max_value=1),
        "luna_max": "Luna maximă", "luna_min": "Luna minimă",
        "total_12_luni": "Total 12 luni", "prognoza_luna_urm": "Prognoză"})
    st.download_button("⬇️ Exportă prognoza (Excel)", xlsx_bytes(det, "Prognoza"), "prognoza.xlsx")

a, b = st.columns(2)
with a:
    with card("Structura vânzărilor pe luni"):
        figm = px.bar(lun, x="luna", y="bucati", color="categorie", color_discrete_map=PAL,
                      labels={"luna": "", "bucati": "bucăți", "categorie": ""})
        figm.update_xaxes(categoryorder="array", categoryarray=list(luni["luna"]))
        st.plotly_chart(style_fig(figm, 340, legend_bottom=True))
with b:
    sqlc = """SELECT tip_client, comenzi, valoare,
       ROUND(valoare * 1.0 / comenzi, 1) AS valoare_medie_comanda,
       ROUND(100.0 * valoare / (SELECT SUM(valoare) FROM clienti), 1) AS pondere_valoare
FROM clienti ORDER BY valoare DESC"""
    cl = q(con, sqlc)
    with card("Clienți"):
        figc = px.pie(cl, names="tip_client", values="valoare", hole=0.6)
        st.plotly_chart(style_fig(figc, 220, legend_bottom=True))
        st.dataframe(cl, hide_index=True, column_config={
            "tip_client": "Tip client", "comenzi": "Comenzi",
            "valoare": st.column_config.NumberColumn("Valoare", format="%d lei"),
            "valoare_medie_comanda": st.column_config.NumberColumn("Medie / comandă", format="%d lei"),
            "pondere_valoare": st.column_config.NumberColumn("Pondere", format="%.1f%%")})
        sql_box(sqlc)
