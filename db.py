from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from typing import Any, Iterable, Optional, Sequence, List, Dict

# ============================================================
# DB backend selection
# - Default: SQLite file (dev / Windows)
# - Production recommended: Postgres via DATABASE_URL (Render)
# ============================================================

DATABASE_URL = (
    os.getenv("DATABASE_URL")
    or os.getenv("RENDER_DATABASE_URL")
    or os.getenv("POSTGRES_URL")
    or os.getenv("POSTGRESQL_URL")
)

DB_KIND = "postgres" if DATABASE_URL else "sqlite"

# SQLite path (dev)
DB_PATH = os.getenv(
    "KARAOKE_DB_PATH",
    os.path.join(os.path.dirname(__file__), "data", "karaoke.db"),
)

# Lazy import for postgres driver
_psycopg2 = None
_psycopg2_extras = None


def _ensure_pg():
    global _psycopg2, _psycopg2_extras
    if _psycopg2 is None:
        import psycopg2  # type: ignore
        import psycopg2.extras  # type: ignore
        _psycopg2 = psycopg2
        _psycopg2_extras = psycopg2.extras


def _pg_connect():
    _ensure_pg()
    assert _psycopg2 is not None
    # Render often needs SSL; if URL already has sslmode we don't override.
    url = DATABASE_URL or ""
    kwargs = {}
    if "sslmode=" not in url:
        kwargs["sslmode"] = "require"
    return _psycopg2.connect(url, **kwargs)


def _adapt_sql(sql: str) -> str:
    # sqlite uses "?" placeholders; psycopg2 uses "%s"
    if DB_KIND == "postgres":
        return sql.replace("?", "%s")
    return sql


def init_db() -> None:
    if DB_KIND == "postgres":
        _init_db_postgres()
    else:
        _init_db_sqlite()


def _init_db_sqlite() -> None:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

    with sqlite3.connect(DB_PATH) as con:
        con.execute("PRAGMA journal_mode=WAL;")
        con.execute("PRAGMA synchronous=NORMAL;")
        con.execute("PRAGMA foreign_keys=ON;")

        con.execute(
            """
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
            """
        )

        con.execute(
            """
            CREATE TABLE IF NOT EXISTS favorites (
                user_id INTEGER NOT NULL,
                code INTEGER NOT NULL,
                created_at TEXT DEFAULT (datetime('now')),
                PRIMARY KEY (user_id, code)
            );
            """
        )

        # indices
        con.execute("CREATE INDEX IF NOT EXISTS idx_songs_pkg ON songs(package);")
        con.execute("CREATE INDEX IF NOT EXISTS idx_songs_title_norm ON songs(title_norm);")
        con.execute("CREATE INDEX IF NOT EXISTS idx_songs_singer_norm ON songs(singer_norm);")

        # keep smallest id per code then UNIQUE index (UPSERT safety)
        con.execute(
            """
            DELETE FROM songs
            WHERE id NOT IN (
              SELECT MIN(id)
              FROM songs
              GROUP BY code
            );
            """
        )
        con.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_songs_code ON songs(code);")

        con.execute("CREATE INDEX IF NOT EXISTS idx_favorites_code ON favorites(code);")
        con.execute("CREATE INDEX IF NOT EXISTS idx_favorites_user ON favorites(user_id, code);")

        con.commit()


def _init_db_postgres() -> None:
    _ensure_pg()
    with _pg_connect() as con:
        with con.cursor() as cur:
            # songs
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS songs (
                    id BIGSERIAL PRIMARY KEY,
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
                """
            )

            # favorites
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS favorites (
                    user_id BIGINT NOT NULL,
                    code INTEGER NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    PRIMARY KEY (user_id, code)
                );
                """
            )

            # de-dup by code then unique constraint
            cur.execute(
                """
                WITH ranked AS (
                    SELECT id, code,
                           ROW_NUMBER() OVER (PARTITION BY code ORDER BY id ASC) AS rn
                    FROM songs
                )
                DELETE FROM songs
                WHERE id IN (SELECT id FROM ranked WHERE rn > 1);
                """
            )
            cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_songs_code ON songs(code);")

            cur.execute("CREATE INDEX IF NOT EXISTS idx_songs_pkg ON songs(package);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_songs_title_norm ON songs(title_norm);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_songs_singer_norm ON songs(singer_norm);")

            cur.execute("CREATE INDEX IF NOT EXISTS idx_favorites_code ON favorites(code);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_favorites_user ON favorites(user_id, code);")

        con.commit()


@contextmanager
def get_conn():
    """Raw connection (mostly for legacy code). Prefer fetchall/execute helpers."""
    if DB_KIND == "postgres":
        con = _pg_connect()
        try:
            yield con
        finally:
            con.close()
    else:
        con = sqlite3.connect(DB_PATH)
        con.row_factory = sqlite3.Row
        try:
            yield con
        finally:
            con.close()


def fetchall(sql: str, params: Optional[Sequence[Any]] = None) -> List[Dict[str, Any]]:
    params = params or []
    if DB_KIND == "postgres":
        _ensure_pg()
        assert _psycopg2_extras is not None
        with _pg_connect() as con:
            with con.cursor(cursor_factory=_psycopg2_extras.RealDictCursor) as cur:
                cur.execute(_adapt_sql(sql), list(params))
                rows = cur.fetchall()
                return [dict(r) for r in rows]
    else:
        with get_conn() as con:
            rows = con.execute(sql, params).fetchall()
            return [dict(r) for r in rows]


def fetchone_value(sql: str, params: Optional[Sequence[Any]] = None, default: Any = None) -> Any:
    params = params or []
    if DB_KIND == "postgres":
        _ensure_pg()
        assert _psycopg2_extras is not None
        with _pg_connect() as con:
            with con.cursor(cursor_factory=_psycopg2_extras.RealDictCursor) as cur:
                cur.execute(_adapt_sql(sql), list(params))
                row = cur.fetchone()
                if not row:
                    return default
                # first column value
                return next(iter(row.values()))
    else:
        with get_conn() as con:
            row = con.execute(sql, params).fetchone()
            if not row:
                return default
            return row[0]


def execute(sql: str, params: Optional[Sequence[Any]] = None) -> None:
    params = params or []
    if DB_KIND == "postgres":
        with _pg_connect() as con:
            with con.cursor() as cur:
                cur.execute(_adapt_sql(sql), list(params))
            con.commit()
    else:
        with get_conn() as con:
            con.execute(sql, params)
            con.commit()
