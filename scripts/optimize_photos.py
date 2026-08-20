#!/usr/bin/env python3
"""Prepare les photos d'un site avant de les ajouter au depot.

Redimensionne, compresse, retire les metadonnees EXIF (dont la position GPS
de l'appareil) et redresse l'image selon son orientation d'origine.

Usage :
    python3 scripts/optimize_photos.py I441310030 ~/Photos/pornic/*.jpg

Les fichiers optimises sont ecrits dans data/photos/<id>/ :
    01-sujet-nom-du-stade-commune.jpg        (large, max 1600 px)
    01-sujet-nom-du-stade-commune.thumb.jpg  (vignette, max 480 px)

Le nom du stade et la commune sont ajoutes automatiquement, lus dans
data/tracks.json. Un nom de fichier descriptif est l'un des rares signaux dont
Google Images dispose en plus de l'attribut alt : « 01-cage-de-lancer.jpg » ne
dit rien, « 01-cage-de-lancer-stade-jean-vincent-saint-brevin-les-pins.jpg »
situe la photo. Nommez donc la source d'apres son sujet, le reste suit.
"""
import json
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

TRACKS = os.path.join(ROOT, "data", "tracks.json")

LARGE, THUMB = 1600, 480
Q_LARGE, Q_THUMB = 76, 70
MAX_KO = 400


def slug(s):
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn").lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s or "photo"


def lieu(site_id):
    """« -stade-jean-vincent-saint-brevin-les-pins », a coller apres le sujet.

    Vide si tracks.json manque ou ne connait pas le site : mieux vaut un nom
    court qu'une construction qui echoue."""
    try:
        with open(TRACKS, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return ""
    cle = {v: k for k, v in data["keymap"].items()}
    for t in data["tracks"]:
        if t.get(cle["id"]) != site_id:
            continue
        morceaux = [t.get(cle["nom"]) or "", t.get(cle["ville"]) or ""]
        suffixe = slug("-".join(m for m in morceaux if m))
        return f"-{suffixe}" if suffixe else ""
    return ""


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
    suffixe = lieu(site_id)
    if not suffixe:
        print(f"{site_id} est inconnu de data/tracks.json : les fichiers seront "
              f"nommes sans le stade ni la commune.", file=sys.stderr)

    start = len([f for f in os.listdir(dest) if f.endswith(".jpg") and ".thumb." not in f])
    for i, src in enumerate(sources, start=start + 1):
        sujet = slug(os.path.splitext(os.path.basename(src))[0])
        base = f"{i:02d}-{sujet}{suffixe}"
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
