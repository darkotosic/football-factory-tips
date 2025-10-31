from typing import List, Dict, Any
from ..odds import fixtures_by_date, odds_by_fixture

MIN_ODD = 1.70
MAX_ODD = 2.50

def build(date: str) -> List[Dict[str, Any]]:
    legs = []
    fixtures = fixtures_by_date(date)
    for f in fixtures:
        fid = f["fixture"]["id"]
        home = f["teams"]["home"]["name"]
        away = f["teams"]["away"]["name"]
        odds = odds_by_fixture(fid)
        best = None
        best_odd = 0.0
        for b in odds.get("bookmakers", []):
            for m in b.get("bets", []):
                if m.get("name") in ("Match Winner", "Matchwinner", "1x2"):
                    for v in m.get("values", []):
                        try:
                            odd = float(v.get("odd", "0"))
                        except ValueError:
                            continue
                        if MIN_ODD <= odd <= MAX_ODD and odd > best_odd:
                            best = v.get("value")
                            best_odd = odd
        if best:
            legs.append({
                "fixture_id": fid,
                "market": "MW",
                "pick": best,
                "odds": best_odd,
                "label": f"{home} vs {away}"
            })
    return legs
