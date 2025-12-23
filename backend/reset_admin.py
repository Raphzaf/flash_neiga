"""
Script to reset the admin user password.
Use this if you forget the admin password.

Usage:
    python reset_admin.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import SessionLocal
from models import UserDB
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def reset_admin_password():
    """Reset admin password to 'admin'"""
    
    db = SessionLocal()
    
    try:
        admin_email = "admin@gmail.com"
        admin_user = db.query(UserDB).filter(UserDB.email == admin_email).first()
        
        if not admin_user:
            print(f"❌ Admin user not found: {admin_email}")
            print("   Run create_admin.py first to create the admin user.")
            return False
        
        # Reset password
        admin_user.hashed_password = pwd_context.hash("admin")
        db.commit()
        
        print("✅ Admin password reset successfully!")
        print(f"   Email: {admin_email}")
        print(f"   New Password: admin")
        
        return True
        
    except Exception as e:
        print(f"❌ Error resetting password: {e}")
        db.rollback()
        return False
        
    finally:
        db.close()

if __name__ == "__main__":
    print("=" * 60)
    print("Flash Neiga - Reset Admin Password")
    print("=" * 60)
    print("")
    
    success = reset_admin_password()
    
    print("")
    print("=" * 60)
    
    sys.exit(0 if success else 1)
