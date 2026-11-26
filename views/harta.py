import streamlit as st

from core.db import q
from core.reports import map_plotly, map_png
from core.state import get_con, sql_box
from core.ui import card, filtre_active, filtru_multi, grafic, header, reset_filtre, xlsx_export

EXPLICATIE = """
**Ce arată pagina:** în ce țări se vând piesele (numărul de comenzi pe țară, din sursa Vânzări).

- **Hartă colorată (cartogramă):** fiecare țară e colorată mai închis cu cât are mai multe comenzi.
- **Cercuri proporționale (cartodiagramă):** pe fiecare țară se desenează un cerc cu atât mai mare cu cât sunt mai multe comenzi.
- Contururile țărilor vin dintr-un fișier **GeoJSON**. Legătura dintre date și hartă se face prin codul țării
  (ex. FR → FRA, RO → ROU).

Harta se poate exporta ca **PNG** (pentru documente) sau **HTML** (interactivă) și apare și în raportul PDF.
"""

header("🌍", "Hartă comenzi", "Unde se vând piesele: comenzi pe țări", EXPLICATIE)

con, tables, log = get_con()
toate_tarile = q(con, "SELECT tara FROM comenzi_tari ORDER BY comenzi DESC")["tara"].tolist()
c1, c2 = st.columns([1, 2.2], vertical_alignment="bottom")
with c1.popover("Filtre", icon=":material/filter_list:", width="stretch"):
    f_tari = filtru_multi(st, "Țări", toate_tarile, "fh_tari")
    f_min = st.slider("Minim comenzi", 0, 100, 0, key="fh_min")
    st.button("Resetează filtrele", on_click=reset_filtre, args=("fh_",), icon=":material/restart_alt:")
tip = c2.segmented_control("Afișare", ["Hartă colorată", "Cercuri proporționale", "Ambele"], default="Ambele",
                           label_visibility="collapsed") or "Ambele"
filtre_active({"Țări": f_tari, "Minim comenzi": f_min or None})

where, params = ["comenzi >= :minim"], {"minim": f_min}
if f_tari:
    where.append("tara IN (" + ", ".join(f":t{i}" for i in range(len(f_tari))) + ")")
    params.update({f"t{i}": t for i, t in enumerate(f_tari)})
sql = f"""SELECT cod_tara, tara, iso3, comenzi,
       ROUND(100.0 * comenzi / (SELECT SUM(comenzi) FROM comenzi_tari), 1) AS pondere_pct
FROM comenzi_tari
WHERE {' AND '.join(where)}
ORDER BY comenzi DESC"""
tari = q(con, sql, params)
if tari.empty:
    st.info("Nicio țară nu corespunde filtrelor.")
    st.stop()

k = st.columns(4)
k[0].metric("Țări", len(tari))
k[1].metric("Comenzi", int(tari["comenzi"].sum()))
k[2].metric("Piața principală", tari.iloc[0]["tara"], f"{tari.iloc[0]['pondere_pct']:.0f}% din total",
            delta_color="off", delta_arrow="off")
k[3].metric("Pondere țări afișate", f"{tari['pondere_pct'].sum():.0f}%", "din toate comenzile",
            delta_color="off", delta_arrow="off")

with card():
    fig = map_plotly(tari, choropleth=tip != "Cercuri proporționale", bubbles=tip != "Hartă colorată")
    fig.update_layout(title=None, margin=dict(l=0, r=0, t=0, b=0), paper_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig)
    sql_box(sql, params)
    d1, d2, d3, _ = st.columns([1, 1, 1, 2])
    d1.download_button("⬇️ Hartă PNG", map_png(tari), "harta_comenzi.png", "image/png", width="stretch")
    d2.download_button("⬇️ Hartă HTML", fig.to_html(include_plotlyjs="cdn"), "harta_comenzi.html", "text/html",
                       width="stretch")
    d3.download_button("⬇️ Excel (date, grafic, hartă)", xlsx_export([("Comenzi pe tari", tari, {"tip": "Bare orizontale", "x": "tara", "y": ["comenzi"],
                                                             "titlu": "Comenzi pe țări", "axa": "comenzi",
                                                             "inaltime": 10, "latime": 14}, map_png(tari))]), "comenzi_tari.xlsx", width="stretch")

a, b = st.columns([3, 2])
with a:
    with card("Clasament"):
        t = st.segmented_control("Tip grafic", ["Bare orizontale", "Coloane", "Plăcintă"], default="Bare orizontale",
                                 key="g_h", label_visibility="collapsed") or "Bare orizontale"
        d = tari.sort_values("comenzi", ascending=(t == "Bare orizontale"))
        st.plotly_chart(grafic(d, "tara", "comenzi", t, color="tara" if t == "Plăcintă" else None, height=430,
                               labels={"tara": "", "comenzi": "comenzi"}, order=d["tara"].tolist()))
with b:
    with card("Detalii"):
        st.dataframe(tari[["tara", "comenzi", "pondere_pct"]], hide_index=True, height=470, column_config={
            "tara": "Țara", "comenzi": "Comenzi",
            "pondere_pct": st.column_config.ProgressColumn("Pondere", format="%.1f%%", min_value=0,
                                                           max_value=float(tari["pondere_pct"].max()))})
