import sqlite3

con = sqlite3.connect("data/karaoke.db")
cur = con.cursor()

# Conta músicas do cantor BELO
qtd = cur.execute("SELECT COUNT(*) FROM songs WHERE singer LIKE '%BELO%'").fetchone()[0]
print("Músicas com BELO:", qtd)

# Mostra algumas músicas do BELO
rows = cur.execute("SELECT code, title, singer FROM songs WHERE singer LIKE '%BELO%' LIMIT 10").fetchall()
for r in rows:
    print(r)

con.close()
