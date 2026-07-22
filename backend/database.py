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
    Checks for and adds missing columns to all tables if needed.
    Supports both SQLite (local) and PostgreSQL (production).
    """
    logger.info("🔍 Checking database schema integrity...")
    
    try:
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        
        # Define expected columns for critical tables
        # Using a controlled dictionary prevents SQL injection
        expected_columns = {
            'traffic_signs': ['id', 'number', 'name', 'description', 'image_url', 'category', 'explanation', 'created_at'],
            'questions': ['id', 'text', 'category', 'options', 'explanation', 'created_at'],
            'users': ['id', 'email', 'hashed_password', 'first_name', 'last_name', 'created_at'],
        }
        
        # Check each table
        for table_name, expected_cols in expected_columns.items():
            # Validate table name is in our controlled list before using in SQL
            if table_name not in expected_columns:
                continue
                
            if table_name not in tables:
                logger.info(f"⚠️  {table_name} table doesn't exist yet, will be created by init_db()")
                continue
            
            # Get existing columns
            existing_columns = [col['name'] for col in inspector.get_columns(table_name)]
            logger.info(f"📋 Checking {table_name} table - found columns: {existing_columns}")
            
            # Find missing columns
            missing_columns = [col for col in expected_cols if col not in existing_columns]
            
            if missing_columns:
                logger.warning(f"⚠️  {table_name} table is missing {len(missing_columns)} column(s): {missing_columns}")
                
                # Add missing columns
                for col_name in missing_columns:
                    try:
                        logger.info(f"🔧 Adding '{col_name}' column to {table_name} table...")
                        
                        with engine.connect() as conn:
                            # Validate column name against expected list
                            if col_name not in expected_cols:
                                logger.error(f"❌ Column '{col_name}' not in expected schema, skipping")
                                continue
                            
                            # Determine column type based on name
                            if col_name == 'created_at':
                                # Use TIMESTAMP with default for PostgreSQL, DATETIME for SQLite
                                if 'postgresql' in str(engine.url):
                                    sql = text(f"ALTER TABLE {table_name} ADD COLUMN {col_name} TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
                                else:
                                    sql = text(f"ALTER TABLE {table_name} ADD COLUMN {col_name} DATETIME DEFAULT CURRENT_TIMESTAMP")
                            elif col_name in ['explanation', 'description', 'text']:
                                sql = text(f"ALTER TABLE {table_name} ADD COLUMN {col_name} TEXT")
                            else:
                                # Default to VARCHAR for other string columns
                                sql = text(f"ALTER TABLE {table_name} ADD COLUMN {col_name} VARCHAR")
                            
                            conn.execute(sql)
                            conn.commit()
                            logger.info(f"✅ Successfully added '{col_name}' column to {table_name} table")
                    except Exception as e:
                        logger.error(f"❌ Failed to add '{col_name}' column to {table_name}: {e}")
                        # Continue with other columns even if one fails
            else:
                logger.info(f"✅ {table_name} table schema is up to date")
        
        logger.info("✅ Schema validation completed")
            
    except Exception as e:
        logger.error(f"❌ Error checking/updating schema: {e}", exc_info=True)
        # Don't raise - allow app to continue starting up
        logger.warning("⚠️  Application will continue but database schema may be incomplete")
