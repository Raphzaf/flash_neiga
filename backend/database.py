from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from pathlib import Path
import os

# Support both PostgreSQL (production) and SQLite (local development)
# Check for DATABASE_URL environment variable first
DATABASE_URL = os.environ.get("DATABASE_URL")

if not DATABASE_URL:
    # Fallback to SQLite for local development
    BACKEND_DIR = Path(__file__).parent
    DB_PATH = BACKEND_DIR / "flash_neiga.db"
    DATABASE_URL = f"sqlite:///{DB_PATH.as_posix()}"
    connect_args = {"check_same_thread": False}
else:
    # Production - PostgreSQL
    # Render provides postgres:// but SQLAlchemy needs postgresql://
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    connect_args = {}

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    echo=False
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
