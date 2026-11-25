import plotly.graph_objects as go
import streamlit as st

from core.db import CATEGORII, q
from core.models import decizie
from core.state import get_con, sql_box
from core.ui import card, header, pozitie_badge, style_fig, verdict_badge, xlsx_bytes

header("🏷️", "Preț de vânzare", "Cost + marjă comparat cu prețurile concurenței")

con, tables, log = get_con()
marja = st.session_state.get("marja", 30)
magazine = st.session_state.get("magazine") or ["Magazin A", "Magazin B", "Magazin C"]

with card():
    c1, c2, c3, c4 = st.columns([3, 2, 1, 1])
    cats = c1.pills("Categorie", CATEGORII, selection_mode="multi",
                    default=st.session_state.get("cat_decizie", ["Ambreiaj"]))
    st.session_state["cat_decizie"] = cats
    marci_all = q(con, "SELECT DISTINCT marca FROM piese ORDER BY marca")["marca"].tolist()
    marci = c2.multiselect("Marcă", marci_all, placeholder="toate mărcile")
    marja_min = c3.number_input("Marjă minimă (%)", 0.0, 200.0, float(st.session_state.get("marja_min", 10.0)), 1.0)
    sub_piata = c4.number_input("Sub piață (%)", 0.0, 50.0, float(st.session_state.get("sub_piata", 3.0)), 0.5)
    st.session_state["marja_min"], st.session_state["sub_piata"] = marja_min, sub_piata

if not cats:
    st.info("Alege cel puțin o categorie.")
    st.stop()
if not magazine:
    st.warning("Alege cel puțin un magazin concurent din bara laterală.")
    st.stop()

df, sql, prm = decizie(con, cats, magazine, marja, marci, marja_min, sub_piata)
if df.empty:
    st.info("Nicio piesă pentru filtrele alese.")
    st.stop()
sql_box(sql, {**prm, "marja": marja}, "Interogarea SQL dinamică")

n_comp = int((df["recomandare"] == "Competitiv").sum())
k = st.columns(4)
k[0].metric("Piese analizate", len(df))
k[1].metric(f"Competitive la marja de {marja}%", f"{n_comp} din {len(df)}",
            f"{len(df) - n_comp} prea scumpe" if n_comp < len(df) else "toate", delta_color="red" if n_comp < len(df) else "green",
            delta_arrow="off")
k[2].metric("Marjă medie recomandată", f"{df['marja_realizata_%'].mean():.1f}%")
k[3].metric("Marjă maximă competitivă", f"{df['marja_max_competitiva_%'].mean():.1f}%")

with card("Prețuri"):
    show = df[["cod", "denumire", "cost_total", "pret_propus", "media_concurenta", "recomandare",
               "pret_recomandat", "marja_realizata_%", "pozitie_piata"]].copy()
    show["recomandare"] = show["recomandare"].map(verdict_badge)
    show["pozitie_piata"] = show["pozitie_piata"].map(pozitie_badge)
    lei = lambda t: st.column_config.NumberColumn(t, format="%d lei")  # noqa: E731
    st.dataframe(show, hide_index=True, column_config={
        "cod": "Cod", "denumire": "Denumire", "marca": "Marcă", "cost_total": lei("Cost"),
        "pret_propus": lei(f"Preț propus ({marja}%)"), "media_concurenta": lei("Media pieței"),
        "recomandare": "Verdict", "pret_recomandat": lei("Preț recomandat"),
        "marja_realizata_%": st.column_config.ProgressColumn("Marjă recomandată", format="%.1f%%", min_value=0,
                                                              max_value=max(60.0, float(df["marja_realizata_%"].max()))),
        "pozitie_piata": "Poziție pe piață"})
    st.download_button("⬇️ Exportă tabelul (Excel)", xlsx_bytes(df, "Decizie pret"), "decizie_pret.xlsx",
                       "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

with card("Prețul față de piață"):
    fig = go.Figure()
    fig.add_bar(x=df["cod"], y=df["max_concurenta"] - df["min_concurenta"], base=df["min_concurenta"],
                name="Interval concurență", marker_color="rgba(148,163,184,0.35)", width=0.55)
    fig.add_scatter(x=df["cod"], y=df["cost_total"], mode="markers", name="Cost",
                    marker=dict(symbol="line-ew-open", size=28, line=dict(width=3, color="#0f172a")))
    fig.add_scatter(x=df["cod"], y=df["media_concurenta"], mode="markers", name="Media pieței",
                    marker=dict(size=10, color="#64748b"))
    fig.add_scatter(x=df["cod"], y=df["pret_propus"], mode="markers", name="Preț propus",
                    marker=dict(size=13, symbol="diamond", color="#2563eb"))
    fig.add_scatter(x=df["cod"], y=df["pret_recomandat"], mode="markers", name="Preț recomandat",
                    marker=dict(size=16, symbol="star", color="#16a34a"))
    fig.update_yaxes(title="lei")
    st.plotly_chart(style_fig(fig, 420, legend_bottom=True))

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
