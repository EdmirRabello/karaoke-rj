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
ALLOWED_TYPES = {"NAC", "INT", "GOSPEL"}  # ✅ agora inclui GOSPEL


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
    # - se vier vazio -> 0
    # - se vier "1" -> 1
    # - se vier texto não numérico -> 1 (porque marcou)
    dup_num = pd.to_numeric(df["duplicated"], errors="coerce")
    df["duplicated"] = dup_num.fillna(0).astype(int)
    df["duplicated"] = (df["duplicated"] != 0).astype(int)

    # normalizados p/ busca
    df["title_norm"] = df["title"].apply(norm)
    df["singer_norm"] = df["singer"].apply(norm)
    df["snippet_norm"] = df["snippet"].apply(norm)

    return df


def upsert(df: pd.DataFrame, replace: bool = True) -> int:
    init_db()
    with get_conn() as con:
        cur = con.cursor()

        if replace:
            cur.execute("DELETE FROM songs;")

        rows = []
        cols = [
            "code", "title", "singer", "snippet",
            "package", "type", "duplicated",
            "title_norm", "singer_norm", "snippet_norm"
        ]

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

        cur.executemany(
            """INSERT INTO songs
            (code,title,singer,snippet,package,type,duplicated,title_norm,singer_norm,snippet_norm)
            VALUES (?,?,?,?,?,?,?,?,?,?)""",
            rows
        )

        con.commit()
        return cur.rowcount


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("excel_path", help="Caminho do banco.xlsx")
    ap.add_argument("--no-replace", action="store_true", help="Não apagar antes de importar (apenas adiciona)")
    args = ap.parse_args()

    df = load_excel(args.excel_path)
    inserted = upsert(df, replace=not args.no_replace)
    print(f"Importação concluída. Linhas inseridas: {inserted}")


if __name__ == "__main__":
    main()

