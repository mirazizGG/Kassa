import sqlite3
import os

# Base directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(BASE_DIR, 'market.db')

def migrate():
    print(f"Connecting to {db_path}...")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        print("Adding low_stock_threshold column to store_settings...")
        cursor.execute("ALTER TABLE store_settings ADD COLUMN low_stock_threshold INTEGER DEFAULT 5;")
        conn.commit()
        print("Success!")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e).lower():
            print("Column already exists.")
        else:
            print(f"Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    # Check if file exists
    if os.path.exists(db_path):
        migrate()
    else:
        print(f"Database not found at {db_path}")
