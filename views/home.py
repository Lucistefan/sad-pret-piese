import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from core.db import CATEGORII
from core.state import build_context, get_con, params
from core.ui import PAL, card, header, style_fig

header("📊", "Panou general", "Situația prețurilor, vânzărilor și piețelor dintr-o privire")

con, tables, log = get_con()
for key, src, status in log:
    if status != "ok":
        st.warning(f"{key}: {status}. Folosesc {src}.")

p = params()
p["categorii"] = CATEGORII
ctx = build_context(con, tables, log, p)
dec = ctx["decizie"]
scumpe = dec[dec["recomandare"] == "Prea scump"]
cl = ctx["clienti"].sort_values("valoare", ascending=False)
tari = ctx["tari"].sort_values("comenzi", ascending=False)
det = ctx["prognoza_det"].set_index("categorie")
lun = ctx["lunar"]
ult = lun[lun["nr"] == lun["nr"].max()]["bucati"].sum()

k = st.columns(4)
k[0].metric(f"Piese competitive la {p['marja']}%", f"{len(dec) - len(scumpe)} din {len(dec)}",
            f"{len(scumpe)} de revizuit", delta_color="red" if len(scumpe) else "off", delta_arrow="off")
k[1].metric("Prognoză luna următoare", f"{int(ctx['prognoza_total'])} buc",
            f"{int(ctx['prognoza_total'] - ult):+d} față de ultima lună")
k[2].metric("Cea mai mare piață", tari.iloc[0]["tara"], f"{int(tari.iloc[0]['comenzi'])} comenzi",
            delta_color="off", delta_arrow="off")
k[3].metric(f"Top clienți: {cl.iloc[0]['tip_client']}", f"{cl.iloc[0]['valoare']:,.0f} lei".replace(",", "."),
            f"{cl.iloc[0]['valoare'] / cl['valoare'].sum() * 100:.0f}% din vânzări", delta_color="off", delta_arrow="off")

a, b = st.columns([3, 2])
with a:
    with card("Prețuri de revizuit"):
        if scumpe.empty:
            st.success("Toate piesele sunt competitive la marja aleasă.")
        else:
            t = scumpe[["cod", "denumire", "pret_propus", "media_concurenta", "pret_recomandat"]].copy()
            st.dataframe(t, hide_index=True, height=260, column_config={
                "cod": "Cod", "denumire": "Denumire",
                "pret_propus": st.column_config.NumberColumn("Preț propus", format="%d lei"),
                "media_concurenta": st.column_config.NumberColumn("Media pieței", format="%d lei"),
                "pret_recomandat": st.column_config.NumberColumn("Preț recomandat", format="%d lei")})
        st.page_link("views/decizie.py", label="Deschide analiza de preț", icon=":material/arrow_forward:")
with b:
    with card("Prognoză luna următoare"):
        d = det.drop(index="Total").reset_index()
        fig = px.bar(d, x="categorie", y="prognoza_luna_urm", text="prognoza_luna_urm", color="categorie",
                     color_discrete_map=PAL, labels={"categorie": "", "prognoza_luna_urm": "bucăți"})
        fig.update_layout(showlegend=False)
        st.plotly_chart(style_fig(fig, 300))

c, d = st.columns([3, 2])
with c:
    with card("Vânzări lunare (toate categoriile)"):
        tot = lun.groupby(["nr", "luna"], as_index=False)["bucati"].sum().sort_values("nr")
        fig = go.Figure(go.Scatter(x=tot["luna"], y=tot["bucati"], mode="lines+markers", fill="tozeroy",
                                   line=dict(color="#2563eb", width=3), fillcolor="rgba(37,99,235,.08)"))
        st.plotly_chart(style_fig(fig, 260))
with d:
    with card("Valoare comenzi pe tip de client"):
        fig = px.pie(cl, names="tip_client", values="valoare", hole=0.6)
        fig.update_traces(textinfo="percent")
        st.plotly_chart(style_fig(fig, 260, legend_bottom=True))
