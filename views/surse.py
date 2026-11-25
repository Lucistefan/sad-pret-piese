import pandas as pd
import streamlit as st

from core.db import SHEETS, SOURCE_LABELS
from core.state import get_con

st.title("🗂️ Surse de date")
con, tables, log = get_con()

st.dataframe(pd.DataFrame([{"sursa": SOURCE_LABELS[k], "încărcată din": src, "stare": stt} for k, src, stt in log]),
             hide_index=True)

st.caption("Pentru «Google Sheets (live)», foile trebuie partajate «Anyone with the link – Viewer».")
st.markdown(f"[Furnizor](https://docs.google.com/spreadsheets/d/{SHEETS['furnizor']}/edit) · "
            f"[Prețuri concurență](https://docs.google.com/spreadsheets/d/{SHEETS['concurenta']}/edit) · "
            f"[Vânzări](https://docs.google.com/spreadsheets/d/{SHEETS['vanzari']}/edit)")
for name, df in tables.items():
    with st.expander(f"Tabelul `{name}` ({len(df)} rânduri)"):
        st.dataframe(df, hide_index=True)
