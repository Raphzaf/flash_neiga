#!/usr/bin/env python3
"""
Database Schema Verification Script

Read-only script to verify database schema against expected models.
Works with both SQLite (local) and PostgreSQL (production).
Does NOT modify anything - safe to run anytime.

Usage:
    # Verify using DATABASE_URL environment variable
    python backend/scripts/verify_db_schema.py
    
    # Verify specific database
    python backend/scripts/verify_db_schema.py --db-url "postgresql://user:pass@host/db"
    
    # Verbose output
    python backend/scripts/verify_db_schema.py --verbose
"""

import sys
import os
import argparse
import logging
from pathlib import Path
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import SQLAlchemyError

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s'
)
logger = logging.getLogger(__name__)


# Expected schema for all tables
EXPECTED_SCHEMAS = {
    'users': {
        'id': 'String',
        'email': 'String',
        'hashed_password': 'String',
        'created_at': 'DateTime'
    },
    'questions': {
        'id': 'String',
        'text': 'Text',
        'category': 'String',
        'options': 'JSON',
        'explanation': 'Text',
        'created_at': 'DateTime'
    },
    'traffic_signs': {
        'id': 'String',
        'number': 'String',
        'name': 'String',
        'description': 'Text',
        'image_url': 'String',
        'category': 'String',
        'explanation': 'Text',
        'created_at': 'DateTime'
    },
    'exam_sessions': {
        'id': 'String',
        'user_id': 'String',
        'status': 'String',
        'answers': 'JSON',
        'question_ids': 'JSON',
        'score': 'Integer',
        'passed': 'Boolean',
        'created_at': 'DateTime',
        'completed_at': 'DateTime'
    },
    'transactions': {
        'id': 'String',
        'user_id': 'String',
        'paddle_transaction_id': 'String',
        'paddle_subscription_id': 'String',
        'amount': 'Float',
        'currency': 'String',
        'status': 'String',
        'event_type': 'String',
        'event_data': 'JSON',
        'created_at': 'DateTime',
        'updated_at': 'DateTime'
    },
    'payments': {
        'id': 'String',
        'user_id': 'String',
        'order_id': 'String',
        'product_id': 'Integer',
        'amount': 'Float',
        'currency': 'String',
        'status': 'String',
        'event_type': 'String',
        'event_data': 'JSON',
        'created_at': 'DateTime',
        'updated_at': 'DateTime'
    },
    'subscriptions': {
        'id': 'String',
        'user_id': 'String',
        'license_id': 'String',
        'product_id': 'Integer',
        'status': 'String',
        'next_renewal': 'DateTime',
        'canceled_at': 'DateTime',
        'created_at': 'DateTime',
        'updated_at': 'DateTime'
    }
}


def get_database_url(args):
    """Get database URL from args or environment"""
    if args.db_url:
        db_url = args.db_url
    else:
        db_url = os.environ.get('DATABASE_URL')
        if not db_url:
            # Default to SQLite for local development
            backend_dir = Path(__file__).parent.parent
            db_path = backend_dir / "flash_neiga.db"
            db_url = f"sqlite:///{db_path.as_posix()}"
            logger.info(f"ℹ️  No DATABASE_URL found, using local SQLite: {db_path}")
    
    # Handle Render's postgres:// format
    if db_url.startswith('postgres://'):
        db_url = db_url.replace('postgres://', 'postgresql://', 1)
    
    return db_url


def mask_db_url(db_url):
    """Mask password in database URL for safe logging"""
    if '@' in db_url and '://' in db_url:
        parts = db_url.split('@')
        proto_creds = parts[0].split('://')
        if len(proto_creds) == 2 and ':' in proto_creds[1]:
            proto = proto_creds[0]
            user = proto_creds[1].split(':')[0]
            return f"{proto}://{user}:****@{parts[1]}"
    return db_url


def connect_to_database(db_url):
    """Create database engine and test connection"""
    logger.info("=" * 80)
    logger.info("🔌 CONNECTING TO DATABASE")
    logger.info("=" * 80)
    
    masked_url = mask_db_url(db_url)
    logger.info(f"📊 Database: {masked_url}")
    
    try:
        engine = create_engine(db_url, echo=False)
        
        # Test connection and get version
        with engine.connect() as conn:
            if 'postgresql' in db_url:
                from sqlalchemy import text
                result = conn.execute(text("SELECT version()"))
                version = result.fetchone()[0]
                db_type = "PostgreSQL"
                logger.info(f"✅ Connected to PostgreSQL")
                logger.info(f"📦 Version: {version.split(',')[0]}")
            else:
                from sqlalchemy import text
                result = conn.execute(text("SELECT sqlite_version()"))
                version = result.fetchone()[0]
                db_type = "SQLite"
                logger.info(f"✅ Connected to SQLite")
                logger.info(f"📦 Version: {version}")
        
        return engine, db_type
    except SQLAlchemyError as e:
        logger.error(f"❌ Failed to connect to database: {e}")
        sys.exit(1)


def verify_table(engine, table_name, expected_schema, verbose=False):
    """Verify a single table's schema"""
    inspector = inspect(engine)
    
    # Check if table exists
    if table_name not in inspector.get_table_names():
        return {
            'exists': False,
            'missing_columns': list(expected_schema.keys()),
            'extra_columns': [],
            'type_mismatches': [],
            'row_count': 0
        }
    
    # Get actual columns
    actual_columns = {}
    for col in inspector.get_columns(table_name):
        col_type = str(col['type']).upper()
        # Normalize type names
        if 'VARCHAR' in col_type or 'TEXT' in col_type or 'CHAR' in col_type:
            if 'TEXT' in col_type:
                normalized_type = 'Text'
            else:
                normalized_type = 'String'
        elif 'TIMESTAMP' in col_type or 'DATETIME' in col_type:
            normalized_type = 'DateTime'
        elif 'INTEGER' in col_type or 'INT' in col_type:
            normalized_type = 'Integer'
        elif 'BOOLEAN' in col_type or 'BOOL' in col_type:
            normalized_type = 'Boolean'
        elif 'FLOAT' in col_type or 'REAL' in col_type or 'NUMERIC' in col_type:
            normalized_type = 'Float'
        elif 'JSON' in col_type:
            normalized_type = 'JSON'
        else:
            normalized_type = str(col['type'])
        
        actual_columns[col['name']] = {
            'type': normalized_type,
            'raw_type': str(col['type']),
            'nullable': col['nullable']
        }
    
    # Find discrepancies
    missing_columns = [col for col in expected_schema if col not in actual_columns]
    extra_columns = [col for col in actual_columns if col not in expected_schema]
    type_mismatches = []
    
    for col_name in expected_schema:
        if col_name in actual_columns:
            expected_type = expected_schema[col_name]
            actual_type = actual_columns[col_name]['type']
            if expected_type != actual_type:
                type_mismatches.append({
                    'column': col_name,
                    'expected': expected_type,
                    'actual': actual_type
                })
    
    # Get row count
    row_count = 0
    try:
        # Validate table_name is from our controlled EXPECTED_SCHEMAS dict
        if table_name not in EXPECTED_SCHEMAS:
            logger.warning(f"⚠️  Table {table_name} not in expected schemas")
            return {
                'exists': False,
                'missing_columns': [],
                'extra_columns': [],
                'type_mismatches': [],
                'row_count': 0
            }
        
        with engine.connect() as conn:
            from sqlalchemy import text
            # table_name is validated above to be from EXPECTED_SCHEMAS keys only
            result = conn.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
            row_count = result.fetchone()[0]
    except:
        pass
    
    return {
        'exists': True,
        'missing_columns': missing_columns,
        'extra_columns': extra_columns,
        'type_mismatches': type_mismatches,
        'row_count': row_count,
        'actual_columns': actual_columns if verbose else None
    }


def print_table_report(table_name, result, verbose=False):
    """Print verification report for a table"""
    logger.info(f"\n📋 Table: {table_name}")
    logger.info("-" * 80)
    
    if not result['exists']:
        logger.warning(f"  ⚠️  Table does not exist!")
        logger.warning(f"  📝 Expected {len(result['missing_columns'])} columns: {', '.join(result['missing_columns'])}")
        return False
    
    logger.info(f"  ✅ Table exists")
    logger.info(f"  📊 Row count: {result['row_count']}")
    
    has_issues = False
    
    # Report missing columns
    if result['missing_columns']:
        has_issues = True
        logger.warning(f"  ❌ Missing {len(result['missing_columns'])} column(s):")
        for col in result['missing_columns']:
            logger.warning(f"     - {col}")
    else:
        logger.info(f"  ✅ All expected columns present")
    
    # Report extra columns
    if result['extra_columns']:
        logger.info(f"  ℹ️  Extra {len(result['extra_columns'])} column(s):")
        for col in result['extra_columns']:
            logger.info(f"     + {col}")
    
    # Report type mismatches
    if result['type_mismatches']:
        has_issues = True
        logger.warning(f"  ⚠️  Type mismatch in {len(result['type_mismatches'])} column(s):")
        for mismatch in result['type_mismatches']:
            logger.warning(f"     - {mismatch['column']}: expected {mismatch['expected']}, got {mismatch['actual']}")
    
    # Verbose output
    if verbose and result.get('actual_columns'):
        logger.info(f"  📝 All columns:")
        for col_name, col_info in result['actual_columns'].items():
            status = "✓" if col_name not in result['extra_columns'] else "+"
            logger.info(f"     {status} {col_name:<25} {col_info['raw_type']:<20} nullable={col_info['nullable']}")
    
    return not has_issues


def main():
    parser = argparse.ArgumentParser(
        description='Verify database schema (read-only)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument(
        '--db-url',
        help='Database URL (default: use DATABASE_URL environment variable or local SQLite)'
    )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Show verbose output including all columns'
    )
    parser.add_argument(
        '--table',
        help='Verify only specific table'
    )
    
    args = parser.parse_args()
    
    logger.info("")
    logger.info("=" * 80)
    logger.info("🔍 DATABASE SCHEMA VERIFICATION")
    logger.info("=" * 80)
    logger.info(f"⏰ Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("ℹ️  This is a READ-ONLY verification - no changes will be made")
    
    # Connect to database
    db_url = get_database_url(args)
    engine, db_type = connect_to_database(db_url)
    
    # Verify tables
    logger.info("")
    logger.info("=" * 80)
    logger.info("📊 SCHEMA VERIFICATION")
    logger.info("=" * 80)
    
    all_ok = True
    tables_to_check = [args.table] if args.table else EXPECTED_SCHEMAS.keys()
    
    for table_name in tables_to_check:
        if table_name not in EXPECTED_SCHEMAS:
            logger.warning(f"⚠️  Unknown table '{table_name}', skipping")
            continue
        
        expected_schema = EXPECTED_SCHEMAS[table_name]
        result = verify_table(engine, table_name, expected_schema, verbose=args.verbose)
        table_ok = print_table_report(table_name, result, verbose=args.verbose)
        
        if not table_ok:
            all_ok = False
    
    # Summary
    logger.info("")
    logger.info("=" * 80)
    logger.info("📊 VERIFICATION SUMMARY")
    logger.info("=" * 80)
    logger.info(f"⏰ Finished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    if all_ok:
        logger.info("✅ All tables verified successfully - schema is correct!")
        logger.info("")
        sys.exit(0)
    else:
        logger.warning("⚠️  Schema verification found issues (see details above)")
        logger.info("")
        logger.info("💡 To fix issues:")
        logger.info("   - Run: python backend/scripts/fix_production_db.py")
        logger.info("   - Or run: python backend/scripts/check_and_fix_db.py --fix")
        logger.info("")
        sys.exit(1)


if __name__ == '__main__':
    main()
