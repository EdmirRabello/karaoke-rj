"""
optimize_images.py — otimização opcional de imagens (sem mudar a estrutura de pastas)

- Converte PNG/JPG para WEBP (mantém o original e cria um .webp ao lado)
- Ideal para reduzir peso e melhorar carregamento no mobile

Uso:
  python optimize_images.py

Requer: Pillow (já incluso na maioria dos ambientes Python; se faltar: pip install pillow)
"""

from __future__ import annotations

from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parent
TARGET_DIRS = [
    ROOT / "static" / "img",
    ROOT / "static" / "media",
]

# Qualidade WEBP (0-100). 82 é um bom equilíbrio.
WEBP_QUALITY = 82

# Extensões aceitas
EXTS = {".png", ".jpg", ".jpeg"}


def convert_one(path: Path) -> bool:
    out = path.with_suffix(".webp")
    if out.exists():
        return False

    try:
        with Image.open(path) as im:
            im = im.convert("RGBA") if im.mode in ("P", "LA") else im.convert("RGB") if im.mode not in ("RGB", "RGBA") else im
            im.save(out, "WEBP", quality=WEBP_QUALITY, method=6)
        return True
    except Exception as e:
        print(f"[ERRO] {path}: {e}")
        return False


def main() -> None:
    created = 0
    scanned = 0

    for base in TARGET_DIRS:
        if not base.exists():
            continue

        for p in base.rglob("*"):
            if p.is_file() and p.suffix.lower() in EXTS:
                scanned += 1
                if convert_one(p):
                    created += 1

    print(f"OK — arquivos analisados: {scanned} | webp criados: {created}")


if __name__ == "__main__":
    main()
