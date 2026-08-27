#!/usr/bin/env python3
"""Cherche dans les marches publics les pistes que l'annuaire ignore ou date mal.

    python3 scripts/marches_publics.py
    python3 scripts/marches_publics.py --dep 74
    python3 scripts/marches_publics.py --depuis 2023-01-01 --json .work/marches.json

Le recensement du ministere est declaratif, et rien n'oblige une commune a le
tenir a jour. Thonon-les-Bains en donne la mesure : le stade de Vongy y est
decrit avec deux terrains de football et des travaux datant de 2012, alors
qu'une piste de huit couloirs homologuee FFA y a ete livree en 2022. L'annuaire
ne pouvait pas l'inventer.

Mais une piste, ca se paie. Depuis 2018, tout marche public au-dessus de
40 000 EUR doit etre publie en donnees ouvertes : les DECP disent qui a depense,
quand, combien, et pour quel objet. C'est le meme raisonnement que
pistes_absentes.py, par une autre porte — la depense plutot que la carte.

Ce que les DECP ne diront jamais : le nombre de couloirs, le revetement, les
agres. L'objet du marche tient en une ligne de majuscules, « PISTE
D'ATHLETISME », et le cahier des charges qui contient les details vit sur le
profil d'acheteur pendant la consultation puis disparait — rien ne l'archive,
rien ne le centralise. Ce script est donc un instrument de datation et de
detection, pas de description.

Chaque ligne est une piste *a verifier*, jamais une piste prouvee. « EQUIPEMENT
ATHLETISME » a 60 000 EUR achete peut-etre des javelots ; « REFECTION » peut
ne concerner qu'un sautoir. Ce qui sort d'ici dit ou regarder, et le reste du
travail commence : la mairie, l'orthophoto, et pour finir quelqu'un sur place.

Source : Donnees Essentielles de la Commande Publique, Licence Ouverte 2.0
https://data.economie.gouv.fr/
"""
import argparse
import json
import os
import sys
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TRACKS = os.path.join(ROOT, "data", "tracks.json")

API = "https://data.economie.gouv.fr/api/explore/v2.1/catalog/datasets"
# Pour nommer une commune que l'annuaire ne connait pas : sans elle, le cas le
# plus interessant — on paie une piste la ou l'annuaire n'en connait aucune —
# serait indiscernable d'un code mal saisi.
API_GEO = "https://geo.api.gouv.fr"
# L'acheteur, quand le code de lieu ne suffit pas. Nature juridique 7210 =
# commune : dans ce cas le siege de l'acheteur est la commune des travaux neuf
# fois sur dix. Une agglomeration ou un departement, non — et on le dit.
API_SIRENE = "https://recherche-entreprises.api.gouv.fr/search"
NATURE_COMMUNE = "7210"
# Les deux arretes se suivent sans se recouvrir tout a fait : le jeu de 2019
# porte les marches anciens, celui de 2022 les recents. On lit les deux et on
# dedoublonne, plutot que de choisir et de perdre une annee.
JEUX = ("decp-2022-marches-valides", "decp-v3-marches-valides")
UA = {"User-Agent": "pistes-athle/1.0 (+https://pistes-athle.com)"}
PAGE = 100

# Mots de l'objet du marche. Volontairement etroits : « piste » seul ramene les
# pistes cyclables et les circuits de BMX, « stade » ramene le football. On
# prefere manquer un marche que noyer la liste — c'est une file de lecture
# humaine, pas un index.
MOTS = ("athlétisme", "sautoir", "tartan", "anneau de course",
        "piste d'athlé", "aire de lancer")
# Codes CPV des travaux d'installations sportives, en complement des mots :
# un marche peut s'appeler « LOT 3 - REVETEMENTS » et n'etre lisible que par la.
# Ils ratissent large — « installations sportives » couvre le padel comme
# l'anneau — d'ou le tri par signal et la liste d'exclusion ci-dessous.
CPV = ("45212200", "45212224", "45236110", "45236119")

# Sports qui ne sont pas de l'athletisme et qui remplissent ces memes codes CPV.
# Un marche pris par le CPV seul dont l'objet nomme l'un d'eux est ecarte : le
# filtre ne s'applique jamais aux marches pris par un mot d'athletisme, pour
# qu'un « refection de la piste d'athletisme et des courts de tennis » survive.
HORS_SUJET = ("padel", "tennis", "squash", "skate", "piscine", "bassin",
              "boulodrome", "petanque", "golf", "escalade", "equitation",
              "manege", "cyclable", "patinoire", "dojo", "vestiaire",
              "club house", "tribune", "eclairage", "billetterie")

# Comment un marche est entre dans la liste. L'objet vaut mieux que le CPV :
# le premier nomme l'athletisme, le second dit seulement « sport ».
PAR_OBJET = "objet"
PAR_CPV = "CPV seul"

# Verdicts, du plus actionnable au moins.
ABSENTE = "aucun site d'athletisme recense dans cette commune"
SANS_PISTE = "des sites recenses, mais aucun avec piste"
PERIMEE = "piste(s) recensee(s), mais plus anciennes que le marche"
A_JOUR = "l'annuaire connait deja des travaux aussi recents"
FLOU = "lieu d'execution trop imprecis pour conclure"

ORDRE = (ABSENTE, SANS_PISTE, PERIMEE, FLOU, A_JOUR)


def deaccent(s):
    return "".join(c for c in unicodedata.normalize("NFD", s or "")
                   if unicodedata.category(c) != "Mn").lower()


def insee_du_site(t):
    """Code INSEE de la commune ou le site a ete recense, ou None.

    Le numero d'installation du ministere encode le code INSEE d'origine :
    « I740110013 » vaut 74011. Un site cree par la communaute n'a pas de
    numero, donc pas de code."""
    i = t.get("id") or ""
    return i[1:6] if i.startswith("I") and len(i) == 10 else None


def charger_communes():
    """Index des communes de l'annuaire, par code INSEE et par code postal.

    Rend {cle: fiche}, ou fiche resume ce que l'annuaire sait de la commune :
    combien de sites, combien avec piste, et l'annee des travaux les plus
    recents qu'il connaisse."""
    with open(TRACKS, encoding="utf-8") as f:
        brut = json.load(f)
    km = brut["keymap"]
    sites = [{km.get(k, k): v for k, v in rec.items()} for rec in brut["tracks"]]

    par_commune = {}
    for t in sites:
        cle = (t.get("dep"), deaccent(t.get("ville")))
        f = par_commune.setdefault(cle, {
            "ville": t.get("ville"), "dep": t.get("dep"),
            "sites": 0, "pistes": 0, "annee_max": None,
            "insee": set(), "cp": set(),
        })
        f["sites"] += 1
        f["pistes"] += 1 if t.get("piste") else 0
        for champ in ("renovation", "annee"):
            a = t.get(champ)
            if a and (f["annee_max"] is None or a > f["annee_max"]):
                f["annee_max"] = a
        if insee_du_site(t):
            f["insee"].add(insee_du_site(t))
        if t.get("cp"):
            f["cp"].add(str(t["cp"]))

    par_insee, par_cp, par_nom = {}, {}, {}
    for f in par_commune.values():
        for c in f["insee"]:
            par_insee[c] = f
        for c in f["cp"]:
            par_cp.setdefault(c, []).append(f)
        par_nom.setdefault((f["dep"], deaccent(f["ville"])), []).append(f)
    return {"insee": par_insee, "cp": par_cp, "nom": par_nom}, len(sites)


def fondre(lot, nom, insee):
    """Resume les communes d'un meme nom en une seule fiche — les
    arrondissements de Lyon ne font qu'une ville pour ce qu'on en fait ici."""
    dep = insee[:3] if insee[:2] in ("97", "98") else insee[:2]
    return {"ville": nom, "dep": dep,
            "sites": sum(f["sites"] for f in lot),
            "pistes": sum(f["pistes"] for f in lot),
            "annee_max": max((f["annee_max"] for f in lot
                              if f["annee_max"] is not None), default=None)}


def par_le_nom(index, dep, nom):
    """Les communes de l'annuaire portant ce nom dans ce departement.

    Le rattachement par code echoue sur Paris, Lyon et Marseille : le marche
    porte le code de la commune, l'annuaire range ses sites par arrondissement.
    On rattrape donc au nom, prefixe compris — « Lyon » retrouve « Lyon 8e
    Arrondissement »."""
    n = deaccent(nom)
    exact = index["nom"].get((dep, n))
    if exact:
        return exact
    return [f for (d, autre), lot in index["nom"].items() if d == dep
            and autre.startswith(n) for f in lot]


def interroger(jeu, ou, timeout=60):
    """Toutes les lignes d'un jeu DECP repondant a `ou`, page par page."""
    lignes, offset = [], 0
    while True:
        params = urllib.parse.urlencode({
            "where": ou, "limit": PAGE, "offset": offset,
            "select": "objet,codecpv,montant,datenotification,"
                      "lieuexecution_code,acheteur_id",
        })
        req = urllib.request.Request(f"{API}/{jeu}/records?{params}", headers=UA)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            d = json.load(r)
        lignes.extend(d.get("results") or [])
        total = d.get("total_count") or 0
        offset += PAGE
        # L'API plafonne la pagination ; au-dela on s'arrete et on le dit.
        if offset >= total or offset >= 10000:
            if offset < total:
                print(f"[!] {jeu} : {total} lignes annoncees, {len(lignes)} lues "
                      f"(plafond de pagination)")
            return lignes


def clause(depuis):
    mots = " or ".join(f"objet like \"{m}\"" for m in MOTS)
    cpv = " or ".join(f"codecpv like \"{c}%\"" for c in CPV)
    ou = f"(({mots}) or ({cpv}))"
    return f"{ou} and datenotification >= date'{depuis}'" if depuis else ou


def rassembler(depuis):
    vus, lignes = set(), []
    for jeu in JEUX:
        try:
            recus = interroger(jeu, clause(depuis))
        except (urllib.error.URLError, OSError, ValueError) as e:
            print(f"[!] {jeu} injoignable ({e}) : ce jeu est saute")
            continue
        neufs = 0
        for r in recus:
            cle = (r.get("objet"), r.get("montant"), r.get("datenotification"),
                   r.get("acheteur_id"))
            if cle in vus:
                continue
            vus.add(cle)
            r["_jeu"] = jeu
            lignes.append(r)
            neufs += 1
        print(f"-> {jeu} : {len(recus)} ligne(s), {neufs} nouvelle(s)")
    return lignes


_communes = {}


def commune_officielle(code, timeout=15):
    """Nom de la commune portant ce code INSEE ou ce code postal, ou None.

    Rend None des qu'il y a doute : un code postal qui couvre plusieurs
    communes ne designe personne, et un code de departement encore moins."""
    if code in _communes:
        return _communes[code]
    nom = None
    for chemin in (f"/communes/{code}?fields=nom,code",
                   f"/communes?codePostal={code}&fields=nom,code"):
        try:
            req = urllib.request.Request(API_GEO + chemin, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                d = json.load(r)
        except (urllib.error.URLError, OSError, ValueError):
            continue
        if isinstance(d, dict) and d.get("nom"):
            nom = (d["nom"], d["code"])
            break
        if isinstance(d, list) and len(d) == 1:
            nom = (d[0]["nom"], d[0]["code"])
            break
    _communes[code] = nom
    return nom


_acheteurs = {}


def acheteur(siret, timeout=15):
    """(nom, commune, code INSEE, est_une_commune) de l'acheteur, ou None."""
    if not siret:
        return None
    if siret in _acheteurs:
        return _acheteurs[siret]
    res = None
    try:
        url = f"{API_SIRENE}?{urllib.parse.urlencode({'q': siret, 'limite_matching_etablissements': 1})}"
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
            d = json.load(r)
        for e in d.get("results", [])[:1]:
            et = (e.get("matching_etablissements") or [{}])[0]
            res = (e.get("nom_complet"), et.get("libelle_commune"),
                   et.get("commune"), e.get("nature_juridique") == NATURE_COMMUNE)
    except (urllib.error.URLError, OSError, ValueError):
        res = None
    _acheteurs[siret] = res
    return res


def situer(ligne, index):
    """Commune de l'annuaire visee par ce marche, et comment on l'a trouvee.

    PIEGE : `lieuexecution_code` melange les codes INSEE et les codes postaux.
    Annecy saisit « 74000 », son code postal, la ou son code INSEE est 74010 ;
    Thonon saisit « 74200 ». On essaie donc l'INSEE, puis le code postal, et on
    dit laquelle des deux lectures a repondu — un code postal peut couvrir
    plusieurs communes, et alors on ne conclut pas."""
    code = (ligne.get("lieuexecution_code") or "").strip()
    if code in index["insee"]:
        return index["insee"][code], "code INSEE"
    candidates = index["cp"].get(code) or []
    if len(candidates) == 1:
        return candidates[0], "code postal"
    if len(candidates) > 1:
        noms = ", ".join(sorted(c["ville"] for c in candidates)[:4])
        return None, f"code postal partage ({noms})"
    if not code:
        return None, "lieu non renseigne"
    # Rien dans l'annuaire : la commune existe-t-elle seulement ? Si oui, c'est
    # le cas qui vaut le detour — on depense sur une piste la ou l'annuaire n'a
    # aucun site d'athletisme.
    officielle = commune_officielle(code)
    # PIEGE : `lieuexecution_code` melange codes INSEE et codes postaux, et un
    # code postal saisi la ou l'INSEE etait attendu tombe parfois sur une vraie
    # petite commune a l'autre bout du pays — d'ou des lignes absurdes, un
    # village de deux cents ames qui refait une piste a 1,4 million. On croise
    # donc avec l'acheteur : si c'est une commune et qu'elle ne correspond pas,
    # on ne conclut pas.
    ach = acheteur(ligne.get("acheteur_id"))
    if ach and ach[3] and ach[2]:
        nom_a, insee_a = ach[1], ach[2]
        if not officielle or officielle[1] != insee_a:
            if insee_a in index["insee"]:
                return index["insee"][insee_a], "acheteur (commune)"
            lot = par_le_nom(index, insee_a[:3] if insee_a[:2] in ("97", "98")
                             else insee_a[:2], nom_a or "")
            if lot:
                return fondre(lot, nom_a, insee_a), "acheteur (commune), par le nom"
            if officielle:
                return None, (f"code {code} lu « {officielle[0]} » mais l'acheteur "
                              f"est {nom_a}")
    if not officielle:
        return None, "code inconnu"
    nom, insee = officielle
    dep = insee[:3] if insee[:2] in ("97", "98") else insee[:2]
    # Le nom rattrape ce que le code a manque : arrondissements, et communes
    # dont l'annuaire ne connait pas le code INSEE faute de numero ministeriel.
    lot = par_le_nom(index, dep, nom)
    if lot:
        return fondre(lot, nom, insee), "nom de commune"
    return {"ville": nom, "dep": dep, "sites": 0, "pistes": 0,
            "annee_max": None}, "code resolu, commune absente de l'annuaire"


def signal(ligne):
    """Ce qui a fait entrer ce marche : un mot de l'objet, ou le seul CPV."""
    objet = deaccent(ligne.get("objet"))
    return PAR_OBJET if any(deaccent(m) in objet for m in MOTS) else PAR_CPV


def hors_sujet(ligne):
    """Vrai si ce marche, pris par le CPV seul, nomme un autre sport."""
    if signal(ligne) == PAR_OBJET:
        return False
    objet = deaccent(ligne.get("objet"))
    return any(m in objet for m in HORS_SUJET)


def juger(ligne, fiche):
    if fiche is None:
        return FLOU
    if fiche["sites"] == 0:
        return ABSENTE
    if fiche["pistes"] == 0:
        return SANS_PISTE
    annee = int((ligne.get("datenotification") or "0")[:4] or 0)
    connu = fiche["annee_max"]
    # Sans annee connue, l'annuaire ne peut pas prouver qu'il est a jour :
    # le doute profite a la relecture.
    if connu is None or connu < annee:
        return PERIMEE
    return A_JOUR


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--depuis", default="2020-01-01",
                    help="date de notification minimale (AAAA-MM-JJ)")
    ap.add_argument("--dep", help="ne garder qu'un departement, ex. 74")
    ap.add_argument("--montant-min", type=float, default=0.0,
                    help="ignorer les marches sous ce montant")
    ap.add_argument("--tout", action="store_true",
                    help="montrer aussi les communes deja a jour et les marches "
                         "pris par le CPV seul qui nomment un autre sport")
    ap.add_argument("--large", action="store_true",
                    help="ajouter les marches pris par le seul code CPV. Le filet "
                         "est large — « installations sportives » couvre le padel "
                         "comme l'anneau — et la liste devient une file de lecture "
                         "beaucoup plus longue pour tres peu de pistes en plus.")
    ap.add_argument("--json", help="ecrit le releve dans ce fichier")
    args = ap.parse_args()

    index, n_sites = charger_communes()
    print(f"-> annuaire : {n_sites} sites, {len(index['insee'])} code(s) INSEE, "
          f"{len(index['cp'])} code(s) postal(aux), {len(index['nom'])} commune(s)")

    lignes = rassembler(args.depuis)
    if not lignes:
        print("Aucun marche ne repond : rien a relire.")
        return 0

    releve, ecartes = [], 0
    for l in lignes:
        if (l.get("montant") or 0) < args.montant_min:
            continue
        sig = signal(l)
        # Par defaut, seuls les marches dont l'objet nomme l'athletisme. Le CPV
        # a ete essaye sur la Haute-Savoie : il ajoute des lots de peinture, des
        # pumptracks et des courts de padel, et pas une piste que l'objet
        # n'avait pas deja nommee. Il reste disponible, mais il se demande.
        if sig != PAR_OBJET and not args.large:
            ecartes += 1
            continue
        if hors_sujet(l) and not args.tout:
            ecartes += 1
            continue
        fiche, comment = situer(l, index)
        if args.dep and (fiche or {}).get("dep") != args.dep:
            continue
        releve.append({
            "date": l.get("datenotification"),
            "montant": l.get("montant"),
            "objet": " ".join((l.get("objet") or "").split()),
            "cpv": l.get("codecpv"),
            "code_lieu": l.get("lieuexecution_code"),
            "commune": (fiche or {}).get("ville"),
            "dep": (fiche or {}).get("dep"),
            "rattachement": comment,
            "signal": sig,
            "sites_connus": (fiche or {}).get("sites"),
            "pistes_connues": (fiche or {}).get("pistes"),
            "derniers_travaux_connus": (fiche or {}).get("annee_max"),
            "verdict": juger(l, fiche),
        })

    par_verdict = {}
    for r in releve:
        par_verdict.setdefault(r["verdict"], []).append(r)

    for verdict in ORDRE:
        lot = par_verdict.get(verdict) or []
        if not lot or (verdict == A_JOUR and not args.tout):
            continue
        print(f"\n{'=' * 74}\n{verdict.upper()}  ({len(lot)})\n{'=' * 74}")
        # L'objet d'abord, le CPV ensuite ; du plus recent au plus ancien.
        for r in sorted(lot, key=lambda x: (x["signal"] == PAR_OBJET,
                                            x["date"] or ""), reverse=True):
            lieu = f"{r['commune']} ({r['dep']})" if r["commune"] else \
                   f"code {r['code_lieu']} — {r['rattachement']}"
            montant = f"{r['montant']:,.0f}".replace(",", " ") if r["montant"] else "?"
            print(f"\n  {r['date']}  {montant:>12} EUR   {lieu}")
            print(f"    {r['objet'][:88]}")
            detail = [f"trouve par {r['signal']}"]
            if r["cpv"]:
                detail.append(f"CPV {r['cpv']}")
            if r["commune"]:
                detail.append(f"rattache par {r['rattachement']}")
                detail.append(f"{r['sites_connus']} site(s) dont "
                              f"{r['pistes_connues']} avec piste")
                detail.append("derniers travaux connus : "
                              f"{r['derniers_travaux_connus'] or 'aucun'}")
            print(f"    {' · '.join(detail)}")

    print(f"\n{'=' * 74}")
    if ecartes:
        print(f"  {ecartes:4d}  ecarte(s) : pris par le seul code CPV, sans que "
              f"l'objet nomme l'athletisme (--large pour les voir)")
    for verdict in ORDRE:
        n = len(par_verdict.get(verdict) or [])
        if n:
            print(f"  {n:4d}  {verdict}")

    if args.json:
        os.makedirs(os.path.dirname(os.path.abspath(args.json)), exist_ok=True)
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump({"genere": date.today().isoformat(),
                       "depuis": args.depuis, "marches": releve},
                      f, ensure_ascii=False, indent=1)
        print(f"-> {args.json}")

    print("\nAucune de ces lignes n'est une piste tant que personne ne l'a vue.\n"
          "Un marche dit qu'on a depense, pas ce qui a ete construit : l'objet\n"
          "tient en une ligne, et le cahier des charges n'est archive nulle part.\n"
          "La suite se joue sur le site de la mairie, sur l'orthophoto, puis sur place.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
