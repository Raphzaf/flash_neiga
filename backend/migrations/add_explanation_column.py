#!/usr/bin/env python3
"""
Migration script to add explanation column to traffic_signs table
Usage: python backend/migrations/add_explanation_column.py
"""
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from database import engine, Base
from models import TrafficSignDB

def run_migration():
    """Add explanation column to traffic_signs table if it doesn't exist"""
    print("Running migration: Add explanation column to traffic_signs table")
    
    try:
        with engine.connect() as conn:
            # For SQLite, we need to handle the migration differently
            # Check if column exists first
            result = conn.execute(text("PRAGMA table_info(traffic_signs)"))
            columns = [row[1] for row in result]
            
            if 'explanation' not in columns:
                print("Adding explanation column...")
                conn.execute(text("ALTER TABLE traffic_signs ADD COLUMN explanation TEXT"))
                conn.commit()
                print("✓ Successfully added explanation column to traffic_signs table")
            else:
                print("✓ explanation column already exists in traffic_signs table")
                
    except Exception as e:
        print(f"Error running migration: {e}")
        # If table doesn't exist, create all tables
        print("Creating all tables from models...")
        Base.metadata.create_all(bind=engine)
        print("✓ All tables created")

if __name__ == "__main__":
    run_migration()
