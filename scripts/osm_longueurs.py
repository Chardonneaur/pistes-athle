#!/usr/bin/env python3
"""Tire d'OpenStreetMap ce que le recensement ne dit pas : developpement et couloirs.

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

LES COULOIRS. Le tag « lanes » d'OSM donne leur nombre. C'est le champ le plus
rare de la base — 123 fiches sur 7 280 — et OSM le porte sur environ 15 % de ses
anneaux : de quoi doubler ce compte. Il n'est pas exploitable brut. Des anneaux
de 400 m portent lanes=1, 2 ou 3, ce qui ne decrit pas une piste a trois
couloirs mais la ligne que le contributeur tracait. D'ou la fourchette de
plausibilite COULOIRS_MIN..COULOIRS_MAX, hors de laquelle on se tait.

Les deux champs se gagnent SEPAREMENT, et c'est voulu : un anneau donne souvent
l'un sans l'autre. Le ministere declare parfois la longueur et jamais les
couloirs ; OSM fait souvent l'inverse. Les lier ferait perdre la moitie du gain.

Ni l'un ni l'autre n'ecrase une valeur deja presente.

(c) OpenStreetMap contributors, ODbL — https://www.openstreetmap.org/copyright
"""
import argparse
import json
import math
import os
import re
import sys
import time
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TRACKS = os.path.join(ROOT, "data", "tracks.json")
OVERRIDES = os.path.join(ROOT, "data", "overrides")
# Overpass rend regulierement des 504 quand il est charge : sur un balayage de
# la France entiere, un departement sur trois se perdait ainsi. Ce ne sont pas
# des refus, ce sont des attentes — la meme requete passe quelques secondes plus
# tard. Deux miroirs, essayes dans l'ordre, et trois tentatives par miroir.
OVERPASS = ("https://overpass-api.de/api/interpreter",
            "https://overpass.kumi.systems/api/interpreter")
TENTATIVES = 3
ATTENTE = 20          # secondes, doublees a chaque echec

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

# Le tag « lanes » d'OSM donne le nombre de couloirs — le champ le plus rare de
# la base : 123 fiches sur 7 280. Il n'est pas exploitable brut. Des anneaux de
# 400 m portent lanes=1, 2 ou 3 : ce n'est pas une piste a trois couloirs,
# c'est un contributeur qui a decrit la ligne qu'il tracait, pas l'equipement.
# Une piste d'athletisme en a quatre au minimum, huit ou neuf au plus large.
# Hors de cette fourchette, on ne conclut pas.
COULOIRS_MIN, COULOIRS_MAX = 4, 10

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
    charge = urllib.parse.urlencode({"data": REQUETE % dep}).encode()
    entetes = {"User-Agent": "pistes-athle/1.0 (github.com/Chardonneaur/pistes-athle)"}
    data = dernier = None
    for miroir in OVERPASS:
        for essai in range(1, TENTATIVES + 1):
            try:
                req = urllib.request.Request(miroir, data=charge, headers=entetes)
                with urllib.request.urlopen(req, timeout=280) as r:
                    data = json.load(r)
                break
            except (urllib.error.HTTPError, urllib.error.URLError,
                    TimeoutError, json.JSONDecodeError) as exc:
                dernier = exc
                code = getattr(exc, "code", None)
                # 400 = la requete elle-meme est fautive, 404 = pas de zone :
                # reessayer ne changera rien, et masquerait l'erreur.
                if code in (400, 404):
                    raise
                pause = ATTENTE * 2 ** (essai - 1)
                print(f"   {type(exc).__name__} {code or ''} sur {urllib.parse.urlsplit(miroir).netloc}"
                      f" — tentative {essai}/{TENTATIVES}, nouvelle dans {pause} s")
                if essai < TENTATIVES:
                    time.sleep(pause)
        if data is not None:
            break
    if data is None:
        raise SystemExit(f"Overpass injoignable pour le departement {dep} apres "
                         f"{TENTATIVES} tentatives sur {len(OVERPASS)} miroirs : {dernier}")
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


def couloirs_de(lanes):
    """Le nombre de couloirs, si le tag OSM est croyable — sinon rien.

    Meme discipline que recaler() pour le developpement : on prefere se taire a
    publier un chiffre qu'on n'aurait pas su defendre. Un blanc ne dit pas
    « pas de couloirs », il ne dit rien.
    """
    try:
        n = int(str(lanes).strip())
    except (TypeError, ValueError):
        return None
    return n if COULOIRS_MIN <= n <= COULOIRS_MAX else None


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


def nie_sa_piste(site_id):
    """Vrai si une contribution declare explicitement qu'il n'y a pas de piste.

    `piste: false` dans data/tracks.json ne suffit pas : c'est aussi la valeur
    par defaut des 605 installations dont le recensement ne declare simplement
    aucune piste. Sur 26 d'entre elles, un anneau trace dans OpenStreetMap
    signale au contraire une piste que le ministere ignore, et c'est
    precisement ce que ce script sert a trouver. Seul un override qui pose
    `piste: false` est un constat de terrain : quelqu'un est alle voir, et il
    n'y a rien.
    """
    chemin = os.path.join(OVERRIDES, f"{site_id}.json")
    if not os.path.exists(chemin):
        return False
    with open(chemin, encoding="utf-8") as f:
        return json.load(f).get("piste") is False


def ecrire_override(site_id, source, longueur=None, couloirs=None):
    """Ajoute `longueur_probable` et/ou `couloirs` sans toucher au reste.

    Les deux s'ecrivent separement parce qu'ils se gagnent separement : un
    anneau peut donner un developpement sans porter de tag « lanes », et
    l'inverse arrive aussi — le ministere declare parfois la longueur et jamais
    les couloirs. Lier les deux ferait perdre la moitie de ce qu'OSM donne.

    Chaque phrase de note est ecrite une seule fois : le script est relance
    departement par departement, et sans ce controle la note s'allongerait d'une
    repetition a chaque passage.
    """
    chemin = os.path.join(OVERRIDES, f"{site_id}.json")
    if os.path.exists(chemin):
        with open(chemin, encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = {"id": site_id}

    phrases = []
    if longueur is not None:
        data["longueur_probable"] = longueur
        # Phrase inchangee au caractere pres : 232 contributions la portent
        # deja, et la reecrire ferait un diff sur des fiches qui n'ont pas
        # bouge.
        phrases.append(f"Développement estimé à {longueur} m d'après le tracé "
                       f"de l'anneau dans OpenStreetMap ({source}), non mesuré "
                       f"sur place.")
    if couloirs is not None:
        data["couloirs"] = couloirs
        phrases.append(f"{couloirs} couloirs d'après le tracé de l'anneau dans "
                       f"OpenStreetMap ({source}), non comptés sur place.")

    for note in phrases:
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
    ap.add_argument("--sites", metavar="IDS",
                    help="ne traiter que ces identifiants, separes par des "
                         "virgules. Sert a l'etage 2 : la file Search Console "
                         "designe des fiches, pas des departements.")
    args = ap.parse_args()

    sites = charger_sites(args.dep)
    if args.sites:
        voulus = {i.strip() for i in args.sites.split(",") if i.strip()}
        connus = {s["id"] for s in sites}
        absents = voulus - connus
        if absents:
            sys.exit(f"pas en departement {args.dep} : {', '.join(sorted(absents))}")
        sites = [s for s in sites if s["id"] in voulus]
    if not sites:
        sys.exit(f"aucun site en departement {args.dep} dans data/tracks.json")
    boucles = anneaux(interroger(args.dep, args.cache))
    print(f"-> {len(boucles)} anneau(x) exploitable(s) dans OSM\n")

    accords = desaccords = nouveaux = refus = 0
    couloirs_neufs = 0
    ecrits = set()
    print(f"{'declare':>8} {'OSM':>7} {'estime':>7} {'coul':>5}  site")
    for s, b, d, cible in sorted(apparier(sites, boucles),
                                 key=lambda p: (p[0].get("longueur_piste") or 0)):
        # « declare » doit couvrir les DEUX champs, pas seulement celui du
        # ministere. Ne regarder que longueur_piste ecrasait toute estimation
        # deja etablie autrement : le releve des pistes absentes ecrit un
        # longueur_probable dont la note dit explicitement que le perimetre
        # trace n'est PAS un developpement, et ce script le remplacait par sa
        # propre valeur recalee, en laissant les deux phrases se contredire
        # dans la meme note. 143 contributions etaient dans ce cas, dont des
        # anneaux courts releves sur place — 75 m, 85 m, 116 m.
        #
        # Regle : on comble un vide, on ne corrige jamais une valeur existante.
        # Un desaccord se signale et se tranche a la main.
        declare = s.get("longueur_piste") or s.get("longueur_probable")
        etat = ""
        nie = nie_sa_piste(s["id"])
        if nie:
            # Un vide laisse par une visite n'est pas un vide a combler. La
            # Neustrie (I440200018) a ete visitee le 27 aout 2026 : le seul
            # anneau du complexe est une piste de roller, et la visite avait
            # efface le developpement. Ce script l'a reecrit a 400 m dix jours
            # plus tard, en mesurant exactement l'anneau que la visite venait de
            # recuser — la fiche affichait donc un chiffre que sa propre note
            # desavouait. Overpass ne sait pas distinguer un anneau de roller
            # d'une piste ; quelqu'un qui y est alle, si.
            refus += 1
            etat = "  (visite sur place : pas de piste d'athletisme ici)"
            cible = None
        elif cible is None:
            refus += 1
            etat = "  (aucun developpement normalise assez proche)"
        elif declare is None:
            nouveaux += 1
        elif cible == declare:
            accords += 1
        else:
            desaccords += 1
            etat = f"  <<< desaccord : le ministere dit {declare} m"

        # Le developpement et les couloirs se gagnent separement : un anneau
        # peut donner l'un sans l'autre, et souvent c'est le cas.
        nb = couloirs_de(b.get("lanes"))
        longueur_a_ecrire = cible if (cible is not None and declare is None) else None
        # les couloirs tombent avec le developpement : compter les couloirs d'un
        # anneau dont la visite dit qu'il n'est pas une piste d'athletisme
        # reintroduirait la meme erreur par l'autre champ.
        couloirs_a_ecrire = (nb if (nb is not None and not s.get("couloirs") and not nie)
                             else None)
        if couloirs_a_ecrire:
            couloirs_neufs += 1
            etat += f"  (+{couloirs_a_ecrire} couloirs)"

        print(f"{str(declare or '?'):>8} {b['m']:7.1f} {str(cible or '-'):>7} "
              f"{str(s.get('couloirs') or nb or '-'):>5}  "
              f"{s['nom'][:44]}, {s['ville']}{etat}")

        if args.ecrire and (longueur_a_ecrire or couloirs_a_ecrire):
            ecrits.add(ecrire_override(s["id"], b["id"],
                                       longueur=longueur_a_ecrire,
                                       couloirs=couloirs_a_ecrire))

    print(f"\n{accords} accord(s) avec le ministere, {desaccords} desaccord(s), "
          f"{nouveaux} site(s) sans developpement declare, {refus} refus.")
    print(f"{couloirs_neufs} site(s) dont OSM donne les couloirs et le site pas encore.")
    if args.ecrire:
        print(f"-> {len(ecrits)} fichier(s) ecrit(s) dans data/overrides/")
    elif nouveaux or couloirs_neufs:
        print("-> relancez avec --ecrire pour renseigner ce qui manque.")
    print("\nLes desaccords ne sont pas ecrits : une estimation ne renverse pas "
          "une donnee declaree.\nVerifiez-les a la vue aerienne "
          "(scripts/ortho.py) avant de trancher a la main.")


if __name__ == "__main__":
    main()
