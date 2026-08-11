# ============================================================
# KRJ Connect - Temas oficiais
# ============================================================
# Regra do projeto:
# - Não existe tema personalizado.
# - Cliente não escolhe cores soltas.
# - O Admin escolhe um dos temas oficiais.
# ============================================================

TEMAS = {
    "krj": {
        "id": "krj",
        "nome": "Karaokê RJ",
        "interno": True,
        "icone": "🎤",
        "descricao": "Tema exclusivo da Karaokê RJ.",
        "classe": "theme-krj",
        "cores": {
            "brand": "#7b2fff",
            "brand_2": "#b26dff",
            "brand_dark": "#140027",
            "accent": "#ffd54f",
            "bg": "#05060a",
            "surface": "#10121d",
            "surface_2": "#171a28",
            "text": "#f7f7fb",
            "muted": "#aab0c5",
        },
    },
    "party": {
        "id": "party",
        "nome": "Party",
        "interno": False,
        "icone": "🎉",
        "descricao": "Colorido para festas, brinquedos e eventos.",
        "classe": "theme-party",
        "cores": {
            "brand": "#ff3fb4",
            "brand_2": "#35c7ff",
            "brand_dark": "#44116d",
            "accent": "#ffe44c",
            "bg": "#fff7ff",
            "surface": "#ffffff",
            "surface_2": "#fff0fb",
            "text": "#1a1230",
            "muted": "#6e6380",
        },
    },
    "fun": {
        "id": "fun",
        "nome": "Fun",
        "interno": False,
        "icone": "🎈",
        "descricao": "Infantil, alegre e vibrante.",
        "classe": "theme-fun",
        "cores": {
            "brand": "#00b875",
            "brand_2": "#ff8a00",
            "brand_dark": "#073b2a",
            "accent": "#ffdd33",
            "bg": "#f5fff9",
            "surface": "#ffffff",
            "surface_2": "#eafff3",
            "text": "#092218",
            "muted": "#557064",
        },
    },
    "ocean": {
        "id": "ocean",
        "nome": "Ocean",
        "interno": False,
        "icone": "🌊",
        "descricao": "Corporativo, limpo e moderno.",
        "classe": "theme-ocean",
        "cores": {
            "brand": "#1b6dff",
            "brand_2": "#7cc8ff",
            "brand_dark": "#001b3d",
            "accent": "#ffd54f",
            "bg": "#f4f9ff",
            "surface": "#ffffff",
            "surface_2": "#eaf3ff",
            "text": "#071a33",
            "muted": "#5c6d82",
        },
    },
    "gold": {
        "id": "gold",
        "nome": "Gold",
        "interno": False,
        "icone": "👑",
        "descricao": "Premium, sofisticado e elegante.",
        "classe": "theme-gold",
        "cores": {
            "brand": "#d4a017",
            "brand_2": "#ffe08a",
            "brand_dark": "#15100a",
            "accent": "#fff2b8",
            "bg": "#090806",
            "surface": "#16130d",
            "surface_2": "#241e12",
            "text": "#fff9e8",
            "muted": "#d4c39c",
        },
    },
    "night": {
        "id": "night",
        "nome": "Night",
        "interno": False,
        "icone": "🌙",
        "descricao": "Noturno, neon e minimalista.",
        "classe": "theme-night",
        "cores": {
            "brand": "#8b5cf6",
            "brand_2": "#22d3ee",
            "brand_dark": "#050816",
            "accent": "#f43f5e",
            "bg": "#02030a",
            "surface": "#0b1020",
            "surface_2": "#111827",
            "text": "#f8fafc",
            "muted": "#94a3b8",
        },
    },
}


def obter_tema(tema_id: str | None) -> dict:
    tema_id = (tema_id or "krj").strip().lower()
    return TEMAS.get(tema_id, TEMAS["krj"])


def temas_publicos() -> list[dict]:
    return [t for t in TEMAS.values() if not t.get("interno")]
