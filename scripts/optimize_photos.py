#!/usr/bin/env python3
"""Prepare les photos d'un site avant de les ajouter au depot.

Redimensionne, compresse, retire les metadonnees EXIF (dont la position GPS
de l'appareil) et redresse l'image selon son orientation d'origine.

Usage :
    python3 scripts/optimize_photos.py I441310030 ~/Photos/pornic/*.jpg

Les fichiers optimises sont ecrits dans data/photos/<id>/ :
    01-nom.jpg        (large, max 1600 px)
    01-nom.thumb.jpg  (vignette, max 480 px)
"""
import os
import re
import sys
import unicodedata

try:
    from PIL import Image, ImageOps
except ImportError:
    sys.exit("Pillow est requis :  pip install Pillow")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PHOTOS = os.path.join(ROOT, "data", "photos")

LARGE, THUMB = 1600, 480
Q_LARGE, Q_THUMB = 76, 70
MAX_KO = 400


def slug(s):
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn").lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s or "photo"


def save(img, path, box, quality):
    out = ImageOps.exif_transpose(img)          # redresse selon l'EXIF
    out.thumbnail((box, box), Image.LANCZOS)
    if out.mode not in ("RGB", "L"):
        out = out.convert("RGB")
    # on repart des pixels bruts : plus aucune metadonnee ne survit
    clean = Image.frombytes(out.mode, out.size, out.tobytes())
    clean.save(path, "JPEG", quality=quality, optimize=True, progressive=True)
    return os.path.getsize(path) / 1024


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    site_id, sources = sys.argv[1], sys.argv[2:]

    dest = os.path.join(PHOTOS, site_id)
    os.makedirs(dest, exist_ok=True)

    start = len([f for f in os.listdir(dest) if f.endswith(".jpg") and ".thumb." not in f])
    for i, src in enumerate(sources, start=start + 1):
        base = f"{i:02d}-{slug(os.path.splitext(os.path.basename(src))[0])}"
        with Image.open(src) as img:
            w, h = img.size
            big = save(img, os.path.join(dest, base + ".jpg"), LARGE, Q_LARGE)
            small = save(img, os.path.join(dest, base + ".thumb.jpg"), THUMB, Q_THUMB)
        flag = "  ⚠ au-dessus de %d Ko" % MAX_KO if big > MAX_KO else ""
        print(f"{base}.jpg  ({w}x{h} → {big:.0f} Ko + {small:.0f} Ko vignette){flag}")

    print(f"\nAjoutez-les à data/overrides/{site_id}.json :")
    print('  "photos": [')
    for f in sorted(f for f in os.listdir(dest) if f.endswith(".jpg") and ".thumb." not in f):
        print(f'    {{"fichier": "{f}", "legende": "à compléter"}},')
    print("  ]")


if __name__ == "__main__":
    main()
