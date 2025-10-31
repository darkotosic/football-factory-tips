#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# evening script content here...
from __future__ import annotations
import os, json, sys
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import httpx

TZ = ZoneInfo(os.getenv("TIMEZONE", "Europe/Belgrade"))
API_KEY = os.getenv("API_FOOTBALL_KEY") or os.getenv("API_KEY")
BASE_URL = os.getenv("API_FOOTBALL_URL", "https://v3.football.api-sports.io")
HEADERS = {"x-apisports-key": API_KEY} if API_KEY else {}

PUBLIC = os.path.join(os.getcwd(), "public")
os.makedirs(PUBLIC, exist_ok=True)

FINAL_STATUSES = {"FT","AET","PEN"}

def api_get(path: str, params: dict) -> dict:
    url = f"{BASE_URL}{'' if path.startswith('/') else '/'}{path}"
    with httpx.Client(timeout=30) as c:
        r = c.get(url, headers=HEADERS, params=params)
        r.raise_for_status()
        return r.json()

def fetch_fixture_by_id(fid: int):
    try:
        data = api_get("/fixtures", {"id": fid})
    except Exception:
        return None
    resp = data.get("response") or []
    return resp[0] if resp else None

def leg_hit(leg: dict, fx: dict):
    goals = fx.get("goals") or {}
    home = goals.get("home") or 0
    away = goals.get("away") or 0
    total = (home or 0) + (away or 0)
    st = (fx.get("fixture") or {}).get("status") or {}
    short = st.get("short")

    if short not in FINAL_STATUSES:
        return False, {"status": short or "NS", "pending": True}

    m = leg.get("market")
    p = (leg.get("pick") or "").upper()

    ok = False
    if m == "Double Chance":
        if p == "1X":
            ok = home > away or home == away
        elif p == "X2":
            ok = away > home or home == away
        elif p == "12":
            ok = home != away
    elif m == "BTTS":
        if p == "YES":
            ok = home > 0 and away > 0
        elif p == "NO":
            ok = not (home > 0 and away > 0)
    elif m == "OVER/UNDER":
        pick = leg.get("pick")
        if pick == "Over 1.5":
            ok = total >= 2
        elif pick == "Over 2.5":
            ok = total >= 3
        elif pick == "Under 3.5":
            ok = total <= 3
    elif m == "MATCH WINNER":
        if p in {"HOME","1"}:
            ok = home > away
        elif p in {"AWAY","2"}:
            ok = away > home

    return ok, {
        "status": short,
        "home_goals": home,
        "away_goals": away,
        "pending": False,
    }

def main():
    snap_path = os.path.join(PUBLIC, "feed_snapshot.json")
    if not os.path.exists(snap_path):
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        out = {"date": today, "tickets": [], "error": "feed_snapshot.json not found"}
        with open(os.path.join(PUBLIC, "evaluation.json"), "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        print(json.dumps({"status":"no-snapshot"}, ensure_ascii=False))
        return

    with open(snap_path, "r", encoding="utf-8") as f:
        snap = json.load(f)

    date_str = snap.get("date")
    tickets = snap.get("tickets") or []

    evaluated = []
    any_pending = False

    for t in tickets:
        legs = t.get("legs") or []
        checked_legs = []
        all_hit = True
        has_loss = False

        for leg in legs:
            fid = leg.get("fixture_id")
            if not fid:
                checked_legs.append({**leg, "result": {"status": "NO_ID", "pending": True}})
                any_pending = True
                all_hit = False
                continue

            fx = fetch_fixture_by_id(int(fid))
            if not fx:
                checked_legs.append({**leg, "result": {"status": "NOT_FOUND", "pending": True}})
                any_pending = True
                all_hit = False
                continue

            ok, res = leg_hit(leg, fx)
            if res.get("pending"):
                any_pending = True
            if not ok and not res.get("pending"):
                all_hit = False
                has_loss = True

            emoji = "✅" if ok else ("🟡" if res.get("pending") else "❌")

            checked_legs.append({
                **leg,
                "result": {**res, "hit": ok, "emoji": emoji}
            })

        ticket_emoji = "✅" if all_hit and not any_pending else ("🟡" if any_pending and not has_loss else "❌")

        evaluated.append({
            **t,
            "legs": checked_legs,
            "evaluation": {
                "all_hit": all_hit,
                "any_pending": any_pending,
                "has_loss": has_loss,
                "emoji": ticket_emoji,
            }
        })

    out = {
        "date": date_str,
        "evaluated_at": datetime.now(TZ).isoformat(),
        "tickets": evaluated,
    }

    with open(os.path.join(PUBLIC, "evaluation.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print(json.dumps({"status":"evaluated", "pending": any_pending}, ensure_ascii=False))

if __name__ == "__main__":
    main()
