import json, os, random
from datetime import datetime, timezone

PUBLIC_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "public")
os.makedirs(PUBLIC_DIR, exist_ok=True)

def _read(name: str):
    fp = os.path.join(PUBLIC_DIR, name)
    if not os.path.exists(fp):
        return None
    with open(fp, "r", encoding="utf-8") as f:
        return json.load(f)

def _write(name: str, data):
    fp = os.path.join(PUBLIC_DIR, name)
    with open(fp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def _mark_leg(leg):
    hit = random.choice([True, False])
    leg["result"] = "✅" if hit else "❌"
    return hit

def _process_ticket_file(name: str):
    data = _read(name)
    if not data:
        return
    for t in data.get("tickets", []):
        all_hit = True
        for leg in t.get("legs", []):
            ok = _mark_leg(leg)
            if not ok:
                all_hit = False
        t["status"] = "✅" if all_hit else "❌"
    data["evaluated_at"] = datetime.now(timezone.utc).isoformat()
    _write(name, data)

def run():
    for fn in ("2plus.json", "3plus.json", "4plus.json"):
        _process_ticket_file(fn)

if __name__ == "__main__":
    run()
