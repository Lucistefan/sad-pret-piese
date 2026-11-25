import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from core.db import CATEGORII
from core.models import ELASTICITATE, REACTIE_IMPLICITA, curba_simulare, marja_pe_categorie, prognoza, simulare
from core.state import get_con, sql_box

st.title("🎚️ Model 3 – merită o reducere (sau o creștere) de preț?")
st.caption("Foaia «Simulare»: estimez câte piese vând după modificarea prețului (elasticitate) și compar banii încasați "
           "înainte și după. În plus, aici calculez și **profitul**, care ține cont de cost.")

con, tables, log = get_con()
marja = st.session_state.get("marja", 30)

mod = st.slider("Cu cât modific prețul (%)", -50, 50, int(st.session_state.get("modificare", -10)), 1,
                help="Negativ = reducere, pozitiv = creștere (celula B2)")
st.session_state["modificare"] = mod

with st.expander("Cât reacționează clienții la preț? (coloana H)", expanded=False):
    cols = st.columns(4)
    reactii = {}
    for col, cat in zip(cols, CATEGORII):
        reactii[cat] = col.selectbox(cat, list(ELASTICITATE),
                                     index=list(ELASTICITATE).index(st.session_state.get(f"reactie_{cat}",
                                                                                         REACTIE_IMPLICITA[cat])))
        st.session_state[f"reactie_{cat}"] = reactii[cat]
    st.markdown("**Coeficienți de elasticitate** (cât se schimbă cantitatea la 1% schimbare de preț)")
    e_cols = st.columns(3)
    saved = st.session_state.get("elast", ELASTICITATE)
    elast = {k: e_cols[i].number_input(k, -5.0, 0.0, float(saved[k]), 0.1) for i, k in enumerate(ELASTICITATE)}
    st.session_state["elast"] = elast
    st.caption("Mult = clienții compară prețurile (ex. filtre) · Mediu = efect moderat · "
               "Puțin = clienții cumpără oricum (ex. piesă urgentă)")

_, _, det, _ = prognoza(con, 1)
pc, sqlp = marja_pe_categorie(con, marja)
dd = det.set_index("categorie")
prog = {c: int(dd.loc[c, "prognoza_luna_urm"]) for c in CATEGORII}
preturi = {c: float(pc.loc[c, "pret_actual"]) for c in CATEGORII}
costuri = {c: float(pc.loc[c, "cost_mediu"]) for c in CATEGORII}

sim = simulare(prog, preturi, costuri, reactii, mod, elast)
tot_inc = sim["castig_pierdere"].sum()
tot_prof = sim["dif_profit"].sum()

k = st.columns(3)
k[0].metric("Încasări acum", f"{sim['incasari_acum'].sum():,.0f} lei")
k[1].metric("Încasări după", f"{sim['incasari_dupa'].sum():,.0f} lei", f"{tot_inc:+,.0f} lei")
k[2].metric("Efect asupra profitului", f"{tot_prof:+,.0f} lei", delta_color="off")
if tot_inc > 0:
    st.success(f"Pe total câștigi {tot_inc:,.0f} lei în plus: modificarea e recomandată (după încasări).")
else:
    st.error(f"Pe total pierzi {-tot_inc:,.0f} lei: modificarea NU e recomandată (după încasări).")
if (tot_inc > 0) != (tot_prof > 0):
    st.warning("Atenție: după **profit** concluzia e inversă față de încasări. O reducere poate aduce mai mulți bani "
               "încasați, dar marja pe fiecare piesă scade.")

st.dataframe(sim, hide_index=True, column_config={
    "vanzari_estimate": "Vânzări estimate (buc)", "pret_actual": "Preț actual", "vanzari_dupa": "Vânzări după (buc)",
    "incasari_acum": "Încasări acum", "incasari_dupa": "Încasări după", "castig_pierdere": "Câștig / pierdere",
    "reactie_clienti": "Reacție clienți", "merita": "Merită?", "profit_acum": "Profit acum",
    "profit_dupa": "Profit după", "dif_profit": "Δ profit"})
st.caption(f"Vânzările estimate vin din Modelul 2 (prognoza pe luna următoare). Prețul actual e costul mediu al "
           f"categoriei × (1 + {marja}%), ca în foaia originală.")
sql_box(sqlp, {"marja": marja}, "Interogarea SQL pentru prețul actual pe categorie")

st.subheader("Care e modificarea optimă?")
curba = curba_simulare(prog, preturi, costuri, reactii, elasticitate=elast)
tot = curba.groupby("modificare_%", as_index=False)[["dif_incasari", "dif_profit"]].sum()
best_i = tot.loc[tot["dif_incasari"].idxmax()]
best_p = tot.loc[tot["dif_profit"].idxmax()]
c = st.columns(2)
c[0].metric("Maximizează încasările", f"{int(best_i['modificare_%']):+d}%", f"{best_i['dif_incasari']:+,.0f} lei")
c[1].metric("Maximizează profitul", f"{int(best_p['modificare_%']):+d}%", f"{best_p['dif_profit']:+,.0f} lei")

ind = st.radio("Indicator", ["dif_incasari", "dif_profit"], horizontal=True,
               format_func={"dif_incasari": "Diferență încasări", "dif_profit": "Diferență profit"}.get)
fig = px.line(curba, x="modificare_%", y=ind, color="categorie",
              color_discrete_map={"Frâne": "#2563eb", "Filtre": "#16a34a", "Suspensie": "#d97706", "Ambreiaj": "#dc2626"})
fig.add_scatter(x=tot["modificare_%"], y=tot[ind], name="TOTAL", line=dict(color="black", width=4))
fig.add_hline(0, line_color="grey")
fig.add_vline(mod, line_dash="dot", line_color="#dc2626", annotation_text="scenariul ales")
fig.update_layout(height=430, xaxis_title="modificare preț (%)", yaxis_title="lei",
                  title="Efectul modificării de preț, de la −50% la +50%")
st.plotly_chart(fig)

opt = []
for cat in CATEGORII:
    g = curba[curba["categorie"] == cat]
    opt.append({"categorie": cat, "reactie": reactii[cat],
                "optim_incasari_%": int(g.loc[g["dif_incasari"].idxmax(), "modificare_%"]),
                "optim_profit_%": int(g.loc[g["dif_profit"].idxmax(), "modificare_%"])})
st.dataframe(pd.DataFrame(opt), hide_index=True)
st.caption("Modificarea optimă diferă pe categorie: unde clienții reacționează mult, o reducere poate aduce mai mult; "
           "unde reacționează puțin, o creștere de preț e mai profitabilă.")
