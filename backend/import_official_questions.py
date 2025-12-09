import requests
import sqlite3
import json
from time import sleep
from pathlib import Path

DB_PATH = Path(__file__).parent / "flash_neiga.db"
API_URL = "https://www.gov.il/fr/departments/dynamiccollectors/theoryexamhe_data"
PAGE_SIZE = 1000


def create_table(conn: sqlite3.Connection):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS questions (
            id TEXT PRIMARY KEY,
            text TEXT NOT NULL,
            category TEXT,
            explanation TEXT,
            options_json TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    conn.commit()


def fetch_page(skip: int):
    url = f"{API_URL}?skip={skip}"
    r = requests.get(url, timeout=20)
    r.raise_for_status()
    body = r.json()
    data = body.get("data", [])
    return data


def map_question(raw: dict):
    text = raw.get("Question") or raw.get("question") or ""
    category = raw.get("Sujet") or raw.get("Category") or "Autre"
    explanation = raw.get("Explication") or raw.get("explanation") or None
    # L’API officielle ne fournit pas les options QCM
    options = []
    return text, category, explanation, json.dumps(options, ensure_ascii=False)


def insert_question(conn: sqlite3.Connection, q: tuple):
    # Generate a deterministic id from text+category to avoid duplicates
    import hashlib
    text, category, explanation, options_json = q
    hash_id = hashlib.sha1(f"{text}||{category}".encode("utf-8")).hexdigest()
    conn.execute(
        """
        INSERT OR IGNORE INTO questions (id, text, category, explanation, options_json)
        VALUES (?, ?, ?, ?, ?)
        """,
        (hash_id, text, category, explanation, options_json),
    )


def import_all():
    conn = sqlite3.connect(DB_PATH.as_posix())
    create_table(conn)

    skip = 0
    total = 0

    print("📥 Début d'import officiel...")

    while True:
        print(f"→ Récupération page skip={skip} ...")
        chunk = fetch_page(skip)

        if not chunk:
            print("✔ Fin de pagination, plus aucune donnée.")
            break

        for raw_q in chunk:
            mapped = map_question(raw_q)
            insert_question(conn, mapped)
            total += 1

        conn.commit()

        if len(chunk) < PAGE_SIZE:
            break

        skip += PAGE_SIZE
        sleep(0.3)  # protéger l'API

    conn.close()
    print(f"🎉 Import terminé : {total} questions importées (doublons ignorés).")


if __name__ == "__main__":
    import_all()
