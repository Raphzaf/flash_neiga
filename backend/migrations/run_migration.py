#!/usr/bin/env python3
"""
Script de migration de base de données pour HYP
Ajoute les colonnes nécessaires à la table transactions et crée la table subscriptions

Usage:
    python backend/migrations/run_migration.py
    
Ou depuis le dossier backend:
    python migrations/run_migration.py
"""

import os
import sys
from pathlib import Path
import psycopg2
from psycopg2 import sql
import logging

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_database_url():
    """Récupère l'URL de la base de données depuis les variables d'environnement"""
    database_url = os.environ.get("DATABASE_URL")
    
    if not database_url:
        logger.error("❌ DATABASE_URL environment variable not set")
        sys.exit(1)
    
    # Render utilise postgres:// mais psycopg2 nécessite postgresql://
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    
    return database_url


def read_migration_file(migration_file: str) -> str:
    """Lit le contenu d'un fichier de migration SQL"""
    script_dir = Path(__file__).parent
    migration_path = script_dir / migration_file
    
    if not migration_path.exists():
        logger.error(f"❌ Migration file not found: {migration_path}")
        sys.exit(1)
    
    with open(migration_path, 'r', encoding='utf-8') as f:
        return f.read()


def run_migration(database_url: str, migration_sql: str):
    """Exécute une migration SQL"""
    try:
        logger.info("🔌 Connecting to database...")
        conn = psycopg2.connect(database_url)
        conn.autocommit = False
        cursor = conn.cursor()
        
        logger.info("🚀 Running migration...")
        cursor.execute(migration_sql)
        
        conn.commit()
        logger.info("✅ Migration completed successfully!")
        
        cursor.close()
        conn.close()
        
    except psycopg2.Error as e:
        logger.error(f"❌ Database error: {e}")
        if conn:
            conn.rollback()
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}")
        sys.exit(1)


def verify_migration(database_url: str):
    """Vérifie que la migration a réussi en testant les colonnes"""
    try:
        conn = psycopg2.connect(database_url)
        cursor = conn.cursor()
        
        # Vérifier les colonnes de transactions
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'transactions' 
            AND column_name IN ('plan_id', 'hyp_transaction_id', 'payment_url', 'callback_data')
        """)
        
        columns = [row[0] for row in cursor.fetchall()]
        
        required_columns = ['plan_id', 'hyp_transaction_id', 'payment_url', 'callback_data']
        missing_columns = [col for col in required_columns if col not in columns]
        
        if missing_columns:
            logger.warning(f"⚠️  Some columns are still missing: {missing_columns}")
        else:
            logger.info("✅ All required columns exist in transactions table")
        
        # Vérifier que la table subscriptions existe
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'subscriptions'
            )
        """)
        
        subscriptions_exists = cursor.fetchone()[0]
        
        if subscriptions_exists:
            logger.info("✅ Subscriptions table exists")
        else:
            logger.warning("⚠️  Subscriptions table does not exist")
        
        cursor.close()
        conn.close()
        
        return len(missing_columns) == 0 and subscriptions_exists
        
    except Exception as e:
        logger.error(f"❌ Verification error: {e}")
        return False


def main():
    """Point d'entrée principal"""
    logger.info("=" * 60)
    logger.info("🔄 HYP Database Migration Script")
    logger.info("=" * 60)
    
    # Récupérer l'URL de la base de données
    database_url = get_database_url()
    logger.info(f"📍 Database: {database_url.split('@')[1] if '@' in database_url else 'local'}")
    
    # Lire le fichier de migration
    migration_sql = read_migration_file("001_add_hyp_columns.sql")
    logger.info("📄 Migration file loaded: 001_add_hyp_columns.sql")
    
    # Demander confirmation
    print("\n⚠️  This will modify the database schema.")
    print("   Make sure you have a backup before proceeding.")
    confirm = input("\nContinue with migration? (yes/no): ").strip().lower()
    
    if confirm not in ['yes', 'y', 'oui', 'o']:
        logger.info("❌ Migration cancelled by user")
        sys.exit(0)
    
    # Exécuter la migration
    run_migration(database_url, migration_sql)
    
    # Vérifier la migration
    logger.info("\n🔍 Verifying migration...")
    success = verify_migration(database_url)
    
    if success:
        logger.info("\n" + "=" * 60)
        logger.info("🎉 Migration completed successfully!")
        logger.info("=" * 60)
        logger.info("\n📝 Next steps:")
        logger.info("   1. Restart your backend service on Render")
        logger.info("   2. Test the payment flow")
        logger.info("   3. Check the logs for any errors")
    else:
        logger.warning("\n⚠️  Migration completed but verification failed")
        logger.warning("   Please check the database manually")


if __name__ == "__main__":
    main()
