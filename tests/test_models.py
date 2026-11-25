"""Verifică că modelele dau exact valorile din foaia «SAD - Aplicatie pret piese»."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.db import CATEGORII, load_all, make_db
from core.models import REACTIE_IMPLICITA, decizie, marja_pe_categorie, prognoza, simulare

t, _ = load_all("local")
con = make_db(t)

# Decizie, categoria Ambreiaj, marjă 30%, doar Magazin A (comportamentul efectiv al foii)
d, _, _ = decizie(con, ["Ambreiaj"], ["Magazin A"], 30)
assert d["pret_propus"].tolist() == [722, 208, 1333, 189, 111]
assert d["media_concurenta"].tolist() == [787, 239, 1233, 177, 124]
assert d["recomandare"].tolist() == ["Competitiv", "Competitiv", "Prea scump", "Prea scump", "Competitiv"]
# Prognoza (FORECAST)
_, _, det, _ = prognoza(con, 1)
dd = det.set_index("categorie")["prognoza_luna_urm"].to_dict()
assert dd == {"Ambreiaj": 12, "Filtre": 85, "Frâne": 60, "Suspensie": 34, "Total": 191}
# Simulare -50%
pc, _ = marja_pe_categorie(con, 30)
assert pc["pret_actual"].to_dict() == {"Ambreiaj": 512, "Filtre": 70, "Frâne": 136, "Suspensie": 213}
s = simulare({c: dd[c] for c in CATEGORII}, pc["pret_actual"].to_dict(), pc["cost_mediu"].to_dict(),
             REACTIE_IMPLICITA, -50)
assert s["castig_pierdere"].tolist() == [-1020, -735, -1810, -2304] and s["castig_pierdere"].sum() == -5869
print("Toate valorile coincid cu foaia Google Sheets.")
