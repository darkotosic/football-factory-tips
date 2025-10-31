#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations
import os, json, sys, random
from datetime import datetime
from zoneinfo import ZoneInfo
import httpx

# ---------------------------------------------------------------------------
# KONFIG
# ---------------------------------------------------------------------------
TZ = ZoneInfo(os.getenv("TIMEZONE", "Europe/Belgrade"))
API_KEY = os.getenv("API_FOOTBALL_KEY") or os.getenv("API_KEY")
BASE_URL = os.getenv("API_FOOTBALL_URL", "https://v3.football.api-sports.io")
HEADERS = {"x-apisports-key": API_KEY} if API_KEY else {}

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")

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

# ---------------------------------------------------------------------------
# POMOĆNE
# ---------------------------------------------------------------------------
def log(section: str, payload):
    """debug ispis kao u focus-bets-feed"""
    print(f"\n=== {section} ===")
    if isinstance(payload, (dict, list)):
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(payload)

def today_str() -> str:
    return datetime.now(TZ).strftime("%Y-%m-%d")

def client() -> httpx.Client:
    return httpx.Client(timeout=30)

def api_get(path: str, params: dict) -> dict:
    url = f"{BASE_URL}{'' if path.startswith('/') else '/'}{path}"
    log("API CALL", {"url": url, "params": params})
    with client() as c:
        r = c.get(url, headers=HEADERS, params=params)
        log("API STATUS", {"status_code": r.status_code})
        r.raise_for_status()
        data = r.json()
        # ispiši prvih 1-2 itema
        resp = data.get("response", [])
        log("API RESPONSE SHORT", resp[:2] if resp else [])
        return data

def fetch_fixtures(date_str: str):
    log("STEP", f"fetch_fixtures for {date_str}")
    try:
        data = api_get("/fixtures", {"date": date_str})
    except Exception as e:
        log("fixtures error", str(e))
        return []
    cleaned = []
    for f in data.get("response", []):
        lg = f.get("league", {}) or {}
        fx = f.get("fixture", {}) or {}
        if lg.get("id") not in ALLOW_LIST:
            continue
        st = (fx.get("status") or {}).get("short", "")
        if st in SKIP_STATUS:
            continue
        cleaned.append(f)
    log("FIXTURES FILTERED", {"count": len(cleaned)})
    # ispis svih utakmica
    for f in cleaned:
        lg = f.get("league", {}) or {}
        tm = f.get("teams", {}) or {}
        fx = f.get("fixture", {}) or {}
        print(f"- [{lg.get('id')}] {lg.get('country')} — {lg.get('name')} | {tm.get('home',{}).get('name')} vs {tm.get('away',{}).get('name')} @ {fx.get('date')}")
    return cleaned

def fetch_odds(fid: int):
    log("STEP", f"fetch_odds for fixture {fid}")
    try:
        data = api_get("/odds", {"fixture": fid})
    except Exception as e:
        log("odds error", str(e))
        return []
    resp = data.get("response", []) or []
    # kratki ispis
    log("ODDS RAW SHORT", resp[:1])
    return resp

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
    log("BEST ODDS", best)
    return best

# ---------------------------------------------------------------------------
# OPENAI DEBUG
# ---------------------------------------------------------------------------
def make_openai_analysis(tickets: list[dict]) -> str:
    if not OPENAI_API_KEY:
        return "OPENAI_API_KEY not set."
    lines = []
    for t in tickets:
        lines.append(f"Ticket: {t.get('name') or t.get('type')}")
        for leg in t.get("legs", []):
            lines.append(f"- {leg.get('teams')} | {leg.get('market')} => {leg.get('pick')} ({leg.get('odd')})")
    content = "\n".join(lines)
    log("OPENAI REQUEST", content)
    with httpx.Client(timeout=120) as c:
        r = c.post(
            f"{OPENAI_BASE_URL.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
            json={
                "model": OPENAI_MODEL,
                "temperature": 0.2,
                "messages": [
                    {"role": "system", "content": "Be concise. Bullet points."},
                    {"role": "user", "content": "Analyze these football betting tickets. Mention league strength and odds logic.\n" + content}
                ],
            }
        )
        log("OPENAI RAW", r.text)
        r.raise_for_status()
        msg = r.json()["choices"][0]["message"]["content"].strip()
        log("OPENAI ANALYSIS", msg)
        return msg

# ---------------------------------------------------------------------------
# BUILDERI
# ---------------------------------------------------------------------------
def build_1x(fixtures: list[dict]):
    log("BUILD", "1X tickets")
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
    log("1X LEGS FOUND", {"count": len(legs)})
    for l in legs:
        log("1X LEG", l)
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
    log("1X TICKETS", tickets[:3])
    return tickets[:3]

def build_all(fixtures: list[dict]):
    log("BUILD", "ALL TIPS tickets")
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
            item = {
                "fixture_id": fx["id"],
                "league": f"{lg.get('country','')} — {lg.get('name','')}",
                "teams": f"{tm['home']['name']} vs {tm['away']['name']}",
                "time": fmt_local(fx["date"]),
                "market": best_leg[0],
                "pick": best_leg[1],
                "odd": float(best_leg[2]),
            }
            cands.append(item)
            log("ALL CAND", item)
    cands.sort(key=lambda x: x["odd"], reverse=True)

    tickets=[]
    used=set()
    for target, name in [(2.0,"all_tips_2"), (3.0,"all_tips_3")]:
        cur=[]; total=1.0
        for leg in cands:
            if leg["fixture_id"] in used:
                continue
            cur.append(leg); total *= leg["odd"]
            log("ALL BUILD PROGRESS", {"target": target, "total": total, "len": len(cur)})
            if len(cur) >= 3 and total >= target:
                t = {
                    "name": name,
                    "type": "all_tips",
                    "target_odds": target,
                    "legs": cur,
                    "total_odds": round(total,2),
                }
                tickets.append(t)
                used.update([x["fixture_id"] for x in cur])
                log("ALL BUILT TICKET", t)
                break
    return tickets

def build_btts(fixtures: list[dict]):
    log("BUILD", "BTTS tickets")
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
            obj = {
                "fixture_id": fx["id"],
                "league": f"{lg.get('country','')} — {lg.get('name','')}",
                "teams": f"{tm['home']['name']} vs {tm['away']['name']}",
                "time": fmt_local(fx["date"]),
                "market": "BTTS",
                "pick": pick,
                "odd": odd,
            }
            cands.append(obj)
            log("BTTS CAND", obj)
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
            t = {
                "name": f"btts_{i+1}",
                "type": "btts",
                "legs": cur,
                "total_odds": round(tot,2),
            }
            tickets.append(t)
            log("BTTS TICKET", t)
    return tickets

# ---------------------------------------------------------------------------
def main():
    date = today_str()
    log("START", {"date": date, "base_url": BASE_URL})

    fixtures = fetch_fixtures(date)
    log("AFTER FIXTURES", f"got {len(fixtures)} fixtures")

    t1x = build_1x(fixtures)
    tall = build_all(fixtures)
    tbtts = build_btts(fixtures)

    all_tickets = t1x + tall + tbtts
    log("ALL TICKETS COMBINED", all_tickets)

    analysis_text = make_openai_analysis(all_tickets) if all_tickets else "no tickets"

    snapshot = {
        "date": date,
        "tickets": all_tickets,
        "openai_analysis": analysis_text,
        "meta": {"app": "football-factory-tips", "version": "1.0.0"}
    }

    with open(os.path.join(OUT_DIR, "feed_snapshot.json"), "w", encoding="utf-8") as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=2)
    with open(os.path.join(OUT_DIR, "daily.json"), "w", encoding="utf-8") as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=2)

    log("WRITE", "public/feed_snapshot.json")
    log("WRITE", "public/daily.json")

    print(json.dumps({"status": "ok", "tickets": len(all_tickets)}, ensure_ascii=False))

if __name__ == "__main__":
    main()
