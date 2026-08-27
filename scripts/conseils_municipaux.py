#!/usr/bin/env python3
"""Cherche dans les deliberations des conseils municipaux ce qui bouge sur un stade.

    python3 scripts/conseils_municipaux.py I441870004
    python3 scripts/conseils_municipaux.py 44187
    python3 scripts/conseils_municipaux.py 44 --limite 20 --json .work/conseils-44.json

Le recensement du ministere est une photographie, rafraichie lentement. Une
piste refaite, un sautoir ajoute, une enceinte rouverte au public : la commune
l'ecrit dans ses deliberations des mois avant que Data ES ne le sache, quand il
le sait. C'est la seule source publique qui *date* un changement au lieu de
decrire un etat.

Le chemin est entierement en donnees ouvertes :

- **l'annuaire de l'administration** (DILA, service-public.fr) donne, pour un
  code INSEE, le site internet de la mairie, son courriel, son telephone et ses
  horaires d'ouverture. C'est lui qui remplace la recherche a la main.
- **le site de la mairie** publie ordres du jour, convocations, listes de
  deliberations et proces-verbaux, presque toujours en PDF. Un site sur deux
  tourne sous WordPress : son API de medias les liste sans qu'on ait a explorer
  les pages.

Ce qui sort d'ici est une file de lecture, pas un fait. Une deliberation dit un
*projet vote*, pas un etat constate : elle n'a rien a faire dans un booleen ni
dans `renovation`, elle se raconte dans `note` avec sa date et son URL, et elle
ne devient un etat que le jour ou quelqu'un va voir. C'est la regle du § 5.2 de
docs/trouver-les-pistes-manquantes.md, et elle ne souffre pas d'exception ici.

Le script distingue donc trois silences, qui ne veulent pas dire la meme chose :
la commune n'a rien vote, la commune n'a rien publie, ou elle a publie des PDF
scannes sans couche texte. Ce dernier cas n'est plus une impasse : avec --ocr,
les scans sont rasterises et passes a tesseract, ce qui transforme un « on n'a
pas pu lire » en « on a lu, il n'y a rien ». L'OCR se trompe, lui : tout ce qui
en vient est signale comme tel dans la sortie et dans le JSON, et se relit a
l'oeil avant d'etre ecrit dans une fiche.

Annuaire de l'administration, DILA - Licence Ouverte 2.0.
Base officielle des codes geographiques / geo.api.gouv.fr - Licence Ouverte 2.0.
Les documents restent la propriete des communes : on n'en recopie que des extraits.
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TRACKS = os.path.join(ROOT, "data", "tracks.json")
UA = "pistes-athle/1.0 (github.com/Chardonneaur/pistes-athle)"
ENTETES = {"User-Agent": UA}

ANNUAIRE = ("https://api-lannuaire.service-public.fr/api/explore/v2.1/catalog/"
            "datasets/api-lannuaire-administration/records")
GEOAPI = "https://geo.api.gouv.fr"

# On visite le site d'une mairie, pas une API : on y va lentement.
PAUSE = 1.5

# Un PDF de deliberations pese rarement plus que ca. Au-dela, c'est un plan ou
# un dossier d'urbanisme : on ne le telecharge pas.
POIDS_MAX = 12 * 1024 * 1024

# En dessous, il n'y a pas de couche texte : le PDF est un scan.
TEXTE_MIN = 200

# L'OCR coute cher : ~3 s par page. Un proces-verbal de conseil depasse rarement
# la quarantaine de pages, et au-dela c'est un dossier annexe qu'on ne lit pas.
OCR_PAGES = 40
# 200 dpi en niveaux de gris suffit a du texte de traitement de texte scanne ;
# 300 dpi double le temps sans rien apporter ici.
OCR_DPI = 200
# Vingt pages a l'oeil prennent une minute et demie ; on laisse de la marge.
OCR_TIMEOUT = 600

# Les pages d'un site de mairie qui menent aux deliberations.
PISTE_PAGE = re.compile(
    r"conseil[- ]municipal|delibera|seance|compte[- ]rendu|proces[- ]verbal|"
    r"documenth|publications|vie[- ]municipale", re.I)

# Les documents qui sont des actes du conseil, et pas le bulletin municipal.
PISTE_DOC = re.compile(
    r"delibera|conseil|convocation|ordre[-_ ]?du[-_ ]?jour|seance|"
    r"compte[-_ ]?rendu|proces[-_ ]?verbal|\bpv\b|cm[-_ ]?\d", re.I)

# Les mois par leur debut : « pdftotext -layout » colle volontiers la lettre
# suivante au dernier mot d'une ligne (« du 29 juinl 2026 »), et un nom de
# fichier abrege (« 15-sept-2025 »). On reconnait donc un prefixe, pas un mot.
MOIS = {"janv": 1, "fevr": 2, "mars": 3, "avri": 4, "mai": 5, "juin": 6,
        "juil": 7, "aout": 8, "sept": 9, "octo": 10, "nove": 11, "dece": 12}
MOIS_RX = "(" + "|".join(sorted(MOIS, key=len, reverse=True)) + ")"

# Trois vocabulaires. Le premier suffit a lui seul : il ne parle que de nous.
# Les deux autres ne comptent qu'ensemble - un « stade » sans « travaux » est
# une subvention au club de foot, et des « travaux » sans « stade » sont la
# toiture de l'ecole.
LEXIQUE = {
    "piste": r"piste d.athletisme|piste d.athle|athletisme|athletique|cendree|"
             r"tartan|revetement synthetique|anneau (?:de|d.)\s*(?:course|athletisme)|"
             r"sautoir|saut en (?:longueur|hauteur)|saut a la perche|"
             r"lancer (?:du|de) (?:poids|disque|marteau|javelot)|"
             r"couloirs? de course|ligne droite",
    "stade": r"\bstade\b|terrain d.honneur|city.?stade|plateau (?:multi.?)?sportif|"
             r"equipements? sportifs?|complexe sportif|installations? sportives?|"
             r"vestiaires?|tribunes?|club.?house|terrain (?:de )?(?:football|foot|rugby)|"
             r"eclairage (?:du|des|de la) (?:stade|terrain|piste)",
    # « marche » tout court attrapait le marche d'approvisionnement du samedi
    # matin : un mot de travaux doit parler de travaux, pas de commerce.
    "travaux": r"travaux|refection|renovation|rehabilitation|amenagement|"
               r"requalification|restructuration|resurfacage|remise en etat|"
               r"mise aux normes|maitrise d.{0,2}uvre|marche (?:public|de travaux|"
               r"de maitrise)|appel d.offres|(?:demande|sollicitation) de subvention|"
               r"\bDETR\b|\bDSIL\b|programme pluriannuel|autorisation de programme|"
               r"etude de faisabilite|desaffectation|declassement|demolition|"
               r"cession (?:de|du|d.)|acquisition (?:de|du|d.)",
}
LEXIQUE = {k: re.compile(v, re.I) for k, v in LEXIQUE.items()}


def plier(s):
    """Minuscules sans accents, *a longueur constante* : les index restent bons.

    On cherche dans le texte plie et on cite le texte d'origine ; si la pliure
    decalait les positions d'un caractere, chaque citation serait tronquee.
    """
    out = []
    for c in s:
        if c in "œŒ":       # oe collé
            out.append("o")
            continue
        if c in "æÆ":       # ae collé
            out.append("a")
            continue
        d = unicodedata.normalize("NFD", c)
        b = "".join(x for x in d if unicodedata.category(x) != "Mn")
        out.append(b[0] if b else c)
    return "".join(out).lower()


def lire(url, cache=None, binaire=False, timeout=30):
    """Telecharge, en gardant une copie sur disque : on ne demande jamais deux fois."""
    if cache and os.path.exists(cache):
        with open(cache, "rb") as f:
            brut = f.read()
        return brut if binaire else brut.decode("utf-8", "replace")
    req = urllib.request.Request(url, headers=ENTETES)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            taille = int(r.headers.get("Content-Length") or 0)
            if binaire and taille > POIDS_MAX:
                return None
            brut = r.read(POIDS_MAX + 1)
    except (urllib.error.URLError, urllib.error.HTTPError, OSError, ValueError):
        return None
    if binaire and len(brut) > POIDS_MAX:
        return None
    if cache:
        os.makedirs(os.path.dirname(cache), exist_ok=True)
        with open(cache, "wb") as f:
            f.write(brut)
    time.sleep(PAUSE)
    return brut if binaire else brut.decode("utf-8", "replace")


def robots(base):
    """Un robot poli demande d'abord. Un robots.txt illisible ne bloque pas."""
    rp = urllib.robotparser.RobotFileParser()
    rp.set_url(urllib.parse.urljoin(base, "/robots.txt"))
    try:
        rp.read()
    except Exception:
        return None
    return rp


def autorise(rp, url):
    return True if rp is None else rp.can_fetch(UA, url)


# --------------------------------------------------------------------------
# 1. De quoi parle-t-on : un site, une commune
# --------------------------------------------------------------------------

def charger_sites():
    """Tous les sites de l'annuaire, avec ce dont ce script a besoin.

    osm_longueurs.charger_sites() faisait l'affaire jusqu'a ce qu'elle prenne un
    departement en argument et se mette a filtrer dessus : l'appel d'ici, reste
    sans argument, levait un TypeError, et le dictionnaire qu'elle rend n'a de
    toute facon pas la cle `dep` sur laquelle main() trie ensuite. Un chargeur
    de trois lignes vaut mieux qu'un emprunt qui derive."""
    with open(TRACKS, encoding="utf-8") as f:
        data = json.load(f)
    cle = {v: k for k, v in data["keymap"].items()}
    champs = ("id", "nom", "ville", "cp", "dep", "lat", "lon", "piste")
    return [{k: t.get(cle[k]) for k in champs} for t in data["tracks"]]


def insee_du_site(site):
    """Le code INSEE est dans l'identifiant du recensement : I + INSEE + rang.

    I441870004 -> 44187, Saint-Pere-en-Retz. Pour une piste `c-...`, contribuee
    et donc sans identifiant ministere, on redemande a la geolocalisation.
    """
    ident = site.get("id") or ""
    m = re.match(r"^I(\d{5})\d+$", ident)
    if m:
        return m.group(1)
    if site.get("lat") is None:
        return None
    url = (f"{GEOAPI}/communes?lat={site['lat']}&lon={site['lon']}"
           f"&fields=code&format=json")
    txt = lire(url)
    try:
        return (json.loads(txt) or [{}])[0].get("code")
    except (TypeError, ValueError, IndexError):
        return None


def mairie(insee, cache_dir):
    """Le site, le courriel, le telephone et les horaires, par l'annuaire DILA."""
    cache = os.path.join(cache_dir, "annuaire", f"{insee}.json")
    url = ANNUAIRE + "?" + urllib.parse.urlencode({
        "where": f'pivot LIKE "mairie" and code_insee_commune="{insee}"',
        "limit": 5,
    })
    txt = lire(url, cache)
    try:
        res = json.loads(txt).get("results") or []
    except (TypeError, ValueError):
        return None
    if not res:
        return None
    r = res[0]

    def premier(champ, cle="valeur"):
        try:
            v = json.loads(r.get(champ) or "[]")
        except ValueError:
            return None
        return (v[0].get(cle) if v else None) or None

    return {
        "insee": insee,
        "nom": r.get("nom"),
        "site": premier("site_internet"),
        "courriel": r.get("adresse_courriel") or None,
        "telephone": premier("telephone"),
        "horaires": r.get("plage_ouverture") or None,
    }


# --------------------------------------------------------------------------
# 2. Trouver les documents du conseil sur le site de la commune
# --------------------------------------------------------------------------

def medias_wordpress(base, cache_dir, insee):
    """L'API des medias de WordPress liste les PDF sans qu'on explore le site."""
    trouves = {}
    for terme in ("deliberation", "conseil municipal", "proces-verbal",
                  "compte-rendu", "ordre du jour", "convocation", "seance"):
        url = (urllib.parse.urljoin(base, "/wp-json/wp/v2/media") + "?" +
               urllib.parse.urlencode({"search": terme, "per_page": 100,
                                       "_fields": "source_url,date,title"}))
        cle = re.sub(r"[^a-z0-9]+", "-", terme)
        txt = lire(url, os.path.join(cache_dir, "wp", insee, f"{cle}.json"))
        try:
            lot = json.loads(txt)
        except (TypeError, ValueError):
            continue
        if not isinstance(lot, list):
            continue
        for m in lot:
            u = m.get("source_url") or ""
            if u.lower().endswith(".pdf"):
                trouves[u] = m.get("date") or ""
    return trouves


def explore(base, cache_dir, insee, rp, profondeur=2):
    """A defaut de WordPress : on suit les liens qui parlent du conseil."""
    hote = urllib.parse.urlsplit(base).netloc
    vus, pdf, file = set(), {}, [(base, 0)]
    while file:
        url, niveau = file.pop(0)
        if url in vus or niveau > profondeur or not autorise(rp, url):
            continue
        vus.add(url)
        cle = re.sub(r"[^a-z0-9]+", "-", urllib.parse.urlsplit(url).path)[:80] or "index"
        html = lire(url, os.path.join(cache_dir, "html", insee, f"{cle}.html"))
        if not html:
            continue
        for m in re.finditer(r'<a[^>]+href="([^"#]+)"[^>]*>(.*?)</a>', html, re.S | re.I):
            lien = urllib.parse.urljoin(url, m.group(1))
            if urllib.parse.urlsplit(lien).netloc != hote:
                continue
            texte = re.sub(r"<[^>]+>", " ", m.group(2))
            if lien.lower().split("?")[0].endswith(".pdf"):
                pdf.setdefault(lien, "")
            elif niveau < profondeur and PISTE_PAGE.search(plier(texte + " " + lien)):
                file.append((lien, niveau + 1))
        if len(vus) > 40:
            break
    return pdf


def documents(base, cache_dir, insee):
    rp = robots(base)
    if not autorise(rp, base):
        return {}, "robots.txt interdit la visite"
    trouves = medias_wordpress(base, cache_dir, insee)
    source = "API WordPress"
    if not trouves:
        trouves = explore(base, cache_dir, insee, rp)
        source = "exploration des pages"
    return {u: d for u, d in trouves.items()
            if PISTE_DOC.search(urllib.parse.unquote(u).rsplit("/", 1)[-1])}, source


# --------------------------------------------------------------------------
# 3. Lire les PDF et y chercher le stade
# --------------------------------------------------------------------------

def texte_pdf(chemin, ocr=False, ocr_pages=OCR_PAGES, _memo={}):
    """Une commune porte souvent plusieurs stades : on n'extrait qu'une fois.

    Rend (texte, par_ocr). `par_ocr` dit que le texte sort de tesseract et non
    d'une couche texte : il se lit avec les reserves qui vont avec.
    """
    cle = (chemin, bool(ocr), ocr_pages)
    if cle not in _memo:
        _memo[cle] = _texte_pdf(chemin, ocr, ocr_pages)
    return _memo[cle]


def _texte_pdf(chemin, ocr, ocr_pages):
    try:
        r = subprocess.run(["pdftotext", "-layout", chemin, "-"],
                           capture_output=True, text=True, timeout=90)
        if r.returncode == 0 and len(r.stdout.strip()) >= TEXTE_MIN:
            return r.stdout, False
    except (OSError, subprocess.SubprocessError):
        pass
    try:
        import pypdf
        pages = pypdf.PdfReader(chemin).pages
        texte = "\n".join(p.extract_text() or "" for p in pages)
        if len(texte.strip()) >= TEXTE_MIN:
            return texte, False
    except Exception:
        texte = ""
    if ocr:
        lu = texte_ocr(chemin, ocr_pages)
        if len(lu.strip()) >= TEXTE_MIN:
            return lu, True
    return texte, False


# --------------------------------------------------------------------------
# 3 bis. Lire a l'oeil les PDF scannes
# --------------------------------------------------------------------------

def outils_ocr(_memo={}):
    """pdftoppm et tesseract sont-ils la, et dans quelle langue lit-on ?

    Le pack francais donne un texte nettement plus propre, mais l'anglais suffit
    a reperer « stade », « piste » ou « athletisme » : ce sont des mots dont les
    lettres ne changent pas d'un modele a l'autre. On prend donc ce qu'il y a.
    """
    if "ok" not in _memo:
        _memo["ok"] = all(shutil.which(x) for x in ("pdftoppm", "tesseract"))
        _memo["langue"] = None
        if _memo["ok"]:
            try:
                r = subprocess.run(["tesseract", "--list-langs"],
                                   capture_output=True, text=True, timeout=30)
                dispo = set((r.stdout + r.stderr).split())
                _memo["langue"] = "fra" if "fra" in dispo else "eng"
            except (OSError, subprocess.SubprocessError):
                _memo["langue"] = "eng"
    return _memo["ok"], _memo["langue"]


def texte_ocr(chemin, ocr_pages):
    """Rasterise le PDF et le passe a tesseract. Le resultat est mis en cache.

    Le cache est un `.ocr.txt` pose a cote du PDF telecharge : relancer le
    script sur la meme commune ne repaie pas la minute d'OCR.
    """
    cache = chemin + ".ocr.txt"
    if os.path.exists(cache):
        try:
            with open(cache, encoding="utf-8") as f:
                return f.read()
        except OSError:
            pass

    ok, langue = outils_ocr()
    if not ok:
        return ""

    morceaux = []
    with tempfile.TemporaryDirectory(prefix="pistes-ocr-") as tmp:
        prefixe = os.path.join(tmp, "p")
        try:
            subprocess.run(["pdftoppm", "-r", str(OCR_DPI), "-gray", "-png",
                            "-f", "1", "-l", str(ocr_pages), chemin, prefixe],
                           capture_output=True, timeout=OCR_TIMEOUT)
        except (OSError, subprocess.SubprocessError):
            return ""
        for page in sorted(f for f in os.listdir(tmp) if f.endswith(".png")):
            try:
                r = subprocess.run(["tesseract", os.path.join(tmp, page), "-",
                                    "-l", langue, "--psm", "6"],
                                   capture_output=True, text=True,
                                   timeout=OCR_TIMEOUT)
            except (OSError, subprocess.SubprocessError):
                continue
            if r.returncode == 0:
                morceaux.append(r.stdout)

    texte = "\n".join(morceaux)
    if texte.strip():
        try:
            with open(cache, "w", encoding="utf-8") as f:
                f.write(texte)
        except OSError:
            pass
    return texte


def date_seance(url, texte):
    """La date de la seance, prise dans le texte ; a defaut, dans le nom du fichier."""
    for source in (plier(texte[:4000]),
                   plier(urllib.parse.unquote(url).rsplit("/", 1)[-1])):
        m = re.search(r"\b(\d{1,2})(?:er)?[-_ ]+" + MOIS_RX +
                      r"[a-z]*\.?[-_ ]+((?:19|20)\d\d)", source)
        if m:
            return f"{m.group(3)}-{MOIS[m.group(2)]:02d}-{int(m.group(1)):02d}"
    nom = plier(urllib.parse.unquote(url).rsplit("/", 1)[-1])
    m = re.search(r"((?:19|20)\d\d)-(\d{2})-(\d{2})", nom)
    if m:
        return m.group(0)
    m = re.search(r"(?<!\d)(\d{2})[-_]?(\d{2})[-_]?((?:19|20)\d\d)(?!\d)", nom)
    if m and 1 <= int(m.group(2)) <= 12:
        return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
    return ""


def extrait(texte, plie, m, marge=130):
    a, b = max(0, m.start() - marge), min(len(texte), m.end() + marge)
    return re.sub(r"\s+", " ", texte[a:b]).strip()


def signaux(texte, noms):
    """Les passages a lire. On rend aussi de quel vocabulaire ils viennent.

    Le vocabulaire de l'athletisme se suffit : il ne parle que de nous. Le nom
    du stade, non - a Ancenis-Saint-Gereon, « la Davrays » nomme aussi bien le
    stade que la residence pour personnes agees, et quatre deliberations sur le
    CCAS remontaient a ce titre. Un toponyme ne vaut donc qu'accompagne d'un mot
    de travaux, comme le vocabulaire general du stade.
    """
    plie = plier(texte)
    trouve = {k: [m for m in rx.finditer(plie)] for k, rx in LEXIQUE.items()}
    for nom in noms:
        if nom:
            trouve.setdefault("nom", []).extend(re.finditer(re.escape(plier(nom)), plie))
    if not trouve.get("piste") and not (
            trouve["travaux"] and (trouve.get("nom") or trouve["stade"])):
        return []
    out, vus = [], set()
    for cle in ("nom", "piste", "stade"):
        for m in trouve.get(cle, []):
            e = extrait(texte, plie, m)
            if e[:60] in vus:
                continue
            vus.add(e[:60])
            out.append({"vocabulaire": cle, "extrait": e})
    return out[:8]


def mots_du_nom(nom):
    """« Complexe Sportif du Parc du Grand Fay » -> « grand fay ».

    On ne garde que ce qui identifie *ce* stade : les mots de categorie
    reviennent dans toutes les deliberations et n'apprennent rien.
    """
    banal = {"complexe", "sportif", "sportive", "stade", "parc", "terrain",
             "municipal", "municipale", "salle", "espace", "plaine", "jeux",
             "des", "du", "de", "la", "le", "les", "d", "l", "et", "aux", "au"}
    mots = [m for m in re.split(r"[^a-z0-9]+", plier(nom or "")) if m and m not in banal]
    return [" ".join(mots)] if len(mots) >= 2 else mots


# --------------------------------------------------------------------------

def etudier(site, cache_dir, max_docs, depuis, ocr=False, ocr_pages=OCR_PAGES):
    fiche = {"id": site["id"], "nom": site["nom"], "ville": site["ville"],
             "mairie": None, "documents": [], "illisibles": [], "signaux": []}
    insee = insee_du_site(site)
    fiche["insee"] = insee
    if not insee:
        fiche["silence"] = "code INSEE introuvable"
        return fiche

    m = mairie(insee, cache_dir)
    fiche["mairie"] = m
    if not m or not m.get("site"):
        fiche["silence"] = "l'annuaire de l'administration ne donne pas de site web"
        return fiche

    docs, source = documents(m["site"], cache_dir, insee)
    fiche["source_documents"] = source
    if not docs:
        fiche["silence"] = f"aucun acte du conseil publie en PDF ({source})"
        return fiche

    noms = mots_du_nom(site.get("nom"))
    lus, vus, extraits = [], set(), set()
    for url in sorted(docs, key=lambda u: docs[u], reverse=True)[:max_docs]:
        # Les mairies republient le meme acte sous plusieurs URL : « -1 », « -2 »,
        # un dossier par mois. Le nom du fichier ne suffit donc pas a nommer la
        # copie locale, et le contenu ne se lit qu'une fois.
        nom = re.sub(r"[^A-Za-z0-9._-]", "_", urllib.parse.unquote(url).rsplit("/", 1)[-1])
        empreinte = hashlib.sha1(url.encode()).hexdigest()[:8]
        chemin = os.path.join(cache_dir, "pdf", insee, f"{empreinte}-{nom}")
        if not os.path.exists(chemin):
            if lire(url, chemin, binaire=True, timeout=60) is None:
                continue
        texte, par_ocr = texte_pdf(chemin, ocr, ocr_pages)
        date = date_seance(url, texte)
        if depuis and date and date < depuis:
            continue
        if len(texte.strip()) < TEXTE_MIN:
            fiche["illisibles"].append({"url": url, "date": date})
            continue
        corps = hashlib.sha1(re.sub(r"\s+", " ", texte).strip().encode()).hexdigest()
        if corps in vus:
            continue
        vus.add(corps)
        lus.append({"url": url, "date": date, "ocr": par_ocr})
        for s in signaux(texte, noms):
            if s["extrait"][:60] in extraits:
                continue
            extraits.add(s["extrait"][:60])
            s.update(url=url, date=date, ocr=par_ocr)
            fiche["signaux"].append(s)

    fiche["documents"] = lus
    fiche["signaux"].sort(key=lambda s: s["date"], reverse=True)
    if not fiche["signaux"]:
        vu_ocr = sum(1 for d in lus if d.get("ocr"))
        detail = f" (dont {vu_ocr} par OCR)" if vu_ocr else ""
        fiche["silence"] = (f"{len(lus)} acte(s) lu(s){detail}, rien sur le stade"
                            if lus else "aucun acte lisible")
    return fiche


def raconter(f):
    print(f"\n{'=' * 78}\n{f['nom']} — {f['ville']}  [{f['id']}]")
    m = f.get("mairie")
    if m:
        print(f"  mairie   {m.get('site') or '(pas de site)'}"
              f"   {m.get('courriel') or ''}   {m.get('telephone') or ''}")
    if f.get("documents"):
        # Savoir *ce qui a ete lu* vaut autant que les passages trouves : c'est
        # ce qui permet d'ecrire « rien vote entre telle et telle seance »
        # plutot que « rien vote », qu'aucune lecture ne peut etablir.
        dates = sorted({d["date"] for d in f["documents"] if d["date"]}, reverse=True)
        vu_ocr = sum(1 for d in f["documents"] if d.get("ocr"))
        print(f"  {len(f['documents'])} acte(s) lu(s)"
              + (f", dont {vu_ocr} scanne(s) lu(s) par OCR" if vu_ocr else "")
              + (f" — seances du {', '.join(dates)}" if dates else ""))
    if f.get("signaux"):
        print(f"  {len(f['signaux'])} passage(s) a lire :")
        for s in f["signaux"]:
            marque = "  [OCR — a relire a l'oeil]" if s.get("ocr") else ""
            print(f"\n   {s['date'] or '(date ?)'}  [{s['vocabulaire']}]{marque}")
            print(f"      … {s['extrait']}")
            print(f"      {s['url']}")
    if f.get("illisibles"):
        ok, _ = outils_ocr()
        raison = ("relancez avec --ocr pour les lire" if ok else
                  "installez pdftoppm et tesseract, puis relancez avec --ocr")
        print(f"\n  {len(f['illisibles'])} PDF sans couche texte (scan) — "
              f"{raison} :")
        for d in f["illisibles"][:5]:
            print(f"      {d['date'] or '(date ?)'}  {d['url']}")
    if f.get("silence"):
        print(f"  silence : {f['silence']}")
        print("            cela ne dit pas qu'il n'y a pas de projet — "
              "seulement qu'on n'en a pas lu.")


def main():
    p = argparse.ArgumentParser(
        description="Ce que les conseils municipaux disent des stades",
        epilog="Aucune ligne de sortie n'est un fait : ce sont des documents a lire.")
    p.add_argument("cible", help="identifiant de site (I441870004, c-piste-casson), "
                                 "code INSEE (44187) ou code departement (44)")
    p.add_argument("--limite", type=int, default=0, help="nombre de sites (departement)")
    p.add_argument("--docs", type=int, default=12, help="PDF lus par commune (defaut 12)")
    p.add_argument("--depuis", default="", help="ignorer les seances avant AAAA-MM-JJ")
    p.add_argument("--ocr", action="store_true",
                   help="lire les PDF scannes avec tesseract (~3 s par page)")
    p.add_argument("--ocr-pages", type=int, default=OCR_PAGES,
                   help=f"pages ocerisees par PDF (defaut {OCR_PAGES})")
    p.add_argument("--cache-dir", default=os.path.join(ROOT, ".work", "conseils"))
    p.add_argument("--json", help="ecrire le detail dans ce fichier")
    args = p.parse_args()

    tous = charger_sites()
    cible = args.cible
    if re.match(r"^(I[0-9A-Z]{9,}|c-[a-z0-9-]+)$", cible):
        sites = [s for s in tous if s["id"] == cible]
    elif re.match(r"^\d{5}$", cible):
        sites = [s for s in tous if insee_du_site(s) == cible]
    elif re.match(r"^\d{2,3}$", cible):
        sites = [s for s in tous if s.get("dep") == cible and s.get("piste")]
    else:
        sys.exit(f"cible '{cible}' incomprise")
    if not sites:
        sys.exit(f"aucun site pour '{cible}' dans data/tracks.json")
    if args.limite:
        sites = sites[:args.limite]

    print(f"{len(sites)} site(s). Les deliberations disent des projets votes, "
          f"jamais un etat\nconstate : rien de ce qui suit ne s'ecrit dans un booleen.")

    if args.ocr:
        ok, langue = outils_ocr()
        if not ok:
            sys.exit("--ocr demande pdftoppm (poppler-utils) et tesseract, "
                     "absents de cette machine.")
        print(f"OCR actif ({langue}, {args.ocr_pages} pages max par PDF) : les scans "
              f"seront lus,\nmais l'OCR se trompe — tout ce qui en vient est marque "
              f"et se relit a l'oeil.")

    fiches = []
    for s in sites:
        f = etudier(s, args.cache_dir, args.docs, args.depuis,
                    args.ocr, args.ocr_pages)
        raconter(f)
        fiches.append(f)

    avec = sum(1 for f in fiches if f.get("signaux"))
    # Une commune porte souvent plusieurs stades et le meme PDF revient dans
    # chaque fiche : on compte les fichiers, pas les occurrences.
    scans = {d["url"] for f in fiches for d in (f.get("illisibles") or [])}
    ocerises = {d["url"] for f in fiches for d in (f.get("documents") or [])
                if d.get("ocr")}
    muets = {f["insee"] for f in fiches
             if not f.get("mairie") or not f["mairie"].get("site")}
    print(f"\n{'=' * 78}\n{avec} site(s) avec un passage a lire, "
          f"{len(scans)} PDF scanne(s) a ouvrir a l'oeil, "
          f"{len(muets)} commune(s) sans site connu de l'annuaire.")
    if ocerises:
        print(f"{len(ocerises)} PDF scanne(s) lu(s) par OCR : leur contenu est "
              f"reconstitue, pas extrait.\nRelisez a l'oeil avant d'ecrire quoi que "
              f"ce soit dans une fiche.")
    elif scans and not args.ocr:
        print("Relancez avec --ocr pour lire les scans plutot que de les signaler.")

    if args.json:
        os.makedirs(os.path.dirname(os.path.abspath(args.json)), exist_ok=True)
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(fiches, f, ensure_ascii=False, indent=2)
            f.write("\n")
        print(f"-> {args.json}")


if __name__ == "__main__":
    main()
