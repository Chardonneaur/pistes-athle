#!/usr/bin/env python3
"""Estime le developpement des pistes d'un departement d'apres OpenStreetMap.

    python3 scripts/osm_longueurs.py 44
    python3 scripts/osm_longueurs.py 44 --ecrire

Le recensement du ministere ne renseigne pas le developpement de la piste pour
la majorite des sites, et se trompe parfois : Saint-Philbert-de-Grand-Lieu y
est declare a 200 m pour un anneau de 250 m. OpenStreetMap trace souvent
l'anneau ; son perimetre donne une estimation.

Une estimation, et rien de plus. Le perimetre d'un anneau OSM depend de ce que
le contributeur a trace : la lice, la corde, ou le bord exterieur du
revetement. Sur les pistes de Loire-Atlantique declarees a 400 m par le
ministere, les perimetres OSM vont de 410 a 457 m. On corrige donc d'un facteur
median puis on recale sur le developpement normalise le plus proche, et on
refuse de conclure quand rien ne tombe assez pres.

Le resultat va dans `longueur_probable`, jamais dans `longueur_piste` : c'est
la meme discipline que `agres_probables`. Une mesure au decametre ou un panneau
de club l'emportent, et l'effacent.

(c) OpenStreetMap contributors, ODbL — https://www.openstreetmap.org/copyright
"""
import argparse
import json
import math
import os
import re
import sys
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TRACKS = os.path.join(ROOT, "data", "tracks.json")
OVERRIDES = os.path.join(ROOT, "data", "overrides")
OVERPASS = "https://overpass-api.de/api/interpreter"

# Developpements normalises rencontres sur le terrain.
NORMALISES = (200, 250, 300, 333, 400)

# Facteur median mesure sur les pistes de Loire-Atlantique dont le ministere
# donne 400 m et dont l'appariement OSM ne fait aucun doute.
FACTEUR = 1.03
# Au-dela, l'anneau OSM ne ressemble a aucun developpement connu : on se tait.
TOLERANCE = 0.08
# Un anneau trace correctement a beaucoup de points : ses virages sont des
# arcs. Une boucle de quatre ou cinq points est un rectangle — l'emprise du
# stade, une cloture — pas une piste.
MIN_POINTS = 10
# Distance maximale entre le centre de l'anneau et le point du ministere.
RAYON = 200.0

R_TERRE = 6371000.0


def dist(a, b):
    (y1, x1), (y2, x2) = a, b
    p = math.pi / 180
    h = (math.sin((y2 - y1) * p / 2) ** 2
         + math.cos(y1 * p) * math.cos(y2 * p) * math.sin((x2 - x1) * p / 2) ** 2)
    return 2 * R_TERRE * math.asin(math.sqrt(h))


def points(geom):
    return [(p["lat"], p["lon"]) for p in geom or []]


def perimetre(g):
    return sum(dist(g[i], g[i + 1]) for i in range(len(g) - 1))


def ferme(g, tol=3.0):
    return len(g) > 3 and dist(g[0], g[-1]) < tol


def centre(g):
    return (sum(p[0] for p in g) / len(g), sum(p[1] for p in g) / len(g))


REQUETE = """
[out:json][timeout:240];
area["ref:INSEE"="%s"]["admin_level"="6"]->.a;
(
  way["leisure"~"^(track|pitch)$"]["sport"~"athletics|running"](area.a);
  relation["leisure"~"^(track|pitch)$"]["sport"~"athletics|running"](area.a);
  way["athletics"](area.a);
  relation["athletics"](area.a);
);
// « out geom » et non « out geom tags » : le mode tags reduit la sortie aux
// etiquettes et fait perdre les MEMBRES des relations. Les anneaux traces en
// multipolygone — un contour exterieur, un contour interieur — revenaient
// alors vides, et etaient silencieusement ignores. Sur le Nord, cela cachait
// 43 anneaux sur 139, soit trois sites apparies sur dix.
out geom;
"""


def interroger(dep, cache=None):
    if cache and os.path.exists(cache):
        print(f"-> lecture du cache {cache}")
        with open(cache, encoding="utf-8") as f:
            return json.load(f)
    req = urllib.request.Request(
        OVERPASS, data=urllib.parse.urlencode({"data": REQUETE % dep}).encode(),
        headers={"User-Agent": "pistes-athle/1.0 (github.com/Chardonneaur/pistes-athle)"})
    with urllib.request.urlopen(req, timeout=280) as r:
        data = json.load(r)
    print(f"-> {len(data['elements'])} objets OSM recus")
    if cache:
        with open(cache, "w", encoding="utf-8") as f:
            json.dump(data, f)
    return data


def est_athle(t):
    sport = t.get("sport") or ""
    return "athletics" in sport or "running" in sport or t.get("athletics") == "running"


def anneaux(data):
    """Boucles fermees susceptibles d'etre un anneau de course."""
    out = []
    for e in data["elements"]:
        tags = e.get("tags", {})
        if not est_athle(tags):
            continue
        boucles = []
        if e["type"] == "way":
            g = points(e.get("geometry"))
            if ferme(g):
                boucles.append(g)
        else:
            for role in ("inner", "outer"):
                for m in e.get("members", []):
                    if m.get("role") == role and m.get("geometry"):
                        g = points(m["geometry"])
                        if ferme(g):
                            boucles.append(g)
                if boucles:
                    break                      # l'interieur prime sur l'exterieur
        for g in boucles:
            if len(g) < MIN_POINTS:
                continue
            m = perimetre(g)
            if not 150 <= m <= 520:            # ni un cercle de lancer, ni un hippodrome
                continue
            out.append({"id": f"{e['type'][0]}{e['id']}", "pts": len(g),
                        "m": m, "c": centre(g), "lanes": tags.get("lanes")})
    return out


def recaler(metres):
    """Developpement normalise le plus proche, ou None si aucun ne convient."""
    estime = metres / FACTEUR
    cible = min(NORMALISES, key=lambda n: abs(n - estime))
    return cible if abs(cible - estime) / cible <= TOLERANCE else None


def apparier(sites, boucles):
    for s in sites:
        proches = [(dist((s["lat"], s["lon"]), b["c"]), b) for b in boucles]
        proches = [(d, b) for d, b in proches if d < RAYON]
        if not proches:
            continue
        # le plus grand anneau du site : les petits sont des pistes annexes
        d, b = max(proches, key=lambda p: p[1]["m"])
        yield s, b, d, recaler(b["m"])


def charger_sites(dep):
    with open(TRACKS, encoding="utf-8") as f:
        data = json.load(f)
    cle = {v: k for k, v in data["keymap"].items()}
    out = []
    for t in data["tracks"]:
        if t.get(cle["dep"]) != dep or t.get(cle["lat"]) is None:
            continue
        out.append({k: t.get(cle[k]) for k in
                    ("id", "nom", "ville", "lat", "lon", "longueur_piste",
                     "longueur_probable", "couloirs", "piste")})
    return out


def ecrire_override(site_id, longueur, source):
    """Ajoute `longueur_probable` sans toucher au reste du fichier."""
    chemin = os.path.join(OVERRIDES, f"{site_id}.json")
    if os.path.exists(chemin):
        with open(chemin, encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = {"id": site_id}
    data["longueur_probable"] = longueur
    note = (f"Développement estimé à {longueur} m d'après le tracé de l'anneau "
            f"dans OpenStreetMap ({source}), non mesuré sur place.")
    if note not in (data.get("note") or ""):
        data["note"] = ((data.get("note") + " ") if data.get("note") else "") + note
    with open(chemin, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    return chemin


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dep", help="code de departement, ex. 44")
    ap.add_argument("--ecrire", action="store_true",
                    help="ecrit longueur_probable dans data/overrides/")
    ap.add_argument("--cache", help="fichier de cache de la reponse Overpass")
    args = ap.parse_args()

    sites = charger_sites(args.dep)
    if not sites:
        sys.exit(f"aucun site en departement {args.dep} dans data/tracks.json")
    boucles = anneaux(interroger(args.dep, args.cache))
    print(f"-> {len(boucles)} anneau(x) exploitable(s) dans OSM\n")

    accords = desaccords = nouveaux = refus = 0
    ecrits = []
    print(f"{'declare':>8} {'OSM':>7} {'estime':>7}  site")
    for s, b, d, cible in sorted(apparier(sites, boucles),
                                 key=lambda p: (p[0].get("longueur_piste") or 0)):
        declare = s.get("longueur_piste")
        etat = ""
        if cible is None:
            refus += 1
            etat = "  (aucun developpement normalise assez proche)"
        elif declare is None:
            nouveaux += 1
        elif cible == declare:
            accords += 1
        else:
            desaccords += 1
            etat = f"  <<< desaccord : le ministere dit {declare} m"
        print(f"{str(declare or '?'):>8} {b['m']:7.1f} {str(cible or '-'):>7}  "
              f"{s['nom'][:44]}, {s['ville']}{etat}")
        if args.ecrire and cible is not None and declare is None:
            ecrits.append(ecrire_override(s["id"], cible, b["id"]))

    print(f"\n{accords} accord(s) avec le ministere, {desaccords} desaccord(s), "
          f"{nouveaux} site(s) sans developpement declare, {refus} refus.")
    if args.ecrire:
        print(f"-> {len(ecrits)} fichier(s) ecrit(s) dans data/overrides/")
    elif nouveaux:
        print("-> relancez avec --ecrire pour renseigner les sites sans developpement.")
    print("\nLes desaccords ne sont pas ecrits : une estimation ne renverse pas "
          "une donnee declaree.\nVerifiez-les a la vue aerienne "
          "(scripts/ortho.py) avant de trancher a la main.")


if __name__ == "__main__":
    main()
