from __future__ import annotations

from typing import Optional, List, Any

from fastapi import FastAPI, Query, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.responses import FileResponse
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from db import init_db, get_conn

app = FastAPI(title="Karaokê RJ • Cantus")

# Compressão (melhora muito no mobile)
app.add_middleware(GZipMiddleware, minimum_size=800)

# Static assets (/static/...)
app.mount("/static", StaticFiles(directory="static"), name="static")

# ✅ Service Worker NO ROOT, mas arquivo fica em static/js/sw.js (como você quer)
@app.get("/sw.js", include_in_schema=False)
def service_worker() -> Response:
    return FileResponse("static/js/sw.js", media_type="application/javascript")

# ✅ (Opcional) também permite acessar direto no caminho onde ele está
@app.get("/static/js/sw.js", include_in_schema=False)
def service_worker_static() -> Response:
    return FileResponse("static/js/sw.js", media_type="application/javascript")

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
            resp.headers["Cache-Control"] = "public, max-age=86400"    # 1 dia
        return resp

    return resp


ALLOWED_TIPOS = {"NAC", "INT", "GOSPEL"}
ALLOWED_PLANOS = {"PLUS", "BASICO"}


@app.on_event("startup")
def on_startup():
    init_db()


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
        return "SOMENTE PLUS"
    if pkg == "BASICO":
        return "PLUS e BÁSICO"
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

    if plano:
        where.append("package = ?")
        params.append(plano)

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

    if plano:
        where.append("package = ?")
        params.append(plano)

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


# ✅ Silencia o log do Chrome DevTools (opcional)
@app.get("/.well-known/appspecific/com.chrome.devtools.json", include_in_schema=False)
def chrome_devtools_stub():
    return {}
