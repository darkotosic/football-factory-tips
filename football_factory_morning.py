#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations
import os, json, sys, random, time, re
from datetime import datetime
from zoneinfo import ZoneInfo
import httpx

TZ = ZoneInfo(os.getenv("TIMEZONE", "Europe/Belgrade"))
API_KEY = os.getenv("API_FOOTBALL_KEY")
BASE_URL = os.getenv("API_FOOTBALL_URL", "https://v3.football.api-sports.io")
HEADERS = {"x-apisports-key": API_KEY} if API_KEY else {}

OUT_DIR = os.path.join(os.getcwd(), "public")
os.makedirs(OUT_DIR, exist_ok=True)

# ako hoćeš da uključiš ALLOW_LIST stavi FOOTBALL_FACTORY_ALLOW=1 u secrets
ALLOW_ENABLED = os.getenv("FOOTBALL_FACTORY_ALLOW", "0") == "1"
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

# kapovi uzeti iz tvojih skripti
BASE_TH = {
    ("Double Chance","1X"): 1.20,
    ("Double Chance","X2"): 1.25,
    ("BTTS","Yes"): 1.40,
    ("BTTS","No"): 1.30,
    ("Over/Under","Over 1.5"): 1.15,
    ("Over/Under","Under 3.5"): 1.20,
    ("Over/Under","Over 2.5"): 1.28,
    ("Match Winner","Home"): 1.30,
    ("Match Winner","Away"): 1.30,
}

def log(sec, val):
    print(f"\n=== {sec} ===", file=sys.stderr)
    if isinstance(val, (dict, list)):
        print(json.dumps(val, ensure_ascii=False, indent=2), file=sys.stderr)
    else:
        print(val, file=sys.stderr)

def today() -> str:
    return datetime.now(TZ).strftime("%Y-%m-%d")

def client() -> httpx.Client:
    return httpx.Client(timeout=30)

def api_get(path: str, params: dict) -> dict:
    url = f"{BASE_URL}{'' if path.startswith('/') else '/'}{path}"
    with client() as c:
        r = c.get(url, headers=HEADERS, params=params)
        log("API", {"url": url, "params": params, "status": r.status_code})
        r.raise_for_status()
        return r.json()

def fetch_fixtures(date_str: str):
    data = api_get("/fixtures", {"date": date_str})
    out = []
    for f in data.get("response", []):
        lg = f.get("league", {}) or {}
        fx = f.get("fixture", {}) or {}
        st = (fx.get("status") or {}).get("short", "")
        if st in SKIP_STATUS:
            continue
        if ALLOW_ENABLED and lg.get("id") not in ALLOW_LIST:
            continue
        out.append(f)
    log("FIXTURES_FOUND", {"count": len(out), "allow_enabled": ALLOW_ENABLED})
    # ispiši sve
    for f in out:
        lg=f["league"]; tm=f["teams"]; fx=f["fixture"]
        print(f"- {lg.get('country')} — {lg.get('name')} | {tm['home']['name']} vs {tm['away']['name']} | {fx['id']}", file=sys.stderr)
    return out

def fetch_odds_raw(fid: int):
    data = api_get("/odds", {"fixture": fid})
    return data.get("response", []) or []

def best_markets_from_odds(raw):
    # isto kao tvoji all_tips
    bets = {}
    FORBIDDEN = [
        "asian","corners","cards","booking","penal","penalty",
        "throw in","interval","race to","period","quarter","to qualify","overtime"
    ]
    def bad(name: str) -> bool:
        n = (name or "").lower()
        return any(bad in n for bad in FORBIDDEN)

    for item in raw:
        for bm in item.get("bookmakers", []) or []:
            for bet in bm.get("bets", []) or []:
                name = (bet.get("name") or "").strip()
                if bad(name):
                    continue
                for v in bet.get("values", []) or []:
                    # value ponekad bude int -> prebacujemo u str
                    raw_val = v.get("value")
                    val = str(raw_val).strip() if raw_val is not None else ""
                    odd = v.get("odd")
                    try:
                        odd = float(odd)
                    except Exception:
                        continue

                    key_market = None
                    key_name = None

                    if name in {"Double Chance","Double chance"}:
                        v2 = val.replace(" ","").upper()
                        if v2 in {"1X","X2","12"}:
                            key_market = "Double Chance"
                            key_name = v2

                    elif name in {"Both Teams To Score","BTTS","Both teams to score"}:
                        key_market = "BTTS"
                        key_name = val.title()

                    elif name in {"Match Winner","1X2","Result","Full Time Result"}:
                        if val in {"Home","1"}:
                            key_market = "Match Winner"; key_name = "Home"
                        elif val in {"Away","2"}:
                            key_market = "Match Winner"; key_name = "Away"

                    elif "Over/Under" in name or "Total Goals" in name:
                        vnorm = " ".join(val.title().split())
                        if vnorm in {"Over 1.5","Over 2.5","Under 3.5"}:
                            key_market = "Over/Under"; key_name = vnorm

                    if key_market and key_name:
                        bets.setdefault(key_market, {})
                        if key_name not in bets[key_market] or odd > bets[key_market][key_name]:
                            bets[key_market][key_name] = odd
    return bets

# ---------------------------------------------------------------------
# 3 x 1X TIKETA  (greedy, bez CAP, samo 1X < X2 kad oba postoje)
# ---------------------------------------------------------------------
def build_1x(fixtures):
    legs = []
    for f in fixtures:
        fx=f["fixture"]; lg=f["league"]; tm=f["teams"]
        raw = fetch_odds_raw(fx["id"])
        odds = best_markets_from_odds(raw) if raw else {}
        dc = odds.get("Double Chance", {})
        o1x = dc.get("1X"); ox2 = dc.get("X2")
        if o1x:
            if ox2 and o1x > ox2:
                pass
            legs.append({
                "fixture_id": fx["id"],
                "league": f"{lg.get('country','')} — {lg.get('name','')}",
                "teams": f"{tm['home']['name']} vs {tm['away']['name']}",
                "time": fx["date"],
                "market": "Double Chance",
                "pick": "1X",
                "odd": float(o1x),
            })
    ...

    # dosta će ih biti → iseckaj u 3 tiketa po 3-4 meča
    random.shuffle(legs)
    tickets = []
    chunk = []
    total = 1.0
    for leg in legs:
        chunk.append(leg); total *= leg["odd"]
        if len(chunk) == 4:
            tickets.append({
                "name": f"1x_{len(tickets)+1}",
                "type": "1x",
                "legs": chunk,
                "total_odds": round(total, 2),
            })
            chunk = []; total = 1.0
        if len(tickets) == 3:
            break
    if chunk and len(tickets) < 3:
        tickets.append({
            "name": f"1x_{len(tickets)+1}",
            "type": "1x",
            "legs": chunk,
            "total_odds": round(total, 2),
        })
    log("TICKETS_1X", tickets)
    return tickets

# ---------------------------------------------------------------------
# 2 x ALL TIPS (2.0 i 3.0) isto kao telegram_all_tips_ticket
# ---------------------------------------------------------------------
def build_all(fixtures):
    all_legs = []
    for f in fixtures:
        fx=f["fixture"]; lg=f["league"]; tm=f["teams"]
        raw = fetch_odds_raw(fx["id"])
        odds = best_markets_from_odds(raw)
        best_leg = None; best_odd = 0.0
        for mkt, vals in odds.items():
            for name, odd in vals.items():
                cap = BASE_TH.get((mkt, name))
                if cap is None:
                    continue
                if odd < cap and odd > best_odd:
                    best_leg = (mkt, name, odd)
                    best_odd = odd
        if best_leg:
            all_legs.append({
                "fixture_id": fx["id"],
                "league": f"{lg.get('country','')} — {lg.get('name','')}",
                "teams": f"{tm['home']['name']} vs {tm['away']['name']}",
                "time": fx["date"],
                "market": best_leg[0],
                "pick": best_leg[1],
                "odd": float(best_leg[2]),
            })
    # sort po kvoti da prvo uzmemo najjače
    all_legs.sort(key=lambda x: x["odd"], reverse=True)
    log("ALL_LEGS", {"count": len(all_legs)})

    tickets = []
    used = set()
    for target in (2.0, 3.0):
        cur=[]; total=1.0
        for leg in all_legs:
            if leg["fixture_id"] in used:
                continue
            cur.append(leg); total *= leg["odd"]
            if len(cur) >= 3 and total >= target:
                tickets.append({
                    "name": f"all_{str(target).replace('.','_')}",
                    "type": "all_tips",
                    "target_odds": target,
                    "legs": cur,
                    "total_odds": round(total, 2),
                })
                used.update([x["fixture_id"] for x in cur])
                break
    log("TICKETS_ALL", tickets)
    return tickets

# ---------------------------------------------------------------------
# 3 x BTTS YES/NO (kao btts_combo ali kraća verzija)
# ---------------------------------------------------------------------
def build_btts(fixtures):
    cands = []
    for f in fixtures:
        fx=f["fixture"]; lg=f["league"]; tm=f["teams"]
        raw = fetch_odds_raw(fx["id"])
        odds = best_markets_from_odds(raw)
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
                "time": fx["date"],
                "market": "BTTS",
                "pick": pick,
                "odd": odd,
            })
    # sortiraj prema tome koliko je blizu 1.5
    cands.sort(key=lambda x: abs(x["odd"] - 1.5))
    log("BTTS_CANDS", {"count": len(cands)})
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
            t={
                "name": f"btts_{i+1}",
                "type": "btts",
                "legs": cur,
                "total_odds": round(tot, 2),
            }
            tickets.append(t)
            log("BTTS_TICKET", t)
    return tickets

def main():
    date = today()
    log("START", {"date": date, "allow_enabled": ALLOW_ENABLED})
    fixtures = fetch_fixtures(date)
    # ako i dalje nema dosta, odmah isključi allow
    if len(fixtures) < 40 and ALLOW_ENABLED:
        log("RELAX", "fixtures < 40, disabling ALLOW_LIST and refetching")
        globals()["ALLOW_ENABLED"] = False
        fixtures = fetch_fixtures(date)

    tickets = []
    tickets += build_1x(fixtures)
    tickets += build_all(fixtures)
    tickets += build_btts(fixtures)

    log("FINAL_TICKETS", {"count": len(tickets)})
    snapshot = {
        "date": date,
        "tickets": tickets,
        "meta": {"app": "football-factory-tips", "version": "2.0.0"}
    }
    with open(os.path.join(OUT_DIR, "feed_snapshot.json"), "w", encoding="utf-8") as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=2)
    with open(os.path.join(OUT_DIR, "daily.json"), "w", encoding="utf-8") as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=2)

    print(json.dumps({"status": "ok", "tickets": len(tickets)}, ensure_ascii=False))

if __name__ == "__main__":
    main()
