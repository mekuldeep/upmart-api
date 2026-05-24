import sqlite3

def update_db():
    try:
        conn = sqlite3.connect('dev.db')
        cursor = conn.cursor()
        
        # Check if column already exists in product_variants
        cursor.execute("PRAGMA table_info(product_variants)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'price' not in columns:
            print("Adding 'price' column to 'product_variants' table...")
            cursor.execute("ALTER TABLE product_variants ADD COLUMN price NUMERIC(10, 2)")
            conn.commit()
            print("Column added successfully.")
        else:
            print("'price' column already exists in 'product_variants'.")
            
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    update_db()
