import json
import uuid
import sys
import time
from urllib.request import urlopen


API_BASE = "https://www.gov.il/fr/departments/dynamiccollectors/theoryexamhe_data?skip={skip}"


def fetch_all():
    all_items = []
    skip = 0
    page_size = 1000
    while True:
        url = API_BASE.format(skip=skip)
        with urlopen(url) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        items = data.get("data", [])
        all_items.extend(items)
        if len(items) == 0 or len(items) < page_size:
            break
        skip += page_size
        time.sleep(0.2)
    return all_items


def sql_escape(s: str) -> str:
    return s.replace("'", "''")


def to_insert_sql(items):
    stmts = []
    # Table: questions (id TEXT PK, text TEXT, category TEXT, options JSON, explanation TEXT, created_at DATETIME DEFAULT CURRENT_TIMESTAMP)
    for it in items:
        text = it.get("Question") or it.get("question") or it.get("text") or ""
        category = it.get("Sujet") or it.get("category") or "Autre"
        explanation = it.get("Explication") or it.get("explanation") or None

        # Many official entries do not include multiple-choice options; store empty list by default
        options = it.get("options") or []
        # Ensure options is list of dicts with id/text/is_correct if present
        norm_opts = []
        if isinstance(options, list):
            for opt in options:
                oid = str(opt.get("id") or uuid.uuid4())
                norm_opts.append({
                    "id": oid,
                    "text": str(opt.get("text") or ""),
                    "is_correct": bool(opt.get("is_correct") or False)
                })

        id_ = str(uuid.uuid4())
        text_sql = sql_escape(text)
        cat_sql = sql_escape(category)
        expl_sql = sql_escape(explanation) if explanation else None
        options_json = json.dumps(norm_opts, ensure_ascii=False)

        stmt = (
            "INSERT INTO questions (id, text, category, options, explanation) VALUES "
            f"('{id_}', '{text_sql}', '{cat_sql}', '{sql_escape(options_json)}', "
            + (f"'{expl_sql}'" if expl_sql is not None else "NULL")
            + ");"
        )
        stmts.append(stmt)
    return stmts


def main():
    out_path = sys.argv[1] if len(sys.argv) > 1 else "official_questions.sql"
    print("Fetching official questions...")
    items = fetch_all()
    print(f"Fetched {len(items)} items.")
    stmts = to_insert_sql(items)
    header = (
        "-- Flash Neiga: Official Questions Import\n"
        "-- Generated from gov.il dynamic collector\n"
        "BEGIN TRANSACTION;\n"
    )
    footer = "\nCOMMIT;\n"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(header)
        for s in stmts:
            f.write(s + "\n")
        f.write(footer)
    print(f"Wrote SQL to {out_path}")


if __name__ == "__main__":
    main()
