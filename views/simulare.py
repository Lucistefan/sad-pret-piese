import pandas as pd
import plotly.express as px
import streamlit as st

from core.db import CATEGORII
from core.models import ELASTICITATE, REACTIE_IMPLICITA, curba_simulare, marja_pe_categorie, prognoza, simulare
from core.state import get_con, sql_box
from core.ui import PAL, card, header, style_fig, xlsx_bytes


def lei(x):
    return f"{x:,.0f} lei".replace(",", ".")


header("🎚️", "Simulare preț", "Merită o reducere sau o creștere de preț?")

con, tables, log = get_con()
marja = st.session_state.get("marja", 30)

with card():
    mod = st.slider("Modificare preț (%)", -50, 50, int(st.session_state.get("modificare", -10)), 1,
                    format="%+d%%")
    st.session_state["modificare"] = mod
    with st.expander("Sensibilitatea clienților la preț"):
        cols = st.columns(4)
        reactii = {}
        for col, cat in zip(cols, CATEGORII):
            reactii[cat] = col.selectbox(cat, list(ELASTICITATE), index=list(ELASTICITATE).index(
                st.session_state.get(f"reactie_{cat}", REACTIE_IMPLICITA[cat])))
            st.session_state[f"reactie_{cat}"] = reactii[cat]
        e_cols = st.columns(3)
        saved = st.session_state.get("elast", ELASTICITATE)
        elast = {k: e_cols[i].number_input(f"Coeficient «{k}»", -5.0, 0.0, float(saved[k]), 0.1)
                 for i, k in enumerate(ELASTICITATE)}
        st.session_state["elast"] = elast

_, _, det, _ = prognoza(con, 1)
pc, sqlp = marja_pe_categorie(con, marja)
dd = det.set_index("categorie")
prog = {c: int(dd.loc[c, "prognoza_luna_urm"]) for c in CATEGORII}
preturi = {c: float(pc.loc[c, "pret_actual"]) for c in CATEGORII}
costuri = {c: float(pc.loc[c, "cost_mediu"]) for c in CATEGORII}

sim = simulare(prog, preturi, costuri, reactii, mod, elast)
tot_inc = float(sim["castig_pierdere"].sum())
tot_prof = float(sim["dif_profit"].sum())
buc_acum, buc_dupa = int(sim["vanzari_estimate"].sum()), int(sim["vanzari_dupa"].sum())

# Verdict unic, după profit (ce rămâne după plata furnizorului)
if mod == 0:
    st.info("Alege o modificare de preț.")
elif tot_prof > 0:
    st.success(f"**Merită.** Profitul crește cu {lei(tot_prof)} (încasările se modifică cu {tot_inc:+,.0f} lei).".replace(",", "."))
else:
    st.error(f"**Nu merită.** Profitul scade cu {lei(-tot_prof)}"
             + (f", chiar dacă încasările cresc cu {lei(tot_inc)}." if tot_inc > 0 else f", iar încasările scad cu {lei(-tot_inc)}."))

k = st.columns(4)
k[0].metric("Piese vândute", f"{buc_dupa} buc", f"{buc_dupa - buc_acum:+d} buc")
k[1].metric("Încasări", lei(sim["incasari_dupa"].sum()), f"{tot_inc:+,.0f} lei".replace(",", "."))
k[2].metric("Profit", lei(sim["profit_dupa"].sum()), f"{tot_prof:+,.0f} lei".replace(",", "."))
k[3].metric("Profit înainte", lei(sim["profit_acum"].sum()))

with card("Pe categorii"):
    t = sim[["categorie", "reactie_clienti", "pret_actual", "vanzari_estimate", "vanzari_dupa", "castig_pierdere",
             "dif_profit"]].copy()
    t["verdict"] = t["dif_profit"].apply(lambda v: "🟢 merită" if v > 0 else "🔴 nu merită")
    leicol = lambda x: st.column_config.NumberColumn(x, format="%+d lei")  # noqa: E731
    st.dataframe(t, hide_index=True, column_config={
        "categorie": "Categorie", "reactie_clienti": "Sensibilitate",
        "pret_actual": st.column_config.NumberColumn("Preț actual", format="%d lei"),
        "vanzari_estimate": "Buc. acum", "vanzari_dupa": "Buc. după",
        "castig_pierdere": leicol("Δ încasări"), "dif_profit": leicol("Δ profit"), "verdict": "Verdict"})
    st.download_button("⬇️ Exportă simularea (Excel)", xlsx_bytes(sim, "Simulare"), "simulare.xlsx")
    sql_box(sqlp, {"marja": marja})

curba = curba_simulare(prog, preturi, costuri, reactii, elasticitate=elast)
tot = curba.groupby("modificare_%", as_index=False)[["dif_incasari", "dif_profit"]].sum()
best_p = tot.loc[tot["dif_profit"].idxmax()]
best_i = tot.loc[tot["dif_incasari"].idxmax()]

with card("Modificarea optimă"):
    c = st.columns([1, 1, 2])
    c[0].metric("Cel mai mare profit", f"{int(best_p['modificare_%']):+d}%", f"{best_p['dif_profit']:+,.0f} lei".replace(",", "."))
    c[1].metric("Cele mai mari încasări", f"{int(best_i['modificare_%']):+d}%",
                f"{best_i['dif_incasari']:+,.0f} lei".replace(",", "."))
    ind = c[2].segmented_control("Grafic", ["Profit", "Încasări"], default="Profit") or "Profit"
    col = "dif_profit" if ind == "Profit" else "dif_incasari"
    fig = px.line(curba, x="modificare_%", y=col, color="categorie", color_discrete_map=PAL,
                  labels={"modificare_%": "modificare preț (%)", col: f"diferență {ind.lower()} (lei)", "categorie": ""})
    fig.add_scatter(x=tot["modificare_%"], y=tot[col], name="Total", line=dict(color="#0f172a", width=4))
    fig.add_hline(0, line_color="#94a3b8")
    fig.add_vline(mod, line_dash="dot", line_color="#dc2626", annotation_text=f"{mod:+d}%")
    st.plotly_chart(style_fig(fig, 400, legend_bottom=True))
    opt = pd.DataFrame([{"Categorie": cat, "Sensibilitate": reactii[cat],
                         "Optim profit": int(curba[curba["categorie"] == cat].set_index("modificare_%")["dif_profit"].idxmax()),
                         "Optim încasări": int(curba[curba["categorie"] == cat].set_index("modificare_%")["dif_incasari"].idxmax())}
                        for cat in CATEGORII])
    st.dataframe(opt, hide_index=True, column_config={
        "Optim profit": st.column_config.NumberColumn(format="%+d%%"),
        "Optim încasări": st.column_config.NumberColumn(format="%+d%%")})
