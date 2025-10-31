import json, os, time
from typing import Any, Optional

CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "public")
os.makedirs(CACHE_DIR, exist_ok=True)

def _path(key: str) -> str:
    return os.path.join(CACHE_DIR, f"{key}.cache.json")

def get(key: str, max_age_sec: int = 1800) -> Optional[Any]:
    fp = _path(key)
    if not os.path.exists(fp):
        return None
    try:
        with open(fp, "r", encoding="utf-8") as f:
            data = json.load(f)
        if time.time() - data["ts"] > max_age_sec:
            return None
        return data["value"]
    except Exception:
        return None

def set(key: str, value: Any) -> None:
    fp = _path(key)
    with open(fp, "w", encoding="utf-8") as f:
        json.dump({"ts": time.time(), "value": value}, f, ensure_ascii=False, indent=2)
