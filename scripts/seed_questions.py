"""
Script pour convertir les questions scrapées en documents MongoDB
et les insérer dans la base de données
"""

import json
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timezone
import os
import uuid
from dotenv import load_dotenv
from pathlib import Path

# Load environment
ROOT_DIR = Path(__file__).parent.parent
load_dotenv(ROOT_DIR / 'backend' / '.env')

MONGO_URL = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
DB_NAME = os.environ.get('DB_NAME', 'flash_neiga')

async def seed_questions_from_json(json_file: str):
    """
    Charge les questions depuis un fichier JSON et les insère dans MongoDB
    """
    # Connexion à MongoDB
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    
    print(f"Connexion à MongoDB: {MONGO_URL}/{DB_NAME}")
    
    # Charger les questions depuis le fichier
    with open(json_file, 'r', encoding='utf-8') as f:
        questions_data = json.load(f)
    
    print(f"Chargement de {len(questions_data)} questions depuis {json_file}")
    
    # Vider la collection existante
    result = await db.questions.delete_many({})
    print(f"Suppression de {result.deleted_count} anciennes questions")
    
    # Préparer les documents pour insertion
    questions_to_insert = []
    
    for q in questions_data:
        # S'assurer que les options ont un format correct
        options = []
        for opt in q.get("options", []):
            if isinstance(opt, dict) and "text" in opt:
                options.append({
                    "id": opt.get("id", str(uuid.uuid4())),
                    "text": opt["text"],
                    "is_correct": opt.get("is_correct", False)
                })
        
        # Si pas assez d'options, on skip (minimum 2 pour un QCM)
        if len(options) < 2:
            print(f"⚠️  Question {q.get('number', '?')} ignorée (pas assez d'options)")
            continue
        
        # Vérifier qu'il y a au moins une bonne réponse
        if not any(opt["is_correct"] for opt in options):
            print(f"⚠️  Question {q.get('number', '?')} ignorée (aucune bonne réponse)")
            continue
        
        doc = {
            "_id": str(uuid.uuid4()),
            "text": q["text"],
            "category": q.get("category", "Général"),
            "image_url": q.get("image_url"),
            "options": options,
            "explanation": q.get("explanation", ""),
            "created_at": datetime.now(timezone.utc),
            "question_number": q.get("number")
        }
        
        questions_to_insert.append(doc)
    
    # Insertion dans MongoDB
    if questions_to_insert:
        result = await db.questions.insert_many(questions_to_insert)
        print(f"✓ {len(result.inserted_ids)} questions insérées avec succès")
    else:
        print("✗ Aucune question valide à insérer")
    
    # Fermer la connexion
    client.close()
    
    # Afficher un résumé par catégorie
    print("\n=== Résumé par catégorie ===")
    categories = {}
    for q in questions_to_insert:
        cat = q["category"]
        categories[cat] = categories.get(cat, 0) + 1
    
    for cat, count in sorted(categories.items(), key=lambda x: x[1], reverse=True):
        print(f"  {cat}: {count} questions")

async def create_sample_questions():
    """
    Crée quelques questions d'exemple si le scraping n'a pas encore été fait
    """
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    
    sample_questions = [
        {
            "_id": str(uuid.uuid4()),
            "text": "Qui a le devoir de connaître le code de la route et de s'y conformer?",
            "category": "Les règles de conduite",
            "image_url": None,
            "options": [
                {"id": str(uuid.uuid4()), "text": "Uniquement les conducteurs professionnels", "is_correct": False},
                {"id": str(uuid.uuid4()), "text": "Tous les usagers de la route", "is_correct": True},
                {"id": str(uuid.uuid4()), "text": "Seulement les propriétaires de véhicules", "is_correct": False},
                {"id": str(uuid.uuid4()), "text": "Uniquement les nouveaux conducteurs", "is_correct": False}
            ],
            "explanation": "Tous les usagers de la route, qu'ils soient conducteurs, piétons ou cyclistes, ont le devoir de connaître et respecter le code de la route.",
            "created_at": datetime.now(timezone.utc),
            "question_number": "0001"
        },
        {
            "_id": str(uuid.uuid4()),
            "text": "À quelle distance minimale d'un passage piéton est-il interdit de stationner?",
            "category": "Stationnement",
            "image_url": None,
            "options": [
                {"id": str(uuid.uuid4()), "text": "3 mètres", "is_correct": False},
                {"id": str(uuid.uuid4()), "text": "5 mètres", "is_correct": False},
                {"id": str(uuid.uuid4()), "text": "12 mètres", "is_correct": True},
                {"id": str(uuid.uuid4()), "text": "Il n'y a pas de restriction", "is_correct": False}
            ],
            "explanation": "Il est interdit de stationner à moins de 12 mètres d'un passage piéton pour garantir une bonne visibilité.",
            "created_at": datetime.now(timezone.utc),
            "question_number": "SAMPLE_001"
        }
    ]
    
    await db.questions.delete_many({})
    result = await db.questions.insert_many(sample_questions)
    print(f"✓ {len(result.inserted_ids)} questions d'exemple créées")
    
    client.close()

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        json_file = sys.argv[1]
        print(f"=== Import des questions depuis {json_file} ===\n")
        asyncio.run(seed_questions_from_json(json_file))
    else:
        print("=== Création de questions d'exemple ===\n")
        print("Usage: python seed_questions.py <fichier_json>")
        print("Ou lancer sans argument pour créer des questions d'exemple\n")
        
        response = input("Créer des questions d'exemple? (o/n): ")
        if response.lower() == 'o':
            asyncio.run(create_sample_questions())
