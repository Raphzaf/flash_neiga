import asyncio
import os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
from pathlib import Path
from datetime import datetime, timezone
import uuid
from passlib.context import CryptContext

# Setup
ROOT_DIR = Path(__file__).parent.parent / 'backend'
load_dotenv(ROOT_DIR / '.env')

MONGO_URL = os.environ['MONGO_URL']
DB_NAME = os.environ.get('DB_NAME', 'flash_neiga')

client = AsyncIOMotorClient(MONGO_URL)
db = client[DB_NAME]
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_hash(password):
    return pwd_context.hash(password)

async def seed():
    print("Seeding database...")
    
    # 1. Users
    await db.users.delete_many({})
    user_id = str(uuid.uuid4())
    await db.users.insert_one({
        "_id": user_id,
        "email": "test@example.com",
        "hashed_password": get_hash("password123"),
        "full_name": "Test User",
        "role": "student",
        "created_at": datetime.now(timezone.utc)
    })
    print("User created: test@example.com / password123")

    # 2. Questions (Generate 40 questions)
    await db.questions.delete_many({})
    categories = ["Priorités", "Croisements", "Signalisations", "Mécanique"]
    
    questions = []
    for i in range(40):
        cat = categories[i % 4]
        q_id = str(uuid.uuid4())
        
        # Simple logic for options
        is_true = i % 2 == 0
        
        questions.append({
            "_id": q_id,
            "text": f"Question Test {i+1}: Ceci est une question de la catégorie {cat}. Quelle est la bonne réponse ?",
            "category": cat,
            "image_url": None, # "https://placehold.co/600x400?text=Situation+Routiere",
            "explanation": f"Ceci est l'explication pour la question {i+1}. La règle est simple...",
            "created_at": datetime.now(timezone.utc),
            "options": [
                {"id": str(uuid.uuid4()), "text": "Réponse A (Correcte)" if is_true else "Réponse A", "is_correct": is_true},
                {"id": str(uuid.uuid4()), "text": "Réponse B (Correcte)" if not is_true else "Réponse B", "is_correct": not is_true},
                {"id": str(uuid.uuid4()), "text": "Réponse C", "is_correct": False},
                {"id": str(uuid.uuid4()), "text": "Réponse D", "is_correct": False}
            ]
        })
    
    await db.questions.insert_many(questions)
    print(f"Created {len(questions)} questions.")

    # 3. Signs
    await db.signs.delete_many({})
    signs = [
        {
            "_id": str(uuid.uuid4()),
            "name": "Stop",
            "category": "Priorité",
            "description": "Arrêt absolu obligatoire à l'intersection.",
            "image_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/f/f9/Stop_sign.jpg/600px-Stop_sign.jpg"
        },
        {
            "_id": str(uuid.uuid4()),
            "name": "Sens Interdit",
            "category": "Interdiction",
            "description": "Interdiction de circuler dans ce sens.",
            "image_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/2/25/France_road_sign_B1.svg/600px-France_road_sign_B1.svg.png"
        },
        {
            "_id": str(uuid.uuid4()),
            "name": "Cédez le passage",
            "category": "Priorité",
            "description": "Vous n'avez pas la priorité.",
            "image_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a1/France_road_sign_AB3a.svg/600px-France_road_sign_AB3a.svg.png"
        },
         {
            "_id": str(uuid.uuid4()),
            "name": "Passage Piéton",
            "category": "Danger",
            "description": "Annonce un passage pour piétons.",
            "image_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/8/8c/France_road_sign_A13b.svg/600px-France_road_sign_A13b.svg.png"
        }
    ]
    await db.signs.insert_many(signs)
    print(f"Created {len(signs)} signs.")

    print("Seed complete.")

if __name__ == "__main__":
    asyncio.run(seed())
