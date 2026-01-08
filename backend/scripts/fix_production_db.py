#!/usr/bin/env python3
"""
Production Database Schema Fix Script

This script connects to the production PostgreSQL database and ensures
all required columns exist in the traffic_signs table with correct types.

Usage:
    # Using environment variable DATABASE_URL
    python backend/scripts/fix_production_db.py
    
    # Or provide connection string directly
    python backend/scripts/fix_production_db.py --db-url "postgresql://user:pass@host/db"
    
    # Dry run (check only, no changes)
    python backend/scripts/fix_production_db.py --dry-run

Expected columns for traffic_signs:
    - id: VARCHAR PRIMARY KEY
    - number: VARCHAR NOT NULL
    - name: VARCHAR NOT NULL
    - description: TEXT NOT NULL
    - image_url: VARCHAR
    - category: VARCHAR NOT NULL
    - explanation: TEXT
    - created_at: TIMESTAMP DEFAULT CURRENT_TIMESTAMP
"""

import sys
import os
import argparse
import logging
from pathlib import Path
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, inspect, text, MetaData, Table, Column, String, Text, DateTime
from sqlalchemy.exc import SQLAlchemyError

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Expected schema for traffic_signs table
EXPECTED_SCHEMA = {
    'id': {'type': 'String', 'nullable': False, 'primary_key': True},
    'number': {'type': 'String', 'nullable': False},
    'name': {'type': 'String', 'nullable': False},
    'description': {'type': 'Text', 'nullable': False},
    'image_url': {'type': 'String', 'nullable': True},
    'category': {'type': 'String', 'nullable': False},
    'explanation': {'type': 'Text', 'nullable': True},
    'created_at': {'type': 'DateTime', 'nullable': True, 'default': 'CURRENT_TIMESTAMP'}
}


def get_database_url(args):
    """Get database URL from args or environment"""
    if args.db_url:
        db_url = args.db_url
    else:
        db_url = os.environ.get('DATABASE_URL')
        if not db_url:
            logger.error("❌ No DATABASE_URL found. Please set DATABASE_URL environment variable or use --db-url")
            sys.exit(1)
    
    # Handle Render's postgres:// format
    if db_url.startswith('postgres://'):
        db_url = db_url.replace('postgres://', 'postgresql://', 1)
    
    return db_url


def connect_to_database(db_url):
    """Create database engine and test connection"""
    logger.info("=" * 70)
    logger.info("🔌 Connecting to database...")
    logger.info("=" * 70)
    
    # Mask password in URL for logging
    masked_url = db_url
    if '@' in db_url:
        parts = db_url.split('@')
        if '://' in parts[0]:
            proto, creds = parts[0].split('://')
            if ':' in creds:
                user = creds.split(':')[0]
                masked_url = f"{proto}://{user}:****@{parts[1]}"
    
    logger.info(f"📊 Database URL: {masked_url}")
    
    try:
        engine = create_engine(db_url, echo=False)
        
        # Test connection
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version()"))
            version = result.fetchone()[0]
            logger.info(f"✅ Connected successfully!")
            logger.info(f"📦 PostgreSQL version: {version.split(',')[0]}")
        
        return engine
    except SQLAlchemyError as e:
        logger.error(f"❌ Failed to connect to database: {e}")
        sys.exit(1)


def check_table_exists(engine, table_name):
    """Check if table exists"""
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    
    if table_name not in tables:
        logger.error(f"❌ Table '{table_name}' does not exist!")
        logger.info(f"ℹ️  Available tables: {tables}")
        return False
    
    return True


def get_current_schema(engine, table_name):
    """Get current schema of the table"""
    logger.info("")
    logger.info("=" * 70)
    logger.info(f"🔍 Checking current schema of '{table_name}' table...")
    logger.info("=" * 70)
    
    inspector = inspect(engine)
    columns = inspector.get_columns(table_name)
    
    current_schema = {}
    for col in columns:
        current_schema[col['name']] = {
            'type': str(col['type']),
            'nullable': col['nullable'],
            'default': col.get('default')
        }
        logger.info(f"  ✓ {col['name']:<20} {str(col['type']):<20} nullable={col['nullable']}")
    
    return current_schema


def find_missing_columns(current_schema, expected_schema):
    """Find columns that are missing from the current schema"""
    missing = []
    for col_name, col_spec in expected_schema.items():
        if col_name not in current_schema:
            missing.append(col_name)
    
    return missing


def add_missing_columns(engine, table_name, missing_columns, dry_run=False):
    """Add missing columns to the table"""
    if not missing_columns:
        logger.info("")
        logger.info("✅ All required columns are present!")
        return 0
    
    logger.info("")
    logger.info("=" * 70)
    logger.info(f"🔧 Found {len(missing_columns)} missing column(s):")
    logger.info("=" * 70)
    
    for col_name in missing_columns:
        col_spec = EXPECTED_SCHEMA[col_name]
        logger.info(f"  ⚠️  {col_name} - Type: {col_spec['type']}, Nullable: {col_spec['nullable']}")
    
    if dry_run:
        logger.info("")
        logger.info("ℹ️  DRY RUN MODE - No changes will be made")
        logger.info("   Run without --dry-run to apply these changes")
        return len(missing_columns)
    
    logger.info("")
    logger.info("🔧 Adding missing columns...")
    logger.info("")
    
    added = 0
    failed = 0
    
    with engine.connect() as conn:
        for col_name in missing_columns:
            col_spec = EXPECTED_SCHEMA[col_name]
            
            # Build SQL statement based on column type
            if col_spec['type'] == 'DateTime':
                if col_spec.get('default') == 'CURRENT_TIMESTAMP':
                    sql = f"ALTER TABLE {table_name} ADD COLUMN {col_name} TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
                else:
                    sql = f"ALTER TABLE {table_name} ADD COLUMN {col_name} TIMESTAMP"
            elif col_spec['type'] == 'Text':
                sql = f"ALTER TABLE {table_name} ADD COLUMN {col_name} TEXT"
            elif col_spec['type'] == 'String':
                sql = f"ALTER TABLE {table_name} ADD COLUMN {col_name} VARCHAR"
            else:
                logger.warning(f"  ⚠️  Unknown type for {col_name}: {col_spec['type']}, using TEXT")
                sql = f"ALTER TABLE {table_name} ADD COLUMN {col_name} TEXT"
            
            try:
                logger.info(f"  🔧 Adding column '{col_name}'...")
                conn.execute(text(sql))
                conn.commit()
                logger.info(f"  ✅ Successfully added column '{col_name}'")
                added += 1
            except SQLAlchemyError as e:
                logger.error(f"  ❌ Failed to add column '{col_name}': {e}")
                failed += 1
    
    logger.info("")
    logger.info("=" * 70)
    logger.info(f"📊 Summary: {added} added, {failed} failed")
    logger.info("=" * 70)
    
    return added


def create_indexes(engine, table_name, dry_run=False):
    """Create recommended indexes if they don't exist"""
    logger.info("")
    logger.info("=" * 70)
    logger.info("🔍 Checking indexes...")
    logger.info("=" * 70)
    
    inspector = inspect(engine)
    existing_indexes = {idx['name']: idx for idx in inspector.get_indexes(table_name)}
    
    # Define recommended indexes
    recommended_indexes = [
        ('idx_traffic_signs_number', 'number'),
        ('idx_traffic_signs_category', 'category'),
    ]
    
    missing_indexes = []
    for idx_name, col_name in recommended_indexes:
        if idx_name not in existing_indexes:
            missing_indexes.append((idx_name, col_name))
    
    if not missing_indexes:
        logger.info("  ✅ All recommended indexes exist")
        return
    
    logger.info(f"  ⚠️  Found {len(missing_indexes)} missing index(es)")
    
    if dry_run:
        for idx_name, col_name in missing_indexes:
            logger.info(f"    - {idx_name} on column {col_name}")
        logger.info("")
        logger.info("ℹ️  DRY RUN MODE - No indexes will be created")
        return
    
    with engine.connect() as conn:
        for idx_name, col_name in missing_indexes:
            try:
                sql = f"CREATE INDEX IF NOT EXISTS {idx_name} ON {table_name} ({col_name})"
                logger.info(f"  🔧 Creating index '{idx_name}' on column '{col_name}'...")
                conn.execute(text(sql))
                conn.commit()
                logger.info(f"  ✅ Index '{idx_name}' created successfully")
            except SQLAlchemyError as e:
                logger.warning(f"  ⚠️  Failed to create index '{idx_name}': {e}")


def verify_final_schema(engine, table_name):
    """Verify the final schema after changes"""
    logger.info("")
    logger.info("=" * 70)
    logger.info("🔍 Verifying final schema...")
    logger.info("=" * 70)
    
    current_schema = {}
    inspector = inspect(engine)
    columns = inspector.get_columns(table_name)
    
    for col in columns:
        current_schema[col['name']] = col
        logger.info(f"  ✓ {col['name']:<20} {str(col['type']):<20} nullable={col['nullable']}")
    
    # Check if all expected columns are present
    missing = find_missing_columns(current_schema, EXPECTED_SCHEMA)
    
    logger.info("")
    if missing:
        logger.warning(f"⚠️  Still missing {len(missing)} column(s): {missing}")
        return False
    else:
        logger.info("✅ All required columns are present!")
        
        # Count rows
        with engine.connect() as conn:
            result = conn.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
            count = result.fetchone()[0]
            logger.info(f"📊 Table contains {count} traffic signs")
        
        return True


def main():
    parser = argparse.ArgumentParser(
        description='Fix production database schema for traffic_signs table',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument(
        '--db-url',
        help='Database URL (default: use DATABASE_URL environment variable)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Check schema without making changes'
    )
    parser.add_argument(
        '--skip-indexes',
        action='store_true',
        help='Skip creating indexes'
    )
    
    args = parser.parse_args()
    
    logger.info("")
    logger.info("=" * 70)
    logger.info("🔧 Production Database Schema Fix")
    logger.info("=" * 70)
    logger.info(f"⏰ Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    if args.dry_run:
        logger.info("ℹ️  Running in DRY RUN mode - no changes will be made")
    
    # Get database URL and connect
    db_url = get_database_url(args)
    engine = connect_to_database(db_url)
    
    # Check if table exists
    # Note: table_name is hardcoded to 'traffic_signs' for this specific fix script
    # This prevents SQL injection as it's a constant, not user input
    table_name = 'traffic_signs'
    if not check_table_exists(engine, table_name):
        logger.error(f"❌ Cannot proceed without '{table_name}' table")
        sys.exit(1)
    
    # Get current schema
    current_schema = get_current_schema(engine, table_name)
    
    # Find missing columns
    missing_columns = find_missing_columns(current_schema, EXPECTED_SCHEMA)
    
    # Add missing columns
    added = add_missing_columns(engine, table_name, missing_columns, dry_run=args.dry_run)
    
    # Create indexes if not dry run
    if not args.dry_run and not args.skip_indexes:
        create_indexes(engine, table_name, dry_run=args.dry_run)
    
    # Verify final schema
    if not args.dry_run:
        success = verify_final_schema(engine, table_name)
        
        logger.info("")
        logger.info("=" * 70)
        if success:
            logger.info("✅ Database schema fix completed successfully!")
        else:
            logger.warning("⚠️  Database schema fix completed with warnings")
        logger.info("=" * 70)
        logger.info(f"⏰ Finished at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("")
        
        if success:
            logger.info("🚀 Next steps:")
            logger.info("   1. Restart your backend service on Render")
            logger.info("   2. Test the /api/admin/signs endpoint")
            logger.info("   3. Verify traffic signs are loading correctly")
        
        sys.exit(0 if success else 1)
    else:
        logger.info("")
        logger.info("=" * 70)
        logger.info("✅ Dry run completed - no changes were made")
        logger.info("=" * 70)
        if missing_columns:
            logger.info(f"⚠️  Run without --dry-run to add {len(missing_columns)} missing column(s)")
        sys.exit(0)


if __name__ == '__main__':
    main()
