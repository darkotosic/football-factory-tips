# src/generate.py
import json, os
from datetime import datetime, timezone
from .builders import safe_dc, btts, ou, mw_value, single_analysis
from . import compose
from .util import today_iso

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
PUBLIC_DIR = os.path.join(BASE_DIR, "public")
os.makedirs(PUBLIC_DIR, exist_ok=True)

def _write(name: str, data):
    fp = os.path.join(PUBLIC_DIR, name)
    with open(fp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def run(date: str = None):
    date = date or today_iso()

    # 1) prikupi sve pool-ove za danas
    dc_legs = safe_dc.build(date)
    btts_legs = btts.build(date)
    ou_legs = ou.build(date)
    mw_legs = mw_value.build(date)

    # 2) AI analize (limitirano na 5 u single_analysis builderu)
    try:
        ai_legs = single_analysis.build(date)
    except Exception as e:
        ai_legs = [{"error": f"single_analysis_failed: {e}"}]

    # ------------------------------------------------------------------
    # FREE VARIJANTE
    # ------------------------------------------------------------------
    # jedan osnovni tiket 2+ (mešani pool: dc + ou)
    free_2plus = compose.make_ticket("2plus", compose.pick_top(dc_legs + ou_legs, 2))
    _write("2plus.json", {
        "date": date,
        "tickets": [free_2plus]
    })

    # BTTS free: samo lista
    _write("2plusbtts.json", {
        "date": date,
        "tickets": [
            compose.make_ticket("2plusbtts", compose.pick_top(btts_legs, 2))
        ]
    })

    # DC free: samo lista
    _write("dc.json", {
        "date": date,
        "legs": dc_legs
    })

    # OU free:
    _write("over15.json", {
        "date": date,
        "legs": [l for l in ou_legs if l["pick"] == "Over 1.5"]
    })
    _write("over25.json", {
        "date": date,
        "legs": [l for l in ou_legs if l["pick"] == "Over 2.5"]
    })

    # AI free: samo prva analiza
    first_ai = ai_legs[0:1] if isinstance(ai_legs, list) else []
    _write("single_analysis.json", {
        "date": date,
        "legs": first_ai
    })

    # ------------------------------------------------------------------
    # VIP VARIJANTE
    # ------------------------------------------------------------------
    # ideja: od svakog pool-a pravimo 3+ i 4+ varijantu, kako si napisao

    # 1) generalni pool (dc + btts + ou + mw) → za 3+ i 4+
    general_pool = dc_legs + btts_legs + ou_legs + mw_legs

    vip3_general = compose.make_ticket("vip3plus", compose.pick_top(general_pool, 3))
    vip4_general = compose.make_ticket("vip4plus", compose.pick_top(general_pool, 4))

    _write("vip3plus.json", {
        "date": date,
        "tickets": [vip3_general]
    })
    _write("vip4plus.json", {
        "date": date,
        "tickets": [vip4_general]
    })

    # 2) BTTS VIP
    vip3_btts = compose.make_ticket("vip3plusbtts", compose.pick_top(btts_legs, 3))
    vip4_btts = compose.make_ticket("vip4plusbtts", compose.pick_top(btts_legs, 4))

    _write("vip3plusbtts.json", {
        "date": date,
        "tickets": [vip3_btts]
    })
    _write("vip4plusbtts.json", {
        "date": date,
        "tickets": [vip4_btts]
    })

    # 3) DC VIP
    vip3_dc = compose.make_ticket("vip3plusdc", compose.pick_top(dc_legs, 3))
    vip4_dc = compose.make_ticket("vip4plusdc", compose.pick_top(dc_legs, 4))

    _write("vip3plusdc.json", {
        "date": date,
        "tickets": [vip3_dc]
    })
    _write("vip4plusdc.json", {   # ispravljeno ime
        "date": date,
        "tickets": [vip4_dc]
    })

    # 4) OVER 1.5 / 2.5 VIP
    over15_legs = [l for l in ou_legs if l["pick"] == "Over 1.5"]
    over25_legs = [l for l in ou_legs if l["pick"] == "Over 2.5"]

    vip3_over15 = compose.make_ticket("vip3plusover15", compose.pick_top(over15_legs, 3))
    vip4_over15 = compose.make_ticket("vip4plusover15", compose.pick_top(over15_legs, 4))
    vip3_over25 = compose.make_ticket("vip3plusover25", compose.pick_top(over25_legs, 3))
    vip4_over25 = compose.make_ticket("vip4plusover25", compose.pick_top(over25_legs, 4))

    _write("vip3plusover15.json", {
        "date": date,
        "tickets": [vip3_over15]
    })
    _write("vip4plusover15.json", {
        "date": date,
        "tickets": [vip4_over15]
    })
    _write("vip3plusover25.json", {
        "date": date,
        "tickets": [vip3_over25]
    })
    _write("vip4plusover25.json", {
        "date": date,
        "tickets": [vip4_over25]
    })

    # 5) AI VIP (sve analize)
    _write("vipsingle_analysis.json", {
        "date": date,
        "legs": ai_legs if isinstance(ai_legs, list) else []
    })

    # ------------------------------------------------------------------
    # LOG
    # ------------------------------------------------------------------
    _write("log.json", {
        "date": date,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "counts": {
            "free_2plus": 1,
            "free_btts": 1,
            "dc_legs": len(dc_legs),
            "btts_legs": len(btts_legs),
            "ou_legs": len(ou_legs),
            "mw_legs": len(mw_legs),
            "ai_free": len(first_ai),
            "ai_vip": len(ai_legs) if isinstance(ai_legs, list) else 0,
        }
    })

if __name__ == "__main__":
    run()
