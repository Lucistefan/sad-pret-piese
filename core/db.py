"""Stratul de date: cele 3 surse (Furnizor, Prețuri concurență, Vânzări) → bază SQLite în memorie.

Sursele pot veni din:
  * Google Sheets (live, prin export CSV – foile trebuie partajate „Anyone with the link – Viewer”)
  * copia locală din folderul data/ (implicit, funcționează mereu)
  * fișiere încărcate de utilizator (CSV / Excel)
"""
from __future__ import annotations

import io
import sqlite3
import urllib.request
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

SHEETS = {
    "furnizor": "1CpZYngCBbNRJZj_x1UPp-F3d-NsU-85Vcm0-hMKbfMU",
    "concurenta": "1pPuCsljHoQIieR_9ER9m0uv4AWsD4rtv-0T45NT1eyc",
    "vanzari": "1D9oOU-nZafO4ETfz7Z62pPF3F6CEww-iobJx82k2Kzc",
}
SOURCE_LABELS = {
    "furnizor": "Sursa 1 – Furnizor (prețuri de achiziție)",
    "concurenta": "Sursa 2 – Prețuri concurență",
    "vanzari": "Sursa 3 – Vânzări, țări, clienți",
}
CATEGORII = ["Frâne", "Filtre", "Suspensie", "Ambreiaj"]
# coloanele din foaia Vânzări sunt fără diacritice
CAT_VANZARI = {"Frane": "Frâne", "Filtre": "Filtre", "Suspensie": "Suspensie", "Ambreiaj": "Ambreiaj"}
ISO2_TO_ISO3 = {"FR": "FRA", "RO": "ROU", "BE": "BEL", "DE": "DEU", "IT": "ITA", "ES": "ESP", "NL": "NLD",
                "CH": "CHE", "PT": "PRT", "LU": "LUX", "AT": "AUT", "MD": "MDA", "PL": "POL", "HU": "HUN",
                "BG": "BGR", "GB": "GBR", "IE": "IRL", "CZ": "CZE", "SK": "SVK", "GR": "GRC", "HR": "HRV",
                "SI": "SVN", "RS": "SRB", "UA": "UKR", "DK": "DNK", "SE": "SWE", "NO": "NOR", "FI": "FIN"}


# --------------------------------------------------------------------------- citire surse
def sheet_csv_url(sheet_id: str) -> str:
    return f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"


def _read_bytes(b: bytes) -> pd.DataFrame:
    return pd.read_csv(io.BytesIO(b), dtype=str, keep_default_na=False)


def read_google(key: str, timeout=10) -> pd.DataFrame:
    req = urllib.request.Request(sheet_csv_url(SHEETS[key]), headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = r.read()
    if data.lstrip()[:15].lower().startswith(b"<!doctype html") or b"<html" in data[:200].lower():
        raise PermissionError("foaia nu este partajată public (Google cere autentificare)")
    return _read_bytes(data)


def read_local(key: str) -> pd.DataFrame:
    return pd.read_csv(DATA_DIR / f"{key}.csv", dtype=str, keep_default_na=False)


def read_upload(upload) -> pd.DataFrame:
    if upload.name.lower().endswith((".xlsx", ".xls")):
        return pd.read_excel(upload, dtype=str).fillna("")
    return _read_bytes(upload.getvalue())


# --------------------------------------------------------------------------- normalizare
def _num(s):
    return pd.to_numeric(pd.Series(s).astype(str).str.replace(",", ".").str.strip(), errors="coerce")


def norm_furnizor(raw: pd.DataFrame) -> pd.DataFrame:
    df = raw.iloc[:, :6].copy()
    df.columns = ["cod", "denumire", "categorie", "marca", "pret_achizitie", "transport"]
    df = df[df["cod"].str.strip() != ""]
    df["pret_achizitie"] = _num(df["pret_achizitie"]).values
    df["transport"] = _num(df["transport"]).values
    return df.dropna(subset=["pret_achizitie"]).reset_index(drop=True)


def norm_concurenta(raw: pd.DataFrame) -> pd.DataFrame:
    """Format lat (Cod, Magazin A, Magazin B, …) → format lung (cod, magazin, pret)."""
    df = raw.copy()
    df = df[df.iloc[:, 0].str.strip() != ""]
    df = df.rename(columns={df.columns[0]: "cod"})
    long = df.melt(id_vars="cod", var_name="magazin", value_name="pret")
    long["pret"] = _num(long["pret"]).values
    return long.dropna(subset=["pret"]).reset_index(drop=True)


def norm_vanzari(raw: pd.DataFrame):
    """Foaia Vânzări conține 3 tabele alăturate: lunar (A:G), țări (I:K), tipuri de clienți (M:O)."""
    cols = list(raw.columns)
    c = {name.strip(): i for i, name in enumerate(cols)}

    lun = raw.iloc[:, c["Nr"]: c["Nr"] + 7].copy()
    lun.columns = ["nr", "luna", "Frane", "Filtre", "Suspensie", "Ambreiaj", "total"]
    lun = lun[lun["nr"].str.strip() != ""]
    for k in ["nr", "Frane", "Filtre", "Suspensie", "Ambreiaj", "total"]:
        lun[k] = _num(lun[k]).values
    lunar = lun.melt(id_vars=["nr", "luna"], value_vars=list(CAT_VANZARI), var_name="cat", value_name="bucati")
    lunar["categorie"] = lunar["cat"].map(CAT_VANZARI)
    lunar = lunar.drop(columns="cat").sort_values(["categorie", "nr"]).reset_index(drop=True)

    i = c["Cod tara"]
    tari = raw.iloc[:, i:i + 3].copy()
    tari.columns = ["cod_tara", "tara", "comenzi"]
    tari = tari[tari["cod_tara"].str.strip() != ""]
    tari["comenzi"] = _num(tari["comenzi"]).values
    tari["iso3"] = tari["cod_tara"].str.upper().map(ISO2_TO_ISO3)

    j = c["Tip client"]
    cl = raw.iloc[:, j:j + 3].copy()
    cl.columns = ["tip_client", "comenzi", "valoare"]
    cl = cl[cl["tip_client"].str.strip() != ""]
    cl["comenzi"] = _num(cl["comenzi"]).values
    cl["valoare"] = _num(cl["valoare"]).values
    return lunar, tari.reset_index(drop=True), cl.reset_index(drop=True)


def load_all(mode: str, uploads: dict | None = None):
    """mode: 'local' | 'google' | 'upload'. Întoarce (tabele, jurnal de încărcare)."""
    raws, log = {}, []
    for key in SHEETS:
        try:
            if mode == "google":
                raws[key] = read_google(key)
                log.append((key, "Google Sheets (live)", "ok"))
            elif mode == "upload" and uploads and uploads.get(key) is not None:
                raws[key] = read_upload(uploads[key])
                log.append((key, f"fișier încărcat: {uploads[key].name}", "ok"))
            else:
                raws[key] = read_local(key)
                log.append((key, "copie locală (data/)", "ok"))
        except Exception as e:  # noqa: BLE001 – revenim la copia locală
            raws[key] = read_local(key)
            log.append((key, "copie locală (data/)", f"sursa aleasă a eșuat: {e}"))
    lunar, tari, clienti = norm_vanzari(raws["vanzari"])
    tables = {
        "piese": norm_furnizor(raws["furnizor"]),
        "preturi_concurenta": norm_concurenta(raws["concurenta"]),
        "vanzari_lunare": lunar,
        "comenzi_tari": tari,
        "clienti": clienti,
    }
    return tables, log


DDL = """
-- nomenclator: categoriile de piese
CREATE TABLE categorii (
    categorie       TEXT PRIMARY KEY
);
-- sursa 1: Furnizor
CREATE TABLE piese (
    cod             TEXT PRIMARY KEY,
    denumire        TEXT NOT NULL,
    categorie       TEXT NOT NULL REFERENCES categorii(categorie),
    marca           TEXT,
    pret_achizitie  REAL NOT NULL CHECK (pret_achizitie >= 0),
    transport       REAL NOT NULL DEFAULT 0
);
-- sursa 2: Prețuri concurență (o linie pentru fiecare piesă × magazin)
CREATE TABLE preturi_concurenta (
    cod             TEXT NOT NULL REFERENCES piese(cod),
    magazin         TEXT NOT NULL,
    pret            REAL NOT NULL CHECK (pret > 0),
    PRIMARY KEY (cod, magazin)
);
-- sursa 3: Vânzări (3 tabele)
CREATE TABLE vanzari_lunare (
    nr              INTEGER NOT NULL,
    luna            TEXT NOT NULL,
    categorie       TEXT NOT NULL REFERENCES categorii(categorie),
    bucati          INTEGER NOT NULL,
    PRIMARY KEY (nr, categorie)
);
CREATE TABLE comenzi_tari (
    cod_tara        TEXT PRIMARY KEY,
    tara            TEXT NOT NULL,
    iso3            TEXT,
    comenzi         INTEGER NOT NULL
);
CREATE TABLE clienti (
    tip_client      TEXT PRIMARY KEY,
    comenzi         INTEGER NOT NULL,
    valoare         REAL NOT NULL
);
CREATE INDEX ix_conc_cod ON preturi_concurenta(cod);
CREATE INDEX ix_piese_categorie ON piese(categorie);
-- vedere: costul total și media pieței pentru fiecare piesă
CREATE VIEW v_piese_piata AS
SELECT p.cod, p.denumire, p.categorie, p.marca,
       p.pret_achizitie + p.transport AS cost_total,
       ROUND(AVG(c.pret), 2) AS media_pietei,
       MIN(c.pret) AS pret_minim, MAX(c.pret) AS pret_maxim,
       COUNT(c.magazin) AS nr_magazine
FROM piese p LEFT JOIN preturi_concurenta c ON c.cod = p.cod
GROUP BY p.cod;
"""

# relațiile (pentru diagrama bazei de date)
RELATII = [("piese", "categorie", "categorii", "categorie", "N:1"),
           ("vanzari_lunare", "categorie", "categorii", "categorie", "N:1"),
           ("preturi_concurenta", "cod", "piese", "cod", "N:1")]


def make_db(tables: dict) -> sqlite3.Connection:
    """Creează baza SQLite cu chei primare, chei străine și constrângeri, apoi încarcă datele."""
    con = sqlite3.connect(":memory:", check_same_thread=False)
    con.executescript(DDL)
    cats = sorted(set(tables["piese"]["categorie"]) | set(tables["vanzari_lunare"]["categorie"]))
    con.executemany("INSERT INTO categorii VALUES (?)", [(c,) for c in cats])
    for name, df in tables.items():
        info = con.execute(f"PRAGMA table_info({name})").fetchall()
        cols = [r[1] for r in info]
        pk = [r[1] for r in info if r[5]]
        d = df.drop_duplicates(subset=pk)        # cheia primară nu permite dubluri
        d = d[[c for c in cols if c in d.columns]].astype(object).where(d.notna(), None)
        con.executemany(f"INSERT INTO {name} ({', '.join(d.columns)}) VALUES ({', '.join('?' * len(d.columns))})",
                        d.itertuples(index=False, name=None))
    con.commit()
    return con


def integritate(con) -> pd.DataFrame:
    """Rânduri care încalcă cheile străine (PRAGMA foreign_key_check)."""
    return pd.DataFrame(con.execute("PRAGMA foreign_key_check").fetchall(),
                        columns=["tabel", "rand", "tabel_parinte", "fk"])


def db_bytes(con) -> bytes:
    """Copia bazei ca fișier .db (se deschide cu DB Browser for SQLite)."""
    return con.serialize()


def q(con, sql: str, params=None) -> pd.DataFrame:
    return pd.read_sql_query(sql, con, params=params or {})


def schema(con) -> pd.DataFrame:
    rows = []
    for (t, tip) in con.execute("SELECT name, type FROM sqlite_master WHERE type IN ('table','view') "
                                "AND name NOT LIKE 'sqlite_%' ORDER BY type, name"):
        n = con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        rows.append({"obiect": t, "tip": "tabel" if tip == "table" else "vedere", "rânduri": n,
                     "coloane": ", ".join(r[1] for r in con.execute(f"PRAGMA table_info({t})"))})
    return pd.DataFrame(rows)


def coloane(con, tabel) -> pd.DataFrame:
    fks = {r[3]: f"→ {r[2]}.{r[4]}" for r in con.execute(f"PRAGMA foreign_key_list({tabel})")}
    rows = []
    for _, nume, tip, notnull, default, pk in con.execute(f"PRAGMA table_info({tabel})"):
        rows.append({"coloana": nume, "tip": tip or "—", "cheie": ("PK" if pk else "") + (" FK" if nume in fks else ""),
                     "referă": fks.get(nume, ""), "obligatoriu": bool(notnull or pk)})
    return pd.DataFrame(rows)
