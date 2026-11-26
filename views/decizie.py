import plotly.graph_objects as go
import streamlit as st

from core.db import CATEGORII, q
from core.models import decizie
from core.state import get_con, sql_box
from core.ui import (card, filtre_active, filtru_multi, grafic, header, pozitie_badge, reset_filtre, sau_toate,
                     style_fig, verdict_badge, xlsx_export, coloreaza)

EXPLICATIE = """
**Ce decide pagina:** ce preț de vânzare pun pe fiecare piesă.

1. **Cost total** = preț de achiziție de la furnizor + transport.
2. **Preț propus** = cost total × (1 + marja dorită). Marja se alege din bara laterală.
3. **Media pieței** = media prețurilor la magazinele concurente selectate (toate, dacă nu e selectat niciunul).
4. **Verdict:** *Competitiv* dacă prețul propus ≤ media pieței, altfel *Prea scump*.
5. **Preț recomandat** = cea mai mare valoare dintre:
   - media pieței minus „sub piață %” (ca să fii puțin mai ieftin decât concurența);
   - cost × (1 + marja minimă), ca să nu vinzi în pierdere.

**Marja maximă competitivă** = cea mai mare marjă la care prețul încă nu depășește media pieței.

Datele vin din baza SQLite, printr-o **interogare SQL construită din filtrele alese** (vezi comutatorul „Arată interogările SQL”).
"""

header("🏷️", "Preț de vânzare", "Cost + marjă comparat cu prețurile concurenței", EXPLICATIE)

con, tables, log = get_con()
marja = st.session_state.get("marja", 30)
magazine = sau_toate(st.session_state.get("magazine"), ["Magazin A", "Magazin B", "Magazin C"])

# ---------------------------------------------------------------- filtre (pornesc goale = toate)
marci_all = q(con, "SELECT DISTINCT marca FROM piese ORDER BY marca")["marca"].tolist()
cmin, cmax = q(con, "SELECT MIN(pret_achizitie + transport) a, MAX(pret_achizitie + transport) b FROM piese").iloc[0]
c1, c2, c3 = st.columns([1.2, 1, 1], vertical_alignment="bottom")
with c1.popover("Filtre", icon=":material/filter_list:", width="stretch"):
    f_cat = filtru_multi(st, "Categorie", CATEGORII, "fd_cat")
    f_marca = filtru_multi(st, "Marcă", marci_all, "fd_marca")
    f_verdict = filtru_multi(st, "Verdict", ["Competitiv", "Prea scump"], "fd_verdict")
    f_cost = st.slider("Cost total (lei)", int(cmin), int(cmax), (int(cmin), int(cmax)), key="fd_cost")
    st.button("Resetează filtrele", on_click=reset_filtre, args=("fd_",), icon=":material/restart_alt:")
marja_min = c2.number_input("Marjă minimă (%)", 0.0, 200.0, float(st.session_state.get("marja_min", 10.0)), 1.0,
                            help="Prețul recomandat nu coboară sub cost × (1 + marja minimă)")
sub_piata = c3.number_input("Sub piață (%)", 0.0, 50.0, float(st.session_state.get("sub_piata", 3.0)), 0.5,
                            help="Cu cât vrei să fii sub media concurenței")
st.session_state["marja_min"], st.session_state["sub_piata"] = marja_min, sub_piata

cost_filtrat = f_cost if f_cost != (int(cmin), int(cmax)) else None
filtre_active({"Categorie": f_cat, "Marcă": f_marca, "Verdict": f_verdict,
               "Cost": f"{cost_filtrat[0]}–{cost_filtrat[1]} lei" if cost_filtrat else None,
               "Magazine": st.session_state.get("magazine")})

df, sql, prm = decizie(con, sau_toate(f_cat, CATEGORII), magazine, marja, f_marca or None, marja_min, sub_piata)
if f_verdict:
    df = df[df["recomandare"].isin(f_verdict)]
if cost_filtrat:
    df = df[df["cost_total"].between(*cost_filtrat)]
sql_box(sql, {**prm, "marja": marja}, "Interogarea SQL dinamică")
if df.empty:
    st.info("Nicio piesă nu corespunde filtrelor.")
    st.stop()

n_comp = int((df["recomandare"] == "Competitiv").sum())
k = st.columns(4)
k[0].metric("Piese afișate", len(df))
k[1].metric(f"Competitive la marja de {marja}%", f"{n_comp} din {len(df)}",
            f"{len(df) - n_comp} prea scumpe" if n_comp < len(df) else "toate", delta_arrow="off",
            delta_color="red" if n_comp < len(df) else "green")
k[2].metric("Marjă medie recomandată", f"{df['marja_realizata_%'].mean():.1f}%",
            help="Marja obținută dacă aplici prețul recomandat")
k[3].metric("Marjă maximă competitivă", f"{df['marja_max_competitiva_%'].mean():.1f}%",
            help="Cea mai mare marjă la care prețul rămâne ≤ media pieței (media pe piesele afișate)")

# ---------------------------------------------------------------- grafic cu comutator
with card("Prețul față de piață"):
    tip = st.segmented_control("Tip grafic", ["Poziționare", "Coloane", "Diferență față de piață"],
                               default="Poziționare", key="g_dec", label_visibility="collapsed") or "Poziționare"
    if tip == "Poziționare":
        fig = go.Figure()
        fig.add_bar(x=df["cod"], y=df["max_concurenta"] - df["min_concurenta"], base=df["min_concurenta"],
                    name="Interval concurență", marker_color="rgba(148,163,184,0.35)", width=0.55)
        fig.add_scatter(x=df["cod"], y=df["cost_total"], mode="markers", name="Cost",
                        marker=dict(symbol="line-ew-open", size=26, color="#0f172a", line=dict(width=3, color="#0f172a")))
        fig.add_scatter(x=df["cod"], y=df["media_concurenta"], mode="markers", name="Media pieței",
                        marker=dict(size=10, color="#64748b"))
        fig.add_scatter(x=df["cod"], y=df["pret_propus"], mode="markers", name="Preț propus",
                        marker=dict(size=13, symbol="diamond", color="#2563eb"))
        fig.add_scatter(x=df["cod"], y=df["pret_recomandat"], mode="markers", name="Preț recomandat",
                        marker=dict(size=16, symbol="star", color="#16a34a"))
        fig.update_yaxes(title="lei")
        fig = style_fig(fig, 420, legend_bottom=True)
    elif tip == "Coloane":
        long = df.melt(id_vars="cod", value_vars=["cost_total", "pret_propus", "media_concurenta", "pret_recomandat"],
                       var_name="indicator", value_name="lei")
        long["indicator"] = long["indicator"].map({"cost_total": "Cost", "pret_propus": "Preț propus",
                                                   "media_concurenta": "Media pieței", "pret_recomandat": "Preț recomandat"})
        fig = grafic(long, "cod", "lei", "Coloane", color="indicator", height=420,
                     color_map={"Cost": "#0f172a", "Preț propus": "#2563eb", "Media pieței": "#94a3b8",
                                "Preț recomandat": "#16a34a"}, labels={"cod": ""})
        fig.update_traces(texttemplate=None)
    else:
        d = df.assign(dif=((df["pret_propus"] / df["media_concurenta"] - 1) * 100).round(1))
        fig = go.Figure(go.Bar(x=d["cod"], y=d["dif"], text=d["dif"].map(lambda v: f"{v:+.1f}%"),
                               marker_color=["#dc2626" if v > 0 else "#16a34a" for v in d["dif"]]))
        fig.add_hline(0, line_color="#0f172a")
        fig.update_yaxes(title="preț propus față de media pieței (%)")
        fig = style_fig(fig, 420)
    st.plotly_chart(fig)

with card("Prețuri"):
    show = df[["cod", "denumire", "marca", "cost_total", "pret_propus", "media_concurenta", "recomandare",
               "pret_recomandat", "marja_realizata_%", "marja_max_competitiva_%", "pozitie_piata"]].copy()
    show.insert(6, "fata_de_piata", ((show["pret_propus"] / show["media_concurenta"] - 1) * 100).round(1))
    show["recomandare"] = show["recomandare"].map(verdict_badge)
    show["pozitie_piata"] = show["pozitie_piata"].map(pozitie_badge)
    st.caption("🟩 verde = bine · 🟥 roșu = problemă · culoarea e mai intensă cu cât diferența e mai mare")
    lei = "{:,.0f} lei"
    st.dataframe(coloreaza(show, bun_mic=["fata_de_piata"], bun_mare=["marja_max_competitiva_%"],
                           intensitate=["marja_realizata_%"],
                           fmt={"cost_total": lei, "pret_propus": lei, "media_concurenta": lei, "pret_recomandat": lei,
                                "fata_de_piata": "{:+.1f}%", "marja_realizata_%": "{:.1f}%",
                                "marja_max_competitiva_%": "{:.1f}%"}),
                 hide_index=True, column_config={
        "cod": "Cod", "denumire": "Denumire", "marca": "Marcă", "cost_total": "Cost",
        "pret_propus": f"Preț propus ({marja}%)", "media_concurenta": "Media pieței",
        "fata_de_piata": st.column_config.Column("Față de piață", help="Preț propus față de media pieței"),
        "recomandare": "Verdict", "pret_recomandat": "Preț recomandat",
        "marja_realizata_%": "Marjă recomandată", "marja_max_competitiva_%": "Marjă max. competitivă",
        "pozitie_piata": "Poziție pe piață"})
    exp = df[["cod", "denumire", "marca", "categorie", "cost_total", "pret_propus", "media_concurenta",
              "min_concurenta", "max_concurenta", "recomandare", "pret_recomandat", "marja_realizata_%",
              "marja_max_competitiva_%", "pozitie_piata"]].copy()
    exp["dif_fata_de_piata_%"] = ((exp["pret_propus"] / exp["media_concurenta"] - 1) * 100).round(1)
    if tip == "Diferență față de piață":
        g = {"tip": "Coloane", "x": "cod", "y": ["dif_fata_de_piata_%"], "titlu": "Preț propus față de media pieței (%)",
             "axa": "%"}
    else:
        g = {"tip": "Coloane", "x": "cod", "y": ["cost_total", "pret_propus", "media_concurenta", "pret_recomandat"],
             "titlu": f"Cost, preț propus ({marja}%), media pieței, preț recomandat", "axa": "lei"}
    st.download_button("⬇️ Exportă tabelul și graficul (Excel)", xlsx_export([("Decizie pret", exp, g, None,
                                                                {"dif_fata_de_piata_%": "bun_mic",
                                                                 "marja_max_competitiva_%": "bun_mare",
                                                                 "marja_realizata_%": "intensitate"})]),
                       "decizie_pret.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

with card("Detaliu piesă"):
    cod = st.selectbox("Piesa", df["cod"] + " – " + df["denumire"], label_visibility="collapsed")
    c = cod.split(" – ")[0]
    det_sql = "SELECT magazin, pret FROM preturi_concurenta WHERE cod = :cod ORDER BY pret"
    det = q(con, det_sql, {"cod": c})
    row = df[df["cod"] == c].iloc[0]
    a, b = st.columns([2, 3])
    with a:
        st.metric("Cost total", f"{row['cost_total']:,.0f} lei")
        st.metric("Preț propus", f"{row['pret_propus']:,.0f} lei",
                  f"{row['pret_propus'] - row['media_concurenta']:+,.0f} lei față de piață", delta_color="inverse")
        st.metric("Preț recomandat", f"{row['pret_recomandat']:,.0f} lei",
                  f"profit {row['profit_unitar']:,.0f} lei / bucată", delta_color="off", delta_arrow="off")
    with b:
        f2 = go.Figure(go.Bar(x=det["magazin"], y=det["pret"], text=det["pret"], marker_color="#cbd5e1",
                              textposition="outside"))
        f2.add_hline(row["pret_propus"], line_color="#2563eb", annotation_text="propus")
        f2.add_hline(row["pret_recomandat"], line_color="#16a34a", line_dash="dash", annotation_text="recomandat")
        f2.add_hline(row["cost_total"], line_color="#0f172a", line_dash="dot", annotation_text="cost")
        st.plotly_chart(style_fig(f2, 330))
    sql_box(det_sql, {"cod": c})
