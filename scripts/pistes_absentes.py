#!/usr/bin/env python3
"""Cherche dans OpenStreetMap les pistes que l'annuaire ne connait pas.

    python3 scripts/pistes_absentes.py 44
    python3 scripts/pistes_absentes.py 44 --ortho .work/ortho
    python3 scripts/pistes_absentes.py --tous --cache-dir .work/osm --json .work/absentes.json

Le recensement du ministere est declaratif : ce qu'une commune ne declare pas
n'y figure pas, et l'application ne peut pas l'inventer. L'anneau de quatre
couloirs peint autour du city-stade du Clion-sur-Mer (Pornic) en est l'exemple :
cartographie dans OpenStreetMap depuis juillet 2025, lisible sur l'orthophoto
IGN, absent des 97 equipements que Data ES declare sur la commune - sous
« Equipement d'athletisme » comme sous n'importe quelle autre famille.

Ce script prend donc le probleme par l'autre bout. Il liste les anneaux de
course cartographies dans OSM, retire ceux qu'un site de data/tracks.json
revendique deja, et affiche ce qui reste.

Chaque ligne est une piste *a verifier*, pas une piste prouvee. Un anneau peut
etre un circuit de karting mal tague, un contributeur peut avoir dessine
l'emprise du stade plutot que la corde, et le perimetre affiche est celui du
trace, jamais une mesure. La vue aerienne (--ortho) tranche depuis le bureau la
plupart des cas ; le reste demande d'y aller, appareil photo en main. Une fois
sur place, CONTRIBUTING.md dit comment transformer une ligne de cette liste en
contribution (identifiant `c-...`).

(c) OpenStreetMap contributors, ODbL - https://www.openstreetmap.org/copyright
(c) IGN - BD ORTHO(R), Licence Ouverte 2.0, pour les images de --ortho.
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

from build_data import annee_ortho
from ortho import carte as url_ortho
from osm_longueurs import OVERPASS, centre, dist, ferme, perimetre, points

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TRACKS = os.path.join(ROOT, "data", "tracks.json")

# Quatre choses que ce fichier importait d'osm_longueurs, ou elles n'ont jamais
# existe : le script ne demarrait donc pas, sous aucune de ses formes. Elles
# vivent ici desormais. Un emprunt entre scripts derive des que l'un des deux
# bouge, et celui-la avait derive sans que rien ne le signale.
ESSAIS = 4                 # reprises d'une requete Overpass avant d'abandonner
PAUSE = 1.5                # secondes entre deux requetes : on visite un bien commun


def code_osm(dep):
    """Le code que porte le departement dans OSM, sous `ref:INSEE`.

    C'est le code du departement tel quel — « 74 », « 2A », « 971 ». La
    fonction existe pour que la requete lise bien, et pour porter cette
    reserve : outre-mer, le departement est aussi une region et OSM le tague
    en admin_level 4, la ou la requete demande 6. Ces departements-la sortent
    donc en echec, ce que le releve final nomme."""
    return dep


def dedans(point, g):
    """Le point (lat, lon) tombe-t-il dans l'anneau g ? (lancer de rayon)

    `g` est une liste de couples (lat, lon), comme la rend points(). Sert a
    savoir si un site du recensement est *a l'interieur* d'un anneau trouve
    dans OSM : c'est le seul rattachement certain, la distance au centre ne
    l'etant jamais — Data ES pointe souvent le gymnase plutot que la piste."""
    if not g or len(g) < 4:
        return False
    lat, lon = point
    if not (min(p[0] for p in g) <= lat <= max(p[0] for p in g)):
        return False                        # boite englobante, pour aller vite
    if not (min(p[1] for p in g) <= lon <= max(p[1] for p in g)):
        return False
    dans = False
    for i in range(len(g) - 1):
        y1, x1 = g[i]
        y2, x2 = g[i + 1]
        if (y1 > lat) != (y2 > lat):
            xi = x1 + (lat - y1) * (x2 - x1) / (y2 - y1)
            if lon < xi:
                dans = not dans
    return dans


def charger_sites():
    """Tous les sites de l'annuaire, departement compris.

    osm_longueurs.charger_sites() prend desormais un departement et filtre
    dessus ; ce script les veut tous, et trie lui-meme."""
    with open(TRACKS, encoding="utf-8") as f:
        data = json.load(f)
    cle = {v: k for k, v in data["keymap"].items()}
    champs = ("id", "nom", "ville", "dep", "lat", "lon", "piste",
              "longueur_piste", "longueur_probable", "couloirs")
    return [{k: t.get(cle[k]) for k in champs}
            for t in data["tracks"] if t.get(cle["lat"]) is not None]

BAN = "https://api-adresse.data.gouv.fr/reverse/"
UA = {"User-Agent": "pistes-athle/1.0 (github.com/Chardonneaur/pistes-athle)"}

# Un anneau autour d'un city-stade de 28 x 15 m developpe 85 m ; en dessous de
# 60 m on tient un rond-point ou un cercle de lancer, au-dessus de 600 m un
# hippodrome ou un circuit automobile.
MIN_METRES, MAX_METRES = 60.0, 600.0

# Une boucle de quatre ou cinq points est un rectangle - l'emprise du stade,
# une cloture. Un anneau trace correctement a des virages, donc des points.
# Un trace ouvert n'a pas cette contrainte : une ligne droite tient en deux.
MIN_POINTS = 8
MIN_POINTS_OUVERT = 2

# Un sautoir, un couloir d'elan, une aire de lancer : de l'athletisme, mais pas
# une piste. Le tag `athletics` le dit lui-meme, et le dire vaut mieux que de
# le deviner a la taille. `sprint` n'y est pas : c'est une ligne droite.
CONCOURS = {"long_jump", "triple_jump", "high_jump", "pole_vault",
            "shot_put", "discus_throw", "javelin_throw", "hammer_throw"}

# Beaucoup de contributeurs dessinent une ligne droite comme une *surface* : un
# quadrilatere long et etroit, ferme, de quatre points. Le compte de points la
# rejette et son perimetre vaut deux fois sa longueur - deux facons de se
# tromper sur le meme objet. Huit couloirs de 1,22 m font 9,8 m de large ; plus
# large que cela, ou moins de quatre fois plus long que large, ce n'est plus une
# ligne droite mais une emprise.
LARGEUR_RUBAN = 12.0
ALLONGEMENT_RUBAN = 4.0

# Data ES place son point ou il veut dans l'installation : a l'entree, sur le
# gymnase voisin, parfois a la mairie. Au-dela de cette distance on considere
# que le site declare n'est pas celui de l'anneau.
RAYON_CONNU = 150.0

# Bord interieur et bord exterieur du meme revetement, anneau et ligne droite
# tracee a part : un equipement, une ligne de resultat.
REGROUPEMENT = 80.0

# Un anneau OSM n'a presque jamais de nom : c'est l'equipement qui le porte.
# On le cherche dans ce rayon, et on prefere le nom d'un complexe sportif a
# celui d'un parc.
RAYON_CONTEXTE = 200.0
CLASSES = (("leisure", ("sports_centre", "stadium")), ("amenity", ("school",
           "kindergarten", "college")), ("leisure", ("track", "pitch", "park",
           "playground")))

# Un anneau sans tag `sport` reste candidat : beaucoup de contributeurs
# s'arretent a leisure=track. Un anneau qui annonce un autre sport, non.
SPORTS_ATHLE = {"athletics", "running"}

REQUETE = """
[out:json][timeout:240];
area["ref:INSEE"="%s"]["admin_level"="6"]->.a;
(
  way["leisure"="track"](area.a);
  relation["leisure"="track"](area.a);
  way["leisure"="pitch"]["sport"~"athletics|running"](area.a);
  relation["leisure"="pitch"]["sport"~"athletics|running"](area.a);
  way["athletics"](area.a);
  relation["athletics"](area.a);
);
out body geom;
"""


CONTEXTE = """
[out:json][timeout:240];
(%s);
out tags center;
(%s);
out geom;
"""


def slug(s):
    s = unicodedata.normalize("NFD", s or "")
    s = "".join(c for c in s if unicodedata.category(c) != "Mn").lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-") or "site"


def overpass(requete, timeout=280, quoi=""):
    """Une requete Overpass, reprise ESSAIS fois avant d'abandonner.

    Overpass renvoie volontiers un 504 quand la requete est lourde ou le
    serveur charge : reessayer coute quelques secondes, echouer coute le
    departement."""
    req = urllib.request.Request(
        OVERPASS, data=urllib.parse.urlencode({"data": requete}).encode(), headers=UA)
    for essai in range(1, ESSAIS + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.load(r)
        except (urllib.error.URLError, OSError, ValueError) as exc:
            if essai == ESSAIS:
                raise
            attente = PAUSE * 4 * essai
            print(f"   {quoi}{exc} - nouvelle tentative dans {attente:.0f} s")
            time.sleep(attente)


def interroger(dep, cache=None, silencieux=False):
    """Reponse Overpass pour un departement, en cache si on en donne un.

    Meme prudence que dans osm_longueurs.py : le cache rend la campagne
    reprenable, et on reessaie plutot que d'abandonner un departement sur un
    Overpass surcharge."""
    if cache and os.path.exists(cache):
        with open(cache, encoding="utf-8") as f:
            return json.load(f)
    data = overpass(REQUETE % code_osm(dep), quoi=f"({dep}) ")
    if not silencieux:
        print(f"-> {len(data['elements'])} objets OSM recus")
    if cache:
        os.makedirs(os.path.dirname(cache), exist_ok=True)
        with open(cache, "w", encoding="utf-8") as f:
            json.dump(data, f)
    return data


def athle_possible(tags):
    sport = (tags.get("sport") or "").lower()
    if not sport:
        return True                       # leisure=track nu : ca se regarde
    return bool(set(re.split(r"[;,| ]+", sport)) & SPORTS_ATHLE)


def traces(e):
    """Traces exploitables d'un objet OSM : (points, boucle fermee ?).

    Sur un multipolygone, le bord interieur serre la corde : il prime sur le
    bord exterieur, qui suit l'enrobe et deborde.

    Un trace ouvert compte aussi. La piste du complexe Mickael-Landreau, a
    Arthon-en-Retz, est taguee leisure=track et dessinee dans OSM depuis des
    mois — mais son auteur a arrete son trait a 52 m du point de depart. Exiger
    une boucle fermee la rendait invisible, elle et toutes les lignes droites
    isolees, que le ministere recense pourtant sous « Piste d'athletisme
    isolee ». On garde le trace, et on dit qu'il est ouvert : sa longueur n'est
    alors pas un tour de piste.

    La meme ligne droite dessinee en *surface* revient ici fermee, et c'est
    `ruban()` qui la remet dans le bon sens : voir candidats()."""
    if e["type"] == "way":
        g = points(e.get("geometry"))
        return [(g, ferme(g))] if g else []
    for role in ("inner", "outer"):
        rings = [points(m["geometry"]) for m in e.get("members", [])
                 if m.get("role") == role and m.get("geometry")]
        rings = [(g, ferme(g)) for g in rings if g]
        if any(f for _, f in rings):
            return [(g, f) for g, f in rings if f]
        if rings:
            return rings
    return []


def emprise(g):
    """Longueur et largeur de la boite englobante, en metres."""
    lats = [p[0] for p in g]
    lons = [p[1] for p in g]
    cotes = (dist((min(lats), min(lons)), (min(lats), max(lons))),
             dist((min(lats), min(lons)), (max(lats), min(lons))))
    return max(cotes), min(cotes)


def aire(g):
    """Aire de la boucle, en metres carres : formule du lacet, projection locale.

    Sur quelques dizaines de metres, un degre de latitude vaut 111 320 m et un
    degre de longitude autant, multiplie par le cosinus de la latitude. La
    deformation residuelle est trois ordres de grandeur sous ce qu'on en fait."""
    lat0 = sum(p[0] for p in g) / len(g)
    k = math.cos(math.radians(lat0))
    xy = [(p[1] * k * 111320.0, p[0] * 111320.0) for p in g]
    return abs(sum(xy[i][0] * xy[i + 1][1] - xy[i + 1][0] * xy[i][1]
                   for i in range(len(xy) - 1))) / 2


def ruban(g):
    """Longueur de la ligne droite, si cette boucle n'est qu'un ruban.

    On cherche le rectangle qui a la meme aire A et le meme perimetre P que la
    boucle : sa longueur vaut P/4 + racine((P/4)^2 - A). Un anneau n'a pas de
    solution - il enferme plus d'aire qu'aucun rectangle de ce perimetre - et
    l'emprise d'un stade en donne une large. Retourne None dans les deux cas.

    C'est le critere que le compte de points remplacait mal : sur les
    soixante-six objets que la Loire-Atlantique ecartait pour « moins de huit
    points », aucun n'etait un anneau, et quarante et un etaient des lignes
    droites dessinees en surface - douze passe les bornes de longueur."""
    p = perimetre(g)
    a = aire(g)
    d = (p / 4) ** 2 - a
    if d <= 0:
        return None
    longueur = p / 4 + math.sqrt(d)
    largeur = a / longueur if longueur else 0
    if largeur > LARGEUR_RUBAN or longueur < ALLONGEMENT_RUBAN * largeur:
        return None
    # Une boucle mince mais repliee - un sentier qui revient sur lui-meme, un
    # pumptrack - enferme aussi peu d'aire qu'un ruban. Ce qui les separe : une
    # ligne droite tient dans sa boite englobante en diagonale, pas au-dela.
    cotes = emprise(g)
    if longueur > 1.05 * math.hypot(*cotes):
        return None
    return longueur


# Motifs d'ecart, dans l'ordre ou ils sont testes. Ils sont comptes et
# affiches : un filtre qui ecarte en silence ne se voit pas, et c'est ainsi que
# la piste d'Arthon-en-Retz a manque pendant tout un balayage.
MOTIFS = {
    "autre_sport": "sport declare autre que l'athletisme",
    "concours": "sautoir ou aire de lancer (tag athletics)",
    "sans_trace": "aucun trace geometrique exploitable",
    "trop_peu_de_points": "boucle trop grossiere (moins de %d points)" % MIN_POINTS,
    "hors_bornes": "longueur hors des bornes %.0f-%.0f m" % (MIN_METRES, MAX_METRES),
}


def candidats(data, ecartes=None):
    """Anneaux plausibles, un par trace retenu.

    `ecartes` recoit le compte des objets refuses, par motif."""
    compte = ecartes if ecartes is not None else {}
    def refuser(motif, e, detail=""):
        compte.setdefault(motif, []).append(f"{e['type']}/{e['id']}{detail}")

    out = []
    for e in data["elements"]:
        tags = e.get("tags", {})
        if not athle_possible(tags):
            refuser("autre_sport", e, f" (sport={tags.get('sport')})")
            continue
        concours = set(re.split(r"[;,| ]+", (tags.get("athletics") or "").lower()))
        if concours & CONCOURS:
            refuser("concours", e, f" (athletics={tags['athletics']})")
            continue
        vus = traces(e)
        if not vus:
            refuser("sans_trace", e)
            continue
        for g, boucle in vus:
            droite = ruban(g) if boucle else None
            if droite:
                boucle = False            # une ligne droite, pas un tour de piste
            if len(g) < (MIN_POINTS if boucle else MIN_POINTS_OUVERT):
                refuser("trop_peu_de_points", e, f" ({len(g)} points)")
                continue
            m = droite or perimetre(g)
            if not MIN_METRES <= m <= MAX_METRES:
                refuser("hors_bornes", e, f" ({m:.0f} m)")
                continue
            out.append({"osm": f"{e['type']}/{e['id']}", "g": g, "m": m,
                        "pts": len(g), "c": centre(g), "tags": tags, "boucle": boucle,
                        "ruban": bool(droite)})
    return out


def regrouper(cands):
    """Un equipement, un groupe. Le representant est la boucle la plus courte,
    celle qui approche le mieux le developpement reel."""
    groupes = []
    for c in sorted(cands, key=lambda x: x["m"]):
        for g in groupes:
            if dist(c["c"], g[0]["c"]) <= REGROUPEMENT:
                g.append(c)
                break
        else:
            groupes.append([c])
    return groupes


def revendique(sites, groupe, rayon):
    """Le site de l'annuaire qui possede cet anneau, s'il existe.

    Un point tombe *dans* la boucle tranche sans discussion. Sinon on regarde
    le plus proche : Data ES pointe souvent le gymnase plutot que la piste.
    Retourne (site, distance, certain)."""
    for c in groupe:
        if not c["boucle"]:
            continue                       # « dedans » ne veut rien dire sur un trait
        for s in sites:
            if dedans((s["lat"], s["lon"]), c["g"]):
                return s, dist(c["c"], (s["lat"], s["lon"])), True
    if not sites:
        return None, None, False
    c = groupe[0]
    s = min(sites, key=lambda s: dist(c["c"], (s["lat"], s["lon"])))
    d = dist(c["c"], (s["lat"], s["lon"]))
    return s, d, d <= rayon


def classe(tags):
    """Rang du lieu : un complexe sportif nomme vaut mieux qu'un parc."""
    for rang, (cle, valeurs) in enumerate(CLASSES):
        if tags.get(cle) in valeurs:
            return rang
    return len(CLASSES)


# Overpass repond 504 des que la requete enchaine trop de `around` : on
# interroge par paquets, quitte a y passer une minute de plus.
PAR_PAQUET = 8


def contexte(fiches):
    """Nom du lieu et enceinte scolaire, cherches autour de chaque anneau.

    Sans cela une fiche s'appellerait « 47.11917, -2.05296 » : l'anneau n'a pas
    de nom, l'equipement qui le porte en a un. La meme requete dit si l'anneau
    tombe dans une cour d'ecole, ce que le filtre « hors enceinte scolaire »
    de l'application demande de savoir."""
    paquets = [fiches[i:i + PAR_PAQUET] for i in range(0, len(fiches), PAR_PAQUET)]
    for n, paquet in enumerate(paquets, 1):
        noms = "".join(
            f'nwr(around:{RAYON_CONTEXTE:.0f},{f["lat"]},{f["lon"]})["name"]'
            '["leisure"~"^(sports_centre|stadium|track|pitch|park|playground)$"];'
            f'nwr(around:{RAYON_CONTEXTE:.0f},{f["lat"]},{f["lon"]})["name"]'
            '["amenity"~"^(school|kindergarten|college)$"];' for f in paquet)
        ecoles = "".join(
            f'way(around:{RAYON_CONTEXTE:.0f},{f["lat"]},{f["lon"]})'
            '["amenity"~"^(school|kindergarten|college)$"];' for f in paquet)
        try:
            data = overpass(CONTEXTE % (noms, ecoles), quoi=f"(contexte {n}/{len(paquets)}) ")
        except (urllib.error.URLError, OSError, ValueError) as exc:
            print(f"   contexte OSM indisponible pour le paquet {n} : {exc}")
            continue
        lieux, enceintes = [], []
        for e in data["elements"]:
            tags = e.get("tags", {})
            g = points(e.get("geometry"))
            c = centre(g) if g else ((e.get("center") or {}).get("lat"),
                                     (e.get("center") or {}).get("lon"))
            if tags.get("amenity") in ("school", "kindergarten", "college") and ferme(g):
                enceintes.append((g, tags.get("name")))
            if tags.get("name") and c and c[0] is not None:
                lieux.append((classe(tags), c, tags["name"]))
        for f in paquet:
            point = (f["lat"], f["lon"])
            proches = [(rang, dist(point, c), nom) for rang, c, nom in lieux
                       if dist(point, c) <= RAYON_CONTEXTE]
            if proches:
                f["lieu_osm"] = min(proches)[2]
            ecole = [nom for g, nom in enceintes if dedans(point, g)]
            if ecole:
                f["scolaire"] = True
                f["ecole"] = ecole[0]
        if n < len(paquets):
            time.sleep(PAUSE)


def adresse(lat, lon, timeout=15):
    """Commune et voie les plus proches, d'apres la Base Adresse Nationale.

    Un anneau n'a pas d'adresse dans OSM ; la contribution en demande une, et
    « Pornic, avenue des Sports » vaut mieux qu'un couple de coordonnees pour
    decider si on connait deja l'endroit."""
    url = BAN + "?" + urllib.parse.urlencode({"lat": lat, "lon": lon})
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA),
                                    timeout=timeout) as r:
            feats = json.load(r).get("features") or []
    except (urllib.error.URLError, OSError, ValueError):
        return None, None, None
    if not feats:
        return None, None, None
    p = feats[0]["properties"]
    return p.get("city"), p.get("street") or p.get("name"), p.get("postcode")


def telecharger_ortho(dossier, dep, fiche):
    """Vue aerienne cadree sur l'anneau, plus le millesime de la prise de vue."""
    os.makedirs(dossier, exist_ok=True)
    champ = max(150, min(500, round(fiche["longueur"] * 2.5 / 10) * 10))
    nom = f"{dep}-{slug(fiche['commune'] or 'commune')}-{fiche['osm'].replace('/', '')}.jpg"
    chemin = os.path.join(dossier, nom)
    urllib.request.urlretrieve(url_ortho(fiche["lat"], fiche["lon"], champ, 2000), chemin)
    try:
        annee = annee_ortho(fiche["lat"], fiche["lon"])
    except (urllib.error.URLError, OSError, ValueError):
        annee = None
    return chemin, champ, annee


def examiner(dep, sites, data, rayon, min_m, max_m, ecartes=None):
    """Anneaux OSM du departement qui ne correspondent a aucun site connu."""
    cands = [c for c in candidats(data, ecartes) if min_m <= c["m"] <= max_m]
    groupes = regrouper(cands)
    connus, absents = 0, []
    for groupe in groupes:
        site, d, certain = revendique(sites, groupe, rayon)
        if certain:
            connus += 1
            continue
        c = groupe[0]
        longueur, largeur = emprise(c["g"])
        absents.append({
            "dep": dep, "osm": c["osm"],
            "url": f"https://www.openstreetmap.org/{c['osm']}",
            "lat": round(c["c"][0], 5), "lon": round(c["c"][1], 5),
            "perimetre": round(c["m"], 1), "points": c["pts"], "boucle": c["boucle"],
            "ruban": c.get("ruban", False),
            "longueur": round(longueur), "largeur": round(largeur),
            "couloirs": c["tags"].get("lanes"),
            "surface": c["tags"].get("surface"),
            "nom_osm": c["tags"].get("name"),
            "boucles": len(groupe),
            "proche_id": site["id"] if site else None,
            "proche_nom": site["nom"] if site else None,
            "proche_ville": site["ville"] if site else None,
            "proche_m": round(d) if d is not None else None,
        })
    return groupes, connus, sorted(absents, key=lambda f: -(f["proche_m"] or 0))


def afficher(fiche):
    lieu = ", ".join(x for x in (fiche.get("commune"), fiche.get("voie")) if x)
    titre = fiche.get("nom_osm") or lieu or f"{fiche['lat']}, {fiche['lon']}"
    print(f"\n  {titre}   [{fiche['dep']}]")
    if lieu and fiche.get("nom_osm"):
        print(f"    {lieu}")
    if fiche.get("lieu_osm") and fiche["lieu_osm"] != fiche.get("nom_osm"):
        print(f"    {fiche['lieu_osm']}" +
              (f"  (enceinte scolaire : {fiche['ecole']})" if fiche.get("scolaire") else ""))
    detail = [f"anneau de {fiche['perimetre']:.0f} m" if fiche["boucle"]
              else f"ligne droite de {fiche['perimetre']:.0f} m" if fiche.get("ruban")
              else f"trace ouvert de {fiche['perimetre']:.0f} m",
              f"{fiche['longueur']} x {fiche['largeur']} m",
              f"{fiche['points']} points"]
    if fiche.get("couloirs"):
        detail.append(f"{fiche['couloirs']} couloirs (OSM)")
    if fiche.get("surface"):
        detail.append(fiche["surface"])
    print(f"    {', '.join(detail)}")
    print(f"    {fiche['lat']}, {fiche['lon']}   {fiche['url']}")
    if fiche.get("proche_nom"):
        print(f"    rien dans l'annuaire avant {fiche['proche_m']} m "
              f"({fiche['proche_nom']}, {fiche['proche_ville']})")
    else:
        print("    aucun site de l'annuaire dans ce departement")
    if fiche.get("ortho"):
        millesime = f", IGN {fiche['ortho_annee']}" if fiche.get("ortho_annee") else ""
        print(f"    {fiche['ortho']}  ({fiche['ortho_champ']} m de cote{millesime})")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dep", nargs="?", help="code de departement, ex. 44")
    ap.add_argument("--tous", action="store_true",
                    help="tous les departements presents dans data/tracks.json")
    ap.add_argument("--ortho", metavar="DOSSIER",
                    help="telecharge la vue aerienne IGN de chaque anneau absent")
    ap.add_argument("--json", metavar="FICHIER", help="ecrit le resultat en JSON")
    ap.add_argument("--cache", help="fichier de cache de la reponse Overpass")
    ap.add_argument("--cache-dir", help="repertoire de cache, un fichier par departement")
    ap.add_argument("--rayon", type=float, default=RAYON_CONNU, metavar="M",
                    help=f"distance en deca de laquelle un site connu revendique "
                         f"l'anneau (defaut {RAYON_CONNU:.0f} m)")
    ap.add_argument("--min", type=float, default=MIN_METRES, metavar="M",
                    help=f"perimetre minimal retenu (defaut {MIN_METRES:.0f} m)")
    ap.add_argument("--max", type=float, default=MAX_METRES, metavar="M",
                    help=f"perimetre maximal retenu (defaut {MAX_METRES:.0f} m)")
    ap.add_argument("--sans-adresse", action="store_true",
                    help="n'interroge pas la Base Adresse Nationale")
    ap.add_argument("--sans-contexte", action="store_true",
                    help="ne cherche pas le nom du lieu ni l'enceinte scolaire")
    args = ap.parse_args()

    if args.tous:
        deps = sorted({s["dep"] for s in charger_sites() if s.get("dep")},
                      key=lambda d: (len(d), d))
    elif args.dep:
        deps = [args.dep]
    else:
        ap.error("indiquez un code de departement, ou --tous")

    tous_sites = charger_sites()
    par_dep = {}
    for s in tous_sites:
        par_dep.setdefault(s.get("dep"), []).append(s)

    absents, echecs, ecartes = [], [], {}
    total_anneaux = total_connus = 0
    for i, dep in enumerate(deps, 1):
        cache = args.cache or (os.path.join(args.cache_dir, f"{dep}.json")
                               if args.cache_dir else None)
        neuf = not (cache and os.path.exists(cache))
        try:
            data = interroger(dep, cache, silencieux=len(deps) > 1)
        except Exception as exc:                            # noqa: BLE001
            echecs.append(dep)
            print(f"[{i:3d}/{len(deps)}] {dep:>4} : echec - {str(exc)[:60]}")
            continue
        groupes, connus, manquants = examiner(
            dep, par_dep.get(dep, []), data, args.rayon, args.min, args.max, ecartes)
        total_anneaux += len(groupes)
        total_connus += connus
        absents.extend(manquants)
        if len(deps) > 1:
            print(f"[{i:3d}/{len(deps)}] {dep:>4} : {len(data['elements']):4d} objets, "
                  f"{len(groupes):3d} anneau(x), {connus:3d} deja connu(s), "
                  f"{len(manquants):3d} absent(s)")
        else:
            print(f"-> {len(groupes)} anneau(x) exploitable(s), {connus} deja "
                  f"dans l'annuaire, {len(manquants)} absent(s)")
        if neuf and len(deps) > 1:
            time.sleep(PAUSE)

    if not args.sans_contexte:
        contexte(absents)
    for fiche in absents:
        if not args.sans_adresse:
            ville, voie, cp = adresse(fiche["lat"], fiche["lon"])
            fiche.update(commune=ville, voie=voie, cp=cp)
        if args.ortho:
            try:
                chemin, champ, annee = telecharger_ortho(args.ortho, fiche["dep"], fiche)
                court = os.path.relpath(chemin, ROOT)
                fiche.update(ortho=chemin if court.startswith("..") else court,
                             ortho_champ=champ, ortho_annee=annee)
            except (urllib.error.URLError, OSError) as exc:
                print(f"   ortho indisponible pour {fiche['osm']} : {exc}")
        afficher(fiche)

    print(f"\n{'=' * 70}")
    print(f"{total_anneaux} anneau(x) OSM sur {len(deps) - len(echecs)} departement(s) : "
          f"{total_connus} apparie(s) a l'annuaire, {len(absents)} sans correspondance")
    if ecartes:
        total = sum(len(v) for v in ecartes.values())
        print(f"\n{total} objet(s) ecarte(s) avant meme d'etre examine(s) — "
              f"c'est ici que se cache ce qui manque :")
        for motif, liste in sorted(ecartes.items(), key=lambda kv: -len(kv[1])):
            exemples = ", ".join(liste[:3]) + (" ..." if len(liste) > 3 else "")
            print(f"  {len(liste):4d}  {MOTIFS.get(motif, motif)}")
            print(f"        {exemples}")
    if echecs:
        print(f"  departements en echec : {', '.join(echecs)}")
    if args.json:
        os.makedirs(os.path.dirname(os.path.abspath(args.json)), exist_ok=True)
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(absents, f, ensure_ascii=False, indent=2)
            f.write("\n")
        print(f"-> {args.json}")
    if absents:
        print("\nAucune de ces lignes n'est une piste tant que personne ne l'a vue :\n"
              "regardez la vue aerienne, puis allez-y. CONTRIBUTING.md, section\n"
              "« Ajouter une piste absente », dit comment en faire une contribution.")


if __name__ == "__main__":
    main()
