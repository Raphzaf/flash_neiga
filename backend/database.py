from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import declarative_base, sessionmaker
from pathlib import Path
import os
import logging

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

logger = logging.getLogger(__name__)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def ensure_schema_updated():
    """
    Ensure database schema is up to date with model definitions.
    Specifically checks for and adds the 'explanation' column to traffic_signs table if missing.
    """
    logger.info("🔍 Checking database schema integrity...")
    
    try:
        inspector = inspect(engine)
        
        # Check if traffic_signs table exists
        if 'traffic_signs' not in inspector.get_table_names():
            logger.info("⚠️  traffic_signs table doesn't exist yet, will be created by init_db()")
            return
        
        # Get existing columns in traffic_signs table
        columns = [col['name'] for col in inspector.get_columns('traffic_signs')]
        logger.info(f"📋 Found columns in traffic_signs: {columns}")
        
        # Check if explanation column is missing
        if 'explanation' not in columns:
            logger.warning("⚠️  'explanation' column is missing from traffic_signs table")
            logger.info("🔧 Adding 'explanation' column to traffic_signs table...")
            
            with engine.connect() as conn:
                # Both SQLite and PostgreSQL use the same ALTER TABLE syntax for adding a TEXT column
                sql = text("ALTER TABLE traffic_signs ADD COLUMN explanation TEXT")
                conn.execute(sql)
                conn.commit()
                logger.info("✅ Successfully added 'explanation' column to traffic_signs table")
        else:
            logger.info("✅ Schema is up to date - 'explanation' column exists")
            
    except Exception as e:
        logger.error(f"❌ Error checking/updating schema: {e}", exc_info=True)
        # Don't raise - allow app to continue starting up
        logger.warning("⚠️  Application will continue but database schema may be incomplete")
