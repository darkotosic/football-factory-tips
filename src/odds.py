from typing import Any, Dict, List
from . import api, cache
from .util import today_iso

def fixtures_by_date(date: str = None) -> List[Dict[str, Any]]:
    date = date or today_iso()
    ck = f"fixtures_{date}"
    cached = cache.get(ck, 1800)
    if cached:
        return cached
    data = api.get("/fixtures", {"date": date})
    fixtures = data.get("response", [])
    cache.set(ck, fixtures)
    return fixtures

def odds_by_fixture(fid: int) -> Dict[str, Any]:
    ck = f"odds_{fid}"
    cached = cache.get(ck, 3600)
    if cached:
        return cached
    data = api.get("/odds", {"fixture": fid})
    resp = data.get("response", [])
    parsed = resp[0] if resp else {}
    cache.set(ck, parsed)
    return parsed

def h2h(f1: int, f2: int, last: int = 5) -> List[Dict[str, Any]]:
    ck = f"h2h_{f1}_{f2}_{last}"
    cached = cache.get(ck, 3600)
    if cached:
        return cached
    data = api.get("/fixtures/headtohead", {"h2h": f"{f1}-{f2}", "last": last})
    res = data.get("response", [])
    cache.set(ck, res)
    return res

def teams_statistics(league: int, season: int, team: int) -> Dict[str, Any]:
    ck = f"stats_{league}_{season}_{team}"
    cached = cache.get(ck, 3600)
    if cached:
        return cached
    data = api.get("/teams/statistics", {
        "league": league,
        "season": season,
        "team": team
    })
    cache.set(ck, data)
    return data

def standings_all(league: int, season: int) -> Dict[str, Any]:
    ck = f"standings_{league}_{season}"
    cached = cache.get(ck, 3600)
    if cached:
        return cached
    data = api.get("/standings", {
        "league": league,
        "season": season
    })
    cache.set(ck, data)
    return data

def predictions_by_fixture(fid: int) -> Dict[str, Any]:
    ck = f"pred_{fid}"
    cached = cache.get(ck, 3600)
    if cached:
        return cached
    data = api.get("/predictions", {"fixture": fid})
    resp = data.get("response", [])
    parsed = resp[0] if resp else {}
    cache.set(ck, parsed)
    return parsed
