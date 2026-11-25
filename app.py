"""SAD – stabilirea prețului de vânzare pentru piese auto (prototip Streamlit)."""
import streamlit as st

from core.db import SOURCE_LABELS
from core.state import MODES

st.set_page_config(page_title="SAD – Preț piese auto", page_icon="🔧", layout="wide")

pages = {
    "": [st.Page("views/home.py", title="Acasă", icon="🏠", default=True)],
    "Modele decizionale": [
        st.Page("views/decizie.py", title="1. Prețul de vânzare", icon="🏷️"),
        st.Page("views/vanzari.py", title="2. Vânzări și prognoză", icon="📈"),
        st.Page("views/simulare.py", title="3. Simulare reducere / creștere", icon="🎚️"),
    ],
    "Rapoarte (Tema 2)": [
        st.Page("views/harta.py", title="Hartă comenzi", icon="🗺️"),
        st.Page("views/rapoarte.py", title="Exporturi Excel / PDF", icon="📄"),
    ],
    "Date": [
        st.Page("views/surse.py", title="Surse de date", icon="🗂️"),
        st.Page("views/sql.py", title="Interogări SQL", icon="🧮"),
    ],
}
nav = st.navigation(pages)

with st.sidebar:
    st.markdown("### ⚙️ Parametri globali")
    st.radio("Sursa datelor", list(MODES), key="sursa")
    if MODES[st.session_state["sursa"]] == "upload":
        ups = {}
        for key, label in SOURCE_LABELS.items():
            ups[key] = st.file_uploader(label, type=["csv", "xlsx"], key=f"up_{key}")
        st.session_state["uploads"] = ups
    else:
        st.session_state["uploads"] = {}
    st.number_input("Marja dorită (%)", 0, 300, 30, 1, key="marja",
                    help="Ca celula B3 din foaia Decizie")
    st.multiselect("Magazine concurente luate în calcul", ["Magazin A", "Magazin B", "Magazin C"],
                   default=["Magazin A", "Magazin B", "Magazin C"], key="magazine")
    st.divider()
    st.caption("SAD · master SIA · FEAA UAIC")

nav.run()
