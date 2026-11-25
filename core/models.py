"""Modelele decizionale – aceleași formule ca în Google Sheets, plus extensii.

M1. Stabilirea prețului (foaia Decizie): preț propus = cost total × (1 + marjă), comparat cu media concurenței.
M2. Prognoza vânzărilor (foaia Vânzări): trend liniar, identic cu FORECAST() din Sheets/Excel.
M3. Simulare modificare de preț (foaia Simulare): elasticitate pe 3 niveluri (Mult / Mediu / Puțin).
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from core.db import q

ELASTICITATE = {"Mult": -1.5, "Mediu": -1.0, "Puțin": -0.5}
REACTIE_IMPLICITA = {"Frâne": "Mult", "Filtre": "Mult", "Suspensie": "Mediu", "Ambreiaj": "Puțin"}


def xround(x, nd=0):
    """ROUND din Excel/Sheets (jumătatea se rotunjește în sus, nu „bancar” ca în Python)."""
    m = 10 ** nd
    return math.floor(abs(x) * m + 0.5 + 1e-9) / m * (1 if x >= 0 else -1)


# =========================================================================== M1 – prețul
def sql_decizie(categorii, magazine, marci=None):
    """Construiește interogarea SQL dinamică (echivalentul QUERY + VLOOKUP din Sheets).
    Filtrele vin din controalele din interfață, valorile sunt transmise ca parametri."""
    params = {}
    cat_ph = ", ".join(f":cat{i}" for i in range(len(categorii)))
    mag_ph = ", ".join(f":mag{i}" for i in range(len(magazine)))
    params.update({f"cat{i}": c for i, c in enumerate(categorii)})
    params.update({f"mag{i}": m for i, m in enumerate(magazine)})
    where_marca = ""
    if marci:
        where_marca = "\n  AND p.marca IN (" + ", ".join(f":mar{i}" for i in range(len(marci))) + ")"
        params.update({f"mar{i}": m for i, m in enumerate(marci)})
    sql = f"""SELECT p.cod, p.denumire, p.categorie, p.marca,
       p.pret_achizitie, p.transport,
       p.pret_achizitie + p.transport                         AS cost_total,
       ROUND((p.pret_achizitie + p.transport) * (1 + :marja / 100.0), 0) AS pret_propus,
       ROUND(AVG(c.pret), 0)                                  AS media_concurenta,
       MIN(c.pret)                                            AS min_concurenta,
       MAX(c.pret)                                            AS max_concurenta,
       COUNT(c.pret)                                          AS nr_magazine
FROM piese p
LEFT JOIN preturi_concurenta c
       ON c.cod = p.cod AND c.magazin IN ({mag_ph})
WHERE p.categorie IN ({cat_ph}){where_marca}
GROUP BY p.cod
ORDER BY p.categorie, p.cod"""
    return sql, params


def decizie(con, categorii, magazine, marja, marci=None, marja_min=10.0, sub_piata=3.0):
    sql, params = sql_decizie(categorii, magazine, marci)
    params["marja"] = marja
    df = q(con, sql, params)
    # Recomandarea din foaia originală
    df["recomandare"] = np.where(df["pret_propus"] <= df["media_concurenta"], "Competitiv", "Prea scump")
    # Extensii: marja maximă care rămâne competitivă și prețul recomandat „aliniat la piață”
    df["marja_max_competitiva_%"] = ((df["media_concurenta"] / df["cost_total"] - 1) * 100).round(1)
    tinta = df["media_concurenta"] * (1 - sub_piata / 100)
    podea = df["cost_total"] * (1 + marja_min / 100)
    df["pret_recomandat"] = np.maximum(tinta, podea).apply(xround)
    df["marja_realizata_%"] = ((df["pret_recomandat"] / df["cost_total"] - 1) * 100).round(1)
    df["pozitie_piata"] = np.select(
        [df["pret_recomandat"] < df["min_concurenta"], df["pret_recomandat"] <= df["media_concurenta"],
         df["pret_recomandat"] <= df["max_concurenta"]],
        ["cel mai ieftin", "sub medie", "peste medie"], "cel mai scump")
    df["profit_unitar"] = df["pret_recomandat"] - df["cost_total"]
    return df, sql, params


def marja_pe_categorie(con, marja):
    """Prețul mediu actual pe categorie (C5:C8 din foaia Simulare)."""
    sql = """SELECT categorie,
       AVG(pret_achizitie + transport) AS cost_mediu,
       COUNT(*) AS nr_piese
FROM piese GROUP BY categorie"""
    df = q(con, sql)
    df["pret_actual"] = (df["cost_mediu"] * (1 + marja / 100)).apply(xround)
    return df.set_index("categorie"), sql


# =========================================================================== M2 – prognoza
def forecast_linear(y, x=None, x_new=None):
    """FORECAST(x_new, y, x) – regresie liniară simplă. Întoarce (prognoză, panta, interceptul, R²)."""
    y = np.asarray(y, float)
    x = np.arange(1, len(y) + 1, dtype=float) if x is None else np.asarray(x, float)
    x_new = len(y) + 1 if x_new is None else x_new
    b, a = np.polyfit(x, y, 1)
    yhat = a + b * x
    ss_res = ((y - yhat) ** 2).sum()
    ss_tot = ((y - y.mean()) ** 2).sum()
    r2 = 1 - ss_res / ss_tot if ss_tot else np.nan
    return a + b * np.asarray(x_new, float), b, a, r2


def prognoza(con, orizont=1, metoda="Trend liniar (FORECAST)"):
    sql = "SELECT nr, luna, categorie, bucati FROM vanzari_lunare ORDER BY categorie, nr"
    lun = q(con, sql)
    rows, detalii = [], []
    for cat, g in lun.groupby("categorie", sort=False):
        y = g["bucati"].to_numpy(float)
        n = len(y)
        xs = np.arange(n + 1, n + orizont + 1)
        f_lin, b, a, r2 = forecast_linear(y, x_new=xs)
        if metoda.startswith("Medie mobilă"):
            hist = list(y)
            f = []
            for _ in xs:
                f.append(np.mean(hist[-3:]))
                hist.append(f[-1])
            f = np.array(f)
        else:
            f = f_lin
        for k, (xx, v) in enumerate(zip(xs, f), 1):
            rows.append({"categorie": cat, "nr": int(xx), "pas": k, "prognoza": xround(v)})
        detalii.append({"categorie": cat, "panta_lunara": round(b, 2), "R2": round(r2, 3),
                        "luna_max": g.loc[g["bucati"].idxmax(), "luna"],
                        "luna_min": g.loc[g["bucati"].idxmin(), "luna"],
                        "total_12_luni": int(y.sum()),
                        "prognoza_luna_urm": xround(f[0])})
    det = pd.DataFrame(detalii)
    # Totalul se prognozează separat (ca G15 din foaie), nu ca sumă a prognozelor
    tot = lun.groupby("nr", as_index=False)["bucati"].sum()
    f_tot, b, a, r2 = forecast_linear(tot["bucati"], x_new=np.arange(13, 13 + orizont))
    luna_tot = lun.drop_duplicates("nr").set_index("nr")["luna"]
    det = pd.concat([det, pd.DataFrame([{
        "categorie": "Total", "panta_lunara": round(b, 2), "R2": round(r2, 3),
        "luna_max": luna_tot[tot.loc[tot["bucati"].idxmax(), "nr"]],
        "luna_min": luna_tot[tot.loc[tot["bucati"].idxmin(), "nr"]],
        "total_12_luni": int(tot["bucati"].sum()), "prognoza_luna_urm": xround(f_tot[0])}])], ignore_index=True)
    return lun, pd.DataFrame(rows), det, sql


# =========================================================================== M3 – simulare
def simulare(prognoze: dict, preturi: dict, costuri: dict, reactii: dict, modificare: float,
             elasticitate=ELASTICITATE):
    """Exact ca foaia Simulare (coloanele B–I), plus profitul (care ține cont de cost)."""
    rows = []
    for cat in prognoze:
        b = prognoze[cat]
        c = preturi[cat]
        coef = elasticitate[reactii[cat]]
        d = xround(b * (1 + coef * modificare / 100))
        e = b * c
        f = xround(d * c * (1 + modificare / 100))
        g = f - e
        profit_acum = b * (c - costuri[cat])
        profit_dupa = d * (c * (1 + modificare / 100) - costuri[cat])
        rows.append({"categorie": cat, "vanzari_estimate": b, "pret_actual": c,
                     "vanzari_dupa": d, "incasari_acum": e, "incasari_dupa": f, "castig_pierdere": g,
                     "reactie_clienti": reactii[cat],
                     "merita": f"DA, câștigi {g:,.0f} lei" if g > 0 else f"NU, pierzi {-g:,.0f} lei",
                     "profit_acum": round(profit_acum), "profit_dupa": round(profit_dupa),
                     "dif_profit": round(profit_dupa - profit_acum)})
    df = pd.DataFrame(rows)
    return df


def curba_simulare(prognoze, preturi, costuri, reactii, grid=range(-50, 51), elasticitate=ELASTICITATE):
    out = []
    for m in grid:
        s = simulare(prognoze, preturi, costuri, reactii, m, elasticitate)
        for _, r in s.iterrows():
            out.append({"modificare_%": m, "categorie": r["categorie"],
                        "dif_incasari": r["castig_pierdere"], "dif_profit": r["dif_profit"]})
    return pd.DataFrame(out)
