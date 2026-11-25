"""Starea comună a aplicației: sursa datelor, conexiunea SQLite, parametrii globali."""
from __future__ import annotations

import hashlib

import numpy as np
import pandas as pd
import streamlit as st

from core.db import CATEGORII, load_all, make_db, q
from core.models import (ELASTICITATE, REACTIE_IMPLICITA, curba_simulare, decizie, marja_pe_categorie, prognoza, simulare)

MODES = {"Copie locală (fișierele echipei)": "local", "Google Sheets (live)": "google",
         "Încarc fișierele mele": "upload"}


@st.cache_data(ttl=300, show_spinner="Încarc sursele de date…")
def _load(mode: str, upload_sig: str, _uploads):
    return load_all(mode, _uploads)


def get_con():
    mode = MODES[st.session_state.get("sursa", next(iter(MODES)))]
    ups = st.session_state.get("uploads", {}) or {}
    sig = hashlib.md5(b"".join(u.getvalue() for u in ups.values() if u is not None)).hexdigest()
    tables, log = _load(mode, sig, ups)
    return make_db(tables), tables, log


def params():
    s = st.session_state
    return {
        "marja": s.get("marja", 30),
        "magazine": s.get("magazine") or ["Magazin A", "Magazin B", "Magazin C"],
        "categorii": s.get("categorii_raport") or CATEGORII,
        "marja_min": s.get("marja_min", 10.0),
        "sub_piata": s.get("sub_piata", 3.0),
        "modificare": s.get("modificare", -10),
        "reactii": {c: s.get(f"reactie_{c}", REACTIE_IMPLICITA[c]) for c in CATEGORII},
        "orizont": s.get("orizont", 1),
        "metoda": s.get("metoda", "Trend liniar (FORECAST)"),
        "elast": s.get("elast", ELASTICITATE),
    }


def sursa_text(log):
    return "; ".join(sorted({x[1] for x in log}))


def build_context(con, tables, log, p=None):
    """Toate rezultatele pentru raport (aceleași calcule ca în pagini)."""
    p = p or params()
    dec, _, _ = decizie(con, p["categorii"], p["magazine"], p["marja"],
                        marja_min=p["marja_min"], sub_piata=p["sub_piata"])
    lun, fc, det, _ = prognoza(con, p["orizont"], p["metoda"])
    _, _, det1, _ = prognoza(con, 1)      # simularea folosește prognoza pe luna următoare (ca în foaie)
    pc, _ = marja_pe_categorie(con, p["marja"])
    cats = [c for c in CATEGORII if c in pc.index]
    dd = det.set_index("categorie")
    prog = {c: int(det1.set_index("categorie").loc[c, "prognoza_luna_urm"]) for c in cats}
    preturi = {c: float(pc.loc[c, "pret_actual"]) for c in cats}
    costuri = {c: float(pc.loc[c, "cost_mediu"]) for c in cats}
    sim = simulare(prog, preturi, costuri, p["reactii"], p["modificare"], p["elast"])
    curba = curba_simulare(prog, preturi, costuri, p["reactii"], elasticitate=p["elast"])
    tot = curba.groupby("modificare_%")[["dif_incasari", "dif_profit"]].sum()
    conc = q(con, "SELECT cod, magazin, pret FROM preturi_concurenta").pivot(index="cod", columns="magazin",
                                                                            values="pret").reset_index()
    return {**p, "sursa": sursa_text(log), "decizie": dec, "lunar": lun, "prognoza_fc": fc, "prognoza_det": det,
            "prognoza_total": float(dd.loc["Total", "prognoza_luna_urm"]), "simulare": sim, "curba": curba,
            "opt_incasari": int(tot["dif_incasari"].idxmax()), "opt_profit": int(tot["dif_profit"].idxmax()),
            "tari": tables["comenzi_tari"], "clienti": tables["clienti"], "concurenta": conc,
            "preturi_cat": pc}


def sql_box(sql, params_=None, title="Interogarea SQL"):
    if not st.session_state.get("arata_sql"):
        return
    with st.expander(f"🔎 {title}"):
        st.code(sql, language="sql")
        if params_:
            st.caption("Parametri: " + ", ".join(f":{k} = {v!r}" for k, v in params_.items()))


def fmt_lei(x):
    return f"{x:,.0f} lei".replace(",", ".") if pd.notna(x) and np.isfinite(x) else "–"
