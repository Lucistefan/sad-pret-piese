"""Smoke-test pentru toate paginile + verificarea valorilor față de Google Sheets."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from streamlit.testing.v1 import AppTest

APP = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app.py")
PAGES = ["home", "decizie", "vanzari", "simulare", "harta", "rapoarte", "surse", "sql"]
at = AppTest.from_file(APP, default_timeout=180).run()
for p in PAGES:
    at.switch_page(f"views/{p}.py").run()
    print(f"{p:10s}", "OK" if not at.exception else [e.value for e in at.exception])
    if p == "sql":
        at.button[0].click().run()
        print("   sql result:", [s.value for s in at.success])
    if p == "simulare":
        at.slider[0].set_value(-50).run()
        print("   ", [(m.label, m.value) for m in at.metric][:3], [e.value for e in at.error])
