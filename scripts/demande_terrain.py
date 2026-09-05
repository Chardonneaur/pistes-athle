#!/usr/bin/env python3
"""
Ce que les gens cherchent, et que seule une visite peut ecrire.

La file de l'etage 2 repond a des QUESTIONS : « le stade X est-il couvert ? »,
« quel revetement a la piste Y ? ». Elle se traite depuis un bureau, en cherchant
une source citable. Mais au 5 septembre 2026, 91 % de cette file ne pose aucune
question : c'est un nom de stade tape tel quel, servi en position 25. Il n'y a
rien a chercher dans une source — la fiche est simplement pauvre.

Ce script lit cette masse pour ce qu'elle est : une mesure de la demande, stade
par stade. Il la croise avec ce que chaque fiche dit deja, et rend la liste des
installations que les gens cherchent et qui ne portent rien de premiere main.
C'est une file de TERRAIN, pas une file de bureau : sa sortie n'est pas « quelle
source citer », c'est « ou aller, et quoi regarder en arrivant ».

Ce qu'il ne fait pas, et pourquoi :

  - Il ne redistribue pas la demande d'une page de commune sur les stades de
    cette commune. Ce serait une arithmetique inventee : 40 impressions sur
    /ville/bouaye/ ne veulent pas dire 20 par stade. La demande communale est
    donc affichee dans sa propre colonne, comme un contexte de deplacement, et
    jamais melangee au compte du site.
  - Il ne classe pas une fiche « incomplete ». Un champ vide ne dit pas « non »,
    il ne dit rien — c'est la promesse du site. La colonne de droite liste donc
    ce qu'une visite permettrait de RENSEIGNER, jamais ce qui « manque » au sens
    d'une absence constatee.
  - Il ne juge pas de l'interet d'un deplacement. 39 impressions en un mois,
    c'est peu dans l'absolu ; c'est beaucoup rapporte a une fiche que personne
    n'a jamais photographiee.

Usage :
  python3 scripts/demande_terrain.py                  # les sites les plus demandes
  python3 scripts/demande_terrain.py --dep 44         # un departement
  python3 scripts/demande_terrain.py --tournee        # ou une journee paie le plus
  python3 scripts/demande_terrain.py --json           # pour un autre script
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from build_api import slug                    # noqa: E402  (meme slug que le site)
from dossier_gsc import charge_tracks         # noqa: E402  (une seule lecture de tracks)
from releve_gsc import D1                     # noqa: E402  (un seul transport D1)

SITE = "https://pistes-athle.com"

# Ce qu'une visite permet d'ecrire, et que rien d'autre ne donne.
#
# L'ordre compte : c'est celui dans lequel les manques sont affiches, et il va
# du plus irremplacable au plus substituable. Une photo et un avis n'existent
# nulle part ailleurs — aucune base ouverte, aucune orthophoto, aucun site de
# mairie ne les porte. Les couloirs sont le champ le plus rare de la base. Le
# revetement ferme la marche parce qu'il se lit parfois dans une source ecrite,
# meme s'il ne se deduit JAMAIS d'une couleur vue du ciel.
#
# Chaque entree : (champ de tracks.json, ce qu'on va regarder sur place)
A_RELEVER = [
    ("photos",         "aucune photo"),
    ("avis",           "aucun avis"),
    ("couloirs",       "couloirs non comptes"),
    ("agres",          "agres non vus"),
    ("horaires",       "horaires non releves"),
    ("surface",        "revetement non foule"),
]

# Le developpement se lit dans deux champs et un seul compte comme releve : une
# longueur estimee d'apres OpenStreetMap attend toujours d'etre mesuree.
MESURE = ("longueur_piste", "longueur_probable")


def demande(db):
    """Impressions par cible, tous statuts confondus sauf le hors-sujet.

    Tous statuts : un dossier ferme en « traite » a repondu a une QUESTION, ce
    qui ne rend pas la fiche moins muette sur son revetement ou ses photos. La
    demande est la demande, elle ne s'efface pas parce qu'on a ferme un dossier.
    Le hors-sujet, lui, ne parlait pas d'une piste d'athletisme : le compter
    ferait voyager pour rien.
    """
    lignes = db.sql(
        "SELECT cible, intention, statut, impressions, position"
        "  FROM requetes_gsc WHERE statut <> 'hors-sujet'")

    par_cible = {}
    for r in lignes:
        c = r["cible"]
        if not c or c == "inconnu":
            continue
        d = par_cible.setdefault(c, {"impressions": 0, "questions": 0,
                                     "position": None, "intentions": set()})
        d["impressions"] += r["impressions"] or 0
        d["questions"] += 1
        d["intentions"].add(r["intention"])
        pos = r["position"]
        # La meilleure position atteinte : c'est celle qui dit si Google a deja
        # compris de quoi parle la page, ou s'il la sert par defaut.
        if pos is not None and (d["position"] is None or pos < d["position"]):
            d["position"] = pos
    return par_cible


def a_relever(t):
    """Ce qu'une visite permettrait d'ecrire sur cette fiche.

    Rend une liste de libelles, vide si la fiche porte deja tout ce qu'une
    visite apporte. Une liste vide n'est pas un certificat d'exactitude : elle
    dit seulement que ce script n'a plus rien a proposer d'aller voir.
    """
    manques = [libelle for champ, libelle in A_RELEVER if not t.get(champ)]
    if not t.get(MESURE[0]):
        # Estime d'apres OSM, ou rien du tout : dans les deux cas, non mesure.
        manques.append("developpement estime" if t.get(MESURE[1])
                       else "developpement inconnu")
    return manques


def croise(par_cible, tracks):
    """La demande d'un cote, ce que la fiche dit de l'autre."""
    par_id = {t["id"]: t for t in tracks}

    # La demande communale ne se redistribue pas : elle se lit a cote.
    communes = {}
    for cible, d in par_cible.items():
        if cible.startswith("ville:"):
            communes[cible[len("ville:"):]] = d["impressions"]

    sites = []
    for cible, d in par_cible.items():
        if cible.startswith(("ville:", "dep:", "critere:")):
            continue
        t = par_id.get(cible)
        if t is None:
            # Une fiche demandee qui n'est plus dans tracks.json : supprimee
            # depuis, ou identifiant change. Le dire plutot que l'ecarter en
            # silence, c'est le genre d'ecart qui se rattrape mal.
            sites.append({"id": cible, "nom": None, "impressions": d["impressions"]})
            continue
        manques = a_relever(t)
        if not manques:
            continue
        sites.append({
            "id": t["id"],
            "nom": t.get("nom") or "",
            "ville": t.get("ville") or "",
            "dep": t.get("dep") or "",
            "lat": t.get("lat"), "lon": t.get("lon"),
            "impressions": d["impressions"],
            "questions": d["questions"],
            "position": d["position"],
            "intentions": sorted(d["intentions"]),
            "demande_commune": communes.get(slug(t.get("ville") or ""), 0),
            "a_relever": manques,
            "url": f"{SITE}/site/{t['id']}/",
        })
    sites.sort(key=lambda s: (-s["impressions"], s.get("nom") or ""))
    return sites


def montre(sites, limite, filtre=None):
    if not sites:
        # Deux vides tres differents, et les confondre ferait croire au travail
        # fini alors qu'on a seulement tape un code de departement inexistant.
        print(f"Aucun site demande dans « {filtre} »." if filtre else
              "Aucun site demande ne reste a visiter : toutes les fiches"
              " cherchees portent deja photos, avis, couloirs et mesure.")
        return
    total = sum(s["impressions"] for s in sites)
    print(f"{len(sites)} installations cherchees dont la fiche ne porte rien"
          f" de premiere main, {total} impressions cumulees.")
    print(f"Les {min(limite, len(sites))} plus demandees :\n")
    for s in sites[:limite]:
        if s.get("nom") is None:
            print(f" {s['impressions']:4} imp   {s['id']}"
                  "  (plus dans tracks.json : identifiant change ou site supprime)")
            continue
        pos = f"{s['position']:5.1f}" if s["position"] is not None else "    ?"
        com = f"  (+{s['demande_commune']} sur la commune)" if s["demande_commune"] else ""
        print(f" {s['impressions']:4} imp  pos {pos}  {s['nom'][:44]}")
        print(f"      {s['ville']} ({s['dep']}){com}   {s['id']}")
        print(f"      a relever : {', '.join(s['a_relever'])}")
    print("\nPreparer une tournee :  python3 scripts/demande_terrain.py --tournee")


def montre_tournee(sites, limite):
    """Ou une journee de terrain paie le plus.

    Un deplacement ne visite pas un site, il visite une region : le cout est
    dans le trajet, pas dans la piste. Regrouper la demande par departement dit
    donc quelque chose que la liste site par site cache — trois fiches muettes
    et cherchees dans le meme departement valent mieux qu'une seule ailleurs.
    """
    par_dep = {}
    for s in sites:
        if s.get("nom") is None:
            continue
        d = par_dep.setdefault(s["dep"], {"imp": 0, "sites": [], "communes": set()})
        d["imp"] += s["impressions"]
        d["sites"].append(s)
        d["communes"].add(s["ville"])
    classes = sorted(par_dep.items(), key=lambda kv: -kv[1]["imp"])[:limite]

    if not classes:
        print("Aucune fiche muette et cherchee : rien a mettre dans une tournee.")
        return
    print("Ou une journee de terrain paie le plus — demande cumulee par departement :\n")
    for dep, d in classes:
        print(f"  {dep or '??'}  {d['imp']:4} imp   {len(d['sites']):3} fiches muettes"
              f"   {len(d['communes'])} communes")
        for s in sorted(d["sites"], key=lambda x: -x["impressions"])[:3]:
            print(f"        {s['impressions']:3} imp  {s['nom'][:40]} — {s['ville']}")
    print("\nLe detail d'un departement :"
          "  python3 scripts/demande_terrain.py --dep <code>")


def main():
    ap = argparse.ArgumentParser(
        description="Les fiches que les gens cherchent et qu'une visite ferait parler.")
    ap.add_argument("--dep", help="ne garder qu'un departement (« 44 », « 2A »)")
    ap.add_argument("--tournee", action="store_true",
                    help="regrouper par departement plutot que site par site")
    ap.add_argument("--json", action="store_true", dest="en_json",
                    help="sortie machine complete, pour enchainer sur un autre script")
    ap.add_argument("--limite", type=int, default=20,
                    help="lignes affichees (sans effet sur --json, qui rend tout)")
    args = ap.parse_args()

    _, tracks = charge_tracks()
    sites = croise(demande(D1()), tracks)

    if args.dep:
        dep = args.dep.upper()
        sites = [s for s in sites if s.get("dep") == dep]

    if args.en_json:
        json.dump(sites, sys.stdout, ensure_ascii=False, indent=2)
        print()
    elif args.tournee:
        montre_tournee(sites, args.limite)
    else:
        montre(sites, args.limite, filtre=args.dep)


if __name__ == "__main__":
    main()
