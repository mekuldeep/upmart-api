import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)

with engine.connect() as conn:
    # Add new columns to users table
    columns_to_add = [
        ("address", "TEXT"),
        ("city", "VARCHAR(100)"),
        ("state", "VARCHAR(100)"),
        ("zip", "VARCHAR(20)"),
        ("country", "VARCHAR(100) DEFAULT 'India'"),
        ("is_active", "BOOLEAN DEFAULT TRUE"),
        ("updated_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
    ]

    for col_name, col_type in columns_to_add:
        try:
            conn.execute(text(f"ALTER TABLE users ADD COLUMN {col_name} {col_type}"))
            print(f"Column {col_name} added to users")
        except Exception as e:
            print(f"Error adding {col_name}: {e}")

    conn.commit()
