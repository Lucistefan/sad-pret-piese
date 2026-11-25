import pandas as pd
import streamlit as st

from core.db import SHEETS, SOURCE_LABELS
from core.state import get_con

st.title("🗂️ Surse de date")
con, tables, log = get_con()

st.dataframe(pd.DataFrame([{"sursa": SOURCE_LABELS[k], "încărcată din": src, "stare": stt} for k, src, stt in log]),
             hide_index=True)

st.markdown(
    f"""
**Cum funcționează:** fiecare sursă e citită (din Google Sheets, din copia locală sau dintr-un fișier încărcat),
curățată cu pandas și scrisă într-o bază **SQLite** în memorie. Toate calculele din aplicație se fac apoi prin
interogări SQL, ca `QUERY(IMPORTRANGE(...))` din Google Sheets.

**Google Sheets live:** în bara laterală alegi «Google Sheets (live)». Pentru asta, fiecare foaie trebuie partajată
*Anyone with the link → Viewer*. Dacă nu e partajată, aplicația revine automat la copia locală și te anunță.
- Furnizor: [deschide](https://docs.google.com/spreadsheets/d/{SHEETS['furnizor']}/edit)
- Prețuri concurență: [deschide](https://docs.google.com/spreadsheets/d/{SHEETS['concurenta']}/edit)
- Vânzări: [deschide](https://docs.google.com/spreadsheets/d/{SHEETS['vanzari']}/edit)

**Fișierele tale:** alege «Încarc fișierele mele» și pune CSV-uri sau Excel-uri cu aceeași structură de coloane.
"""
)
for name, df in tables.items():
    with st.expander(f"Tabelul `{name}` ({len(df)} rânduri)"):
        st.dataframe(df, hide_index=True)
