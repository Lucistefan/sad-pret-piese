import streamlit as st

from core.state import get_con

st.title("🔧 SAD – stabilirea prețului de vânzare pentru piese auto")
st.markdown(
    """
Prototip de **sistem de asistare a deciziilor** pentru un magazin online de piese auto: **ce preț pun pe o piesă**,
pornind de la costul de la furnizor, prețurile concurenței și istoricul vânzărilor.

**Surse de date** (aceleași foi Google Sheets ca în varianta din Sheets, încărcate într-o bază **SQLite**):
1. **Furnizor**: cod, denumire, categorie, marcă, preț de achiziție, transport
2. **Prețuri concurență**: prețul fiecărei piese la Magazin A, B, C
3. **Vânzări**: vânzări lunare pe categorii, comenzi pe țări, tipuri de clienți

**Modele decizionale**
| # | Model | Întrebarea la care răspunde |
|---|---|---|
| 1 | Cost + marjă vs. piață | Prețul meu e competitiv? Ce preț recomand? Câtă marjă îmi permit? |
| 2 | Prognoză (trend liniar) | Câte piese voi vinde luna viitoare pe fiecare categorie? |
| 3 | Simulare cu elasticitate | Merită o reducere / o creștere de preț? Care e modificarea optimă? |

**Rapoarte (Tema 2):** export **Excel** formatat, cu grafice; raport **PDF**; **cartodiagramă** cu comenzile pe țări.

👈 Parametrii globali (sursa datelor, marja, magazinele concurente) sunt în bara din stânga și se aplică în toate paginile.
"""
)
con, tables, log = get_con()
c = st.columns(5)
c[0].metric("Piese (furnizor)", len(tables["piese"]))
c[1].metric("Prețuri concurență", len(tables["preturi_concurenta"]))
c[2].metric("Luni de vânzări", tables["vanzari_lunare"]["nr"].nunique())
c[3].metric("Țări cu comenzi", len(tables["comenzi_tari"]))
c[4].metric("Tipuri de clienți", len(tables["clienti"]))
for key, src, status in log:
    if status != "ok":
        st.warning(f"{key}: {status}. Folosesc {src}.")
