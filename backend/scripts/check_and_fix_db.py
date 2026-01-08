#!/usr/bin/env python3
"""
Database integrity check and fix script
Usage: python backend/scripts/check_and_fix_db.py [--fix]

This script checks the database schema for missing columns and offers to fix them.
Use --fix flag to automatically apply fixes without prompting.
"""
import sys
import os
from pathlib import Path
import argparse

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import inspect, text, Column, Text, Boolean, TIMESTAMP
from sqlalchemy.schema import Table, MetaData
from database import engine, Base, DATABASE_URL
from models import TrafficSignDB, QuestionDB, UserDB, ExamSessionDB, TransactionDB
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def check_table_columns(table_name, expected_columns):
    """
    Check if a table has all expected columns.
    Returns list of missing columns.
    """
    inspector = inspect(engine)
    
    if table_name not in inspector.get_table_names():
        logger.warning(f"⚠️  Table '{table_name}' does not exist")
        return None
    
    existing_columns = [col['name'] for col in inspector.get_columns(table_name)]
    missing_columns = [col for col in expected_columns if col not in existing_columns]
    
    return existing_columns, missing_columns


def check_database_integrity():
    """
    Check database integrity and return a report of issues.
    """
    logger.info("=" * 60)
    logger.info("🔍 Checking database integrity...")
    logger.info("=" * 60)
    logger.info(f"📊 Database: {DATABASE_URL.split('@')[-1] if '@' in DATABASE_URL else 'SQLite'}")
    
    issues = []
    
    # Define expected columns for each table
    expected_schema = {
        'traffic_signs': ['id', 'number', 'name', 'description', 'image_url', 'category', 'explanation', 'created_at'],
        'questions': ['id', 'text', 'category', 'options', 'explanation', 'created_at'],
        'users': ['id', 'email', 'hashed_password', 'created_at', 'is_premium', 'premium_until'],
        'exam_sessions': ['id', 'user_id', 'started_at', 'ended_at', 'score', 'total_questions', 'passed', 'answers'],
        'transactions': ['id', 'user_id', 'transaction_id', 'amount', 'currency', 'provider', 'status', 'created_at', 'metadata']
    }
    
    # Check each table
    for table_name, expected_columns in expected_schema.items():
        logger.info(f"\n📋 Checking table: {table_name}")
        result = check_table_columns(table_name, expected_columns)
        
        if result is None:
            issues.append({
                'table': table_name,
                'issue': 'table_missing',
                'details': f"Table '{table_name}' does not exist"
            })
            logger.error(f"   ❌ Table does not exist")
        else:
            existing_columns, missing_columns = result
            logger.info(f"   Existing columns: {existing_columns}")
            
            if missing_columns:
                logger.error(f"   ❌ Missing columns: {missing_columns}")
                for col in missing_columns:
                    issues.append({
                        'table': table_name,
                        'issue': 'missing_column',
                        'column': col,
                        'details': f"Column '{col}' is missing from table '{table_name}'"
                    })
            else:
                logger.info(f"   ✅ All expected columns present")
    
    return issues


def fix_missing_column(table_name, column_name):
    """
    Add a missing column to a table using SQLAlchemy DDL.
    """
    logger.info(f"🔧 Adding column '{column_name}' to table '{table_name}'...")
    
    try:
        # Define column types based on table and column name
        column_definitions = {
            'traffic_signs': {
                'explanation': Column('explanation', Text, nullable=True)
            },
            'questions': {
                'explanation': Column('explanation', Text, nullable=True)
            },
            'users': {
                'is_premium': Column('is_premium', Boolean, default=False),
                'premium_until': Column('premium_until', TIMESTAMP, nullable=True)
            }
        }
        
        column_def = column_definitions.get(table_name, {}).get(column_name)
        
        if not column_def:
            logger.warning(f"⚠️  Column definition for {table_name}.{column_name} not found, using TEXT")
            column_def = Column(column_name, Text, nullable=True)
        
        # Use SQLAlchemy's DDL to add the column
        with engine.connect() as conn:
            # Get table metadata
            metadata = MetaData()
            table = Table(table_name, metadata, autoload_with=engine)
            
            # Add column using DDL
            column_def.table = table
            from sqlalchemy.schema import AddColumn
            conn.execute(AddColumn(table, column_def))
            conn.commit()
            logger.info(f"   ✅ Successfully added column '{column_name}'")
            return True
    except Exception as e:
        logger.error(f"   ❌ Error adding column: {e}")
        return False


def fix_issues(issues):
    """
    Fix all detected issues.
    """
    logger.info("\n" + "=" * 60)
    logger.info("🔧 Fixing detected issues...")
    logger.info("=" * 60)
    
    fixed = 0
    failed = 0
    
    for issue in issues:
        if issue['issue'] == 'missing_column':
            if fix_missing_column(issue['table'], issue['column']):
                fixed += 1
            else:
                failed += 1
        elif issue['issue'] == 'table_missing':
            logger.warning(f"⚠️  Cannot fix missing table '{issue['table']}' - run init_db() instead")
            failed += 1
    
    logger.info("\n" + "=" * 60)
    logger.info(f"📊 Fix summary: {fixed} fixed, {failed} failed")
    logger.info("=" * 60)
    
    return fixed, failed


def main():
    parser = argparse.ArgumentParser(description='Check and fix database integrity')
    parser.add_argument('--fix', action='store_true', help='Automatically fix detected issues')
    args = parser.parse_args()
    
    # Check database
    issues = check_database_integrity()
    
    if not issues:
        logger.info("\n" + "=" * 60)
        logger.info("✅ Database integrity check passed - no issues found!")
        logger.info("=" * 60)
        return 0
    
    # Report issues
    logger.warning("\n" + "=" * 60)
    logger.warning(f"⚠️  Found {len(issues)} issue(s):")
    logger.warning("=" * 60)
    for i, issue in enumerate(issues, 1):
        logger.warning(f"{i}. {issue['details']}")
    
    # Fix if requested
    if args.fix:
        fix_issues(issues)
    else:
        logger.info("\n💡 Run with --fix flag to automatically fix these issues")
        logger.info("   Example: python backend/scripts/check_and_fix_db.py --fix")
    
    return len(issues)


if __name__ == "__main__":
    sys.exit(main())
