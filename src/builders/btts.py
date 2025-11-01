from typing import List, Dict, Any
from ..odds import fixtures_by_date, odds_by_fixture

MIN_ODD = 1.20  # BTTS obično skuplji, malo viši prag

def _best_btts_yes(odds: Dict[str, Any]):
    best_odd = 0.0
    for b in odds.get("bookmakers", []):
        for m in b.get("bets", []):
            if m.get("name") not in ("Both Teams Score", "Both Teams To Score"):
                continue
            for v in m.get("values", []):
                if v.get("value") != "Yes":
                    continue
                try:
                    odd = float(v.get("odd", "0"))
                except Exception:
                    continue
                if odd >= MIN_ODD and odd > best_odd:
                    best_odd = odd
    if best_odd > 0:
        return "BTTS Yes", best_odd
    return None, None

def build(date: str) -> List[Dict[str, Any]]:
    legs: List[Dict[str, Any]] = []
    fixtures = fixtures_by_date(date)
    for f in fixtures:
        fid = f["fixture"]["id"]
        home = f["teams"]["home"]["name"]
        away = f["teams"]["away"]["name"]
        o = odds_by_fixture(fid)
        pick, odd = _best_btts_yes(o)
        if not pick:
            continue
        legs.append({
            "fixture_id": fid,
            "market": "BTTS",
            "pick": pick,
            "odds": round(odd, 2),
            "label": f"{home} vs {away}",
        })
    return legs
