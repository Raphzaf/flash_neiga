"""
Script to create an admin user in the database.
Run this once after deploying to create the initial admin account.

Usage:
    python create_admin.py
"""

import sys
import os

# Add backend directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import SessionLocal, engine, Base
from models import UserDB
from passlib.context import CryptContext

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def create_admin_user():
    """Create admin user with credentials: admin@gmail.com / admin"""
    
    print("🔧 Creating database tables if they don't exist...")
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    
    try:
        # Check if admin already exists
        admin_email = "admin@gmail.com"
        existing_admin = db.query(UserDB).filter(UserDB.email == admin_email).first()
        
        if existing_admin:
            print(f"⚠️  Admin user already exists: {admin_email}")
            print("ℹ️  If you need to reset the password, delete the user first from the database.")
            return False
        
        # Create admin user
        print(f"📝 Creating admin user: {admin_email}")
        
        hashed_password = pwd_context.hash("admin")
        
        admin_user = UserDB(
            email=admin_email,
            hashed_password=hashed_password
        )
        
        db.add(admin_user)
        db.commit()
        db.refresh(admin_user)
        
        print("✅ Admin user created successfully!")
        print(f"   Email: {admin_email}")
        print(f"   Password: admin")
        print(f"   User ID: {admin_user.id}")
        print("")
        print("⚠️  IMPORTANT: Change the admin password after first login!")
        print("   You can access the app at your frontend URL and login with these credentials.")
        
        return True
        
    except Exception as e:
        print(f"❌ Error creating admin user: {e}")
        db.rollback()
        return False
        
    finally:
        db.close()

if __name__ == "__main__":
    print("=" * 60)
    print("Flash Neiga - Admin User Creation")
    print("=" * 60)
    print("")
    
    success = create_admin_user()
    
    print("")
    print("=" * 60)
    
    sys.exit(0 if success else 1)
