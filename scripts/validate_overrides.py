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

STR = {"nom", "adresse", "cp", "ville", "dep", "dep_nom", "region", "surface",
       "url", "horaires", "acces_note", "note", "photo", "proprietaire", "gestionnaire"}
BOOL = {"piste", "couvert", "eclairage", "acces_libre", "ouvert_public", "vestiaires",
        "douches", "sanitaires", "scolaire", "supprime"}
INT = {"couloirs", "longueur_piste", "tribunes", "annee", "renovation"}
NUM = {"lat", "lon"}
LIST = {"agres", "agres_probables"}
ALLOWED = STR | BOOL | INT | NUM | LIST | {"id"}

ID_RE = re.compile(r"^(I[0-9A-Z]{9,}|c-[a-z0-9-]{3,60})$")

errors = []


def err(fn, msg):
    errors.append(f"{fn}: {msg}")


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
        elif k in LIST:
            if not isinstance(v, list):
                err(fn, f"'{k}' doit etre une liste")
            else:
                for a in v:
                    if k == "agres" and a not in AGRES:
                        err(fn, f"agres '{a}' inconnu (valeurs : {', '.join(sorted(AGRES))})")

    if rec.get("surface") and rec["surface"] not in SURFACES:
        err(fn, f"surface '{rec['surface']}' inconnue (valeurs : {', '.join(sorted(SURFACES))})")

    lat, lon = rec.get("lat"), rec.get("lon")
    if (lat is None) != (lon is None):
        err(fn, "lat et lon doivent etre fournis ensemble")
    if lat is not None and not (-90 <= lat <= 90 and -180 <= lon <= 180):
        err(fn, "coordonnees hors limites")
    if lat is not None and not (41 <= lat <= 52 and -62 <= lon <= 56):
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
