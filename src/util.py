from datetime import datetime, timezone

def today_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")

def ensure_list(x):
    return x if isinstance(x, list) else [x]
