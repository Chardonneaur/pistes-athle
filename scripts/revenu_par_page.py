#!/usr/bin/env python3
"""Le tunnel publicitaire d'une page, bout a bout : vu, servi, impression, clic.

    python3 scripts/revenu_par_page.py
    python3 scripts/revenu_par_page.py --jours 7 --limite 40
    python3 scripts/revenu_par_page.py --json .work/revenu.json

POURQUOI DEUX SOURCES, ET PAS UNE. Un clic sur une annonce est invisible depuis
la page : l'annonce est une iframe d'un autre domaine, et la politique de meme
origine interdit d'observer ce qui s'y passe. Matomo ne le verra jamais, et
aucun bricolage ne vaut la peine d'etre tente — voir l'en-tete de
assets/adsense.js.

Les deux moities sont donc chez deux fournisseurs, et la jointure se fait sur
l'URL de la page :

  MATOMO   pages vues, et les trois etats que assets/adsense.js mesure —
           emplacement vu, emplacement servi, chargeur bloque. C'est l'AMONT,
           et personne d'autre ne le rend.
  ADSENSE  impressions, clics, CTR, revenu estime, par PAGE_URL. C'est l'AVAL,
           et c'est la seule source autoritative.

Sans l'amont, une page qui ne rapporte rien ne dit pas si elle convertit mal ou
si son encart n'est jamais rempli — deux problemes opposes, deux remedes
opposes. Sans l'aval, on ne sait rien de l'argent.

IDENTIFIANTS. AdSense reutilise ceux du serveur MCP, dans
~/.config/adsense-mcp/ : rien a creer. Matomo demande un jeton d'API, a poser
dans l'environnement — sans lui, le script rend la moitie AdSense seule, ce qui
reste utile :

    MATOMO_TOKEN=xxxxxxxx python3 scripts/revenu_par_page.py

Les revenus sont des ESTIMATIONS jusqu'a la cloture du mois.
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, timedelta

ADSENSE_CONF = os.path.expanduser("~/.config/adsense-mcp")
ADSENSE_API = "https://adsense.googleapis.com/v2"
MATOMO_URL = "https://ronanchardonneau.matomo.cloud/index.php"
MATOMO_SITE = "149"
UA = {"User-Agent": "pistes-athle/1.0 (github.com/Chardonneaur/pistes-athle)"}

# Les trois etats que assets/adsense.js pousse dans Matomo, et le quatrieme
# qui n'a de sens que sur un emplacement rempli. Les libelles doivent rester
# identiques des deux cotes : ce sont eux la cle de jointure.
ETATS = ("emplacement vu", "emplacement servi", "emplacement vide",
         "chargeur bloque")


def _json(url, data=None, entetes=None):
    req = urllib.request.Request(url, data=data, headers={**UA, **(entetes or {})})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


# ---------------------------------------------------------------- AdSense

def jeton_adsense():
    """Rafraichit le jeton OAuth du serveur MCP, sans jamais l'ecrire ailleurs."""
    chemin = os.path.join(ADSENSE_CONF, "token.json")
    try:
        with open(chemin, encoding="utf-8") as f:
            t = json.load(f)
    except OSError:
        sys.exit(f"ERREUR : {chemin} introuvable. Le serveur MCP AdSense n'a "
                 f"jamais ete authentifie sur cette machine.")
    corps = urllib.parse.urlencode({
        "client_id": t["client_id"], "client_secret": t["client_secret"],
        "refresh_token": t["refresh_token"], "grant_type": "refresh_token",
    }).encode()
    try:
        rep = _json(t.get("token_uri") or "https://oauth2.googleapis.com/token",
                    data=corps,
                    entetes={"Content-Type": "application/x-www-form-urlencoded"})
    except urllib.error.HTTPError as e:
        sys.exit(f"ERREUR : rafraichissement du jeton AdSense refuse "
                 f"({e.code}). Reauthentifier le serveur MCP.")
    return rep["access_token"], t.get("account")


def compte_adsense(jeton, defaut=None):
    if defaut:
        return defaut
    rep = _json(f"{ADSENSE_API}/accounts",
                entetes={"Authorization": "Bearer " + jeton})
    comptes = rep.get("accounts") or []
    if not comptes:
        sys.exit("ERREUR : aucun compte AdSense accessible.")
    return comptes[0]["name"]


def adsense_par_page(jeton, compte, debut, fin, limite):
    """Impressions, clics et revenu, page par page."""
    p = [("dateRange", "CUSTOM"),
         ("startDate.year", debut.year), ("startDate.month", debut.month),
         ("startDate.day", debut.day),
         ("endDate.year", fin.year), ("endDate.month", fin.month),
         ("endDate.day", fin.day),
         ("dimensions", "PAGE_URL"),
         ("orderBy", "-ESTIMATED_EARNINGS"),
         ("limit", limite)]
    for m in ("ESTIMATED_EARNINGS", "PAGE_VIEWS", "IMPRESSIONS", "CLICKS",
              "PAGE_VIEWS_CTR"):
        p.append(("metrics", m))
    url = f"{ADSENSE_API}/{compte}/reports:generate?" + urllib.parse.urlencode(p)
    rep = _json(url, entetes={"Authorization": "Bearer " + jeton})
    out = {}
    for ligne in rep.get("rows") or []:
        cells = [c.get("value") for c in ligne["cells"]]
        chemin = chemin_de(cells[0])
        out[chemin] = {
            "revenu": float(cells[1] or 0), "vues_adsense": int(cells[2] or 0),
            "impressions": int(cells[3] or 0), "clics": int(cells[4] or 0),
            "ctr": float(cells[5] or 0),
        }
    return out, (rep.get("headers") or [])


def chemin_de(url):
    """« https://pistes-athle.com/site/I441090215/ » -> « /site/I441090215/ ».

    AdSense rend une URL complete, Matomo un chemin : sans cette reduction, la
    jointure ne tomberait jamais. Une URL qui n'est pas la notre garde sa forme
    entiere — elle se verra tout de suite dans la sortie.
    """
    m = urllib.parse.urlsplit(url if "//" in url else "//" + url)
    return m.path or url


# ----------------------------------------------------------------- Matomo

def matomo(methode, jeton, **extra):
    p = {"module": "API", "method": methode, "idSite": MATOMO_SITE,
         "format": "JSON", "token_auth": jeton, "filter_limit": "-1", **extra}
    rep = _json(MATOMO_URL, data=urllib.parse.urlencode(p).encode())
    if isinstance(rep, dict) and rep.get("result") == "error":
        sys.exit(f"ERREUR Matomo : {rep.get('message')}")
    return rep


def matomo_par_page(jeton, debut, fin):
    """Pages vues, puis les quatre etats de l'encart, page par page."""
    plage = f"{debut},{fin}"
    out = {}
    for r in matomo("Actions.getPageUrls", jeton, period="range", date=plage,
                    flat="1"):
        chemin = r.get("label") or ""
        if not chemin.startswith("/"):
            chemin = "/" + chemin
        out.setdefault(chemin, {})["vues"] = int(r.get("nb_hits") or 0)

    # Un appel par etat : le nom de l'evenement porte le chemin de la page,
    # l'action porte l'etat. Segmenter sur l'action et lister les noms rend
    # donc exactement « cet etat, page par page ».
    for etat in ETATS:
        try:
            lignes = matomo("Events.getName", jeton, period="range", date=plage,
                            segment=f"eventCategory==Publicite;eventAction=={etat}")
        except urllib.error.HTTPError:
            continue
        for r in lignes:
            chemin = r.get("label") or ""
            out.setdefault(chemin, {})[etat] = int(r.get("nb_events") or 0)
    return out


# ------------------------------------------------------------------ sortie

def raconter(pages, devise, avec_matomo):
    if not pages:
        print("Aucune ligne. Si les annonces ne sont pas encore diffusees "
              "(etat GETTING_READY), c'est le resultat attendu.")
        return
    if avec_matomo:
        print(f"{'page':<42}{'vues':>6}{'vu':>6}{'servi':>6}{'vide':>6}"
              f"{'bloq':>6}{'impr':>7}{'clics':>6}{'revenu':>9}")
    else:
        print(f"{'page':<42}{'vues':>7}{'impr':>7}{'clics':>6}{'ctr':>7}"
              f"{'revenu':>9}")
    for chemin, d in pages:
        if avec_matomo:
            print(f"{chemin[:41]:<42}{d.get('vues', 0):>6}"
                  f"{d.get('emplacement vu', 0):>6}{d.get('emplacement servi', 0):>6}"
                  f"{d.get('emplacement vide', 0):>6}{d.get('chargeur bloque', 0):>6}"
                  f"{d.get('impressions', 0):>7}{d.get('clics', 0):>6}"
                  f"{d.get('revenu', 0):>8.2f} ")
        else:
            print(f"{chemin[:41]:<42}{d.get('vues_adsense', 0):>7}"
                  f"{d.get('impressions', 0):>7}{d.get('clics', 0):>6}"
                  f"{100 * d.get('ctr', 0):>6.2f}%{d.get('revenu', 0):>8.2f} ")
    print(f"\nRevenu en {devise}, ESTIME tant que le mois n'est pas clos.")
    if avec_matomo:
        print(
            "Lire les colonnes ensemble, jamais l'une sans l'autre :\n"
            "  vues >> vu       l'encart est trop bas, ou la visite trop courte ;\n"
            "  vu   >> servi    Google n'avait rien a mettre sur cette page ;\n"
            "  servi >> impr    ecart normal (une impression demande d'etre vue),\n"
            "                   mais un ecart massif signale un encart hors ecran ;\n"
            "  bloq             la part de visiteurs qui bloquent les annonces,\n"
            "                   la seule chose qu'AdSense ne dira jamais.")
    else:
        print("Sans MATOMO_TOKEN, seule la moitie AdSense est lue : on voit "
              "l'argent,\nmais pas pourquoi une page n'en fait pas.")


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--jours", type=int, default=28,
                    help="largeur de la fenetre, qui se termine hier (defaut 28)")
    ap.add_argument("--limite", type=int, default=25)
    ap.add_argument("--json", metavar="FICHIER")
    args = ap.parse_args()

    fin = date.today() - timedelta(days=1)
    debut = fin - timedelta(days=args.jours - 1)
    print(f"Du {debut} au {fin}.\n")

    jeton, compte_defaut = jeton_adsense()
    compte = compte_adsense(jeton, compte_defaut)
    pub, entetes = adsense_par_page(jeton, compte, debut, fin, args.limite)
    devise = "EUR"
    for h in entetes:
        if h.get("name") == "ESTIMATED_EARNINGS":
            devise = h.get("currencyCode") or devise

    jeton_matomo = os.environ.get("MATOMO_TOKEN")
    fusion = {}
    if jeton_matomo:
        for chemin, d in matomo_par_page(jeton_matomo, debut, fin).items():
            fusion.setdefault(chemin, {}).update(d)
    for chemin, d in pub.items():
        fusion.setdefault(chemin, {}).update(d)

    # Trier par revenu d'abord, puis par pages vues : sans annonces diffusees,
    # le revenu est nul partout et c'est l'audience qui ordonne utilement.
    pages = sorted(fusion.items(),
                   key=lambda kv: (-kv[1].get("revenu", 0), -kv[1].get("vues", 0)))
    raconter(pages[:args.limite], devise, bool(jeton_matomo))

    if args.json:
        os.makedirs(os.path.dirname(os.path.abspath(args.json)), exist_ok=True)
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump({"debut": str(debut), "fin": str(fin), "devise": devise,
                       "pages": dict(pages)}, f, ensure_ascii=False, indent=2)
            f.write("\n")
        print(f"-> {args.json}")


if __name__ == "__main__":
    main()
