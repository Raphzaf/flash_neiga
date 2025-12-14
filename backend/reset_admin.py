"""
Script to reset the admin user password in the database.
Run this if you need to reset the admin password.

Usage:
    python reset_admin.py
"""

import sys
import os

# Add backend directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import SessionLocal
from models import UserDB
from passlib.context import CryptContext

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def reset_admin_password():
    """Reset admin password to: admin"""
    
    db = SessionLocal()
    
    try:
        # Find admin user
        admin_email = "admin@gmail.com"
        admin_user = db.query(UserDB).filter(UserDB.email == admin_email).first()
        
        if not admin_user:
            print(f"❌ Admin user not found: {admin_email}")
            print("ℹ️  Run create_admin.py first to create the admin user.")
            return False
        
        # Reset password
        print(f"🔧 Resetting password for admin user: {admin_email}")
        
        admin_user.hashed_password = pwd_context.hash("admin")
        
        db.commit()
        
        print("✅ Admin password reset successfully!")
        print(f"   Email: {admin_email}")
        print(f"   Password: admin")
        print("")
        print("⚠️  IMPORTANT: Change the admin password after first login!")
        
        return True
        
    except Exception as e:
        print(f"❌ Error resetting admin password: {e}")
        db.rollback()
        return False
        
    finally:
        db.close()

if __name__ == "__main__":
    print("=" * 60)
    print("Flash Neiga - Admin Password Reset")
    print("=" * 60)
    print("")
    
    success = reset_admin_password()
    
    print("")
    print("=" * 60)
    
    sys.exit(0 if success else 1)
