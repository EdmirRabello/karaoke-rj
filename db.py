from __future__ import annotations
import os
import sqlite3
from contextlib import contextmanager

DB_PATH = os.getenv("KARAOKE_DB_PATH", os.path.join(os.path.dirname(__file__), "data", "karaoke.db"))

def init_db() -> None:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with sqlite3.connect(DB_PATH) as con:
        con.execute("PRAGMA journal_mode=WAL;")
        con.execute("PRAGMA synchronous=NORMAL;")
        con.execute("PRAGMA foreign_keys=ON;")

        con.execute("""
        CREATE TABLE IF NOT EXISTS songs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code INTEGER NOT NULL,
            title TEXT NOT NULL,
            singer TEXT NOT NULL,
            snippet TEXT,
            package TEXT NOT NULL DEFAULT 'PLUS',
            type TEXT,
            duplicated INTEGER NOT NULL DEFAULT 0,
            title_norm TEXT NOT NULL,
            singer_norm TEXT NOT NULL,
            snippet_norm TEXT
        );
        """)

        # Indexes (sem UNIQUE porque pode existir o mesmo código repetido na base)
        con.execute("CREATE INDEX IF NOT EXISTS idx_songs_code ON songs(code);")
        con.execute("CREATE INDEX IF NOT EXISTS idx_songs_pkg ON songs(package);")
        con.execute("CREATE INDEX IF NOT EXISTS idx_songs_title_norm ON songs(title_norm);")
        con.execute("CREATE INDEX IF NOT EXISTS idx_songs_singer_norm ON songs(singer_norm);")

@contextmanager
def get_conn():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    try:
        yield con
    finally:
        con.close()
