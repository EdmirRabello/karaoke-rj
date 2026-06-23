from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Optional, List, Any

from fastapi import FastAPI, Query, Request
from fastapi.responses import HTMLResponse, FileResponse, PlainTextResponse
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from datetime import datetime, timezone

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
# FILA ONLINE DO KARAOKÊ
# - Usada pelo KRJ_Monitor para receber pedidos do catálogo
# - Monitor espera resposta em texto puro: ID|CODIGO
# ============================================================
def init_fila_karaoke():
    """Cria a tabela da fila de pedidos, se ainda não existir."""
    if DB_KIND == "postgres":
        execute("""
        CREATE TABLE IF NOT EXISTS fila_karaoke (
            id SERIAL PRIMARY KEY,
            maquina TEXT NOT NULL,
            codigo INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'PENDENTE',
            criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            executado_em TIMESTAMP,
            erro TEXT
        )
        """)
        execute("""
        CREATE INDEX IF NOT EXISTS idx_fila_karaoke_maquina_status
        ON fila_karaoke (maquina, status, id)
        """)
    else:
        execute("""
        CREATE TABLE IF NOT EXISTS fila_karaoke (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            maquina TEXT NOT NULL,
            codigo INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'PENDENTE',
            criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            executado_em TIMESTAMP,
            erro TEXT
        )
        """)
        execute("""
        CREATE INDEX IF NOT EXISTS idx_fila_karaoke_maquina_status
        ON fila_karaoke (maquina, status, id)
        """)


def init_fila_atual_monitor():
    """Guarda a fila real lida pelo KRJ_Monitor em cada máquina."""
    if DB_KIND == "postgres":
        execute("""
        CREATE TABLE IF NOT EXISTS fila_atual_monitor (
            maquina TEXT PRIMARY KEY,
            fila TEXT NOT NULL DEFAULT '',
            atualizado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
    else:
        execute("""
        CREATE TABLE IF NOT EXISTS fila_atual_monitor (
            maquina TEXT PRIMARY KEY,
            fila TEXT NOT NULL DEFAULT '',
            atualizado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)


def normalizar_maquina(maquina: str) -> str:
    return (maquina or "").strip().upper()[:60]


def normalizar_codigo_5(codigo: int | str) -> int:
    try:
        c = int(str(codigo).strip())
    except Exception:
        return 0
    if c < 0 or c > 99999:
        return 0
    return c


# ============================================================
# ✅ STARTUP (Render-safe)
# - garante DB e tabelas (SQLite ou Postgres)
# - se songs estiver vazia, importa banco.xlsx
# ============================================================
@app.on_event("startup")
def on_startup():
    init_db()
    init_fila_karaoke()
    init_fila_atual_monitor()

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
    return templates.TemplateResponse(
        request=request,
        name="home.html",
        context={"ASSET_V": ASSET_V}
    )


@app.get("/catalogo", response_class=HTMLResponse)
async def catalogo(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="catalogo.html",
        context={"ASSET_V": ASSET_V}
    )


# ============================================================
# API SEARCH
# ============================================================
@app.get("/api/search")
def search(
        q: str = Query("", description="Busca por código, título, cantor ou trecho"),
        tipo: Optional[str] = Query(None, description="NAC / INT / GOSPEL"),
        plano: Optional[str] = Query(None, description="PLUS / BASICO"),
        letter: Optional[str] = Query(None, description="Filtra cantor por inicial (A-Z)"),
        limit: int = Query(60, ge=1, le=1000),
        offset: int = Query(0, ge=0, le=2_000_000),
):
    q = (q or "").strip()
    tipo = normalize_tipo(tipo)
    plano = normalize_plano(plano)
    letter = (letter or "").strip()[:1].upper() if letter else None
    if letter and not ("A" <= letter <= "Z"):
        letter = None

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

    if letter:
        # usa colunas normalizadas (sem acento / lower)
        where.append("singer_norm LIKE ?")
        params.append(f"{letter.lower()}%")

    if q:
        q_low = q.lower()
        if DB_KIND == "postgres":
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

    # total
    total_sql = f"SELECT COUNT(1) as c FROM songs {where_sql}"
    total_val = fetchone_value(total_sql, params)
    total = int(total_val or 0)

    # page
    sql = f"""
    SELECT code, title, singer, snippet, package, type, duplicated
    FROM songs
    {where_sql}
    {order_sql}
    LIMIT ?
    OFFSET ?
    """
    page_params = list(params) + [limit, offset]
    rows = fetchall(sql, page_params)

    for d in rows:
        d["availability"] = availability_from_package(d.get("package", ""))

    has_more = (offset + len(rows)) < total
    return {
        "q": q, "tipo": tipo, "plano": plano, "letter": letter,
        "count": len(rows), "total": total,
        "limit": limit, "offset": offset, "has_more": has_more,
        "items": rows
    }


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
    mode: str = "merge"  # "merge" ou "replace"


@app.get("/api/fav/user")
def fav_user(user_id: int = Query(...), limit: int = Query(500, ge=1, le=2000)):
    sql = f"""
      SELECT s.code, s.title, s.singer, s.snippet,
             s.package, s.type, s.duplicated
      FROM favorites f
      JOIN songs s ON s.code = f.code
      WHERE f.user_id = ?
      {("ORDER BY lower(s.singer) ASC, lower(s.title) ASC, s.code ASC" if DB_KIND == "postgres" else "ORDER BY s.singer COLLATE NOCASE ASC, s.title COLLATE NOCASE ASC, s.code ASC")}
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
# API FILA KARAOKÊ - MONITOR ONLINE
# ============================================================
@app.get("/api/monitor/proximo", response_class=PlainTextResponse)
def monitor_proximo(maquina: str = Query(..., description="Nome da máquina configurada no KRJ_Monitor")):
    """
    Usado pelo KRJ_Monitor.

    Respostas em texto puro:
    - Sem pedido: VAZIO
    - Com pedido: 123|01039
    """
    maquina_norm = normalizar_maquina(maquina)
    if not maquina_norm:
        return "VAZIO"

    sql = """
    SELECT id, codigo
    FROM fila_karaoke
    WHERE maquina = ?
      AND status = 'PENDENTE'
    ORDER BY id ASC
    LIMIT 1
    """
    rows = fetchall(sql, [maquina_norm])

    if not rows:
        return "VAZIO"

    item = rows[0]
    pedido_id = int(item.get("id") or 0)
    codigo = int(item.get("codigo") or 0)

    if pedido_id <= 0 or codigo <= 0 or codigo > 99999:
        return "VAZIO"

    return f"{pedido_id}|{codigo:05d}"


@app.get("/api/monitor/confirmar")
def monitor_confirmar(
        id: int = Query(..., description="ID do pedido retornado em /api/monitor/proximo"),
        maquina: str = Query("", description="Nome da máquina"),
        status: str = Query("executado", description="executado ou erro"),
        erro: str = Query("", description="Mensagem de erro opcional"),
):
    """Confirma o pedido como executado ou erro."""
    maquina_norm = normalizar_maquina(maquina)
    status_norm = (status or "executado").strip().upper()
    if status_norm not in {"EXECUTADO", "ERRO"}:
        status_norm = "EXECUTADO"

    if status_norm == "EXECUTADO":
        execute(
            """
            UPDATE fila_karaoke
            SET status = 'EXECUTADO',
                executado_em = CURRENT_TIMESTAMP,
                erro = NULL
            WHERE id = ?
              AND status = 'PENDENTE'
            """,
            [id],
        )
    else:
        execute(
            """
            UPDATE fila_karaoke
            SET status = 'ERRO',
                executado_em = CURRENT_TIMESTAMP,
                erro = ?
            WHERE id = ?
              AND status = 'PENDENTE'
            """,
            [(erro or "ERRO MONITOR")[:250], id],
        )

    return {"ok": True, "id": id, "maquina": maquina_norm, "status": status_norm}


def limpar_fila_codigos(fila: str) -> str:
    """Mantém somente códigos de 5 dígitos, preservando a ordem."""
    codigos = []
    for parte in (fila or "").split(","):
        p = parte.strip()
        if len(p) == 5 and p.isdigit():
            codigos.append(p)
    return ",".join(codigos)


@app.get("/api/monitor/fila_atual")
def monitor_fila_atual(
        maquina: str = Query(..., description="Nome da máquina"),
        fila: str = Query("", description="Códigos da lista de espera separados por vírgula. Ex: 18016,18017,18018"),
):
    """
    Usado pelo KRJ_Monitor para informar ao servidor a fila real do Radical-Okê.

    Exemplo:
    /api/monitor/fila_atual?maquina=SALAO&fila=18016,18017,18018
    """
    maquina_norm = normalizar_maquina(maquina)
    fila_limpa = limpar_fila_codigos(fila)

    if not maquina_norm:
        return {"ok": False, "erro": "MAQUINA_INVALIDA"}

    if DB_KIND == "postgres":
        execute(
            """
            INSERT INTO fila_atual_monitor (maquina, fila, atualizado_em)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT (maquina)
            DO UPDATE SET fila = EXCLUDED.fila,
                          atualizado_em = CURRENT_TIMESTAMP
            """,
            [maquina_norm, fila_limpa],
        )
    else:
        execute(
            """
            INSERT OR REPLACE INTO fila_atual_monitor (maquina, fila, atualizado_em)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            """,
            [maquina_norm, fila_limpa],
        )

    return {
        "ok": True,
        "maquina": maquina_norm,
        "fila": fila_limpa,
        "qtd": len([x for x in fila_limpa.split(",") if x.strip()]),
    }


@app.get("/api/monitor/ver_fila")
def monitor_ver_fila(maquina: str = Query(..., description="Nome da máquina")):
    """Mostra a última fila real enviada pelo monitor."""
    maquina_norm = normalizar_maquina(maquina)

    if not maquina_norm:
        return {"ok": False, "erro": "MAQUINA_INVALIDA"}

    rows = fetchall(
        """
        SELECT maquina, fila, atualizado_em
        FROM fila_atual_monitor
        WHERE maquina = ?
        """,
        [maquina_norm],
    )

    if not rows:
        return {"ok": True, "maquina": maquina_norm, "fila": "", "qtd": 0, "items": []}

    item = rows[0]
    fila = item.get("fila") or ""
    codigos = [x for x in fila.split(",") if x.strip()]

    return {
        "ok": True,
        "maquina": item.get("maquina"),
        "fila": fila,
        "qtd": len(codigos),
        "items": codigos,
        "atualizado_em": item.get("atualizado_em"),
    }


@app.get("/api/monitor/status")
def monitor_status(
        maquina: str = Query(..., description="Nome da máquina")
):
    maquina_norm = normalizar_maquina(maquina)

    if not maquina_norm:
        return {
            "ok": False,
            "online": False,
            "erro": "MAQUINA_INVALIDA"
        }

    rows = fetchall(
        """
        SELECT maquina, atualizado_em
        FROM fila_atual_monitor
        WHERE maquina = ?
        """,
        [maquina_norm],
    )

    if not rows:
        return {
            "ok": False,
            "online": False,
            "erro": "MAQUINA_NAO_ENCONTRADA"
        }

    item = rows[0]
    atualizado_em = item.get("atualizado_em")

    try:
        dt = datetime.fromisoformat(str(atualizado_em).replace("Z", "+00:00"))
        agora = datetime.utcnow()
        segundos = (agora - dt).total_seconds()
    except Exception:
        segundos = 999999

    online = segundos >= 0 and segundos <= 30

    return {
        "ok": True,
        "online": online,
        "maquina": item.get("maquina"),
        "atualizado_em": atualizado_em,
        "segundos_sem_atualizar": int(segundos)
    }


@app.get("/api/teste/enviar")
def teste_enviar(
        maquina: str = Query(..., description="Nome da máquina. Exemplo: SALAO"),
        codigo: int = Query(..., ge=0, le=99999, description="Código da música"),
):
    """
    Endpoint temporário para testar sem alterar a tela do catálogo.

    Exemplo:
    /api/teste/enviar?maquina=SALAO&codigo=1039
    """
    maquina_norm = normalizar_maquina(maquina)
    codigo_int = normalizar_codigo_5(codigo)

    if not maquina_norm:
        return {"ok": False, "erro": "MAQUINA_INVALIDA"}

    if codigo_int <= 0:
        return {"ok": False, "erro": "CODIGO_INVALIDO"}

    execute(
        """
        INSERT INTO fila_karaoke (maquina, codigo, status)
        VALUES (?, ?, 'PENDENTE')
        """,
        [maquina_norm, codigo_int],
    )

    return {
        "ok": True,
        "maquina": maquina_norm,
        "codigo": f"{codigo_int:05d}",
        "status": "PENDENTE",
    }


@app.get("/api/teste/fila")
def teste_fila(maquina: str = Query("", description="Opcional: filtrar por máquina"),
               limit: int = Query(50, ge=1, le=200)):
    """Mostra os últimos pedidos para conferência."""
    maquina_norm = normalizar_maquina(maquina)

    if maquina_norm:
        rows = fetchall(
            """
            SELECT id, maquina, codigo, status, criado_em, executado_em, erro
            FROM fila_karaoke
            WHERE maquina = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            [maquina_norm, limit],
        )
    else:
        rows = fetchall(
            """
            SELECT id, maquina, codigo, status, criado_em, executado_em, erro
            FROM fila_karaoke
            ORDER BY id DESC
            LIMIT ?
            """,
            [limit],
        )

    for r in rows:
        try:
            r["codigo"] = f"{int(r.get('codigo') or 0):05d}"
        except Exception:
            pass

    return {"count": len(rows), "items": rows}


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
        "has_database_url": bool(
            os.getenv("DATABASE_URL") or os.getenv("RENDER_DATABASE_URL") or os.getenv("POSTGRES_URL")),
    }
    try:
        info["songs_count"] = int(fetchone_value("SELECT COUNT(*) FROM songs", default=0) or 0)
        info["favorites_count"] = int(fetchone_value("SELECT COUNT(*) FROM favorites", default=0) or 0)
    except Exception as e:
        info["error"] = str(e)
    return info
