# Catálogo Karaokê RJ

App web (PWA) com tema preto/dourado e busca por **música, cantor, trecho ou código**.  
Base inicial: Excel (`banco.xlsx`) → SQLite (`data/karaoke.db`).

## Rodar local
```bash
pip install -r requirements.txt
python import_excel.py banco.xlsx
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Abra:
- http://localhost:8000

> Dica (Windows): usar `python -m uvicorn ...` evita o erro “uvicorn não é reconhecido”.

## Produção (deploy)
### Comando
```bash
python -m uvicorn main:app --host 0.0.0.0 --port $PORT
```

### Variáveis de ambiente (recomendado)
Se você for usar login/admin, NÃO deixe segredo fixo no código. Configure:
- `JWT_SECRET` (obrigatório em produção)

Exemplos:
- PowerShell: `setx JWT_SECRET "SUA_SENHA_FORTE"`
- Linux/Mac: `export JWT_SECRET="SUA_SENHA_FORTE"`

## Coluna P (Pacote)
Use exatamente:
- BASICO
- PLUS
