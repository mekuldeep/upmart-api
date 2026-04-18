import os
import sys
# Add current directory to path so we can import models/database
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import datetime

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("DATABASE_URL not found in .env")
    sys.exit(1)

engine = create_engine(DATABASE_URL)

categories = [
    {"name": "Men", "slug": "men", "description": "Men's Apparel and Fashion"},
    {"name": "Women", "slug": "women", "description": "Women's Apparel and Fashion"},
    {"name": "Kids", "slug": "kids", "description": "Clothing for Kids"},
    {"name": "Accessories", "slug": "accessories", "description": "Jewelry, Bags, and more"},
]

with engine.connect() as conn:
    print("Checking categories...")
    for cat in categories:
        # Check if exists by slug
        result = conn.execute(text("SELECT id FROM categories WHERE slug = :slug"), {"slug": cat['slug']}).fetchone()
        if not result:
            conn.execute(
                text("INSERT INTO categories (name, slug, description, created_at) VALUES (:name, :slug, :description, :created_at)"),
                {
                    "name": cat['name'],
                    "slug": cat['slug'],
                    "description": cat['description'],
                    "created_at": datetime.datetime.utcnow()
                }
            )
            print(f"Created category: {cat['name']}")
        else:
            print(f"Category already exists: {cat['name']}")
    conn.commit()
print("Done seeding categories.")
