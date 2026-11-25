from datetime import datetime

import streamlit as st

from core.db import CATEGORII
from core.reports import raport_excel, raport_pdf
from core.state import build_context, get_con, params

st.title("📄 Export Excel / PDF")

con, tables, log = get_con()
p = params()

c1, c2, c3 = st.columns(3)
p["categorii"] = c1.multiselect("Categorii", CATEGORII, default=CATEGORII)
p["marja"] = c2.number_input("Marja dorită (%)", 0, 300, int(p["marja"]))
p["modificare"] = c3.slider("Simulare preț (%)", -50, 50, int(p["modificare"]))
if not p["categorii"]:
    st.stop()

ctx = build_context(con, tables, log, p)
with st.expander("Previzualizare", expanded=False):
    t1, t2, t3 = st.tabs(["Decizie preț", "Prognoză", "Simulare"])
    t1.dataframe(ctx["decizie"][["cod", "denumire", "cost_total", "pret_propus", "media_concurenta", "recomandare",
                                 "pret_recomandat"]], hide_index=True)
    t2.dataframe(ctx["prognoza_det"], hide_index=True)
    t3.dataframe(ctx["simulare"], hide_index=True)

stamp = datetime.now().strftime("%Y%m%d_%H%M")
with st.spinner("Generez rapoartele…"):
    xlsx = raport_excel(ctx)
    pdf = raport_pdf(ctx)
csv = ctx["decizie"].to_csv(index=False).encode("utf-8-sig")
a, b, c, _ = st.columns([1, 1, 1, 1])
a.download_button("📊 Excel", xlsx, f"raport_pret_piese_{stamp}.xlsx",
                  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", type="primary", width="stretch")
b.download_button("📕 PDF", pdf, f"raport_pret_piese_{stamp}.pdf", "application/pdf", type="primary", width="stretch")
c.download_button("🧾 CSV", csv, f"decizie_pret_{stamp}.csv", "text/csv", width="stretch")
