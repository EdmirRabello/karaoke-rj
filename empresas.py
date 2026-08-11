import json
from pathlib import Path

from fastapi import Request

from db import fetchall
from temas import obter_tema

BASE_EMPRESAS_URL = "/static/img/logos/empresas"
BASE_EMPRESAS_PATH = Path("static/img/logos/empresas")

DOMINIOS_OFICIAIS = {
    "www.karaokerj.com.br",
    "karaokerj.com.br",
    "localhost",
    "127.0.0.1",
}

MODULOS_PADRAO = {
    "portal": True,
    "redes": True,
    "whatsapp": True,
    "pdf": False,
    "catalogo": True,
    "qr": True,
    "vitrine": False,
    "galeria": False,
    "videos": False,
    "promocoes": False,
    "agenda": False,
    "reservas": False,
    "loja": False,
}

PORTAL_PADRAO = {
    "headline": "Bem-vindo ao KRJ Connect",
    "subtitulo": "Portal digital da empresa.",
    "botao_whatsapp": "Falar no WhatsApp",
    "botao_catalogo": "Entrar no catálogo",
    "botao_pdf": "Ver PDF",
    "pdf_url": "",
}


def ler_json(valor, padrao=None):
    try:
        if isinstance(valor, dict):
            return valor
        return json.loads(valor or "{}")
    except Exception:
        return padrao or {}


def normalizar_slug(slug: str | None) -> str:
    slug = (slug or "karaokerj").strip().lower()
    slug = "".join(ch for ch in slug if ch.isalnum() or ch in "-_")
    return slug or "karaokerj"


def arquivo_empresa(slug: str, nome_arquivo: str):
    slug = normalizar_slug(slug)
    caminho = BASE_EMPRESAS_PATH / slug / nome_arquivo
    if caminho.exists():
        return f"{BASE_EMPRESAS_URL}/{slug}/{nome_arquivo}"
    return None


def arquivos_empresa(slug: str) -> dict:
    slug = normalizar_slug(slug)
    return {
        "logo": arquivo_empresa(slug, "logo.png"),
        "favicon": arquivo_empresa(slug, "favicon.png"),
        "social": arquivo_empresa(slug, "social.png"),
        "landing": arquivo_empresa(slug, "landing.png"),
        "qr": arquivo_empresa(slug, "qr.png"),
    }


def mesclar_modulos(valor) -> dict:
    modulos = dict(MODULOS_PADRAO)
    modulos.update(ler_json(valor, {}))
    return modulos


def mesclar_portal(valor) -> dict:
    portal = dict(PORTAL_PADRAO)
    portal.update(ler_json(valor, {}))
    return portal


def montar_empresa(row: dict) -> dict:
    slug = normalizar_slug(row.get("slug") or "karaokerj")

    redes = ler_json(row.get("redes"), {})
    config = ler_json(row.get("config"), {})
    modulos = mesclar_modulos(row.get("modulos"))
    portal = mesclar_portal(row.get("portal"))
    arquivos = arquivos_empresa(slug)
    tema_id = (row.get("tema") or "krj").strip().lower()
    tema = obter_tema(tema_id)

    empresa = {
        "id": row.get("id"),
        "dominio": row.get("dominio", ""),
        "nome": row.get("nome") or "Karaokê RJ",
        "slug": slug,
        "tema_id": tema_id,
        "tema": tema,
        "perfil": (row.get("perfil") or "catalogo").strip().lower(),
        "catalogo_nivel": (row.get("catalogo_nivel") or "PLUS").strip().upper(),
        "catalogo_release": int(row.get("catalogo_release") or 202606),
        "modulos": modulos,
        "portal": portal,
        **arquivos,
        "titulo_popup": row.get("titulo_popup") or row.get("nome") or "Karaokê RJ",
        "mensagem_popup": row.get("mensagem_popup") or "",
        "redes": {
            "instagram": redes.get("instagram", ""),
            "facebook": redes.get("facebook", ""),
            "youtube": redes.get("youtube", ""),
            "site": redes.get("site", ""),
            "whatsapp": redes.get("whatsapp", ""),
            "tiktok": redes.get("tiktok", ""),
        },
        "config": {
            "popup": config.get("popup", True),
            "mostrar_logo": config.get("mostrar_logo", True),
        },
        "ativo": int(row.get("ativo", 1) or 1),
    }

    empresa["url_portal"] = f"/{slug}"
    empresa["url_catalogo"] = f"/{slug}/catalogo" if modulos.get("catalogo") else ""
    return empresa


EMPRESA_PADRAO = {
    "id": 0,
    "dominio": "www.karaokerj.com.br",
    "nome": "Karaokê RJ",
    "slug": "karaokerj",
    "tema_id": "krj",
    "tema": obter_tema("krj"),
    "perfil": "catalogo",
    "catalogo_nivel": "PLUS",
    "catalogo_release": 202606,
    "modulos": dict(MODULOS_PADRAO),
    "portal": {
        **PORTAL_PADRAO,
        "headline": "Karaokê RJ",
        "subtitulo": "O maior catálogo de karaokê do Brasil.",
        "botao_catalogo": "Entrar no catálogo",
    },
    **arquivos_empresa("karaokerj"),
    "titulo_popup": "Karaokê RJ",
    "mensagem_popup": "Bem-vindo ao maior catálogo de karaokê do Brasil.",
    "redes": {
        "instagram": "https://instagram.com/karaokerj",
        "facebook": "https://facebook.com/karaokerj",
        "youtube": "https://youtube.com/@karaokerj4569",
        "site": "https://www.karaokerj.com.br",
        "whatsapp": "5521996504516",
        "tiktok": "",
    },
    "config": {"popup": True, "mostrar_logo": True},
    "ativo": 1,
    "url_portal": "/karaokerj",
    "url_catalogo": "/karaokerj/catalogo",
}


def obter_empresa(request: Request, slug: str | None = None) -> dict:
    host = request.headers.get("host", "")
    host = host.split(":")[0].lower().strip()

    # Prioridade 1: slug explícito na rota ou query (?empresa=vivioke)
    slug_param = normalizar_slug(slug or request.query_params.get("empresa") or "") if (slug or request.query_params.get("empresa")) else ""

    try:
        rows = []

        if slug_param:
            rows = fetchall(
                """
                SELECT *
                FROM empresas
                WHERE LOWER(slug) = ?
                  AND ativo = 1
                LIMIT 1
                """,
                [slug_param],
            )

        # Prioridade 2: domínio próprio/host
        if not rows:
            rows = fetchall(
                """
                SELECT *
                FROM empresas
                WHERE LOWER(dominio) = ?
                  AND ativo = 1
                LIMIT 1
                """,
                [host],
            )

        if rows:
            empresa = montar_empresa(rows[0])
        else:
            empresa = dict(EMPRESA_PADRAO)

    except Exception as e:
        print("WARN obter_empresa:", e)
        empresa = dict(EMPRESA_PADRAO)

    empresa["host"] = host
    empresa["dominio_oficial"] = host in DOMINIOS_OFICIAIS
    return empresa


def empresa_tem_catalogo(empresa: dict) -> bool:
    return bool((empresa or {}).get("modulos", {}).get("catalogo"))
