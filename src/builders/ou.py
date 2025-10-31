from typing import List, Dict, Any
from ..odds import fixtures_by_date, odds_by_fixture

TARGET_LINES = ("Over 1.5", "Over 2.5")

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
                if m.get("name") == "Over/Under":
                    for v in m.get("values", []):
                        val = v.get("value")
                        if val in TARGET_LINES:
                            pick = val
                            o = float(v.get("odd", "1.40"))
                            break
            if pick:
                break
        if pick:
            legs.append({
                "fixture_id": fid,
                "market": "OU",
                "pick": pick,
                "odds": o,
                "label": f"{home} vs {away}"
            })
    return legs
