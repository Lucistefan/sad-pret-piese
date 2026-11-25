import re

import streamlit as st

from core.db import q, schema
from core.state import get_con
from core.ui import header

header("🧮", "Interogări SQL", "Interogări libere pe baza de date a aplicației")

con, tables, log = get_con()
st.dataframe(schema(con), hide_index=True)

EXEMPLE = {
    "Piese competitive la marja de 30%": """SELECT p.cod, p.denumire,
       p.pret_achizitie + p.transport AS cost,
       ROUND((p.pret_achizitie + p.transport) * 1.30) AS pret_propus,
       ROUND(AVG(c.pret)) AS media_conc
FROM piese p JOIN preturi_concurenta c ON c.cod = p.cod
GROUP BY p.cod
HAVING pret_propus <= media_conc
ORDER BY p.categorie;""",
    "Cel mai ieftin magazin pentru fiecare piesă": """SELECT c.cod, p.denumire, c.magazin, c.pret
FROM preturi_concurenta c JOIN piese p ON p.cod = c.cod
WHERE c.pret = (SELECT MIN(pret) FROM preturi_concurenta x WHERE x.cod = c.cod)
ORDER BY c.cod;""",
    "Marja maximă competitivă pe categorie": """SELECT p.categorie,
       ROUND(AVG((m.media / (p.pret_achizitie + p.transport) - 1) * 100), 1) AS marja_max_pct
FROM piese p
JOIN (SELECT cod, AVG(pret) AS media FROM preturi_concurenta GROUP BY cod) m ON m.cod = p.cod
GROUP BY p.categorie ORDER BY marja_max_pct DESC;""",
    "Vânzări totale pe categorie": """SELECT categorie, SUM(bucati) AS total, ROUND(AVG(bucati), 1) AS medie_lunara,
       MAX(bucati) AS maxim, MIN(bucati) AS minim
FROM vanzari_lunare GROUP BY categorie ORDER BY total DESC;""",
    "Ponderea țărilor în comenzi": """SELECT tara, comenzi,
       ROUND(100.0 * comenzi / SUM(comenzi) OVER (), 1) AS pondere_pct,
       SUM(comenzi) OVER (ORDER BY comenzi DESC) AS cumulat
FROM comenzi_tari ORDER BY comenzi DESC;""",
}
ex = st.selectbox("Exemplu", list(EXEMPLE))
sql = st.text_area("Interogare", EXEMPLE[ex], height=200)
if st.button("▶️ Rulează", type="primary"):
    if not re.match(r"^\s*(select|with)\b", sql, re.I) or re.search(r"\b(insert|update|delete|drop|alter|create|attach|pragma)\b", sql, re.I):
        st.error("Sunt permise doar interogări de citire (SELECT / WITH).")
    else:
        try:
            res = q(con, sql)
            st.success(f"{len(res)} rânduri")
            st.dataframe(res, hide_index=True)
            st.download_button("⬇️ Rezultat CSV", res.to_csv(index=False).encode("utf-8-sig"), "rezultat.csv", "text/csv")
        except Exception as e:  # noqa: BLE001
            st.error(f"Eroare SQL: {e}")
