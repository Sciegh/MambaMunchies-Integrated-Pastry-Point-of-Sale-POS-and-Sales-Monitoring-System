import sqlite3

conn = sqlite3.connect("mambamunchies.db")
cursor = conn.cursor()
cursor.execute("PRAGMA table_info(sales)")
print(cursor.fetchall())
conn.close()
