# Karaokê RJ — Deploy (FastAPI)

## Rodar local
```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/Mac: source .venv/bin/activate
pip install -r requirements.txt
python -m uvicorn main:app --reload
```

Abra:
- Home: http://127.0.0.1:8000/
- Catálogo: http://127.0.0.1:8000/catalogo

## Deploy no Render (mais simples e gratuito)
Build Command:
- `pip install -r requirements.txt`

Start Command:
- `uvicorn main:app --host 0.0.0.0 --port $PORT`

Obs: Render (free) pode "hibernar" quando fica ocioso, então o primeiro acesso pode demorar um pouco.

## Pastas importantes
- `templates/` (HTML)
- `static/` (CSS/JS/Imagens)
- `data/karaoke.db` (SQLite)
