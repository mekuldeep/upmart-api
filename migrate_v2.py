from database import engine
from sqlalchemy import text

def update_db():
    try:
        with engine.connect() as conn:
            # Check if price column exists in product_variants
            # This is slightly db-dependent but we can try common ways
            
            # For Postgres
            try:
                conn.execute(text("ALTER TABLE product_variants ADD COLUMN price NUMERIC(10, 2)"))
                conn.commit()
                print("Added price to product_variants (Postgres/Other)")
            except Exception as e:
                print(f"Postgres attempt failed: {e}")
                # For SQLite
                try:
                    conn.execute(text("ALTER TABLE product_variants ADD COLUMN price NUMERIC(10, 2)"))
                    conn.commit()
                    print("Added price to product_variants (SQLite)")
                except Exception as e2:
                    print(f"SQLite attempt failed: {e2}")
            
    except Exception as e:
        print(f"Migration failed: {e}")

if __name__ == "__main__":
    update_db()
