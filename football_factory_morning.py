#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations
import os, json, sys, random
from datetime import datetime
from zoneinfo import ZoneInfo
import httpx

TZ = ZoneInfo(os.getenv("TIMEZONE", "Europe/Belgrade"))
API_KEY = os.getenv("API_FOOTBALL_KEY") or os.getenv("API_KEY")
BASE_URL = os.getenv("API_FOOTBALL_URL", "https://v3.football.api-sports.io")
HEADERS = {"x-apisports-key": API_KEY} if API_KEY else {}

OUT_DIR = os.path.join(os.getcwd(), "public")
os.makedirs(OUT_DIR, exist_ok=True)

ALLOW_LIST = {
    2,3,5,10,29,30,31,32,33,34,35,36,37,38,39,40,
    41,42,43,44,45,46,47,48,49,50,51,52,53,54,
    56,57,58,59,60,61,62,78,79,88,89,94,
    135,136,140,141,144,197,202,203,207,208,210,211,
    218,219,233,244,245,261,268,269,270,271,272,283,
    286,287,310,311,323,329,332,333,340,345,346,362,365,
    373,374,389,408,490,506,536,703,808,848,850,890,909,960,1083,
}
SKIP_STATUS = {"FT","AET","PEN","ABD","AWD","CANC","POSTP","PST","SUSP","INT","WO","LIVE"}

def today_str() -> str:
    return datetime.now(TZ).strftime("%Y-%m-%d")

def client() -> httpx.Client:
    return httpx.Client(timeout=30)

def api_get(path: str, params: dict) -> dict:
    url = f"{BASE_URL}{'' if path.startswith('/') else '/'}{path}"
    with client() as c:
        r = c.get(url, headers=HEADERS, params=params)
        r.raise_for_status()
        return r.json()

def fetch_fixtures(date_str: str):
    try:
        data = api_get("/fixtures", {"date": date_str})
    except Exception as e:
        print("fixtures error:", e, file=sys.stderr)
        return []
    out = []
    for f in data.get("response", []):
        lg = f.get("league", {}) or {}
        fx = f.get("fixture", {}) or {}
        if lg.get("id") not in ALLOW_LIST:
            continue
        st = (fx.get("status") or {}).get("short", "")
        if st in SKIP_STATUS:
            continue
        out.append(f)
    return out

def fetch_odds(fid: int):
    try:
        data = api_get("/odds", {"fixture": fid})
        return data.get("response", []) or []
    except Exception:
        return []

def fmt_local(iso: str) -> str:
    try:
        return datetime.fromisoformat(iso.replace("Z","+00:00")).astimezone(TZ).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return iso

def best_odds(fid: int) -> dict:
    DOC = {
        "dc": {"Double Chance","Double chance"},
        "btts": {"Both Teams To Score","Both teams to score","BTTS"},
        "ou": {"Over/Under","Total Goals","Goals Over/Under","Total Goals Over/Under"},
        "mw": {"Match Winner","1X2","Full Time Result","Result"},
    }
    best: dict = {}
    raw = fetch_odds(fid)
    def put(mkt, val, odd):
        try: o = float(odd)
        except: return
        if o <= 0: return
        best.setdefault(mkt, {})
        if val not in best[mkt] or o > best[mkt][val]:
            best[mkt][val] = o
    for item in raw:
        for bm in item.get("bookmakers", []) or []:
            for bet in bm.get("bets", []) or []:
                name = (bet.get("name") or "").strip()
                if name in DOC["dc"]:
                    for v in bet.get("values", []) or []:
                        val = (v.get("value") or "").replace(" ","").upper()
                        if val in {"1X","X2","12"}:
                            put("Double Chance", val, v.get("odd"))
                elif name in DOC["btts"]:
                    for v in bet.get("values", []) or []:
                        val = (v.get("value") or "").title()
                        if val in {"Yes","No"}:
                            put("BTTS", val, v.get("odd"))
                elif name in DOC["ou"]:
                    for v in bet.get("values", []) or []:
                        val = (v.get("value") or "").title()
                        if val in {"Over 1.5","Over 2.5","Under 3.5"}:
                            put("Over/Under", val, v.get("odd"))
                elif name in DOC["mw"]:
                    for v in bet.get("values", []) or []:
                        val = (v.get("value") or "").strip()
                        if val in {"Home","1"}:
                            put("Match Winner","Home", v.get("odd"))
                        elif val in {"Away","2"}:
                            put("Match Winner","Away", v.get("odd"))
    return best

# ---- builders ----

def build_1x(date_str: str):
    fixtures = fetch_fixtures(date_str)
    legs = []
    for f in fixtures:
        fx = f["fixture"]; lg = f["league"]; tm = f["teams"]
        odds = best_odds(fx["id"])
        dc = odds.get("Double Chance", {})
        odd_1x = dc.get("1X")
        odd_x2 = dc.get("X2")
        if odd_1x and odd_1x >= 1.05 and (not odd_x2 or odd_1x <= odd_x2):
            legs.append({
                "fixture_id": fx["id"],
                "league": f"{lg.get('country','')} — {lg.get('name','')}",
                "teams": f"{tm['home']['name']} vs {tm['away']['name']}",
                "time": fmt_local(fx["date"]),
                "market": "Double Chance",
                "pick": "1X",
                "odd": float(odd_1x),
            })
    random.shuffle(legs)
    tickets = []
    cur = []; total = 1.0
    for leg in legs:
        if len(cur) < 4:
            cur.append(leg); total *= leg["odd"]
        else:
            tickets.append({"name":"1x","type":"1x","legs":cur,"total_odds":round(total,2)})
            cur = [leg]; total = leg["odd"]
    if cur:
        tickets.append({"name":"1x","type":"1x","legs":cur,"total_odds":round(total,2)})
    return tickets[:3]

def build_all(date_str: str):
    fixtures = fetch_fixtures(date_str)
    cands = []
    for f in fixtures:
        fx = f["fixture"]; lg = f["league"]; tm = f["teams"]
        odds = best_odds(fx["id"])
        best_leg = None; best_odd = 0
        for mkt, vals in odds.items():
            for name, odd in vals.items():
                if odd and odd > best_odd:
                    best_leg = (mkt, name, odd)
                    best_odd = odd
        if best_leg:
            cands.append({
                "fixture_id": fx["id"],
                "league": f"{lg.get('country','')} — {lg.get('name','')}",
                "teams": f"{tm['home']['name']} vs {tm['away']['name']}",
                "time": fmt_local(fx["date"]),
                "market": best_leg[0],
                "pick": best_leg[1],
                "odd": float(best_leg[2]),
            })
    cands.sort(key=lambda x: x["odd"], reverse=True)
    tickets=[]
    used=set()
    for target, name in [(2.0,"all_tips_2"), (3.0,"all_tips_3")]:
        cur=[]; total=1.0
        for leg in cands:
            if leg["fixture_id"] in used:
                continue
            cur.append(leg); total *= leg["odd"]
            if len(cur) >= 3 and total >= target:
                tickets.append({
                    "name": name,
                    "type": "all_tips",
                    "target_odds": target,
                    "legs": cur,
                    "total_odds": round(total,2),
                })
                used.update([x["fixture_id"] for x in cur])
                break
    return tickets

def build_btts(date_str: str):
    fixtures = fetch_fixtures(date_str)
    cands=[]
    for f in fixtures:
        fx = f["fixture"]; lg = f["league"]; tm = f["teams"]
        odds = best_odds(fx["id"])
        btts = odds.get("BTTS", {})
        yes = btts.get("Yes"); no = btts.get("No")
        pick=None; odd=None
        if yes and 1.30 <= yes <= 2.10:
            pick="Yes"; odd=float(yes)
        elif no and 1.30 <= no <= 2.10:
            pick="No"; odd=float(no)
        if pick:
            cands.append({
                "fixture_id": fx["id"],
                "league": f"{lg.get('country','')} — {lg.get('name','')}",
                "teams": f"{tm['home']['name']} vs {tm['away']['name']}",
                "time": fmt_local(fx["date"]),
                "market": "BTTS",
                "pick": pick,
                "odd": odd,
            })
    cands.sort(key=lambda x: abs(x["odd"] - 1.50))
    tickets=[]
    used=set()
    for i in range(3):
        cur=[]
        for leg in cands:
            if leg["fixture_id"] in used:
                continue
            cur.append(leg); used.add(leg["fixture_id"])
            if len(cur) >= 2:
                break
        if cur:
            tot=1.0
            for c in cur: tot *= c["odd"]
            tickets.append({
                "name": f"btts_{i+1}",
                "type": "btts",
                "legs": cur,
                "total_odds": round(tot,2),
            })
    return tickets

def main():
    date = today_str()
    tickets = []
    tickets.extend(build_1x(date))
    tickets.extend(build_all(date))
    tickets.extend(build_btts(date))

    snapshot = {
        "date": date,
        "tickets": tickets,
        "meta": {"app": "football-factory-tips", "version": "1.0.0"}
    }
    with open(os.path.join(OUT_DIR, "feed_snapshot.json"), "w", encoding="utf-8") as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=2)
    with open(os.path.join(OUT_DIR, "daily.json"), "w", encoding="utf-8") as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=2)

    print(json.dumps({"status": "ok", "tickets": len(tickets)}, ensure_ascii=False))

if __name__ == "__main__":
    main()
