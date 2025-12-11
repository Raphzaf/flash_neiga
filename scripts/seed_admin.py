import argparse
import uuid
from pathlib import Path

from backend.database import SessionLocal, Base, engine
from backend.models import UserDB
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def ensure_tables():
    try:
        Base.metadata.create_all(bind=engine)
    except Exception as e:
        print(f"[seed_admin] Failed to create tables: {e}")
        raise


def upsert_admin(email: str, password: str):
    ensure_tables()
    db = SessionLocal()
    try:
        user = db.query(UserDB).filter(UserDB.email == email).first()
        if user:
            user.hashed_password = hash_password(password)
            db.add(user)
            action = "updated"
        else:
            user = UserDB(
                id=str(uuid.uuid4()),
                email=email,
                hashed_password=hash_password(password),
            )
            db.add(user)
            action = "created"
        db.commit()
        print(f"[seed_admin] Admin user {action}: {email}")
        return user.id
    except Exception as e:
        db.rollback()
        print(f"[seed_admin] Error: {e}")
        raise
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description="Seed or update an admin user.")
    parser.add_argument("--email", "-e", default="admin@gmail.com", help="Admin email (default: admin@gmail.com)")
    parser.add_argument("--password", "-p", default="admin", help="Admin password (default: admin)")
    args = parser.parse_args()

    user_id = upsert_admin(args.email, args.password)
    print(f"[seed_admin] Done. User ID: {user_id}")


if __name__ == "__main__":
    main()
