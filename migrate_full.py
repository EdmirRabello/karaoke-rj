import sqlite3
from pathlib import Path

DB = Path("data/karaoke.db")

SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  email TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS favorites (
  user_id INTEGER NOT NULL,
  code INTEGER NOT NULL,
  created_at TEXT DEFAULT (datetime('now')),
  PRIMARY KEY (user_id, code),
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS song_overrides (
  code INTEGER PRIMARY KEY,
  package TEXT NOT NULL CHECK (package IN ('PLUS','BASICO')),
  updated_at TEXT DEFAULT (datetime('now'))
);
"""

con = sqlite3.connect(DB)
con.executescript(SQL)
con.commit()
con.close()
print("BANCO ATUALIZADO")
