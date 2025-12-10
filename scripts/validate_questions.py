import json
from pathlib import Path
from collections import Counter

DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "data_v3.json"

def is_playable(q: dict) -> bool:
    opts = q.get("options") or []
    if not isinstance(opts, list) or len(opts) < 2:
        return False
    return any(bool(o.get("is_correct")) for o in opts if isinstance(o, dict))

def main():
    if not DATA_PATH.exists():
        print(f"File not found: {DATA_PATH}")
        return
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    if isinstance(data, dict) and "questions" in data:
        data = data["questions"]
    if not isinstance(data, list):
        print("Invalid format: expected list of questions")
        return
    total = len(data)
    playable = sum(1 for q in data if is_playable(q))
    missing_text = sum(1 for q in data if not q.get("text"))
    missing_category = sum(1 for q in data if not q.get("category"))
    missing_options = sum(1 for q in data if not q.get("options"))
    dup_counter = Counter((q.get("text"), q.get("category")) for q in data)
    duplicates = sum(1 for k, c in dup_counter.items() if c > 1)
    print("=== Validation Report ===")
    print(f"Total questions: {total}")
    print(f"Playable questions: {playable}")
    print(f"Missing text: {missing_text}")
    print(f"Missing category: {missing_category}")
    print(f"Missing options: {missing_options}")
    print(f"Duplicate (text+category) pairs: {duplicates}")

if __name__ == "__main__":
    main()
