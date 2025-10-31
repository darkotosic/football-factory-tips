from typing import List, Dict, Any
from ..odds import fixtures_by_date, odds_by_fixture

def build(date: str) -> List[Dict[str, Any]]:
    legs = []
    fixtures = fixtures_by_date(date)
    for f in fixtures:
        fid = f["fixture"]["id"]
        home = f["teams"]["home"]["name"]
        away = f["teams"]["away"]["name"]
        odds = odds_by_fixture(fid)
        pick = None
        o = None
        for b in odds.get("bookmakers", []):
            for m in b.get("bets", []):
                if m.get("name") in ("Both Teams Score", "Both Teams To Score"):
                    values = m.get("values", [])
                    yes = next((v for v in values if v.get("value") == "Yes"), None)
                    if yes:
                        pick = "BTTS Yes"
                        o = float(yes.get("odd", "1.50"))
                        break
            if pick:
                break
        if pick:
            legs.append({
                "fixture_id": fid,
                "market": "BTTS",
                "pick": pick,
                "odds": o,
                "label": f"{home} vs {away}"
            })
    return legs
