
import sqlite3
import os

db_path = r'c:\Users\u0068\Desktop\Kassa\backend\market.db'
if not os.path.exists(db_path):
    print(f"DB not found at {db_path}")
else:
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        print(f"Connected successfully. Tables: {len(tables)}")
        conn.close()
    except Exception as e:
        print(f"Error: {e}")
