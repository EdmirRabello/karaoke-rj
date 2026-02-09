from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Optional, List, Any

from fastapi import FastAPI, Query, Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from db import init_db, fetchall, fetchone_value, execute, DB_KIND, DB_PATH

app = FastAPI(title="Karaokê RJ • Cantus")

# ============================================================
# ✅ 1) VERSÃO DOS ASSETS (para o ?v=... do base.html)
# ============================================================
ASSET_V = os.getenv("ASSET_V") or str(int(time.time()))

# ============================================================
# Compressão (melhora muito no mobile)
# ============================================================
app.add_middleware(GZipMiddleware, minimum_size=800)

# ============================================================
# Static assets (/static/...)
# ============================================================
app.mount("/static", StaticFiles(directory="static"), name="static")

BASE_DIR = Path(__file__).resolve().parent
SW_PATH = BASE_DIR / "static" / "sw.js"

@app.get("/sw.js", include_in_schema=False)
def service_worker():
    return FileResponse(str(SW_PATH), media_type="application/javascript")

@app.get("/static/sw.js", include_in_schema=False)
def service_worker_static():
    return FileResponse(str(SW_PATH), media_type="application/javascript")

# ============================================================
# Templates (pages)
# ============================================================
templates = Jinja2Templates(directory="templates")

# ============================================================
# ✅ 2) CACHE HEADERS
#    + HTML sempre sem cache
# ============================================================
@app.middleware("http")
async def add_cache_headers(request: Request, call_next):
    resp = await call_next(request)
    path = request.url.path or ""

    # HTML sem cache
    if path == "/" or path.startswith("/catalogo"):
        resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        resp.headers["Pragma"] = "no-cache"
        resp.headers["Expires"] = "0"
        return resp

    # Static com cache
    if path.startswith("/static/") or path == "/sw.js":
        if path.endswith(".css") or path.endswith(".js"):
            resp.headers["Cache-Control"] = "public, max-age=604800"  # 7 dias
        elif any(path.endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".webp", ".svg", ".gif", ".mp4"]):
            resp.headers["Cache-Control"] = "public, max-age=2592000"  # 30 dias
        else:
            resp.headers["Cache-Control"] = "public, max-age=86400"  # 1 dia
        return resp

    return resp

# ============================================================
# CONFIGURAÇÕES
# ============================================================
ALLOWED_TIPOS = {"NAC", "INT", "GOSPEL"}
ALLOWED_PLANOS = {"PLUS", "BASICO"}

def availability_from_package(pkg: str) -> str:
    pkg = (pkg or "").strip().upper()
    if pkg == "PLUS":
        return "PLUS"
    if pkg == "BASICO":
        return "BÁSICO"
    return "INDISPONÍVEL"

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

# ============================================================
# ✅ STARTUP (Render-safe)
# - garante DB e tabelas (SQLite ou Postgres)
# - se songs estiver vazia, importa banco.xlsx
# ============================================================
@app.on_event("startup")
def on_startup():
    init_db()

    excel_path = os.getenv("EXCEL_PATH", "banco.xlsx")

    try:
        count = int(fetchone_value("SELECT COUNT(*) FROM songs", default=0) or 0)
    except Exception as e:
        print("WARN count songs:", e)
        count = 0

    if count == 0:
        print("songs=0 -> importando", excel_path)
        from import_excel import load_excel, upsert
        df = load_excel(excel_path)
        result = upsert(df, replace=False)  # incremental / UPSERT
        print("IMPORT OK:", result)
    else:
        print("songs OK:", count)

# ============================================================
# PÁGINAS
# ============================================================
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("home.html", {"request": request, "ASSET_V": ASSET_V})

@app.get("/catalogo", response_class=HTMLResponse)
async def catalogo(request: Request):
    return templates.TemplateResponse("catalogo.html", {"request": request, "ASSET_V": ASSET_V})

# ============================================================
# API SEARCH
# ============================================================
@app.get("/api/search")
def search(
    q: str = Query("", description="Busca por código, título, cantor ou trecho"),
    tipo: Optional[str] = Query(None, description="NAC / INT / GOSPEL"),
    plano: Optional[str] = Query(None, description="PLUS / BASICO"),
    limit: int = Query(200, ge=1, le=1000),
):
    q = (q or "").strip()
    tipo = normalize_tipo(tipo)
    plano = normalize_plano(plano)

    code_int = None
    if q.isdigit():
        try:
            code_int = int(q)
        except Exception:
            code_int = None

    where = []
    params: List[Any] = []

    if tipo:
        where.append("type = ?")
        params.append(tipo)

    if plano == "BASICO":
        where.append("package = ?")
        params.append("BASICO")

    if q:
        q_low = q.lower()
        if DB_KIND == "postgres":
            # Postgres: use ILIKE para colunas "originais" (case-insensitive)
            if code_int is not None:
                where.append(
                    "(code = ? OR title ILIKE ? OR singer ILIKE ? OR snippet ILIKE ? "
                    "OR title_norm LIKE ? OR singer_norm LIKE ? OR snippet_norm LIKE ?)"
                )
                params.extend([
                    code_int,
                    f"%{q}%", f"%{q}%", f"%{q}%",
                    f"%{q_low}%", f"%{q_low}%", f"%{q_low}%"
                ])
            else:
                where.append(
                    "(title ILIKE ? OR singer ILIKE ? OR snippet ILIKE ? "
                    "OR title_norm LIKE ? OR singer_norm LIKE ? OR snippet_norm LIKE ?)"
                )
                params.extend([
                    f"%{q}%", f"%{q}%", f"%{q}%",
                    f"%{q_low}%", f"%{q_low}%", f"%{q_low}%"
                ])
        else:
            # SQLite
            if code_int is not None:
                where.append(
                    "(code = ? OR title LIKE ? OR singer LIKE ? OR snippet LIKE ? "
                    "OR title_norm LIKE ? OR singer_norm LIKE ? OR snippet_norm LIKE ?)"
                )
                params.extend([
                    code_int,
                    f"%{q}%", f"%{q}%", f"%{q}%",
                    f"%{q_low}%", f"%{q_low}%", f"%{q_low}%"
                ])
            else:
                where.append(
                    "(title LIKE ? OR singer LIKE ? OR snippet LIKE ? "
                    "OR title_norm LIKE ? OR singer_norm LIKE ? OR snippet_norm LIKE ?)"
                )
                params.extend([
                    f"%{q}%", f"%{q}%", f"%{q}%",
                    f"%{q_low}%", f"%{q_low}%", f"%{q_low}%"
                ])

    where_sql = " AND ".join(where)
    if where_sql:
        where_sql = "WHERE " + where_sql

    order_sql = (
        "ORDER BY lower(singer) ASC, lower(title) ASC, code ASC"
        if DB_KIND == "postgres"
        else "ORDER BY singer COLLATE NOCASE ASC, title COLLATE NOCASE ASC, code ASC"
    )

    sql = f"""
    SELECT code, title, singer, snippet, package, type, duplicated
    FROM songs
    {where_sql}
    {order_sql}
    LIMIT ?
    """
    params.append(limit)

    rows = fetchall(sql, params)

    for d in rows:
        d["availability"] = availability_from_package(d.get("package", ""))

    return {"q": q, "tipo": tipo, "plano": plano, "count": len(rows), "items": rows}

# ============================================================
# AUX: buscar músicas por códigos (para offline/localStorage)
# ============================================================
class CodesIn(BaseModel):
    codes: List[int]

@app.post("/api/songs/by-codes")
def songs_by_codes(payload: CodesIn):
    codes = [int(c) for c in (payload.codes or []) if int(c) > 0]
    if not codes:
        return {"count": 0, "items": []}

    if DB_KIND == "postgres":
        sql = """
        SELECT code, title, singer, snippet, package, type, duplicated
        FROM songs
        WHERE code = ANY(?)
        """
        rows = fetchall(sql, [codes])
    else:
        qmarks = ",".join(["?"] * len(codes))
        sql = f"""
        SELECT code, title, singer, snippet, package, type, duplicated
        FROM songs
        WHERE code IN ({qmarks})
        """
        rows = fetchall(sql, codes)

    for d in rows:
        d["availability"] = availability_from_package(d.get("package", ""))

    return {"count": len(rows), "items": rows}

# ============================================================
# FAVORITOS POR USUÁRIO
# ============================================================
class FavRegisterIn(BaseModel):
    user_id: int
    code: int

class FavSyncIn(BaseModel):
    user_id: int
    codes: List[int]
    mode: str = "merge"   # "merge" ou "replace"

@app.get("/api/fav/user")
def fav_user(user_id: int = Query(...), limit: int = Query(500, ge=1, le=2000)):
    sql = f"""
      SELECT s.code, s.title, s.singer, s.snippet,
             s.package, s.type, s.duplicated
      FROM favorites f
      JOIN songs s ON s.code = f.code
      WHERE f.user_id = ?
      {("ORDER BY lower(s.singer) ASC, lower(s.title) ASC, s.code ASC" if DB_KIND=="postgres" else "ORDER BY s.singer COLLATE NOCASE ASC, s.title COLLATE NOCASE ASC, s.code ASC")}
      LIMIT ?
    """
    rows = fetchall(sql, [user_id, limit])

    for d in rows:
        d["availability"] = availability_from_package(d.get("package", ""))

    return {"count": len(rows), "items": rows}

@app.post("/api/fav/register")
def fav_register(payload: FavRegisterIn):
    if DB_KIND == "postgres":
        execute(
            "INSERT INTO favorites (user_id, code) VALUES (?, ?) ON CONFLICT DO NOTHING",
            [payload.user_id, payload.code],
        )
    else:
        execute(
            "INSERT OR IGNORE INTO favorites (user_id, code) VALUES (?, ?)",
            [payload.user_id, payload.code],
        )
    return {"ok": True}

@app.post("/api/fav/remove")
def fav_remove(payload: FavRegisterIn):
    execute(
        "DELETE FROM favorites WHERE user_id = ? AND code = ?",
        [payload.user_id, payload.code],
    )
    return {"ok": True}

@app.post("/api/fav/sync")
def fav_sync(payload: FavSyncIn):
    user_id = int(payload.user_id)
    codes = [int(c) for c in (payload.codes or []) if int(c) > 0]
    mode = (payload.mode or "merge").lower().strip()
    mode = mode if mode in {"merge", "replace"} else "merge"

    if mode == "replace":
        execute("DELETE FROM favorites WHERE user_id = ?", [user_id])

    if not codes:
        return {"ok": True, "mode": mode, "count": 0}

    if DB_KIND == "postgres":
        # insert missing
        for c in codes:
            execute(
                "INSERT INTO favorites (user_id, code) VALUES (?, ?) ON CONFLICT DO NOTHING",
                [user_id, c],
            )
    else:
        for c in codes:
            execute(
                "INSERT OR IGNORE INTO favorites (user_id, code) VALUES (?, ?)",
                [user_id, c],
            )

    return {"ok": True, "mode": mode, "count": len(codes)}

# ============================================================
# TOP FAVORITOS (GLOBAL)
# ============================================================
_TOP_CACHE = {"ts": 0.0, "data": None, "limit": None}
_TOP_TTL = 30

@app.get("/api/top-favoritos")
def top_favoritos(limit: int = Query(50, ge=1, le=200)):
    now = time.time()

    cached = _TOP_CACHE["data"]
    if (
        cached is not None
        and _TOP_CACHE["limit"] == limit
        and (now - _TOP_CACHE["ts"]) < _TOP_TTL
    ):
        return cached

    sql = f"""
      SELECT s.code, s.title, s.singer, s.package,
             COUNT(f.code) as total
      FROM favorites f
      JOIN songs s ON s.code = f.code
      GROUP BY s.code, s.title, s.singer, s.package
      ORDER BY total DESC
      LIMIT {int(limit)}
    """

    rows = fetchall(sql)

    _TOP_CACHE["ts"] = now
    _TOP_CACHE["data"] = rows
    _TOP_CACHE["limit"] = limit

    return rows

# ============================================================
# STUB CHROME DEVTOOLS
# ============================================================
@app.get("/.well-known/appspecific/com.chrome.devtools.json", include_in_schema=False)
def chrome_devtools_stub():
    return {}

# ============================================================
# DEBUG: ver qual banco está ativo
# ============================================================
@app.get("/api/_debug/db", include_in_schema=False)
def debug_db():
    info = {
        "db_kind": DB_KIND,
        "db_path_sqlite": str(DB_PATH),
        "has_database_url": bool(os.getenv("DATABASE_URL") or os.getenv("RENDER_DATABASE_URL") or os.getenv("POSTGRES_URL")),
    }
    try:
        info["songs_count"] = int(fetchone_value("SELECT COUNT(*) FROM songs", default=0) or 0)
        info["favorites_count"] = int(fetchone_value("SELECT COUNT(*) FROM favorites", default=0) or 0)
    except Exception as e:
        info["error"] = str(e)
    return info
