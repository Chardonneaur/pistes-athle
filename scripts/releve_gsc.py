#!/usr/bin/env python3
"""
Releve quotidien de la Search Console, vers la base « pistes-athle-seo ».

Ce script est la moitie BETE de la boucle : il lit ce que Google a vu, en tire
une cle stable, et l'ecrit en base. Il ne juge rien, n'ecrit dans aucune fiche,
n'envoie aucun message. Le jugement — lire une fiche, chercher une source,
ouvrir une pull request — est fait separement, par un agent, sur la file que ce
script prepare.

Pourquoi cette coupure : la memoire de la boucle doit etre la piece la plus
fiable du montage. Le jour ou l'agent ne tourne pas, le releve, lui, doit avoir
eu lieu — sinon une requete apparue ce jour-la est perdue pour toujours, et
c'est precisement ce que la table sert a empecher.

Une ligne par QUESTION POSEE, jamais par formulation : la cle est
« <cible>|<intention> ». « piste tartan lorient » et « revetement stade
lorient » sont la meme question ; les compter deux fois rouvrirait chaque
matin un dossier deja traite.

DEPENSE : nulle, et pas par chance — voir les PLAFONDS ci-dessous.
  - API Search Console : gratuite, sans facturation possible. Quotas seulement.
  - D1 : le plan gratuit couvre 100 000 lignes ecrites par jour ; un passage en
    ecrit quelques dizaines.
  - GitHub Actions : gratuit et illimite sur un depot public.

Usage :
  python3 scripts/releve_gsc.py                 # fenetre de 7 jours
  python3 scripts/releve_gsc.py --amorcage      # tout l'historique, une fois
  python3 scripts/releve_gsc.py --simulation    # n'ecrit rien, montre tout
"""

import argparse
import datetime
import json
import os
import subprocess
import sys
import unicodedata
import urllib.error
import urllib.parse
import urllib.request

PROPRIETE = "sc-domain:pistes-athle.com"
BASE = "pistes-athle-seo"

# ---------------------------------------------------------------------------
# PLAFONDS
#
# Aucun de ces chiffres n'est une optimisation : ce sont des butoirs. Le script
# s'arrete net s'il les atteint, plutot que de continuer « juste un peu ». A
# l'echelle du site — 92 couples sur tout l'historique au 29 aout 2026 — ils
# sont deux ordres de grandeur au-dessus du besoin. Ils ne servent que le jour
# ou quelque chose derape : une boucle qui se relance, un parametre errone.
# ---------------------------------------------------------------------------
MAX_APPELS_GSC = 6          # appels d'API par execution, tout compris
LIGNES_PAR_APPEL = 25000    # maximum accepte par l'API
MAX_LIGNES = 50000          # au-dela, on s'arrete et on le dit
MAX_REQUETES_D1 = 40        # ecritures HTTP vers la base, par execution
LIGNES_PAR_ECRITURE = 100   # lignes groupees dans une seule requete SQL

JETON_MCP = os.path.expanduser("~/.config/gsc-mcp/token.json")


# ---------------------------------------------------------------------------
# Authentification Google
# ---------------------------------------------------------------------------

def jeton_google():
    """Un jeton d'acces, echange contre le refresh token.

    Trois variables d'environnement en production (secrets du depot), le
    fichier du serveur MCP local en repli, pour qu'un essai sur la machine ne
    demande aucune configuration.
    """
    cid = os.environ.get("GSC_CLIENT_ID")
    secret = os.environ.get("GSC_CLIENT_SECRET")
    refresh = os.environ.get("GSC_REFRESH_TOKEN")

    if not (cid and secret and refresh):
        if not os.path.exists(JETON_MCP):
            sys.exit("ERREUR : ni GSC_CLIENT_ID/GSC_CLIENT_SECRET/GSC_REFRESH_TOKEN\n"
                     f"         ni {JETON_MCP}. Voir docs/releve-search-console.md")
        with open(JETON_MCP) as f:
            t = json.load(f)
        cid, secret, refresh = t["client_id"], t["client_secret"], t["refresh_token"]

    corps = urllib.parse.urlencode({
        "client_id": cid, "client_secret": secret,
        "refresh_token": refresh, "grant_type": "refresh_token",
    }).encode()
    req = urllib.request.Request(
        "https://oauth2.googleapis.com/token", data=corps,
        headers={"Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)["access_token"]
    except urllib.error.HTTPError as e:
        sys.exit(f"ERREUR : Google refuse le refresh token ({e.code}). "
                 "Il a peut-etre ete revoque : refaire « gsc-mcp auth ».")


# ---------------------------------------------------------------------------
# Lecture de la Search Console
# ---------------------------------------------------------------------------

def lignes_gsc(jeton, debut, fin):
    """Les couples (requete, page) de la fenetre, pagines sous plafond."""
    url = ("https://www.googleapis.com/webmasters/v3/sites/"
           + urllib.parse.quote(PROPRIETE, safe="") + "/searchAnalytics/query")
    lignes, depart, appels = [], 0, 0

    while appels < MAX_APPELS_GSC:
        charge = json.dumps({
            "startDate": str(debut), "endDate": str(fin),
            "dimensions": ["query", "page"],
            "rowLimit": LIGNES_PAR_APPEL, "startRow": depart,
        }).encode()
        req = urllib.request.Request(url, data=charge, headers={
            "Authorization": "Bearer " + jeton, "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=90) as r:
            lot = json.load(r).get("rows", [])
        appels += 1
        lignes.extend(lot)

        if len(lot) < LIGNES_PAR_APPEL:
            break                      # derniere page
        if len(lignes) >= MAX_LIGNES:
            print(f"PLAFOND : {MAX_LIGNES} lignes atteintes, on s'arrete la.")
            break
        depart += LIGNES_PAR_APPEL

    return lignes, appels


# ---------------------------------------------------------------------------
# La cle : cible + intention
# ---------------------------------------------------------------------------

def sans_accent(texte):
    return "".join(c for c in unicodedata.normalize("NFD", texte.lower())
                   if unicodedata.category(c) != "Mn")


def cible(page):
    """Ce que la page d'atterrissage designe.

    On la prefere a la requete : GSC a deja fait l'appariement, et il est juste.
    Deviner une commune dans du texte libre, avec ses homonymes et ses stades
    qui ne portent pas le nom de la ville, ne ferait qu'ajouter des erreurs.
    """
    chemin = urllib.parse.urlsplit(page).path
    parts = [p for p in chemin.split("/") if p]
    if parts and parts[0] == "en":
        parts = parts[1:]
    if not parts:
        return "inconnu"
    tete = parts[0]
    if tete in ("site", "track") and len(parts) > 1:
        return parts[1]
    if tete in ("ville", "city") and len(parts) > 1:
        return "ville:" + parts[1]
    if tete in ("departement", "department") and len(parts) > 1:
        return "dep:" + parts[1]
    if tete == "pistes" and len(parts) > 1:
        return "critere:" + "/".join(parts[1:])
    return "inconnu"


# L'ordre compte : la premiere famille qui repond gagne. « piste couverte
# tartan » est d'abord une question sur le couvert.
INTENTIONS = [
    ("couvert",    ("couvert", "indoor", "salle", "interieur", "halle")),
    ("revetement", ("tartan", "synthetique", "revetement", "gazon", "cendree",
                    "herbe", "surface", "resine", "en dur", "sable")),
    ("horaires",   ("horaire", "heure", "ouverture", "fermeture", "nocturne",
                    "eclairage", "eclaire", "la nuit", "dimanche")),
    ("tarif",      ("tarif", "prix", "cout", "payant", "abonnement", "cotisation")),
    ("acces",      ("acces", "libre", "ouvert au public", "gratuit", "peut on",
                    "peut-on", "autorise", "reserve", "sans club", "public")),
    ("agres",      ("sautoir", "perche", "saut", "poids", "disque", "javelot",
                    "marteau", "steeple", "haies", "agres", "lancer")),
    ("distance",   ("combien de tour", "tour de piste", "longueur", "distance",
                    "circonference", "metres", "combien de metres")),
    ("contact",    ("contact", "telephone", "numero", "mail", "reservation",
                    "reserver", "joindre", "adresse")),
    ("photos",     ("photo", "image", "vue", "aerienne")),
    ("existence",  ("y a t il", "y a-t-il", "existe", "ou courir",
                    "ou s entrainer", "ou s'entrainer", "pres de", "proche")),
]


def intention(requete):
    """Ce que la personne veut savoir, ramene a une famille stable.

    Les designations — « stade », « piste », « anneau », « 400m » — ne sont pas
    des intentions : elles nomment l'objet, pas la question. Les prendre pour
    des intentions ferait de chaque nom de stade une question distincte.
    """
    q = sans_accent(requete)
    for nom, mots in INTENTIONS:
        if any(m in q for m in mots):
            return nom
    return "autre"


def cle_de(requete, page):
    """La cle, et le repli quand aucune famille de mots ne repond.

    Ce repli n'est pas un fourre-tout : c'est le cas le plus frequent du site.
    Au 29 aout 2026, 66 des 76 questions relevees sont le nom d'un stade tape
    tel quel — « stade du fort louis », « parc du bouchet ». La personne ne
    pose pas de question precise, elle cherche l'installation. C'est l'intention
    « fiche », et le travail qu'elle appelle est different : non pas repondre a
    un point manquant, mais verifier que la fiche entiere tient debout.

    Le meme silence, quand aucune fiche ne correspond, veut dire l'inverse :
    quelqu'un cherche un lieu que le recensement ignore peut-etre. C'est
    « existence », le signal le plus precieux du lot.
    """
    c = cible(page)
    i = intention(requete)
    if i == "autre":
        i = "existence" if c == "inconnu" else "fiche"
    return f"{c}|{i}", c, i


# ---------------------------------------------------------------------------
# Ecriture dans D1
#
# Deux transports : l'API HTTP quand un jeton est fourni (c'est le cas dans
# GitHub Actions), sinon wrangler, qui reutilise la session locale. Le second
# evite d'avoir a creer un jeton pour un simple essai sur la machine.
# ---------------------------------------------------------------------------

class D1:
    def __init__(self, simulation=False):
        self.simulation = simulation
        self.requetes = 0
        self.jeton = os.environ.get("CF_API_TOKEN")
        self.compte = os.environ.get("CF_ACCOUNT_ID")
        self.base = os.environ.get("CF_DATABASE_ID")
        self.http = bool(self.jeton and self.compte and self.base)

    def sql(self, sql, params=()):
        if self.simulation:
            return []
        if self.requetes >= MAX_REQUETES_D1:
            sys.exit(f"PLAFOND : {MAX_REQUETES_D1} requetes D1 atteintes. "
                     "Rien de plus ne sera ecrit pendant cette execution.")
        self.requetes += 1
        return self._http(sql, params) if self.http else self._wrangler(sql, params)

    def _http(self, sql, params):
        url = (f"https://api.cloudflare.com/client/v4/accounts/{self.compte}"
               f"/d1/database/{self.base}/query")
        req = urllib.request.Request(
            # L'API refuse un parametre nul : on n'en passe jamais. Les deux
            # transports doivent ecrire exactement la meme chose, sinon la base
            # ne dit pas la meme chose selon l'endroit d'ou le releve tourne.
            url, data=json.dumps({"sql": sql, "params": list(params)}).encode(),
            headers={"Authorization": "Bearer " + self.jeton,
                     "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                rep = json.load(r)
        except urllib.error.HTTPError as e:
            sys.exit(f"ERREUR D1 ({e.code}) : {e.read().decode()[:300]}")
        if not rep.get("success"):
            sys.exit(f"ERREUR D1 : {json.dumps(rep.get('errors'))[:300]}")
        return rep["result"][0].get("results", [])

    def _wrangler(self, sql, params):
        # wrangler ne lie pas de parametres : on interpole, en echappant.
        rendu, reste = [], list(params)
        for morceau in sql.split("?"):
            rendu.append(morceau)
            if reste:
                rendu.append(_litteral(reste.pop(0)))
        cmd = ["npx", "wrangler", "d1", "execute", BASE, "--remote",
               "--json", "--command", "".join(rendu)]
        p = subprocess.run(cmd, capture_output=True, text=True,
                           cwd=os.path.expanduser("~"))
        if p.returncode != 0:
            sys.exit(f"ERREUR wrangler : {p.stderr[-500:]}")
        # Wrangler prefixe sa sortie d'avertissements colores qui contiennent
        # eux-memes des crochets : chercher le premier « [ » tombe juste par
        # chance. On tente un decodage a chaque crochet jusqu'a ce qu'un
        # document JSON complet sorte.
        d = json.JSONDecoder()
        for i, c in enumerate(p.stdout):
            if c == "[":
                try:
                    return d.raw_decode(p.stdout[i:])[0][0].get("results", [])
                except (json.JSONDecodeError, IndexError, AttributeError):
                    continue
        sys.exit(f"ERREUR : sortie wrangler illisible :\n{p.stdout[-500:]}")


def _litteral(v):
    if v is None:
        return "NULL"
    if isinstance(v, (int, float)):
        return repr(v)
    return "'" + str(v).replace("'", "''") + "'"


UPSERT = """
INSERT INTO requetes_gsc
  (cle, cible, intention, requete, page, impressions, position, vu_le, revu_le)
VALUES {valeurs}
ON CONFLICT(cle) DO UPDATE SET
  impressions = excluded.impressions,
  position    = excluded.position,
  revu_le     = excluded.revu_le,
  page        = COALESCE(requetes_gsc.page, excluded.page),
  variantes   = requetes_gsc.variantes + (requetes_gsc.requete <> excluded.requete)
"""


# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--jours", type=int, default=7,
                    help="fenetre relevee, en jours (defaut : 7)")
    ap.add_argument("--amorcage", action="store_true",
                    help="releve tout l'historique disponible (16 mois)")
    ap.add_argument("--simulation", action="store_true",
                    help="lit Google, n'ecrit rien, affiche ce qui serait ecrit")
    args = ap.parse_args()

    jours = 16 * 30 if args.amorcage else args.jours
    fin = datetime.date.today()
    debut = fin - datetime.timedelta(days=jours)
    fenetre = f"{debut} -> {fin}"

    jeton = jeton_google()
    lignes, appels = lignes_gsc(jeton, debut, fin)
    print(f"Search Console : {len(lignes)} couples sur {fenetre} "
          f"({appels} appel{'s' if appels > 1 else ''})")

    # Une cle peut recevoir plusieurs couples : on additionne les impressions
    # et on garde la meilleure position, celle qui dit ce qu'il y a a gagner.
    cles = {}
    for ligne in lignes:
        requete, page = ligne["keys"][0], ligne["keys"][1]
        cle, c, i = cle_de(requete, page)
        e = cles.setdefault(cle, {"cible": c, "intention": i, "requete": requete,
                                  "page": page, "impressions": 0, "position": 999.0})
        e["impressions"] += int(ligne["impressions"])
        e["position"] = min(e["position"], round(float(ligne["position"]), 1))

    print(f"           -> {len(cles)} questions distinctes")
    par_intention = {}
    for e in cles.values():
        par_intention[e["intention"]] = par_intention.get(e["intention"], 0) + 1
    for nom, n in sorted(par_intention.items(), key=lambda x: -x[1]):
        print(f"              {n:4}  {nom}")

    db = D1(simulation=args.simulation)

    connues = set()
    if not args.simulation:
        for r in db.sql("SELECT cle FROM requetes_gsc"):
            connues.add(r["cle"])
    neuves = [c for c in cles if c not in connues]
    print(f"           -> {len(neuves)} nouvelles, {len(cles) - len(neuves)} deja connues")

    if args.simulation:
        for cle, e in sorted(cles.items(), key=lambda x: -x[1]["impressions"])[:20]:
            print(f"   {e['impressions']:4} imp  pos {e['position']:5.1f}  "
                  f"{cle:45} « {e['requete']} »")
        print("\nSimulation : rien n'a ete ecrit.")
        return

    aujourdhui = str(fin)
    items = list(cles.items())
    for i in range(0, len(items), LIGNES_PAR_ECRITURE):
        lot = items[i:i + LIGNES_PAR_ECRITURE]
        valeurs, params = [], []
        for cle, e in lot:
            valeurs.append("(?,?,?,?,?,?,?,?,?)")
            params += [cle, e["cible"], e["intention"], e["requete"], e["page"],
                       e["impressions"], e["position"], aujourdhui, aujourdhui]
        db.sql(UPSERT.format(valeurs=",".join(valeurs)), params)

    restante = db.sql("SELECT COUNT(*) AS n FROM requetes_gsc WHERE statut='file'")
    restante = restante[0]["n"] if restante else 0

    db.sql("INSERT INTO passages (lance_le, fenetre, appels_gsc, couples_vus,"
           " cles_neuves, cles_majes, file_restante, note)"
           " VALUES (?,?,?,?,?,?,?,?)",
           [datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
            fenetre, appels, len(lignes), len(neuves), len(cles) - len(neuves),
            restante, "amorcage" if args.amorcage else ""])

    print(f"Base : {len(cles)} cles ecrites, file a traiter = {restante}")
    print(f"       {db.requetes} requetes D1 (plafond {MAX_REQUETES_D1})")


if __name__ == "__main__":
    main()
