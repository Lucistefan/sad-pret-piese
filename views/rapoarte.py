from datetime import datetime

import streamlit as st

from core.db import CATEGORII
from core.reports import raport_excel, raport_pdf
from core.state import build_context, get_con, params

st.title("📄 Exporturi și rapoarte")
st.caption("Tema 2: generarea de rapoarte din prototipul SAD (.xlsx, .pdf și cartodiagramă).")

con, tables, log = get_con()
p = params()

st.markdown("**Conținutul raportului** (parametrii vin din celelalte pagini și din bara laterală; îi poți ajusta aici)")
c1, c2, c3 = st.columns(3)
p["categorii"] = c1.multiselect("Categorii incluse", CATEGORII, default=CATEGORII)
p["marja"] = c2.number_input("Marja dorită (%)", 0, 300, int(p["marja"]))
p["modificare"] = c3.slider("Scenariul de simulare (%)", -50, 50, int(p["modificare"]))
if not p["categorii"]:
    st.stop()

ctx = build_context(con, tables, log, p)
with st.expander("Previzualizare date din raport", expanded=True):
    t1, t2, t3 = st.tabs(["Decizie preț", "Prognoză", "Simulare"])
    t1.dataframe(ctx["decizie"][["cod", "denumire", "cost_total", "pret_propus", "media_concurenta", "recomandare",
                                 "pret_recomandat"]], hide_index=True)
    t2.dataframe(ctx["prognoza_det"], hide_index=True)
    t3.dataframe(ctx["simulare"], hide_index=True)

stamp = datetime.now().strftime("%Y%m%d_%H%M")
st.subheader("Descarcă")
a, b, c = st.columns(3)
with a:
    st.markdown("**📊 Excel (.xlsx)**")
    st.caption("9 foi formatate: parametri, decizie (cu formatare condiționată), concurență, vânzări, prognoză, "
               "simulare (cu formule SUM), curbă, țări, clienți și 4 grafice Excel native.")
    with st.spinner("Generez Excel…"):
        xlsx = raport_excel(ctx)
    st.download_button("⬇️ Descarcă Excel", xlsx, f"raport_pret_piese_{stamp}.xlsx",
                       "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", type="primary")
with b:
    st.markdown("**📕 Raport PDF**")
    st.caption("4 pagini: indicatori, tabel de decizie, grafice, prognoză, clienți, simulare cu concluzie "
               "și cartodiagrama comenzilor pe țări.")
    with st.spinner("Generez PDF…"):
        pdf = raport_pdf(ctx)
    st.download_button("⬇️ Descarcă PDF", pdf, f"raport_pret_piese_{stamp}.pdf", "application/pdf", type="primary")
with c:
    st.markdown("**🧾 CSV (date brute)**")
    st.caption("Tabelul de decizie, pentru import în alt sistem (de ex. în magazinul online).")
    csv = ctx["decizie"].to_csv(index=False).encode("utf-8-sig")
    st.download_button("⬇️ Descarcă CSV", csv, f"decizie_pret_{stamp}.csv", "text/csv")

st.caption("Harta se exportă separat (PNG / HTML interactiv) din pagina «Hartă comenzi».")
