#!/usr/bin/env python3
"""Fabrique la file des endroits a regarder a l'orthophoto, pour un departement.

    python3 scripts/lieux_a_regarder.py 44
    python3 scripts/lieux_a_regarder.py 44 --planches .work/planches44
    python3 scripts/lieux_a_regarder.py 44 --deja .work/absentes-44.json --json .work/lieux-44.json

`pistes_absentes.py` cherche des pistes deja tracees dans OpenStreetMap. Ce
script-ci cherche des *endroits ou une piste pourrait etre*, sans qu'aucune base
ne la connaisse. Il n'affirme rien : il fabrique une file d'attente pour l'oeil.

Deux canaux, complementaires et tous deux absents de `pistes_absentes.py` :

- **la toponymie.** La plupart des complexes sportifs francais sont rue du
  Stade, rue ou avenue des Sports, ou portent un nom de sportif. C'est le seul
  canal qui attrape un complexe dont *rien* n'est tague : ni le ministere, ni
  `leisure=track`, ni la BD TOPO.
- **les city-stades de la BD TOPO(R)** de l'IGN. Trois pistes du Pays de Retz
  ont ete trouvees ainsi, autour d'un plateau multisports que l'IGN recense et
  que personne d'autre ne relie a l'athletisme. Attention : la categorie
  « Stade d'athletisme » de la BD TOPO ne trouve que les grands stades, deja
  tous connus — le gisement est « Petit terrain multi-sports ».

Ce qui sort de la est une liste de lieux, pas de pistes. La suite est dans
docs/trouver-les-pistes-manquantes.md : on regarde, on tranche, on va voir.

(c) OpenStreetMap contributors, ODbL - https://www.openstreetmap.org/copyright
(c) IGN - BD TOPO(R) et BD ORTHO(R), Licence Ouverte 2.0.
Base Adresse Nationale, Licence Ouverte 2.0.
"""
import argparse
import json
import math
import os
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request

from ortho import carte as url_ortho
from osm_longueurs import PAUSE, centre, charger_sites, code_osm, dist, points
from pistes_absentes import UA, adresse, overpass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WFS = "https://data.geopf.fr/wfs/ows"
GEOAPI = "https://geo.api.gouv.fr"

# Un « rue du Stade » designe le quartier, pas l'equipement : son centre peut
# tomber a 200 m du terrain. On est donc plus large qu'en cherchant un anneau.
RAYON_CONNU = 200.0

# Deux sources qui pointent le meme complexe, ou la rue et le gymnase qu'elle
# dessert : un seul lieu a regarder.
REGROUPEMENT = 200.0

# Champ de l'orthophoto : de quoi voir un anneau de 400 m et son alentour.
CHAMP = 260


REQUETE_OSM = """
[out:json][timeout:240];
area["ref:INSEE"="%s"]["admin_level"="6"]->.a;
(
  way["highway"]["name"~"stade|sports?",i](area.a);
  nwr["leisure"~"^(sports_centre|stadium)$"]["name"](area.a);
);
out center tags;
"""


def slug(s):
    s = unicodedata.normalize("NFD", s or "")
    s = "".join(c for c in s if unicodedata.category(c) != "Mn").lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-") or "lieu"


def toponymie(dep, cache=None):
    """Rues et equipements dont le nom annonce du sport."""
    if cache and os.path.exists(cache):
        with open(cache, encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = overpass(REQUETE_OSM % code_osm(dep), quoi=f"({dep}) ")
        if cache:
            os.makedirs(os.path.dirname(cache) or ".", exist_ok=True)
            with open(cache, "w", encoding="utf-8") as f:
                json.dump(data, f)
    out = []
    for e in data["elements"]:
        tags = e.get("tags", {})
        c = e.get("center") or {"lat": e.get("lat"), "lon": e.get("lon")}
        if c.get("lat") is None:
            g = points(e.get("geometry"))
            if not g:
                continue
            c = dict(zip(("lat", "lon"), centre(g)))
        quoi = "equipement nomme" if tags.get("leisure") else "voie"
        out.append({"source": f"OSM ({quoi})", "nom": tags.get("name"),
                    "lat": c["lat"], "lon": c["lon"],
                    "osm": f"{e['type']}/{e['id']}"})
    return out


def emprise_departement(dep, timeout=60):
    """Boite englobante d'un departement, d'apres les centres de ses communes."""
    url = f"{GEOAPI}/departements/{code_osm(dep)}/communes?fields=centre&format=json"
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
        communes = json.load(r)
    lats = [c["centre"]["coordinates"][1] for c in communes]
    lons = [c["centre"]["coordinates"][0] for c in communes]
    # les centres ne sont pas les bords : on elargit d'un rayon de commune
    return (min(lons) - .12, min(lats) - .10, max(lons) + .12, max(lats) + .10)


def citystades(dep, cache=None, timeout=240):
    """Petits terrains multi-sports de la BD TOPO(R).

    On interroge par boite englobante du departement, donc large : le tri par
    commune coute une requete par objet et ne sert a rien tant qu'on n'a pas
    retire ce qui est deja connu. On le fait apres."""
    if cache and os.path.exists(cache):
        with open(cache, encoding="utf-8") as f:
            feats = json.load(f)
    else:
        bbox = emprise_departement(dep)
        feats, start = [], 0
        while True:
            q = {"SERVICE": "WFS", "VERSION": "2.0.0", "REQUEST": "GetFeature",
                 "TYPENAMES": "BDTOPO_V3:terrain_de_sport",
                 "OUTPUTFORMAT": "application/json",
                 "COUNT": "1000", "STARTINDEX": str(start),
                 # SRSNAME est un piege : la requete renvoie zero objet, sans erreur.
                 "BBOX": "%f,%f,%f,%f,CRS:84" % bbox}
            url = WFS + "?" + urllib.parse.urlencode(q)
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA),
                                        timeout=timeout) as r:
                d = json.load(r)
            lot = d.get("features", [])
            feats += lot
            if len(lot) < 1000:
                break
            start += 1000
        if cache:
            os.makedirs(os.path.dirname(cache) or ".", exist_ok=True)
            with open(cache, "w", encoding="utf-8") as f:
                json.dump(feats, f)
    out = []
    for f in feats:
        p = f["properties"]
        if p.get("nature") != "Petit terrain multi-sports":
            continue
        pts = []
        def parcourir(x):
            if isinstance(x, list) and x and isinstance(x[0], (int, float)):
                pts.append(x)
            elif isinstance(x, list):
                for y in x:
                    parcourir(y)
        parcourir(f["geometry"]["coordinates"])
        if not pts:
            continue
        out.append({"source": "BD TOPO (city-stade)",
                    "nom": p.get("nature_detaillee") or "Plateau multisports",
                    "lat": sum(q[1] for q in pts) / len(pts),
                    "lon": sum(q[0] for q in pts) / len(pts),
                    "osm": None})
    return out


def contour(dep, timeout=60):
    """Anneaux du contour d'un departement, pour un test point-dans-polygone.

    La BD TOPO s'interroge par boite englobante : sans ce redecoupage, un
    balayage de la Loire-Atlantique remonte des city-stades de Vendee, du
    Maine-et-Loire et d'Ille-et-Vilaine. Une requete, et le compte tombe de
    moitie."""
    # geo.api.gouv.fr ne sert pas le contour d'un departement, seulement celui
    # d'une commune : on prend les communes, en une requete, et on teste
    # l'appartenance a l'une quelconque d'entre elles.
    url = f"{GEOAPI}/departements/{code_osm(dep)}/communes?fields=contour&format=json&geometry=contour"
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
        communes = json.load(r)
    anneaux = []
    for c in communes:
        geom = c.get("contour")
        if not geom:
            continue
        if geom["type"] == "Polygon":
            anneaux.append(geom["coordinates"][0])
        else:
            anneaux += [poly[0] for poly in geom["coordinates"]]
    return anneaux


def dedans(lon, lat, anneaux):
    """Le point tombe-t-il dans l'une des communes ? (lancer de rayon)

    Un anneau a la fois : les communes sont disjointes, donc appartenir a deux
    d'entre elles n'a pas de sens et un compteur global s'annulerait."""
    for g in anneaux:
        if not (min(p[1] for p in g) <= lat <= max(p[1] for p in g)):
            continue                        # boite englobante, pour aller vite
        dans = False
        for i in range(len(g) - 1):
            x1, y1 = g[i][0], g[i][1]
            x2, y2 = g[i + 1][0], g[i + 1][1]
            if (y1 > lat) != (y2 > lat):
                xi = x1 + (lat - y1) * (x2 - x1) / (y2 - y1)
                if lon < xi:
                    dans = not dans
        if dans:
            return True
    return False


def regrouper(lieux):
    """Une rue, le gymnase qu'elle dessert et son city-stade : un seul lieu."""
    groupes = []
    for l in lieux:
        for g in groupes:
            if dist((l["lat"], l["lon"]), (g[0]["lat"], g[0]["lon"])) <= REGROUPEMENT:
                g.append(l)
                break
        else:
            groupes.append([l])
    out = []
    for g in groupes:
        # le representant porte le nom le plus parlant : un equipement plutot
        # qu'une voie, une voie plutot qu'un plateau anonyme
        rang = {"OSM (equipement nomme)": 0, "OSM (voie)": 1}
        chef = min(g, key=lambda l: rang.get(l["source"], 2))
        chef = dict(chef)
        chef["sources"] = sorted({l["source"] for l in g})
        chef["noms"] = sorted({l["nom"] for l in g if l["nom"]})
        out.append(chef)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dep", help="code de departement, ex. 44")
    ap.add_argument("--sans-toponymie", action="store_true")
    ap.add_argument("--sans-bdtopo", action="store_true")
    ap.add_argument("--rayon", type=float, default=RAYON_CONNU, metavar="M",
                    help=f"distance en deca de laquelle un site connu couvre le lieu "
                         f"(defaut {RAYON_CONNU:.0f} m)")
    ap.add_argument("--deja", metavar="FICHIER",
                    help="JSON produit par pistes_absentes.py : ses candidats sont retires")
    ap.add_argument("--cache-dir", default=".work/lieux", help="cache des requetes")
    ap.add_argument("--ortho", metavar="DOSSIER", help="telecharge une vue aerienne par lieu")
    ap.add_argument("--planches", metavar="DOSSIER",
                    help="idem, et assemble des planches-contact de 9 vignettes")
    ap.add_argument("--json", metavar="FICHIER")
    ap.add_argument("--limite", type=int, help="s'arrete apres N lieux (essai)")
    args = ap.parse_args()

    cd = args.cache_dir
    lieux = []
    if not args.sans_toponymie:
        lieux += toponymie(args.dep, os.path.join(cd, f"osm-{args.dep}.json"))
        print(f"-> {len(lieux)} lieu(x) au nom parlant dans OpenStreetMap")
    if not args.sans_bdtopo:
        n = len(lieux)
        lieux += citystades(args.dep, os.path.join(cd, f"bdtopo-{args.dep}.json"))
        print(f"-> {len(lieux) - n} city-stade(s) dans la BD TOPO")

    avant = len(lieux)
    anneaux = contour(args.dep)
    lieux = [l for l in lieux if dedans(l["lon"], l["lat"], anneaux)]
    if avant != len(lieux):
        print(f"-> {avant - len(lieux)} lieu(x) hors du departement, retire(s)")

    groupes = regrouper(lieux)
    print(f"-> {len(groupes)} lieu(x) distinct(s) apres regroupement")

    sites = charger_sites()
    reste = []
    for l in groupes:
        p = (l["lat"], l["lon"])
        proche = min(sites, key=lambda s: dist(p, (s["lat"], s["lon"])))
        d = dist(p, (proche["lat"], proche["lon"]))
        if d <= args.rayon:
            continue
        l["proche_nom"], l["proche_m"] = proche["nom"], round(d)
        reste.append(l)
    print(f"-> {len(reste)} sans site connu a moins de {args.rayon:.0f} m")

    if args.deja and os.path.exists(args.deja):
        with open(args.deja, encoding="utf-8") as f:
            candidats = json.load(f)
        avant = len(reste)
        reste = [l for l in reste
                 if all(dist((l["lat"], l["lon"]), (c["lat"], c["lon"])) > REGROUPEMENT
                        for c in candidats)]
        print(f"-> {avant - len(reste)} deja signale(s) par pistes_absentes.py, retire(s)")

    reste.sort(key=lambda l: -l["proche_m"])
    if args.limite:
        reste = reste[:args.limite]

    dossier = args.planches or args.ortho
    for i, l in enumerate(reste, 1):
        ville, voie, cp = adresse(l["lat"], l["lon"])
        l.update(commune=ville, voie=voie, cp=cp)
        if dossier:
            os.makedirs(dossier, exist_ok=True)
            f = os.path.join(dossier, f"{i:03d}-{slug(ville)}-{slug(l['nom'])}.jpg")
            if not os.path.exists(f):
                urllib.request.urlretrieve(url_ortho(l["lat"], l["lon"], CHAMP, 800), f)
            l["ortho"] = f
        etiquette = " · ".join(x for x in (l.get("nom"), ville, voie) if x)
        print(f"{i:3d}. {etiquette[:70]:<70} {l['lat']:.5f},{l['lon']:.5f}"
              f"  ({l['proche_m']} m du plus proche connu)")

    if args.planches:
        planches(reste, args.planches)
    if args.json:
        os.makedirs(os.path.dirname(os.path.abspath(args.json)), exist_ok=True)
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(reste, f, ensure_ascii=False, indent=2)
            f.write("\n")
        print(f"-> {args.json}")

    print(f"\n{len(reste)} lieu(x) a regarder. Aucun n'est une piste tant que "
          f"personne\nne l'a vu : ce sont des endroits ou il pourrait y en avoir une.")


def planches(lieux, dossier, tuile=470, par=9):
    """Planches-contact numerotees : neuf vignettes se lisent d'un coup d'oeil."""
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        sys.exit("Pillow est requis pour --planches :  pip install Pillow")
    vignettes = []
    for i, l in enumerate(lieux, 1):
        if not l.get("ortho") or not os.path.exists(l["ortho"]):
            continue
        im = Image.open(l["ortho"]).resize((tuile, tuile), Image.LANCZOS).convert("RGB")
        d = ImageDraw.Draw(im)
        etiquette = f"{i} {(l.get('commune') or '?')[:24]}"
        d.rectangle([0, 0, len(etiquette) * 8 + 10, 24], fill=(0, 0, 0))
        d.text((5, 7), etiquette, fill=(255, 255, 0))
        d.rectangle([0, 0, tuile - 1, tuile - 1], outline=(255, 255, 0), width=2)
        vignettes.append(im)
    for n in range(0, len(vignettes), par):
        lot = vignettes[n:n + par]
        cote = int(math.ceil(math.sqrt(par)))
        planche = Image.new("RGB", (tuile * cote, tuile * cote), (20, 20, 20))
        for k, v in enumerate(lot):
            planche.paste(v, ((k % cote) * tuile, (k // cote) * tuile))
        chemin = os.path.join(dossier, f"planche{n // par + 1:02d}.png")
        planche.save(chemin)
    print(f"-> {(len(vignettes) + par - 1) // par} planche(s) dans {dossier}/")


if __name__ == "__main__":
    main()
