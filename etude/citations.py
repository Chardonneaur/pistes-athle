#!/usr/bin/env python3
"""Isole, dans le journal des robots, ce qui ressemble a une citation.

Etre explore n'est pas etre cite. Les 28 000 pages que ClaudeBot et GPTBot ont
avalees en une journee alimentent un corpus ; elles ne prouvent pas qu'un
assistant reponde un jour en s'appuyant sur le site. Ce sont deux questions
differentes, et le journal les distingue deja sans le dire : le nom du robot
suffit.

Trois familles, par ordre de proximite avec une reponse rendue a quelqu'un :

- **exploration** : la constitution d'un corpus. GPTBot, ClaudeBot, Googlebot.
  Passe une fois, prend tout, ne dit rien de l'usage.
- **index de reponse** : l'index propre au moteur de reponse, celui d'ou les
  citations sont tirees. OAI-SearchBot, PerplexityBot, Claude-SearchBot. Y
  figurer est la condition d'etre cite ; ce n'en est pas la preuve.
- **a la demande** : la page est allee etre lue *parce qu'un humain venait de
  poser une question*. ChatGPT-User, Claude-User, Perplexity-User,
  MistralAI-User. C'est le signal le plus proche d'une citation qu'un site
  puisse observer depuis ses propres logs.

D'ou le grain : les passages d'exploration se comptent, ceux des deux autres
familles s'enumerent un par un. Ils sont rares et chacun designe **une page** —
savoir quelle fiche un assistant est alle lire vaut plus que leur nombre.

Le fichier est en ajout seul, et ne reecrit jamais une ligne : on ne reprend
que ce qui est postereur au dernier passage deja enregistre.

    python3 etude/citations.py --sortie etude
"""
import argparse
import csv
import json
import subprocess
import sys
from datetime import date, datetime, timezone
from pathlib import Path

BASE = "pistes-athle-logs"

# Le nom canonique tel que le Worker l'ecrit (voir logs/worker.js), et sa famille.
FAMILLES = {
    "ChatGPT-User": "a-la-demande",
    "Claude-User": "a-la-demande",
    "Perplexity-User": "a-la-demande",
    "MistralAI-User": "a-la-demande",
    "OAI-SearchBot": "index-reponse",
    "PerplexityBot": "index-reponse",
    "Claude-SearchBot": "index-reponse",
    "YouBot": "index-reponse",
}
# Tout le reste est de l'exploration : on ne l'enumere pas ici, pour qu'un robot
# inconnu tombe du bon cote plutot que d'etre compte comme une citation.

ENTETES = ["releve", "horodatage", "famille", "robot", "vu_le", "statut",
           "gabarit", "chemin"]


def interroger(depuis):
    """wrangler plutot que l'API REST : il porte deja l'authentification."""
    noms = ", ".join("'" + n.replace("'", "''") + "'" for n in FAMILLES)
    ou = f"robot IN ({noms})"
    if depuis:
        ou += f" AND vu_le > '{depuis}'"
    requete = (f"SELECT vu_le, robot, chemin, gabarit, statut "
               f"FROM visites_robots WHERE {ou} ORDER BY vu_le;")
    r = subprocess.run(
        ["npx", "wrangler", "d1", "execute", BASE, "--remote", "--json",
         "--command", requete],
        capture_output=True, text=True, timeout=300,
    )
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip()[:500] or "wrangler a echoue")
    debut = r.stdout.find("[")
    if debut < 0:
        raise RuntimeError(f"sortie inattendue : {r.stdout[:300]}")
    return json.loads(r.stdout[debut:])[0]["results"]


def dernier_vu(chemin):
    """Le passage le plus recent deja enregistre, pour ne rien redoubler."""
    if not chemin.exists():
        return None
    dernier = None
    with chemin.open(encoding="utf-8") as f:
        for ligne in csv.DictReader(f):
            v = ligne.get("vu_le")
            if v and (dernier is None or v > dernier):
                dernier = v
    return dernier


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--sortie", type=Path, default=Path("etude"))
    p.add_argument("--tout", action="store_true",
                   help="reprendre depuis le debut au lieu du dernier passage connu")
    args = p.parse_args()

    chemin = args.sortie / "citations.csv"
    depuis = None if args.tout else dernier_vu(chemin)

    try:
        lignes = interroger(depuis)
    except Exception as e:                       # noqa: BLE001
        print(f"Echec : {e}", file=sys.stderr)
        return 1

    jour = date.today().isoformat()
    horodatage = datetime.now(timezone.utc).isoformat(timespec="seconds")
    neuf = not chemin.exists()
    chemin.parent.mkdir(parents=True, exist_ok=True)
    with chemin.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=ENTETES)
        if neuf:
            w.writeheader()
        for l in lignes:
            w.writerow({"releve": jour, "horodatage": horodatage,
                        "famille": FAMILLES.get(l["robot"], "?"), **l})

    if not lignes:
        depuis_dit = f" depuis {depuis[:19]}" if depuis else ""
        print(f"{jour} — aucun passage de citation{depuis_dit}. "
              f"L'exploration ne compte pas ici.")
        return 0

    demande = [l for l in lignes if FAMILLES.get(l["robot"]) == "a-la-demande"]
    index = [l for l in lignes if FAMILLES.get(l["robot"]) == "index-reponse"]
    print(f"{jour} — {len(lignes)} passage(s) nouveau(x) : "
          f"{len(demande)} a la demande, {len(index)} d'index de reponse.")
    for l in lignes:
        famille = FAMILLES.get(l["robot"], "?")
        marque = " <<<" if famille == "a-la-demande" and l["chemin"] != "/robots.txt" else ""
        print(f"   {l['vu_le'][:19]}  {famille:<14} {l['robot']:<16} "
              f"{l['statut']}  {l['chemin']}{marque}")
    if any(l["chemin"] != "/robots.txt" for l in demande):
        print("\n   Les lignes marquees sont des pages qu'un assistant est alle lire")
        print("   parce qu'un humain venait de poser une question. C'est le signal.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
