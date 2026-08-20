#!/usr/bin/env python3
"""Dessine assets/og.png, la vignette de partage du site.

Aucune page n'avait d'image Open Graph : partagee sur un reseau ou reprise par
un agent, l'accueil n'affichait qu'un rectangle vide. L'image est generee ici
une fois pour toutes et versionnee, parce que la CI ne dispose pas de Pillow.

    python3 scripts/og_image.py
"""
import os

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SORTIE = os.path.join(ROOT, "assets", "og.png")

W, H = 1200, 630
ENCRE = "#0f172a"
ACCENT = "#fb923c"
BLANC = "#f8fafc"
GRIS = "#94a3b8"

GRAS = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
NORMAL = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


def piste(d, cx, cy, rx, ry):
    """La piste du logo : deux ellipses concentriques, la seconde effacee."""
    d.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], outline=ACCENT, width=13)
    d.ellipse([cx - rx * .63, cy - ry * .54, cx + rx * .63, cy + ry * .54],
              outline="#7c4a22", width=9)


def epingle(d, cx, cy, r):
    """La goutte du logo, pointe en bas, avec son oeil sombre."""
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=ACCENT)
    d.polygon([(cx - r * .74, cy + r * .62), (cx + r * .74, cy + r * .62),
               (cx, cy + r * 2.05)], fill=ACCENT)
    d.ellipse([cx - r * .38, cy - r * .38, cx + r * .38, cy + r * .38], fill=ENCRE)


def main():
    img = Image.new("RGB", (W, H), ENCRE)
    d = ImageDraw.Draw(img)

    # marque, a gauche
    piste(d, 232, 340, 150, 86)
    epingle(d, 232, 226, 46)

    x = 430
    d.text((x, 176), "Où s'entraîner ?", font=ImageFont.truetype(GRAS, 62), fill=BLANC)
    d.text((x, 254), "Where to train?", font=ImageFont.truetype(NORMAL, 40), fill=GRIS)
    d.text((x, 334), "7 100 pistes et équipements", font=ImageFont.truetype(NORMAL, 31), fill=BLANC)
    d.text((x, 374), "d'athlétisme en France", font=ImageFont.truetype(NORMAL, 31), fill=BLANC)

    d.line([(x, 438), (x + 90, 438)], fill=ACCENT, width=4)
    d.text((x, 458), "Revêtement · sautoirs · lancers · accès libre",
           font=ImageFont.truetype(NORMAL, 23), fill=GRIS)

    img.save(SORTIE, optimize=True)
    print(f"-> {SORTIE} ({os.path.getsize(SORTIE) // 1024} ko)")


if __name__ == "__main__":
    main()
