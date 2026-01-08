#!/usr/bin/env python3
"""
Recreate Traffic Signs Table Script

⚠️  WARNING: This is a NUCLEAR OPTION script that drops and recreates the traffic_signs table.
Use this ONLY when other migration methods have failed.

This script:
1. Backs up existing data if any
2. Drops the traffic_signs table
3. Recreates it with correct schema
4. Restores backed up data (if any)
5. Reloads from JSON if table was empty

Usage:
    # Show what would be done (safe - no changes)
    python backend/scripts/recreate_traffic_signs_table.py --dry-run
    
    # Actually recreate the table (DESTRUCTIVE!)
    python backend/scripts/recreate_traffic_signs_table.py --confirm
    
    # With custom database URL
    python backend/scripts/recreate_traffic_signs_table.py --confirm --db-url "postgresql://..."
"""

import sys
import os
import argparse
import logging
import json
from pathlib import Path
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text, inspect
from sqlalchemy.exc import SQLAlchemyError

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_database_url(args):
    """Get database URL from args or environment"""
    if args.db_url:
        db_url = args.db_url
    else:
        db_url = os.environ.get('DATABASE_URL')
        if not db_url:
            logger.error("❌ No DATABASE_URL found. Set DATABASE_URL or use --db-url")
            sys.exit(1)
    
    # Handle Render's postgres:// format
    if db_url.startswith('postgres://'):
        db_url = db_url.replace('postgres://', 'postgresql://', 1)
    
    return db_url


def mask_db_url(db_url):
    """Mask password in URL for safe logging"""
    if '@' in db_url and '://' in db_url:
        parts = db_url.split('@')
        proto_creds = parts[0].split('://')
        if len(proto_creds) == 2 and ':' in proto_creds[1]:
            proto = proto_creds[0]
            user = proto_creds[1].split(':')[0]
            return f"{proto}://{user}:****@{parts[1]}"
    return db_url


def backup_existing_data(engine):
    """Backup existing traffic signs data"""
    logger.info("=" * 70)
    logger.info("💾 Backing up existing data...")
    logger.info("=" * 70)
    
    inspector = inspect(engine)
    
    # Check if table exists
    if 'traffic_signs' not in inspector.get_table_names():
        logger.info("ℹ️  Table doesn't exist - no data to backup")
        return None
    
    # Get existing data
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT * FROM traffic_signs"))
            rows = result.fetchall()
            columns = result.keys()
            
            if not rows:
                logger.info("ℹ️  Table is empty - no data to backup")
                return None
            
            # Convert to list of dicts
            backup_data = []
            for row in rows:
                backup_data.append(dict(zip(columns, row)))
            
            logger.info(f"✅ Backed up {len(backup_data)} traffic signs")
            
            # Save to file for safety
            backup_dir = Path(__file__).parent.parent / 'backups'
            backup_dir.mkdir(exist_ok=True)
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_file = backup_dir / f'traffic_signs_backup_{timestamp}.json'
            
            with open(backup_file, 'w', encoding='utf-8') as f:
                json.dump(backup_data, f, indent=2, default=str)
            
            logger.info(f"💾 Backup saved to: {backup_file}")
            
            return backup_data
            
    except SQLAlchemyError as e:
        logger.error(f"❌ Failed to backup data: {e}")
        return None


def drop_table(engine, dry_run=False):
    """Drop the traffic_signs table"""
    logger.info("")
    logger.info("=" * 70)
    logger.info("🗑️  Dropping traffic_signs table...")
    logger.info("=" * 70)
    
    if dry_run:
        logger.info("ℹ️  DRY RUN: Would drop table traffic_signs")
        return
    
    try:
        with engine.connect() as conn:
            conn.execute(text("DROP TABLE IF EXISTS traffic_signs CASCADE"))
            conn.commit()
            logger.info("✅ Table dropped successfully")
    except SQLAlchemyError as e:
        logger.error(f"❌ Failed to drop table: {e}")
        raise


def create_table(engine, dry_run=False):
    """Create traffic_signs table with correct schema"""
    logger.info("")
    logger.info("=" * 70)
    logger.info("🔧 Creating traffic_signs table with correct schema...")
    logger.info("=" * 70)
    
    # SQL for creating the table
    create_sql = """
    CREATE TABLE traffic_signs (
        id VARCHAR PRIMARY KEY,
        number VARCHAR NOT NULL,
        name VARCHAR NOT NULL,
        description TEXT NOT NULL,
        image_url VARCHAR,
        category VARCHAR NOT NULL,
        explanation TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """
    
    # SQL for creating indexes
    index_sqls = [
        "CREATE INDEX idx_traffic_signs_number ON traffic_signs (number)",
        "CREATE INDEX idx_traffic_signs_category ON traffic_signs (category)"
    ]
    
    if dry_run:
        logger.info("ℹ️  DRY RUN: Would create table with schema:")
        logger.info(create_sql)
        logger.info("ℹ️  DRY RUN: Would create indexes:")
        for idx_sql in index_sqls:
            logger.info(f"   {idx_sql}")
        return
    
    try:
        with engine.connect() as conn:
            # Create table
            conn.execute(text(create_sql))
            logger.info("✅ Table created successfully")
            
            # Create indexes
            for idx_sql in index_sqls:
                conn.execute(text(idx_sql))
            logger.info("✅ Indexes created successfully")
            
            conn.commit()
    except SQLAlchemyError as e:
        logger.error(f"❌ Failed to create table: {e}")
        raise


def restore_data(engine, backup_data, dry_run=False):
    """Restore backed up data"""
    if not backup_data:
        return
    
    logger.info("")
    logger.info("=" * 70)
    logger.info("♻️  Restoring backed up data...")
    logger.info("=" * 70)
    
    if dry_run:
        logger.info(f"ℹ️  DRY RUN: Would restore {len(backup_data)} traffic signs")
        return
    
    try:
        with engine.connect() as conn:
            for item in backup_data:
                # Build insert statement
                columns = ', '.join(item.keys())
                placeholders = ', '.join([f":{k}" for k in item.keys()])
                insert_sql = f"INSERT INTO traffic_signs ({columns}) VALUES ({placeholders})"
                
                conn.execute(text(insert_sql), item)
            
            conn.commit()
            logger.info(f"✅ Restored {len(backup_data)} traffic signs")
    except SQLAlchemyError as e:
        logger.error(f"❌ Failed to restore data: {e}")
        raise


def load_from_json(engine, dry_run=False):
    """Load traffic signs from JSON file"""
    logger.info("")
    logger.info("=" * 70)
    logger.info("📥 Loading traffic signs from JSON...")
    logger.info("=" * 70)
    
    json_path = Path(__file__).parent.parent.parent / "data" / "signs_israel_fr_117.json"
    
    if not json_path.exists():
        logger.warning(f"⚠️  JSON file not found at {json_path}")
        return
    
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if not isinstance(data, list):
            logger.warning("⚠️  JSON format invalid (expected list)")
            return
        
        if dry_run:
            logger.info(f"ℹ️  DRY RUN: Would load {len(data)} traffic signs from JSON")
            return
        
        import uuid
        with engine.connect() as conn:
            imported = 0
            for item in data:
                if not isinstance(item, dict):
                    continue
                
                raw_id = item.get("id")
                number = f"IL-{raw_id}" if raw_id is not None else None
                if not number:
                    continue
                
                insert_sql = """
                INSERT INTO traffic_signs (id, number, name, description, image_url, category)
                VALUES (:id, :number, :name, :description, :image_url, :category)
                """
                
                conn.execute(text(insert_sql), {
                    'id': str(uuid.uuid4()),
                    'number': str(number),
                    'name': item.get("nom") or "",
                    'description': item.get("nom") or "",
                    'image_url': item.get("image"),
                    'category': item.get("type") or "Autre"
                })
                imported += 1
            
            conn.commit()
            logger.info(f"✅ Loaded {imported} traffic signs from JSON")
    
    except Exception as e:
        logger.error(f"❌ Failed to load from JSON: {e}")


def main():
    parser = argparse.ArgumentParser(
        description='Recreate traffic_signs table (DESTRUCTIVE - use with caution)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument(
        '--db-url',
        help='Database URL (default: use DATABASE_URL environment variable)'
    )
    parser.add_argument(
        '--confirm',
        action='store_true',
        help='Confirm that you want to recreate the table (REQUIRED for execution)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be done without making changes'
    )
    
    args = parser.parse_args()
    
    logger.info("")
    logger.info("=" * 70)
    logger.info("⚠️  RECREATE TRAFFIC SIGNS TABLE")
    logger.info("=" * 70)
    logger.warning("⚠️  WARNING: This script will DROP and RECREATE the traffic_signs table!")
    logger.warning("⚠️  All existing data will be backed up and restored if possible.")
    logger.info("")
    
    if not args.confirm and not args.dry_run:
        logger.error("❌ This is a destructive operation!")
        logger.error("   Use --dry-run to preview, or --confirm to execute")
        sys.exit(1)
    
    if args.dry_run:
        logger.info("ℹ️  DRY RUN MODE - No changes will be made")
    
    # Get database URL and connect
    db_url = get_database_url(args)
    masked_url = mask_db_url(db_url)
    logger.info(f"📊 Database: {masked_url}")
    
    try:
        engine = create_engine(db_url, echo=False)
        
        # Test connection
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("✅ Connected to database")
        
    except SQLAlchemyError as e:
        logger.error(f"❌ Failed to connect: {e}")
        sys.exit(1)
    
    # Execute steps
    try:
        # 1. Backup existing data
        backup_data = backup_existing_data(engine)
        
        # 2. Drop table
        drop_table(engine, dry_run=args.dry_run)
        
        # 3. Create table with correct schema
        create_table(engine, dry_run=args.dry_run)
        
        # 4. Restore backed up data OR load from JSON
        if backup_data:
            restore_data(engine, backup_data, dry_run=args.dry_run)
        else:
            load_from_json(engine, dry_run=args.dry_run)
        
        # Summary
        logger.info("")
        logger.info("=" * 70)
        if args.dry_run:
            logger.info("✅ Dry run completed - no changes made")
            logger.info("   Run with --confirm to execute these changes")
        else:
            logger.info("✅ Traffic signs table recreated successfully!")
            logger.info("")
            logger.info("🚀 Next steps:")
            logger.info("   1. Restart your backend service")
            logger.info("   2. Test the /api/admin/signs endpoint")
            logger.info("   3. Verify traffic signs are displaying correctly")
        logger.info("=" * 70)
        
    except Exception as e:
        logger.error(f"❌ Operation failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
