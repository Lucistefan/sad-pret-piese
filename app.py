"""PrețPiese – sistem de asistare a deciziilor pentru prețul pieselor auto."""
import streamlit as st

from core.db import SOURCE_LABELS
from core.state import MODES, reload_data
from core.ui import setup

st.set_page_config(page_title="PrețPiese – SAD", page_icon="assets/icon.svg", layout="wide")
st.logo("assets/logo.svg", size="large", icon_image="assets/icon.svg")
setup()

pages = {
    "": [st.Page("views/home.py", title="Panou general", icon=":material/dashboard:", default=True)],
    "Decizii": [
        st.Page("views/decizie.py", title="Preț de vânzare", icon=":material/sell:"),
        st.Page("views/vanzari.py", title="Vânzări și prognoză", icon=":material/trending_up:"),
        st.Page("views/simulare.py", title="Simulare preț", icon=":material/tune:"),
    ],
    "Rapoarte": [
        st.Page("views/harta.py", title="Hartă comenzi", icon=":material/public:"),
        st.Page("views/rapoarte.py", title="Export Excel / PDF", icon=":material/download:"),
    ],
    "Date": [
        st.Page("views/surse.py", title="Surse de date", icon=":material/database:"),
        st.Page("views/sql.py", title="Baza de date & SQL", icon=":material/terminal:"),
    ],
}
nav = st.navigation(pages)

with st.sidebar:
    st.markdown("**SETĂRI**")
    st.selectbox("Sursa datelor", list(MODES), key="sursa")
    if MODES[st.session_state["sursa"]] == "google":
        st.button("Reîncarcă datele", icon=":material/refresh:", on_click=reload_data, width="stretch")
    if MODES[st.session_state["sursa"]] == "upload":
        st.session_state["uploads"] = {key: st.file_uploader(label, type=["csv", "xlsx"], key=f"up_{key}")
                                       for key, label in SOURCE_LABELS.items()}
    else:
        st.session_state["uploads"] = {}
    st.number_input("Marja dorită (%)", 0, 300, 30, 1, key="marja")
    st.multiselect("Magazine concurente", ["Magazin A", "Magazin B", "Magazin C"], default=[],
                   key="magazine", placeholder="Toate magazinele")
    st.toggle("Explicații", value=True, key="explicatii", help="Arată butonul «Cum funcționează?» pe fiecare pagină")
    st.toggle("Arată interogările SQL", value=False, key="arata_sql")

nav.run()
