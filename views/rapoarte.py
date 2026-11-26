from datetime import datetime

import streamlit as st

from core.db import CATEGORII
from core.reports import raport_excel, raport_pdf
from core.state import build_context, get_con, params
from core.ui import card, filtre_active, filtru_multi, header

EXPLICATIE = """
**Ce conține raportul:** aceleași calcule ca în aplicație, pentru categoriile și parametrii aleși aici.

- **Excel (.xlsx):** 9 foi: prețuri, piață, prognoză, simulare, comenzi pe țări, clienți etc.
  Are formatare condiționată (roșu/verde), formule `SUM`, grafice native Excel pe fiecare foaie și harta comenzilor ca imagine.
- **PDF:** raport de 4 pagini cu tabele, grafice, harta comenzilor și concluzia.
- **CSV:** lista de prețuri recomandate, ca să poată fi importată în magazinul online.

Rapoartele se generează în Python (openpyxl pentru Excel, fpdf2 + matplotlib pentru PDF).
"""

header("📄", "Export Excel / PDF", "Raportul complet de decizie, gata de descărcat", EXPLICATIE)

con, tables, log = get_con()
p = params()

with card("Conținutul raportului"):
    c1, c2, c3 = st.columns([2, 1, 1])
    f_cat = filtru_multi(c1, "Categorii", CATEGORII, "fr_cat")
    p["categorii"] = f_cat or CATEGORII
    p["marja"] = c2.number_input("Marja dorită (%)", 0, 300, int(p["marja"]))
    p["modificare"] = c3.number_input("Simulare preț (%)", -50, 50, int(p["modificare"]))
filtre_active({"Categorii": f_cat})

ctx = build_context(con, tables, log, p)
stamp = datetime.now().strftime("%Y%m%d_%H%M")
with st.spinner("Generez rapoartele…"):
    xlsx = raport_excel(ctx)
    pdf = raport_pdf(ctx)
csv = ctx["decizie"].to_csv(index=False).encode("utf-8-sig")

a, b, c = st.columns(3)
with a:
    with card():
        st.markdown("#### 📊 Excel")
        st.caption("9 foi, cu grafice native și hartă")
        st.download_button("Descarcă .xlsx", xlsx, f"raport_pret_piese_{stamp}.xlsx",
                           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", type="primary",
                           width="stretch")
with b:
    with card():
        st.markdown("#### 📕 PDF")
        st.caption("Raport de 4 pagini, cu grafice și hartă")
        st.download_button("Descarcă .pdf", pdf, f"raport_pret_piese_{stamp}.pdf", "application/pdf", type="primary",
                           width="stretch")
with c:
    with card():
        st.markdown("#### 🧾 CSV")
        st.caption("Lista de prețuri, pentru import în magazin")
        st.download_button("Descarcă .csv", csv, f"preturi_{stamp}.csv", "text/csv", width="stretch")

with card("Previzualizare"):
    t1, t2, t3 = st.tabs(["Prețuri", "Prognoză", "Simulare"])
    t1.dataframe(ctx["decizie"][["cod", "denumire", "cost_total", "pret_propus", "media_concurenta", "recomandare",
                                 "pret_recomandat"]], hide_index=True)
    t2.dataframe(ctx["prognoza_det"], hide_index=True)
    t3.dataframe(ctx["simulare"], hide_index=True)
