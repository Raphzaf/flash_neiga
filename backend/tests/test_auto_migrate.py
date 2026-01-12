"""
Unit tests for auto_migrate module
Tests the automatic migration that runs on startup
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker
from pathlib import Path
import sys

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from database import Base
from migrations.auto_migrate import run_hyp_migration


class TestAutoMigration:
    """Test automatic migration on startup"""
    
    @pytest.fixture
    def test_engine(self):
        """Create a test database engine"""
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=engine)
        return engine
    
    def test_run_hyp_migration_returns_boolean(self, test_engine):
        """Test that run_hyp_migration returns a boolean"""
        with patch('migrations.auto_migrate.engine', test_engine):
            result = run_hyp_migration()
            assert isinstance(result, bool)
    
    def test_migration_succeeds_when_tables_exist(self, test_engine):
        """Test migration succeeds when tables exist"""
        # Create transactions and subscriptions tables
        with test_engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS transactions (
                    id VARCHAR PRIMARY KEY,
                    user_id VARCHAR,
                    amount DECIMAL,
                    created_at TIMESTAMP
                )
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS subscriptions (
                    id VARCHAR PRIMARY KEY,
                    user_id VARCHAR
                )
            """))
            conn.commit()
        
        with patch('migrations.auto_migrate.engine', test_engine):
            result = run_hyp_migration()
            assert result is True
    
    def test_migration_is_idempotent(self, test_engine):
        """Test that migration can be run multiple times safely"""
        # Create tables
        with test_engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS transactions (
                    id VARCHAR PRIMARY KEY
                )
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS subscriptions (
                    id VARCHAR PRIMARY KEY
                )
            """))
            conn.commit()
        
        with patch('migrations.auto_migrate.engine', test_engine):
            # Run first time
            result1 = run_hyp_migration()
            assert result1 is True
            
            # Run second time - should still succeed
            result2 = run_hyp_migration()
            assert result2 is True
    
    def test_migration_adds_columns_to_transactions(self, test_engine):
        """Test that migration adds HYP columns to transactions table"""
        # Create minimal transactions table
        with test_engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS transactions (
                    id VARCHAR PRIMARY KEY
                )
            """))
            conn.commit()
        
        with patch('migrations.auto_migrate.engine', test_engine):
            run_hyp_migration()
        
        # Verify columns were added
        inspector = inspect(test_engine)
        columns = {col['name'] for col in inspector.get_columns('transactions')}
        
        # Check for HYP-related columns
        assert 'plan_id' in columns
        assert 'hyp_transaction_id' in columns
        assert 'hyp_internal_deal_id' in columns
        assert 'payment_url' in columns
    
    def test_migration_adds_columns_to_subscriptions(self, test_engine):
        """Test that migration adds columns to subscriptions table"""
        # Create minimal subscriptions table
        with test_engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS subscriptions (
                    id VARCHAR PRIMARY KEY
                )
            """))
            conn.commit()
        
        with patch('migrations.auto_migrate.engine', test_engine):
            run_hyp_migration()
        
        # Verify columns were added
        inspector = inspect(test_engine)
        columns = {col['name'] for col in inspector.get_columns('subscriptions')}
        
        # Check for expected columns
        assert 'plan_id' in columns
        assert 'license_id' in columns
        assert 'status' in columns
        assert 'start_date' in columns
        assert 'end_date' in columns
    
    def test_migration_does_not_fail_when_tables_missing(self, test_engine):
        """Test that migration doesn't fail when tables don't exist"""
        # Don't create any tables
        with patch('migrations.auto_migrate.engine', test_engine):
            result = run_hyp_migration()
            # Should still return True (or False but not raise)
            assert isinstance(result, bool)
    
    def test_migration_handles_errors_gracefully(self):
        """Test that migration handles errors and doesn't crash"""
        # Create a mock engine that raises an error
        mock_engine = Mock()
        mock_engine.connect.side_effect = Exception("Database connection failed")
        
        with patch('migrations.auto_migrate.engine', mock_engine):
            with patch('migrations.auto_migrate.inspect') as mock_inspect:
                mock_inspect.side_effect = Exception("Inspect failed")
                
                # Should not raise, should return False
                result = run_hyp_migration()
                assert result is False
    
    def test_migration_creates_indexes(self, test_engine):
        """Test that migration creates necessary indexes"""
        # Create tables
        with test_engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS transactions (
                    id VARCHAR PRIMARY KEY
                )
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS subscriptions (
                    id VARCHAR PRIMARY KEY
                )
            """))
            conn.commit()
        
        with patch('migrations.auto_migrate.engine', test_engine):
            run_hyp_migration()
        
        # Verify indexes were created (SQLite stores indexes)
        inspector = inspect(test_engine)
        indexes_trans = inspector.get_indexes('transactions')
        indexes_subs = inspector.get_indexes('subscriptions')
        
        # Check that indexes exist
        trans_index_names = [idx['name'] for idx in indexes_trans]
        subs_index_names = [idx['name'] for idx in indexes_subs]
        
        assert 'idx_transactions_plan_id' in trans_index_names
        assert 'idx_subscriptions_plan_id' in subs_index_names
        assert 'idx_subscriptions_status' in subs_index_names
