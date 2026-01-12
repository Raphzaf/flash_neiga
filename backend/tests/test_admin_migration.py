"""
Unit tests for admin migration endpoint
"""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from pathlib import Path
import sys

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from server import app
from database import Base, get_db
from models import TransactionDB, SubscriptionDB, UserDB, User
from auth import get_current_user

# Create test database
SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///./test_admin_migration.db"
engine = create_engine(SQLALCHEMY_TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Override get_db dependency
def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

# Setup and teardown
@pytest.fixture(scope="function")
def test_db():
    Base.metadata.create_all(bind=engine)
    yield TestingSessionLocal()
    Base.metadata.drop_all(bind=engine)

@pytest.fixture
def client():
    return TestClient(app)

# Test user
SAMPLE_USER = User(
    id="test-user-123",
    email="test@example.com"
)


class TestAdminMigration:
    """Test admin migration endpoint"""
    
    def test_run_migration_without_auth(self, client):
        """Test run-migration endpoint without authentication"""
        response = client.get("/api/admin/run-migration")
        assert response.status_code == 403  # FastAPI security returns 403 for missing auth
    
    def test_run_migration_with_auth(self, client, test_db):
        """Test run-migration endpoint with authentication"""
        # Mock the get_current_user to return a test user
        def mock_get_current_user():
            return SAMPLE_USER
        
        app.dependency_overrides[get_current_user] = mock_get_current_user
        
        try:
            response = client.get("/api/admin/run-migration")
            assert response.status_code == 200
            
            data = response.json()
            assert data["success"] == True
            assert "message" in data
            assert "log" in data
            assert "Migration completed successfully" in data["log"]
            
        finally:
            # Clean up override
            if get_current_user in app.dependency_overrides:
                del app.dependency_overrides[get_current_user]
    
    def test_migration_is_idempotent(self, client, test_db):
        """Test that migration can be run multiple times safely"""
        # Mock the get_current_user to return a test user
        def mock_get_current_user():
            return SAMPLE_USER
        
        app.dependency_overrides[get_current_user] = mock_get_current_user
        
        try:
            # Run migration first time
            response1 = client.get("/api/admin/run-migration")
            assert response1.status_code == 200
            data1 = response1.json()
            assert data1["success"] == True
            
            # Run migration second time - should still succeed
            response2 = client.get("/api/admin/run-migration")
            assert response2.status_code == 200
            data2 = response2.json()
            assert data2["success"] == True
            
            # Both runs should complete successfully (tables may not exist in test DB)
            assert "Migration completed successfully" in data2["log"]
            
        finally:
            # Clean up override
            if get_current_user in app.dependency_overrides:
                del app.dependency_overrides[get_current_user]
    
    def test_migration_checks_transactions_table(self, client, test_db):
        """Test that migration checks transactions table"""
        def mock_get_current_user():
            return SAMPLE_USER
        
        app.dependency_overrides[get_current_user] = mock_get_current_user
        
        try:
            response = client.get("/api/admin/run-migration")
            assert response.status_code == 200
            
            data = response.json()
            log = data["log"]
            
            # Should check transactions table
            assert "Checking transactions table" in log
            
        finally:
            if get_current_user in app.dependency_overrides:
                del app.dependency_overrides[get_current_user]
    
    def test_migration_checks_subscriptions_table(self, client, test_db):
        """Test that migration checks subscriptions table"""
        def mock_get_current_user():
            return SAMPLE_USER
        
        app.dependency_overrides[get_current_user] = mock_get_current_user
        
        try:
            response = client.get("/api/admin/run-migration")
            assert response.status_code == 200
            
            data = response.json()
            log = data["log"]
            
            # Should check subscriptions table
            assert "Checking subscriptions table" in log
            
        finally:
            if get_current_user in app.dependency_overrides:
                del app.dependency_overrides[get_current_user]
