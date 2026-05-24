import os
from sqlalchemy import create_engine, text, inspect
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

def update_db():
    try:
        print(f"Connecting to: {DATABASE_URL}")
        engine = create_engine(DATABASE_URL)
        inspector = inspect(engine)
        
        columns = [c['name'] for c in inspector.get_columns('products')]
        
        if 'sizes' not in columns:
            print("Adding 'sizes' column to 'products' table...")
            with engine.connect() as conn:
                # Use JSON for both SQLite and Postgres
                # In Postgres it will be JSON type
                # In SQLite it will be JSON type (if supported) or TEXT
                conn.execute(text("ALTER TABLE products ADD COLUMN sizes JSON"))
                conn.commit()
            print("Column added successfully.")
        else:
            print("'sizes' column already exists.")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    update_db()
