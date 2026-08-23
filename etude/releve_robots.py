#!/usr/bin/env python3
"""Ajoute au journal d'etude ce que la base D1 sait des passages de robots.

Le Worker (voir logs/) enregistre chaque visite de robot. Ce script en tire un
resume quotidien : qui est passe, combien de fois, sur combien de pages
distinctes, et surtout **quand il est passe la premiere fois** — la date qui
repond a la question de l'etude.

    python3 etude/releve_robots.py --sortie etude
"""
import argparse
import csv
import json
import subprocess
import sys
from datetime import date, datetime, timezone
from pathlib import Path

BASE = "pistes-athle-logs"
REQUETE = """
SELECT robot,
       COUNT(*)                AS passages,
       COUNT(DISTINCT chemin)  AS pages_distinctes,
       MIN(vu_le)              AS premier_vu,
       MAX(vu_le)              AS dernier_vu
FROM visites_robots
GROUP BY robot
ORDER BY premier_vu;
"""


def interroger():
    """wrangler plutot que l'API REST : il porte deja l'authentification."""
    r = subprocess.run(
        ["npx", "wrangler", "d1", "execute", BASE, "--remote", "--json",
         "--command", REQUETE.strip()],
        capture_output=True, text=True, timeout=300,
    )
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip()[:500] or "wrangler a echoue")
    # wrangler prefixe parfois sa sortie d'une banniere : on repart du premier « [ ».
    debut = r.stdout.find("[")
    if debut < 0:
        raise RuntimeError(f"sortie inattendue : {r.stdout[:300]}")
    return json.loads(r.stdout[debut:])[0]["results"]


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--sortie", type=Path, default=Path("etude"))
    args = p.parse_args()

    try:
        lignes = interroger()
    except Exception as e:                       # noqa: BLE001
        print(f"Echec : {e}", file=sys.stderr)
        return 1

    jour = date.today().isoformat()
    horodatage = datetime.now(timezone.utc).isoformat(timespec="seconds")
    chemin = args.sortie / "robots.csv"
    entetes = ["releve", "horodatage", "robot", "passages", "pages_distinctes",
               "premier_vu", "dernier_vu"]
    neuf = not chemin.exists()
    chemin.parent.mkdir(parents=True, exist_ok=True)
    with chemin.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=entetes)
        if neuf:
            w.writeheader()
        for l in lignes:
            w.writerow({"releve": jour, "horodatage": horodatage, **l})

    if not lignes:
        print(f"{jour} — aucun robot enregistre pour l'instant")
    else:
        print(f"{jour} — {len(lignes)} robot(s) :")
        for l in lignes:
            print(f"   {l['robot']:20} {l['passages']:6} passages, "
                  f"{l['pages_distinctes']:6} pages, depuis {l['premier_vu'][:19]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
