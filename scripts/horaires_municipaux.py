#!/usr/bin/env python3
"""Cherche sur le site de la commune l'horaire d'ouverture d'une piste au public.

    python3 scripts/horaires_municipaux.py I940160010
    python3 scripts/horaires_municipaux.py 94 --limite 20
    python3 scripts/horaires_municipaux.py 94 --json .work/horaires-94.json

L'horaire est le champ le plus utile et le seul qu'aucune donnee ouverte ne
porte. Data ES ne le connait pas, OpenStreetMap non plus, et les deliberations
des conseils municipaux ont ete mesurees a zero fait ecrivable sur 167 communes
(docs/ce-que-dit-la-mairie.md). Il en restait 9 sur 7 287 fiches le 2 septembre
2026, soit 0,12 %.

Un canal rend, et c'est un autre que celui des deliberations : la **fiche
d'equipement** que beaucoup de villes publient dans leur annuaire. Cachan
donne les creneaux d'ouverture de sa piste au public, Gap ses agres discipline
par discipline, Beauvais un « 8h00-22h00 ». Sur 36 stades cherches a la main le
2 septembre 2026, neuf ont rendu un horaire : un sur quatre.

CE SCRIPT EST LA MOITIE BETE DU CHANTIER, comme releve_gsc.py l'est de la
Search Console. Il trouve les pages, en extrait les horaires avec leur phrase,
les classe, et s'arrete la. **Il n'ecrit dans aucune fiche.** Le jugement — la
page parle-t-elle bien de CETTE piste, l'horaire est-il celui de l'installation
ou d'autre chose — reste a l'agent ou a la personne qui lit la sortie, guides
par la competence contribution-piste.

LE PIEGE QUI COMMANDE TOUT LE RESTE. Sur les 36 stades cherches a la main, il a
fallu ecarter autant d'horaires qu'on en a ecrit : ceux de l'**accueil
administratif de la mairie**. « Lundi 14h-17h, mardi 8h30-12h30 et 14h-17h »,
c'est le secretariat de Maurepas, pas son parc des sports — et un agregateur
l'affichait comme l'horaire du stade. Meme piege a Franconville, Ermont,
Feyzin, Troyes et Rosny.

Un horaire faux est PIRE qu'un champ vide : il envoie quelqu'un devant un
portail ferme, ce qui est exactement la promesse que ce site ne doit pas
trahir. Le classement ci-dessous ecarte donc par defaut et n'admet que ce qui
porte un signe positif ; ce qu'il ecarte reste visible dans la sortie, pour
qu'on puisse verifier qu'il n'ecarte pas trop.

CE QU'IL NE SAIT PAS FAIRE, et il faut le savoir avant de lire un silence.
L'annuaire DILA donne le site de la *mairie*. Or l'equipement est souvent gere
par l'agglomeration, qui a son propre site : les horaires de Beauvais sont sur
beauvaisis.fr, ceux de Clamart dans un reglement interieur de Vallee Sud -
Grand Paris, ceux d'Ermont et de Franconville sur valparisis.fr. Aucun de ces
trois-la n'est atteignable depuis le site de la commune seule. Un « rien
trouve » d'ici veut donc dire « rien sur le site de la mairie », pas « rien ne
existe ».

Annuaire de l'administration, DILA - Licence Ouverte 2.0.
Les pages restent la propriete des communes : on n'en recopie que des extraits.
"""
import argparse
import hashlib
import html as html_mod
import json
import os
import re
import sys
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# On emprunte a conseils_municipaux ses primitives, pas sa logique : `lire`
# (cache disque et pause entre deux appels), `plier` (minuscules sans accents a
# longueur constante, pour citer le texte d'origine sans decalage), l'annuaire
# DILA et le chargement des sites. Elles sont stables et deja eprouvees sur
# 167 communes ; les recopier ici les ferait diverger.
from conseils_municipaux import (           # noqa: E402
    ANNUAIRE, GEOAPI, autorise, charger_sites, insee_du_site, lire, mairie,
    plier, robots,
)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, ".work", "horaires")

# Les liens qu'on suit depuis l'accueil. On vise l'annuaire des equipements,
# pas l'actualite : c'est la page « fiche d'equipement » qui porte un horaire,
# jamais un article de journal municipal.
PISTE_PAGE = re.compile(
    r"equipement|installation|sport|stade|complexe|gymnase|piscine|"
    r"annuaire|lieux?|point.d.interet|infrastructure|athletisme", re.I)

# Une plage horaire : « 8h a 22h », « 8h00-22h00 », « 17h30 a 21h30 ».
# L'heure de fin est obligatoire — un « ouvert a 8h » seul ne dit rien.
HEURE = r"\d{1,2}\s?(?:h|:)\s?(?:\d{2})?"
PLAGE = re.compile(rf"({HEURE})\s*(?:a|à|-|–|—|/|jusqu.a)\s*({HEURE})", re.I)

JOURS = re.compile(
    r"lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche|"
    r"week.?end|jours? ferie", re.I)

# Le contexte qui DISQUALIFIE : on parle du guichet, pas du terrain.
MAIRIE = re.compile(
    r"mairie|hotel de ville|accueil|etat civil|secretariat|"
    r"services? administratifs?|guichet|standard|permanence|ccas|"
    r"urbanisme|passeport|carte d.identite|elections|"
    r"service (?:population|scolaire|jeunesse|technique)|"
    # « Contact Service des sports [...] Ouvert du lundi [...] de 8h30 a
    # 12h30 » : a Franconville, c'est le bureau qui repond au telephone, pas
    # un gymnase. Un service des sports a des horaires, et ce ne sont jamais
    # ceux de la piste.
    r"services? (?:des )?sports?|direction des sports|sur rendez.vous|"
    # Le pied de page, qui suit le lecteur sur toutes les pages du site. A
    # Franconville il porte « Horaires d'ouverture Lundi, Mardi, Jeudi et
    # Vendredi de 8h30 a 12h15 de 13h30 a 18h » sans jamais ecrire le mot
    # mairie — et le samedi qu'il cite suffisait a le faire passer pour un
    # equipement. Ces mots-la, eux, n'existent que dans le chrome d'un site.
    r"nous contacter|\bcedex\b|\bbp\s?\d|\bfax\b|newsletter|"
    r"plan du site|mentions legales|nous ecrire|suivez.nous", re.I)

# Le contexte qui QUALIFIE, et il faut les DEUX. Un seul des deux ne suffit
# pas : la fiche du complexe Robert Monseau a Saint-Medard porte le tableau
# horaire de la PISCINE — « Mercredi 10h15 – 16h15, Jeudi 12h15 – 15h00 » —
# dans une page qui parle par ailleurs de terrains et de creneaux. Le mot de
# lieu passait, et un horaire de bassin serait entre dans une fiche de piste.
# En exigeant en plus un mot d'ouverture ou d'acces, le tableau nu tombe et la
# phrase « En acces libre de 8h a 22h », elle, passe.
LIEU = re.compile(
    r"piste|stade|athletisme|anneau|terrain|gymnase|complexe|"
    r"installation|equipement|plaine sportive|parc des sports", re.I)
ACCES = re.compile(
    r"ouvert|ouverture|fermeture|acces|horaires?|creneaux?|"
    r"public|disposition|pratique libre|utilisation", re.I)

# Le troisieme piege, mesure sur la Loire-Atlantique le 2 septembre 2026 : le
# CRENEAU DE CLUB. La page du club de badminton de Coueron nomme bien le
# complexe sportif Paul Langevin et donne bien des heures — celles de ses
# entrainements. Les ecrire dans une fiche dirait a un coureur de venir
# precisement quand la salle est occupee. C'est l'inverse de ce qu'on cherche.
CLUB = re.compile(
    r"/association|/club|entrainement|entrainements|licencie|adherent|"
    r"cotisation|inscription|creneaux jeunes|categorie|"
    r"benjamin|poussin|minime|cadet|junior|veteran|"
    r"cours (?:de|d.|collectif)|saison sportive", re.I)

MARGE = 220          # caracteres cites de part et d'autre d'une plage horaire
# Le classement lit plus large que ce qu'il cite. Un titre « Horaires
# d'ouverture de la piste d'athletisme au public » chapeaute souvent cinq ou
# six plages : la troisieme est a 400 caracteres de lui, et la citer seule ne
# dit plus de quoi elle parle. A Gap, « les horaires indiques » tombait juste
# hors des 220 caracteres et la seule page du lot qui documente vraiment son
# stade etait ecartee.
CONTEXTE = 700
MAX_PAGES = 25       # par commune : au-dela, on explore un site, plus une piste
PROFONDEUR = 2


def heure_en_minutes(s):
    """« 8h30 » -> 510. Rend None sur ce qui ne se lit pas."""
    m = re.match(rf"^\s*(\d{{1,2}})\s?(?:h|:)\s?(\d{{2}})?\s*$", s)
    if not m:
        return None
    h, mn = int(m.group(1)), int(m.group(2) or 0)
    return h * 60 + mn if h <= 24 and mn < 60 else None


def signature_administrative(debut, fin, contexte):
    """La plage a-t-elle la forme d'un guichet plutot que d'un stade ?

    Mesure le 2 septembre 2026 sur les six communes ou le piege s'est presente
    (Maurepas, Franconville, Ermont, Feyzin, Troyes, Rosny) : toutes tenaient
    dans la journee de bureau — ouverture au plus tot a 8h, fermeture au plus
    tard a 18h45 — et aucune ne citait le week-end. Un stade, lui, deborde par
    au moins un bout : Nice ouvre a 6h30, Clamart ferme a 22h30, Saint-Medard
    et Livry-Gargan tiennent 8h-22h, Gap cite le samedi.

    La forme seule ne suffit pas a condamner — une piste peut n'ouvrir que de
    9h a 17h. C'est pourquoi elle n'est qu'un des deux motifs, et jamais le
    seul a decider : voir classer().
    """
    if debut is None or fin is None:
        return False
    if debut < 8 * 60 or fin > 18 * 60 + 45:
        return False
    return not re.search(r"samedi|dimanche|week.?end", contexte, re.I)


def classer(url, extrait, large, debut, fin):
    """Retenu, ou ecarte avec son motif. On ecarte par defaut.

    Un horaire faux vaut moins qu'un champ vide : il envoie quelqu'un devant un
    portail ferme. La regle est donc asymetrique — il faut un signe positif
    pour retenir, un seul signe negatif pour ecarter.

    Les deux fenetres ne servent pas a la meme chose. Le motif qui DISQUALIFIE
    se lit au plus pres — un « accueil de la mairie » a 600 caracteres ne dit
    rien de cette plage-ci. Les motifs qui QUALIFIENT se lisent large, parce
    qu'un intitule chapeaute plusieurs plages.
    """
    if MAIRIE.search(extrait):
        return None, "contexte administratif : mairie, accueil ou service"
    if CLUB.search(url) or CLUB.search(extrait):
        return None, ("creneau d'association, pas horaire d'ouverture : "
                      "l'ecrire enverrait un coureur quand la piste est prise")
    if not LIEU.search(large):
        return None, "aucun mot d'installation autour de la plage"
    if not ACCES.search(large):
        return None, ("mot d'installation mais rien sur l'ouverture ni "
                      "l'acces : probablement un tableau d'activites")
    if not JOURS.search(extrait):
        return None, "plage sans jour : impossible de savoir quand elle vaut"
    if signature_administrative(debut, fin, extrait):
        return None, ("forme de journee de bureau (dans 8h-18h45, sans "
                      "week-end) : a verifier a la main avant d'ecrire")
    return True, None


def extraits_horaires(html, noms, url=""):
    """Les plages horaires de la page, avec leur phrase et leur verdict.

    On cite le texte d'origine et on cherche dans le texte plie : `plier`
    conserve les longueurs, donc les positions restent bonnes.
    """
    texte = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.S | re.I)
    texte = re.sub(r"<[^>]+>", " ", texte)
    # Decoder les entites, et pas seulement &nbsp; : Gap ecrit ses horaires
    # « 8h &#8211; 20h », avec un tiret demi-cadratin en entite numerique. Sans
    # cette ligne, la seule page du lot de controle qui portait un horaire
    # d'ouverture au public ne matchait aucune plage — un faux silence sur la
    # commune qui documente le mieux son stade.
    texte = html_mod.unescape(texte)
    texte = texte.replace("\u00a0", " ")
    texte = re.sub(r"[ \t\r\f\v]+", " ", texte)
    plie = plier(texte)

    out, vus = [], set()
    for m in PLAGE.finditer(texte):
        a, b = m.start(), m.end()
        extrait = texte[max(0, a - MARGE):b + MARGE].strip()
        large = texte[max(0, a - CONTEXTE):b + CONTEXTE]
        cle = re.sub(r"\s+", " ", extrait[:80])
        if cle in vus:
            continue
        vus.add(cle)
        debut, fin = heure_en_minutes(m.group(1)), heure_en_minutes(m.group(2))
        garde, motif = classer(url, extrait, large, debut, fin)
        # Le nom du stade dans la meme phrase est le signe le plus fort qu'on
        # tienne la bonne installation, et non la piscine d'a cote.
        nomme = any(n and plier(n) in plie[max(0, a - MARGE):b + MARGE]
                    for n in noms)
        out.append({"plage": m.group(0).strip(), "extrait": extrait,
                    "retenu": bool(garde), "motif": motif, "nomme": nomme})
    out.sort(key=lambda e: (not e["nomme"], not e["retenu"]))
    return out[:12]


def mots_du_nom(nom):
    """« Complexe Sportif Robert Monseau » -> « robert monseau ».

    Meme intention que dans conseils_municipaux, mais la liste banale est plus
    longue ici : on cherche dans un annuaire d'equipements, ou « complexe
    sportif » nomme la moitie des pages et n'identifie rien.
    """
    banal = {"complexe", "sportif", "sportive", "stade", "parc", "terrain",
             "municipal", "municipale", "salle", "espace", "plaine", "jeux",
             "gymnase", "centre", "cosec", "halle", "sports", "athletisme",
             "des", "du", "de", "la", "le", "les", "d", "l", "et", "aux", "au"}
    mots = [m for m in re.split(r"[^a-z0-9]+", plier(nom or ""))
            if m and m not in banal and len(m) > 2]
    return [" ".join(mots)] if len(mots) >= 2 else mots


# Les prefixes sous lesquels les villes rangent leurs fiches d'equipement.
# Releve a la main le 2 septembre 2026 sur les communes du lot des 36 : elles
# ne s'accordent sur rien sauf la forme <base>/<prefixe>/<nom-en-slug>/.
PREFIXES = ("annuaire-des-equipements", "points-interets", "point-d-interet",
            "equipements", "equipement", "equipements-sportifs",
            "infrastructures-sportives", "annuaire-general", "lieux", "lieu",
            "sport", "")


def slug(nom):
    """« Complexe Sportif Léo Lagrange » -> « complexe-sportif-leo-lagrange »."""
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", plier(nom or ""))).strip("-")


def meme_hote(a, b):
    """Deux URL sur le meme site, « www. » mis a part.

    L'annuaire DILA donne « http://www.ville-cachan.fr », qui redirige vers
    « https://ville-cachan.fr » — et toutes les pages du site sont ecrites sans
    le www. Comparer les netloc bruts rejetait alors CHAQUE lien de la page
    d'accueil, et le script rendait « aucune page atteinte » sur une commune
    dont on savait qu'elle publie ses horaires. C'est le genre de silence qu'on
    prend pour une donnee manquante.
    """
    na = urllib.parse.urlsplit(a).netloc.lower().removeprefix("www.")
    nb = urllib.parse.urlsplit(b).netloc.lower().removeprefix("www.")
    return na == nb


def epci(insee, cache_dir):
    """Le site de l'intercommunalite, quand elle en a un.

    C'est la moitie manquante du gisement, mesuree le 2 septembre 2026 : sur
    les neuf horaires trouves a la main ce jour-la, cinq etaient sur le site de
    la commune et QUATRE sur celui de l'agglomeration ou du gestionnaire —
    beauvaisis.fr, valparisis.fr deux fois, m2a.fr. Un parcours limite a la
    mairie plafonne donc a la moitie du possible.

    Le chemin passe par deux jeux, parce que l'annuaire DILA ne rattache pas
    toujours l'EPCI a ses communes : geo.api.gouv.fr donne le SIREN de
    l'intercommunalite d'une commune, et c'est ce SIREN qui retrouve la fiche
    DILA — et son site. Interroger DILA directement sur le code INSEE de la
    commune ne rend rien pour Ermont, Franconville ni Cachan.

    Limite connue : geo.api rattache Clamart a la Metropole du Grand Paris,
    alors que son stade est gere par l'etablissement public territorial Vallee
    Sud - Grand Paris, que ni l'un ni l'autre des deux jeux ne nomme. Les EPT
    de la petite couronne echappent a ce chemin.
    """
    txt = lire(f"{GEOAPI}/communes/{insee}?fields=epci",
               os.path.join(cache_dir, "epci", f"{insee}.json"))
    try:
        code = (json.loads(txt).get("epci") or {}).get("code")
    except (TypeError, ValueError, AttributeError):
        return None
    if not code:
        return None
    url = ANNUAIRE + "?" + urllib.parse.urlencode({
        "where": f'siren="{code}"', "limit": 3,
        "select": "nom,site_internet"})
    txt = lire(url, os.path.join(cache_dir, "epci", f"siren-{code}.json"))
    try:
        res = (json.loads(txt).get("results") or [])
    except (TypeError, ValueError):
        return None
    if not res:
        return None
    try:
        v = json.loads(res[0].get("site_internet") or "[]")
    except ValueError:
        return None
    site = (v[0].get("valeur") if v else None) or None
    return {"nom": res[0].get("nom"), "site": site} if site else None


def wp_recherche(base, insee, mots):
    """L'API de recherche de WordPress, qui ignore les menus.

    C'est le canal qui rend le mieux, et pour une raison de fond : la page
    qu'on cherche n'est presque jamais liee depuis l'accueil. Cachan range ses
    fiches sous /annuaire-des-equipements/, Challans sous /point-d-interet/,
    Saint-Medard sous /points-interets/ — aucune de ces trois n'apparait dans
    les 32 liens de la page d'accueil de sa commune. Une exploration en
    profondeur 2 ne les atteint donc jamais, et rendrait un « rien trouve » qui
    serait faux.

    Teste le 2 septembre 2026 sur quatre communes connues pour publier leurs
    horaires : Challans, Saint-Medard et Gap rendent la bonne fiche du premier
    coup, Cachan rend une liste vide (son wp-json existe mais n'expose pas ce
    type de contenu). D'ou les deux canaux de repli ci-dessous.
    """
    trouves = {}
    for mot in mots:
        if not mot:
            continue
        url = (urllib.parse.urljoin(base, "/wp-json/wp/v2/search") + "?" +
               urllib.parse.urlencode({"search": mot, "per_page": 10}))
        cle = re.sub(r"[^a-z0-9]+", "-", mot)[:40] or "vide"
        txt = lire(url, os.path.join(CACHE, "wp", insee, f"{cle}.json"))
        try:
            lot = json.loads(txt)
        except (TypeError, ValueError):
            continue
        if not isinstance(lot, list):
            continue
        for r in lot:
            u = r.get("url")
            if u and meme_hote(u, base):
                trouves[u] = r.get("title") or ""
    return trouves


def urls_devinees(base, nom, insee, rp):
    """A defaut de WordPress : la forme <base>/<prefixe>/<nom-en-slug>/.

    Douze essais par site, chacun une requete. C'est peu cher, et c'est ce qui
    rattrape Cachan — dont la fiche est exactement
    /annuaire-des-equipements/complexe-sportif-leo-lagrange/ — quand son API
    de recherche ne rend rien.
    """
    s = slug(nom)
    mots = [m for m in s.split("-") if len(m) > 3]
    if not s or not mots:
        return {}
    trouves, vus = {}, set()
    for prefixe in PREFIXES:
        chemin = f"/{prefixe}/{s}/" if prefixe else f"/{s}/"
        url = urllib.parse.urljoin(base, chemin)
        if not autorise(rp, url):
            continue
        cle = re.sub(r"[^a-z0-9]+", "-", chemin)[:60]
        html = lire(url, os.path.join(CACHE, "devine", insee, f"{cle}.html"))
        if not html:
            continue
        # Beaucoup de sites rendent 200 sur une URL inconnue — page d'erreur
        # habillee, ou fourre-tout qui sert l'accueil. Deux garde-fous : le
        # titre de la page doit nommer l'equipement, et deux URL qui rendent
        # exactement le meme corps ne comptent que pour une.
        titre = re.search(r"<title[^>]*>(.*?)</title>", html, re.S | re.I)
        titre = plier(re.sub(r"<[^>]+>", " ", titre.group(1))) if titre else ""
        if not all(m in titre for m in mots[-2:]):
            continue
        empreinte = hashlib.sha1(html.encode("utf-8", "replace")).hexdigest()
        if empreinte in vus:
            continue
        vus.add(empreinte)
        trouves[url] = ""
        # Une seule suffit, et il faut s'arreter la. Cachan sert la meme fiche
        # sous n'importe quel prefixe — /annuaire-des-equipements/, mais aussi
        # /points-interets/, /lieux/, /sport/ — avec un HTML chaque fois un peu
        # different : l'empreinte ne les rattrape pas, et on lisait douze fois
        # les memes horaires.
        break
    return trouves


def pages_sport(base, insee, rp):
    """Les pages du site communal qui peuvent porter une fiche d'equipement."""
    vus, gardees, file = set(), [], [(base, 0)]
    while file and len(vus) < MAX_PAGES:
        url, niveau = file.pop(0)
        if url in vus or niveau > PROFONDEUR or not autorise(rp, url):
            continue
        vus.add(url)
        cle = re.sub(r"[^a-z0-9]+", "-",
                     urllib.parse.urlsplit(url).path)[:80] or "index"
        html = lire(url, os.path.join(CACHE, "html", insee, f"{cle}.html"))
        if not html:
            continue
        if niveau:                       # l'accueil n'est jamais une fiche
            gardees.append((url, html))
        for m in re.finditer(r'<a[^>]+href="([^"#]+)"[^>]*>(.*?)</a>',
                             html, re.S | re.I):
            lien = urllib.parse.urljoin(url, m.group(1))
            if not meme_hote(lien, base):
                continue
            if lien.lower().split("?")[0].endswith((".pdf", ".jpg", ".png", ".zip")):
                continue
            texte = re.sub(r"<[^>]+>", " ", m.group(2))
            if niveau < PROFONDEUR and PISTE_PAGE.search(plier(texte + " " + lien)):
                file.append((lien, niveau + 1))
    return gardees


def chercher(base, insee, nom, cle_cache):
    """Les pages d'un site, par les trois canaux, du plus sur au moins sur.

    Rend (pages, canal, silence). `cle_cache` distingue le site de la mairie de
    celui de l'agglomeration, qui portent les memes chemins pour des pages
    differentes.
    """
    if not base.startswith("http"):
        base = "https://" + base
    rp = robots(base)
    if not autorise(rp, base):
        return [], None, "robots.txt interdit la visite"

    noms = mots_du_nom(nom)
    urls, canal = (wp_recherche(base, cle_cache, noms + [nom]),
                   "recherche WordPress")
    if not urls:
        urls, canal = urls_devinees(base, nom, cle_cache, rp), "URL devinee"
    pages = [(u, lire(u, os.path.join(
                 CACHE, "page", cle_cache,
                 re.sub(r"[^a-z0-9]+", "-", urllib.parse.urlsplit(u).path)[:70] + ".html")))
             for u in urls]
    pages = [(u, h) for u, h in pages if h]
    if not pages:
        pages, canal = pages_sport(base, cle_cache, rp), "exploration des pages"
    if not pages:
        return [], None, ("aucune page d'equipement trouvee : ni par la "
                          "recherche WordPress, ni par URL devinee, ni en "
                          "explorant depuis l'accueil")
    return pages, canal, None


def etudier(site):
    """Le dossier d'un site : la commune, ses pages, les horaires candidats."""
    fiche = {"id": site["id"], "nom": site["nom"], "ville": site["ville"],
             "commune": None, "site": None, "canal": None, "pages": 0,
             "candidats": [], "ecartes": 0, "silence": None}
    insee = insee_du_site(site)
    if not insee:
        fiche["silence"] = "code INSEE introuvable"
        return fiche
    m = mairie(insee, CACHE)
    if not m:
        fiche["silence"] = "commune absente de l'annuaire DILA"
        return fiche
    fiche["commune"] = m.get("nom")
    if not m.get("site"):
        fiche["silence"] = "l'annuaire DILA ne donne pas de site pour cette mairie"
        return fiche

    # Deux sites a interroger, et l'ordre compte : la commune d'abord, parce
    # qu'une fiche d'equipement y est plus souvent qu'ailleurs ; l'agglomeration
    # ensuite, parce que c'est elle qui gere l'installation dans la moitie des
    # cas ou l'horaire existe. Voir epci().
    lieux = [(m["site"], insee, "mairie")]
    e = epci(insee, CACHE)
    if e:
        lieux.append((e["site"], f"epci-{urllib.parse.urlsplit(e['site']).netloc}",
                      f"agglomeration ({e['nom']})"))

    pages, canal, silences = [], None, []
    for base, cle_cache, quoi in lieux:
        p, c, silence = chercher(base, insee, site["nom"], cle_cache)
        if silence:
            silences.append(f"{quoi} : {silence}")
            continue
        fiche["site"] = fiche["site"] or base
        pages += p
        canal = canal or f"{c} sur le site de la {quoi}"
    fiche["site"] = fiche["site"] or m["site"]
    fiche["canal"] = canal
    fiche["pages"] = len(pages)
    if not pages:
        fiche["silence"] = " ; ".join(silences) or "aucune page d'equipement trouvee"
        return fiche

    # Plus le canal est large, plus le contenu doit etre strict. Une URL
    # devinee ou une recherche WordPress porte deja le nom de l'equipement :
    # la page est la bonne par construction. L'exploration, elle, ramene
    # n'importe quelle page du site — a La Chapelle-sur-Erdre elle a rendu
    # « Horaires d'ouverture du complexe de tennis de Gesvrine », une vraie
    # page d'equipement avec de vrais horaires publics, mais pas ceux du
    # complexe cherche. On y exige donc que le nom du stade figure pres de la
    # plage.
    exige_le_nom = bool(canal) and canal.startswith("exploration des pages")

    noms = mots_du_nom(site["nom"])
    vus = set()
    for url, html in pages:
        for e in extraits_horaires(html, noms, url):
            if e["retenu"] and exige_le_nom and not e["nomme"]:
                e["retenu"], e["motif"] = False, (
                    "page trouvee en explorant le site, et le nom de "
                    "l'equipement n'est pas dans la phrase : rien ne dit "
                    "qu'il s'agit de cette installation")
            if not e["retenu"]:
                fiche["ecartes"] += 1
                continue
            # Une fiche d'equipement repete ses horaires — en-tete, encadre,
            # pied de page. La meme plage sur la meme page est une seule
            # information, pas six.
            cle = (url, re.sub(r"\s+", "", e["plage"]))
            if cle in vus:
                continue
            vus.add(cle)
            fiche["candidats"].append(dict(e, url=url))
    # Le nom du stade dans la phrase passe devant : c'est le seul signe qui
    # dise qu'on tient la bonne installation et non la piscine municipale.
    fiche["candidats"].sort(key=lambda e: not e["nomme"])
    fiche["candidats"] = fiche["candidats"][:6]
    if not fiche["candidats"] and not fiche["silence"]:
        fiche["silence"] = (f"{len(pages)} page(s) lue(s), aucun horaire retenu"
                            + (f" ({fiche['ecartes']} ecarte(s))"
                               if fiche["ecartes"] else ""))
    return fiche


def raconter(f):
    print("=" * 72)
    print(f"  {f['id']}  {f['nom']} — {f['ville']}")
    if f["site"]:
        par = f" par {f['canal']}" if f.get("canal") else ""
        print(f"  mairie : {f['site']}  ({f['pages']} page(s){par})")
    if f["silence"]:
        print(f"  RIEN : {f['silence']}")
        return
    for c in f["candidats"]:
        marque = "NOMME" if c["nomme"] else "     "
        print(f"  [{marque}] {c['plage']}")
        print(f"          {c['url']}")
        extrait = re.sub(r"\s+", " ", c["extrait"])
        print(f"          « …{extrait[:300]}… »")
    if f["ecartes"]:
        print(f"  ({f['ecartes']} plage(s) ecartee(s) : mairie, sans jour, "
              f"ou hors contexte sportif)")


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cible", help="un identifiant de site, un code INSEE, "
                                  "ou un numero de departement")
    ap.add_argument("--limite", type=int, default=10,
                    help="nombre de sites a etudier (defaut 10)")
    ap.add_argument("--json", metavar="FICHIER",
                    help="ecrire le releve complet, extraits compris")
    args = ap.parse_args()

    sites = [s for s in charger_sites() if s.get("piste")]
    # charger_sites() ne rend pas le type de piste : on le rattache ici plutot
    # que d'elargir une fonction dont conseils_municipaux depend aussi.
    with open(os.path.join(ROOT, "data", "tracks.json"), encoding="utf-8") as fp:
        brut = json.load(fp)
    tp = {t["i"]: t.get("tp") for t in brut["tracks"]}
    for s in sites:
        s["type_piste"] = tp.get(s["id"])
    c = args.cible
    if re.fullmatch(r"I\d+|c-.+", c):
        choisis = [s for s in sites if s["id"] == c]
    elif re.fullmatch(r"\d{5}", c):
        choisis = [s for s in sites if (s["id"] or "")[1:6] == c]
    else:
        choisis = [s for s in sites if s.get("dep") == c.zfill(2)]
    if not choisis:
        sys.exit(f"Aucun site pour « {c} ».")

    # Les stades d'athletisme d'abord : ce sont eux qu'on cherche a documenter,
    # et une piste isolee n'a presque jamais de fiche d'equipement dediee.
    choisis.sort(key=lambda s: (s.get("type_piste") != "stade", s["id"]))
    choisis = choisis[:args.limite]
    print(f"{len(choisis)} site(s) a etudier.\n")

    fiches = []
    for s in choisis:
        f = etudier(s)
        fiches.append(f)
        raconter(f)

    avec = [f for f in fiches if f["candidats"]]
    print("\n" + "=" * 72)
    print(f"{len(avec)} site(s) sur {len(fiches)} avec au moins un horaire retenu "
          f"({100 * len(avec) / len(fiches):.0f} %), "
          f"{sum(len(f['candidats']) for f in fiches)} candidat(s), "
          f"{sum(f['ecartes'] for f in fiches)} plage(s) ecartee(s).")
    print("\nAucun de ces horaires n'est un fait tant que personne ne l'a lu :\n"
          "verifiez que la page parle bien de CETTE installation, puis ecrivez\n"
          "dans data/overrides/<id>.json en citant l'URL et la date.\n"
          "Rappel : le site de l'agglomeration n'est pas explore. Un silence\n"
          "d'ici ne dit rien de beauvaisis.fr ou de valparisis.fr.")

    if args.json:
        os.makedirs(os.path.dirname(os.path.abspath(args.json)), exist_ok=True)
        with open(args.json, "w", encoding="utf-8") as fp:
            json.dump(fiches, fp, ensure_ascii=False, indent=2)
            fp.write("\n")
        print(f"-> {args.json}")


if __name__ == "__main__":
    main()
