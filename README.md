# SAD – stabilirea prețului de vânzare pentru piese auto (Streamlit)

Varianta în Python a prototipului făcut în Google Sheets („SAD - Aplicatie pret piese”), cu aceleași surse
de date și formule, plus extensii și exporturile cerute la Tema 2.

## Ce face

| Pagină | Ce conține |
|---|---|
| Preț de vânzare | cost + marjă vs. media concurenței (foaia Decizie), preț recomandat cu marjă minimă, marja maximă competitivă, filtre pe categorie / marcă / magazine, **SQL dinamic** afișat |
| Vânzări și prognoză | FORECAST (trend liniar) sau medie mobilă, orizont 1–6 luni, R², luni max/min, tipuri de clienți |
| Simulare preț | aceeași elasticitate ca în foaia Simulare (Mult / Mediu / Puțin), plus efectul asupra **profitului** și modificarea optimă |
| Hartă comenzi | cartodiagramă (choropleth + cercuri proporționale), export PNG și HTML |
| Exporturi Excel / PDF | Excel cu 9 foi formatate și 4 grafice native, raport PDF de 4 pagini, CSV |
| Surse de date | copie locală / Google Sheets live / fișiere încărcate → bază SQLite |
| Interogări SQL | consolă SELECT + exemple |

Rezultatele sunt identice cu foaia Google (`python tests/test_models.py`): prețuri propuse 722 / 208 / 1333 / 189 / 111,
prognoză 60 / 85 / 34 / 12 / 191, simulare −50% → −5869 lei.

**Diferență intenționată:** în foaia Decizie, `AVERAGE(VLOOKUP(...;{2,3,4};0))` fără ARRAYFORMULA întoarce doar
prețul de la Magazin A. Aplicația calculează media reală a magazinelor bifate. Dacă bifezi doar Magazin A, obții
exact valorile din foaie.

## Cerințe acoperite (fișa disciplinei SAD, până la Tema 2)

| Cerință | Unde în aplicație |
|---|---|
| Grafice și grid-uri | toate paginile (Plotly + tabele interactive) |
| Cel puțin 2 surse de date | 3 surse: Furnizor, Prețuri concurență, Vânzări; citite din Google Sheets (live), din fișierele locale sau din fișiere încărcate (CSV/Excel), apoi încărcate în SQLite |
| Cel puțin 2 modele decizionale | 3 modele: preț cost + marjă vs. piață; prognoză (trend liniar / medie mobilă); simulare cu elasticitate |
| Interogări SQL dinamice | construite din controale (categorie, marcă, magazine, marjă, minim comenzi); vizibile cu comutatorul „Arată interogările SQL”; consolă SQL |
| Controale care modifică conținutul | filtre, slidere, selecții în fiecare pagină; setările din bara laterală se aplică peste tot |
| **Tema 2 – export .xlsx** | raport Excel cu 9 foi, formatare condiționată, formule și grafice; export Excel pe fiecare pagină |
| **Tema 2 – export .pdf** | raport PDF de 4 pagini cu tabele, grafice, concluzii și hartă |
| **Tema 2 – cartodiagrame / hărți** | pagina Hartă comenzi (choropleth + cercuri proporționale), export PNG / HTML, hartă inclusă în PDF |

## Rulare locală
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Google Sheets live
În bara laterală alegi „Google Sheets (live)”. Cele 3 foi (Furnizor, Prețuri concurență, Vânzări) trebuie partajate
*Anyone with the link → Viewer*. Altfel aplicația folosește automat copia din `data/`.

## Publicare gratuită (Streamlit Community Cloud)
1. Urcă folderul într-un repository GitHub.
2. https://share.streamlit.io → **Create app** → alegi repository-ul și fișierul `app.py` → **Deploy**.

## Structură
```
app.py            navigare + parametri globali (bara laterală)
core/db.py        citirea surselor, normalizare, SQLite
core/models.py    cele 3 modele decizionale
core/reports.py   export Excel, raport PDF, hărți
core/state.py     stare comună, context pentru rapoarte
views/*.py        paginile aplicației
data/             copia surselor (CSV) + contururile țărilor (GeoJSON)
tests/            verificări față de foaia Google
```
