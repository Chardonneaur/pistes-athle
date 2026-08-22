#!/usr/bin/env python3
"""Genere l'API statique et sa description OpenAPI, sous _site/api/.

Appele par build_site.py ; utilisable seul pour inspecter le resultat :

    python3 scripts/build_api.py --out _site

L'annuaire etait lisible par un agent — llms.txt, JSON-LD, tracks.json — sans
etre interrogeable : pour repondre a « une piste de 400 m en acces libre pres
de Nantes », il fallait telecharger 1,5 Mo et filtrer soi-meme. Peu d'agents le
font ; ils citent la source qui repond en un appel.

CE QU'IL FAUT SAVOIR AVANT DE LIRE LA SUITE
-------------------------------------------
Le site est publie sur GitHub Pages, qui sert des fichiers statiques et
**ignore la chaine de requete**. `/api/tracks?city=Nantes` et
`/api/tracks?city=Lyon` designent le meme fichier. Une API a parametres
combinables ne peut donc pas etre servie par cet hebergement, et pretendre le
contraire produirait des reponses fausses en silence — le pire cas pour un
agent, qui n'a aucun moyen de s'en apercevoir.

D'ou trois couches, de la plus honnete a la plus puissante :

1. **Les facettes statiques** (ici). Un fichier par critere simple :
   `/api/tracks/city/44/nantes.json`, `/api/tracks/discipline/javelin.json`.
   Elles marchent aujourd'hui, sans rien deployer.
2. **L'index compact** `/api/index.json` : les 7 135 installations reduites aux
   seuls champs sur lesquels on filtre — 1,0 Mo contre 1,5 Mo pour tracks.json,
   sans les adresses, les services, les avis ni les photos. De quoi faire
   soi-meme n'importe quelle conjonction, en un telechargement.
3. **Le worker** `api/worker.js`, a deployer sur Cloudflare (ou equivalent) :
   il lit l'index publie ici et sert `/api/tracks?...` avec les vrais
   parametres. C'est la seule couche qui delivre la combinaison arbitraire et
   la recherche par rayon.

`/api/tracks.json` est le document de capacites : il dit a l'agent lequel de
ces trois chemins est disponible, et comment s'en servir. `/api/tracks/` (page
HTML) sert le meme contenu a qui appelle l'URL nue avec une chaine de requete
que l'hebergement a jetee — un 404 n'apprendrait rien.

Deux regles de contrat viennent de la donnee, pas du confort. Elles decoulent
de docs/trouver-les-pistes-manquantes.md § 5.2 :

- `free_access=false` est **refuse** (400). 5 551 sites ont `acces_libre` a
  null : le recensement ne dit rien, ce n'est pas un « non ». Repondre par une
  liste de 5 551 sites « non accessibles » serait une affirmation inventee.
  `free_access=unknown` sert a les demander explicitement.
- Les disciplines filtrent sur `agres` (declare), jamais sur `agres_probables`
  (deduit d'une orthophoto) sans le dire. `certainty=probable|any` ouvre le
  second. `saut_indetermine` et `lancer_indetermine` ne sont pas des
  disciplines : ils disent « il y a un sautoir, on ne sait pas lequel ».

(c) Data ES, ministere charge des Sports, Licence Ouverte 2.0.
"""
import argparse
import json
import os
import re
import unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Nom de parametre cote API -> valeur du champ `agres`. Les noms anglais sont
# ceux de la specification : ce sont eux qu'un agent lira dans openapi.json.
DISCIPLINES = {
    "long_jump": "longueur", "triple_jump": "triple", "high_jump": "hauteur",
    "pole_vault": "perche", "shot_put": "poids", "discus": "disque",
    "hammer": "marteau", "javelin": "javelot", "steeplechase": "steeple",
}
# « Lyon 3e Arrondissement » : le recensement decoupe Paris, Lyon et Marseille,
# et personne ne cherche « une piste a Lyon 3e Arrondissement ».
ARRONDISSEMENT = re.compile(r"^(.+?)\s+\d+(?:er|e|eme|ème)\s+Arrondissement$", re.I)

SURFACES = ("synthetique", "bitume", "cendree", "sable", "gazon", "naturel", "interieur")
SURFACE_EN = {"synthetique": "synthetic", "bitume": "asphalt", "cendree": "cinder",
              "sable": "sand", "gazon": "grass", "naturel": "natural",
              "interieur": "indoor"}

# Une facette ne merite un fichier que si quelqu'un peut la demander. En deca,
# c'est du bruit dans le plan du site et dans l'index de l'agent.
MIN_FACETTE = 1
# Cellule de la grille geographique, en degres. 0,1 deg ~ 11 km en latitude :
# un agent qui cherche dans 20 km lit sa cellule et les huit voisines.
PAS_GRILLE = 0.1

LICENCE = "https://github.com/etalab/licence-ouverte/blob/master/LO.md"


def slug(s):
    """Segment d'URL canonique. **Ne jamais modifier sans redirection** : ces
    slugs sont des URLs publiques indexees."""
    s = unicodedata.normalize("NFD", s or "")
    s = "".join(c for c in s if unicodedata.category(c) != "Mn").lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def compact(t):
    """Un site, reduit a ce qu'on filtre et a ce qu'on affiche.

    Les cles sont abregees comme dans tracks.json — meme convention, meme
    raison : sur 7 135 lignes, les noms complets pesent plus que les valeurs.
    `keymap` du fichier index.json donne la correspondance."""
    r = {"i": t["id"], "n": t.get("nom"), "v": t.get("ville"),
         "d": t.get("dep"), "cp": t.get("cp"),
         "y": t.get("lat"), "x": t.get("lon"),
         "p": 1 if t.get("piste") else 0}
    if t.get("longueur_piste"):
        r["lp"] = t["longueur_piste"]
    if t.get("longueur_probable"):
        r["lpp"] = t["longueur_probable"]
    if t.get("couloirs"):
        r["cl"] = t["couloirs"]
    if t.get("surface"):
        r["s"] = t["surface"]
    if t.get("acces_libre"):
        r["al"] = 1                       # jamais 0 : l'absence n'est pas un non
    if t.get("agres"):
        r["g"] = sorted(t["agres"])
    if t.get("agres_probables"):
        r["gp"] = sorted(t["agres_probables"])
    if t.get("nb_avis"):
        r["nv"] = t["nb_avis"]
    if t.get("note_moyenne"):
        r["nt"] = t["note_moyenne"]
    return r


KEYMAP = {"i": "id", "n": "nom", "v": "ville", "d": "departement", "cp": "code_postal",
          "y": "latitude", "x": "longitude", "p": "piste",
          "lp": "longueur_piste_m", "lpp": "longueur_probable_m", "cl": "couloirs",
          "s": "revetement", "al": "acces_libre", "g": "agres_declares",
          "gp": "agres_probables", "nv": "nb_avis", "nt": "note_moyenne"}


def plein(t, url_base):
    """Un site en noms de champs complets, tel que le decrit openapi.json.

    L'index compact economise un tiers sur 7 135 lignes et vaut la peine d'etre
    dechiffre une fois ; une facette en rend rarement plus de cent, et un agent
    qui lit `acces_libre` sans table de correspondance se trompe moins qu'un
    agent qui lit `al`. Les champs absents sont explicitement `null` : c'est ce
    que le schema promet, et un blanc doit se voir."""
    r = {"id": t["i"], "nom": t.get("n"), "ville": t.get("v"),
         "departement": t.get("d"), "code_postal": t.get("cp"),
         "latitude": t.get("y"), "longitude": t.get("x"),
         "piste": bool(t.get("p")),
         "longueur_piste_m": t.get("lp"), "longueur_probable_m": t.get("lpp"),
         "couloirs": t.get("cl"), "revetement": t.get("s"),
         "acces_libre": True if t.get("al") else None,
         "agres_declares": t.get("g") or [],
         "agres_probables": t.get("gp") or [],
         # Ici, contrairement a `acces_libre`, l'absence *est* un fait : on sait
         # si quelqu'un a decrit ce site, parce que c'est notre propre base.
         # Zero avis se dit donc zero, et se filtre.
         "nb_avis": t.get("nv") or 0,
         "note_moyenne": t.get("nt"),
         "url": f"{url_base}/site/{t['i']}/"}
    return r


def enveloppe(query, resultats, maj, total=None):
    """Reponse commune a tous les points d'entree.

    `query` rejoue ce qui a ete compris : un agent doit pouvoir verifier qu'il
    a ete entendu avant de citer la reponse. `source` et `license` voyagent
    avec les donnees — separees d'elles, elles ne reviennent jamais."""
    return {
        "query": query,
        "count": len(resultats),
        "total": len(resultats) if total is None else total,
        "source": f"Data ES, ministere charge des Sports, Licence Ouverte 2.0 — build {maj}",
        "license": LICENCE,
        "results": resultats,
    }


def ecrire(chemin, obj):
    os.makedirs(os.path.dirname(chemin), exist_ok=True)
    with open(chemin, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))
        f.write("\n")


# --------------------------------------------------------------- les facettes
def facettes(index, deps):
    """Toutes les listes pre-calculees, par chemin relatif sous /api/tracks/.

    On part de l'index et on remplit des seaux : jamais du produit cartesien
    des vocabulaires. Une facette qui n'a aucun site n'existe pas, et c'est
    ainsi qu'on evite l'explosion combinatoire — 9 disciplines x 108
    departements font 972 combinaisons possibles et 318 non vides."""
    par = {}

    def seau(chemin, query):
        return par.setdefault(chemin, {"query": query, "ids": []})

    slugs_dep = {code: slug(v[0]) or code for code, v in deps.items() if v}
    # Homonymes de communes entre departements : Valence est dans la Drome et
    # dans le Tarn-et-Garonne. Le slug nu irait a la premiere rencontree.
    villes = {}
    for t in index:
        villes.setdefault(slug(t["v"] or ""), set()).add(t.get("d") or "00")

    for t in index:
        dep = t.get("d") or "00"
        sid = t["i"]

        seau(f"department/{dep}", {"department": dep})["ids"].append(sid)

        sv = slug(t["v"] or "")
        if sv:
            seau(f"city/{dep}/{sv}", {"city": t["v"], "department": dep})["ids"].append(sid)
        # Data ES ne connait pas Lyon, seulement « Lyon 3e Arrondissement ».
        # La facette de la commune entiere doit exister, sinon la page
        # /ville/lyon/ pointe vers une URL d'API qui n'est pas la.
        mere = ARRONDISSEMENT.match(t["v"] or "")
        if mere:
            seau(f"city/{dep}/{slug(mere.group(1))}",
                 {"city": mere.group(1), "department": dep})["ids"].append(sid)

        if t.get("lp"):
            seau(f"length/{t['lp']}", {"track_length": t["lp"]})["ids"].append(sid)
            seau(f"length/{t['lp']}/{dep}",
                 {"track_length": t["lp"], "department": dep})["ids"].append(sid)

        if t.get("cl"):
            for n in range(1, t["cl"] + 1):
                seau(f"lanes/{n}", {"lanes_min": n})["ids"].append(sid)
                seau(f"lanes/{n}/{dep}",
                     {"lanes_min": n, "department": dep})["ids"].append(sid)

        if t.get("s"):
            seau(f"surface/{SURFACE_EN[t['s']]}", {"surface": t["s"]})["ids"].append(sid)
            seau(f"surface/{SURFACE_EN[t['s']]}/{dep}",
                 {"surface": t["s"], "department": dep})["ids"].append(sid)

        if t.get("nv"):
            seau("reviewed", {"has_reviews": True})["ids"].append(sid)
            seau(f"reviewed/{dep}",
                 {"has_reviews": True, "department": dep})["ids"].append(sid)

        if t.get("al"):
            seau("free-access", {"free_access": True})["ids"].append(sid)
            seau(f"free-access/{dep}",
                 {"free_access": True, "department": dep})["ids"].append(sid)

        for param, valeur in DISCIPLINES.items():
            if valeur in (t.get("g") or []):
                seau(f"discipline/{param}", {param: True})["ids"].append(sid)
                seau(f"discipline/{param}/{dep}",
                     {param: True, "department": dep})["ids"].append(sid)

    return par, slugs_dep, villes


def grille(index):
    """Cellules de PAS_GRILLE degre contenant au moins un site."""
    cellules = {}
    for t in index:
        if t.get("y") is None:
            continue
        cle = (round(t["y"] / PAS_GRILLE) * PAS_GRILLE,
               round(t["x"] / PAS_GRILLE) * PAS_GRILLE)
        cellules.setdefault(cle, []).append(t["i"])
    return cellules


# ----------------------------------------------------------- document OpenAPI
def parametres_recherche():
    """Les parametres de GET /api/tracks, dans l'ordre ou on les explique."""
    p = [
        ("city", "string", "Commune, en clair ou en slug (`Nantes`, `nantes`). "
                           "Associer `department` pour lever les homonymes."),
        ("department", "string", "Code INSEE du departement (`44`, `2A`, `971`)."),
        ("lat", "number", "Latitude WGS84 du point de recherche. Exige `lon`."),
        ("lon", "number", "Longitude WGS84 du point de recherche. Exige `lat`."),
        ("radius", "integer", "Rayon de recherche en km autour de (`lat`, `lon`). "
                              "Defaut 10, maximum 100. Sans `lat`/`lon`, ignore."),
        ("track_length", "string", "Developpement de l'anneau en metres : valeur exacte "
                                   "(`400`) ou intervalle (`300-400`). Alias : `length`. "
                                   "Ne porte que sur les 2 255 sites dont le ministere "
                                   "declare la longueur, jamais sur les estimations."),
        ("lanes_min", "integer", "Nombre minimal de couloirs. Attention : `couloirs` "
                                 "n'est renseigne que sur 112 sites sur 7 135 ; ce filtre "
                                 "exclut de fait tous les autres."),
        ("surface", "string", "Revetement : " + ", ".join(f"`{SURFACE_EN[s]}`" for s in SURFACES) + "."),
        ("free_access", "string", "`true` : les sites declares en acces libre. "
                                  "`unknown` : ceux dont l'acces n'est pas renseigne. "
                                  "`false` est **refuse** (400) — un blanc n'est pas un "
                                  "non, et repondre par une liste serait inventer."),
        ("has_reviews", "boolean", "`true` : les installations qu'au moins un contributeur "
                                   "a decrites. `false` : celles que personne n'a encore "
                                   "vues — 7 130 sur 7 135. Contrairement a `free_access`, "
                                   "le `false` est ici legitime : l'absence d'avis est un "
                                   "fait de notre propre base, pas un silence du "
                                   "recensement."),
        ("certainty", "string", "`declared` (defaut) : les disciplines filtrent sur les "
                                "agres declares. `probable` : sur les agres deduits d'une "
                                "orthophoto. `any` : les deux."),
    ]
    p += [(nom, "boolean", f"Presence d'un agres « {val} ».")
          for nom, val in DISCIPLINES.items()]
    p += [
        ("limit", "integer", "Nombre de resultats par page. Defaut 50, maximum 500."),
        ("page", "integer", "Page de resultats, a partir de 1."),
    ]
    return p


def openapi(url_base, api_url, index, maj):
    """Description machine de l'API, generee — jamais ecrite a la main.

    Les vocabulaires (departements, longueurs, revetements) sortent du jeu de
    donnees et changent au rebuild mensuel : une copie manuelle divergerait au
    premier passage du cron."""
    def param(nom, typ, desc, exemple=None):
        s = {"type": typ}
        if typ == "boolean" and nom != "has_reviews":
            # Une discipline se demande avec true : « sans cet agres » n'existe
            # pas, une fiche muette n'affirmant pas l'absence. `has_reviews`
            # est le seul booleen ou le faux veut dire quelque chose.
            s["enum"] = [True]
        d = {"name": nom, "in": "query", "required": False,
             "description": desc, "schema": s}
        if exemple is not None:
            d["example"] = exemple
        return d

    exemples = {"city": "Nantes", "department": "44", "lat": 47.21, "lon": -1.55,
                "radius": 20, "track_length": "400", "lanes_min": 6,
                "surface": "synthetic", "free_access": "true", "javelin": True}

    piste = {
        "type": "object",
        "required": ["id", "nom", "ville", "latitude", "longitude", "url"],
        "properties": {
            "id": {"type": "string", "description": "Identifiant national de l'installation.",
                   "example": "I505020004"},
            "nom": {"type": "string"},
            "ville": {"type": "string"},
            "departement": {"type": "string"},
            "code_postal": {"type": "string"},
            "latitude": {"type": "number"}, "longitude": {"type": "number"},
            "distance_km": {"type": ["number", "null"],
                            "description": "Renseigne seulement si la requete portait "
                                           "`lat`/`lon`."},
            "piste": {"type": "boolean"},
            "longueur_piste_m": {"type": ["integer", "null"],
                                 "description": "Developpement declare par le ministere."},
            "longueur_probable_m": {"type": ["integer", "null"],
                                    "description": "Estimation deduite d'OpenStreetMap, "
                                                   "jamais mesuree. A ne pas confondre avec "
                                                   "`longueur_piste_m`."},
            "couloirs": {"type": ["integer", "null"]},
            "revetement": {"type": ["string", "null"], "enum": list(SURFACES) + [None]},
            "acces_libre": {"type": ["boolean", "null"],
                            "description": "`true` si declare en acces libre, `null` si le "
                                           "recensement ne dit rien. **Jamais `false`** : "
                                           "l'absence d'information n'est pas un refus."},
            "agres_declares": {"type": "array", "items": {"type": "string",
                               "enum": sorted(DISCIPLINES.values())}},
            "agres_probables": {"type": "array", "items": {"type": "string"},
                                "description": "Deduits d'une orthophoto par un contributeur. "
                                               "`saut_indetermine` / `lancer_indetermine` "
                                               "signalent un agres dont la discipline est "
                                               "inconnue."},
            "nb_avis": {"type": "integer",
                        "description": "Nombre d'avis rediges par des contributeurs. "
                                       "Zero est un fait, pas un blanc : la base sait si "
                                       "quelqu'un a decrit ce site."},
            "note_moyenne": {"type": ["number", "null"],
                             "description": "Moyenne des notes, si au moins un avis en porte une."},
            "url": {"type": "string", "format": "uri",
                    "description": "Fiche HTML de l'installation, avec son JSON-LD."},
        },
    }
    reponse = {
        "type": "object",
        "required": ["query", "count", "total", "source", "license", "results"],
        "properties": {
            "query": {"type": "object", "description": "Les parametres compris, rejoues."},
            "count": {"type": "integer", "description": "Resultats dans cette page."},
            "total": {"type": "integer", "description": "Resultats pour la requete entiere."},
            "source": {"type": "string"},
            "license": {"type": "string", "format": "uri"},
            "results": {"type": "array", "items": {"$ref": "#/components/schemas/Track"}},
        },
    }

    deps = sorted({t["d"] for t in index if t.get("d")})
    longueurs = sorted({t["lp"] for t in index if t.get("lp")})

    chemins = {
        "/api/tracks": {
            "get": {
                "operationId": "searchTracks",
                "summary": "Rechercher des installations d'athletisme",
                "description":
                    "Tous les parametres se combinent en conjonction (ET).\n\n"
                    "**Disponible uniquement sur le serveur de recherche** (voir `servers`). "
                    "Sur le miroir statique GitHub Pages, la chaine de requete est ignoree "
                    "par l'hebergeur : cette URL y renvoie le document de capacites "
                    "`/api/tracks.json`, qui indique quoi appeler a la place.",
                "parameters": [param(n, t, d, exemples.get(n)) for n, t, d in parametres_recherche()],
                "responses": {
                    "200": {"description": "Liste des installations correspondantes.",
                            "content": {"application/json": {
                                "schema": {"$ref": "#/components/schemas/SearchResponse"}}}},
                    "400": {"description": "Parametre invalide. `free_access=false` tombe "
                                           "toujours ici, par choix de contrat.",
                            "content": {"application/json": {"schema": {
                                "type": "object",
                                "properties": {"error": {"type": "string"},
                                               "parameter": {"type": "string"},
                                               "hint": {"type": "string"}}}}}},
                },
            }
        },
        "/api/tracks.json": {
            "get": {
                "operationId": "getCapabilities",
                "summary": "Document de capacites : ce que cet hote sait faire",
                "description": "Toujours disponible, y compris sur l'hebergement statique. "
                               "Dit si la recherche par parametres est servie ici, et liste "
                               "les points d'entree statiques a defaut.",
                "responses": {"200": {"description": "Document de capacites.",
                                      "content": {"application/json": {"schema": {"type": "object"}}}}},
            }
        },
        "/api/index.json": {
            "get": {
                "operationId": "getIndex",
                "summary": "Index compact des 7 135 installations, en un fichier",
                "description": "1,0 Mo contre 1,5 Mo pour `data/tracks.json` : "
                               "uniquement les champs sur lesquels on filtre. Permet a un "
                               "agent de faire lui-meme n'importe quelle conjonction, sans "
                               "serveur de recherche. Les cles sont abregees ; `keymap` "
                               "donne la correspondance.",
                "responses": {"200": {"description": "Index complet.",
                                      "content": {"application/json": {"schema": {"type": "object"}}}}},
            }
        },
        "/api/tracks/{id}.json": {
            "get": {
                "operationId": "getTrack",
                "summary": "Une installation par son identifiant national",
                "parameters": [{"name": "id", "in": "path", "required": True,
                                "schema": {"type": "string"}, "example": "I505020004"}],
                "responses": {"200": {"description": "L'installation.",
                                      "content": {"application/json": {"schema": {
                                          "$ref": "#/components/schemas/Track"}}}},
                              "404": {"description": "Identifiant inconnu."}},
            }
        },
    }

    # Les facettes statiques : memes reponses, sans chaine de requete.
    statiques = [
        ("/api/tracks/department/{code}.json", "listByDepartment",
         "Installations d'un departement", "code", "Code INSEE", "44", deps),
        ("/api/tracks/city/{department}/{city}.json", "listByCity",
         "Installations d'une commune", "city", "Slug de la commune", "nantes", None),
        ("/api/tracks/discipline/{discipline}.json", "listByDiscipline",
         "Installations declarant une discipline", "discipline",
         "Nom de parametre de la discipline", "javelin", sorted(DISCIPLINES)),
        ("/api/tracks/discipline/{discipline}/{department}.json", "listByDisciplineAndDepartment",
         "Croisement discipline x departement", "discipline",
         "Nom de parametre de la discipline", "pole_vault", sorted(DISCIPLINES)),
        ("/api/tracks/length/{metres}.json", "listByLength",
         "Installations d'un developpement donne", "metres", "Developpement en metres",
         "400", [str(v) for v in longueurs]),
        ("/api/tracks/surface/{surface}.json", "listBySurface",
         "Installations d'un revetement", "surface", "Revetement", "synthetic",
         [SURFACE_EN[s] for s in SURFACES]),
        ("/api/tracks/lanes/{n}.json", "listByLanes",
         "Installations d'au moins N couloirs", "n", "Nombre minimal de couloirs", "6", None),
        ("/api/tracks/lanes/{n}/{department}.json", "listByLanesAndDepartment",
         "Croisement couloirs x departement", "n", "Nombre minimal de couloirs", "6", None),
        ("/api/tracks/free-access.json", "listFreeAccess",
         "Installations declarees en acces libre", None, None, None, None),
        ("/api/tracks/reviewed.json", "listReviewed",
         "Installations decrites par un contributeur", None, None, None, None),
        ("/api/geo/{lat}/{lon}.json", "listByCell",
         "Cellule geographique de 0,1 degre", "lat",
         f"Latitude arrondie au pas de {PAS_GRILLE}", "47.2", None),
    ]
    for chemin, opid, resume, nom_p, desc_p, ex, enum in statiques:
        params = []
        for seg in re.findall(r"\{(\w+)\}", chemin):
            s = {"type": "string"}
            if seg == nom_p and enum:
                s["enum"] = enum
            params.append({"name": seg, "in": "path", "required": True, "schema": s,
                           "description": desc_p if seg == nom_p else None,
                           "example": ex if seg == nom_p else None})
        for p in params:
            for k in ("description", "example"):
                if p[k] is None:
                    del p[k]
        chemins[chemin] = {"get": {
            "operationId": opid, "summary": resume,
            "description": "Facette pre-calculee, servie par l'hebergement statique. "
                           "N'existe que si elle contient au moins un resultat.",
            "parameters": params,
            "responses": {"200": {"description": resume,
                                  "content": {"application/json": {"schema": {
                                      "$ref": "#/components/schemas/SearchResponse"}}}},
                          "404": {"description": "Aucune installation pour cette facette."}},
        }}

    serveurs = [{"url": api_url or url_base,
                 "description": "Serveur de recherche : parametres de requete actifs."
                                if api_url else
                                "Miroir statique GitHub Pages : facettes seulement, la "
                                "chaine de requete y est ignoree."}]
    if api_url:
        serveurs.append({"url": url_base,
                         "description": "Miroir statique : facettes et index compact."})

    return {
        "openapi": "3.1.0",
        "info": {
            "title": "Ou s'entrainer ? — API des pistes d'athletisme francaises",
            "version": maj,
            "summary": "Recherche dans les 7 135 installations d'athletisme recensees en France.",
            "description":
                "Annuaire libre des installations d'athletisme francaises : revetement, "
                "developpement, couloirs, agres, conditions d'acces, coordonnees.\n\n"
                "**Deux regles de contrat a connaitre avant d'interpreter une reponse.**\n\n"
                "1. `acces_libre` vaut `true` ou `null`, jamais `false`. 5 551 des 7 135 "
                "installations n'ont pas d'information d'acces ; un blanc n'est pas un "
                "refus. C'est pourquoi `free_access=false` renvoie une 400.\n"
                "2. `agres_declares` vient de l'exploitant ; `agres_probables` est deduit "
                "d'une orthophoto par un contributeur. Les filtres de discipline portent "
                "sur le premier, sauf `certainty=probable|any`.\n\n"
                "Les donnees sont declaratives : ce qu'une commune ne declare pas n'y "
                "figure pas. Verifiez les conditions d'acces avant de vous deplacer.",
            "license": {"name": "Licence Ouverte 2.0", "url": LICENCE},
            "contact": {"url": f"{url_base}/"},
        },
        "servers": serveurs,
        "externalDocs": {"url": f"{url_base}/llms.txt",
                         "description": "Orientation generale du corpus (convention llms.txt)."},
        "paths": chemins,
        "components": {"schemas": {"Track": piste, "SearchResponse": reponse}},
    }


def capacites(url_base, api_url, maj, nb, facettes_dispo):
    """Ce que l'hote sait faire, en JSON, pour l'agent qui frappe a la porte.

    C'est la reponse a `/api/tracks?city=Nantes` sur l'hebergement statique.
    Elle ne pretend pas avoir filtre : elle dit pourquoi elle n'a pas pu, et
    quelle URL appeler a la place. Un agent qui recoit une liste fausse la
    cite ; un agent qui recoit ceci recommence correctement."""
    return {
        "service": "Ou s'entrainer ? — API des pistes d'athletisme francaises",
        "openapi": f"{url_base}/openapi.json",
        "documentation": f"{url_base}/llms.txt",
        "license": LICENCE,
        "build": maj,
        "count": nb,
        "query_api": {
            "available": bool(api_url),
            "endpoint": f"{api_url}/api/tracks" if api_url else None,
            "note": None if api_url else
                    "Cet hote est un site statique (GitHub Pages) : la chaine de requete "
                    "est ignoree par l'hebergeur, donc /api/tracks?city=Nantes ne peut pas "
                    "filtrer. Utilisez les facettes ci-dessous, ou telechargez index_url "
                    "et filtrez localement.",
            "parameters": [n for n, _, _ in parametres_recherche()],
        },
        "index_url": f"{url_base}/api/index.json",
        "endpoints": {
            "track": f"{url_base}/api/tracks/{{id}}.json",
            "department": f"{url_base}/api/tracks/department/{{code}}.json",
            "city": f"{url_base}/api/tracks/city/{{department}}/{{city-slug}}.json",
            "discipline": f"{url_base}/api/tracks/discipline/{{discipline}}.json",
            "discipline_in_department":
                f"{url_base}/api/tracks/discipline/{{discipline}}/{{department}}.json",
            "length": f"{url_base}/api/tracks/length/{{metres}}.json",
            "surface": f"{url_base}/api/tracks/surface/{{surface}}.json",
            "lanes_min": f"{url_base}/api/tracks/lanes/{{n}}.json",
            "free_access": f"{url_base}/api/tracks/free-access.json",
            "reviewed": f"{url_base}/api/tracks/reviewed.json",
            "geo_cell": f"{url_base}/api/geo/{{lat}}/{{lon}}.json",
        },
        "vocabularies": {
            "disciplines": sorted(DISCIPLINES),
            "surfaces": [SURFACE_EN[s] for s in SURFACES],
        },
        "contract": {
            "free_access": "true | unknown. `false` est refuse : 5 551 installations n'ont "
                           "pas d'information d'acces, et un blanc n'est pas un non.",
            "disciplines": "Filtrent sur les agres declares. Les agres deduits d'une "
                           "orthophoto sont rendus a part, dans agres_probables.",
            "has_reviews": "true | false. Le false est ici legitime, contrairement a "
                           "free_access : l'absence d'avis est un fait de cette base. "
                           "Sur cet hote statique, les 7 130 installations sans avis se "
                           "obtiennent en retirant reviewed.json de index.json.",
        },
        "facets_generated": facettes_dispo,
    }


PAGE_HTML = """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>API — Où s'entraîner ?</title>
<meta name="description" content="Interroger l'annuaire des pistes d'athlétisme françaises : facettes statiques, index compact, OpenAPI.">
<meta name="robots" content="index,follow">
<link rel="canonical" href="{url_base}/api/tracks/">
<link rel="service-desc" type="application/json" href="{url_base}/openapi.json">
<link rel="stylesheet" href="../../assets/page.css?v=10">
<script type="application/json" id="capabilities">{capacites}</script>
</head>
<body>
<header class="page-bar"><a class="home" href="../../">Où s'entraîner ?</a></header>
<main class="wrap">
<h1>API des pistes d'athlétisme</h1>
<p>Vous êtes probablement arrivé ici en appelant <code>/api/tracks?…</code>. Ce site est
hébergé sur GitHub&nbsp;Pages, qui sert des fichiers statiques et <strong>ignore la chaîne de
requête</strong> : les paramètres n'ont pas pu être appliqués, et cette page ne prétend pas
avoir filtré quoi que ce soit.</p>
<p>Le document de capacités lisible par une machine est ci-dessus dans
<code>&lt;script id="capabilities"&gt;</code>, et à part&nbsp;:
<a href="../tracks.json">/api/tracks.json</a>.</p>
<h2>Trois façons d'interroger l'annuaire</h2>
<ul class="liste">
<li><a href="../index.json">/api/index.json</a><span class="meta">Les {nb} installations
réduites aux champs filtrables, en un fichier. Téléchargez, filtrez localement : n'importe
quelle conjonction, sans serveur.</span></li>
<li><a href="../tracks/free-access.json">Facettes pré-calculées</a><span class="meta">Un
fichier par critère simple : département, commune, discipline, développement, revêtement,
couloirs, accès libre, cellule géographique.</span></li>
<li><a href="../../openapi.json">/openapi.json</a><span class="meta">Le contrat complet, y
compris les paramètres de recherche combinables servis par le serveur de recherche lorsqu'il
est déployé.</span></li>
</ul>
<h2>Deux règles à connaître avant d'interpréter une réponse</h2>
<p><code>acces_libre</code> vaut <code>true</code> ou <code>null</code>, jamais
<code>false</code> : {sans_acces} installations sur {nb} n'ont aucune information d'accès, et
un blanc n'est pas un refus.</p>
<p>Les disciplines filtrent sur les agrès <em>déclarés</em> par l'exploitant. Ce qu'un
contributeur a déduit d'une orthophoto est rendu à part, dans <code>agres_probables</code> —
et <code>saut_indetermine</code> signifie « il y a un sautoir, on ne sait pas lequel ».</p>
</main>
<footer class="wrap src"><p><a href="../../">Voir la carte</a> ·
<a href="../../llms.txt">llms.txt</a> ·
<a href="https://github.com/{depot}">Code source</a></p></footer>
</body>
</html>
"""


def construire(out, sites, deps, url_base, maj, depot, api_url=None):
    """Ecrit tout /api sous `out`. Retourne la liste des chemins publies."""
    index = [compact(t) for t in sites
             if t.get("lat") is not None and t.get("lon") is not None]
    par_id = {t["i"]: t for t in index}
    api = os.path.join(out, "api")

    # --- index compact : le fichier qui rend l'agent autonome
    ecrire(os.path.join(api, "index.json"), {
        "generated": maj, "count": len(index),
        "source": "Data ES, ministere charge des Sports, Licence Ouverte 2.0",
        "license": LICENCE,
        "keymap": KEYMAP,
        "url_pattern": f"{url_base}/site/{{id}}/",
        "note": "acces_libre (al) vaut 1 ou est absent : l'absence n'est pas un non. "
                "agres_declares (g) vient de l'exploitant, agres_probables (gp) d'une "
                "lecture d'orthophoto. L'URL de chaque fiche se deduit de son id par "
                "url_pattern ; la repeter sur 7 135 lignes pesait 430 Ko.",
        "tracks": index,
    })

    # --- une fiche par installation
    for t in index:
        ecrire(os.path.join(api, "tracks", f"{t['i']}.json"),
               enveloppe({"id": t["i"]}, [plein(t, url_base)], maj))

    # --- les facettes
    par, slugs_dep, _villes = facettes(index, deps)
    publies = []
    for chemin, seau in par.items():
        ids = seau["ids"]
        if len(ids) < MIN_FACETTE:
            continue
        resultats = sorted((par_id[i] for i in ids),
                           key=lambda t: ((t.get("v") or "").lower(), (t.get("n") or "").lower()))
        ecrire(os.path.join(api, "tracks", chemin + ".json"),
               enveloppe(seau["query"], [plein(t, url_base) for t in resultats], maj))
        publies.append(chemin)

    # --- la grille geographique
    cellules = grille(index)
    for (lat, lon), ids in cellules.items():
        resultats = [plein(par_id[i], url_base) for i in ids]
        voisines = [f"{url_base}/api/geo/{lat + dy * PAS_GRILLE:.1f}/{lon + dx * PAS_GRILLE:.1f}.json"
                    for dy in (-1, 0, 1) for dx in (-1, 0, 1)
                    if (dy or dx) and (round((lat + dy * PAS_GRILLE) / PAS_GRILLE) * PAS_GRILLE,
                                       round((lon + dx * PAS_GRILLE) / PAS_GRILLE) * PAS_GRILLE) in cellules]
        env = enveloppe({"cell": [round(lat, 1), round(lon, 1)], "step_deg": PAS_GRILLE},
                        resultats, maj)
        env["neighbours"] = voisines
        env["note"] = ("Une cellule de 0,1 degre mesure environ 11 km du nord au sud. "
                       "Pour un rayon plus large, lisez aussi les cellules voisines.")
        ecrire(os.path.join(api, "geo", f"{lat:.1f}", f"{lon:.1f}.json"), env)

    # --- capacites, en JSON et en HTML
    sans_acces = sum(1 for t in index if not t.get("al"))
    cap = capacites(url_base, api_url, maj, len(index), len(publies))
    ecrire(os.path.join(api, "tracks.json"), cap)
    chemin_html = os.path.join(api, "tracks", "index.html")
    os.makedirs(os.path.dirname(chemin_html), exist_ok=True)
    with open(chemin_html, "w", encoding="utf-8") as f:
        f.write(PAGE_HTML.format(
            url_base=url_base, depot=depot, nb=f"{len(index):,}".replace(",", " "),
            sans_acces=f"{sans_acces:,}".replace(",", " "),
            capacites=json.dumps(cap, ensure_ascii=False).replace("</", "<\\/")))

    # --- le contrat
    ecrire(os.path.join(out, "openapi.json"), openapi(url_base, api_url, index, maj))

    return {"facettes": len(publies), "cellules": len(cellules), "sites": len(index),
            "slugs_dep": slugs_dep}


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=os.path.join(ROOT, "_site"))
    ap.add_argument("--url", help="URL publique du site")
    ap.add_argument("--api-url", help="URL du serveur de recherche, s'il est deploye")
    args = ap.parse_args()

    import build_site
    url_base = build_site.url_du_site(args.url)
    brut, sites, deps = build_site.charger()
    maj = brut.get("generated")
    stat = construire(os.path.abspath(args.out), sites, deps, url_base, maj,
                      os.environ.get("GITHUB_REPOSITORY") or "Chardonneaur/pistes-athle",
                      args.api_url or os.environ.get("API_URL"))
    print(f"-> {stat['sites']} fiches, {stat['facettes']} facettes, "
          f"{stat['cellules']} cellules geo, openapi.json")


if __name__ == "__main__":
    main()
