import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)

with engine.connect() as conn:
    # 1. Add variant_id to product_images
    try:
        conn.execute(text("ALTER TABLE product_images ADD COLUMN variant_id INTEGER REFERENCES product_variants(id)"))
        print("Column variant_id added to product_images")
    except Exception as e:
        print(f"Error adding variant_id: {e}")

    # 2. Make product_id nullable in product_images
    try:
        conn.execute(text("ALTER TABLE product_images ALTER COLUMN product_id DROP NOT NULL"))
        print("Column product_id made nullable in product_images")
    except Exception as e:
        print(f"Error making product_id nullable: {e}")

    conn.commit()
