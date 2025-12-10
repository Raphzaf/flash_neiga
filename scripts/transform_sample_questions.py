import json
from pathlib import Path
from bs4 import BeautifulSoup
import uuid

SRC_PATH = Path(__file__).resolve().parents[1] / "data" / "sample_questions.json"
OUT_PATH = Path(__file__).resolve().parents[1] / "data" / "data_v3.json"

def extract_options(html: str):
    opts = []
    if not html:
        return opts
    soup = BeautifulSoup(html, "html.parser")
    # Each li contains a span; the correct answer span has id like 'correctAnswerXXXX'
    for li in soup.find_all("li"):
        span = li.find("span")
        if not span:
            continue
        text = span.get_text(strip=True)
        is_correct = False
        # Mark correct if id contains 'correctAnswer'
        sid = span.get("id") or ""
        if "correctAnswer" in sid:
            is_correct = True
        opts.append({
            "id": str(uuid.uuid4()),
            "text": text,
            "is_correct": is_correct
        })
    return opts

def main():
    src = json.loads(SRC_PATH.read_text(encoding="utf-8"))
    items = src.get("items") or []
    out = []
    for item in items:
        raw = item.get("raw", {})
        text = raw.get("title2") or raw.get("title")
        category = raw.get("category") or "Autre"
        html = raw.get("description4")
        options = extract_options(html)
        explanation = None
        out.append({
            "text": text,
            "category": category,
            "options": options,
            "explanation": explanation
        })
    OUT_PATH.write_text(json.dumps({"questions": out}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote transformed questions to {OUT_PATH} (count={len(out)})")

if __name__ == "__main__":
    main()
