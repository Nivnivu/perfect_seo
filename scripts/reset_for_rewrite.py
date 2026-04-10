"""
Reset update guards so ALL Everest posts are eligible for a fresh rewrite.

Clears:
  - "hurt" verdicts in everest_impact_verdicts.json → "reset"
  - updated_at timestamps in everest_update_history.json → 90 days ago
    (so all cooldown windows are expired)

Run from project root: python scripts/reset_for_rewrite.py
"""
import sys, io, os, json
from datetime import datetime, timezone, timedelta
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

VERDICTS_PATH  = "output/everest_impact_verdicts.json"
HISTORY_PATH   = "output/everest_update_history.json"
OLD_DATE       = (datetime.now(timezone.utc) - timedelta(days=90)).isoformat()


def reset_verdicts():
    with open(VERDICTS_PATH, encoding="utf-8") as f:
        verdicts = json.load(f)

    changed = 0
    for title, entry in verdicts.items():
        if entry.get("status") == "hurt":
            entry["status"] = "reset"
            entry["reset_reason"] = "manual reset — rewriting with improved prompts"
            changed += 1

    with open(VERDICTS_PATH, "w", encoding="utf-8") as f:
        json.dump(verdicts, f, ensure_ascii=False, indent=2)

    print(f"[verdicts] Reset {changed} hurt verdicts to 'reset' in {VERDICTS_PATH}")


def reset_cooldowns():
    with open(HISTORY_PATH, encoding="utf-8") as f:
        history = json.load(f)

    changed = 0
    for post_id, entry in history.items():
        if entry.get("updated_at") or entry.get("timestamp"):
            key = "updated_at" if "updated_at" in entry else "timestamp"
            entry[key] = OLD_DATE
            changed += 1

    with open(HISTORY_PATH, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

    print(f"[history]  Reset {changed} updated_at timestamps to 90 days ago in {HISTORY_PATH}")


if __name__ == "__main__":
    print("Resetting Everest update guards for full rewrite...")
    reset_verdicts()
    reset_cooldowns()
    print("\nDone. Run: python run.py --config config.everst.yaml update")
