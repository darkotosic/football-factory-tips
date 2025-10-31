# src/generate.py
import json, os
from datetime import datetime, timezone
from .builders import safe_dc, btts, ou, mw_value, single_analysis
from . import compose
from .util import today_iso

PUBLIC_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "public")
os.makedirs(PUBLIC_DIR, exist_ok=True)

def _write(name: str, data):
    fp = os.path.join(PUBLIC_DIR, name)
    with open(fp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def run(date: str = None):
    date = date or today_iso()

    dc_legs = safe_dc.build(date)
    btts_legs = btts.build(date)
    ou_legs = ou.build(date)
    mw_legs = mw_value.build(date)

    # AI deo ne sme da sruši jutarnji run
    try:
        ana_legs = single_analysis.build(date)
    except Exception as e:
        ana_legs = [{"error": f"single_analysis_failed: {e}"}]

    t2 = compose.make_ticket("2plus", compose.pick_top(dc_legs + ou_legs, 2))
    t3 = compose.make_ticket("3plus", compose.pick_top(dc_legs + btts_legs + ou_legs, 3))
    t4 = compose.make_ticket("4plus", compose.pick_top(dc_legs + btts_legs + ou_legs + mw_legs, 4))

    _write("2plus.json", {"date": date, "tickets": [t2]})
    _write("3plus.json", {"date": date, "tickets": [t3]})
    _write("4plus.json", {"date": date, "tickets": [t4]})
    _write("btts.json", {"date": date, "legs": btts_legs})
    _write("dc.json", {"date": date, "legs": dc_legs})
    _write("over15.json", {"date": date, "legs": [l for l in ou_legs if l["pick"] == "Over 1.5"]})
    _write("over25.json", {"date": date, "legs": [l for l in ou_legs if l["pick"] == "Over 2.5"]})
    _write("single_analysis.json", {"date": date, "legs": ana_legs})

    _write("log.json", {
        "date": date,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "counts": {
            "dc": len(dc_legs),
            "btts": len(btts_legs),
            "ou": len(ou_legs),
            "mw": len(mw_legs),
            "analysis": len(ana_legs),
        }
    })

if __name__ == "__main__":
    run()
