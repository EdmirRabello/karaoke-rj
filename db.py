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

        # ------------------------------------------------------------
        # TABELA SONGS
        # ------------------------------------------------------------
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

        # ------------------------------------------------------------
        # FAVORITES (garante existir no Render / produção)
        # ------------------------------------------------------------
        con.execute("""
        CREATE TABLE IF NOT EXISTS favorites (
            user_id INTEGER NOT NULL,
            code INTEGER NOT NULL,
            created_at TEXT DEFAULT (datetime('now')),
            PRIMARY KEY (user_id, code)
        );
        """)

        # ------------------------------------------------------------
        # Índices songs
        # ------------------------------------------------------------
        con.execute("CREATE INDEX IF NOT EXISTS idx_songs_pkg ON songs(package);")
        con.execute("CREATE INDEX IF NOT EXISTS idx_songs_title_norm ON songs(title_norm);")
        con.execute("CREATE INDEX IF NOT EXISTS idx_songs_singer_norm ON songs(singer_norm);")

        # ------------------------------------------------------------
        # ✅ GARANTIR UPSERT POR code (precisa UNIQUE)
        # - Se já existir duplicado por algum motivo, mantém o menor id
        # ------------------------------------------------------------
        con.execute("""
        DELETE FROM songs
        WHERE id NOT IN (
          SELECT MIN(id)
          FROM songs
          GROUP BY code
        );
        """)

        con.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_songs_code ON songs(code);")

        # ------------------------------------------------------------
        # Índices favorites
        # ------------------------------------------------------------
        con.execute("CREATE INDEX IF NOT EXISTS idx_favorites_code ON favorites(code);")
        con.execute("CREATE INDEX IF NOT EXISTS idx_favorites_user ON favorites(user_id, code);")

        con.commit()


@contextmanager
def get_conn():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    try:
        yield con
    finally:
        con.close()
