import streamlit as st

from core.db import CATEGORII
from core.state import build_context, get_con, params
from core.ui import PAL, card, coloreaza, filtre_active, filtru_multi, grafic, header, reset_filtre

EXPLICATIE = """
**PrețPiese** este un sistem de asistare a deciziilor pentru un magazin online de piese auto.
Răspunde la întrebarea: **ce preț pun pe fiecare piesă?**

**Surse de date** (3 foi Google Sheets, încărcate într-o bază SQLite):
1. **Furnizor:** prețul de achiziție și transportul fiecărei piese;
2. **Concurență:** prețurile aceleiași piese la 3 magazine;
3. **Vânzări:** vânzări lunare pe categorii, comenzi pe țări, tipuri de clienți.

**Modele decizionale:**
- **Preț de vânzare:** cost + marjă comparat cu media pieței → verdict și preț recomandat;
- **Prognoză:** câte piese voi vinde luna viitoare (trend liniar);
- **Simulare:** merită o reducere / creștere de preț? (elasticitate, profit).

**Rapoarte:** export Excel, PDF și hartă a comenzilor.

Pe această pagină vezi rezumatul; detaliile sunt în paginile din meniul din stânga.
"""

header("📊", "Panou general", "Situația prețurilor, vânzărilor și piețelor dintr-o privire", EXPLICATIE)

con, tables, log = get_con()
for key, src, status in log:
    if status != "ok":
        st.warning(f"{key}: {status}. Folosesc {src}.")

with st.columns([1, 3])[0].popover("Filtre", icon=":material/filter_list:", width="stretch"):
    f_cat = filtru_multi(st, "Categorie", CATEGORII, "fp_cat")
    st.button("Resetează filtrele", on_click=reset_filtre, args=("fp_",), icon=":material/restart_alt:")
filtre_active({"Categorie": f_cat})

p = params()
p["categorii"] = f_cat or CATEGORII
ctx = build_context(con, tables, log, p)
dec = ctx["decizie"]
scumpe = dec[dec["recomandare"] == "Prea scump"]
cl = ctx["clienti"].sort_values("valoare", ascending=False)
tari = ctx["tari"].sort_values("comenzi", ascending=False)
det = ctx["prognoza_det"].set_index("categorie")
cats = p["categorii"]
lun = ctx["lunar"][ctx["lunar"]["categorie"].isin(cats)]
ult = lun[lun["nr"] == lun["nr"].max()]["bucati"].sum()
prog = sum(int(det.loc[c, "prognoza_luna_urm"]) for c in cats) if f_cat else int(ctx["prognoza_total"])

k = st.columns(4)
k[0].metric(f"Piese competitive la {p['marja']}%", f"{len(dec) - len(scumpe)} din {len(dec)}",
            f"{len(scumpe)} de revizuit", delta_color="red" if len(scumpe) else "off", delta_arrow="off",
            help="Piese al căror preț propus (cost + marjă) nu depășește media pieței")
k[1].metric("Prognoză luna următoare", f"{prog} buc", f"{prog - int(ult):+d} față de ultima lună",
            help="Trend liniar pe ultimele 12 luni")
k[2].metric("Cea mai mare piață", tari.iloc[0]["tara"], f"{int(tari.iloc[0]['comenzi'])} comenzi",
            delta_color="off", delta_arrow="off")
k[3].metric(f"Top clienți: {cl.iloc[0]['tip_client']}", f"{cl.iloc[0]['valoare']:,.0f} lei".replace(",", "."),
            f"{cl.iloc[0]['valoare'] / cl['valoare'].sum() * 100:.0f}% din vânzări", delta_color="off", delta_arrow="off")

a, b = st.columns([3, 2])
with a:
    with card("Prețuri de revizuit"):
        if scumpe.empty:
            st.success("Toate piesele sunt competitive la marja aleasă.", icon="✅")
        else:
            t = scumpe[["cod", "denumire", "pret_propus", "media_concurenta", "pret_recomandat"]].copy()
            t.insert(0, "ok", "❌")
            t["peste_piata"] = ((t["pret_propus"] / t["media_concurenta"] - 1) * 100).round(1)
            st.dataframe(coloreaza(t, bun_mic=["peste_piata"],
                                   fmt={"pret_propus": "{:,.0f} lei", "media_concurenta": "{:,.0f} lei",
                                        "pret_recomandat": "{:,.0f} lei", "peste_piata": "{:+.1f}%"}),
                         hide_index=True, height=260, column_config={
                "ok": st.column_config.Column("", width=40), "cod": "Cod", "denumire": "Denumire",
                "pret_propus": "Preț propus", "media_concurenta": "Media pieței", "pret_recomandat": "Preț recomandat",
                "peste_piata": "Peste piață"})
        st.page_link("views/decizie.py", label="Deschide analiza de preț", icon=":material/arrow_forward:")
with b:
    with card("Prognoză luna următoare"):
        tip = st.segmented_control("Tip grafic", ["Coloane", "Plăcintă", "Bare orizontale"], default="Coloane",
                                   key="g_home_prog", label_visibility="collapsed") or "Coloane"
        d = det.drop(index="Total").reset_index()
        d = d[d["categorie"].isin(cats)]
        fig = grafic(d, "categorie", "prognoza_luna_urm", tip, color="categorie", color_map=PAL, height=300,
                     labels={"categorie": "", "prognoza_luna_urm": "bucăți"})
        fig.update_layout(showlegend=tip == "Plăcintă")
        st.plotly_chart(fig)

c, d = st.columns([3, 2])
with c:
    with card("Vânzări lunare"):
        tip2 = st.segmented_control("Tip grafic", ["Arie", "Linii", "Coloane stivuite"], default="Arie",
                                    key="g_home_vz", label_visibility="collapsed") or "Arie"
        ordine = lun.drop_duplicates("nr").sort_values("nr")["luna"].tolist()
        st.plotly_chart(grafic(lun, "luna", "bucati", tip2, color="categorie", color_map=PAL, height=280,
                               labels={"luna": "", "bucati": "bucăți", "categorie": ""}, order=ordine))
with d:
    with card("Valoare comenzi pe tip de client"):
        tip3 = st.segmented_control("Tip grafic", ["Plăcintă", "Coloane"], default="Plăcintă", key="g_home_cl",
                                    label_visibility="collapsed") or "Plăcintă"
        st.plotly_chart(grafic(cl, "tip_client", "valoare", tip3, color="tip_client", height=280,
                               labels={"tip_client": "", "valoare": "lei"}))
