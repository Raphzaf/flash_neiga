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
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    
    logger.info(f"🔗 Connecting to database...")
    logger.info(f"   Type: {'PostgreSQL' if 'postgresql://' in database_url else 'SQLite'}")
    
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
    logger.info("   This may take a few seconds...")
    
    try:
        with engine.connect() as conn:
            # Pour PostgreSQL, exécuter tout le script en une fois
            # car il contient des blocs DO $$ qui doivent rester ensemble
            logger.info("   Executing migration script...")
            conn.execute(text(sql_content))
            conn.commit()
        
        logger.info("✅ Migration completed successfully!")
        
        # Vérifier les colonnes
        logger.info("\n📊 Verifying database schema...")
        
        with engine.connect() as conn:
            # Compter les colonnes de transactions
            result = conn.execute(text("""
                SELECT COUNT(*) as col_count
                FROM information_schema.columns 
                WHERE table_name = 'transactions'
            """))
            trans_count = result.fetchone()[0]
            logger.info(f"\n   ✓ Table 'transactions': {trans_count} columns")
            
            # Vérifier les colonnes HYP spécifiques
            result = conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'transactions' 
                AND column_name IN ('plan_id', 'hyp_transaction_id', 'payment_url', 'callback_data')
                ORDER BY column_name
            """))
            
            hyp_cols = [row[0] for row in result]
            logger.info(f"   ✓ HYP columns present: {', '.join(hyp_cols)}")
            
            # Compter les colonnes de subscriptions
            result = conn.execute(text("""
                SELECT COUNT(*) as col_count
                FROM information_schema.columns 
                WHERE table_name = 'subscriptions'
            """))
            subs_count = result.fetchone()[0]
            logger.info(f"\n   ✓ Table 'subscriptions': {subs_count} columns")
            
            # Vérifier les colonnes clés de subscriptions
            result = conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'subscriptions' 
                AND column_name IN ('user_id', 'plan_id', 'status', 'start_date', 'end_date')
                ORDER BY column_name
            """))
            
            subs_cols = [row[0] for row in result]
            logger.info(f"   ✓ Key columns present: {', '.join(subs_cols)}")
        
        logger.info("\n🎉 Database schema is ready for HYP integration!")
        logger.info("\n📝 Next steps:")
        logger.info("   1. Restart your backend service on Render")
        logger.info("   2. Test the payment endpoint")
        logger.info("   3. Check that no 500 errors occur")
        
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        logger.error(f"   Error type: {type(e).__name__}")
        logger.error(f"\n💡 Troubleshooting:")
        logger.error(f"   - Check if the database is accessible")
        logger.error(f"   - Verify DATABASE_URL is correct")
        logger.error(f"   - Check Render logs for more details")
        sys.exit(1)

if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("HYP Database Migration Script")
    logger.info("=" * 60)
    logger.info("")
    
    run_migration()
