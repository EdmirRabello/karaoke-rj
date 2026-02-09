from __future__ import annotations

import argparse
import pandas as pd
from unidecode import unidecode

from db import init_db, get_conn

COLUMN_MAP = {
    "CÓD.": "code",
    "TÍTULO": "title",
    "CANTOR": "singer",
    "INÍCIO DA LETRA": "snippet",
    "P": "package",
    "TIPO": "type",
    "DUPLICADO": "duplicated",
}

ALLOWED_PACKAGES = {"BASICO", "PLUS"}
ALLOWED_TYPES = {"NAC", "INT", "GOSPEL"}  # inclui GOSPEL


def norm(s: str | None) -> str:
    if s is None:
        return ""
    s = str(s).strip()
    s = unidecode(s).lower()
    s = " ".join(s.split())
    return s


def load_excel(path: str) -> pd.DataFrame:
    df = pd.read_excel(path)
    df = df.rename(columns=COLUMN_MAP)

    required = ["code", "title", "singer", "snippet", "package", "type", "duplicated"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(
            f"Planilha está sem colunas esperadas: {missing}. "
            f"Colunas encontradas: {list(df.columns)}"
        )

    # code
    df["code"] = pd.to_numeric(df["code"], errors="coerce").astype("Int64")
    df = df.dropna(subset=["code", "title", "singer"])
    df["code"] = df["code"].astype(int)

    # textos básicos
    for col in ["title", "singer", "snippet", "type", "package"]:
        df[col] = df[col].fillna("").astype(str).str.strip()

    # package (P): PLUS/BASICO
    df["package"] = df["package"].str.upper()
    df.loc[~df["package"].isin(ALLOWED_PACKAGES), "package"] = "PLUS"

    # type (TIPO): NAC/INT/GOSPEL
    df["type"] = df["type"].str.upper()
    df.loc[~df["type"].isin(ALLOWED_TYPES), "type"] = ""

    # duplicated: tenta tratar 0/1 corretamente
    dup_num = pd.to_numeric(df["duplicated"], errors="coerce")
    df["duplicated"] = dup_num.fillna(0).astype(int)
    df["duplicated"] = (df["duplicated"] != 0).astype(int)

    # normalizados p/ busca
    df["title_norm"] = df["title"].apply(norm)
    df["singer_norm"] = df["singer"].apply(norm)
    df["snippet_norm"] = df["snippet"].apply(norm)

    return df


def upsert(df: pd.DataFrame, replace: bool = False) -> dict:
    """
    replace=False (padrão): UPSERT por code (insere novos e atualiza existentes)
    replace=True: apaga songs e recria tudo do zero (evite em produção)
    Retorna contagens reais: novos, atualizados, total.

    Compatível com:
      - SQLite (dev / Windows)
      - Postgres (produção no Render) quando DATABASE_URL estiver setado
    """
    from db import init_db, get_conn, DB_KIND
    init_db()

    cols = [
        "code", "title", "singer", "snippet",
        "package", "type", "duplicated",
        "title_norm", "singer_norm", "snippet_norm"
    ]

    rows = []
    for r in df[cols].itertuples(index=False):
        rows.append((
            int(r.code),
            str(r.title),
            str(r.singer),
            str(r.snippet) if r.snippet is not None else "",
            str(r.package),
            str(r.type),
            int(r.duplicated),
            str(r.title_norm),
            str(r.singer_norm),
            str(r.snippet_norm) if r.snippet_norm is not None else ""
        ))

    total = len(rows)
    if total == 0:
        return {"total": 0, "novos": 0, "atualizados": 0}

    if DB_KIND == "postgres":
        # Postgres: usa ON CONFLICT (code) DO UPDATE
        import psycopg2.extras  # type: ignore

        with get_conn() as con:
            with con.cursor() as cur:
                if replace:
                    cur.execute("DELETE FROM songs;")
                    con.commit()

                # contar existentes
                codes = [r[0] for r in rows]
                cur.execute("SELECT COUNT(*) FROM songs WHERE code = ANY(%s)", (codes,))
                exists = cur.fetchone()[0]
                novos = max(total - int(exists), 0)

                psycopg2.extras.execute_values(
                    cur,
                    """
                    INSERT INTO songs
                      (code,title,singer,snippet,package,type,duplicated,title_norm,singer_norm,snippet_norm)
                    VALUES %s
                    ON CONFLICT (code) DO UPDATE SET
                      title = EXCLUDED.title,
                      singer = EXCLUDED.singer,
                      snippet = EXCLUDED.snippet,
                      package = EXCLUDED.package,
                      type = EXCLUDED.type,
                      duplicated = EXCLUDED.duplicated,
                      title_norm = EXCLUDED.title_norm,
                      singer_norm = EXCLUDED.singer_norm,
                      snippet_norm = EXCLUDED.snippet_norm
                    """,
                    rows,
                    page_size=1000
                )
                con.commit()

                # atualizados = total - novos (aprox. suficiente para relatório)
                return {"total": total, "novos": novos, "atualizados": max(total - novos, 0)}

    # SQLite (original)
    with get_conn() as con:
        cur = con.cursor()

        if replace:
            cur.execute("DELETE FROM songs;")
            cur.executemany(
                """
                INSERT INTO songs
                  (code,title,singer,snippet,package,type,duplicated,title_norm,singer_norm,snippet_norm)
                VALUES (?,?,?,?,?,?,?,?,?,?)
                """,
                rows
            )
            con.commit()
            return {"total": total, "novos": total, "atualizados": 0}

        # contar novos vs existentes antes
        codes = [r[0] for r in rows]
        novos = 0
        batch = 900  # evita limite de parâmetros

        for i in range(0, len(codes), batch):
            chunk = codes[i:i + batch]
            q = ",".join(["?"] * len(chunk))
            exists = cur.execute(
                f"SELECT COUNT(*) FROM songs WHERE code IN ({q})",
                chunk
            ).fetchone()[0]
            novos += max(len(chunk) - int(exists), 0)

        cur.executemany(
            """
            INSERT INTO songs
              (code,title,singer,snippet,package,type,duplicated,title_norm,singer_norm,snippet_norm)
            VALUES (?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(code) DO UPDATE SET
              title=excluded.title,
              singer=excluded.singer,
              snippet=excluded.snippet,
              package=excluded.package,
              type=excluded.type,
              duplicated=excluded.duplicated,
              title_norm=excluded.title_norm,
              singer_norm=excluded.singer_norm,
              snippet_norm=excluded.snippet_norm
            """,
            rows
        )
        con.commit()

        return {"total": total, "novos": novos, "atualizados": max(total - novos, 0)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("excel", nargs="?", default="banco.xlsx")
    parser.add_argument("--replace", action="store_true")
    args = parser.parse_args()

    df = load_excel(args.excel)
    result = upsert(df, replace=args.replace)
    print(result)


if __name__ == "__main__":
    main()
