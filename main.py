from __future__ import annotations

from typing import Optional, List, Any

from fastapi import FastAPI, Query, Request
from fastapi.responses import HTMLResponse, Response, FileResponse
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from db import init_db, get_conn

app = FastAPI(title="Karaokê RJ • Cantus")

# Compressão (melhora muito no mobile)
app.add_middleware(GZipMiddleware, minimum_size=800)

# Static assets (/static/...)
app.mount("/static", StaticFiles(directory="static"), name="static")


from pathlib import Path
from fastapi.responses import FileResponse

BASE_DIR = Path(__file__).resolve().parent
SW_PATH = BASE_DIR / "static" / "sw.js"   # ✅ AGORA É static/sw.js

@app.get("/sw.js", include_in_schema=False)
def service_worker():
    return FileResponse(str(SW_PATH), media_type="application/javascript")

# (opcional) se você quiser também servir por /static/sw.js
@app.get("/static/sw.js", include_in_schema=False)
def service_worker_static():
    return FileResponse(str(SW_PATH), media_type="application/javascript")


# Templates (pages)
templates = Jinja2Templates(directory="templates")


# Cache headers (melhora performance em 4G/5G)
@app.middleware("http")
async def add_cache_headers(request: Request, call_next):
    resp = await call_next(request)
    path = request.url.path or ""

    # HTML: sempre revalidar
    if path == "/" or path.startswith("/catalogo"):
        resp.headers["Cache-Control"] = "no-cache"
        return resp

    # Static: cache control conservador (sem versionamento em URL)
    if path.startswith("/static/") or path == "/sw.js":
        if path.endswith(".css") or path.endswith(".js"):
            resp.headers["Cache-Control"] = "public, max-age=604800"  # 7 dias
        elif any(path.endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".webp", ".svg", ".gif", ".mp4"]):
            resp.headers["Cache-Control"] = "public, max-age=2592000"  # 30 dias
        else:
            resp.headers["Cache-Control"] = "public, max-age=86400"  # 1 dia
        return resp

    return resp


ALLOWED_TIPOS = {"NAC", "INT", "GOSPEL"}
ALLOWED_PLANOS = {"PLUS", "BASICO"}


@app.on_event("startup")
def on_startup():
    init_db()

    # ✅ Índices (se já existirem, não recria)
    with get_conn() as con:
        con.execute("CREATE INDEX IF NOT EXISTS idx_favorites_user ON favorites(user_id, code)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_favorites_code ON favorites(code)")
        con.commit()


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("home.html", {"request": request})


@app.get("/catalogo", response_class=HTMLResponse)
async def catalogo(request: Request):
    return templates.TemplateResponse("catalogo.html", {"request": request})


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

    # Plano:
    # - PLUS = Todos (não filtra)
    # - BASICO = filtra só basico
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
    SELECT
      code,
      title,
      singer,
      snippet,
      package,
      type,
      duplicated
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


@app.get("/api/favorites")
def favorites(
        codes: str = Query(..., description="lista separada por vírgula"),
        tipo: Optional[str] = Query(None, description="NAC / INT / GOSPEL"),
        plano: Optional[str] = Query(None, description="PLUS / BASICO"),
        limit: int = Query(500, ge=1, le=2000),
):
    tipo = normalize_tipo(tipo)
    plano = normalize_plano(plano)

    raw = [c.strip() for c in (codes or "").split(",") if c.strip()]
    code_list = [int(c) for c in raw if c.isdigit()]

    if not code_list:
        return {"count": 0, "items": []}

    placeholders = ",".join(["?"] * len(code_list))
    where = [f"code IN ({placeholders})"]
    params: List[Any] = list(code_list)

    if tipo:
        where.append("type = ?")
        params.append(tipo)

    # Plano:
    # - PLUS = Todos (não filtra)
    # - BASICO = filtra só basico
    if plano == "BASICO":
        where.append("package = ?")
        params.append("BASICO")

    where_sql = " AND ".join(where)
    if where_sql:
        where_sql = "WHERE " + where_sql

    sql = f"""
    SELECT
      code,
      title,
      singer,
      snippet,
      package,
      type,
      duplicated
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

    return {"count": len(items), "items": items}


# ✅ TOP 50 favoritos (global) — usa o MESMO padrão do projeto (get_conn)
import time

_TOP_CACHE = {"ts": 0.0, "data": None}
_TOP_TTL = 30  # segundos


@app.get("/api/top-favoritos")
def top_favoritos():
    now = time.time()
    cached = _TOP_CACHE["data"]
    if cached is not None and (now - _TOP_CACHE["ts"]) < _TOP_TTL:
        return cached

    sql = """
          SELECT s.code,
                 s.title,
                 s.singer,
                 s.package,
                 COUNT(f.code) as total
          FROM favorites f
                   JOIN songs s ON s.code = f.code
          GROUP BY f.code
          ORDER BY total DESC LIMIT 50 \
          """

    with get_conn() as con:
        rows = con.execute(sql).fetchall()

    data = [dict(r) for r in rows]
    _TOP_CACHE["ts"] = now
    _TOP_CACHE["data"] = data
    return data

from fastapi import Query

@app.get("/api/fav/user")
def fav_user(user_id: int = Query(...), limit: int = Query(500, ge=1, le=2000)):
    sql = """
      SELECT
        s.code,
        s.title,
        s.singer,
        s.snippet,
        s.package,
        s.type,
        s.duplicated
      FROM favorites f
      JOIN songs s ON s.code = f.code
      WHERE f.user_id = ?
      ORDER BY s.singer COLLATE NOCASE ASC, s.title COLLATE NOCASE ASC, s.code ASC
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

from pydantic import BaseModel


class FavRegisterIn(BaseModel):
    user_id: int
    code: int


@app.post("/api/fav/register")
def fav_register(payload: FavRegisterIn):
    user_id = int(payload.user_id)
    code = int(payload.code)

    with get_conn() as con:
        # evita duplicar o mesmo favorito do mesmo usuário
        con.execute(
            "INSERT OR IGNORE INTO favorites (user_id, code) VALUES (?, ?)",
            (user_id, code)
        )
        con.commit()

    return {"ok": True, "user_id": user_id, "code": code}


@app.post("/api/fav/remove")
def fav_remove(payload: FavRegisterIn):
    user_id = int(payload.user_id)
    code = int(payload.code)

    with get_conn() as con:
        con.execute(
            "DELETE FROM favorites WHERE user_id = ? AND code = ?",
            (user_id, code)
        )
        con.commit()

    return {"ok": True, "user_id": user_id, "code": code}


# ✅ Silencia o log do Chrome DevTools (opcional)
@app.get("/.well-known/appspecific/com.chrome.devtools.json", include_in_schema=False)
def chrome_devtools_stub():
    return {}
