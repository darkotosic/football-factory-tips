from typing import List, Dict, Any

def pick_top(legs: List[Dict[str, Any]], n: int) -> List[Dict[str, Any]]:
    legs_sorted = sorted(legs, key=lambda x: x.get("odds", 1.0))
    return legs_sorted[:n]

def make_ticket(name: str, legs: List[Dict[str, Any]]) -> Dict[str, Any]:
    total_odds = 1.0
    for l in legs:
        total_odds *= float(l.get("odds", 1.0))
    return {
        "name": name,
        "legs": legs,
        "total_odds": round(total_odds, 2),
        "status": "pending"
    }
