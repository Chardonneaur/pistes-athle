#!/usr/bin/env python3
"""Valide les contributions de data/overrides/ avant fusion.

Lance : python3 scripts/validate_overrides.py
Sortie : code 0 si tout est valide, 1 sinon (utilise par la CI).
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIR = os.path.join(ROOT, "data", "overrides")

AGRES = {"longueur", "triple", "hauteur", "perche", "poids", "disque",
         "marteau", "javelot", "steeple"}
SURFACES = {"synthetique", "bitume", "cendree", "sable", "gazon", "naturel", "interieur"}

# Le vocabulaire du ministere, repris tel quel : un anneau de stade, une piste
# de 2 a 4 couloirs, ou une piste isolee — c'est-a-dire hors stade
# d'athletisme, souvent une ligne droite. Une visite peut corriger le type,
# jamais l'inventer : hors de ces trois valeurs, on refuse.
TYPES_PISTE = {"stade", "couloirs_2_4", "isolee"}

STR = {"nom", "adresse", "cp", "ville", "dep", "dep_nom", "region", "surface",
       "type_piste", "url", "horaires", "acces_note", "note", "photo",
       "proprietaire", "gestionnaire", "commune_deleguee"}
BOOL = {"piste", "couvert", "eclairage", "acces_libre", "ouvert_public", "vestiaires",
        "douches", "sanitaires", "scolaire", "supprime"}
INT = {"couloirs", "longueur_piste", "longueur_probable", "tribunes", "annee", "renovation"}
NUM = {"lat", "lon"}
LIST = {"agres", "agres_probables"}
MEDIA = {"photos", "avis"}
ALLOWED = STR | BOOL | INT | NUM | LIST | MEDIA | {"id"}

PHOTOS_DIR = os.path.join(ROOT, "data", "photos")

ID_RE = re.compile(r"^(I[0-9A-Z]{9,}|c-[a-z0-9-]{3,60})$")

# Une boite par territoire, et non une seule pour tous. Le controle d'avant
# tenait en une ligne — 41 <= lat <= 52 et -62 <= lon <= 56 — qui prenait la
# latitude de la metropole et la longitude de la Guadeloupe a La Reunion : le
# produit des deux ne decrit aucune terre francaise, place La Reunion en Asie
# centrale et refusait tout l'outre-mer, que son propre message annoncait
# pourtant couvrir. Aucune contribution ultramarine n'aurait pu etre acceptee.
TERRITOIRES = {
    "metropole": (41.3, 51.2, -5.2, 9.6),
    "guadeloupe-martinique-saint-martin": (14.3, 18.2, -63.2, -60.7),
    "guyane": (2.0, 6.0, -54.7, -51.5),
    "reunion": (-21.4, -20.8, 55.2, 55.9),
    "mayotte": (-13.1, -12.6, 45.0, 45.4),
    "saint-pierre-et-miquelon": (46.7, 47.2, -56.5, -56.1),
    "polynesie": (-28.0, -7.8, -154.8, -134.4),
    "nouvelle-caledonie": (-22.8, -18.0, 162.4, 168.2),
    "wallis-et-futuna": (-14.4, -13.2, -178.3, -176.1),
}


errors = []


def err(fn, msg):
    errors.append(f"{fn}: {msg}")


def check_photos(fn, site_id, photos):
    if not isinstance(photos, list):
        return err(fn, "'photos' doit etre une liste")
    for p in photos:
        if not isinstance(p, dict) or not p.get("fichier"):
            err(fn, "chaque photo doit etre un objet avec au moins un champ 'fichier'")
            continue
        extra = set(p) - {"fichier", "legende", "credit"}
        if extra:
            err(fn, f"photo : cle(s) inconnue(s) {sorted(extra)} "
                    f"(autorisees : fichier, legende, credit)")
        f = p["fichier"]
        if "/" in f or "\\" in f or f.startswith("."):
            err(fn, f"photo '{f}' : indiquez seulement le nom du fichier")
            continue
        if not f.lower().endswith((".jpg", ".jpeg")):
            err(fn, f"photo '{f}' : format JPEG attendu")
        path = os.path.join(PHOTOS_DIR, site_id, f)
        if not os.path.exists(path):
            err(fn, f"photo introuvable : data/photos/{site_id}/{f} "
                    f"(lancez scripts/optimize_photos.py)")
        elif os.path.getsize(path) > 400 * 1024:
            err(fn, f"photo '{f}' trop lourde ({os.path.getsize(path)//1024} Ko, max 400) : "
                    f"passez-la par scripts/optimize_photos.py")


def check_avis(fn, avis):
    if not isinstance(avis, list):
        return err(fn, "'avis' doit etre une liste")
    for a in avis:
        if not isinstance(a, dict):
            err(fn, "chaque avis doit etre un objet JSON")
            continue
        extra = set(a) - {"auteur", "date", "note", "texte"}
        if extra:
            err(fn, f"avis : cle(s) inconnue(s) {sorted(extra)} "
                    f"(autorisees : auteur, date, note, texte)")
        texte = a.get("texte")
        if not texte or not isinstance(texte, str):
            err(fn, "avis : le champ 'texte' est obligatoire")
        elif len(texte) > 1200:
            err(fn, f"avis : texte trop long ({len(texte)} caracteres, max 1200)")
        if "note" in a and a["note"] not in (1, 2, 3, 4, 5):
            err(fn, "avis : 'note' doit etre un entier de 1 a 5")
        if a.get("date") and not re.match(r"^\d{4}-\d{2}-\d{2}$", str(a["date"])):
            err(fn, "avis : 'date' doit etre au format AAAA-MM-JJ")
        if a.get("auteur") and len(str(a["auteur"])) > 40:
            err(fn, "avis : 'auteur' est limite a 40 caracteres")


def check(fn, rec):
    if not isinstance(rec, dict):
        return err(fn, "chaque entree doit etre un objet JSON")

    rid = rec.get("id")
    if not rid or not isinstance(rid, str):
        return err(fn, "champ 'id' manquant")
    if not ID_RE.match(rid):
        err(fn, f"id '{rid}' invalide : reprenez la reference affichee sur la fiche "
                f"(ex. I352380090) ou creez un id du type c-ma-nouvelle-piste")

    for k, v in rec.items():
        if k not in ALLOWED:
            err(fn, f"cle inconnue '{k}' (autorisees : {', '.join(sorted(ALLOWED))})")
        elif k in BOOL and not isinstance(v, bool):
            err(fn, f"'{k}' doit valoir true ou false")
        elif k in INT and not (isinstance(v, int) and not isinstance(v, bool)):
            err(fn, f"'{k}' doit etre un nombre entier")
        elif k in NUM and not isinstance(v, (int, float)):
            err(fn, f"'{k}' doit etre un nombre")
        elif k in STR and not isinstance(v, str):
            err(fn, f"'{k}' doit etre une chaine de caracteres")
        elif k == "photos":
            check_photos(fn, rid, v)
        elif k == "avis":
            check_avis(fn, v)
        elif k in LIST:
            if not isinstance(v, list):
                err(fn, f"'{k}' doit etre une liste")
            else:
                for a in v:
                    if k == "agres" and a not in AGRES:
                        err(fn, f"agres '{a}' inconnu (valeurs : {', '.join(sorted(AGRES))})")

    if rec.get("surface") and rec["surface"] not in SURFACES:
        err(fn, f"surface '{rec['surface']}' inconnue (valeurs : {', '.join(sorted(SURFACES))})")

    if rec.get("type_piste") and rec["type_piste"] not in TYPES_PISTE:
        err(fn, f"type_piste '{rec['type_piste']}' inconnu "
                f"(valeurs : {', '.join(sorted(TYPES_PISTE))})")

    lat, lon = rec.get("lat"), rec.get("lon")
    if (lat is None) != (lon is None):
        err(fn, "lat et lon doivent etre fournis ensemble")
    if lat is not None and not (-90 <= lat <= 90 and -180 <= lon <= 180):
        err(fn, "coordonnees hors limites")
    if lat is not None and not any(a <= lat <= b and c <= lon <= d
                                   for a, b, c, d in TERRITOIRES.values()):
        err(fn, f"coordonnees ({lat}, {lon}) hors de France et outre-mer : "
                f"lat et lon sont-ils inverses ?")

    if rid.startswith("c-"):
        for k in ("nom", "ville", "lat", "lon"):
            if rec.get(k) in (None, ""):
                err(fn, f"nouvelle piste : le champ '{k}' est obligatoire")

    if rec.get("url") and not rec["url"].startswith(("http://", "https://")):
        err(fn, "'url' doit commencer par http:// ou https://")


def main():
    if not os.path.isdir(DIR):
        print("Aucun dossier data/overrides/ : rien a valider.")
        return 0

    files = sorted(f for f in os.listdir(DIR) if f.endswith(".json") and not f.startswith("_"))
    seen = {}
    for fn in files:
        with open(os.path.join(DIR, fn), encoding="utf-8") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError as exc:
                err(fn, f"JSON invalide -> {exc}")
                continue
        for rec in (data if isinstance(data, list) else [data]):
            check(fn, rec)
            rid = rec.get("id") if isinstance(rec, dict) else None
            if rid:
                if rid in seen:
                    err(fn, f"id '{rid}' deja defini dans {seen[rid]}")
                seen[rid] = fn

    if errors:
        print(f"{len(errors)} probleme(s) :\n")
        for e in errors:
            print("  x", e)
        return 1
    print(f"{len(files)} fichier(s), {len(seen)} site(s) : tout est valide.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
