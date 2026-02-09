from __future__ import annotations

import os
import time
import sqlite3
from pathlib import Path
from typing import Optional, List, Any

from fastapi import FastAPI, Query, Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

# ============================================================
# APP
# ============================================================

app = FastAPI(title="Karaokê RJ • Cantus")

# ============================================================
# BASE / PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "karaoke.db"

STATIC_DIR = BASE_DIR / "static"
SW_PATH = STATIC_DIR / "sw.js"

# ============================================================
# ASSETS VERSION
# ============================================================

ASSET_V = os.getenv("ASSET_V") or str(int(time.time()))

# ============================================================
# MIDDLEWARES
# ============================================================

app.add_middleware(GZipMiddleware, minimum_size=800)

# ============================================================
# STATIC
# ============================================================

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/sw.js", include_in_schema=False)
def service_worker():
    return FileResponse(str(SW_PATH), media_type="application/javascript")


@app.get("/static/sw.js", include_in_schema=False)
def service_worker_static():
    return FileResponse(str(SW_PATH), media_type="application/javascript")


# ============================================================
# TEMPLATES
# ============================================================

templates = Jinja2Templates(directory="templates")

# ============================================================
# CACHE HEADERS
# ============================================================

@app.middleware("http")
async def add_cache_headers(request: Request, call_next):
    resp = await call_next(request)
    path = request.url.path or ""

    # HTML sempre sem cache
    if path == "/" or path.startswith("/catalogo"):
        resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        resp.headers["Pragma"] = "no-cache"
        resp.headers["Expires"] = "0"
        return resp

    # Static
    if path.startswith("/static/") or path == "/sw.js":
        if path.endswith((".css", ".js")):
            resp.headers["Cache-Control"] = "public, max-age=604800"
        elif path.endswith((".png", ".jpg", ".jpeg", ".webp", ".svg", ".gif", ".mp4")):
            resp.headers["Cache-Control"] = "public, max-age=2592000"
        else:
            resp.headers["Cache-Control"] = "public, max-age=86400"
        return resp

    return resp


# ============================================================
# DB HELPERS
# ============================================================

def get_conn() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


# ============================================================
# STARTUP (RENDER SAFE)
# ============================================================

@app.on_event("startup")
def on_startup():
    with get_conn() as con:

        # SONGS
        con.execute("""
        CREATE TABLE IF NOT EXISTS songs (
            code INTEGER PRIMARY KEY,
            title TEXT,
            singer TEXT,
            snippet TEXT,
            package TEXT,
            type TEXT,
            duplicated INTEGER DEFAULT 0,
            title_norm TEXT,
            singer_norm TEXT,
            snippet_norm TEXT
        )
        """)

        # FAVORITES
        con.execute("""
        CREATE TABLE IF NOT EXISTS favorites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            code INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, code)
        )
        """)

        # INDEXES
        con.execute("CREATE INDEX IF NOT EXISTS idx_favorites_user ON favorites(user_id, code)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_favorites_code ON favorites(code)")

        con.commit()


# ============================================================
# PAGES
# ============================================================

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(
        "home.html",
        {"request": request, "ASSET_V": ASSET_V}
    )


@app.get("/catalogo", response_class=HTMLResponse)
async def catalogo(request: Request):
    return templates.TemplateResponse(
        "catalogo.html",
        {"request": request, "ASSET_V": ASSET_V}
    )


# ============================================================
# HELPERS
# ============================================================

ALLOWED_TIPOS = {"NAC", "INT", "GOSPEL"}
ALLOWED_PLANOS = {"PLUS", "BASICO"}


def normalize_tipo(tipo: Optional[str]) -> Optional[str]:
    if not tipo:
        return None
    t = tipo.strip().upper()
    return t if t in ALLOWED_TIPOS else None


def normalize_plano(plano: Optional[str]) -> Optional[str]:
    if not plano:
        return None
    p = plano.strip().upper()
    return p if p in ALLOWED_PLANOS else None


def availability_from_package(pkg: str) -> str:
    pkg = (pkg or "").strip().upper()
    if pkg == "PLUS":
        return "PLUS"
    if pkg == "BASICO":
        return "BÁSICO"
    return "INDISPONÍVEL"


# ============================================================
# SEARCH API
# ============================================================

@app.get("/api/search")
def search(
    q: str = Query(""),
    tipo: Optional[str] = Query(None),
    plano: Optional[str] = Query(None),
    limit: int = Query(200, ge=1, le=1000),
):
    q = q.strip()
    tipo = normalize_tipo(tipo)
    plano = normalize_plano(plano)

    where = []
    params: List[Any] = []

    if tipo:
        where.append("type = ?")
        params.append(tipo)

    if plano == "BASICO":
        where.append("package = ?")
        params.append("BASICO")

    if q:
        ql = q.lower()
        where.append("""
        (code = ? OR title LIKE ? OR singer LIKE ? OR snippet LIKE ?
         OR title_norm LIKE ? OR singer_norm LIKE ? OR snippet_norm LIKE ?)
        """)
        params.extend([q if q.isdigit() else -1,
                       f"%{q}%", f"%{q}%", f"%{q}%",
                       f"%{ql}%", f"%{ql}%", f"%{ql}%"])

    where_sql = " AND ".join(where)
    if where_sql:
        where_sql = "WHERE " + where_sql

    sql = f"""
    SELECT code, title, singer, snippet, package, type, duplicated
    FROM songs
    {where_sql}
    ORDER BY singer COLLATE NOCASE, title COLLATE NOCASE, code
    LIMIT ?
    """

    params.append(limit)

    with get_conn() as con:
        rows = con.execute(sql, params).fetchall()

    items = []
    for r in rows:
        d = dict(r)
        d["availability"] = availability_from_package(d.get("package", ""))
        items.append(d)

    return {"count": len(items), "items": items}


# ============================================================
# FAVORITES
# ============================================================

class FavRegisterIn(BaseModel):
    user_id: int
    code: int


@app.get("/api/fav/user")
def fav_user(user_id: int, limit: int = 500):
    sql = """
    SELECT s.code, s.title, s.singer, s.snippet, s.package, s.type, s.duplicated
    FROM favorites f
    JOIN songs s ON s.code = f.code
    WHERE f.user_id = ?
    ORDER BY s.singer, s.title, s.code
    LIMIT ?
    """

    with get_conn() as con:
        rows = con.execute(sql, (user_id, limit)).fetchall()

    items = []
    for r in rows:
        d = dict(r)
        d["availability"] = availability_from_package(d.get("package", ""))
        items.append(d)

    return {"count": len(items), "items": items}


@app.post("/api/fav/register")
def fav_register(payload: FavRegisterIn):
    with get_conn() as con:
        con.execute(
            "INSERT OR IGNORE INTO favorites (user_id, code) VALUES (?, ?)",
            (payload.user_id, payload.code)
        )
        con.commit()
    return {"ok": True}


@app.post("/api/fav/remove")
def fav_remove(payload: FavRegisterIn):
    with get_conn() as con:
        con.execute(
            "DELETE FROM favorites WHERE user_id = ? AND code = ?",
            (payload.user_id, payload.code)
        )
        con.commit()
    return {"ok": True}


# ============================================================
# TOP FAVORITES
# ============================================================

_TOP_CACHE = {"ts": 0.0, "data": None}
_TOP_TTL = 30


@app.get("/api/top-favoritos")
def top_favoritos():
    now = time.time()
    if _TOP_CACHE["data"] and now - _TOP_CACHE["ts"] < _TOP_TTL:
        return _TOP_CACHE["data"]

    sql = """
    SELECT s.code, s.title, s.singer, s.package, COUNT(f.code) as total
    FROM favorites f
    JOIN songs s ON s.code = f.code
    GROUP BY f.code
    ORDER BY total DESC
    LIMIT 50
    """

    with get_conn() as con:
        rows = con.execute(sql).fetchall()

    data = [dict(r) for r in rows]
    _TOP_CACHE["data"] = data
    _TOP_CACHE["ts"] = now
    return data
