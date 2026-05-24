import os
import sys
from getpass import getpass
from dotenv import load_dotenv

# Add the current directory to python path to import app modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import SessionLocal
import models
from utils.auth import get_password_hash

def create_admin():
    load_dotenv()
    db = SessionLocal()
    try:
        print("--- Safe Admin User Creator ---")
        
        email = input("Enter admin email (default: admin@upmart.com): ").strip()
        if not email:
            email = "admin@upmart.com"
            
        # Check if user already exists
        existing_user = db.query(models.User).filter(models.User.email == email).first()
        if existing_user:
            print(f"\nUser with email {email} already exists.")
            make_admin = input("Do you want to grant this user admin privileges? (y/n): ").strip().lower()
            if make_admin == 'y':
                existing_user.is_admin = True
                db.commit()
                print(f"Granted admin privileges to {email}.")
            else:
                print("No changes made.")
            return

        name = input("Enter admin name (default: Admin User): ").strip()
        if not name:
            name = "Admin User"

        password = getpass("Enter admin password (min 8 chars): ").strip()
        if not password:
            print("Password cannot be empty.")
            return
        if len(password) < 8:
            print("Warning: Password is less than 8 characters.")
            confirm = input("Are you sure you want to use this password? (y/n): ").strip().lower()
            if confirm != 'y':
                return

        # Confirm password
        confirm_password = getpass("Confirm admin password: ").strip()
        if password != confirm_password:
            print("Passwords do not match.")
            return

        new_admin = models.User(
            email=email,
            name=name,
            password_hash=get_password_hash(password),
            is_admin=True,
            is_active=True
        )
        db.add(new_admin)
        db.commit()
        print(f"\nSuccess! Admin user '{name}' ({email}) created successfully.")
    except Exception as e:
        print(f"\nAn error occurred: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == '__main__':
    create_admin()
