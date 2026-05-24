import sqlite3

def update_db():
    try:
        conn = sqlite3.connect('dev.db')
        cursor = conn.cursor()
        
        # Check if column already exists
        cursor.execute("PRAGMA table_info(products)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'sizes' not in columns:
            print("Adding 'sizes' column to 'products' table...")
            cursor.execute("ALTER TABLE products ADD COLUMN sizes JSON")
            conn.commit()
            print("Column added successfully.")
        else:
            print("'sizes' column already exists.")
            
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    update_db()
