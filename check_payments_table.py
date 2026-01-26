import sqlite3

# Ma'lumotlar bazasini tekshirish
conn = sqlite3.connect('market.db')
cursor = conn.cursor()

# Payments jadvalining strukturasini ko'rish
cursor.execute("PRAGMA table_info(payments)")
columns = cursor.fetchall()

print("\n📊 Payments jadvali ustunlari:")
for col in columns:
    print(f"  - {col[1]} ({col[2]})")

# shift_id ustuni bormi?
has_shift_id = any(col[1] == 'shift_id' for col in columns)
print(f"\n✅ shift_id ustuni: {'MAVJUD' if has_shift_id else 'YUOQ'}")

conn.close()
