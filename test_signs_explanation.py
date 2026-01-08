#!/usr/bin/env python3
"""
Test script to verify the traffic signs explanation feature implementation.
This tests all the requirements from issue #19.
"""

import sys
import os
import traceback
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database import Base, get_db
from server import app
from models import TrafficSignDB, UserDB
from passlib.context import CryptContext
import uuid

# Create test database
TEST_DATABASE_URL = "sqlite:///./test_signs.db"
engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Override get_db dependency
def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

# Create tables
Base.metadata.create_all(bind=engine)

# Create test client
client = TestClient(app)

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def setup_test_user():
    """Create a test user and return auth token"""
    db = TestingSessionLocal()
    
    # Create test user
    test_email = "admin@test.com"
    test_password = "testpassword123"
    
    # Check if user exists
    existing_user = db.query(UserDB).filter(UserDB.email == test_email).first()
    if not existing_user:
        user = UserDB(
            id=str(uuid.uuid4()),
            email=test_email,
            hashed_password=pwd_context.hash(test_password)
        )
        db.add(user)
        db.commit()
    
    db.close()
    
    # Login to get token (using OAuth2PasswordRequestForm)
    response = client.post("/api/auth/login", data={
        "username": test_email,
        "password": test_password
    })
    
    if response.status_code != 200:
        print(f"❌ Login failed: {response.status_code}")
        print(response.json())
        sys.exit(1)
    
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

def test_traffic_sign_model():
    """Test 1: Verify TrafficSignDB model has explanation field"""
    print("\n📋 Test 1: Verify TrafficSignDB model has explanation field")
    
    from sqlalchemy import inspect
    inspector = inspect(engine)
    columns = inspector.get_columns('traffic_signs')
    column_names = [col['name'] for col in columns]
    
    required_columns = ['id', 'number', 'name', 'description', 'image_url', 'category', 'explanation', 'created_at']
    
    for col in required_columns:
        if col in column_names:
            print(f"  ✅ Column '{col}' exists")
        else:
            print(f"  ❌ Column '{col}' missing")
            return False
    
    # Check that explanation is nullable
    explanation_col = next(col for col in columns if col['name'] == 'explanation')
    if explanation_col['nullable']:
        print(f"  ✅ Explanation column is nullable")
    else:
        print(f"  ❌ Explanation column should be nullable")
        return False
    
    return True

def test_create_sign_with_explanation():
    """Test 2: Create a traffic sign and add explanation"""
    print("\n📋 Test 2: Create traffic sign and add explanation")
    
    db = TestingSessionLocal()
    
    # Create a test sign
    sign = TrafficSignDB(
        id=str(uuid.uuid4()),
        number="A1",
        name="Test Sign",
        description="Test Description",
        image_url="https://example.com/sign.png",
        category="Danger",
        explanation="This is a test explanation"
    )
    db.add(sign)
    db.commit()
    db.refresh(sign)
    
    print(f"  ✅ Created sign with ID: {sign.id}")
    print(f"  ✅ Explanation: {sign.explanation}")
    
    sign_id = sign.id
    db.close()
    
    return sign_id

def test_admin_list_signs_endpoint(headers):
    """Test 3: GET /api/admin/signs endpoint"""
    print("\n📋 Test 3: Test GET /api/admin/signs endpoint")
    
    # Test basic list
    response = client.get("/api/admin/signs", headers=headers)
    if response.status_code != 200:
        print(f"  ❌ Failed with status {response.status_code}")
        return False
    
    signs = response.json()
    print(f"  ✅ Retrieved {len(signs)} signs")
    
    # Verify response structure
    if len(signs) > 0:
        sign = signs[0]
        required_fields = ['id', 'number', 'name', 'description', 'category', 'explanation', 'has_explanation']
        for field in required_fields:
            if field in sign:
                print(f"  ✅ Response includes '{field}' field")
            else:
                print(f"  ❌ Response missing '{field}' field")
                return False
    
    # Test missingOnly filter
    response = client.get("/api/admin/signs?missingOnly=true", headers=headers)
    if response.status_code != 200:
        print(f"  ❌ missingOnly filter failed")
        return False
    print(f"  ✅ missingOnly filter works")
    
    return True

def test_update_sign_explanation_endpoint(headers, sign_id):
    """Test 4: PATCH /api/admin/signs/{sign_id}/explanation endpoint"""
    print("\n📋 Test 4: Test PATCH /api/admin/signs/{sign_id}/explanation endpoint")
    
    new_explanation = "Updated explanation for testing"
    
    response = client.patch(
        f"/api/admin/signs/{sign_id}/explanation",
        headers=headers,
        json={"explanation": new_explanation}
    )
    
    if response.status_code != 200:
        print(f"  ❌ Failed with status {response.status_code}")
        print(response.json())
        return False
    
    result = response.json()
    if result.get("success") and result.get("explanation") == new_explanation:
        print(f"  ✅ Explanation updated successfully")
        print(f"  ✅ New explanation: {result['explanation']}")
    else:
        print(f"  ❌ Update failed or explanation doesn't match")
        return False
    
    # Verify the update persisted
    db = TestingSessionLocal()
    sign = db.query(TrafficSignDB).filter(TrafficSignDB.id == sign_id).first()
    if sign and sign.explanation == new_explanation:
        print(f"  ✅ Explanation persisted in database")
    else:
        print(f"  ❌ Explanation not persisted correctly")
        db.close()
        return False
    db.close()
    
    return True

def test_delete_sign_endpoint(headers, sign_id):
    """Test 5: DELETE /api/admin/signs/{sign_id} endpoint"""
    print("\n📋 Test 5: Test DELETE /api/admin/signs/{sign_id} endpoint")
    
    response = client.delete(f"/api/admin/signs/{sign_id}", headers=headers)
    
    if response.status_code != 200:
        print(f"  ❌ Failed with status {response.status_code}")
        return False
    
    result = response.json()
    if result.get("success"):
        print(f"  ✅ Sign deleted successfully")
    else:
        print(f"  ❌ Delete failed")
        return False
    
    # Verify deletion
    db = TestingSessionLocal()
    sign = db.query(TrafficSignDB).filter(TrafficSignDB.id == sign_id).first()
    if sign is None:
        print(f"  ✅ Sign no longer exists in database")
    else:
        print(f"  ❌ Sign still exists in database")
        db.close()
        return False
    db.close()
    
    return True

def test_frontend_integration():
    """Test 6: Verify frontend Admin.js has the required components"""
    print("\n📋 Test 6: Verify frontend implementation")
    
    admin_js_path = os.path.join(os.path.dirname(__file__), 'frontend', 'src', 'pages', 'Admin.js')
    
    if not os.path.exists(admin_js_path):
        print(f"  ❌ Admin.js not found at {admin_js_path}")
        return False
    
    with open(admin_js_path, 'r') as f:
        content = f.read()
    
    # Check for required state variables
    required_states = [
        'manageSigns',
        'manageSignsSearch',
        'manageSignsLoading',
        'manageSignsOnlyMissing'
    ]
    
    for state in required_states:
        if state in content:
            print(f"  ✅ State '{state}' found in Admin.js")
        else:
            print(f"  ❌ State '{state}' missing in Admin.js")
            return False
    
    # Check for required functions
    required_functions = [
        'fetchManageSigns',
        'saveSignExplanation',
        'deleteSign'
    ]
    
    for func in required_functions:
        if func in content:
            print(f"  ✅ Function '{func}' found in Admin.js")
        else:
            print(f"  ❌ Function '{func}' missing in Admin.js")
            return False
    
    # Check for the manageSigns tab
    if 'manageSigns' in content and 'Gérer Panneaux' in content:
        print(f"  ✅ 'Gérer Panneaux' tab found in Admin.js")
    else:
        print(f"  ❌ 'Gérer Panneaux' tab missing in Admin.js")
        return False
    
    return True

def cleanup():
    """Clean up test database"""
    import os
    if os.path.exists("test_signs.db"):
        os.remove("test_signs.db")
        print("\n🧹 Cleaned up test database")

def main():
    print("=" * 60)
    print("Testing Traffic Signs Explanation Feature (Issue #19)")
    print("=" * 60)
    
    try:
        # Run tests
        all_passed = True
        
        # Test 1: Model verification
        if not test_traffic_sign_model():
            all_passed = False
        
        # Setup authentication
        print("\n🔐 Setting up test user and authentication...")
        headers = setup_test_user()
        print("  ✅ Authentication successful")
        
        # Test 2: Create sign with explanation
        sign_id = test_create_sign_with_explanation()
        if not sign_id:
            all_passed = False
        
        # Test 3: List signs endpoint
        if not test_admin_list_signs_endpoint(headers):
            all_passed = False
        
        # Test 4: Update explanation endpoint
        if sign_id and not test_update_sign_explanation_endpoint(headers, sign_id):
            all_passed = False
        
        # Test 5: Delete sign endpoint
        if sign_id and not test_delete_sign_endpoint(headers, sign_id):
            all_passed = False
        
        # Test 6: Frontend integration
        if not test_frontend_integration():
            all_passed = False
        
        # Summary
        print("\n" + "=" * 60)
        if all_passed:
            print("✅ ALL TESTS PASSED - Feature is fully implemented!")
        else:
            print("❌ SOME TESTS FAILED - Check output above")
        print("=" * 60)
        
        cleanup()
        
        return 0 if all_passed else 1
        
    except Exception as e:
        print(f"\n❌ Test suite failed with error: {e}")
        traceback.print_exc()
        cleanup()
        return 1

if __name__ == "__main__":
    sys.exit(main())
