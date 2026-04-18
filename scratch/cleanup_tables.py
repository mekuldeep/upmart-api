from database import engine
from sqlalchemy import text

def cleanup_old_tables():
    with engine.connect() as conn:
        print("Dropping old tables...")
        try:
            conn.execute(text("DROP TABLE IF EXISTS admins CASCADE"))
            print("Dropped 'admins' table.")
        except Exception as e:
            print(f"Error dropping 'admins': {e}")
            
        try:
            conn.execute(text("DROP TABLE IF EXISTS customers CASCADE"))
            print("Dropped 'customers' table.")
        except Exception as e:
            print(f"Error dropping 'customers': {e}")
            
        conn.commit()
    print("Cleanup complete.")

if __name__ == "__main__":
    cleanup_old_tables()
