#!/usr/bin/env python3
"""
Assemble le site publiable dans _site/ : l'application (français et anglais) plus
une page HTML complete par site et par departement, un plan de site, robots.txt
et llms.txt.

Pourquoi ces pages statiques : l'application est un fichier JSON de 1,5 Mo rendu
en JavaScript. Un moteur de recherche ou un agent IA qui ne l'execute pas ne voit
rien. Chaque installation recoit donc sa propre page HTML, lisible sans script,
avec ses donnees en JSON-LD.

Usage : python3 scripts/build_site.py [--out _site] [--url https://exemple.org/base]
"""

import argparse
import html
import json
import math
import os
import re
import shutil
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TRACKS = os.path.join(ROOT, "data", "tracks.json")

# URL ecrite en dur dans index.html ; remplacee partout si --url differe.
URL_DEFAUT = "https://chardonneaur.github.io/pistes-athle"


def url_du_site(explicite=None):
    if explicite:
        return explicite.rstrip("/")
    if os.environ.get("SITE_URL"):
        return os.environ["SITE_URL"].rstrip("/")
    depot = os.environ.get("GITHUB_REPOSITORY")           # « proprietaire/depot »
    if depot and "/" in depot:
        proprio, nom = depot.split("/", 1)
        if nom.lower() == f"{proprio.lower()}.github.io":
            return f"https://{proprio.lower()}.github.io"
        return f"https://{proprio.lower()}.github.io/{nom}"
    return URL_DEFAUT


# --------------------------------------------------------------------- langues
# Les libelles sont le miroir de assets/i18n.js : l'application les utilise a
# l'execution, ces pages-ci les utilisent a la generation.
SOL = {
    "fr": {"synthetique": "Synthétique (tartan)", "bitume": "Bitume / goudron",
           "cendree": "Cendrée / stabilisé", "sable": "Sable", "gazon": "Gazon",
           "naturel": "Surface naturelle", "interieur": "Sol intérieur"},
    "en": {"synthetique": "Synthetic (tartan)", "bitume": "Asphalt / tarmac",
           "cendree": "Cinder / gravel", "sable": "Sand", "gazon": "Grass",
           "naturel": "Natural surface", "interieur": "Indoor flooring"},
}
AGRES = {
    "fr": {"longueur": "Sautoir longueur", "triple": "Triple saut",
           "hauteur": "Sautoir hauteur", "perche": "Sautoir à la perche",
           "poids": "Lancer du poids", "disque": "Lancer du disque",
           "marteau": "Lancer du marteau", "javelot": "Lancer du javelot",
           "steeple": "Steeple", "saut_indetermine": "Aire de saut (type inconnu)",
           "lancer_indetermine": "Aire de lancer (type inconnue)"},
    "en": {"longueur": "Long jump pit", "triple": "Triple jump",
           "hauteur": "High jump area", "perche": "Pole vault",
           "poids": "Shot put", "disque": "Discus", "marteau": "Hammer throw",
           "javelot": "Javelin", "steeple": "Steeplechase",
           "saut_indetermine": "Jump area (type unknown)",
           "lancer_indetermine": "Throwing area (type unknown)"},
}
SOURCES = {
    "fr": ["Data ES (ministère)", "Data ES + communauté", "Contribution communautaire"],
    "en": ["Data ES (French sports ministry)", "Data ES + community", "Community contribution"],
}
ORDRE_AGRES = ["steeple", "longueur", "triple", "hauteur", "perche",
               "poids", "disque", "marteau", "javelot"]

T = {
    "fr": {
        "html_lang": "fr", "og_locale": "fr_FR", "autre": "en",
        "prefixe": "", "seg_site": "site", "seg_dep": "departement",
        "seg_index": "departements",
        "marque": "Où s'entraîner ?",
        "bascule": "English", "bascule_code": "EN",
        "accueil": "Accueil",
        "index_titre": "Pistes d'athlétisme par département",
        "index_desc": "Les {n} sites d'athlétisme recensés en France, département par département : "
                      "piste, revêtement, sautoirs, aires de lancer, accès.",
        "index_intro": "Chaque département renvoie vers la liste de ses installations d'athlétisme, "
                       "puis vers la fiche détaillée de chacune.",
        "dep_titre": "Pistes d'athlétisme en {dep}",
        "dep_desc": "Les {n} sites d'athlétisme du département {dep} ({reg}) : revêtement, "
                    "couloirs, sautoirs, aires de lancer, éclairage, accès libre.",
        "nb_sites": lambda n: f"{n} site{'s' if n > 1 else ''}",
        "sec_piste": "Piste", "sec_agres": "Agrès recensés",
        "sec_acces": "Accès & services", "sec_avis": "Avis des athlètes",
        "sec_photos": "Photos", "sec_proches": "Autres sites du département",
        "sec_aerienne": "Vue aérienne",
        "aerienne_alt": lambda n: f"Vue aérienne de {n}",
        "aerienne_legende": "Vue aérienne, à défaut de photo du site.",
        "aerienne_credit": "L'image peut avoir plusieurs années et ne dit rien de "
                           "l'état des agrès. © IGN — BD ORTHO®",
        "kv": {"revetement": "Revêtement", "developpement": "Développement",
               "couloirs": "Couloirs", "config": "Configuration",
               "service": "Mise en service", "renovation": "Dernière rénovation",
               "acces_libre": "Accès libre", "eclairage": "Éclairage",
               "vestiaires": "Vestiaires", "douches": "Douches",
               "sanitaires": "Sanitaires", "tribunes": "Tribunes",
               "type_site": "Type de site", "horaires": "Horaires"},
        "couverte": "Couverte / indoor", "plein_air": "Plein air",
        "oui": "Oui", "non": "Non", "non_reserve": "Non / réservé",
        "ouvert_horaires": "Ouvert au public (horaires)",
        "places": lambda n: f"{n} places",
        "enceinte_scolaire": "Enceinte scolaire",
        "itineraire": "Itinéraire", "ouvrir_appli": "Ouvrir dans l'application",
        "site_officiel": "Site officiel de l'équipement",
        "signaler": "Signaler une erreur ou compléter la fiche",
        "sans_nom": "Équipement d'athlétisme",
        "anonyme": "Anonyme",
        "pas_davis": "Personne n'a encore décrit ce site.",
        "sur_5": lambda n, k: f"{n} sur 5 · {k} avis",
        "mois": ["janvier", "février", "mars", "avril", "mai", "juin", "juillet",
                 "août", "septembre", "octobre", "novembre", "décembre"],
        "titre_site": lambda nom, ville, piste: (
            f"{nom} — piste d'athlétisme à {ville}" if piste
            else f"{nom} — équipement d'athlétisme à {ville}"),
        "source_note": lambda src: (
            f"Source : {src} — <a href=\"https://equipements.sports.gouv.fr/\">Data ES</a>, "
            "ministère chargé des Sports, Licence Ouverte 2.0. Les données sont déclaratives "
            "et peuvent être incomplètes : vérifiez les conditions d'accès avant de vous déplacer."),
        "voir_carte": "Voir la carte interactive",
        "voir_dep_carte": "Voir ces sites sur la carte",
        "annuaire": "Annuaire par département",
        "code_source": "Code source",
    },
    "en": {
        "html_lang": "en", "og_locale": "en_GB", "autre": "fr",
        "prefixe": "en/", "seg_site": "track", "seg_dep": "department",
        "seg_index": "departments",
        "marque": "Where to train?",
        "bascule": "Français", "bascule_code": "FR",
        "accueil": "Home",
        "index_titre": "Athletics tracks in France by department",
        "index_desc": "All {n} athletics venues recorded in France, department by department: "
                      "track, surface, jump and throwing areas, access.",
        "index_intro": "Each department links to the list of its athletics facilities, "
                       "and from there to the full record of each venue.",
        "dep_titre": "Athletics tracks in {dep}, France",
        "dep_desc": "The {n} athletics venues of the {dep} department ({reg}), France: surface, "
                    "lanes, jump and throwing areas, floodlighting, free access.",
        "nb_sites": lambda n: f"{n} venue{'s' if n > 1 else ''}",
        "sec_piste": "Track", "sec_agres": "Recorded facilities",
        "sec_acces": "Access & amenities", "sec_avis": "Athlete reviews",
        "sec_photos": "Photos", "sec_proches": "Other venues in the department",
        "sec_aerienne": "Aerial view",
        "aerienne_alt": lambda n: f"Aerial view of {n}",
        "aerienne_legende": "Aerial view, in the absence of a photo of the venue.",
        "aerienne_credit": "The image may be several years old and says nothing about "
                           "the state of the equipment. © IGN — BD ORTHO®",
        "kv": {"revetement": "Surface", "developpement": "Lap length",
               "couloirs": "Lanes", "config": "Setting",
               "service": "Opened", "renovation": "Last refurbished",
               "acces_libre": "Free access", "eclairage": "Floodlighting",
               "vestiaires": "Changing rooms", "douches": "Showers",
               "sanitaires": "Toilets", "tribunes": "Stand",
               "type_site": "Venue type", "horaires": "Opening hours"},
        "couverte": "Covered / indoor", "plein_air": "Outdoor",
        "oui": "Yes", "non": "No", "non_reserve": "No / members only",
        "ouvert_horaires": "Open to the public (set hours)",
        "places": lambda n: f"{n} seats",
        "enceinte_scolaire": "School grounds",
        "itineraire": "Directions", "ouvrir_appli": "Open in the app",
        "site_officiel": "Official website of the venue",
        "signaler": "Report an error or complete this record",
        "sans_nom": "Athletics facility",
        "anonyme": "Anonymous",
        "pas_davis": "Nobody has described this venue yet.",
        "sur_5": lambda n, k: f"{n} out of 5 · {k} review{'s' if k > 1 else ''}",
        "mois": ["January", "February", "March", "April", "May", "June", "July",
                 "August", "September", "October", "November", "December"],
        "titre_site": lambda nom, ville, piste: (
            f"{nom} — athletics track in {ville}, France" if piste
            else f"{nom} — athletics facility in {ville}, France"),
        "source_note": lambda src: (
            f"Source: {src} — <a href=\"https://equipements.sports.gouv.fr/\">Data ES</a>, "
            "French ministry for sport, Licence Ouverte 2.0. Records are self-declared and may be "
            "incomplete: check access conditions before travelling."),
        "voir_carte": "Open the interactive map",
        "voir_dep_carte": "Show these venues on the map",
        "annuaire": "Browse by department",
        "code_source": "Source code",
    },
}

E = html.escape


def rel(chemin):
    """Chemin relatif vers la racine du site depuis un repertoire publie."""
    return "../" * chemin.count("/")


def url_site(lang, ident):
    return f"{T[lang]['prefixe']}{T[lang]['seg_site']}/{ident}/"


def url_dep(lang, code):
    return f"{T[lang]['prefixe']}{T[lang]['seg_dep']}/{code}/"


def url_index(lang):
    return f"{T[lang]['prefixe']}{T[lang]['seg_index']}/"


def url_appli(lang):
    return T[lang]["prefixe"]


# ---------------------------------------------------------------------- donnees
def charger():
    with open(TRACKS, encoding="utf-8") as f:
        brut = json.load(f)
    km = brut["keymap"]
    deps = brut.get("deps", {})
    sites = []
    for rec in brut["tracks"]:
        t = {km.get(k, k): v for k, v in rec.items()}
        for cle in ("piste", "couvert", "eclairage", "acces_libre", "ouvert_public",
                    "vestiaires", "douches", "sanitaires", "scolaire"):
            t[cle] = bool(t.get(cle))
        t["agres"] = t.get("agres") or []
        t["agres_probables"] = t.get("agres_probables") or []
        t["photos"] = t.get("photos") or []
        t["avis"] = t.get("avis") or []
        t["nb_avis"] = t.get("nb_avis") or 0
        d = deps.get(t.get("dep") or "", ["", ""])
        t["dep_nom"], t["region"] = d[0], d[1]
        sites.append(t)
    return brut, sites, deps


def tri_agres(liste):
    return sorted(liste, key=lambda a: ORDRE_AGRES.index(a) if a in ORDRE_AGRES else 99)


def nom_de(t, lang):
    return t.get("nom") or T[lang]["sans_nom"]


def phrase_liste(elements, lang):
    """« a, b et c » / “a, b and c ”."""
    if not elements:
        return ""
    if len(elements) == 1:
        return elements[0]
    liaison = " et " if lang == "fr" else " and "
    return ", ".join(elements[:-1]) + liaison + elements[-1]


def resume(t, lang):
    """Paragraphe d'introduction, en phrases completes."""
    nom, ville = nom_de(t, lang), t.get("ville") or ""
    lieu = ville + (f" ({t['dep_nom']})" if t.get("dep_nom") else "")
    if lang == "fr":
        p = [f"<strong>{E(nom)}</strong> est un équipement d'athlétisme situé à {E(lieu)}"
             + (f", en {E(t['region'])}." if t.get("region") else ".")]
    else:
        p = [f"<strong>{E(nom)}</strong> is an athletics venue in {E(lieu)}"
             + (f", {E(t['region'])}, France." if t.get("region") else ", France.")]

    if t["piste"]:
        sol = SOL[lang].get(t.get("surface"), t.get("surface"))
        longueur = f"{t['longueur_piste']} m" if t.get("longueur_piste") else ""
        if lang == "fr":
            bout = "Il dispose d'une piste"
            if longueur:
                bout += f" de {longueur}"
            if sol:
                bout += f" en {sol.lower()}"
            if t.get("couloirs"):
                bout += f", à {t['couloirs']} couloirs"
        else:
            bout = "It has a"
            bout += f" {longueur}" if longueur else "n"
            if sol:
                bout += f" {sol.lower()}"
            bout += " running track"
            if t.get("couloirs"):
                bout += f" with {t['couloirs']} lanes"
        p.append(bout + ".")

    agres = [AGRES[lang][a].lower() for a in tri_agres(t["agres"]) if a in AGRES[lang]]
    if agres:
        p.append(("On y trouve " if lang == "fr" else "It also offers ")
                 + phrase_liste(agres, lang) + ".")

    services = []
    if t["eclairage"]:
        services.append("l'éclairage" if lang == "fr" else "floodlighting")
    if t["couvert"]:
        services.append("une piste couverte" if lang == "fr" else "an indoor track")
    if t["vestiaires"]:
        services.append("des vestiaires" if lang == "fr" else "changing rooms")
    if t["douches"]:
        services.append("des douches" if lang == "fr" else "showers")
    if services:
        p.append(("Le site propose " if lang == "fr" else "The venue provides ")
                 + phrase_liste(services, lang) + ".")

    if t["acces_libre"]:
        p.append("L'accès est libre." if lang == "fr" else "Access is free and unrestricted.")
    elif t["ouvert_public"]:
        p.append("Le site est ouvert au public sur certains horaires." if lang == "fr"
                 else "The venue is open to the public at set times.")
    return " ".join(p)


def description(t, lang):
    """Meta description : les faits saillants, coupes a 160 caracteres."""
    faits = []
    if t["piste"]:
        bout = []
        if t.get("longueur_piste"):
            bout.append(f"{t['longueur_piste']} m")
        if t.get("surface"):
            bout.append(SOL[lang].get(t["surface"], t["surface"]))
        if t.get("couloirs"):
            bout.append(f"{t['couloirs']} couloirs" if lang == "fr" else f"{t['couloirs']} lanes")
        faits.append(("Piste " if lang == "fr" else "Track ") + ", ".join(bout) if bout
                     else ("Piste d'athlétisme" if lang == "fr" else "Running track"))
    faits += [AGRES[lang][a] for a in tri_agres(t["agres"]) if a in AGRES[lang]]
    if t["eclairage"]:
        faits.append("éclairée" if lang == "fr" else "floodlit")
    if t["acces_libre"]:
        faits.append("accès libre" if lang == "fr" else "free access")
    tete = f"{nom_de(t, lang)}, {t.get('ville') or ''}"
    texte = tete + (" : " if lang == "fr" else " — ") + ", ".join(faits) + "."
    return texte[:157].rsplit(" ", 1)[0] + "…" if len(texte) > 160 else texte


def fmt_note(n, lang):
    return f"{n:.1f}".replace(".", ",") if lang == "fr" else f"{n:.1f}"


def fmt_date(iso, lang):
    """Les dates des avis sont en ISO ; on les rend lisibles sans dependre de la
    locale de la machine qui construit le site."""
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})$", iso or "")
    if not m:
        return iso
    annee, mois, jour = m.groups()
    return f"{int(jour)} {T[lang]['mois'][int(mois) - 1]} {annee}"


def etoiles(note, lang):
    plein = int(round(note))
    return ("<span class=\"stars\" aria-hidden=\"true\">" + "★" * plein + "☆" * (5 - plein)
            + "</span>")



IGN_WMS = "https://data.geopf.fr/wms-r/wms"


def vue_aerienne(t, largeur=960):
    """URL d'orthophoto IGN centree sur le site (Licence Ouverte 2.0).

    Servie en direct par la Geoplateforme : aucune image n'est stockee dans le
    depot. Ce n'est pas une photo du site — une orthophoto a souvent plusieurs
    annees et ne dit rien de l'etat des agres.
    """
    lat, lon = t.get("lat"), t.get("lon")
    if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
        return None
    hauteur = round(largeur * 9 / 16)
    lg = t.get("longueur_piste") or 0
    champ = 360 if lg >= 400 else (260 if lg else 300)
    dlat = (champ * hauteur / largeur) / 2 / 111132
    dlon = champ / 2 / (111320 * math.cos(math.radians(lat)))
    bbox = f"{lat - dlat},{lon - dlon},{lat + dlat},{lon + dlon}"
    return (f"{IGN_WMS}?SERVICE=WMS&VERSION=1.3.0&REQUEST=GetMap"
            "&LAYERS=HR.ORTHOIMAGERY.ORTHOPHOTOS&STYLES=&CRS=EPSG:4326"
            f"&BBOX={bbox}&WIDTH={largeur}&HEIGHT={hauteur}&FORMAT=image/jpeg")


def dimensions_jpeg(chemin):
    """Largeur et hauteur d'un JPEG, lues dans son marqueur SOF.

    Les photos vont du panorama au portrait : sans leurs dimensions reelles, la
    page reserve la mauvaise place et le contenu saute au chargement. On les lit
    a la main plutot que d'imposer Pillow a la construction du site."""
    try:
        with open(chemin, "rb") as f:
            donnees = f.read()
    except OSError:
        return None
    i = 2                                        # on saute le SOI (0xFFD8)
    while i + 9 < len(donnees):
        if donnees[i] != 0xFF:
            i += 1
            continue
        marqueur = donnees[i + 1]
        if marqueur in (0xD8, 0x01) or 0xD0 <= marqueur <= 0xD7:
            i += 2
            continue
        taille = int.from_bytes(donnees[i + 2:i + 4], "big")
        if 0xC0 <= marqueur <= 0xCF and marqueur not in (0xC4, 0xC8, 0xCC):
            hauteur = int.from_bytes(donnees[i + 5:i + 7], "big")
            largeur = int.from_bytes(donnees[i + 7:i + 9], "big")
            return largeur, hauteur
        i += 2 + taille
    return None


def distance(a, b, c, d):
    r = math.pi / 180
    dlat, dlon = (c - a) * r, (d - b) * r
    h = math.sin(dlat / 2) ** 2 + math.cos(a * r) * math.cos(c * r) * math.sin(dlon / 2) ** 2
    return 2 * 6371 * math.asin(math.sqrt(h))


# ------------------------------------------------------------------- gabarits
def entete(lang, titre, desc, chemin, alternatives, jsonld, url_base):
    """<head> commun : canonique, alternatives de langue, Open Graph, JSON-LD."""
    r = rel(chemin)
    autre = T[lang]["autre"]
    blocs = "\n".join(
        f'<script type="application/ld+json">{json.dumps(j, ensure_ascii=False).replace("</", "<\\/")}</script>'
        for j in jsonld)
    return f"""<!DOCTYPE html>
<html lang="{T[lang]['html_lang']}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{E(titre)}</title>
<meta name="description" content="{E(desc)}">
<meta name="theme-color" content="#0f172a">
<link rel="canonical" href="{url_base}/{chemin}">
<link rel="alternate" hreflang="fr" href="{url_base}/{alternatives['fr']}">
<link rel="alternate" hreflang="en" href="{url_base}/{alternatives['en']}">
<link rel="alternate" hreflang="x-default" href="{url_base}/{alternatives['fr']}">
<meta property="og:type" content="website">
<meta property="og:locale" content="{T[lang]['og_locale']}">
<meta property="og:title" content="{E(titre)}">
<meta property="og:description" content="{E(desc)}">
<meta property="og:url" content="{url_base}/{chemin}">
<meta name="twitter:card" content="summary">
<link rel="icon" href="{r}assets/icon.svg" type="image/svg+xml">
<link rel="stylesheet" href="{r}assets/page.css?v=6">
{blocs}
</head>
<body>
<header class="page-bar">
  <a class="home" href="{r}{url_appli(lang)}">
    <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 17c3.5-8 7-11 11-11 3 0 5 1.6 6 4" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"/><path d="M7 21c3-7 6-9.5 9.5-9.5" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" opacity=".5"/></svg>
    {E(T[lang]['marque'])}</a>
  <a class="lang" href="{r}{alternatives[autre]}" hreflang="{autre}" lang="{autre}">{E(T[lang]['bascule'])}</a>
</header>
<main class="wrap">"""


def pied(lang, chemin, url_base, depot):
    r = rel(chemin)
    return f"""
</main>
<footer class="wrap src">
  <p><a href="{r}{url_appli(lang)}">{E(T[lang]['voir_carte'])}</a> ·
     <a href="{r}{url_index(lang)}">{E(T[lang]['annuaire'])}</a> ·
     <a href="https://github.com/{depot}">{E(T[lang]['code_source'])}</a></p>
</footer>
</body>
</html>
"""


def page_site(t, lang, voisins, url_base, depot, maj):
    chemin = url_site(lang, t["id"])
    r = rel(chemin)
    tr = T[lang]
    nom = nom_de(t, lang)
    ville = t.get("ville") or ""
    titre = tr["titre_site"](nom, ville, t["piste"])
    desc = description(t, lang)
    alternatives = {l: url_site(l, t["id"]) for l in T}
    url_absolue = f"{url_base}/{chemin}"

    # --- JSON-LD : c'est ce que lisent Google et les agents IA
    lieu = {
        "@context": "https://schema.org",
        "@type": "SportsActivityLocation",
        "@id": url_absolue + "#place",
        "name": nom,
        "url": url_absolue,
        "description": re.sub(r"<[^>]+>", "", resume(t, lang)),
        "sport": "Athletics",
        "identifier": t["id"],
        "geo": {"@type": "GeoCoordinates", "latitude": t["lat"], "longitude": t["lon"]},
        "address": {k: v for k, v in {
            "@type": "PostalAddress",
            "streetAddress": t.get("adresse"),
            "postalCode": t.get("cp"),
            "addressLocality": ville,
            "addressRegion": t.get("dep_nom"),
            "addressCountry": "FR",
        }.items() if v},
        "isAccessibleForFree": bool(t["acces_libre"]),
        "publicAccess": bool(t["acces_libre"] or t["ouvert_public"]),
        "inLanguage": lang,
    }
    equipements = [{"@type": "LocationFeatureSpecification",
                    "name": AGRES[lang].get(a, a), "value": True}
                   for a in tri_agres(t["agres"])]
    for actif, nom_eq in ((t["eclairage"], tr["kv"]["eclairage"]),
                          (t["vestiaires"], tr["kv"]["vestiaires"]),
                          (t["douches"], tr["kv"]["douches"]),
                          (t["sanitaires"], tr["kv"]["sanitaires"]),
                          (t["couvert"], tr["couverte"])):
        if actif:
            equipements.append({"@type": "LocationFeatureSpecification",
                                "name": nom_eq, "value": True})
    if equipements:
        lieu["amenityFeature"] = equipements
    proprietes = []
    if t.get("surface"):
        proprietes.append({"@type": "PropertyValue", "name": tr["kv"]["revetement"],
                           "value": SOL[lang].get(t["surface"], t["surface"])})
    if t.get("longueur_piste"):
        proprietes.append({"@type": "PropertyValue", "name": tr["kv"]["developpement"],
                           "value": f"{t['longueur_piste']} m"})
    if t.get("couloirs"):
        proprietes.append({"@type": "PropertyValue", "name": tr["kv"]["couloirs"],
                           "value": t["couloirs"]})
    if proprietes:
        lieu["additionalProperty"] = proprietes
    if t["photos"]:
        lieu["photo"] = [f"{url_base}/{p['f']}" for p in t["photos"]]
    if t.get("url"):
        lieu["sameAs"] = t["url"]
    if t.get("note_moyenne"):
        lieu["aggregateRating"] = {"@type": "AggregateRating",
                                   "ratingValue": t["note_moyenne"],
                                   "reviewCount": t["nb_avis"], "bestRating": 5}
    avis_ld = [{"@type": "Review",
                "reviewBody": a["t"],
                **({"datePublished": a["d"]} if a.get("d") else {}),
                "author": {"@type": "Person", "name": a.get("a") or tr["anonyme"]},
                **({"reviewRating": {"@type": "Rating", "ratingValue": a["n"],
                                     "bestRating": 5}} if a.get("n") else {})}
               for a in t["avis"]]
    if avis_ld:
        lieu["review"] = avis_ld

    fil = {
        "@context": "https://schema.org", "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": tr["accueil"],
             "item": f"{url_base}/{url_appli(lang)}"},
            {"@type": "ListItem", "position": 2, "name": t.get("dep_nom") or "France",
             "item": f"{url_base}/{url_dep(lang, t['dep'])}" if t.get("dep")
                     else f"{url_base}/{url_index(lang)}"},
            {"@type": "ListItem", "position": 3, "name": nom, "item": url_absolue},
        ],
    }

    # --- corps
    adresse = ", ".join(x for x in [t.get("adresse"),
                                    " ".join(x for x in [t.get("cp"), ville] if x)] if x)
    gmaps = f"https://www.google.com/maps/dir/?api=1&amp;destination={t['lat']},{t['lon']}"

    lignes = [entete(lang, titre, desc, chemin, alternatives, [lieu, fil], url_base)]
    lignes.append(f"""
<nav class="crumb"><a href="{r}{url_appli(lang)}">{E(tr['accueil'])}</a> ›
  <a href="{r}{url_dep(lang, t['dep'])}">{E(t.get('dep_nom') or t.get('dep') or '')}</a> ›
  {E(nom)}</nav>
<h1>{E(nom)}</h1>
<p class="loc">{E(adresse)}{f" · {E(t['dep_nom'])}" if t.get('dep_nom') else ''}</p>""")

    if t.get("note_moyenne"):
        lignes.append(f'<p class="rating">{etoiles(t["note_moyenne"], lang)} '
                      f'<span>{E(tr["sur_5"](fmt_note(t["note_moyenne"], lang), t["nb_avis"]))}</span></p>')

    lignes.append(f'<p class="lede">{resume(t, lang)}</p>')
    lignes.append(f"""<div class="actions">
  <a class="btn primary" href="{gmaps}" rel="nofollow noopener">{E(tr['itineraire'])}</a>
  <a class="btn" href="{r}{url_appli(lang)}#site={E(t['id'])}">{E(tr['ouvrir_appli'])}</a>
</div>""")

    if t["photos"]:
        def figure(p):
            fichier = p.get("t") or p["f"]
            taille = dimensions_jpeg(os.path.join(ROOT, fichier))
            dims = f' width="{taille[0]}" height="{taille[1]}"' if taille else ""
            legende = (f'<figcaption>{E(p["l"])}'
                       + (f' <span>© {E(p["c"])}</span>' if p.get("c") else "")
                       + "</figcaption>") if p.get("l") else ""
            # la vignette s'affiche, le lien mene a la photo pleine taille
            return (f'<figure><a href="{r}{E(p["f"])}">'
                    f'<img loading="lazy" src="{r}{E(fichier)}" '
                    f'alt="{E(p.get("l") or nom)}"{dims}></a>{legende}</figure>')
        figures = "".join(figure(p) for p in t["photos"])
        lignes.append(f'<h2>{E(tr["sec_photos"])}</h2><div class="gallery">{figures}</div>')
    else:
        # a defaut de photo de terrain, l'implantation vue du ciel
        aerienne = vue_aerienne(t)
        if aerienne:
            lignes.append(
                f'<h2>{E(tr["sec_aerienne"])}</h2>'
                f'<figure class="aerial">'
                f'<img loading="lazy" src="{E(aerienne)}" width="960" height="540" '
                f'alt="{E(tr["aerienne_alt"](nom))}">'
                f'<figcaption>{E(tr["aerienne_legende"])} '
                f'<span>{E(tr["aerienne_credit"])}</span></figcaption></figure>')

    def kv(cle, valeur):
        return (f'<div class="kv"><dt>{E(cle)}</dt><dd>{E(str(valeur))}</dd></div>'
                if valeur not in (None, "", False) else "")

    piste = "".join([
        kv(tr["kv"]["revetement"], SOL[lang].get(t.get("surface")) if t.get("surface") else None),
        kv(tr["kv"]["developpement"], f"{t['longueur_piste']} m" if t.get("longueur_piste") else None),
        kv(tr["kv"]["couloirs"], t.get("couloirs")),
        kv(tr["kv"]["config"], tr["couverte"] if t["couvert"] else (tr["plein_air"] if t["piste"] else None)),
        kv(tr["kv"]["service"], t.get("annee")),
        kv(tr["kv"]["renovation"], t.get("renovation")),
    ])
    if piste:
        lignes.append(f'<h2>{E(tr["sec_piste"])}</h2><dl class="grid">{piste}</dl>')

    if t["agres"] or t["agres_probables"]:
        items = "".join(f"<li>{E(AGRES[lang].get(a, a))}</li>" for a in tri_agres(t["agres"]))
        items += "".join(f'<li class="maybe">{E(AGRES[lang].get(a, a))}</li>'
                         for a in t["agres_probables"])
        lignes.append(f'<h2>{E(tr["sec_agres"])}</h2><ul class="eq">{items}</ul>')

    acces = "".join([
        kv(tr["kv"]["acces_libre"], tr["oui"] if t["acces_libre"]
           else (tr["ouvert_horaires"] if t["ouvert_public"] else tr["non_reserve"])),
        kv(tr["kv"]["eclairage"], tr["oui"] if t["eclairage"] else tr["non"]),
        kv(tr["kv"]["vestiaires"], tr["oui"] if t["vestiaires"] else tr["non"]),
        kv(tr["kv"]["douches"], tr["oui"] if t["douches"] else tr["non"]),
        kv(tr["kv"]["sanitaires"], tr["oui"] if t["sanitaires"] else tr["non"]),
        kv(tr["kv"]["tribunes"], tr["places"](t["tribunes"]) if t.get("tribunes") else None),
        kv(tr["kv"]["type_site"], tr["enceinte_scolaire"] if t["scolaire"] else None),
        kv(tr["kv"]["horaires"], t.get("horaires")),
    ])
    lignes.append(f'<h2>{E(tr["sec_acces"])}</h2><dl class="grid">{acces}</dl>')
    if t.get("acces_note"):
        lignes.append(f'<p>{E(t["acces_note"])}</p>')

    lignes.append(f'<h2>{E(tr["sec_avis"])}</h2>')
    if t["avis"]:
        for a in t["avis"]:
            note = etoiles(a["n"], lang) if a.get("n") else ""
            quand = (f'<time datetime="{E(a["d"])}">{E(fmt_date(a["d"], lang))}</time>'
                     if a.get("d") else "")
            lignes.append(f'<article class="avis"><header>{note}'
                          f'<strong>{E(a.get("a") or tr["anonyme"])}</strong>{quand}</header>'
                          f'<p>{E(a["t"])}</p></article>')
    else:
        lignes.append(f'<p>{E(tr["pas_davis"])}</p>')

    # Le champ libre 'note' porte les remarques qui ne rentrent dans aucune case :
    # une correction, une reserve sur la fiche du ministere, l'origine d'une donnee.
    # L'application l'affiche depuis toujours ; la page statique l'oubliait.
    if t.get("note"):
        lignes.append(f'<p class="note">{E(t["note"])}</p>')

    if voisins:
        items = "".join(
            f'<li><a href="{r}{url_site(lang, v["id"])}">{E(nom_de(v, lang))}'
            f'<span class="meta">{E(v.get("ville") or "")}'
            + (f' · {E(SOL[lang].get(v.get("surface"), ""))}' if v.get("surface") else "")
            + f'</span></a></li>'
            for v in voisins)
        lignes.append(f'<h2>{E(tr["sec_proches"])}</h2><ul class="liste">{items}</ul>')

    liens = []
    if t.get("url"):
        liens.append(f'<a href="{E(t["url"])}" rel="nofollow noopener">{E(tr["site_officiel"])}</a>')
    liens.append(f'<a href="https://github.com/{depot}/issues/new?template=correction.yml'
                 f'&amp;id={E(t["id"])}" rel="nofollow noopener">{E(tr["signaler"])}</a>')
    lignes.append('<p class="src">' + " · ".join(liens) + "</p>")
    lignes.append(f'<p class="src">Réf. {E(t["id"])} · '
                  + tr["source_note"](E(SOURCES[lang][t.get("source", 0)])) + "</p>")
    lignes.append(pied(lang, chemin, url_base, depot))
    return "".join(lignes)


def page_departement(code, nom_dep, region, sites, lang, url_base, depot):
    chemin = url_dep(lang, code)
    r = rel(chemin)
    tr = T[lang]
    titre = tr["dep_titre"].format(dep=nom_dep or code)
    desc = tr["dep_desc"].format(n=len(sites), dep=nom_dep or code, reg=region or "France")
    alternatives = {l: url_dep(l, code) for l in T}

    liste_ld = {
        "@context": "https://schema.org", "@type": "ItemList",
        "name": titre, "numberOfItems": len(sites),
        "itemListElement": [
            {"@type": "ListItem", "position": i + 1, "name": nom_de(s, lang),
             "url": f"{url_base}/{url_site(lang, s['id'])}"}
            for i, s in enumerate(sites)],
    }
    fil = {
        "@context": "https://schema.org", "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": tr["accueil"],
             "item": f"{url_base}/{url_appli(lang)}"},
            {"@type": "ListItem", "position": 2, "name": tr["index_titre"],
             "item": f"{url_base}/{url_index(lang)}"},
            {"@type": "ListItem", "position": 3, "name": nom_dep or code,
             "item": f"{url_base}/{chemin}"},
        ],
    }

    lignes = [entete(lang, titre, desc, chemin, alternatives, [liste_ld, fil], url_base)]
    lignes.append(f"""
<nav class="crumb"><a href="{r}{url_appli(lang)}">{E(tr['accueil'])}</a> ›
  <a href="{r}{url_index(lang)}">{E(tr['index_titre'])}</a> › {E(nom_dep or code)}</nav>
<h1>{E(titre)}</h1>
<p class="loc">{E(region or '')} · {E(tr['nb_sites'](len(sites)))}</p>
<div class="actions">
  <a class="btn primary" href="{r}{url_appli(lang)}#carte&amp;dep={E(code)}">{E(tr['voir_dep_carte'])}</a>
</div>""")

    ville_courante = None
    for s in sites:
        if s.get("ville") != ville_courante:
            if ville_courante is not None:
                lignes.append("</ul>")
            ville_courante = s.get("ville")
            lignes.append(f'<h2 class="ville">{E(ville_courante or "")}</h2><ul class="liste">')
        details = []
        if s.get("longueur_piste"):
            details.append(f"{s['longueur_piste']} m")
        if s.get("surface"):
            details.append(SOL[lang].get(s["surface"], s["surface"]))
        if s.get("couloirs"):
            details.append(f"{s['couloirs']} couloirs" if lang == "fr" else f"{s['couloirs']} lanes")
        details += [AGRES[lang][a] for a in tri_agres(s["agres"]) if a in AGRES[lang]]
        meta = f'<span class="meta">{E(" · ".join(details))}</span>' if details else ""
        lignes.append(f'<li><a href="{r}{url_site(lang, s["id"])}">'
                      f'{E(nom_de(s, lang))}{meta}</a></li>')
    if ville_courante is not None:
        lignes.append("</ul>")
    lignes.append(pied(lang, chemin, url_base, depot))
    return "".join(lignes)


def page_index(deps_tries, total, lang, url_base, depot):
    chemin = url_index(lang)
    r = rel(chemin)
    tr = T[lang]
    titre = tr["index_titre"]
    desc = tr["index_desc"].format(n=total)
    alternatives = {l: url_index(l) for l in T}
    fil = {
        "@context": "https://schema.org", "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": tr["accueil"],
             "item": f"{url_base}/{url_appli(lang)}"},
            {"@type": "ListItem", "position": 2, "name": titre, "item": f"{url_base}/{chemin}"},
        ],
    }
    lignes = [entete(lang, titre, desc, chemin, alternatives, [fil], url_base)]
    lignes.append(f"""
<nav class="crumb"><a href="{r}{url_appli(lang)}">{E(tr['accueil'])}</a> › {E(titre)}</nav>
<h1>{E(titre)}</h1>
<p class="lede">{E(tr['index_intro'])}</p>""")

    region_courante = None
    for code, nom_dep, region, nb in deps_tries:
        if region != region_courante:
            if region_courante is not None:
                lignes.append("</div>")
            region_courante = region
            lignes.append(f'<h2>{E(region or "France")}</h2><div class="cols">')
        lignes.append(f'<a href="{r}{url_dep(lang, code)}">{E(nom_dep or code)} '
                      f'<span class="meta">({nb})</span></a>')
    if region_courante is not None:
        lignes.append("</div>")
    lignes.append(pied(lang, chemin, url_base, depot))
    return "".join(lignes)


# ------------------------------------------------- coquilles de l'application
# L'application est ecrite en francais dans index.html ; les libelles visibles
# sont reposes a l'execution par assets/i18n.js. On traduit tout de meme la
# coquille anglaise ici, pour qu'un robot qui n'execute pas JavaScript lise de
# l'anglais. Cette table est courte : le dictionnaire complet reste i18n.js.
COQUILLE_EN = [
    ('<html lang="fr">', '<html lang="en">'),
    ("<title>Où s'entraîner ? — Pistes d'athlétisme en France</title>",
     "<title>Where to train? — Athletics tracks in France</title>"),
    ('content="Trouvez la piste d\'athlétisme la plus proche et découvrez ses équipements : '
     'sautoirs longueur, hauteur, perche, aires de lancer, revêtement synthétique ou cendrée."',
     'content="Find the nearest athletics track in France and what it offers: long, high and pole '
     'vault areas, throwing circles, synthetic or cinder surface."'),
    ('<link rel="canonical" href="{BASE}/">', '<link rel="canonical" href="{BASE}/en/">'),
    ('<meta property="og:locale" content="fr_FR">', '<meta property="og:locale" content="en_GB">'),
    ('<meta property="og:locale:alternate" content="en_GB">',
     '<meta property="og:locale:alternate" content="fr_FR">'),
    ('<meta property="og:site_name" content="Où s\'entraîner ?">',
     '<meta property="og:site_name" content="Where to train?">'),
    ('<meta property="og:title" content="Où s\'entraîner ? — Pistes d\'athlétisme en France">',
     '<meta property="og:title" content="Where to train? — Athletics tracks in France">'),
    ('<meta property="og:description" content="7 100 sites d\'athlétisme en France : revêtement, '
     'couloirs, sautoirs, aires de lancer, éclairage, accès libre.">',
     '<meta property="og:description" content="7,100 athletics venues across France: surface, '
     'lanes, jump and throwing areas, floodlighting, free access.">'),
    ('<meta property="og:url" content="{BASE}/">', '<meta property="og:url" content="{BASE}/en/">'),
    ('href="assets/', 'href="../assets/'),
    ('src="assets/', 'src="../assets/'),
    ('../assets/manifest.webmanifest', '../assets/manifest.en.webmanifest'),
    ('href="departements/"', 'href="departments/"'),
    ('href="en/"', 'href="../"'),
    ('hreflang="en" lang="en"', 'hreflang="fr" lang="fr"'),
    ('title="Read this site in English">EN</a>', 'title="Lire ce site en français">FR</a>'),
    ('aria-label="À propos" title="À propos"', 'aria-label="About" title="About"'),
    ('placeholder="Ville, code postal ou nom du stade" aria-label="Rechercher"',
     'placeholder="Town, postcode or stadium name" aria-label="Search"'),
    ('aria-label="Effacer"', 'aria-label="Clear"'),
    ('aria-label="Autour de moi"', 'aria-label="Near me"'),
    ('aria-label="Filtres"', 'aria-label="Filters"'),
    ('aria-label="Fermer"', 'aria-label="Close"'),
    ('aria-label="Plan du site"', 'aria-label="Site map"'),
    ('data-i18n="vide" hidden>Aucun site ne correspond à ces critères.',
     'data-i18n="vide" hidden>No venue matches these filters.'),
    ('<h1 data-i18n="marque">Où s\'entraîner&nbsp;?</h1>',
     '<h1 data-i18n="marque">Where to train?</h1>'),
    ('data-i18n="onglet_liste">Liste<', 'data-i18n="onglet_liste">List<'),
    ('data-i18n="onglet_carte">Carte<', 'data-i18n="onglet_carte">Map<'),
    ('data-i18n="plus" hidden>Afficher plus de sites<',
     'data-i18n="plus" hidden>Show more venues<'),
    ('data-i18n="chargement">Chargement des 7&nbsp;000 sites…<',
     'data-i18n="chargement">Loading 7,000 venues…<'),
    ('data-i18n="nav_annuaire">Annuaire par département<',
     'data-i18n="nav_annuaire">Browse by department<'),
    ('data-i18n="nav_source">Source des données<', 'data-i18n="nav_source">Data source<'),
    ('data-i18n="nav_code">Code source<', 'data-i18n="nav_code">Source code<'),
    ('data-i18n="changer_langue">Read this site in English<',
     'data-i18n="changer_langue">Lire ce site en français<'),
    ("""<p class="empty">Cette application a besoin de JavaScript pour la carte et les filtres.
        L'annuaire complet reste consultable en pages HTML&nbsp;:
        <a href="departments/">tous les sites d'athlétisme, département par département</a>.</p>""",
     """<p class="empty">This app needs JavaScript for the map and the filters.
        The full directory is also available as plain HTML pages:
        <a href="departments/">every athletics venue, department by department</a>.</p>"""),
]


def coquilles(html_fr, url_base):
    """Retourne (index.html francais, en/index.html anglais)."""
    fr = html_fr.replace(URL_DEFAUT, url_base)
    en = fr
    for avant, apres in COQUILLE_EN:
        avant = avant.replace("{BASE}", url_base)
        apres = apres.replace("{BASE}", url_base)
        if avant not in en:
            raise SystemExit(f"[ERREUR] index.html ne contient plus : {avant[:70]}…")
        en = en.replace(avant, apres)          # toutes les occurrences
    # l'ordre des alternatives hreflang reste correct : elles sont absolues
    return fr, en


# ------------------------------------------------------------------- fichiers
def ecrire(chemin, contenu):
    os.makedirs(os.path.dirname(chemin), exist_ok=True)
    with open(chemin, "w", encoding="utf-8") as f:
        f.write(contenu)


def sitemap(urls, url_base, maj):
    corps = "".join(
        f"  <url><loc>{url_base}/{u}</loc><lastmod>{maj}</lastmod>"
        f"<changefreq>monthly</changefreq><priority>{p}</priority></url>\n"
        for u, p in urls)
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            f"{corps}</urlset>\n")


def sitemap_index(fichiers, url_base, maj):
    corps = "".join(f"  <sitemap><loc>{url_base}/{f}</loc><lastmod>{maj}</lastmod></sitemap>\n"
                    for f in fichiers)
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            f"{corps}</sitemapindex>\n")


def robots(url_base):
    """Tout est ouvert, y compris aux robots d'IA : les donnees sont publiques
    et sous Licence Ouverte. On le dit explicitement plutot que de laisser
    chaque robot deviner."""
    agents = ["*", "Googlebot", "Bingbot", "DuckDuckBot", "Qwantify", "Applebot",
              "GPTBot", "OAI-SearchBot", "ChatGPT-User", "ClaudeBot", "Claude-User",
              "Claude-SearchBot", "anthropic-ai", "PerplexityBot", "Perplexity-User",
              "Google-Extended", "Amazonbot", "meta-externalagent", "CCBot",
              "Bytespider", "cohere-ai", "MistralAI-User", "YouBot"]
    blocs = "\n\n".join(f"User-agent: {a}\nAllow: /" for a in agents)
    return (f"# Où s'entraîner ? — annuaire ouvert des pistes d'athlétisme françaises.\n"
            f"# Données sous Licence Ouverte 2.0, réutilisation libre avec attribution.\n"
            f"# Description lisible par un agent : {url_base}/llms.txt\n"
            f"# Jeu de données complet : {url_base}/data/tracks.json\n\n"
            f"{blocs}\n\nSitemap: {url_base}/sitemap.xml\n")


def llms_txt(url_base, total, avec_piste, deps, maj, depot):
    """Convention llms.txt : une page d'orientation pour les agents."""
    fr_total, fr_piste = f"{total:,}".replace(",", " "), f"{avec_piste:,}".replace(",", " ")
    return f"""# Où s'entraîner ? / Where to train?

> Annuaire libre des {fr_total} installations d'athlétisme de France ({fr_piste} avec piste),
> avec leur revêtement, leurs agrès, leurs conditions d'accès et leurs coordonnées.
> Open directory of the {total:,} athletics venues in France ({avec_piste:,} with a running track),
> including surface, equipment, access conditions and coordinates.

Données issues du Recensement des équipements sportifs (Data ES) du ministère français chargé
des Sports, sous Licence Ouverte 2.0, enrichies par des contributions communautaires.
Data from the French sports ministry's facilities census (Data ES), Licence Ouverte 2.0,
enriched by community contributions. Dernière génération / last build: {maj}.

## Jeu de données / Dataset

- [tracks.json]({url_base}/data/tracks.json): l'intégralité du jeu de données en un seul fichier
  JSON (~1,5 Mo). Les clés sont abrégées ; l'objet `keymap` du fichier donne la correspondance
  vers les noms complets (`n` = nom, `v` = ville, `y`/`x` = latitude/longitude, `s` = revêtement,
  `g` = agrès, `lp` = longueur de piste, `cl` = couloirs, `al` = accès libre…). `deps` associe
  chaque code de département à son nom et à sa région. / Whole dataset in one JSON file; the
  `keymap` object maps the short keys to full field names.
- Licence : [Licence Ouverte 2.0](https://github.com/etalab/licence-ouverte/blob/master/LO.md) —
  réutilisation libre, y compris commerciale, avec mention de la source.

## Pages HTML (sans JavaScript) / Plain HTML pages

- [Application française]({url_base}/) — carte, filtres et recherche (nécessite JavaScript).
- [English app]({url_base}/en/) — same application in English.
- [Annuaire par département]({url_base}/departements/) — les {len(deps)} départements.
- [Directory by department]({url_base}/en/departments/) — English version.
- Une page par installation / one page per venue:
  `{url_base}/site/<ID>/` (fr) et `{url_base}/en/track/<ID>/` (en), où `<ID>` est
  l'identifiant national de l'installation (champ `i` du JSON, ex. `I441310030`).
- Une page par département / one page per department:
  `{url_base}/departement/<CODE>/` (fr) et `{url_base}/en/department/<CODE>/` (en),
  où `<CODE>` est le code INSEE du département (ex. `44`, `2A`, `971`).
- Chaque page site porte un balisage JSON-LD `SportsActivityLocation` avec adresse, coordonnées,
  agrès, accès et avis. / Every venue page embeds JSON-LD.

## À savoir / Caveats

- Les données sont **déclaratives** : saisies par les propriétaires des installations, elles
  peuvent être incomplètes ou périmées, en particulier les conditions d'accès.
  / Records are self-declared and may be outdated, especially access conditions.
- Certaines fiches indiquent « aire de saut » ou « aire de lancer » sans préciser la discipline :
  elles sont marquées comme probables (`gp` dans le JSON, mentions en pointillés sur le site).
  / Some records report a jump or throwing area without naming the discipline; those are flagged
  as uncertain.
- Corrections et ajouts : {url_base}/ ou https://github.com/{depot}
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(ROOT, "_site"))
    ap.add_argument("--url", help="URL publique du site (sinon SITE_URL, sinon GitHub Pages)")
    args = ap.parse_args()

    url_base = url_du_site(args.url)
    depot = os.environ.get("GITHUB_REPOSITORY") or "Chardonneaur/pistes-athle"
    out = os.path.abspath(args.out)
    brut, sites, deps = charger()
    maj = brut.get("generated") or date.today().isoformat()

    if os.path.isdir(out):
        shutil.rmtree(out)
    os.makedirs(out)

    # --- fichiers de l'application
    with open(os.path.join(ROOT, "index.html"), encoding="utf-8") as f:
        fr, en = coquilles(f.read(), url_base)
    ecrire(os.path.join(out, "index.html"), fr)
    ecrire(os.path.join(out, "en", "index.html"), en)
    for nom_fichier in ("sw.js", ".nojekyll"):
        shutil.copy2(os.path.join(ROOT, nom_fichier), os.path.join(out, nom_fichier))
    shutil.copytree(os.path.join(ROOT, "assets"), os.path.join(out, "assets"))
    os.makedirs(os.path.join(out, "data"))
    shutil.copy2(TRACKS, os.path.join(out, "data", "tracks.json"))
    photos = os.path.join(ROOT, "data", "photos")
    if os.path.isdir(photos):
        shutil.copytree(photos, os.path.join(out, "data", "photos"))

    # --- regroupement par departement
    sur = re.compile(r"[^A-Za-z0-9._-]")
    par_dep = {}
    publiables = []
    for t in sites:
        if not t.get("id") or sur.search(t["id"]):
            print(f"[!] identifiant inutilisable dans une URL, site ignore : {t.get('id')!r}")
            continue
        if t.get("lat") is None or t.get("lon") is None:
            continue
        if not t.get("dep"):
            t["dep"] = "00"
            t["dep_nom"] = t["dep_nom"] or "Département non renseigné"
        par_dep.setdefault(t["dep"], []).append(t)
        publiables.append(t)

    for liste in par_dep.values():
        liste.sort(key=lambda s: ((s.get("ville") or "").lower(), (s.get("nom") or "").lower()))

    # voisins : les six installations les plus proches du meme departement
    voisins = {}
    for code, liste in par_dep.items():
        for t in liste:
            autres = sorted((s for s in liste if s["id"] != t["id"]),
                            key=lambda s: distance(t["lat"], t["lon"], s["lat"], s["lon"]))
            voisins[t["id"]] = autres[:6]

    deps_tries = sorted(
        ((code, (liste[0].get("dep_nom") or code), (liste[0].get("region") or ""), len(liste))
         for code, liste in par_dep.items()),
        key=lambda d: (d[2], d[1]))

    # --- generation
    urls = {"fr": [], "en": []}
    for lang in T:
        urls[lang].append((url_appli(lang), "1.0"))
        urls[lang].append((url_index(lang), "0.8"))
        ecrire(os.path.join(out, url_index(lang), "index.html"),
               page_index(deps_tries, len(publiables), lang, url_base, depot))
        for code, liste in par_dep.items():
            nom_dep = liste[0].get("dep_nom") or code
            region = liste[0].get("region") or ""
            ecrire(os.path.join(out, url_dep(lang, code), "index.html"),
                   page_departement(code, nom_dep, region, liste, lang, url_base, depot))
            urls[lang].append((url_dep(lang, code), "0.7"))
        for t in publiables:
            ecrire(os.path.join(out, url_site(lang, t["id"]), "index.html"),
                   page_site(t, lang, voisins.get(t["id"], []), url_base, depot, maj))
            urls[lang].append((url_site(lang, t["id"]), "0.6"))

    # --- plan du site, robots, llms
    for lang in T:
        ecrire(os.path.join(out, f"sitemap-{lang}.xml"), sitemap(urls[lang], url_base, maj))
    ecrire(os.path.join(out, "sitemap.xml"),
           sitemap_index([f"sitemap-{l}.xml" for l in T], url_base, maj))
    ecrire(os.path.join(out, "robots.txt"), robots(url_base))
    avec_piste = sum(1 for t in publiables if t["piste"])
    ecrire(os.path.join(out, "llms.txt"),
           llms_txt(url_base, len(publiables), avec_piste, par_dep, maj, depot))

    pages = sum(len(u) for u in urls.values())
    print(f"-> {out}")
    print(f"   {len(publiables)} sites x 2 langues, {len(par_dep)} departements, "
          f"{pages} URL au plan du site")
    print(f"   URL publique : {url_base}")


if __name__ == "__main__":
    main()
