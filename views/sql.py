import re

import streamlit as st

from core.db import DDL, RELATII, coloane, db_bytes, integritate, q, schema
from core.state import get_con
from core.ui import card, header

EXPLICATIE = """
**Cum ajung datele în baza de date:**
1. La pornire, aplicația citește cele 3 foi Google Sheets (export CSV) sau copia locală.
2. Datele sunt curățate și aduse în formă de tabel (ex. prețurile concurenței: din coloane pe magazine → câte un rând pentru fiecare piesă și magazin).
3. Se creează o bază **SQLite în memorie** cu `CREATE TABLE` (chei primare, chei străine, constrângeri `CHECK`) și se inserează datele.

**De ce SQL dinamic:** interogările se construiesc din filtrele alese de utilizator
(ex. `WHERE categorie IN (:cat0, :cat1)`), cu **parametri** (`:nume`), nu prin lipirea textului. Așa se evită SQL injection.

**Relații:**
- `piese` 1 → N `preturi_concurenta` (prin `cod`);
- `categorii` 1 → N `piese` și 1 → N `vanzari_lunare` (prin `categorie`).
"""

header("🗄️", "Baza de date & SQL", "Structura bazei, relațiile și interogări pe date", EXPLICATIE)
con, tables, log = get_con()

sch = schema(con)
k = st.columns(4)
k[0].metric("Tabele", int((sch["tip"] == "tabel").sum()))
k[1].metric("Vederi (VIEW)", int((sch["tip"] == "vedere").sum()))
k[2].metric("Înregistrări", int(sch.loc[sch["tip"] == "tabel", "rânduri"].sum()))
k[3].metric("Relații (chei străine)", len(RELATII))

t_er, t_str, t_build, t_cons = st.tabs(["Diagrama", "Structura", "Constructor de interogări", "Consolă SQL"])

# ------------------------------------------------------------------ diagrama ER
with t_er:
    def nod(t):
        rows = "".join(
            f'<TR><TD ALIGN="LEFT" PORT="{r.coloana}">{"🔑 " if "PK" in r.cheie else ("🔗 " if "FK" in r.cheie else "")}'
            f'<B>{r.coloana}</B></TD><TD ALIGN="LEFT"><FONT COLOR="#64748b">{r.tip}</FONT></TD></TR>'
            for r in coloane(con, t).itertuples())
        culoare = "#2563eb" if t != "categorii" else "#0f172a"
        return (f'{t} [label=<<TABLE BORDER="0" CELLBORDER="1" CELLSPACING="0" CELLPADDING="5" COLOR="#cbd5e1">'
                f'<TR><TD COLSPAN="2" BGCOLOR="{culoare}"><FONT COLOR="white"><B>{t}</B></FONT></TD></TR>{rows}</TABLE>>];')

    tab_names = sch.loc[sch["tip"] == "tabel", "obiect"].tolist()
    muchii = "\n".join(f'{b} -> {a} [label="  1 : N\\n  ({ca})", fontsize=10, color="#2563eb", fontcolor="#1d4ed8"];'
                       for a, ca, b, cb, _ in RELATII)
    dot = f"""digraph ER {{
        graph [rankdir=TB, bgcolor="transparent", nodesep=0.6, ranksep=0.7, fontname="Helvetica"];
        node [shape=plaintext, fontname="Helvetica", fontsize=11];
        edge [fontname="Helvetica", dir=both, arrowtail=tee, arrowhead=crow];
        {"".join(nod(t) for t in tab_names)}
        {muchii}
        comenzi_tari -> clienti [style=invis];
    }}"""
    with card():
        st.graphviz_chart(dot, width="stretch")
        st.caption("🔑 cheie primară · 🔗 cheie străină · linia simplă = „unu”, ramificația = „mulți”. "
                   "`comenzi_tari` și `clienti` sunt tabele de sine stătătoare (agregate din sursa Vânzări).")

# ------------------------------------------------------------------ structura
with t_str:
    a, b = st.columns([1, 2])
    with a:
        st.dataframe(sch[["obiect", "tip", "rânduri"]], hide_index=True, width="stretch")
        fk = integritate(con)
        if fk.empty:
            st.success("Integritate referențială: toate cheile străine sunt valide.", icon=":material/verified:")
        else:
            st.warning(f"{len(fk)} rânduri încalcă cheile străine.")
            st.dataframe(fk, hide_index=True)
    with b:
        ales = st.selectbox("Tabel / vedere", sch["obiect"].tolist())
        st.dataframe(coloane(con, ales), hide_index=True, width="stretch", column_config={
            "coloana": "Coloană", "tip": "Tip", "cheie": "Cheie", "referă": "Referă", "obligatoriu": "NOT NULL"})
        st.dataframe(q(con, f"SELECT * FROM {ales} LIMIT 50"), hide_index=True, height=240)
    with st.expander("Scriptul de creare a bazei (DDL)"):
        st.code(DDL.strip(), language="sql")
    d1, d2, _ = st.columns([1, 1, 2])
    d1.download_button("⬇️ Baza de date (.db)", db_bytes(con), "pret_piese.db", "application/x-sqlite3",
                       width="stretch", help="Se deschide cu DB Browser for SQLite")
    d2.download_button("⬇️ Script SQL (.sql)", DDL.strip(), "schema.sql", "text/plain", width="stretch")

# ------------------------------------------------------------------ constructor vizual
OPERATORI = {"=": "=", "≠": "<>", ">": ">", "≥": ">=", "<": "<", "≤": "<=", "conține": "LIKE"}
AGREGARI = {"Număr (COUNT)": "COUNT", "Sumă (SUM)": "SUM", "Medie (AVG)": "AVG", "Minim (MIN)": "MIN",
            "Maxim (MAX)": "MAX"}

with t_build:
    st.caption("Alegi din liste, aplicația scrie interogarea SQL. Câmpurile lăsate goale nu se aplică.")
    c1, c2 = st.columns(2)
    tabel = c1.selectbox("Din tabelul", sch["obiect"].tolist(), index=sch["obiect"].tolist().index("v_piese_piata"))
    cols_info = q(con, f"SELECT * FROM {tabel} LIMIT 200")
    cols = cols_info.columns.tolist()
    numerice = cols_info.select_dtypes("number").columns.tolist()
    sel = c2.multiselect("Coloane", cols, placeholder="Toate coloanele (*)")

    c3, c4, c5 = st.columns([1.2, 0.8, 1.2])
    f_col = c3.selectbox("Condiție (WHERE)", cols, index=None, placeholder="fără condiție")
    f_op = c4.selectbox("Operator", list(OPERATORI), disabled=f_col is None)
    if f_col and f_col in numerice:
        f_val = c5.number_input("Valoare", value=float(cols_info[f_col].median()))
    elif f_col:
        f_val = c5.selectbox("Valoare", sorted(cols_info[f_col].dropna().astype(str).unique()), accept_new_options=True)
    else:
        f_val = c5.text_input("Valoare", disabled=True)

    c6, c7, c8 = st.columns([1.2, 1, 1.2])
    grup = c6.selectbox("Grupare (GROUP BY)", [c for c in cols if c not in numerice], index=None,
                        placeholder="fără grupare")
    agr = c7.selectbox("Funcție", list(AGREGARI), disabled=grup is None)
    agr_col = c8.selectbox("Pe coloana", numerice or cols, disabled=grup is None)

    c9, c10, c11 = st.columns([1.2, 1, 1.2])
    ord_opt = ([grup, "rezultat"] if grup else (sel or cols))
    ordine = c9.selectbox("Sortare (ORDER BY)", ord_opt, index=None, placeholder="fără sortare")
    desc = c10.toggle("Descrescător", disabled=ordine is None)
    limita = c11.number_input("Limită rânduri", 1, 1000, 100)

    params = {}
    if grup:
        select = f"{grup}, {AGREGARI[agr]}({agr_col}) AS rezultat"
    else:
        select = ", ".join(sel) if sel else "*"
    sql_b = f"SELECT {select}\nFROM {tabel}"
    if f_col:
        op = OPERATORI[f_op]
        params["valoare"] = f"%{f_val}%" if op == "LIKE" else f_val
        sql_b += f"\nWHERE {f_col} {op} :valoare"
    if grup:
        sql_b += f"\nGROUP BY {grup}"
    if ordine:
        sql_b += f"\nORDER BY {ordine}{' DESC' if desc else ''}"
    sql_b += f"\nLIMIT {int(limita)}"

    with card():
        st.code(sql_b, language="sql")
        if params:
            st.caption(f"Parametri: `{params}`")
        try:
            res = q(con, sql_b, params)
            st.caption(f"{len(res)} rânduri")
            st.dataframe(res, hide_index=True)
        except Exception as e:  # noqa: BLE001
            st.error(f"Eroare SQL: {e}")

# ------------------------------------------------------------------ consola
EXEMPLE = {
    "Piese competitive la marja de 30% (JOIN + GROUP BY + HAVING)": """SELECT p.cod, p.denumire,
       p.pret_achizitie + p.transport AS cost,
       ROUND((p.pret_achizitie + p.transport) * 1.30) AS pret_propus,
       ROUND(AVG(c.pret)) AS media_conc
FROM piese p JOIN preturi_concurenta c ON c.cod = p.cod
GROUP BY p.cod
HAVING pret_propus <= media_conc
ORDER BY p.categorie;""",
    "Cel mai ieftin magazin pentru fiecare piesă (subinterogare corelată)": """SELECT c.cod, p.denumire, c.magazin, c.pret
FROM preturi_concurenta c JOIN piese p ON p.cod = c.cod
WHERE c.pret = (SELECT MIN(pret) FROM preturi_concurenta x WHERE x.cod = c.cod)
ORDER BY c.cod;""",
    "Marja maximă competitivă pe categorie (folosește vederea)": """SELECT categorie,
       ROUND(AVG((media_pietei / cost_total - 1) * 100), 1) AS marja_max_pct
FROM v_piese_piata
GROUP BY categorie ORDER BY marja_max_pct DESC;""",
    "Vânzări totale pe categorie (agregări)": """SELECT categorie, SUM(bucati) AS total, ROUND(AVG(bucati), 1) AS medie_lunara,
       MAX(bucati) AS maxim, MIN(bucati) AS minim
FROM vanzari_lunare GROUP BY categorie ORDER BY total DESC;""",
    "Ponderea țărilor în comenzi (funcții fereastră)": """SELECT tara, comenzi,
       ROUND(100.0 * comenzi / SUM(comenzi) OVER (), 1) AS pondere_pct,
       SUM(comenzi) OVER (ORDER BY comenzi DESC) AS cumulat
FROM comenzi_tari ORDER BY comenzi DESC;""",
    "Clasificarea pieselor după preț (CASE)": """SELECT cod, denumire, cost_total, media_pietei,
       CASE WHEN media_pietei >= cost_total * 1.5 THEN 'marjă mare'
            WHEN media_pietei >= cost_total * 1.2 THEN 'marjă medie'
            ELSE 'marjă mică' END AS clasa
FROM v_piese_piata ORDER BY media_pietei / cost_total DESC;""",
    "Vânzări pe trimestre (CTE)": """WITH t AS (
  SELECT categorie, (nr - 1) / 3 + 1 AS trimestru, bucati FROM vanzari_lunare)
SELECT categorie, trimestru, SUM(bucati) AS bucati
FROM t GROUP BY categorie, trimestru ORDER BY categorie, trimestru;""",
}

with t_cons:
    ex = st.selectbox("Exemplu", list(EXEMPLE))
    sql = st.text_area("Interogare", EXEMPLE[ex], height=200)
    if st.button("Rulează", type="primary", icon=":material/play_arrow:"):
        if not re.match(r"^\s*(select|with)\b", sql, re.I) or re.search(
                r"\b(insert|update|delete|drop|alter|create|attach|pragma|replace)\b", sql, re.I):
            st.error("Sunt permise doar interogări de citire (SELECT / WITH).")
        else:
            try:
                res = q(con, sql)
                st.success(f"{len(res)} rânduri")
                st.dataframe(res, hide_index=True)
                st.download_button("⬇️ Rezultat CSV", res.to_csv(index=False).encode("utf-8-sig"), "rezultat.csv",
                                   "text/csv")
            except Exception as e:  # noqa: BLE001
                st.error(f"Eroare SQL: {e}")
