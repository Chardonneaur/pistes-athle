#!/usr/bin/env python3
"""Telecharge l'orthophoto IGN d'un site, pour lire son implantation.

    python3 scripts/ortho.py I440180009 [I441310030 ...]
    python3 scripts/ortho.py 47.15415,-1.68232        # coordonnees libres

Ecrit un JPEG par site dans le repertoire courant. Le cadrage est celui de la
vue aerienne de l'application (assets/app.js), a la resolution native de la
BD ORTHO(R) : 20 cm/pixel.

Ce que l'image permet d'en deduire, et ce qu'elle ne permet pas :
voir docs/lecture-orthophoto.md. En resume, on n'en tire jamais des `agres`,
seulement des `agres_probables`.

(C) IGN - BD ORTHO(R), Licence Ouverte 2.0.
"""
import json
import math
import os
import sys
import urllib.request

WMS = "https://data.geopf.fr/wms-r/wms"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TAILLE = 2000  # px de cote


def carte(lat, lon, champ, taille):
    """URL WMS d'un carre de `champ` metres centre sur le site."""
    dlat = champ / 2 / 111132
    dlon = champ / 2 / (111320 * math.cos(math.radians(lat)))
    bbox = ",".join(str(v) for v in (lat - dlat, lon - dlon, lat + dlat, lon + dlon))
    return (f"{WMS}?SERVICE=WMS&VERSION=1.3.0&REQUEST=GetMap"
            "&LAYERS=HR.ORTHOIMAGERY.ORTHOPHOTOS&STYLES=&CRS=EPSG:4326"
            f"&BBOX={bbox}&WIDTH={taille}&HEIGHT={taille}&FORMAT=image/jpeg")


def sites():
    with open(os.path.join(ROOT, "data", "tracks.json"), encoding="utf-8") as f:
        return {t["i"]: t for t in json.load(f)["tracks"]}


def main(args):
    if not args:
        sys.exit(__doc__)
    par_id = None
    for arg in args:
        if "," in arg:
            lat, lon = (float(v) for v in arg.split(","))
            nom, champ = arg.replace(",", "_"), 400
        else:
            par_id = par_id or sites()
            t = par_id.get(arg)
            if t is None:
                print(f"{arg} : identifiant inconnu de data/tracks.json", file=sys.stderr)
                continue
            # un anneau de 400 m tient dans 360 m de champ ; on prend un peu
            # de marge, les aires de lancer debordent souvent de l'anneau.
            nom, lat, lon = arg, t["y"], t["x"]
            champ = 400 if (t.get("lp") or 0) >= 400 else 260
        fichier = f"{nom}.jpg"
        urllib.request.urlretrieve(carte(lat, lon, champ, TAILLE), fichier)
        print(f"{fichier}  {champ} m de cote, {champ / TAILLE * 100:.0f} cm/px")


if __name__ == "__main__":
    main(sys.argv[1:])
