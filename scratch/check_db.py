from database import SessionLocal
import models

def check_db():
    db = SessionLocal()
    try:
        user = db.query(models.User).filter(models.User.email == 'admin@upmart.com').first()
        if user:
            print(f"User email: {user.email}")
            print(f"Is Admin: {user.is_admin}")
            print(f"Hash: {user.password_hash}")
            print(f"Hash Length: {len(user.password_hash)}")
        else:
            print("User not found")
    finally:
        db.close()

if __name__ == "__main__":
    check_db()
