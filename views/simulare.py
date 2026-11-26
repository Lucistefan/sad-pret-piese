import pandas as pd
import plotly.express as px
import streamlit as st

from core.db import CATEGORII
from core.models import ELASTICITATE, REACTIE_IMPLICITA, curba_simulare, marja_pe_categorie, prognoza, simulare
from core.state import get_con, sql_box
from core.ui import PAL, card, filtre_active, filtru_multi, grafic, header, reset_filtre, style_fig, xlsx_export, coloreaza, semn_icon

EXPLICATIE = """
**Întrebarea:** dacă schimb prețul cu X%, câștig sau pierd bani?

1. **Vânzări estimate** = prognoza pe luna următoare (din pagina Vânzări).
2. **Elasticitatea** spune cât de tare reacționează clienții la preț:
   - *Mult* (−1,5): la 10% reducere vinzi cu 15% mai mult (ex. filtre, frâne: clienții compară prețurile);
   - *Mediu* (−1,0): la 10% reducere vinzi cu 10% mai mult;
   - *Puțin* (−0,5): la 10% reducere vinzi doar cu 5% mai mult (ex. ambreiaj: piesă urgentă, o cumperi oricum).
3. **Vânzări după** = vânzări estimate × (1 + coeficient × modificare%).
4. **Încasări** = bucăți × preț. **Profit** = bucăți × (preț − cost).

**Verdictul se dă după profit:** o reducere poate aduce mai mulți bani încasați, dar mai puțin profit,
pentru că pe fiecare piesă câștigi mai puțin.

Coeficienții sunt estimări pe tipul de piesă și se pot modifica mai jos.
"""


def lei(x):
    return f"{x:,.0f} lei".replace(",", ".")


header("🎚️", "Simulare preț", "Merită o reducere sau o creștere de preț?", EXPLICATIE)

con, tables, log = get_con()
marja = st.session_state.get("marja", 30)

with card():
    c1, c2 = st.columns([3, 1], vertical_alignment="bottom")
    mod = c1.slider("Modificare preț (%)", -50, 50, int(st.session_state.get("modificare", -10)), 1, format="%+d%%")
    st.session_state["modificare"] = mod
    with c2.popover("Filtre", icon=":material/filter_list:", width="stretch"):
        f_cat = filtru_multi(st, "Categorie", CATEGORII, "fs_cat")
        st.button("Resetează filtrele", on_click=reset_filtre, args=("fs_",), icon=":material/restart_alt:")
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
filtre_active({"Categorie": f_cat})
cats = f_cat or CATEGORII

_, _, det, _ = prognoza(con, 1)
pc, sqlp = marja_pe_categorie(con, marja)
dd = det.set_index("categorie")
prog = {c: int(dd.loc[c, "prognoza_luna_urm"]) for c in cats}
preturi = {c: float(pc.loc[c, "pret_actual"]) for c in cats}
costuri = {c: float(pc.loc[c, "cost_mediu"]) for c in cats}

sim = simulare(prog, preturi, costuri, reactii, mod, elast)
tot_inc = float(sim["castig_pierdere"].sum())
tot_prof = float(sim["dif_profit"].sum())
buc_acum, buc_dupa = int(sim["vanzari_estimate"].sum()), int(sim["vanzari_dupa"].sum())

if mod == 0:
    st.info("Alege o modificare de preț.")
elif tot_prof > 0:
    st.success(icon="✅", body=f"**Merită.** Profitul crește cu {lei(tot_prof)} (încasările se modifică cu {tot_inc:+,.0f} lei)."
               .replace(",", "."))
else:
    st.error(icon="❌", body=f"**Nu merită.** Profitul scade cu {lei(-tot_prof)}"
             + (f", chiar dacă încasările cresc cu {lei(tot_inc)}." if tot_inc > 0 else f", iar încasările scad cu {lei(-tot_inc)}."))

k = st.columns(4)
k[0].metric("Piese vândute", f"{buc_dupa} buc", f"{buc_dupa - buc_acum:+d} buc", help="Estimare după modificarea prețului")
k[1].metric("Încasări", lei(sim["incasari_dupa"].sum()), f"{tot_inc:+,.0f} lei".replace(",", "."),
            help="Bucăți × preț")
k[2].metric("Profit", lei(sim["profit_dupa"].sum()), f"{tot_prof:+,.0f} lei".replace(",", "."),
            help="Bucăți × (preț − cost)")
k[3].metric("Profit înainte", lei(sim["profit_acum"].sum()))

with card("Pe categorii"):
    tip = st.segmented_control("Tip grafic", ["Coloane", "Bare orizontale"], default="Coloane",
                               key="g_sim", label_visibility="collapsed") or "Coloane"
    long = sim.melt(id_vars="categorie", value_vars=["castig_pierdere", "dif_profit"], var_name="indicator",
                    value_name="lei")
    long["indicator"] = long["indicator"].map({"castig_pierdere": "Δ încasări", "dif_profit": "Δ profit"})
    st.plotly_chart(grafic(long, "categorie", "lei", tip, color="indicator", height=320,
                           color_map={"Δ încasări": "#94a3b8", "Δ profit": "#2563eb"}, labels={"categorie": ""}))
    t = sim[["categorie", "reactie_clienti", "pret_actual", "vanzari_estimate", "vanzari_dupa", "castig_pierdere",
             "dif_profit"]].copy()
    t.insert(0, "ok", t["dif_profit"].map(lambda v: semn_icon(v)))
    t["verdict"] = t["dif_profit"].map(lambda v: "merită" if v > 0 else ("fără efect" if v == 0 else "nu merită"))
    t["reactie_clienti"] = t["reactie_clienti"].map({"Mult": "🔥 Mult", "Mediu": "🌤️ Mediu", "Puțin": "🧊 Puțin"})
    st.caption("✅ merită (profitul crește) · ❌ nu merită (profitul scade) · culoarea e mai intensă cu cât efectul e mai mare")
    st.dataframe(coloreaza(t, bun_mare=["castig_pierdere", "dif_profit"],
                           fmt={"pret_actual": "{:,.0f} lei", "vanzari_dupa": "{:.0f}", "vanzari_estimate": "{:.0f}", "castig_pierdere": "{:+,.0f} lei",
                                "dif_profit": "{:+,.0f} lei"}),
                 hide_index=True, column_config={
        "ok": st.column_config.Column("", width=40), "categorie": "Categorie", "reactie_clienti": "Sensibilitate",
        "pret_actual": "Preț actual", "vanzari_estimate": "Buc. acum", "vanzari_dupa": "Buc. după",
        "castig_pierdere": "Δ încasări", "dif_profit": "Δ profit", "verdict": "Verdict"})
    sql_box(sqlp, {"marja": marja})

curba = curba_simulare(prog, preturi, costuri, reactii, elasticitate=elast)
tot = curba.groupby("modificare_%", as_index=False)[["dif_incasari", "dif_profit"]].sum()
best_p = tot.loc[tot["dif_profit"].idxmax()]
best_i = tot.loc[tot["dif_incasari"].idxmax()]

with card("Modificarea optimă"):
    c = st.columns([1, 1, 2])
    c[0].metric("Cel mai mare profit", f"{int(best_p['modificare_%']):+d}%",
                f"{best_p['dif_profit']:+,.0f} lei".replace(",", "."))
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
                        for cat in cats])
    directie = lambda v: f"⬇️ {v:+d}% (reducere)" if v < 0 else (f"⬆️ {v:+d}% (creștere)" if v > 0 else "➡️ 0%")  # noqa: E731
    opt_v = opt.copy()
    opt_v["Optim profit"] = opt_v["Optim profit"].map(directie)
    opt_v["Optim încasări"] = opt_v["Optim încasări"].map(directie)
    opt_v["Sensibilitate"] = opt_v["Sensibilitate"].map({"Mult": "🔥 Mult", "Mediu": "🌤️ Mediu", "Puțin": "🧊 Puțin"})
    st.dataframe(opt_v, hide_index=True)
    curba_w = curba.pivot_table(index="modificare_%", columns="categorie", values=col).reset_index()
    curba_w["Total"] = curba_w[cats].sum(axis=1)
    curba_w.columns.name = None
    st.download_button("⬇️ Exportă simularea și graficele (Excel)", xlsx_export([
        ("Simulare", sim, {"tip": tip, "x": "categorie",
                           "y": ["castig_pierdere", "dif_profit"], "titlu": f"Efectul modificării de {mod:+d}%",
                           "axa": "lei"}, None, {"castig_pierdere": "bun_mare", "dif_profit": "bun_mare"}),
        ("Curba", curba_w, {"tip": "Linii", "x": "modificare_%", "y": [*cats, "Total"],
                            "titlu": f"Diferență {ind.lower()} după modificarea prețului", "axa": "lei"}, None,
         {c: "bun_mare" for c in [*cats, "Total"]}),
        ("Optim", opt, None, None)]), "simulare.xlsx")
