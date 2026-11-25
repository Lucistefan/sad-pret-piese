import plotly.graph_objects as go
import streamlit as st

from core.db import CATEGORII, q
from core.models import decizie
from core.state import get_con, sql_box

st.title("🏷️ Preț de vânzare")

con, tables, log = get_con()
marja = st.session_state.get("marja", 30)
magazine = st.session_state.get("magazine") or ["Magazin A", "Magazin B", "Magazin C"]

c1, c2, c3, c4 = st.columns([2, 2, 1, 1])
cats = c1.multiselect("Categorie", CATEGORII, default=st.session_state.get("cat_decizie", ["Ambreiaj"]))
st.session_state["cat_decizie"] = cats
marci_all = q(con, "SELECT DISTINCT marca FROM piese ORDER BY marca")["marca"].tolist()
marci = c2.multiselect("Marcă (opțional)", marci_all)
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
sql_box(sql, {**prm, "marja": marja}, "Interogarea SQL dinamică")

k = st.columns(4)
n_comp = int((df["recomandare"] == "Competitiv").sum())
k[0].metric("Piese", len(df))
k[1].metric(f"Competitive la {marja}%", f"{n_comp} / {len(df)}")
k[2].metric("Marjă medie recomandată", f"{df['marja_realizata_%'].mean():.1f}%")
k[3].metric("Marjă maximă competitivă", f"{df['marja_max_competitiva_%'].mean():.1f}%")

show = df[["cod", "denumire", "marca", "cost_total", "pret_propus", "media_concurenta", "recomandare",
           "pret_recomandat", "marja_realizata_%", "pozitie_piata"]]


def color(v):
    return {"Competitiv": "background-color:#dcfce7", "Prea scump": "background-color:#fee2e2"}.get(v, "")


st.dataframe(show.style.map(color, subset=["recomandare"]).format(precision=0, subset=[
    "cost_total", "pret_propus", "media_concurenta", "pret_recomandat"]).format(precision=1, subset=["marja_realizata_%"]),
    hide_index=True, column_config={
        "cod": "Cod", "denumire": "Denumire", "marca": "Marcă",
        "cost_total": "Cost", "pret_propus": "Preț propus", "media_concurenta": "Media pieței",
        "recomandare": "Verdict", "pret_recomandat": "Preț recomandat", "marja_realizata_%": "Marjă %",
        "pozitie_piata": "Poziție"})

fig = go.Figure()
fig.add_bar(x=df["cod"], y=df["max_concurenta"] - df["min_concurenta"], base=df["min_concurenta"],
            name="Interval concurență (min–max)", marker_color="rgba(148,163,184,0.35)")
fig.add_scatter(x=df["cod"], y=df["cost_total"], mode="markers", name="Cost total",
                marker=dict(symbol="line-ew-open", size=26, line=dict(width=3, color="black")))
fig.add_scatter(x=df["cod"], y=df["media_concurenta"], mode="markers", name="Media concurenței",
                marker=dict(size=10, color="#64748b"))
fig.add_scatter(x=df["cod"], y=df["pret_propus"], mode="markers", name=f"Preț propus (marjă {marja}%)",
                marker=dict(size=12, symbol="diamond", color="#2563eb"))
fig.add_scatter(x=df["cod"], y=df["pret_recomandat"], mode="markers", name="Preț recomandat",
                marker=dict(size=15, symbol="star", color="#16a34a"))
fig.update_layout(title="Prețul față de piață", yaxis_title="lei", height=440,
                  legend=dict(orientation="h", y=-0.15))
st.plotly_chart(fig)

st.subheader("Detaliu piesă")
cod = st.selectbox("Piesa", df["cod"] + " – " + df["denumire"])
c = cod.split(" – ")[0]
det_sql = "SELECT magazin, pret FROM preturi_concurenta WHERE cod = :cod ORDER BY pret"
det = q(con, det_sql, {"cod": c})
row = df[df["cod"] == c].iloc[0]
a, b = st.columns([2, 3])
with a:
    st.metric("Cost total", f"{row['cost_total']:,.0f} lei")
    st.metric("Preț propus", f"{row['pret_propus']:,.0f} lei", f"{row['pret_propus'] - row['media_concurenta']:+,.0f} față de medie",
              delta_color="inverse")
    st.metric("Preț recomandat", f"{row['pret_recomandat']:,.0f} lei", f"profit {row['profit_unitar']:,.0f} lei/buc",
              delta_color="off")
with b:
    f2 = go.Figure(go.Bar(x=det["magazin"], y=det["pret"], text=det["pret"], marker_color="#94a3b8"))
    f2.add_hline(row["pret_propus"], line_color="#2563eb", annotation_text="propus")
    f2.add_hline(row["pret_recomandat"], line_color="#16a34a", line_dash="dash", annotation_text="recomandat")
    f2.add_hline(row["cost_total"], line_color="black", line_dash="dot", annotation_text="cost")
    f2.update_layout(title=f"{c}: prețuri la concurență", height=320)
    st.plotly_chart(f2)
sql_box(det_sql, {"cod": c})
