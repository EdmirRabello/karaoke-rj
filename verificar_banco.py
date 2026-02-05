import sqlite3

con = sqlite3.connect("data/karaoke.db")
cur = con.cursor()

total = cur.execute("select count(*) from songs").fetchone()[0]
plus = cur.execute("select count(*) from songs where package='PLUS'").fetchone()[0]
basico = cur.execute("select count(*) from songs where package='BASICO'").fetchone()[0]

print("TOTAL:", total)
print("PLUS:", plus)
print("BASICO:", basico)

con.close()
