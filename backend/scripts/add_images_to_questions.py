#!/usr/bin/env python3
"""
Script d'enrichissement des questions avec les URLs d'images.

Extrait les URLs d'images depuis sample_questions.json et les ajoute
à la table questions dans la base de données.

Usage:
    cd backend
    python scripts/add_images_to_questions.py
"""

import json
import sqlite3
import re
from pathlib import Path
import sys


def extract_image_url(html):
    """Extrait l'URL de l'image depuis le HTML"""
    if not html:
        return None
    # Support both single and double quotes for robustness
    match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', html)
    return match.group(1) if match else None


def add_images_to_database():
    print("\n🎨 Enrichissement des questions avec les images")
    print("=" * 60)
    
    # Chemins relatifs au script
    script_dir = Path(__file__).parent
    project_root = script_dir.parent.parent
    data_dir = project_root / "data"
    db_path = script_dir.parent / "flash_neiga.db"
    
    # 1. Charger les fichiers JSON
    print("\n📖 Chargement des fichiers...")
    with open(data_dir / 'data_v3.json', 'r', encoding='utf-8') as f:
        data_v3 = json.load(f)
    print(f"✅ data_v3.json chargé ({len(data_v3['questions'])} questions)")
    
    with open(data_dir / 'sample_questions.json', 'r', encoding='utf-8') as f:
        sample_questions = json.load(f)
    print(f"✅ sample_questions.json chargé ({len(sample_questions['items'])} items)")
    
    # Validation: Vérifier que les fichiers ont le même nombre d'éléments
    if len(data_v3['questions']) != len(sample_questions['items']):
        print(f"⚠️  AVERTISSEMENT : Nombre d'éléments différent !")
        print(f"   data_v3.json: {len(data_v3['questions'])} questions")
        print(f"   sample_questions.json: {len(sample_questions['items'])} items")
    
    # Validation: Vérifier que l'ordre correspond (premiers éléments)
    if len(data_v3['questions']) > 0 and len(sample_questions['items']) > 0:
        first_q_text = data_v3['questions'][0]['text']
        first_s_text = sample_questions['items'][0]['raw'].get('title2', '')
        if first_q_text != first_s_text:
            print(f"⚠️  AVERTISSEMENT : L'ordre des questions ne correspond pas !")
            print(f"   Premier élément data_v3: {first_q_text[:60]}...")
            print(f"   Premier élément sample: {first_s_text[:60]}...")
    
    # 2. Connexion à la base de données
    print(f"\n💾 Connexion à la base de données : {db_path}")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 3. Ajouter la colonne image_url si nécessaire
    print("\n🔧 Vérification du schéma de la table...")
    try:
        cursor.execute('ALTER TABLE questions ADD COLUMN image_url TEXT')
        print("✅ Colonne 'image_url' ajoutée à la table 'questions'")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e).lower():
            print("ℹ️  Colonne 'image_url' existe déjà")
        else:
            raise
    
    # 4. Extraire et mettre à jour les images
    print("\n🖼️  Extraction et mise à jour des images...")
    # Note: Les questions dans data_v3.json et sample_questions.json sont dans le même ordre
    # Cette correspondance par index est basée sur la source de données d'origine
    updated = 0
    with_images = 0
    without_images = 0
    
    for i, question in enumerate(data_v3['questions']):
        if i < len(sample_questions['items']):
            sample = sample_questions['items'][i]
            description4 = sample.get('raw', {}).get('description4', '')
            image_url = extract_image_url(description4)
            
            if image_url:
                with_images += 1
                # Mise à jour en utilisant le texte comme clé unique
                cursor.execute(
                    'UPDATE questions SET image_url = ? WHERE text = ?',
                    (image_url, question['text'])
                )
                if cursor.rowcount > 0:
                    updated += 1
            else:
                without_images += 1
        
        # Afficher la progression tous les 200 questions
        if (i + 1) % 200 == 0:
            print(f"   Progression : {i + 1}/{len(data_v3['questions'])} questions traitées...")
    
    conn.commit()
    conn.close()
    
    # 5. Afficher les statistiques
    print("\n" + "=" * 60)
    print("✅ Enrichissement terminé !")
    print("=" * 60)
    print(f"\n📊 Statistiques :")
    print(f"   • Questions traitées        : {len(data_v3['questions'])}")
    print(f"   • Questions avec images     : {with_images}")
    print(f"   • Questions sans images     : {without_images}")
    print(f"   • Questions mises à jour DB : {updated}")
    print(f"\n💡 Pourcentage avec images : {with_images * 100 / len(data_v3['questions']):.1f}%")
    print()


if __name__ == '__main__':
    try:
        add_images_to_database()
    except FileNotFoundError as e:
        print(f"\n❌ Erreur : Fichier non trouvé - {e}")
        sys.exit(1)
    except sqlite3.Error as e:
        print(f"\n❌ Erreur de base de données : {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Erreur inattendue : {e}")
        sys.exit(1)
