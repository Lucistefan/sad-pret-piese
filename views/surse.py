import pandas as pd
import streamlit as st

from core.db import SHEETS, SOURCE_LABELS
from core.state import get_con
from core.ui import card, header

header("🗂️", "Surse de date", "Furnizor, concurență și vânzări, încărcate într-o bază SQLite")
con, tables, log = get_con()

k = st.columns(3)
for col, (key, src, stt) in zip(k, log):
    ok = stt == "ok"
    col.metric(SOURCE_LABELS[key].split(" – ")[1], src.split(" (")[0],
               "conectat" if ok else "copie locală (sursa live indisponibilă)", delta_color="normal" if ok else "inverse")

with card("Foile Google Sheets"):
    st.markdown(f"[Furnizor](https://docs.google.com/spreadsheets/d/{SHEETS['furnizor']}/edit) · "
                f"[Prețuri concurență](https://docs.google.com/spreadsheets/d/{SHEETS['concurenta']}/edit) · "
                f"[Vânzări](https://docs.google.com/spreadsheets/d/{SHEETS['vanzari']}/edit)")
    st.caption("Pentru citirea live, foile trebuie partajate «Anyone with the link – Viewer».")

with card("Tabelele din baza de date"):
    tabs = st.tabs([f"{n} ({len(df)})" for n, df in tables.items()])
    for t, df in zip(tabs, tables.values()):
        t.dataframe(df, hide_index=True)
