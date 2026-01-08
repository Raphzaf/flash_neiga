#!/usr/bin/env python3
"""
Migration script to add explanation column to traffic_signs table
Usage: python backend/migrations/add_explanation_column.py
"""
import sys
import os
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text, inspect
from database import engine, Base, DATABASE_URL
from models import TrafficSignDB
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_migration():
    """Add explanation column to traffic_signs table if it doesn't exist"""
    logger.info("=" * 60)
    logger.info("🔧 Running migration: Add explanation column to traffic_signs")
    logger.info("=" * 60)
    logger.info(f"📊 Database: {DATABASE_URL.split('@')[-1] if '@' in DATABASE_URL else 'SQLite'}")
    
    try:
        # Use inspector to check if table and column exist
        inspector = inspect(engine)
        
        # Check if table exists
        if 'traffic_signs' not in inspector.get_table_names():
            logger.warning("⚠️  traffic_signs table doesn't exist")
            logger.info("📝 Creating all tables from models...")
            Base.metadata.create_all(bind=engine)
            logger.info("✅ All tables created successfully")
            return
        
        # Check if column exists
        columns = [col['name'] for col in inspector.get_columns('traffic_signs')]
        logger.info(f"📋 Current columns in traffic_signs: {columns}")
        
        if 'explanation' in columns:
            logger.info("✅ explanation column already exists in traffic_signs table")
            logger.info("   No migration needed")
            return
        
        # Add the column
        logger.info("🔨 Adding explanation column to traffic_signs table...")
        
        with engine.connect() as conn:
            # Determine database type and use appropriate SQL
            if DATABASE_URL.startswith("sqlite"):
                logger.info("   Using SQLite ALTER TABLE syntax")
                sql = text("ALTER TABLE traffic_signs ADD COLUMN explanation TEXT")
            else:
                logger.info("   Using PostgreSQL ALTER TABLE syntax")
                sql = text("ALTER TABLE traffic_signs ADD COLUMN explanation TEXT")
            
            conn.execute(sql)
            conn.commit()
            logger.info("✅ Successfully added explanation column to traffic_signs table")
        
        # Verify the column was added
        inspector = inspect(engine)
        columns_after = [col['name'] for col in inspector.get_columns('traffic_signs')]
        logger.info(f"📋 Columns after migration: {columns_after}")
        
        if 'explanation' in columns_after:
            logger.info("✅ Migration verified successfully")
        else:
            logger.error("❌ Migration verification failed - column not found after adding")
            
    except Exception as e:
        logger.error(f"❌ Error running migration: {e}", exc_info=True)
        sys.exit(1)
    
    logger.info("=" * 60)
    logger.info("🎉 Migration completed successfully")
    logger.info("=" * 60)

if __name__ == "__main__":
    run_migration()
