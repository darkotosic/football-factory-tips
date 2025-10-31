import os, json
from typing import List, Dict, Any
from ..odds import fixtures_by_date, odds_by_fixture

try:
    from openai import OpenAI
    _has_openai = True
except ImportError:
    _has_openai = False

MODEL_NAME = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

def _make_prompt(fixture: Dict[str, Any], odds: Dict[str, Any]) -> str:
    home = fixture["teams"]["home"]["name"]
    away = fixture["teams"]["away"]["name"]
    league = fixture["league"]["name"]
    return (
        f"Do an in-depth football match analysis for {home} vs {away} in {league}. "
        "Focus on recent form, goals, BTTS patterns, and safest educational markets. "
        "Return JSON with: title, summary, safest_markets, observations."
    )

def build(date: str) -> List[Dict[str, Any]]:
    fixtures = fixtures_by_date(date)
    fixtures = fixtures[:10]  # limit
    legs = []
    openai_key = os.getenv("OPENAI_API_KEY", "")
    client = None
    if _has_openai and openai_key:
        client = OpenAI(api_key=openai_key)

    for f in fixtures:
        fid = f["fixture"]["id"]
        home = f["teams"]["home"]["name"]
        away = f["teams"]["away"]["name"]
        analysis_payload: Any = {"note": "OPENAI not configured"}
        if client:
            odds = odds_by_fixture(fid)
            prompt = _make_prompt(f, odds)
            try:
                resp = client.responses.create(
                    model=MODEL_NAME,
                    input=prompt,
                    format="json_object"
                )
                raw = resp.output[0].content[0].text
                try:
                    analysis_payload = json.loads(raw)
                except Exception:
                    analysis_payload = {"raw": raw}
            except Exception as e:
                analysis_payload = {"error": str(e)}
        legs.append({
            "fixture_id": fid,
            "market": "ANALYSIS",
            "pick": "AI_ANALYSIS",
            "odds": 1.00,
            "label": f"{home} vs {away}",
            "analysis": analysis_payload
        })
    return legs
