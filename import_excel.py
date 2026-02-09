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
ALLOWED_TYPES = {"NAC", "INT", "GOSPEL"}


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

    # ---------------------------------------------------------
    # CODE COMO INTEGER (compatível com db.py atual)
    # ---------------------------------------------------------
    df["code"] = pd.to_numeric(df["code"], errors="coerce")
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

    # duplicated: trata 0/1 corretamente
    dup_num = pd.to_numeric(df["duplicated"], errors="coerce")
    df["duplicated"] = dup_num.fillna(0).astype(int)
    df["duplicated"] = (df["duplicated"] != 0).astype(int)

    # normalizados p/ busca
    df["title_norm"] = df["title"].apply(norm)
    df["singer_norm"] = df["singer"].apply(norm)
    df["snippet_norm"] = df["snippet"].apply(norm)

    # ---------------------------------------------------------
    # DEDUPLICAÇÃO NO FORMATO QUE O BANCO ENXERGA
    # ---------------------------------------------------------
    dups = df.duplicated(subset=["code"], keep=False).sum()
    print(f"[import] duplicados por code após cast int: {dups}")
    if dups:
        print("[import] removendo duplicados (mantendo último registro por code)")
        df = df.drop_duplicates(subset=["code"], keep="last")

    return df


def upsert(df: pd.DataFrame, replace: bool = False) -> dict:
    """
    replace=False: UPSERT por code (insere novos e atualiza existentes)
    replace=True: apaga songs e recria tudo do zero (evite em produção)
    """
    from db import DB_KIND
    init_db()

    cols = [
        "code", "title", "singer", "snippet",
        "package", "type", "duplicated",
        "title_norm", "singer_norm", "snippet_norm"
    ]

    # Montagem do lote
    rows = []
    for r in df[cols].itertuples(index=False):
        rows.append((
            int(r.code),                     # INTEGER
            str(r.title),
            str(r.singer),
            str(r.snippet) if r.snippet else "",
            str(r.package),
            str(r.type),
            int(r.duplicated),
            str(r.title_norm),
            str(r.singer_norm),
            str(r.snippet_norm) if r.snippet_norm else ""
        ))

    total = len(rows)
    if total == 0:
        return {"total": 0, "novos": 0, "atualizados": 0}

    # ---------------------------------------------------------
    # POSTGRES
    # ---------------------------------------------------------
    if DB_KIND == "postgres":
        import psycopg2.extras  # type: ignore

        with get_conn() as con:
            with con.cursor() as cur:
                if replace:
                    cur.execute("DELETE FROM songs;")
                    con.commit()

                # contagem aproximada
                codes = [r[0] for r in rows]
                cur.execute("SELECT COUNT(*) FROM songs WHERE code = ANY(%s)", (codes,))
                exists = int(cur.fetchone()[0] or 0)
                novos = max(total - exists, 0)

                # UPSERT em lote
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

                return {
                    "total": total,
                    "novos": novos,
                    "atualizados": max(total - novos, 0)
                }

    # ---------------------------------------------------------
    # SQLITE (DEV)
    # ---------------------------------------------------------
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

        codes = [r[0] for r in rows]
        novos = 0
        batch = 900

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

        return {
            "total": total,
            "novos": novos,
            "atualizados": max(total - novos, 0)
        }


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
