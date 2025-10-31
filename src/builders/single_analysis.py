# src/builders/single_analysis.py
import os
import json
import requests
from typing import List, Dict, Any
from ..odds import fixtures_by_date, odds_by_fixture

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_URL = "https://api.openai.com/v1/responses"

# dozvoljene lige + UEFA takmičenja (po API-Football ID-jevima)
ALLOWED_COMPETITIONS = {
    # Top 5
    39,   # Premier League
    140,  # La Liga
    61,   # Ligue 1
    78,   # Bundesliga
    135,  # Serie A
    # Ostale jake
    94,   # Primeira Liga
    88,   # Eredivisie
    203,  # Super Lig (TUR)
    197,  # Jupiler Pro League (BEL)
    179,  # Championship (ENG2) ako želiš
    2,    # UEFA Champions League
    3,    # UEFA Europa League
    848,  # UEFA Europa Conference League (noviji ID, proveri u svom accountu)
    848,  # duplikat nije problem u setu
    4,    # UEFA Super Cup
    566,  # Nations League (opciono)
    262,  # MLS (opciono)
    253,  # Brasileirão (opciono)
}

MAX_FIXTURES = 5  # koliko analiza hoćemo dnevno

def _make_prompt(fixture: Dict[str, Any], odds: Dict[str, Any]) -> str:
    home = fixture["teams"]["home"]["name"]
    away = fixture["teams"]["away"]["name"]
    league = fixture["league"]["name"]
    return (
        f"Make an in-depth football match analysis for {home} vs {away} in {league}. "
        "Use only educational and analytical wording, do not recommend betting or staking. "
        "Focus on form, goals, BTTS tendency, over/under patterns, home/away strength. "
        "Return JSON with keys: title, summary, safest_markets (array of strings), observations (array of strings)."
    )

def _call_openai(prompt: str) -> Any:
    if not OPENAI_API_KEY:
        return {"note": "OPENAI not configured"}
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }
    body = {
        "model": OPENAI_MODEL,
        "input": prompt,
        "format": "json_object",
    }
    resp = requests.post(OPENAI_URL, headers=headers, json=body, timeout=40)
    if resp.status_code != 200:
        return {"error": f"openai_http_{resp.status_code}", "detail": resp.text}
    data = resp.json()
    try:
        raw = data["output"][0]["content"][0]["text"]
        try:
            return json.loads(raw)
        except Exception:
            return {"raw": raw}
    except Exception:
        return {"error": "unexpected_openai_payload", "raw": data}

def build(date: str) -> List[Dict[str, Any]]:
    # 1. uzmi sve mečeve za danas
    all_fixtures = fixtures_by_date(date)

    # 2. filtriraj samo naše lige/UEFA
    filtered = [
        f for f in all_fixtures
        if f["league"]["id"] in ALLOWED_COMPETITIONS
    ]

    # 3. uzmi samo prvih 5
    fixtures = filtered[:MAX_FIXTURES]

    legs: List[Dict[str, Any]] = []

    for f in fixtures:
        fid = f["fixture"]["id"]
        home = f["teams"]["home"]["name"]
        away = f["teams"]["away"]["name"]

        odds = odds_by_fixture(fid)
        prompt = _make_prompt(f, odds)
        analysis_payload = _call_openai(prompt)

        legs.append({
            "fixture_id": fid,
            "league_id": f["league"]["id"],
            "league_name": f["league"]["name"],
            "market": "ANALYSIS",
            "pick": "AI_ANALYSIS",
            "odds": 1.00,
            "label": f"{home} vs {away}",
            "analysis": analysis_payload
        })

    return legs
