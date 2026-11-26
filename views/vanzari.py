import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from core.db import q
from core.models import prognoza
from core.state import get_con, sql_box
from core.ui import PAL, card, filtre_active, filtru_multi, grafic, header, reset_filtre, style_fig, xlsx_bytes

EXPLICATIE = """
**Ce face pagina:** estimează câte piese se vor vinde în lunile următoare, pe fiecare categorie.

- **Trend liniar (FORECAST):** trasează o dreaptă prin vânzările din ultimele 12 luni (regresie liniară) și o prelungește.
  Este aceeași metodă ca funcția FORECAST din Excel/Sheets.
- **Medie mobilă 3 luni:** prognoza = media ultimelor 3 luni. E mai simplă, dar nu prinde tendința.
- **Trend (buc/lună):** cu câte bucăți cresc (+) sau scad (−) vânzările în fiecare lună.
- **Siguranța trendului (R²):** între 0 și 1. Aproape de 1 = vânzările urmează clar un trend, deci prognoza e mai sigură.

Prognoza pe luna următoare este folosită apoi în pagina **Simulare preț**.
"""

header("📈", "Vânzări și prognoză", "Istoricul pe 12 luni și estimarea pentru lunile următoare", EXPLICATIE)

con, tables, log = get_con()
lun_all = q(con, "SELECT DISTINCT nr, luna FROM vanzari_lunare ORDER BY nr")
luni_ordine = lun_all["luna"].tolist()

c1, c2, c3 = st.columns([1, 1.4, 1.2], vertical_alignment="bottom")
with c1.popover("Filtre", icon=":material/filter_list:", width="stretch"):
    f_cat = filtru_multi(st, "Categorie", list(PAL), "fv_cat")
    f_luni = st.select_slider("Perioada", options=luni_ordine, value=(luni_ordine[0], luni_ordine[-1]), key="fv_luni")
    st.button("Resetează filtrele", on_click=reset_filtre, args=("fv_",), icon=":material/restart_alt:")
metoda = c2.segmented_control("Metodă de prognoză", ["Trend liniar (FORECAST)", "Medie mobilă 3 luni"],
                              default=st.session_state.get("metoda", "Trend liniar (FORECAST)")) \
    or "Trend liniar (FORECAST)"
orizont = c3.slider("Orizont (luni)", 1, 6, st.session_state.get("orizont", 1))
st.session_state["metoda"], st.session_state["orizont"] = metoda, orizont

perioada_filtrata = f_luni != (luni_ordine[0], luni_ordine[-1])
filtre_active({"Categorie": f_cat, "Perioada": f"{f_luni[0]} – {f_luni[1]}" if perioada_filtrata else None})

lun, fc, det, sql = prognoza(con, orizont, metoda)
cats = f_cat or list(PAL)
i0, i1 = luni_ordine.index(f_luni[0]) + 1, luni_ordine.index(f_luni[1]) + 1
lun_v = lun[lun["categorie"].isin(cats) & lun["nr"].between(i0, i1)]
dd = det.set_index("categorie")

k = st.columns(len(cats) + 1)
for col, cat in zip(k, ["Total", *cats]):
    col.metric(f"{cat} – luna viitoare", f"{int(dd.loc[cat, 'prognoza_luna_urm'])} buc",
               f"{dd.loc[cat, 'panta_lunara']:+.1f} buc/lună", help="Prognoza și trendul lunar")

with card("Vânzări lunare și prognoză"):
    tip = st.segmented_control("Tip grafic", ["Linii", "Coloane", "Coloane stivuite", "Arie"], default="Linii",
                               key="g_vz", label_visibility="collapsed") or "Linii"
    if tip == "Linii":
        fig = go.Figure()
        for cat in cats:
            g = lun_v[lun_v["categorie"] == cat]
            f = fc[fc["categorie"] == cat]
            fig.add_scatter(x=g["luna"], y=g["bucati"], mode="lines+markers", name=cat,
                            line=dict(color=PAL[cat], width=2.5))
            if i1 == 12:      # prognoza continuă doar dacă perioada se termină cu ultima lună
                fig.add_scatter(x=[g["luna"].iloc[-1], *[f"Prognoză {p}" for p in f["pas"]]],
                                y=[g["bucati"].iloc[-1], *f["prognoza"]], mode="lines+markers",
                                line=dict(color=PAL[cat], dash="dash"), showlegend=False,
                                marker=dict(symbol="circle-open", size=9))
        fig.update_yaxes(title="bucăți")
        st.plotly_chart(style_fig(fig, 420, legend_bottom=True))
    else:
        prog = fc[fc["categorie"].isin(cats)].assign(luna=lambda d: "Prognoză " + d["pas"].astype(str),
                                                     bucati=lambda d: d["prognoza"])
        data = pd.concat([lun_v[["luna", "categorie", "bucati"]], prog[["luna", "categorie", "bucati"]]])
        ordine = luni_ordine[i0 - 1:i1] + [f"Prognoză {p}" for p in range(1, orizont + 1)]
        st.plotly_chart(grafic(data, "luna", "bucati", tip, color="categorie", color_map=PAL, height=420,
                               labels={"luna": "", "bucati": "bucăți", "categorie": ""}, order=ordine))
    sql_box(sql)

with card("Indicatori pe categorie"):
    t = det[det["categorie"].isin(cats + ["Total"])]
    st.dataframe(t, hide_index=True, column_config={
        "categorie": "Categorie", "panta_lunara": st.column_config.NumberColumn("Trend", format="%+.2f buc/lună"),
        "R2": st.column_config.ProgressColumn("Siguranța trendului (R²)", format="%.2f", min_value=0, max_value=1),
        "luna_max": "Luna maximă", "luna_min": "Luna minimă",
        "total_12_luni": "Total 12 luni", "prognoza_luna_urm": "Prognoză"})
    st.download_button("⬇️ Exportă prognoza (Excel)", xlsx_bytes(t, "Prognoza"), "prognoza.xlsx")

sqlc = """SELECT tip_client, comenzi, valoare,
       ROUND(valoare * 1.0 / comenzi, 1) AS valoare_medie_comanda,
       ROUND(100.0 * valoare / (SELECT SUM(valoare) FROM clienti), 1) AS pondere_valoare
FROM clienti ORDER BY valoare DESC"""
cl = q(con, sqlc)
with card("Clienți"):
    a, b = st.columns([3, 2])
    with a:
        ind = st.segmented_control("Indicator", ["Valoare", "Comenzi", "Valoare medie / comandă"], default="Valoare",
                                   key="g_cl_ind", label_visibility="collapsed") or "Valoare"
        tip_c = st.segmented_control("Tip grafic", ["Plăcintă", "Coloane", "Bare orizontale"], default="Plăcintă",
                                     key="g_cl", label_visibility="collapsed") or "Plăcintă"
        col = {"Valoare": "valoare", "Comenzi": "comenzi", "Valoare medie / comandă": "valoare_medie_comanda"}[ind]
        st.plotly_chart(grafic(cl, "tip_client", col, tip_c, color="tip_client", height=300,
                               labels={"tip_client": "", col: ind}))
    with b:
        st.dataframe(cl, hide_index=True, column_config={
            "tip_client": "Tip client", "comenzi": "Comenzi",
            "valoare": st.column_config.NumberColumn("Valoare", format="%d lei"),
            "valoare_medie_comanda": st.column_config.NumberColumn("Medie / comandă", format="%d lei"),
            "pondere_valoare": st.column_config.NumberColumn("Pondere", format="%.1f%%")})
    sql_box(sqlc)
