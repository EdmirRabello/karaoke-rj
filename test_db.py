import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "karaoke.db")

con = sqlite3.connect(DB_PATH)
cur = con.cursor()

print("\n=== CONTAGEM POR PACKAGE ===\n")
for row in cur.execute("SELECT package, COUNT(*) FROM songs GROUP BY package"):
    print(row)

print("\n=== EXEMPLOS REAIS ===\n")
for row in cur.execute("SELECT code, title, singer, package FROM songs LIMIT 20"):
    print(row)

con.close()
