#!/usr/bin/env python3
"""
Annonce a IndexNow les pages qui viennent de changer.

IndexNow est le pendant ouvert du bouton « Demander une indexation » : on
previent le moteur au lieu d'attendre qu'il repasse. Bing, Yandex, Seznam et
Naver le respectent et se partagent les notifications ; Google ne le lit pas.
Ce n'est donc pas un remplacant du plan de site, c'est un signal de plus, et
il vise surtout les agents qui s'appuient sur Bing.

Le script tourne APRES le deploiement, jamais avant : annoncer une page qui
n'est pas encore servie apprend au moteur que le signal ment. Il lit donc le
site publie — ses plans de site, tels qu'ils viennent d'etre mis en ligne — et
retient les URL dont le <lastmod> est celui du jour. Comme build_site.py ne
redate une page que si son empreinte a change, cette liste est exactement
celle des pages qui ont bouge.

Usage : python3 scripts/indexnow.py --url https://pistes-athle.com [--envoyer]
Sans --envoyer, le script dit ce qu'il enverrait et n'envoie rien.
"""

import argparse
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

# La cle IndexNow est publique par construction : elle est servie a la racine
# du site, en clair, et n'importe qui peut la lire. Ce n'est pas un secret mais
# une preuve de possession du domaine — le moteur verifie que celui qui annonce
# des URL est bien celui qui tient le fichier. Elle a donc sa place dans le
# depot, et surtout pas dans un secret GitHub, ou elle serait invisible a la
# relecture tout en restant lisible sur le site.
CLE = "e96f06a2fa705cb6717134aec1d9d6f1"

POINT_DE_COLLECTE = "https://api.indexnow.org/indexnow"
UA = {"User-Agent": "pistes-athle/1.0 (+https://pistes-athle.com)"}

# Au-dela, ce n'est plus une notification, c'est un reindexage complet. Deux
# cas le declenchent : le journal des dates a ete perdu — toutes les pages
# portent alors la date du jour sans avoir bouge — ou le ministere a republie
# son jeu de donnees. Dans les deux cas, arroser le moteur de milliers d'URL
# est le signal qui fait plafonner un domaine, et le plan de site fait deja ce
# travail-la. On se tait et on le dit.
PLAFOND = 2000

# Nombre maximal d'URL par requete, fixe par le protocole.
LOT = 10000


def plans_de_site(url_base, timeout=30):
    """Les plans de site declares par l'index, tels qu'ils sont en ligne."""
    index = lire(f"{url_base}/sitemap.xml", timeout)
    return re.findall(r"<loc>([^<]+)</loc>", index)


def lire(url, timeout=30):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8")


def urls_du_jour(url_base, jour, timeout=30):
    """URL du site publie dont la date de derniere modification est `jour`.

    build_site.py date chaque page sur l'empreinte de son contenu : une page
    inchangee garde sa date d'avant. Porter la date du jour, c'est donc avoir
    change aujourd'hui."""
    trouvees = []
    for plan in plans_de_site(url_base, timeout):
        xml = lire(plan, timeout)
        for bloc in re.findall(r"<url>(.*?)</url>", xml, re.S):
            loc = re.search(r"<loc>([^<]+)</loc>", bloc)
            mod = re.search(r"<lastmod>([^<]+)</lastmod>", bloc)
            if loc and mod and mod.group(1).strip() == jour:
                trouvees.append(loc.group(1).strip())
    return trouvees


def cle_en_ligne(url_base, timeout=30):
    """L'URL du fichier de cle s'il est bien servi, sinon None.

    Le moteur ira le chercher avant d'accepter quoi que ce soit : mieux vaut
    s'en assurer ici et le dire clairement que laisser l'annonce etre rejetee
    en silence a l'autre bout."""
    url = f"{url_base}/{CLE}.txt"
    try:
        if lire(url, timeout).strip() == CLE:
            return url
        print(f"[!] {url} ne contient pas la cle attendue")
    except (urllib.error.URLError, OSError) as e:
        print(f"[!] fichier de cle injoignable ({e})")
    return None


def annoncer(url_base, urls, emplacement_cle, timeout=30):
    """Envoie les URL par lots. Rend le nombre de lots acceptes."""
    hote = urllib.parse.urlsplit(url_base).netloc
    acceptes = 0
    for depart in range(0, len(urls), LOT):
        lot = urls[depart:depart + LOT]
        corps = json.dumps({
            "host": hote,
            "key": CLE,
            "keyLocation": emplacement_cle,
            "urlList": lot,
        }).encode("utf-8")
        req = urllib.request.Request(
            POINT_DE_COLLECTE, data=corps, method="POST",
            headers={**UA, "Content-Type": "application/json; charset=utf-8"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                print(f"   lot de {len(lot)} URL : HTTP {r.status}")
                acceptes += 1
        except urllib.error.HTTPError as e:
            # 422 = des URL n'appartiennent pas au domaine, 403 = cle refusee.
            print(f"[!] lot de {len(lot)} URL refuse : HTTP {e.code} "
                  f"{e.read().decode('utf-8', 'replace')[:200]}")
        except (urllib.error.URLError, OSError) as e:
            print(f"[!] lot de {len(lot)} URL non envoye : {e}")
    return acceptes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True,
                    help="URL publique du site, sans barre finale")
    ap.add_argument("--jour", default=None,
                    help="date a annoncer (AAAA-MM-JJ), aujourd'hui par defaut")
    ap.add_argument("--envoyer", action="store_true",
                    help="envoie reellement ; sans lui, le script se contente de dire")
    args = ap.parse_args()

    url_base = args.url.rstrip("/")
    # IndexNow veut la cle a la racine de l'hote pour couvrir tout l'hote. Un
    # fork publie sous « github.io/pistes-athle », un sous-dossier d'un domaine
    # qui ne lui appartient pas : il n'a rien a annoncer et le dire vaut mieux
    # que d'echouer a l'aveugle.
    if urllib.parse.urlsplit(url_base).path:
        print(f"-> {url_base} est servi depuis un sous-dossier : rien a annoncer.")
        return 0

    # La date du site, pas celle de la machine : build_site.py date en UTC.
    jour = args.jour or datetime.now(timezone.utc).strftime("%Y-%m-%d")

    try:
        urls = urls_du_jour(url_base, jour)
    except (urllib.error.URLError, OSError, ValueError) as e:
        print(f"[!] plans de site illisibles ({e}) : rien n'est annonce.")
        return 0

    print(f"-> {len(urls)} URL datees du {jour} dans les plans de site publies")
    if not urls:
        print("   rien n'a change : aucune annonce.")
        return 0
    if len(urls) > PLAFOND:
        print(f"   au-dela de {PLAFOND} URL, ce n'est plus une notification mais un\n"
              f"   reindexage : le plan de site s'en charge mieux. Aucune annonce.")
        return 0

    for u in urls[:10]:
        print(f"   {u}")
    if len(urls) > 10:
        print(f"   ... et {len(urls) - 10} autres")

    if not args.envoyer:
        print("   (essai a blanc : relancer avec --envoyer pour annoncer)")
        return 0

    emplacement = cle_en_ligne(url_base)
    if not emplacement:
        print("   sans fichier de cle servi, l'annonce serait rejetee : on s'abstient.")
        return 0

    lots = annoncer(url_base, urls, emplacement)
    print(f"-> {lots} lot(s) accepte(s) par IndexNow")
    return 0


if __name__ == "__main__":
    sys.exit(main())
