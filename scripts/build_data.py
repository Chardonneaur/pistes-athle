#!/usr/bin/env python3
"""
Construit data/tracks.json a partir du Recensement des Equipements Sportifs (RES)
du Ministere des Sports (Data ES), puis applique les contributions de la
communaute stockees dans data/overrides/*.json.

Source : https://equipements.sports.gouv.fr/  (Licence Ouverte 2.0)
Usage  : python3 scripts/build_data.py [--offline]
"""

import argparse
import json
import os
import re
import subprocess
import sys
import unicodedata
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from functools import lru_cache

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_CACHE = os.path.join(ROOT, "data", ".res_raw.json")
OUT = os.path.join(ROOT, "data", "tracks.json")
OVERRIDES_DIR = os.path.join(ROOT, "data", "overrides")

API = "https://equipements.sports.gouv.fr/api/explore/v2.1/catalog/datasets/data-es/exports/json"

FIELDS = [
    "inst_numero", "inst_nom", "inst_adresse", "inst_cp", "new_name", "new_code",
    "dep_code", "dep_nom", "reg_nom", "inst_uai",
    "equip_numero", "equip_nom", "equip_type_name", "equip_coordonnees",
    "equip_sol", "equip_nature", "equip_piste_nb", "equip_piste_long",
    "equip_eclair", "equip_acc_libre", "equip_ouv_public_bool",
    "equip_douche", "equip_vest_sport", "equip_sanit", "equip_trib_nb",
    "equip_url", "equip_service_date", "equip_travaux_date",
    "equip_prop_type", "equip_gest_type",
]

# --- normalisation des surfaces -------------------------------------------
SURFACES = {
    "synthetique (hors gazon)": "synthetique",
    "synthetique": "synthetique",
    "tartan": "synthetique",
    "bitume": "bitume",
    "beton": "bitume",
    "stabilise/cendree": "cendree",
    "stabilise / cendre": "cendree",
    "terre battue": "cendree",
    "sable": "sable",
    "gazon naturel": "gazon",
    "gazon synthetique": "gazon",
    "surface naturelle": "naturel",
    "parquet": "interieur",
    "carrelage": "interieur",
    "dalles en polypropylene": "interieur",
    "sciure/copeaux": "naturel",
}

# --- detection des agres a partir du libelle libre -------------------------
# ordre important : "triple saut" avant "saut"
DISCIPLINE_PATTERNS = [
    ("triple", r"triple[- ]?saut|triplesaut"),
    ("perche", r"\bperche"),
    ("hauteur", r"\bhauteur"),
    ("longueur", r"longueur|longeur"),
    ("poids", r"\bpoids\b"),
    ("disque", r"\bdisque"),
    ("marteau", r"\bmarteau"),
    ("javelot", r"\bjavelot"),
    ("steeple", r"steeple"),
]

JUMP_DISCIPLINES = {"longueur", "hauteur", "perche", "triple"}
THROW_DISCIPLINES = {"poids", "disque", "marteau", "javelot"}

TRACK_TYPES = {"Stade d’athlétisme", "Stade d'athlétisme",
               "Piste d'athlétisme isolée", "Piste d'athlétisme 2 à 4 couloirs"}


# --- normalisation typographique des libelles ------------------------------
SMALL_WORDS = {"de", "du", "des", "d", "le", "la", "les", "l", "et", "a", "au",
               "aux", "en", "sur", "sous", "par", "pour", "lez", "les-"}


def smart_title(s):
    """Les fiches ministerielles melangent MAJUSCULES et casse normale.
    On retypographie uniquement les libelles integralement en majuscules."""
    if not s:
        return s
    letters = [c for c in s if c.isalpha()]
    if not letters or sum(1 for c in letters if c.isupper()) / len(letters) < 0.8:
        return s.strip()
    out = []
    for i, word in enumerate(s.lower().split()):
        parts = re.split(r"([-'\u2019])", word)
        rebuilt = []
        for j, part in enumerate(parts):
            if part in "-'\u2019":
                rebuilt.append(part)
            elif i > 0 and j == 0 and part in SMALL_WORDS:
                rebuilt.append(part)
            else:
                rebuilt.append(part.capitalize())
        out.append("".join(rebuilt))
    return " ".join(out).strip()


def deaccent(s):
    if not s:
        return ""
    return "".join(c for c in unicodedata.normalize("NFD", s)
                   if unicodedata.category(c) != "Mn").lower()


def as_bool(v):
    if v is None:
        return None
    if isinstance(v, bool):
        return v
    return str(v).strip().lower() in ("true", "1", "oui")


def as_int(v):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None



# --------------------------------------------------------- millesime des orthos
IGN_WMS = "https://data.geopf.fr/wms-r/wms"


def annee_ortho(lat, lon, timeout=20):
    """Annee de prise de vue de l'orthophoto IGN a ce point, ou None.

    La Licence Ouverte 2.0 demande de citer la source ET la date de derniere
    mise a jour de l'information reutilisee : c'est cette date-la.
    """
    d = 0.0009
    params = {
        "SERVICE": "WMS", "VERSION": "1.3.0", "REQUEST": "GetFeatureInfo",
        "LAYERS": "HR.ORTHOIMAGERY.ORTHOPHOTOS",
        "QUERY_LAYERS": "HR.ORTHOIMAGERY.ORTHOPHOTOS", "STYLES": "",
        "CRS": "EPSG:4326", "BBOX": f"{lat-d},{lon-d},{lat+d},{lon+d}",
        "WIDTH": "101", "HEIGHT": "101", "I": "50", "J": "50",
        "FORMAT": "image/jpeg", "INFO_FORMAT": "application/json",
    }
    url = IGN_WMS + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "pistes-athle/1.0 (+github pages)"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        feats = json.load(r).get("features") or []
    for f in feats:
        pva = (f.get("properties") or {}).get("pva")
        if isinstance(pva, int):
            return pva
    return None


def millesimes(tracks, deps):
    """Complete deps avec l'annee de l'ortho, par sondage d'un departement.

    La BD ORTHO est volee par departement : l'annee y est constante, seule la
    date exacte du vol change d'un chantier a l'autre. Trois sondages suffisent
    a s'en assurer, la ou interroger les 7 000 sites prendrait une demi-heure.

    Le service IGN n'est pas indispensable a la construction : s'il ne repond
    pas, on s'en passe et la legende reste generique.
    """
    par_dep = {}
    for t in tracks:
        d = t.get("d")
        if d and t.get("y") is not None and len(par_dep.setdefault(d, [])) < 3:
            par_dep[d].append((t["y"], t["x"]))

    def sonde(args):
        code, points = args
        annees = set()
        for lat, lon in points:
            try:
                a = annee_ortho(lat, lon)
            except Exception:
                a = None
            if a:
                annees.add(a)
        return code, annees

    # En serie, 300 sondages prennent cinq minutes : trop pour une construction
    # qui tourne a chaque poussee. Huit requetes concurrentes restent tres en
    # deca des 40 par seconde et par IP autorisees par la Geoplateforme.
    trouves = divergents = 0
    with ThreadPoolExecutor(max_workers=8) as pool:
        for code, annees in pool.map(sonde, sorted(par_dep.items())):
            if len(annees) == 1 and code in deps:
                deps[code].append(annees.pop())
                trouves += 1
            elif len(annees) > 1:
                divergents += 1       # chantiers a cheval : on prefere ne rien dire
    print(f"-> millesimes ortho IGN : {trouves} departement(s)"
          + (f", {divergents} non homogene(s)" if divergents else ""))
    return deps


def app_version():
    """Lit APP_VERSION dans assets/app.js : une seule source de verite.
    La valeur voyage dans tracks.json pour qu'un navigateur executant une
    version perimee puisse le detecter et purger son cache."""
    js = os.path.join(ROOT, "assets", "app.js")
    with open(js, encoding="utf-8") as f:
        m = re.search(r"const APP_VERSION = '([^']+)'", f.read())
    if not m:
        raise SystemExit("[ERREUR] APP_VERSION introuvable dans assets/app.js")
    return m.group(1)


def fetch_raw(offline=False):
    if offline and os.path.exists(RAW_CACHE):
        print("-> lecture du cache local", RAW_CACHE)
        with open(RAW_CACHE, encoding="utf-8") as f:
            return json.load(f)
    params = {
        "where": 'equip_type_famille="Equipement d\'athlétisme"',
        "select": ",".join(FIELDS),
    }
    url = API + "?" + urllib.parse.urlencode(params)
    print("-> telechargement Data ES ...")
    req = urllib.request.Request(url, headers={"User-Agent": "pistes-athle/1.0 (+github pages)"})
    with urllib.request.urlopen(req, timeout=180) as r:
        data = json.load(r)
    print(f"   {len(data)} equipements d'athletisme recus")
    os.makedirs(os.path.dirname(RAW_CACHE), exist_ok=True)
    with open(RAW_CACHE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    return data


def detect_disciplines(label, type_name):
    """Retourne (set de disciplines certaines, set de disciplines probables)."""
    txt = deaccent(label or "") + " " + deaccent(type_name or "")
    found = {name for name, pat in DISCIPLINE_PATTERNS if re.search(pat, txt)}
    if found:
        return found, set()
    # aire generique : on sait qu'il y a un sautoir / une aire de lancer,
    # mais pas laquelle -> "probable"
    if "saut" in txt or "sautoir" in txt:
        return set(), {"saut_indetermine"}
    if "lancer" in txt:
        return set(), {"lancer_indetermine"}
    return set(), set()


def aggregate(raw):
    installations = {}

    for e in raw:
        inst_id = e.get("inst_numero")
        if not inst_id:
            continue
        coords = e.get("equip_coordonnees") or {}
        lat, lon = coords.get("lat"), coords.get("lon")

        inst = installations.get(inst_id)
        if inst is None:
            inst = installations[inst_id] = {
                "id": inst_id,
                "nom": smart_title(e.get("inst_nom")),
                "adresse": smart_title(e.get("inst_adresse")),
                "cp": e.get("inst_cp"),
                "ville": smart_title(e.get("new_name")),
                "insee": e.get("new_code"),
                "dep": e.get("dep_code"),
                "dep_nom": e.get("dep_nom"),
                "region": e.get("reg_nom"),
                "scolaire": bool(e.get("inst_uai")),
                "lat": lat, "lon": lon,
                "piste": False,
                "couloirs": None,
                "longueur_piste": None,
                "longueur_probable": None,
                "surface": None,
                "couvert": False,
                "eclairage": False,
                "acces_libre": False,
                "ouvert_public": False,
                "vestiaires": False,
                "douches": False,
                "sanitaires": False,
                "tribunes": None,
                "agres": set(),
                "agres_probables": set(),
                "nb_sautoirs": 0,
                "nb_aires_lancer": 0,
                "annee": None,
                "renovation": None,
                "url": None,
                "photos": [],
                "avis": [],
                "proprietaire": e.get("equip_prop_type"),
                "gestionnaire": e.get("equip_gest_type"),
                "equipements": [],
                "source": "res",
            }

        type_name = e.get("equip_type_name") or ""
        label = e.get("equip_nom") or ""
        is_track = type_name in TRACK_TYPES

        # coordonnees : on privilegie celles de la piste
        if lat and lon and (inst["lat"] is None or is_track):
            inst["lat"], inst["lon"] = lat, lon

        if is_track:
            inst["piste"] = True
            couloirs = as_int(e.get("equip_piste_nb"))
            if couloirs and (inst["couloirs"] is None or couloirs > inst["couloirs"]):
                inst["couloirs"] = couloirs
            lg = as_int(e.get("equip_piste_long"))
            if lg and (inst["longueur_piste"] is None or lg > inst["longueur_piste"]):
                inst["longueur_piste"] = lg
            sol = SURFACES.get(deaccent(e.get("equip_sol")), None)
            if sol and (inst["surface"] is None or sol == "synthetique"):
                inst["surface"] = sol
            if (e.get("equip_nature") or "") in ("Intérieur", "Extérieur couvert", "Découvrable"):
                inst["couvert"] = True

        sure, maybe = detect_disciplines(label, type_name)
        inst["agres"] |= sure
        inst["agres_probables"] |= maybe
        if "saut" in deaccent(type_name) or sure & JUMP_DISCIPLINES:
            inst["nb_sautoirs"] += 1
        if "lancer" in deaccent(type_name) or sure & THROW_DISCIPLINES:
            inst["nb_aires_lancer"] += 1

        for src, dst in (("equip_eclair", "eclairage"), ("equip_acc_libre", "acces_libre"),
                         ("equip_ouv_public_bool", "ouvert_public"),
                         ("equip_douche", "douches"), ("equip_sanit", "sanitaires")):
            if as_bool(e.get(src)):
                inst[dst] = True
        if as_int(e.get("equip_vest_sport")):
            inst["vestiaires"] = True
        trib = as_int(e.get("equip_trib_nb"))
        if trib and (inst["tribunes"] is None or trib > inst["tribunes"]):
            inst["tribunes"] = trib
        an = as_int(e.get("equip_service_date"))
        if an and (inst["annee"] is None or an < inst["annee"]):
            inst["annee"] = an
        rn = as_int(e.get("equip_travaux_date"))
        if rn and (inst["renovation"] is None or rn > inst["renovation"]):
            inst["renovation"] = rn
        if e.get("equip_url") and not inst["url"]:
            u = e["equip_url"].strip()
            inst["url"] = u if u.startswith("http") else "https://" + u
        inst["equipements"].append({"type": type_name, "nom": label})

    return installations


def load_overrides():
    """Charge data/overrides/*.json (corrections + ajouts communautaires)."""
    items = []
    if not os.path.isdir(OVERRIDES_DIR):
        return items
    for fn in sorted(os.listdir(OVERRIDES_DIR)):
        if not fn.endswith(".json") or fn.startswith("_"):
            continue
        path = os.path.join(OVERRIDES_DIR, fn)
        with open(path, encoding="utf-8") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError as exc:
                raise SystemExit(f"[ERREUR] {fn} : JSON invalide -> {exc}")
        if isinstance(data, list):
            items.extend(data)
        else:
            items.append(data)
    print(f"-> {len(items)} contribution(s) communautaire(s)")
    return items


LIST_FIELDS = {"agres", "agres_probables"}
ALLOWED_OVERRIDE_KEYS = {
    "id", "nom", "adresse", "cp", "ville", "dep", "lat", "lon", "piste", "couloirs",
    "longueur_piste", "longueur_probable", "surface", "couvert", "eclairage",
    "acces_libre", "ouvert_public",
    "horaires", "acces_note", "vestiaires", "douches", "sanitaires", "tribunes",
    "agres", "agres_probables", "url", "annee", "renovation", "photos", "avis", "note",
    "supprime", "scolaire", "region", "dep_nom", "proprietaire", "gestionnaire",
}


def apply_overrides(installations, overrides):
    for ov in overrides:
        unknown = set(ov) - ALLOWED_OVERRIDE_KEYS
        if unknown:
            raise SystemExit(f"[ERREUR] cle(s) inconnue(s) dans une contribution : {sorted(unknown)}")
        oid = ov.get("id")
        if not oid:
            raise SystemExit("[ERREUR] une contribution n'a pas de champ 'id'")
        inst = installations.get(oid)
        if inst is None:
            # nouvelle piste ajoutee par la communaute
            inst = installations[oid] = {
                "id": oid, "nom": "", "adresse": "", "cp": None, "ville": "",
                "insee": None, "dep": None, "dep_nom": None, "region": None,
                "scolaire": False, "lat": None, "lon": None, "piste": True,
                "couloirs": None, "longueur_piste": None, "longueur_probable": None,
                "surface": None,
                "couvert": False, "eclairage": False, "acces_libre": False,
                "ouvert_public": False, "vestiaires": False, "douches": False,
                "sanitaires": False, "tribunes": None, "agres": set(),
                "agres_probables": set(), "nb_sautoirs": 0, "nb_aires_lancer": 0,
                "annee": None, "renovation": None, "url": None,
                "photos": [], "avis": [],
                "proprietaire": None, "gestionnaire": None, "equipements": [],
                "source": "communaute",
            }
        else:
            inst["source"] = "res+communaute"
        for k, v in ov.items():
            if k == "id":
                continue
            if k in LIST_FIELDS:
                inst[k] = set(v or [])
            else:
                inst[k] = v
        # une correction communautaire leve l'incertitude sur les agres
        if "agres" in ov and "agres_probables" not in ov:
            inst["agres_probables"] = set()
        # de meme, un developpement releve sur place chasse celui estime par OSM
        if "longueur_piste" in ov and "longueur_probable" not in ov:
            inst["longueur_probable"] = None
    return {k: v for k, v in installations.items() if not v.get("supprime")}


# --- encodage compact du fichier publie -------------------------------------
KEYMAP = {
    "id": "i", "nom": "n", "adresse": "a", "cp": "cp", "ville": "v",
    "dep": "d", "lat": "y", "lon": "x", "piste": "p", "couloirs": "cl",
    "longueur_piste": "lp", "longueur_probable": "lpp", "surface": "s", "couvert": "cv", "eclairage": "ec",
    "acces_libre": "al", "ouvert_public": "op", "vestiaires": "ve", "douches": "du",
    "sanitaires": "wc", "tribunes": "tr", "agres": "g", "agres_probables": "gp",
    "nb_sautoirs": "ns", "nb_aires_lancer": "nl", "annee": "an", "renovation": "rn",
    "url": "u", "scolaire": "sc", "source": "sr", "horaires": "h",
    "acces_note": "na", "note": "no", "photos": "ph", "avis": "av",
    "note_moyenne": "nt", "nb_avis": "nv",
}
SOURCE_CODES = {"res": 0, "res+communaute": 1, "communaute": 2}


def prepare_photos(site_id, photos):
    """Verifie que les fichiers existent et produit les chemins publics."""
    out = []
    for p in photos or []:
        fichier = p.get("fichier") if isinstance(p, dict) else p
        if not fichier:
            continue
        rel = os.path.join("data", "photos", site_id, fichier)
        if not os.path.exists(os.path.join(ROOT, rel)):
            raise SystemExit(f"[ERREUR] photo introuvable : {rel}")
        thumb = fichier.rsplit(".", 1)[0] + ".thumb." + fichier.rsplit(".", 1)[1]
        entry = {"f": rel.replace(os.sep, "/")}
        if os.path.exists(os.path.join(ROOT, "data", "photos", site_id, thumb)):
            entry["t"] = f"data/photos/{site_id}/{thumb}"
        if isinstance(p, dict):
            if p.get("legende"):
                entry["l"] = p["legende"]
            if p.get("credit"):
                entry["c"] = p["credit"]
        out.append(entry)
    return out


def prepare_avis(avis):
    """Normalise les avis et calcule la note moyenne."""
    out, notes = [], []
    for a in sorted(avis or [], key=lambda a: a.get("date", ""), reverse=True):
        entry = {"t": a["texte"]}
        if a.get("auteur"):
            entry["a"] = a["auteur"]
        if a.get("date"):
            entry["d"] = a["date"]
        if a.get("note"):
            entry["n"] = int(a["note"])
            notes.append(int(a["note"]))
        out.append(entry)
    moyenne = round(sum(notes) / len(notes), 1) if notes else None
    return out, moyenne


def finalize(installations):
    deps = {}
    tracks = []
    for inst in installations.values():
        if inst["lat"] is None or inst["lon"] is None:
            continue
        inst["photos"] = prepare_photos(inst["id"], inst.get("photos"))
        inst["avis"], inst["note_moyenne"] = prepare_avis(inst.get("avis"))
        inst["nb_avis"] = len(inst["avis"])
        if inst.get("dep") and inst.get("dep_nom"):
            deps[inst["dep"]] = [inst["dep_nom"], inst.get("region") or ""]
        rec = {}
        for key, short in KEYMAP.items():
            v = inst.get(key)
            if key in ("lat", "lon"):
                v = round(float(v), 5)
            elif key in LIST_FIELDS:
                v = sorted(v) if v else None
            elif key == "source":
                v = SOURCE_CODES.get(v, 0)
            if v in (None, "", False, [], 0):
                continue
            rec[short] = 1 if v is True else v
        rec.setdefault("p", 0)
        tracks.append(rec)
    tracks.sort(key=lambda t: (t.get("d") or "", t.get("v") or "", t.get("n") or ""))
    return tracks, deps


# --- vitrine des contributions ----------------------------------------------
@lru_cache(maxsize=1)
def depot_complet():
    """Vrai si l'historique git est la, faux sur un clone superficiel.

    On le verifie une fois plutot que de decouvrir apres coup que toutes les
    contributions portent la meme date."""
    try:
        out = subprocess.run(["git", "rev-parse", "--is-shallow-repository"],
                             cwd=ROOT, capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return False
    if out.returncode != 0:
        return False                                     # pas un depot git
    if out.stdout.strip() == "true":
        print("-> historique git superficiel : les dates de contribution "
              "retombent sur la date des fichiers (voir fetch-depth dans deploy.yml)")
        return False
    return True


def date_contribution(site_id):
    """Date du commit qui a *cree* la contribution de ce site.

    C'est la seule date dont on dispose : les avis portent la date de la
    visite, pas celle de l'envoi, et une photo n'en porte aucune.

    La creation, et non la derniere modification : un commit de maintenance qui
    passe sur tous les fichiers d'override — un renommage de photos, une
    migration de champ — redaterait sinon toutes les contributions du meme
    jour, et « les dernieres contributions » ne voudrait plus rien dire. Le
    prix est qu'une fiche enrichie des mois plus tard ne remonte pas ; c'est
    voulu, la vitrine annonce des contributions nouvelles.

    Hors depot git (archive telechargee, clone superficiel), on retombe sur la
    date de modification du fichier."""
    chemin = os.path.join(OVERRIDES_DIR, f"{site_id}.json")
    if not os.path.exists(chemin):
        return None
    if not depot_complet():
        # Un clone superficiel ne connait qu'un commit : git repondrait la date
        # du deploiement pour toutes les contributions, ce qui est pire qu'une
        # date de fichier. La CI doit demander fetch-depth: 0.
        return date.fromtimestamp(os.path.getmtime(chemin)).isoformat()
    try:
        out = subprocess.run(
            ["git", "log", "--follow", "--diff-filter=A", "--format=%cs", "--", chemin],
            cwd=ROOT, capture_output=True, text=True, timeout=10)
        # --follow suit les renommages ; le dernier ajout listé est le plus ancien
        lignes = [l for l in out.stdout.splitlines() if l.strip()]
        if out.returncode == 0 and lignes:
            return lignes[-1].strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return date.fromtimestamp(os.path.getmtime(chemin)).isoformat()


def fusionne_noms(noms):
    """« Ronan » et « Ronan Chardonneau » sont la meme personne.

    Les credits de photo portent souvent le nom complet et les avis le prenom
    seul. On rattache un nom court a un nom long qui commence pareil, et on
    garde le plus long comme forme canonique. Deux homonymes distincts qui
    signeraient l'un « Marie » et l'autre « Marie Dupont » seraient fusionnes a
    tort : c'est le prix a payer, et il reste tres inferieur a celui d'un
    classement ou la meme personne apparait deux fois."""
    longs = sorted(noms, key=lambda n: -len(n))
    canon = {}
    for n in longs:
        cle = deaccent(n).lower()
        for autre in longs:
            if autre is n:
                continue
            a = deaccent(autre).lower()
            if len(a) > len(cle) and (a == cle or a.startswith(cle + " ")):
                canon[n] = canon.get(autre, autre)
                break
        canon.setdefault(n, n)
    return canon


def communaute(tracks, recentes=200, top=200):
    """Les dernieres contributions et le classement des contributeurs.

    Calcule ici plutot que dans l'application : le classement demande de
    parcourir les 7 100 sites et de reconcilier les noms, ce qui n'a aucune
    raison d'etre refait dans chaque navigateur a chaque chargement.

    Les listes sont completes, pas tronquees a ce qu'affiche la vitrine : la
    page /contributeurs/ les rend toutes. Une entree pese une trentaine
    d'octets, le plafond n'est la que pour borner un futur lointain."""
    ph, av = KEYMAP["photos"], KEYMAP["avis"]
    brut = {}                                   # nom tel qu'ecrit -> compteurs
    sites = {}                                  # nom -> ids distincts

    for t in tracks:
        for p in t.get(ph) or []:
            nom = (p.get("c") or "").strip()
            if not nom:
                continue
            brut.setdefault(nom, {"p": 0, "a": 0})["p"] += 1
            sites.setdefault(nom, set()).add(t["i"])
        for a in t.get(av) or []:
            nom = (a.get("a") or "").strip()
            if not nom:
                continue
            brut.setdefault(nom, {"p": 0, "a": 0})["a"] += 1
            sites.setdefault(nom, set()).add(t["i"])

    canon = fusionne_noms(list(brut))
    fusion = {}
    for nom, c in brut.items():
        cible = fusion.setdefault(canon[nom], {"n": canon[nom], "s": set(), "p": 0, "a": 0})
        cible["p"] += c["p"]
        cible["a"] += c["a"]
        cible["s"] |= sites[nom]
    classement = sorted(fusion.values(),
                        key=lambda c: (-len(c["s"]), -c["p"], -c["a"], c["n"]))
    classement = [{"n": c["n"], "s": len(c["s"]), "p": c["p"], "a": c["a"]}
                  for c in classement[:top]]

    # les dernieres contributions : celles qui ont une photo a montrer
    avec_photo = [t for t in tracks if t.get(ph)]
    datees = [{"i": t["i"], "d": date_contribution(t["i"])} for t in avec_photo]
    datees = [d for d in datees if d["d"]]
    datees.sort(key=lambda d: d["d"], reverse=True)
    return {"recentes": datees[:recentes], "top": classement}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true",
                    help="utilise le cache data/.res_raw.json au lieu d'appeler l'API")
    args = ap.parse_args()

    raw = fetch_raw(offline=args.offline)
    installations = aggregate(raw)
    installations = apply_overrides(installations, load_overrides())
    tracks, deps = finalize(installations)
    deps = millesimes(tracks, deps)

    avec_piste = sum(1 for t in tracks if t.get("p"))
    avec_photo = sum(1 for t in tracks if t.get("ph"))
    avec_avis = sum(1 for t in tracks if t.get("av"))
    payload = {
        "generated": date.today().isoformat(),
        "app_version": app_version(),
        "count": len(tracks),
        "source": {
            "nom": "Recensement des equipements sportifs (Data ES) - Ministere charge des Sports",
            "url": "https://equipements.sports.gouv.fr/",
            "licence": "Licence Ouverte 2.0 (Etalab)",
            "licence_url": "https://github.com/etalab/licence-ouverte/blob/master/LO.md",
        },
        "keymap": {v: k for k, v in KEYMAP.items()},
        "deps": deps,
        "communaute": communaute(tracks),
        "tracks": tracks,
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
    size = os.path.getsize(OUT) / 1024
    print(f"-> {OUT}")
    print(f"   {len(tracks)} sites ({avec_piste} avec piste, "
          f"{avec_photo} avec photos, {avec_avis} avec avis) - {size:.0f} Ko")


if __name__ == "__main__":
    main()
