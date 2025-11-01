from typing import List, Dict, Any
from ..odds import fixtures_by_date, odds_by_fixture

MIN_ODD = 1.10  # da ne uzme 1.00 ili prazno

def _best_dc_from_odds(odds: Dict[str, Any]):
    best = None
    best_odd = 0.0

    for b in odds.get("bookmakers", []):
        for m in b.get("bets", []):
            if m.get("name") not in ("Double Chance", "Double chance"):
                continue
            for v in m.get("values", []):
                val = v.get("value")
                odd_str = v.get("odd", "")
                try:
                    odd = float(odd_str)
                except Exception:
                    continue
                if odd >= MIN_ODD and odd > best_odd:
                    best = val
                    best_odd = odd
    if best:
        return best, best_odd
    return None, None

def build(date: str) -> List[Dict[str, Any]]:
    legs: List[Dict[str, Any]] = []
    fixtures = fixtures_by_date(date)
    for f in fixtures:
        fid = f["fixture"]["id"]
        home = f["teams"]["home"]["name"]
        away = f["teams"]["away"]["name"]
        o = odds_by_fixture(fid)
        pick, odd = _best_dc_from_odds(o)
        if not pick:
            continue
        legs.append({
            "fixture_id": fid,
            "market": "DC",
            "pick": pick,
            "odds": round(odd, 2),
            "label": f"{home} vs {away}",
        })
    return legs
