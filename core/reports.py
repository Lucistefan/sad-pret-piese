"""Tema 2 – exporturi și rapoarte: Excel formatat (cu grafice native), raport PDF, hartă (cartodiagramă)."""
from __future__ import annotations

import io
import json
from datetime import datetime
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
from fpdf import FPDF  # noqa: E402
from matplotlib.collections import PatchCollection  # noqa: E402
from matplotlib.patches import Polygon  # noqa: E402
from openpyxl.chart import BarChart, LineChart, PieChart, Reference  # noqa: E402
from openpyxl.drawing.image import Image as XLImage  # noqa: E402
from openpyxl.formatting.rule import CellIsRule  # noqa: E402
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side  # noqa: E402
from openpyxl.utils import get_column_letter  # noqa: E402

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
BLUE = "#2563eb"
PALETTE = ["#2563eb", "#16a34a", "#d97706", "#dc2626", "#7c3aed"]
FONT_PATH = Path(matplotlib.get_data_path()) / "fonts" / "ttf"


# =========================================================================== hartă
def load_europe():
    return json.loads((DATA_DIR / "europa.geojson").read_text())


def map_png(tari: pd.DataFrame, value_col="comenzi", title="Comenzi pe țări", dpi=160) -> bytes:
    """Cartodiagramă: țările colorate după valoare + cercuri proporționale (fără dependențe GIS)."""
    geo = load_europe()
    vals = tari.set_index("iso3")[value_col].to_dict()
    vmax = max(vals.values()) if vals else 1
    cmap = plt.get_cmap("Blues")
    fig, ax = plt.subplots(figsize=(8, 6.2))
    patches, colors = [], []
    for f in geo["features"]:
        geom = f["geometry"]
        polys = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]
        v = vals.get(f["id"])
        col = cmap(0.25 + 0.75 * v / vmax) if v is not None else "#eef0f3"
        for poly in polys:
            patches.append(Polygon(poly[0], closed=True))
            colors.append(col)
    ax.add_collection(PatchCollection(patches, facecolor=colors, edgecolor="white", linewidths=0.5))
    # cercuri proporționale în centrul fiecărei țări
    for f in geo["features"]:
        if f["id"] not in vals:
            continue
        geom = f["geometry"]
        polys = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]
        ring = max((p[0] for p in polys), key=len)
        xs, ys = zip(*ring)
        cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
        if f["id"] == "FRA":
            cx, cy = 2.5, 46.6
        v = vals[f["id"]]
        ax.scatter(cx, cy, s=30 + 900 * v / vmax, color="#dc2626", alpha=0.55, edgecolor="white", zorder=3)
        ax.text(cx, cy, f"{int(v)}", ha="center", va="center", fontsize=7, color="white", weight="bold", zorder=4)
    ax.set_xlim(-11, 33)
    ax.set_ylim(35, 60)
    ax.set_aspect(1.4)
    ax.axis("off")
    ax.set_title(title, fontsize=13, weight="bold")
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=plt.Normalize(0, vmax))
    fig.colorbar(sm, ax=ax, shrink=0.6, label=value_col)
    return _fig_bytes(fig, dpi)


# =========================================================================== grafice pentru PDF
def _fig_bytes(fig, dpi=160) -> bytes:
    buf = io.BytesIO()
    fig.tight_layout()
    fig.savefig(buf, format="png", dpi=dpi)
    plt.close(fig)
    return buf.getvalue()


def chart_decizie(dec: pd.DataFrame) -> bytes:
    fig, ax = plt.subplots(figsize=(8, 3.4))
    x = range(len(dec))
    ax.vlines(x, dec["min_concurenta"], dec["max_concurenta"], color="#94a3b8", lw=6, alpha=0.5,
              label="interval concurență (min–max)")
    ax.scatter(x, dec["cost_total"], marker="_", s=400, color="black", label="cost total", zorder=3)
    ax.scatter(x, dec["media_concurenta"], color="#64748b", label="media concurenței", zorder=3)
    ax.scatter(x, dec["pret_propus"], color=BLUE, marker="D", label="preț propus (cost + marjă)", zorder=4)
    ax.scatter(x, dec["pret_recomandat"], color="#16a34a", marker="*", s=120, label="preț recomandat", zorder=5)
    ax.set_xticks(list(x), dec["cod"], rotation=45, ha="right", fontsize=8)
    ax.set_ylabel("lei")
    ax.legend(fontsize=7, ncol=3, loc="upper left")
    ax.grid(axis="y", alpha=0.3)
    ax.set_title("Prețul propus față de piață", weight="bold")
    return _fig_bytes(fig)


def chart_vanzari(lun: pd.DataFrame, fc: pd.DataFrame) -> bytes:
    fig, ax = plt.subplots(figsize=(8, 3.6))
    for i, (cat, g) in enumerate(lun.groupby("categorie")):
        ax.plot(g["nr"], g["bucati"], marker="o", color=PALETTE[i], label=cat)
        f = fc[fc["categorie"] == cat]
        ax.plot([g["nr"].iloc[-1]] + list(f["nr"]), [g["bucati"].iloc[-1]] + list(f["prognoza"]),
                ls="--", color=PALETTE[i])
    luni = lun.drop_duplicates("nr").sort_values("nr")
    ticks = list(luni["nr"]) + list(sorted(fc["nr"].unique()))
    labels = [x[:3] for x in luni["luna"]] + [f"P{k}" for k in range(1, len(ticks) - len(luni) + 1)]
    ax.set_xticks(ticks, labels, fontsize=8)
    ax.set_ylabel("bucăți")
    ax.legend(fontsize=8, ncol=4)
    ax.grid(alpha=0.3)
    ax.set_title("Vânzări lunare și prognoză (linie punctată)", weight="bold")
    return _fig_bytes(fig)


def chart_simulare(curba: pd.DataFrame, modificare: float) -> bytes:
    fig, axs = plt.subplots(1, 2, figsize=(8, 3.3), sharex=True)
    tot = curba.groupby("modificare_%", as_index=False)[["dif_incasari", "dif_profit"]].sum()
    for ax, col, t in [(axs[0], "dif_incasari", "Diferență încasări (lei)"),
                       (axs[1], "dif_profit", "Diferență profit (lei)")]:
        for i, (cat, g) in enumerate(curba.groupby("categorie")):
            ax.plot(g["modificare_%"], g[col], color=PALETTE[i], lw=1, label=cat)
        ax.plot(tot["modificare_%"], tot[col], color="black", lw=2.5, label="Total")
        ax.axhline(0, color="grey", lw=0.8)
        ax.axvline(modificare, color="#dc2626", ls=":", lw=1.2)
        ax.set_title(t, fontsize=10, weight="bold")
        ax.set_xlabel("modificare preț (%)")
        ax.grid(alpha=0.3)
    axs[0].legend(fontsize=7)
    return _fig_bytes(fig)


def chart_clienti(cl: pd.DataFrame) -> bytes:
    fig, ax = plt.subplots(figsize=(8, 2.6))
    ax.barh(cl["tip_client"], cl["valoare"], color=PALETTE[:len(cl)])
    for i, v in enumerate(cl["valoare"]):
        ax.text(v, i, f" {v:,.0f} lei", va="center", fontsize=8)
    ax.set_title("Valoarea comenzilor pe tip de client", weight="bold")
    ax.set_xlim(0, cl["valoare"].max() * 1.25)
    return _fig_bytes(fig)


# =========================================================================== PDF
class Raport(FPDF):
    def __init__(self, titlu):
        super().__init__(format="A4")
        self.titlu = titlu
        self.add_font("DejaVu", "", str(FONT_PATH / "DejaVuSans.ttf"))
        self.add_font("DejaVu", "B", str(FONT_PATH / "DejaVuSans-Bold.ttf"))
        self.set_auto_page_break(True, margin=15)

    def header(self):
        self.set_font("DejaVu", "B", 9)
        self.set_text_color(100, 116, 139)
        self.cell(0, 6, self.titlu, align="L")
        self.cell(0, 6, datetime.now().strftime("%d.%m.%Y %H:%M"), align="R", new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(37, 99, 235)
        self.line(10, 17, 200, 17)
        self.ln(4)
        self.set_text_color(0, 0, 0)

    def footer(self):
        self.set_y(-12)
        self.set_font("DejaVu", "", 8)
        self.set_text_color(120, 120, 120)
        self.cell(0, 8, f"Pagina {self.page_no()}/{{nb}}", align="C")

    def h1(self, t):
        self.set_font("DejaVu", "B", 15)
        self.cell(0, 9, t, new_x="LMARGIN", new_y="NEXT")

    def h2(self, t):
        self.ln(2)
        self.set_font("DejaVu", "B", 11.5)
        self.set_text_color(37, 99, 235)
        self.cell(0, 7, t, new_x="LMARGIN", new_y="NEXT")
        self.set_text_color(0, 0, 0)

    def p(self, t, size=10):
        self.set_font("DejaVu", "", size)
        self.multi_cell(0, 5.2, t, new_x="LMARGIN", new_y="NEXT")

    def kpis(self, items):
        w = 190 / len(items)
        y = self.get_y()
        for i, (label, val) in enumerate(items):
            x = 10 + i * w
            self.set_fill_color(239, 246, 255)
            self.rect(x + 1, y, w - 2, 16, style="F")
            self.set_xy(x + 2, y + 1.5)
            self.set_font("DejaVu", "", 7.5)
            self.cell(w - 4, 4, label)
            self.set_xy(x + 2, y + 6.5)
            self.set_font("DejaVu", "B", 12)
            self.cell(w - 4, 7, str(val))
        self.set_y(y + 19)

    def table(self, df: pd.DataFrame, widths=None, size=8, highlight=None):
        cols = list(df.columns)
        widths = widths or [190 / len(cols)] * len(cols)
        self.set_font("DejaVu", "B", size)
        self.set_fill_color(37, 99, 235)
        self.set_text_color(255, 255, 255)
        for c, w in zip(cols, widths):
            self.cell(w, 6, str(c), border=0, fill=True, align="C")
        self.ln()
        self.set_text_color(0, 0, 0)
        self.set_font("DejaVu", "", size)
        for i, (_, row) in enumerate(df.iterrows()):
            fill = i % 2 == 1
            self.set_fill_color(245, 247, 250)
            if highlight:
                col = highlight(row)
                if col:
                    self.set_fill_color(*col)
                    fill = True
            for c, w in zip(cols, widths):
                v = row[c]
                if isinstance(v, (int, float)) and not isinstance(v, bool) and pd.notna(v):
                    txt = f"{v:,.0f}" if float(v).is_integer() or abs(v) >= 100 else f"{v:,.2f}"
                else:
                    txt = str(v)
                self.cell(w, 5.5, txt, fill=fill, align="R" if isinstance(v, (int, float)) else "L")
            self.ln()

    def image_bytes(self, b, w=190):
        self.image(io.BytesIO(b), w=w)


def raport_pdf(ctx: dict) -> bytes:
    """ctx: parametri și rezultate (vezi pagina Rapoarte)."""
    pdf = Raport("SAD – stabilirea prețului de vânzare pentru piese auto")
    pdf.alias_nb_pages()
    pdf.add_page()
    pdf.h1("Raport de decizie – prețuri piese auto")
    pdf.p(f"Categorii analizate: {', '.join(ctx['categorii'])}. Marja dorită: {ctx['marja']}%. "
          f"Magazine concurente: {', '.join(ctx['magazine'])}. Sursa datelor: {ctx['sursa']}.", 9)
    dec = ctx["decizie"]
    n_comp = int((dec["recomandare"] == "Competitiv").sum())
    pdf.ln(2)
    pdf.kpis([("Piese analizate", len(dec)), ("Competitive la marja dorită", f"{n_comp}/{len(dec)}"),
              ("Marja medie realizată", f"{dec['marja_realizata_%'].mean():.1f}%"),
              ("Prognoză luna urm. (buc)", int(ctx["prognoza_total"]))])

    pdf.h2("1. Model 1 – prețul de vânzare (cost + marjă vs. concurență)")
    t = dec[["cod", "denumire", "cost_total", "pret_propus", "media_concurenta", "recomandare",
             "pret_recomandat", "marja_realizata_%"]].rename(columns={
                 "cod": "Cod", "denumire": "Denumire", "cost_total": "Cost", "pret_propus": "Propus",
                 "media_concurenta": "Media conc.", "recomandare": "Verdict", "pret_recomandat": "Recomandat",
                 "marja_realizata_%": "Marjă %"})
    pdf.table(t, widths=[17, 45, 17, 18, 22, 25, 25, 21], size=7.5,
              highlight=lambda r: (254, 226, 226) if r["Verdict"] == "Prea scump" else None)
    pdf.ln(1)
    pdf.p("Prețul recomandat = maximul dintre (media concurenței − "
          f"{ctx['sub_piata']}%) și (cost × (1 + {ctx['marja_min']}% marjă minimă)).", 8)
    img = chart_decizie(dec)
    if pdf.h - 15 - pdf.get_y() < 75:
        pdf.add_page()
    pdf.image_bytes(img, w=min(190, (pdf.h - 17 - pdf.get_y()) * 8 / 3.4))

    pdf.add_page()
    pdf.h2("2. Model 2 – prognoza vânzărilor (trend liniar, FORECAST)")
    det = ctx["prognoza_det"][["categorie", "total_12_luni", "prognoza_luna_urm", "panta_lunara", "R2",
                               "luna_max", "luna_min"]].rename(columns={
        "categorie": "Categorie", "total_12_luni": "Total 12 luni", "prognoza_luna_urm": "Prognoză",
        "panta_lunara": "Trend/lună", "R2": "R²", "luna_max": "Luna max", "luna_min": "Luna min"})
    pdf.table(det, widths=[30, 26, 24, 24, 18, 34, 34], size=8)
    pdf.ln(2)
    pdf.image_bytes(chart_vanzari(ctx["lunar"], ctx["prognoza_fc"]))
    pdf.image_bytes(chart_clienti(ctx["clienti"]), w=170)
    best = ctx["clienti"].loc[ctx["clienti"]["valoare"].idxmax(), "tip_client"]
    pdf.p(f"Cel mai valoros tip de client: {best}.", 9)

    pdf.add_page()
    pdf.h2(f"3. Model 3 – simulare: modificare de preț cu {ctx['modificare']:+g}%")
    sim = ctx["simulare"]
    t = sim[["categorie", "vanzari_estimate", "vanzari_dupa", "pret_actual", "incasari_acum", "incasari_dupa",
             "castig_pierdere", "dif_profit"]].rename(columns={
        "categorie": "Categorie", "vanzari_estimate": "Buc. acum", "vanzari_dupa": "Buc. după",
        "pret_actual": "Preț", "incasari_acum": "Încasări acum", "incasari_dupa": "Încasări după",
        "castig_pierdere": "Δ încasări", "dif_profit": "Δ profit"})
    pdf.table(t, widths=[26, 20, 20, 18, 27, 27, 26, 26], size=8,
              highlight=lambda r: (220, 252, 231) if r["Δ încasări"] > 0 else (254, 226, 226))
    tot = sim["castig_pierdere"].sum()
    prof = sim["dif_profit"].sum()
    pdf.ln(1)
    pdf.p(("Concluzie: MERITĂ. " if prof > 0 else "Concluzie: NU merită. ")
          + f"Profitul se modifică cu {prof:+,.0f} lei, iar încasările cu {tot:+,.0f} lei.", 9.5)
    pdf.image_bytes(chart_simulare(ctx["curba"], ctx["modificare"]))
    pdf.p(f"Modificarea care maximizează încasările totale: {ctx['opt_incasari']:+d}%. "
          f"Modificarea care maximizează profitul total: {ctx['opt_profit']:+d}%.", 9)

    pdf.add_page()
    pdf.h2("4. Cartodiagramă – comenzi pe țări")
    pdf.image_bytes(map_png(ctx["tari"]), w=175)
    tari = ctx["tari"].sort_values("comenzi", ascending=False)[["tara", "cod_tara", "comenzi"]]
    tari["pondere_%"] = (tari["comenzi"] / tari["comenzi"].sum() * 100).round(1)
    pdf.table(tari.rename(columns={"tara": "Țara", "cod_tara": "Cod", "comenzi": "Comenzi", "pondere_%": "Pondere %"}),
              widths=[60, 30, 40, 40], size=8)
    return bytes(pdf.output())


# =========================================================================== Excel
HEADER_FILL = PatternFill("solid", fgColor="2563EB")
THIN = Side(style="thin", color="D0D7E2")


def reguli_excel(ws, df, reguli: dict):
    """Formatare condiționată în Excel: culori pe intensitate + iconițe (✓ ! ✗, săgeți).

    reguli = {coloana: "bun_mare" | "bun_mic" | "intensitate" | "trend"}
    """
    from openpyxl.formatting.rule import ColorScaleRule, IconSetRule

    n = len(df) + 1
    for col, tip in reguli.items():
        if col not in df.columns or n < 2:
            continue
        L = get_column_letter(list(df.columns).index(col) + 1)
        rng = f"{L}2:{L}{n}"
        if tip in ("bun_mare", "bun_mic", "trend"):
            rosu, verde = "F8696B", "63BE7B"
            jos, sus = (rosu, verde) if tip != "bun_mic" else (verde, rosu)
            ws.conditional_formatting.add(rng, ColorScaleRule(start_type="min", start_color=jos, mid_type="num",
                                                              mid_value=0, mid_color="FFFFFF", end_type="max",
                                                              end_color=sus))
            stil = "3Arrows" if tip == "trend" else "3Symbols"
            ws.conditional_formatting.add(rng, IconSetRule(stil, "num", [0, 0, 1e-9], reverse=(tip == "bun_mic")))
        elif tip == "intensitate":
            ws.conditional_formatting.add(rng, ColorScaleRule(start_type="min", start_color="F1F5FE",
                                                              end_type="max", end_color="5B8FF9"))


def _format_sheet(ws, df, money_cols=(), pct_cols=()):
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = HEADER_FILL
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    ws.row_dimensions[1].height = 30
    ws.freeze_panes = "A2"
    ws.page_setup.orientation = "landscape"          # la tipărire: o pagină pe lățime
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.page_setup.fitToWidth, ws.page_setup.fitToHeight = 1, 0
    for i, col in enumerate(df.columns, 1):
        width = max(len(str(col)), *(len(str(v)) for v in df[col].head(200))) + 2
        ws.column_dimensions[get_column_letter(i)].width = min(max(width, 9), 40)
        for row in ws.iter_rows(min_row=2, min_col=i, max_col=i):
            for c in row:
                c.border = Border(bottom=THIN)
                if col in money_cols:
                    c.number_format = '#,##0 "lei"'
                elif col in pct_cols:
                    c.number_format = '0.0"%"'
    ws.auto_filter.ref = ws.dimensions


def raport_excel(ctx: dict) -> bytes:
    buf = io.BytesIO()
    dec = ctx["decizie"].drop(columns=["nr_magazine"], errors="ignore")
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        # Parametri
        pd.DataFrame({"Parametru": ["Data raportului", "Sursa datelor", "Categorii", "Magazine concurente",
                                    "Marja dorită (%)", "Marja minimă (%)", "Sub media pieței (%)",
                                    "Modificare preț simulată (%)"],
                      "Valoare": [datetime.now().strftime("%d.%m.%Y %H:%M"), ctx["sursa"], ", ".join(ctx["categorii"]),
                                  ", ".join(ctx["magazine"]), ctx["marja"], ctx["marja_min"], ctx["sub_piata"],
                                  ctx["modificare"]]}).to_excel(w, sheet_name="Parametri", index=False)
        dec.to_excel(w, sheet_name="Decizie pret", index=False)
        ctx["concurenta"].to_excel(w, sheet_name="Preturi concurenta", index=False)
        lun = ctx["lunar"].pivot_table(index=["nr", "luna"], columns="categorie", values="bucati").reset_index()
        lun.to_excel(w, sheet_name="Vanzari lunare", index=False)
        ctx["prognoza_det"].to_excel(w, sheet_name="Prognoza", index=False)
        ctx["simulare"].to_excel(w, sheet_name="Simulare", index=False)
        curba_w = ctx["curba"].pivot_table(index="modificare_%", columns="categorie", values="dif_incasari").reset_index()
        curba_w.to_excel(w, sheet_name="Curba simulare", index=False)
        ctx["tari"].to_excel(w, sheet_name="Comenzi pe tari", index=False)
        ctx["clienti"].to_excel(w, sheet_name="Clienti", index=False)

        wb = w.book
        _format_sheet(wb["Parametri"], pd.DataFrame(columns=["Parametru", "Valoare"], data=[["x" * 28, "y" * 40]]))
        _format_sheet(wb["Decizie pret"], dec,
                      money_cols={"pret_achizitie", "transport", "cost_total", "pret_propus", "media_concurenta",
                                  "min_concurenta", "max_concurenta", "pret_recomandat", "profit_unitar"},
                      pct_cols={"marja_max_competitiva_%", "marja_realizata_%"})
        ws = wb["Decizie pret"]
        col_rec = get_column_letter(list(dec.columns).index("recomandare") + 1)
        rng = f"{col_rec}2:{col_rec}{len(dec) + 1}"
        ws.conditional_formatting.add(rng, CellIsRule(operator="equal", formula=['"Prea scump"'],
                                                      fill=PatternFill("solid", fgColor="FEE2E2")))
        ws.conditional_formatting.add(rng, CellIsRule(operator="equal", formula=['"Competitiv"'],
                                                      fill=PatternFill("solid", fgColor="DCFCE7")))
        ch = BarChart()
        ch.title, ch.y_axis.title, ch.height, ch.width = "Preț propus vs media concurenței", "lei", 8, 18
        cols = list(dec.columns)
        for name in ["cost_total", "pret_propus", "media_concurenta", "pret_recomandat"]:
            k = cols.index(name) + 1
            ch.add_data(Reference(ws, min_col=k, min_row=1, max_row=len(dec) + 1), titles_from_data=True)
        ch.set_categories(Reference(ws, min_col=1, min_row=2, max_row=len(dec) + 1))
        ws.add_chart(ch, f"A{len(dec) + 4}")

        simple = {"Preturi concurenta": ctx["concurenta"], "Prognoza": ctx["prognoza_det"],
                  "Comenzi pe tari": ctx["tari"], "Clienti": ctx["clienti"], "Curba simulare": curba_w}
        for name, frame in simple.items():
            _format_sheet(wb[name], frame, money_cols={"pret", "valoare"})
        _format_sheet(wb["Vanzari lunare"], lun)
        reguli_excel(wb["Decizie pret"], dec, {"marja_max_competitiva_%": "bun_mare", "marja_realizata_%": "intensitate",
                                               "profit_unitar": "intensitate"})
        reguli_excel(wb["Prognoza"], ctx["prognoza_det"], {"panta_lunara": "trend", "R2": "intensitate",
                                                          "prognoza_luna_urm": "intensitate"})
        reguli_excel(wb["Curba simulare"], curba_w, {c: "bun_mare" for c in curba_w.columns[1:]})
        reguli_excel(wb["Comenzi pe tari"], ctx["tari"], {"comenzi": "intensitate", "pondere_pct": "intensitate"})
        reguli_excel(wb["Clienti"], ctx["clienti"], {"valoare": "intensitate", "comenzi": "intensitate"})
        ws = wb["Vanzari lunare"]
        reguli_excel(ws, lun, {c: "intensitate" for c in lun.columns[2:]})
        lc = LineChart()
        lc.title, lc.y_axis.title, lc.height, lc.width = "Vânzări lunare (bucăți)", "buc", 8, 18
        lc.add_data(Reference(ws, min_col=3, max_col=2 + lun.shape[1] - 2, min_row=1, max_row=len(lun) + 1),
                    titles_from_data=True)
        lc.set_categories(Reference(ws, min_col=2, min_row=2, max_row=len(lun) + 1))
        ws.add_chart(lc, "H2")

        sim = ctx["simulare"]
        _format_sheet(wb["Simulare"], sim, money_cols={"pret_actual", "incasari_acum", "incasari_dupa",
                                                       "castig_pierdere", "profit_acum", "profit_dupa", "dif_profit"})
        ws = wb["Simulare"]
        reguli_excel(ws, sim, {"castig_pierdere": "bun_mare", "dif_profit": "bun_mare"})
        r = len(sim) + 2
        ws.cell(r, 1, "TOTAL").font = Font(bold=True)
        for name in ["incasari_acum", "incasari_dupa", "castig_pierdere", "profit_acum", "profit_dupa", "dif_profit"]:
            k = list(sim.columns).index(name) + 1
            L = get_column_letter(k)
            c = ws.cell(r, k, f"=SUM({L}2:{L}{r - 1})")   # formulă Excel reală, nu valoare
            c.font, c.number_format = Font(bold=True), '#,##0 "lei"'
        bc = BarChart()
        bc.title, bc.height, bc.width = "Diferența de încasări și de profit", 8, 18
        for name in ["castig_pierdere", "dif_profit"]:
            k = list(sim.columns).index(name) + 1
            bc.add_data(Reference(ws, min_col=k, min_row=1, max_row=len(sim) + 1), titles_from_data=True)
        bc.set_categories(Reference(ws, min_col=1, min_row=2, max_row=len(sim) + 1))
        ws.add_chart(bc, f"A{r + 3}")

        ws = wb["Comenzi pe tari"]
        bc = BarChart()
        bc.type, bc.title, bc.height, bc.width = "bar", "Comenzi pe țări", 9, 14
        k = list(ctx["tari"].columns).index("comenzi") + 1
        bc.add_data(Reference(ws, min_col=k, min_row=1, max_row=len(ctx["tari"]) + 1), titles_from_data=True)
        bc.set_categories(Reference(ws, min_col=2, min_row=2, max_row=len(ctx["tari"]) + 1))
        ws.add_chart(bc, "G2")
        pic = XLImage(io.BytesIO(map_png(ctx["tari"])))       # harta (cartodiagrama) ca imagine
        pic.width, pic.height = pic.width * 0.5, pic.height * 0.5
        ws.add_image(pic, "G22")

        ws = wb["Prognoza"]
        det = ctx["prognoza_det"]
        n = len(det) - 1 if det["categorie"].iloc[-1] == "Total" else len(det)
        bc = BarChart()
        bc.title, bc.y_axis.title, bc.height, bc.width = "Prognoza pe luna următoare", "buc", 8, 16
        k = list(det.columns).index("prognoza_luna_urm") + 1
        bc.add_data(Reference(ws, min_col=k, min_row=1, max_row=n + 1), titles_from_data=True)
        bc.set_categories(Reference(ws, min_col=1, min_row=2, max_row=n + 1))
        ws.add_chart(bc, f"A{len(det) + 4}")

        ws = wb["Clienti"]
        cl = ctx["clienti"]
        pc = PieChart()
        pc.title, pc.height, pc.width = "Valoarea comenzilor pe tip de client", 8, 12
        k = list(cl.columns).index("valoare") + 1
        pc.add_data(Reference(ws, min_col=k, min_row=1, max_row=len(cl) + 1), titles_from_data=True)
        pc.set_categories(Reference(ws, min_col=1, min_row=2, max_row=len(cl) + 1))
        ws.add_chart(pc, "F2")

        ws = wb["Curba simulare"]
        lc = LineChart()
        lc.title, lc.y_axis.title, lc.x_axis.title = "Diferența de încasări după modificarea prețului", "lei", "modificare %"
        lc.height, lc.width = 9, 18
        lc.add_data(Reference(ws, min_col=2, max_col=curba_w.shape[1], min_row=1, max_row=len(curba_w) + 1),
                    titles_from_data=True)
        lc.set_categories(Reference(ws, min_col=1, min_row=2, max_row=len(curba_w) + 1))
        ws.add_chart(lc, f"{get_column_letter(curba_w.shape[1] + 2)}2")
    return buf.getvalue()


# =========================================================================== hartă interactivă (plotly, offline)
def _centroid(feature):
    g = feature["geometry"]
    polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
    ring = max((p[0] for p in polys), key=len)
    xs, ys = zip(*ring)
    if feature["id"] == "FRA":
        return 2.5, 46.6
    return (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2


def map_plotly(tari: pd.DataFrame, value_col="comenzi", choropleth=True, bubbles=True):
    """Cartodiagramă interactivă desenată din contururi (nu are nevoie de servicii de hărți/CDN)."""
    import plotly.graph_objects as go
    from plotly.colors import sample_colorscale

    geo = load_europe()
    vals = tari.set_index("iso3")[value_col].to_dict()
    names = tari.set_index("iso3")["tara"].to_dict()
    vmax = max(vals.values()) if vals else 1
    fig = go.Figure()
    for f in geo["features"]:
        g = f["geometry"]
        polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
        v = vals.get(f["id"])
        col = sample_colorscale("Blues", 0.2 + 0.8 * v / vmax)[0] if (v is not None and choropleth) else "#eef0f3"
        hover = f"{names.get(f['id'], f['properties']['name'])}: {int(v)} comenzi" if v is not None \
            else f["properties"]["name"]
        for poly in polys:
            xs, ys = zip(*poly[0])
            fig.add_scatter(x=xs, y=ys, fill="toself", fillcolor=col, mode="lines",
                            line=dict(color="white", width=0.8), hoverinfo="text", text=hover, showlegend=False)
    if choropleth:   # bara de culori
        fig.add_scatter(x=[None], y=[None], mode="markers", showlegend=False, hoverinfo="skip",
                        marker=dict(colorscale="Blues", cmin=0, cmax=vmax, color=[0], showscale=True,
                                    colorbar=dict(title=value_col, thickness=14)))
    if bubbles:
        pts = [(f["id"], *_centroid(f)) for f in geo["features"] if f["id"] in vals]
        fig.add_scatter(x=[p[1] for p in pts], y=[p[2] for p in pts], mode="markers+text",
                        text=[str(int(vals[p[0]])) for p in pts], textfont=dict(color="white", size=10),
                        hovertext=[f"{names[p[0]]}: {int(vals[p[0]])} comenzi" for p in pts], hoverinfo="text",
                        marker=dict(size=[12 + 45 * vals[p[0]] / vmax for p in pts], color="rgba(220,38,38,0.65)",
                                    line=dict(color="white", width=1)), showlegend=False)
    fig.update_xaxes(range=[-11, 33], visible=False)
    fig.update_yaxes(range=[35, 60], visible=False, scaleanchor="x", scaleratio=1.4)
    fig.update_layout(plot_bgcolor="#f8fbff", height=620, margin=dict(l=0, r=0, t=40, b=0),
                      title="Comenzi pe țări", hoverlabel=dict(bgcolor="white"))
    return fig
