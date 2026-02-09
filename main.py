from __future__ import annotations

from typing import Optional, List, Any

from fastapi import FastAPI, Query, Request
from fastapi.responses import HTMLResponse, Response, FileResponse
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from db import init_db, get_conn

import os
import time

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

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
SW_PATH = BASE_DIR / "static" / "sw.js"   # static/sw.js


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
# ✅ 2) CACHE HEADERS (mantendo sua lógica original)
#    + HTML sempre sem cache para forçar versão nova
# ============================================================

@app.middleware("http")
async def add_cache_headers(request: Request, call_next):
    resp = await call_next(request)
    path = request.url.path or ""

    # --------------------------------------------------------
    # HTML: sempre revalidar (regra MAIS IMPORTANTE)
    # --------------------------------------------------------
    if path == "/" or path.startswith("/catalogo"):
        resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        resp.headers["Pragma"] = "no-cache"
        resp.headers["Expires"] = "0"
        return resp

    # --------------------------------------------------------
    # Static: sua regra original mantida
    # --------------------------------------------------------
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


@app.on_event("startup")
def on_startup():
    init_db()

    # Índices (se já existirem, não recria)
    with get_conn() as con:
        con.execute("CREATE INDEX IF NOT EXISTS idx_favorites_user ON favorites(user_id, code)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_favorites_code ON favorites(code)")
        con.commit()


# ============================================================
# PÁGINAS
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
# FUNÇÕES AUXILIARES
# ============================================================

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
        except:
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

    sql = f"""
    SELECT code, title, singer, snippet, package, type, duplicated
    FROM songs
    {where_sql}
    ORDER BY singer COLLATE NOCASE ASC, title COLLATE NOCASE ASC, code ASC
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

    return {"q": q, "tipo": tipo, "plano": plano, "count": len(items), "items": items}


# ============================================================
# FAVORITOS POR USUÁRIO
# ============================================================

from pydantic import BaseModel


class FavRegisterIn(BaseModel):
    user_id: int
    code: int


@app.get("/api/fav/user")
def fav_user(user_id: int = Query(...), limit: int = Query(500, ge=1, le=2000)):

    sql = """
      SELECT s.code, s.title, s.singer, s.snippet,
             s.package, s.type, s.duplicated
      FROM favorites f
      JOIN songs s ON s.code = f.code
      WHERE f.user_id = ?
      ORDER BY s.singer COLLATE NOCASE ASC,
               s.title COLLATE NOCASE ASC,
               s.code ASC
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
# TOP FAVORITOS (GLOBAL)
# ============================================================

_TOP_CACHE = {"ts": 0.0, "data": None}
_TOP_TTL = 30


@app.get("/api/top-favoritos")
def top_favoritos():
    now = time.time()
    cached = _TOP_CACHE["data"]

    if cached is not None and (now - _TOP_CACHE["ts"]) < _TOP_TTL:
        return cached

    sql = """
      SELECT s.code, s.title, s.singer, s.package,
             COUNT(f.code) as total
      FROM favorites f
      JOIN songs s ON s.code = f.code
      GROUP BY f.code
      ORDER BY total DESC LIMIT 50
    """

    with get_conn() as con:
        rows = con.execute(sql).fetchall()

    data = [dict(r) for r in rows]

    _TOP_CACHE["ts"] = now
    _TOP_CACHE["data"] = data

    return data


# ============================================================
# STUB CHROME DEVTOOLS
# ============================================================

@app.get("/.well-known/appspecific/com.chrome.devtools.json", include_in_schema=False)
def chrome_devtools_stub():
    return {}
