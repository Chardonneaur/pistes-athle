#!/usr/bin/env python3
"""
Mesurer ce que l'IA generative de Google fait au trafic du site.

CE QU'IL FAUT SAVOIR AVANT DE LIRE UN SEUL CHIFFRE

Search Console publie depuis le 3 juin 2026 un rapport « IA generative », qui
couvre les AI Overviews et l'AI Mode. Ce rapport n'existe QUE dans l'interface.
Il ne donne que des impressions — ni clic, ni CTR, ni position, ni requete — et
l'API ne l'expose pas du tout : le parametre « type » s'arrete a googleNews, et
aucune valeur de « searchAppearance » ne designe une surface IA. Verifie le
1er septembre 2026 contre le document de decouverte de l'API, et re-verifiable
a tout moment par « --sonde » : le jour ou Google ouvrira, la sonde le dira.

Ce script ne pretend donc pas lire un chiffre que Google ne donne pas. Il
mesure autre chose, qui est mesurable et qui repond a la meme question :

  L'IA de Google prend-elle les clics que ce site gagnait ?

LA MESURE : L'EROSION DU CLIC A RANG CONSTANT

Une AI Overview ne fait pas perdre de position. Elle s'insere au-dessus du
resultat, repond a la place de la page, et le resultat reste ou il etait avec
ses impressions intactes — mais sans le clic. C'est une signature reconnaissable
et c'est la seule que les donnees publiees permettent de suivre : position
stable ou meilleure, impressions stables ou en hausse, clics en baisse.

Perdre des clics EN reculant, au contraire, n'est pas un effet de l'IA : c'est
une perte de rang ordinaire. Le script separe les deux, parce que les confondre
ferait accuser l'IA de tout ce qui va mal.

LE PARTAGE QUI REND LA MESURE LISIBLE

Une AI Overview se declenche sur une question, pas sur un nom propre. Quelqu'un
qui tape « cosec ostwald » cherche une adresse et Google la lui donne en lien ;
quelqu'un qui tape « piste d'athletisme ouverte au public toulouse » pose une
question, et c'est la que l'IA repond a la place du site.

D'ou les deux familles, construites avec le meme classement d'intentions que le
releve quotidien (releve_gsc.intention) :

  NAVIGATIONNEL   « fiche » — le nom d'un stade tape tel quel. Temoin.
  INFORMATIONNEL  tout le reste — acces, revetement, horaires, distance,
                  existence... Exposé.

Le temoin est la piece maitresse du montage. Si les deux familles perdent leurs
clics ensemble, la cause est ailleurs — saison, refonte, declassement. Si seul
l'informationnel s'effondre a rang constant, c'est l'IA. Sans temoin, n'importe
quelle baisse pourrait etre attribuee a n'importe quoi.

CE QUE CE SCRIPT NE PROUVERA JAMAIS

Il ne voit pas si une AI Overview s'est affichee. Il voit la trace qu'elle
laisse. Deux impressions identiques peuvent recouvrir une page IA presente ou
absente, et rien ici ne les distingue. Le rapport de l'interface, lui, sait le
dire — mais seulement en impressions, et seulement a la main : d'ou --csv, qui
range son export a cote de la mesure au lieu de le laisser dans un onglet.

Usage :
  python3 scripts/generative_gsc.py                  # la mesure, 28 j contre 28 j
  python3 scripts/generative_gsc.py --jours 90       # fenetres plus larges
  python3 scripts/generative_gsc.py --sonde          # l'API a-t-elle ouvert ?
  python3 scripts/generative_gsc.py --csv export.csv # joint le rapport IA de l'interface
"""

import argparse
import csv
import datetime
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from releve_gsc import PROPRIETE, cible, intention, jeton_google   # noqa: E402

# ---------------------------------------------------------------------------
# PLAFONDS — memes principes que releve_gsc.py : des butoirs, pas des reglages.
# ---------------------------------------------------------------------------
MAX_APPELS_GSC = 8          # 2 fenetres, paginees ; le besoin constate est de 2
LIGNES_PAR_APPEL = 25000

# Latence de la Search Console : trois jours. Une fenetre qui va jusqu'a
# aujourd'hui compare du complet a de l'incomplet et invente une baisse.
LATENCE_JOURS = 3

# En dessous, on n'annonce rien. Un CTR calcule sur dix clics bouge de moitie
# quand un seul visiteur change d'avis : ce n'est pas une mesure, c'est un
# tirage. Le script prefere dire « trop peu » que produire un chiffre qu'on
# citera ensuite comme un fait.
CLICS_MINIMUM = 30

API = ("https://www.googleapis.com/webmasters/v3/sites/"
       + urllib.parse.quote(PROPRIETE, safe="") + "/searchAnalytics/query")

DECOUVERTE = "https://searchconsole.googleapis.com/$discovery/rest?version=v1"

# Ce que Google appellerait une surface IA s'il en ouvrait une. Aucune de ces
# valeurs n'est documentee : la liste est une hypothese, et c'est assume — la
# sonde ne cherche pas a deviner juste, elle cherche a ne pas rater le jour ou
# quelque chose s'ouvre.
TYPES_TENTES = ["aiMode", "AI_MODE", "generativeAi", "GENERATIVE_AI",
                "aiOverview", "AI_OVERVIEW", "discoverAi"]
APPARENCES_TENTEES = ["AI_OVERVIEW", "AI_OVERVIEWS", "AI_MODE", "GENERATIVE_AI",
                      "SGE", "AI", "AI_ANSWER"]


# ---------------------------------------------------------------------------
# Lire Google
# ---------------------------------------------------------------------------

class Compteur:
    """Le nombre d'appels, porte a la main plutot que cache dans un global.

    Le plafond doit etre verifiable en lisant le code qui appelle, pas en
    faisant confiance a une variable de module qu'un autre script pourrait
    avoir deja consommee.
    """

    def __init__(self):
        self.n = 0


def appel(jeton, corps, compteur):
    if compteur.n >= MAX_APPELS_GSC:
        sys.exit(f"PLAFOND : {MAX_APPELS_GSC} appels d'API atteints, on s'arrete la.")
    compteur.n += 1
    req = urllib.request.Request(API, data=json.dumps(corps).encode(), headers={
        "Authorization": "Bearer " + jeton, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=90) as r:
        return json.load(r)


def total(jeton, debut, fin, compteur):
    """Le total de la fenetre, sans aucune dimension.

    Sans dimension, Google ne peut rien anonymiser : il rend l'agregat entier.
    C'est le seul chiffre du script qui couvre 100 % du trafic.
    """
    lignes = appel(jeton, {"startDate": str(debut), "endDate": str(fin),
                           "dimensions": [], "rowLimit": 1}, compteur).get("rows", [])
    if not lignes:
        return {"clics": 0, "imp": 0, "pos": 0.0, "ctr": 0.0}
    l = lignes[0]
    imp = int(l["impressions"])
    return {"clics": int(l["clicks"]), "imp": imp,
            "pos": round(float(l.get("position", 0.0)), 1),
            "ctr": (int(l["clicks"]) / imp) if imp else 0.0}


def couples(jeton, debut, fin, compteur):
    """Les couples (requete, page) d'une fenetre, pagines sous plafond."""
    lignes, depart = [], 0
    while True:
        lot = appel(jeton, {
            "startDate": str(debut), "endDate": str(fin),
            "dimensions": ["query", "page"],
            "rowLimit": LIGNES_PAR_APPEL, "startRow": depart,
        }, compteur).get("rows", [])
        lignes.extend(lot)
        if len(lot) < LIGNES_PAR_APPEL:
            return lignes
        depart += LIGNES_PAR_APPEL


# ---------------------------------------------------------------------------
# La sonde : l'API s'est-elle ouverte ?
# ---------------------------------------------------------------------------

def sonde(jeton):
    """Redemande a Google, aujourd'hui, ce qu'il refusait hier.

    Cette fonction existe parce qu'une limite d'API notee dans un document
    devient fausse sans prevenir, et qu'une limite fausse coute plus cher qu'une
    limite absente : elle empeche de chercher. La sonde est donc le seul endroit
    du projet ou l'on a le droit d'affirmer « l'API ne le donne pas » — et elle
    le re-verifie a chaque fois qu'on le lui demande.
    """
    print("Sonde de l'API Search Console — ce que Google accepte aujourd'hui\n")

    print("  1. Le document de decouverte (la liste officielle des valeurs)")
    try:
        with urllib.request.urlopen(DECOUVERTE, timeout=60) as r:
            doc = json.load(r)
        req = doc["schemas"]["SearchAnalyticsQueryRequest"]["properties"]
        types = req["type"]["enum"]
        dims = doc["schemas"]["ApiDimensionFilter"]["properties"]["dimension"]["enum"]
        print(f"     type       : {', '.join(types)}")
        print(f"     dimensions : {', '.join(dims)}")
        ouvert = [t for t in types if "AI" in t.upper() or "GENERATIV" in t.upper()]
        print(f"     -> surface IA declaree : {ouvert or 'AUCUNE'}")
    except urllib.error.URLError as e:
        print(f"     injoignable ({e}) — la sonde continue sur les essais directs")
        ouvert = []

    print("\n  2. Les essais directs, au cas ou une valeur existerait sans etre publiee")
    compteur = Compteur()
    base = {"startDate": str(datetime.date.today() - datetime.timedelta(days=30)),
            "endDate": str(datetime.date.today()), "rowLimit": 1}
    trouve = []
    for t in TYPES_TENTES:
        corps = dict(base, dimensions=["date"], type=t)
        try:
            appel(jeton, corps, compteur)
            print(f"     type={t:14s} ACCEPTE  <-- l'API s'est ouverte")
            trouve.append("type=" + t)
        except urllib.error.HTTPError as e:
            print(f"     type={t:14s} refuse ({e.code})")
        compteur.n = 0            # la sonde ne consomme pas le budget de mesure

    for a in APPARENCES_TENTEES:
        corps = dict(base, dimensions=[], dimensionFilterGroups=[
            {"filters": [{"dimension": "searchAppearance",
                          "operator": "equals", "expression": a}]}])
        try:
            appel(jeton, corps, compteur)
            print(f"     searchAppearance={a:14s} ACCEPTE  <-- l'API s'est ouverte")
            trouve.append("searchAppearance=" + a)
        except urllib.error.HTTPError as e:
            print(f"     searchAppearance={a:14s} refuse ({e.code})")
        compteur.n = 0

    print()
    if trouve or ouvert:
        print("L'API EXPOSE MAINTENANT UNE SURFACE IA : " + ", ".join(trouve + ouvert))
        print("Il faut reecrire ce script pour lire le chiffre au lieu de sa trace,")
        print("et corriger docs/mesurer-le-trafic-des-ia.md, qui affirme le contraire.")
    else:
        print("Rien n'a change : le rapport « IA generative » reste dans l'interface")
        print("seule, en impressions seules. La mesure indirecte garde donc son sens.")
        print("Interface : Search Console > Performances > Recherche generative par IA")
    return 0


# ---------------------------------------------------------------------------
# La mesure
# ---------------------------------------------------------------------------

NAVIGATIONNEL = "fiche"


def famille(requete, page):
    """« temoin » ou « expose », selon que la requete nomme ou demande.

    On reutilise le classement du releve quotidien plutot que d'en ecrire un
    second : deux classements qui derivent l'un de l'autre finissent par ne plus
    dire la meme chose, et personne ne s'en apercoit avant d'avoir conclu.
    """
    i = intention(requete)
    if i == "autre":
        i = "existence" if cible(page) == "inconnu" else NAVIGATIONNEL
    return ("temoin" if i == NAVIGATIONNEL else "expose"), i


def agrege(lignes):
    """Additionne par famille, par intention, et par couple."""
    fam = {"temoin": {"clics": 0, "imp": 0, "pos": 0.0},
           "expose": {"clics": 0, "imp": 0, "pos": 0.0}}
    par_intention, par_couple = {}, {}
    for l in lignes:
        requete, page = l["keys"][0], l["keys"][1]
        f, i = famille(requete, page)
        clics, imp, pos = int(l["clicks"]), int(l["impressions"]), float(l["position"])
        for cible_dict, cle in ((fam, f), (par_intention, i)):
            e = cible_dict.setdefault(cle, {"clics": 0, "imp": 0, "pos": 0.0})
            e["clics"] += clics
            e["imp"] += imp
            e["pos"] += pos * imp          # moyenne ponderee par les impressions
        e = par_couple.setdefault((requete, page),
                                  {"clics": 0, "imp": 0, "pos": 0.0, "famille": f})
        e["clics"] += clics
        e["imp"] += imp
        e["pos"] += pos * imp
    for d in (fam, par_intention, par_couple):
        for e in d.values():
            e["pos"] = round(e["pos"] / e["imp"], 1) if e["imp"] else 0.0
            e["ctr"] = e["clics"] / e["imp"] if e["imp"] else 0.0
    return fam, par_intention, par_couple


def pourcent(x):
    return f"{100 * x:5.2f} %"


def ligne_famille(nom, avant, apres):
    """Une ligne avant/apres, qui refuse de soustraire a partir de rien.

    Une fenetre sans impression n'a pas un CTR de zero : elle n'en a pas. Ecrire
    « +0,76 pt » quand la fenetre temoin est vide fabrique une progression qui
    n'a jamais eu lieu, et c'est exactement le chiffre qu'on recopierait.
    """
    tete = (f"  {nom:12s} {avant['imp']:6d} -> {apres['imp']:6d} imp   "
            f"{avant['clics']:4d} -> {apres['clics']:4d} clics   ")
    if not avant["imp"]:
        print(tete + f"CTR      ? -> {pourcent(apres['ctr'])}          "
                     f"pos     ? -> {apres['pos']:5.1f}"
                     "        (rien a comparer)")
        return
    d_ctr = apres["ctr"] - avant["ctr"]
    d_pos = apres["pos"] - avant["pos"]
    print(tete + f"CTR {pourcent(avant['ctr'])} -> {pourcent(apres['ctr'])} "
                 f"({100 * d_ctr:+.2f})   "
                 f"pos {avant['pos']:5.1f} -> {apres['pos']:5.1f} ({d_pos:+.1f})")


def mesure(jeton, jours):
    fin = datetime.date.today() - datetime.timedelta(days=LATENCE_JOURS)
    debut = fin - datetime.timedelta(days=jours - 1)
    fin_avant = debut - datetime.timedelta(days=1)
    debut_avant = fin_avant - datetime.timedelta(days=jours - 1)

    compteur = Compteur()
    apres_l = couples(jeton, debut, fin, compteur)
    avant_l = couples(jeton, debut_avant, fin_avant, compteur)

    print(f"Fenetre recente : {debut} -> {fin}   ({len(apres_l)} couples)")
    print(f"Fenetre temoin  : {debut_avant} -> {fin_avant}   ({len(avant_l)} couples)")

    # Le total du site, avant tout decoupage. Il faut le poser en premier parce
    # qu'il ne souffre pas l'anonymisation : Google tait les requetes rares mais
    # compte leurs impressions dans le total. Sur ce site, 84 % des impressions
    # n'ont pas de requete nommee — tout ce qui suit dans ce rapport ne porte
    # donc que sur la partie emergee, et l'ecart entre les deux lignes ci-dessous
    # est la mesure de ce qu'on ne verra jamais.
    tot_a = total(jeton, debut_avant, fin_avant, compteur)
    tot_b = total(jeton, debut, fin, compteur)
    print(f"                  {compteur.n} appels d'API, la Search Console accuse "
          f"{LATENCE_JOURS} jours de latence\n")

    print("TOUT LE SITE — la seule ligne qui ne souffre pas l'anonymisation")
    ligne_famille("total", tot_a, tot_b)
    nomme_a = sum(int(l["impressions"]) for l in avant_l)
    nomme_b = sum(int(l["impressions"]) for l in apres_l)
    for etiquette, nomme, tot in (("temoin", nomme_a, tot_a), ("recente", nomme_b, tot_b)):
        part = f"{100 * nomme / tot['imp']:.0f} %" if tot["imp"] else "?"
        print(f"    fenetre {etiquette:8s} : {nomme} impressions sur {tot['imp']} "
              f"portent une requete nommee ({part})")
    print()

    fam_a, int_a, cpl_a = agrege(avant_l)
    fam_b, int_b, cpl_b = agrege(apres_l)

    print("LES DEUX FAMILLES")
    print("  temoin = le nom d'un stade tape tel quel ; expose = une question posee\n")
    ligne_famille("temoin", fam_a["temoin"], fam_b["temoin"])
    ligne_famille("expose", fam_a["expose"], fam_b["expose"])

    print("\nPAR INTENTION (fenetre recente)")
    for nom in sorted(set(int_a) | set(int_b),
                      key=lambda n: -int_b.get(n, {"imp": 0})["imp"]):
        a = int_a.get(nom, {"clics": 0, "imp": 0, "pos": 0.0, "ctr": 0.0})
        b = int_b.get(nom, {"clics": 0, "imp": 0, "pos": 0.0, "ctr": 0.0})
        ligne_famille(nom, a, b)

    # Les couples qui portent la signature : rang tenu, clic perdu.
    print("\nCOUPLES A SIGNATURE — position tenue ou gagnee, impressions tenues,"
          " clics perdus")
    suspects = []
    for cle, b in cpl_b.items():
        a = cpl_a.get(cle)
        if not a or a["clics"] == 0:
            continue                       # sans clic avant, rien a perdre
        if b["pos"] > a["pos"] + 0.5:
            continue                       # a recule : c'est du rang, pas de l'IA
        if b["imp"] < a["imp"] * 0.8:
            continue                       # moins vu : la demande a baisse
        if b["clics"] >= a["clics"]:
            continue
        suspects.append((a["clics"] - b["clics"], cle, a, b))
    if not suspects:
        print("  aucun. Aucune requete de la fenetre precedente n'a garde son rang"
              " et ses impressions en perdant ses clics.")
    for perdu, (requete, page), a, b in sorted(suspects, reverse=True)[:20]:
        print(f"  -{perdu} clic(s)  « {requete} »")
        print(f"        {a['clics']}->{b['clics']} clics, {a['imp']}->{b['imp']} imp,"
              f" pos {a['pos']}->{b['pos']}   {page}")

    # Le verdict, et son refus de conclure.
    print("\nVERDICT")
    if not tot_a["imp"]:
        print("  RIEN A COMPARER : la fenetre temoin est vide. La propriete n'a pas")
        print(f"  encore {2 * jours} jours d'historique — la Search Console ne remonte")
        print("  qu'a sa verification. Rien a corriger : il faut attendre. La mesure")
        print("  deviendra lisible d'elle-meme, Google gardant seize mois d'historique.")
        return
    clics = fam_a["expose"]["clics"] + fam_b["expose"]["clics"]
    if clics < CLICS_MINIMUM:
        print(f"  TROP PEU POUR CONCLURE : {clics} clics informationnels sur les deux")
        print(f"  fenetres, il en faut {CLICS_MINIMUM}. Un CTR calcule la-dessus bouge")
        print("  de moitie quand un seul visiteur change d'avis. Les chiffres")
        print("  ci-dessus sont a lire, pas a citer.")
        return
    d_expose = fam_b["expose"]["ctr"] - fam_a["expose"]["ctr"]
    d_temoin = fam_b["temoin"]["ctr"] - fam_a["temoin"]["ctr"]
    ecart = d_expose - d_temoin
    print(f"  CTR informationnel {100 * d_expose:+.2f} pt, temoin"
          f" {100 * d_temoin:+.2f} pt, ecart {100 * ecart:+.2f} pt.")
    if ecart < -0.5:
        print("  L'informationnel perd ses clics plus vite que le navigationnel, a")
        print("  rang comparable. C'est la signature attendue d'une reponse rendue")
        print("  au-dessus du resultat. Ce n'est pas une preuve : c'est une trace.")
    elif d_expose < -0.5 and d_temoin < -0.5:
        print("  Les deux familles baissent ensemble : chercher ailleurs qu'a l'IA")
        print("  — saison, refonte, declassement general.")
    else:
        print("  Rien qui ressemble a une erosion propre a l'informationnel.")


# ---------------------------------------------------------------------------
# L'export de l'interface
# ---------------------------------------------------------------------------

def colonne(entetes, mots):
    for i, e in enumerate(entetes):
        n = e.strip().lower()
        if any(m in n for m in mots):
            return i
    return None


def joint_csv(jeton, chemin, jours):
    """Range l'export du rapport « IA generative » a cote des chiffres Web.

    L'export ne porte que des impressions : c'est tout ce que Google publie. Le
    joindre aux impressions Web de la meme periode donne la seule chose que
    l'interface ne montre nulle part — la PART de l'affichage d'une page qui
    passe par une surface IA. C'est un ratio d'impressions, jamais un ratio de
    clics : le rapport IA n'en contient pas.
    """
    with open(chemin, encoding="utf-8-sig", newline="") as f:
        echantillon = f.read(4096)
        f.seek(0)
        try:
            dialecte = csv.Sniffer().sniff(echantillon, delimiters=",;\t")
        except csv.Error:
            dialecte = csv.excel
        lignes = list(csv.reader(f, dialecte))
    if not lignes:
        sys.exit(f"{chemin} : fichier vide.")

    entetes = lignes[0]
    i_page = colonne(entetes, ("url", "page", "adresse"))
    i_imp = colonne(entetes, ("impression",))
    if i_page is None or i_imp is None:
        sys.exit(f"{chemin} : colonnes attendues introuvables.\n"
                 f"  entetes lus : {entetes}\n"
                 "  il faut une colonne d'URL et une colonne d'impressions "
                 "(export « Pages » du rapport).")

    ia = {}
    for l in lignes[1:]:
        if len(l) <= max(i_page, i_imp):
            continue
        page = l[i_page].strip()
        brut = l[i_imp].strip().replace(" ", "").replace(" ", "").replace(",", "")
        if not page.startswith("http") or not brut.isdigit():
            continue
        ia[page] = ia.get(page, 0) + int(brut)
    if not ia:
        sys.exit(f"{chemin} : aucune ligne exploitable.")

    fin = datetime.date.today() - datetime.timedelta(days=LATENCE_JOURS)
    debut = fin - datetime.timedelta(days=jours - 1)
    compteur = Compteur()
    web = {}
    for l in appel(jeton, {"startDate": str(debut), "endDate": str(fin),
                           "dimensions": ["page"], "rowLimit": LIGNES_PAR_APPEL},
                   compteur).get("rows", []):
        web[l["keys"][0]] = {"imp": int(l["impressions"]), "clics": int(l["clicks"])}

    print(f"Export IA : {len(ia)} pages, {sum(ia.values())} impressions")
    print(f"Web       : {debut} -> {fin}, {len(web)} pages, "
          f"{sum(v['imp'] for v in web.values())} impressions")
    print("\nATTENTION AUX PERIODES. L'export porte la periode choisie dans")
    print("l'interface ; la colonne Web ci-dessous porte la fenetre demandee ici")
    print(f"(--jours {jours}). Si les deux ne coincident pas, la part n'a pas de sens.\n")
    print(f"{'part IA':>8}  {'imp. IA':>8}  {'imp. web':>8}  {'clics web':>9}  page")
    for page, imp in sorted(ia.items(), key=lambda x: -x[1])[:40]:
        w = web.get(page)
        part = f"{100 * imp / w['imp']:6.1f} %" if w and w["imp"] else "     ?"
        print(f"{part:>8}  {imp:8d}  {w['imp'] if w else '?':>8}  "
              f"{w['clics'] if w else '?':>9}  {page}")
    absentes = [p for p in ia if p not in web]
    if absentes:
        print(f"\n{len(absentes)} page(s) vues par l'IA et absentes du rapport Web sur")
        print("cette fenetre — l'IA les affiche sans que la recherche classique le")
        print("fasse. C'est la ligne la plus interessante du lot :")
        for p in absentes[:10]:
            print(f"  {ia[p]:6d} imp IA   {p}")


# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--jours", type=int, default=28,
                    help="largeur de chaque fenetre, en jours (defaut : 28)")
    ap.add_argument("--sonde", action="store_true",
                    help="redemande a l'API si une surface IA s'est ouverte")
    ap.add_argument("--csv", metavar="FICHIER",
                    help="export « Pages » du rapport IA generative de l'interface")
    args = ap.parse_args()

    if args.jours < 7:
        sys.exit("--jours : moins de 7 jours ne compare que du bruit.")

    jeton = jeton_google()
    if args.sonde:
        return sonde(jeton)
    if args.csv:
        return joint_csv(jeton, args.csv, args.jours)
    return mesure(jeton, args.jours)


if __name__ == "__main__":
    main()
