import os, time, requests
from typing import Dict, Any, Optional

API_BASE = "https://v3.football.api-sports.io"
API_KEY = os.getenv("API_FOOTBALL_KEY", "")
QPS_DELAY = 0.8
RETRIES = 3

_last_call = 0.0

def _throttle():
    global _last_call
    delta = time.time() - _last_call
    if delta < QPS_DELAY:
        time.sleep(QPS_DELAY - delta)
    _last_call = time.time()

def get(path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    if not API_KEY:
        raise RuntimeError("API_FOOTBALL_KEY not set")
    url = f"{API_BASE}{path}"
    headers = {
        "x-apisports-key": API_KEY,
        "Accept": "application/json",
    }
    for _ in range(RETRIES):
        _throttle()
        r = requests.get(url, headers=headers, params=params, timeout=20)
        if r.status_code == 200:
            return r.json()
        time.sleep(2)
    raise RuntimeError(f"API error {r.status_code}: {r.text}")
