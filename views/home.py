import plotly.express as px
import streamlit as st

from core.db import CATEGORII
from core.state import build_context, get_con, params

st.title("🔧 Prețuri piese auto")

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

k = st.columns(4)
k[0].metric(f"Piese competitive (marjă {p['marja']}%)", f"{len(dec) - len(scumpe)} / {len(dec)}")
k[1].metric("Prognoză luna următoare", f"{int(ctx['prognoza_total'])} buc")
k[2].metric(f"Cea mai mare piață: {tari.iloc[0]['tara']}", f"{int(tari.iloc[0]['comenzi'])} comenzi")
k[3].metric(f"Top clienți: {cl.iloc[0]['tip_client']}", f"{cl.iloc[0]['valoare']:,.0f} lei")

a, b = st.columns([3, 2])
with a:
    st.subheader("De revizuit: prețuri peste piață")
    if scumpe.empty:
        st.success("Toate piesele sunt competitive.")
    else:
        st.dataframe(scumpe[["cod", "denumire", "pret_propus", "media_concurenta", "pret_recomandat"]],
                     hide_index=True, column_config={"cod": "Cod", "denumire": "Denumire",
                                                     "pret_propus": "Preț propus", "media_concurenta": "Media pieței",
                                                     "pret_recomandat": "Preț recomandat"})
with b:
    st.subheader("Prognoză pe categorii")
    det = ctx["prognoza_det"]
    det = det[det["categorie"] != "Total"]
    st.plotly_chart(px.bar(det, x="categorie", y="prognoza_luna_urm", text="prognoza_luna_urm",
                           labels={"categorie": "", "prognoza_luna_urm": "bucăți"}, height=300))
