#!/usr/bin/env python3
"""
Les fiches que Google sert encore et que le site ne publie plus.

Data ES renumerote. Une installation change d'identifiant, ou sort du
recensement, et la page /site/<ancien>/ disparait du build au matin suivant.
Google, lui, continue de la servir pendant des semaines : releve du 5 septembre
2026, 36 identifiants morts recevaient encore 191 impressions et 5 clics sur
28 jours, tous vers un 404. Des gens cherchaient un stade, le trouvaient dans
Google, et tombaient sur rien.

Ce script tient la liste de ces identifiants dans data/disparus.json, que
build_site.py relit pour publier une passerelle vers la commune plutot qu'un
404 sec.

POURQUOI LA SEARCH CONSOLE, ET RIEN D'AUTRE. Il faut savoir ce que le site
publiait AVANT, et cette memoire n'existe nulle part : data/tracks.json est
regenere a chaque build et n'est pas versionne, le plan du site en ligne est
celui du dernier build — donc deja purge des morts. La Search Console est le
seul temoin de ce qui a ete publie et indexe. C'est aussi pour cela que le
fichier est CUMULATIF : on n'y retire jamais une entree parce qu'elle a cesse
de recevoir des impressions, sinon la passerelle disparaitrait et le 404
reviendrait.

POURQUOI PAS DANS LE WORKFLOW. deploy.yml tourne en « contents: read » et
n'ecrit rien dans le depot. Ce script se lance donc a la main, comme
pistes_absentes.py ou marches_publics.py, et son resultat se commite.

CE QU'IL NE FAIT PAS. Il ne devine pas ou l'installation est passee. Un
identifiant mort ne dit pas si le site a ete renumerote, fusionne ou demoli :
il dit seulement que le recensement ne le porte plus. La destination est donc
la page de la COMMUNE — qui liste les installations encore recensees, dont,
le plus souvent, la meme sous son nouveau numero — et jamais une autre fiche,
qui serait une equivalence inventee.

Usage :
  python3 scripts/disparus.py                 # releve et met a jour le fichier
  python3 scripts/disparus.py --jours 180     # fenetre plus large
  python3 scripts/disparus.py --simulation    # montre sans ecrire
"""

import argparse
import datetime
import json
import os
import re
import sys
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from releve_gsc import PROPRIETE, jeton_google        # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TRACKS = os.path.join(ROOT, "data", "tracks.json")
DISPARUS = os.path.join(ROOT, "data", "disparus.json")

# /site/<id>/ en francais, /en/track/<id>/ en anglais : les deux servent la
# meme fiche et meritent la meme passerelle.
CHEMIN_FICHE = re.compile(r"/(?:site|en/track)/([^/?#]+)/?")

# L'identifiant Data ES porte l'INSEE de sa commune : « I440180009 » est le
# neuvieme equipement de la commune 44018, Bouaye. Verifie sur le jeu publie :
# 3 796 prefixes sur 3 813 ne designent qu'une seule commune. C'est ce qui
# permet de situer un identifiant que plus aucune donnee ne decrit.
INSEE_DANS_ID = re.compile(r"^I(\d{5})\d+$")


def charge_tracks():
    with open(TRACKS, encoding="utf-8") as f:
        d = json.load(f)
    km = d["keymap"]
    return [{km.get(k, k): v for k, v in t.items()} for t in d["tracks"]]


def pages_gsc(jeton, jours):
    """Les pages vues par Google sur la fenetre, avec leurs compteurs."""
    fin = datetime.date.today() - datetime.timedelta(days=2)   # latence GSC
    debut = fin - datetime.timedelta(days=jours)
    url = ("https://www.googleapis.com/webmasters/v3/sites/"
           + urllib.parse.quote(PROPRIETE, safe="") + "/searchAnalytics/query")
    lignes, depart = [], 0
    while True:
        charge = json.dumps({"startDate": str(debut), "endDate": str(fin),
                             "dimensions": ["page"], "rowLimit": 25000,
                             "startRow": depart}).encode()
        req = urllib.request.Request(url, data=charge, headers={
            "Authorization": "Bearer " + jeton, "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=90) as r:
            lot = json.load(r).get("rows", [])
        lignes.extend(lot)
        if len(lot) < 25000:
            break
        depart += 25000
    return lignes, debut, fin


def communes_par_insee(tracks):
    """INSEE -> (slug de commune, departement), quand il n'y a pas d'ambiguite.

    Un prefixe partage par deux communes est ecarte plutot qu'arbitre : mieux
    vaut renvoyer vers le departement que vers la mauvaise commune.
    """
    from build_api import slug
    vus = {}
    for t in tracks:
        m = INSEE_DANS_ID.match(t["id"])
        if not m:
            continue                       # « c-… », une contribution, pas Data ES
        vus.setdefault(m.group(1), set()).add(
            (slug(t.get("ville") or ""), t.get("dep")))
    return {k: next(iter(v)) for k, v in vus.items() if len(v) == 1}


def releve(jours):
    tracks = charge_tracks()
    vivants = {t["id"] for t in tracks}
    par_insee = communes_par_insee(tracks)

    lignes, debut, fin = pages_gsc(jeton_google(), jours)
    morts = {}
    for r in lignes:
        m = CHEMIN_FICHE.search(r["keys"][0])
        if not m or m.group(1) in vivants:
            continue
        e = morts.setdefault(m.group(1), {"impressions": 0, "clics": 0})
        e["impressions"] += r.get("impressions", 0)
        e["clics"] += r.get("clicks", 0)

    aujourdhui = str(datetime.date.today())
    sortie = []
    for ident, compte in sorted(morts.items(),
                                key=lambda kv: -kv[1]["impressions"]):
        m = INSEE_DANS_ID.match(ident)
        insee = m.group(1) if m else None
        commune, dep = par_insee.get(insee or "", (None, None))
        if dep is None and insee:
            # Aucune installation vivante dans la commune : le departement se
            # lit quand meme dans l'INSEE. Trois chiffres outre-mer — 97x pour
            # les DOM, 98x pour la Polynesie et la Nouvelle-Caledonie — deux
            # partout ailleurs. Rien ne garantit que la page existe : c'est
            # build_site.py qui verifie et retombe sur l'accueil au besoin.
            dep = insee[:3] if insee[:2] in ("97", "98") else insee[:2]
        sortie.append({"id": ident, "insee": insee, "commune": commune,
                       "dep": dep, "impressions": compte["impressions"],
                       "clics": compte["clics"], "vu_le": aujourdhui})
    return sortie, debut, fin


def fusionne(neufs):
    """Cumule sans jamais perdre une entree deja connue.

    Un identifiant qui cesse de recevoir des impressions n'est pas ressuscite :
    il est seulement sorti de la fenetre. Retirer sa passerelle rendrait le 404
    qu'on vient d'enlever.
    """
    ancien = {}
    if os.path.exists(DISPARUS):
        with open(DISPARUS, encoding="utf-8") as f:
            ancien = {e["id"]: e for e in json.load(f).get("sites", [])}
    ajouts = 0
    for e in neufs:
        if e["id"] in ancien:
            a = ancien[e["id"]]
            a["impressions"] = max(a.get("impressions", 0), e["impressions"])
            a["clics"] = max(a.get("clics", 0), e["clics"])
            a["vu_le"] = e["vu_le"]
            # La commune peut s'etre remplie depuis : une installation voisine
            # a pu entrer au recensement et donner enfin le prefixe.
            if not a.get("commune") and e["commune"]:
                a["commune"], a["dep"] = e["commune"], e["dep"]
        else:
            ancien[e["id"]] = e
            ajouts += 1
    return sorted(ancien.values(), key=lambda e: -e["impressions"]), ajouts


def main():
    ap = argparse.ArgumentParser(
        description="Identifiants que Google sert encore et que le site ne publie plus.")
    ap.add_argument("--jours", type=int, default=90,
                    help="largeur de la fenetre Search Console (defaut 90)")
    ap.add_argument("--simulation", action="store_true",
                    help="montrer le releve sans ecrire data/disparus.json")
    args = ap.parse_args()

    neufs, debut, fin = releve(args.jours)
    print(f"Fenetre {debut} -> {fin} : {len(neufs)} identifiant(s) mort(s), "
          f"{sum(e['impressions'] for e in neufs)} impressions, "
          f"{sum(e['clics'] for e in neufs)} clics.")
    for e in neufs[:15]:
        ou = f"/ville/{e['commune']}/" if e["commune"] else \
             (f"/departement/{e['dep']}/" if e["dep"] else "accueil")
        print(f"  {e['impressions']:4} imp {e['clics']:2} clics  {e['id']:14} -> {ou}")
    if len(neufs) > 15:
        print(f"  … et {len(neufs) - 15} autres")

    tous, ajouts = fusionne(neufs)
    sans_commune = sum(1 for e in tous if not e["commune"])
    print(f"\ndata/disparus.json : {len(tous)} entrees ({ajouts} nouvelle(s)), "
          f"{sans_commune} sans commune vivante — renvoyees vers leur departement.")

    if args.simulation:
        print("Simulation : rien ecrit.")
        return
    with open(DISPARUS, "w", encoding="utf-8") as f:
        json.dump({"genere": str(datetime.date.today()),
                   "source": f"Search Console, {debut} -> {fin}",
                   "sites": tous}, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print("Ecrit. Reconstruire le site, puis committer le fichier.")


if __name__ == "__main__":
    main()
