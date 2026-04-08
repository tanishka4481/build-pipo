"""
seed_demo_data.py
==================
Seeds the DB with a realistic week of data for demo day.
Run ONCE before demo. Shows judges a real product, not an empty screen.

Usage:
    python3 seed_demo_data.py
    python3 seed_demo_data.py --server https://popi-api.onrender.com
"""

import requests
import random
import argparse
import json
from datetime import datetime, timedelta, timezone

BASE    = "http://localhost:8000"
CHILD   = {
    "name":           "Arjun",
    "age":            4,
    "disorder_type":  "articulation",
    "target_phoneme": "s",
    "notes":          "Initial /s/ substitution — producing /th/ for /s/. Good compliance, responds well to modeling.",
}
WORDS   = [
    {"word": "sun",   "prompt": "Can you help me say... sun?",   "position": "initial"},
    {"word": "sea",   "prompt": "Can you help me say... sea?",   "position": "initial"},
    {"word": "sock",  "prompt": "Can you help me say... sock?",  "position": "initial"},
    {"word": "soap",  "prompt": "Can you help me say... soap?",  "position": "initial"},
    {"word": "sand",  "prompt": "Can you help me say... sand?",  "position": "initial"},
    {"word": "bus",   "prompt": "Can you help me say... bus?",   "position": "final"},
    {"word": "house", "prompt": "Can you help me say... house?", "position": "final"},
]


def seed(base_url: str):
    print(f"Seeding demo data → {base_url}")

    # 1. Health check
    try:
        r = requests.get(f"{base_url}/health", timeout=5)
        r.raise_for_status()
        print("  ✓ Server reachable")
    except Exception as e:
        print(f"  ✗ Cannot reach server: {e}")
        return

    # 2. Create child
    r = requests.post(f"{base_url}/child/create", json=CHILD, timeout=5)
    r.raise_for_status()
    child_id = r.json()["child_id"]
    print(f"  ✓ Child created: {CHILD['name']} ({child_id[:8]}...)")

    # 3. Push word plan
    today = datetime.now(timezone.utc).date()
    monday = today - timedelta(days=today.weekday())
    r = requests.post(f"{base_url}/plan/push", json={
        "child_id":       child_id,
        "week_start":     monday.isoformat(),
        "word_list":      WORDS,
        "start_level":    "word_init",
        "pass_threshold": 0.70,
        "max_attempts":   5,
    }, timeout=5)
    r.raise_for_status()
    print(f"  ✓ Word plan pushed: {len(WORDS)} words for week of {monday}")

    # 4. Seed 5 days of sessions
    # Improving trend: starts ~0.42 avg, ends ~0.71 avg
    day_configs = [
        {"days_ago": 5, "n_attempts": 8,  "base_score": 0.40, "variance": 0.12},
        {"days_ago": 4, "n_attempts": 10, "base_score": 0.48, "variance": 0.12},
        {"days_ago": 3, "n_attempts": 9,  "base_score": 0.55, "variance": 0.11},
        {"days_ago": 2, "n_attempts": 11, "base_score": 0.63, "variance": 0.10},
        {"days_ago": 1, "n_attempts": 12, "base_score": 0.70, "variance": 0.09},
    ]

    for day in day_configs:
        session_time = datetime.now(timezone.utc) - timedelta(days=day["days_ago"])

        # start session
        r = requests.post(f"{base_url}/session/start", json={
            "child_id":       child_id,
            "level":          "word_init",
            "target_phoneme": "s",
        }, timeout=5)
        r.raise_for_status()
        session_id = r.json()["session_id"]

        scores = []
        for i in range(day["n_attempts"]):
            score = min(max(day["base_score"] + random.uniform(-day["variance"], day["variance"]), 0.15), 0.95)
            scores.append(score)

        avg = round(sum(scores) / len(scores), 3)

        # end session with computed avg
        requests.post(f"{base_url}/session/end", json={
            "session_id":    session_id,
            "total_attempts": day["n_attempts"],
            "avg_score":     avg,
        }, timeout=5)

        date_str = (datetime.now().date() - timedelta(days=day["days_ago"])).isoformat()
        print(f"  ✓ Day -{day['days_ago']} ({date_str}): {day['n_attempts']} attempts, avg score {avg:.2f}")

    # 5. Summary
    r = requests.get(f"{base_url}/children", timeout=5)
    r.raise_for_status()
    children = r.json()["children"]
    child_data = next((c for c in children if c["id"] == child_id), None)

    print()
    print("=" * 50)
    print("DEMO DATA SEEDED")
    print("=" * 50)
    print(f"Child:          {CHILD['name']}, age {CHILD['age']}")
    print(f"Child ID:       {child_id[:8]}...")
    print(f"Sessions:       5 (Mon–Fri)")
    print(f"Score trend:    0.40 → 0.70 (improving)")
    print(f"Word plan:      {len(WORDS)} words pushed")
    print()
    print("Dashboard will show:")
    print("  - 5-day practice streak")
    print("  - Improving score trend graph")
    print("  - Current word plan with 7 words")
    print("  - Child profile with SLP notes")
    print()
    print(f"Child ID for demo: {child_id}")
    print("Save this — you need it for laptop_demo.py CHILD_ID")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--server", default="http://localhost:8000",
                        help="Server URL (default: localhost)")
    args = parser.parse_args()
    seed(args.server)
