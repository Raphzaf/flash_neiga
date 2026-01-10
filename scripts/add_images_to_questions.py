#!/usr/bin/env python3
import json
import re
import os
from pathlib import Path

print("\n🎨 Enrichissement des questions")
print("=" * 60)

# Détection automatique :  PostgreSQL ou SQLite
DATABASE_URL = os.getenv('DATABASE_URL')

if DATABASE_URL and 'postgres' in DATABASE_URL: 
    # PostgreSQL (Render)
    print("✅ Mode PostgreSQL détecté")
    import psycopg2
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    placeholder = "%s"
else:
    # SQLite (local)
    print("✅ Mode SQLite détecté")
    import sqlite3
    script_dir = Path(__file__).parent
    db_path = script_dir. parent / "database.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    placeholder = "?"

print("✅ Connecté à la base de données")

cursor.execute("SELECT COUNT(*) FROM questions")
count = cursor.fetchone()[0]
print(f"✅ {count} questions trouvées")

# Charger les fichiers
script_dir = Path(__file__).parent
data_dir = script_dir. parent. parent / "data"

with open(data_dir / 'data_v3.json', 'r', encoding='utf-8') as f:
    data_v3 = json.load(f)

with open(data_dir / 'sample_questions. json', 'r', encoding='utf-8') as f:
    sample = json.load(f)

print(f"✅ {len(data_v3['questions'])} questions chargées")

# Ajouter la colonne
try:
    cursor.execute("ALTER TABLE questions ADD COLUMN image_url TEXT")
    conn.commit()
    print("✅ Colonne image_url ajoutée")
except Exception as e:
    conn. rollback()
    if "exist" in str(e).lower() or "duplicate" in str(e).lower():
        print("ℹ️  Colonne image_url existe déjà")
    else:
        print(f"⚠️  {e}")

# Fonction d'extraction
def extract_image_url(html):
    if not html:
        return None
    match = re.search(r'<img[^>]+src="([^">]+)"', html)
    return match.group(1) if match else None

# Enrichissement
print("\n🖼️  Enrichissement en cours...")
updated = 0
with_images = 0

for i, question in enumerate(data_v3['questions']):
    if i < len(sample['items']):
        img_url = extract_image_url(sample['items'][i].get('raw', {}).get('description4', ''))
        if img_url:
            with_images += 1
            cursor.execute(
                f"UPDATE questions SET image_url = {placeholder} WHERE text = {placeholder}",
                (img_url, question['text'])
            )
            updated += cursor.rowcount
    
    if (i + 1) % 200 == 0:
        print(f"   📊 {i + 1}/{len(data_v3['questions'])}...")
        conn.commit()

conn.commit()
conn.close()

print("\n" + "=" * 60)
print("✅ ENRICHISSEMENT TERMINÉ !")
print("=" * 60)
print(f"\n📊 Questions avec images : {with_images}")
print(f"📊 Mises à jour en DB : {updated}")
print(f"💡 Pourcentage :  {with_images * 100 / len(data_v3['questions']):.1f}%\n")
