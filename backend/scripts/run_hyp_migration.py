#!/usr/bin/env python3
"""
Script pour exécuter la migration HYP sur PostgreSQL
Usage: python backend/scripts/run_hyp_migration.py
"""

import os
import sys
from pathlib import Path
from sqlalchemy import create_engine, text
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_migration():
    """Exécute la migration SQL"""
    
    # Obtenir l'URL de la base de données
    database_url = os.environ.get("DATABASE_URL")
    
    if not database_url:
        logger.error("❌ DATABASE_URL environment variable not set")
        logger.info("For local: export DATABASE_URL=sqlite:///backend/flash_neiga.db")
        logger.info("For Render: DATABASE_URL is auto-configured")
        sys.exit(1)
    
    # Convertir postgres:// en postgresql:// si nécessaire
    original_url = database_url
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    
    # Vérifier que c'est PostgreSQL
    if 'postgresql://' not in database_url:
        logger.error("❌ This migration script is designed for PostgreSQL only")
        logger.error(f"   Your database URL: {original_url}")
        logger.info("   For SQLite, the models will automatically create the schema")
        logger.info("   Simply delete your SQLite database and restart the server")
        sys.exit(1)
    
    logger.info(f"🔗 Connecting to database...")
    logger.info(f"   Type: PostgreSQL")
    
    # Créer le moteur
    try:
        engine = create_engine(database_url)
    except Exception as e:
        logger.error(f"❌ Failed to connect to database: {e}")
        sys.exit(1)
    
    # Lire le fichier SQL
    script_dir = Path(__file__).parent
    sql_file = script_dir.parent / "migrations" / "002_add_hyp_support.sql"
    
    if not sql_file.exists():
        logger.error(f"❌ Migration file not found: {sql_file}")
        sys.exit(1)
    
    logger.info(f"📖 Reading migration file: {sql_file.name}")
    
    with open(sql_file, 'r', encoding='utf-8') as f:
        sql_content = f.read()
    
    # Exécuter la migration
    logger.info("🚀 Executing migration...")
    
    try:
        with engine.begin() as conn:
            # Séparer les commandes SQL (PostgreSQL peut avoir des problèmes avec plusieurs commandes)
            statements = [s.strip() for s in sql_content.split(';') if s.strip()]
            
            executed = 0
            for statement in statements:
                # Skip empty statements and comments
                if not statement or statement.startswith('--'):
                    continue
                
                # Remove comments from the statement
                lines = [line for line in statement.split('\n') if not line.strip().startswith('--')]
                clean_statement = '\n'.join(lines).strip()
                
                if not clean_statement:
                    continue
                
                executed += 1
                logger.info(f"   Executing statement {executed}...")
                conn.execute(text(clean_statement))
        
        logger.info(f"✅ Migration completed successfully! ({executed} statements executed)")
        
        # Vérifier les colonnes
        logger.info("\n📊 Verifying database schema...")
        
        with engine.connect() as conn:
            # Vérifier transactions avec PostgreSQL
            result = conn.execute(text("""
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_name = 'transactions' 
                ORDER BY ordinal_position
            """))
            
            logger.info("\n   Table 'transactions' columns:")
            for row in result:
                logger.info(f"     - {row[0]}: {row[1]}")
            
            # Vérifier subscriptions
            result = conn.execute(text("""
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_name = 'subscriptions' 
                ORDER BY ordinal_position
            """))
            
            logger.info("\n   Table 'subscriptions' columns:")
            for row in result:
                logger.info(f"     - {row[0]}: {row[1]}")
        
        logger.info("\n🎉 Database schema is ready for HYP integration!")
        
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        logger.error(f"   Error details: {type(e).__name__}")
        sys.exit(1)

if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("HYP Database Migration Script")
    logger.info("=" * 60)
    logger.info("")
    
    run_migration()
