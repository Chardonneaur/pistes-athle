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
from urllib.parse import quote_plus, urlsplit
import re
import shutil
from datetime import date

import build_api
from build_api import DISCIPLINES, MATOMO_HEAD, SURFACE_EN, slug

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TRACKS = os.path.join(ROOT, "data", "tracks.json")

# URL ecrite en dur dans index.html ; remplacee partout si --url differe.
URL_DEFAUT = "https://pistes-athle.com"
# Le depot d'origine publie sur son domaine ; un fork n'a que son github.io.
DEPOT_ORIGINE = "chardonneaur/pistes-athle"


def url_du_site(explicite=None):
    if explicite:
        return explicite.rstrip("/")
    if os.environ.get("SITE_URL"):
        return os.environ["SITE_URL"].rstrip("/")
    depot = os.environ.get("GITHUB_REPOSITORY")           # « proprietaire/depot »
    # L'inference ne vaut que pour un fork. Sur le depot d'origine, elle
    # rendrait l'URL github.io et ecraserait le domaine : GITHUB_REPOSITORY est
    # toujours defini dans Actions, donc URL_DEFAUT n'y serait jamais lu.
    if depot and "/" in depot and depot.lower() != DEPOT_ORIGINE:
        proprio, nom = depot.split("/", 1)
        if nom.lower() == f"{proprio.lower()}.github.io":
            return f"https://{proprio.lower()}.github.io"
        return f"https://{proprio.lower()}.github.io/{nom}"
    return URL_DEFAUT


def domaine_personnalise(url_base):
    """Le domaine a declarer a GitHub Pages, ou None s'il n'y en a pas.

    GitHub relit le fichier CNAME publie a chaque deploiement : sans lui, un
    deploiement efface le domaine configure a la main dans les reglages. Un
    fork publie sur github.io n'en veut pas — il revendiquerait un domaine
    qui ne lui appartient pas, et GitHub refuserait le deploiement."""
    hote = urlsplit(url_base).netloc
    return None if not hote or hote.endswith("github.io") else hote


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
        "seg_index": "departements", "seg_contrib": "contributeurs",
        "seg_pistes": "pistes", "seg_ville": "ville",
        "seg_prive": "confidentialite",
        "marque": "Où s'entraîner ?",
        "bascule": "English", "bascule_code": "EN",
        "accueil": "Accueil",
        "index_titre": "Pistes d'athlétisme par département",
        "index_desc": "Les {n} sites d'athlétisme recensés en France, département par département : "
                      "piste, revêtement, sautoirs, aires de lancer, accès.",
        "index_intro": "Chaque département renvoie vers la liste de ses installations d'athlétisme, "
                       "puis vers la fiche détaillée de chacune.",
        "index_criteres": "Par critère",
        "index_criteres_intro": "Les mêmes installations, prises par ce qu'on y cherche : "
                                "développement de l'anneau, couloirs, revêtement, agrès, accès.",
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
        "aerienne_legende_datee": lambda a: f"Vue aérienne de {a}, à défaut de photo du site.",
        "lp_estime": "estimé d'après OpenStreetMap, non mesuré sur place",
        "aerienne_credit": "Elle montre l'implantation, pas l'état des agrès : une bâche "
                           "signale bien un sautoir, mais pas s'il est praticable, et un "
                           "tapis rentré ne laisse rien voir. "
                           "© IGN — BD ORTHO®, Licence Ouverte 2.0",
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
        "horaires_google": "Horaires sur Google Maps",
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
        "contrib_titre": "Les contributeurs",
        "contrib_desc": "Qui a photographié, noté et corrigé les pistes d'athlétisme "
                        "françaises, et ce que chacun a apporté.",
        "contrib_intro": "Les données du ministère disent qu'un stade existe. Elles ne "
                         "disent pas si le sautoir tient encore debout. Tout ce qui suit "
                         "vient de gens qui sont allés voir.",
        "contrib_classement": "Classement",
        "contrib_toutes": "Toutes les contributions",
        "contrib_sites": lambda n: f"{n} site{'s' if n > 1 else ''}",
        "contrib_photos": lambda n: f"{n} photo{'s' if n > 1 else ''}",
        "contrib_avis": lambda n: f"{n} avis",
        "contrib_le": lambda d: f"le {d}",
        "contrib_par": lambda a: f"par {a}",
        "contrib_vide": "Aucune contribution pour l'instant. La première est à écrire.",
        "photo_titre_sans": "Cette piste n'a pas encore de photo",
        "photo_sans": "La vue aérienne montre l'implantation et se tait sur l'état. Une photo, "
                      "elle, tranche : synthétique ou cendrée, tapis en place ou retiré, couloirs "
                      "tracés ou effacés, portail ouvert ou fermé. Le recensement du ministère ne "
                      "dira jamais rien de tout ça. Si vous vous entraînez ici, vous avez déjà la "
                      "réponse dans votre téléphone.",
        "photo_titre_avec": "Il manque sûrement une photo",
        "photo_avec": "Les sautoirs et les aires de lancer sont ce que la donnée publique décrit "
                      "le plus mal, et ce qu'on photographie le moins. Un gros plan du sol, une "
                      "perche bâchée, un bac de sable envahi : chacun ajoute ce qu'aucun champ ne "
                      "porte.",
        "photo_bouton": "Envoyer une photo",
        "photo_sans_compte": "Sans compte GitHub",
        "contrib_appel": "Vous vous entraînez quelque part ?",
        "contrib_appel_texte": "Une photo du sautoir, une note sur l'état de la piste, un "
                               "horaire : c'est ce que les données publiques n'auront jamais.",
        "contrib_appel_lien": "Comment contribuer",
        "code_source": "Code source",
        "prive_titre": "Confidentialité",
        "prive_desc": "Ce que ce site mesure, ce qu'il ne mesure pas, et pourquoi il n'y a aucun bandeau à cliquer : mesure d'audience sans cookie, journal des robots, contributions.",
        "prive_lede": "Aucun cookie, aucune publicité, aucun profil. La seule mesure faite ici est anonyme, et elle sert à répondre à une question : les agents IA lisent-ils cet annuaire, et y envoient-ils des gens ? Voici, précisément, ce qui est enregistré — et ce qui ne l'est pas.",
        "prive_maj": lambda d: f"Cette page décrit le code publié le {d}. Elle change le jour où il change.",
        "crit_partout": "Où trouver ces installations",
        "crit_dep_lien": lambda n: f"{n} site{'s' if n > 1 else ''}",
        "crit_api": "Cette liste en JSON",
        "crit_api_texte": "La même sélection, servie à une machine : mêmes sites, mêmes "
                          "champs, avec la licence et la date de génération.",
        "ville_titre": lambda v: f"Pistes d'athlétisme à {v}",
        "ville_desc": lambda v, n: (f"Les {n} installations d'athlétisme recensées à {v} : "
                                    f"piste, revêtement, agrès, accès."
                                    if n > 1 else
                                    f"L'installation d'athlétisme recensée à {v} : "
                                    f"piste, revêtement, agrès, accès."),
        "ville_autour": "À moins de 20 km",
        "ville_autour_vide": "Aucune autre installation recensée dans un rayon de 20 km.",
        "crit_vide": "Aucune installation ne correspond.",
        "a_km": lambda d: f"à {d} km",
    },
    "en": {
        "html_lang": "en", "og_locale": "en_GB", "autre": "fr",
        "prefixe": "en/", "seg_site": "track", "seg_dep": "department",
        "seg_index": "departments", "seg_contrib": "contributors",
        "seg_pistes": "tracks", "seg_ville": "city",
        "seg_prive": "privacy",
        "marque": "Where to train?",
        "bascule": "Français", "bascule_code": "FR",
        "accueil": "Home",
        "index_titre": "Athletics tracks in France by department",
        "index_desc": "All {n} athletics venues recorded in France, department by department: "
                      "track, surface, jump and throwing areas, access.",
        "index_intro": "Each department links to the list of its athletics facilities, "
                       "and from there to the full record of each venue.",
        "index_criteres": "By criterion",
        "index_criteres_intro": "The same venues, taken by what people look for: lap length, "
                                "lanes, surface, equipment, access.",
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
        "aerienne_legende_datee": lambda a: f"{a} aerial view, in the absence of a photo of the venue.",
        "lp_estime": "estimated from OpenStreetMap, not measured on site",
        "aerienne_credit": "It shows the layout, not the state of the equipment: a cover "
                           "marks a landing mat without saying whether it is usable, and a "
                           "mat put away leaves nothing to see. "
                           "© IGN — BD ORTHO®, Licence Ouverte 2.0",
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
        "horaires_google": "Opening hours on Google Maps",
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
        "contrib_titre": "Contributors",
        "contrib_desc": "Who photographed, rated and corrected France's athletics tracks, "
                        "and what each of them added.",
        "contrib_intro": "Ministry records say a stadium exists. They do not say whether the "
                         "pole vault pit is still standing. Everything below comes from "
                         "people who went and looked.",
        "contrib_classement": "Ranking",
        "contrib_toutes": "All contributions",
        "contrib_sites": lambda n: f"{n} venue{'s' if n > 1 else ''}",
        "contrib_photos": lambda n: f"{n} photo{'s' if n > 1 else ''}",
        "contrib_avis": lambda n: f"{n} review{'s' if n > 1 else ''}",
        "contrib_le": lambda d: f"on {d}",
        "contrib_par": lambda a: f"by {a}",
        "contrib_vide": "No contributions yet. The first one is waiting to be written.",
        "photo_titre_sans": "This track has no photo yet",
        "photo_sans": "The aerial view shows the layout and says nothing about the state of it. A "
                      "photo settles the matter: synthetic or cinder, mat in place or taken away, "
                      "lanes marked or worn off, gate open or shut. The ministry's census will "
                      "never tell you any of that. If you train here, the answer is already in "
                      "your phone.",
        "photo_titre_avec": "A photo is surely still missing",
        "photo_avec": "Jump pits and throwing areas are what public data describes worst, and what "
                      "gets photographed least. A close-up of the ground, a covered vault pit, a "
                      "sand box gone to weeds: each adds what no field carries.",
        "photo_bouton": "Send a photo",
        "photo_sans_compte": "No GitHub account?",
        "contrib_appel": "Do you train somewhere?",
        "contrib_appel_texte": "A photo of the pole vault pit, a note on the state of the "
                               "track, an opening time: that is what open data will never hold.",
        "contrib_appel_lien": "How to contribute",
        "code_source": "Source code",
        "prive_titre": "Privacy",
        "prive_desc": "What this site measures, what it does not, and why there is no cookie banner to click: cookieless analytics, a crawler log, and what contributing publishes.",
        "prive_lede": "No cookie, no advertising, no profile. The only measurement here is anonymous, and it exists to answer one question: do AI agents read this directory, and do they send people to it? Here is exactly what is recorded — and what is not.",
        "prive_maj": lambda d: f"This page describes the code published on {d}. It changes the day that code changes.",
        "crit_partout": "Where to find them",
        "crit_dep_lien": lambda n: f"{n} venue{'s' if n > 1 else ''}",
        "crit_api": "This list as JSON",
        "crit_api_texte": "The same selection, served to a machine: same venues, same "
                          "fields, with the licence and build date.",
        "ville_titre": lambda v: f"Athletics tracks in {v}, France",
        "ville_desc": lambda v, n: (f"The {n} athletics venues recorded in {v}, France: "
                                    f"track, surface, equipment, access."
                                    if n > 1 else
                                    f"The athletics venue recorded in {v}, France: "
                                    f"track, surface, equipment, access."),
        "ville_autour": "Within 20 km",
        "ville_autour_vide": "No other venue recorded within 20 km.",
        "crit_vide": "No venue matches.",
        "a_km": lambda d: f"{d} km away",
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


def url_contrib(lang):
    return f"{T[lang]['prefixe']}{T[lang]['seg_contrib']}/"


def url_prive(lang):
    return f"{T[lang]['prefixe']}{T[lang]['seg_prive']}/"


def url_critere(lang, cle, dep_slug=None):
    base = f"{T[lang]['prefixe']}{T[lang]['seg_pistes']}/{cle}/"
    return f"{base}{dep_slug}/" if dep_slug else base


def url_ville(lang, ville_slug):
    return f"{T[lang]['prefixe']}{T[lang]['seg_ville']}/{ville_slug}/"


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
        t["longueur_probable"] = t.get("longueur_probable") or None
        t["avis"] = t.get("avis") or []
        t["nb_avis"] = t.get("nb_avis") or 0
        d = deps.get(t.get("dep") or "", ["", ""])
        t["dep_nom"], t["region"] = d[0], d[1]
        # 3e element eventuel : annee de l'orthophoto IGN du departement
        t["ortho_annee"] = d[2] if len(d) > 2 else None
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
        tour, sur = tour_de_piste(t)
        # une estimation OSM ne part pas dans la description : c'est la phrase
        # qu'un moteur de recherche affiche et qu'un agent recopie comme un
        # fait. Elle reste sur la fiche, suivie de sa mention d'incertitude.
        longueur = f"{tour} m" if tour and sur else ""
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
        tour, sur = tour_de_piste(t)
        if tour:
            bout.append(f"{tour} m" if sur else f"{tour} m ?")
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
    lg = tour_de_piste(t)[0] or 0
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


# Code de `source` d'un site cree par la communaute (build_data.SOURCE_CODES) :
# le ministere ne le connait pas du tout.
SOURCE_COMMUNAUTE = 2


def tour_de_piste(t):
    """Developpement de l'anneau, et s'il est declare ou seulement estime.

    Le ministere ne renseigne le developpement que d'une minorite de sites.
    Quand OpenStreetMap permet de l'estimer, on l'affiche — en disant que c'est
    une estimation, jamais en le faisant passer pour une mesure."""
    if t.get("longueur_piste"):
        return t["longueur_piste"], True
    if t.get("longueur_probable"):
        return t["longueur_probable"], False
    return None, True


def developpement_affiche(t, lang):
    tour, sur = tour_de_piste(t)
    if not tour:
        return None
    return f"{tour} m" if sur else f"{tour} m — {T[lang]['lp_estime']}"


def alt_photo(p, t, lang):
    """Texte alternatif d'une photo : la legende, puis le stade et la commune.

    Une legende seule (« La cage de lancer du disque et du marteau ») decrit
    bien l'objet mais ne le situe nulle part. Un lecteur d'ecran comme un
    moteur d'images ont besoin des deux, et c'est la meme phrase qui les sert."""
    lieu_dit = ", ".join(x for x in (nom_de(t, lang), t.get("ville")) if x)
    legende = (p.get("l") or "").strip().rstrip(".")
    return f"{legende} — {lieu_dit}" if legende and lieu_dit else (legende or lieu_dit)


def image_ld(p, t, lang, url_base):
    """Une photo en schema.org ImageObject, licence comprise.

    Les photos sont publiees sous ODbL avec le credit de leur auteur :
    `license` et `creditText` disent a un reutilisateur — humain ou agent — ce
    qu'il a le droit d'en faire, ce qu'une simple URL ne dit pas."""
    obj = {
        "@type": "ImageObject",
        "contentUrl": f"{url_base}/{p['f']}",
        "url": f"{url_base}/{p['f']}",
        "caption": alt_photo(p, t, lang),
        "license": "https://opendatacommons.org/licenses/odbl/1-0/",
        "acquireLicensePage": f"{url_base}/{url_site(lang, t['id'])}",
        "isPartOf": {"@type": "WebPage", "@id": f"{url_base}/{url_site(lang, t['id'])}"},
    }
    if p.get("t"):
        obj["thumbnailUrl"] = f"{url_base}/{p['t']}"
    if p.get("c"):
        obj["creditText"] = p["c"]
        obj["copyrightNotice"] = p["c"]
        obj["author"] = {"@type": "Person", "name": p["c"]}
    taille = dimensions_jpeg(os.path.join(ROOT, p["f"]))
    if taille:
        obj["width"], obj["height"] = taille
    if t.get("lat") is not None and t.get("lon") is not None:
        obj["contentLocation"] = {
            "@type": "Place",
            "name": ", ".join(x for x in (nom_de(t, lang), t.get("ville")) if x),
            "geo": {"@type": "GeoCoordinates",
                    "latitude": t["lat"], "longitude": t["lon"]},
        }
    return obj


# ------------------------------------------------------------------- gabarits
def entete(lang, titre, desc, chemin, alternatives, jsonld, url_base,
           image=None, preconnect=()):
    """<head> commun : canonique, alternatives de langue, Open Graph, JSON-LD.

    `image` est la photo de couverture de la page, si elle en a une : une URL
    absolue, sa description et ses dimensions. Sans elle, un partage de la
    fiche ne montre rien, et l'image n'a aucune chance d'etre reprise en
    vignette par un moteur ou un agent ; on retombe alors sur la vignette de
    marque, qui vaut toujours mieux qu'un rectangle vide.

    `preconnect` liste les origines dont la page tire une image : ouvrir la
    connexion des la lecture du <head> evite d'attendre DNS et TLS au moment
    ou l'image, le plus gros element affiche, est enfin demandee."""
    r = rel(chemin)
    autre = T[lang]["autre"]
    blocs = "\n".join(
        f'<script type="application/ld+json">{json.dumps(j, ensure_ascii=False).replace("</", "<\\/")}</script>'
        for j in jsonld)
    if not image:
        image = {"url": f"{url_base}/assets/og.png", "alt": T[lang]["marque"],
                 "w": 1200, "h": 630}
    og_image = (f'<meta property="og:image" content="{E(image["url"])}">\n'
                f'<meta property="og:image:alt" content="{E(image["alt"])}">\n')
    if image.get("w") and image.get("h"):
        og_image += (f'<meta property="og:image:width" content="{image["w"]}">\n'
                     f'<meta property="og:image:height" content="{image["h"]}">\n')
    # sans crossorigin : une image et une feuille de style sont demandees
    # hors CORS, et une connexion CORS preouverte ne leur servirait pas.
    liens = "".join(f'<link rel="preconnect" href="{o}">\n' for o in preconnect)
    mesure = MATOMO_HEAD.format(r=r)
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
<meta property="og:site_name" content="{E(T[lang]['marque'])}">
<meta property="og:locale" content="{T[lang]['og_locale']}">
<meta property="og:locale:alternate" content="{T[autre]['og_locale']}">
<meta property="og:title" content="{E(titre)}">
<meta property="og:description" content="{E(desc)}">
<meta property="og:url" content="{url_base}/{chemin}">
{og_image}<meta name="twitter:card" content="summary_large_image">
<link rel="icon" href="{r}assets/icon.svg" type="image/svg+xml">
{liens}<link rel="stylesheet" href="{r}assets/page.css?v=13">
{mesure}
<link rel="service-desc" type="application/json" href="{url_base}/openapi.json">
<link rel="alternate" type="application/json" href="{url_base}/api/index.json" title="Index des installations (JSON)">
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
     <a href="{r}{url_prive(lang)}">{E(T[lang]['prive_titre'])}</a> ·
     <a href="https://github.com/{depot}">{E(T[lang]['code_source'])}</a></p>
</footer>
</body>
</html>
"""


def page_site(t, lang, voisins, url_base, depot, maj, ville_slug=None):
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
        # meme regle que la fiche : un site communautaire dont l'acces n'est pas
        # renseigne ne declare pas un acces ferme, il ne declare rien.
        **({"isAccessibleForFree": bool(t["acces_libre"]),
            "publicAccess": bool(t["acces_libre"] or t["ouvert_public"])}
           if t.get("source") != SOURCE_COMMUNAUTE or t["acces_libre"] or t["ouvert_public"]
           else {}),
        "inLanguage": lang,
        # la date de mise a jour decrit la page, pas le stade : schema.org ne
        # definit dateModified que sur une oeuvre, d'ou ce noeud WebPage.
        "mainEntityOfPage": {"@type": "WebPage", "@id": url_absolue,
                             "dateModified": maj, "inLanguage": lang},
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
        # seul le declare part en donnee structuree : une estimation OSM n'a
        # rien a faire dans ce qu'un agent recopiera comme un fait.
        proprietes.append({"@type": "PropertyValue", "name": tr["kv"]["developpement"],
                           "value": f"{t['longueur_piste']} m"})
    if t.get("couloirs"):
        proprietes.append({"@type": "PropertyValue", "name": tr["kv"]["couloirs"],
                           "value": t["couloirs"]})
    if proprietes:
        lieu["additionalProperty"] = proprietes
    photos_ld = [image_ld(p, t, lang, url_base) for p in t["photos"]]
    if photos_ld:
        # des ImageObject plutot que des URL nues : une URL seule ne dit ni ce
        # que montre la photo, ni qui l'a prise, ni sous quelle licence on peut
        # la reutiliser. Google Images et les agents lisent ces trois choses.
        lieu["photo"] = photos_ld
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

    # Le fil d'Ariane est aussi un chemin d'exploration. Sans son maillon
    # commune, les pages de ville ne sont atteignables que par le plan du site :
    # rien n'y mene depuis l'accueil, et une page orpheline est exploree tard,
    # re-exploree rarement, et ne recoit aucune autorite interne.
    etapes = [(tr["accueil"], f"{url_base}/{url_appli(lang)}"),
              (t.get("dep_nom") or "France",
               f"{url_base}/{url_dep(lang, t['dep'])}" if t.get("dep")
               else f"{url_base}/{url_index(lang)}")]
    if ville_slug and ville:
        etapes.append((ville, f"{url_base}/{url_ville(lang, ville_slug)}"))
    etapes.append((nom, url_absolue))
    fil = {
        "@context": "https://schema.org", "@type": "BreadcrumbList",
        "itemListElement": [{"@type": "ListItem", "position": i + 1, "name": n, "item": u}
                            for i, (n, u) in enumerate(etapes)],
    }

    # --- corps
    adresse = ", ".join(x for x in [t.get("adresse"),
                                    " ".join(x for x in [t.get("cp"), ville] if x)] if x)
    gmaps = f"https://www.google.com/maps/dir/?api=1&amp;destination={t['lat']},{t['lon']}"
    # Les horaires ne figurent dans aucune donnee ouverte : le recensement du
    # ministere n'a pas le champ et OpenStreetMap n'en renseigne aucune piste.
    # On renvoie vers la fiche Google du site plutot que d'en recopier le
    # contenu, ce que ses conditions interdisent de stocker et redistribuer.
    requete = quote_plus(" ".join(x for x in (nom, t.get("ville"), t.get("cp")) if x))
    gplace = f"https://www.google.com/maps/search/?api=1&amp;query={requete}"

    couverture = None
    origines = []
    if t["photos"]:
        p0 = t["photos"][0]
        taille = dimensions_jpeg(os.path.join(ROOT, p0["f"])) or (None, None)
        couverture = {"url": f"{url_base}/{p0['f']}", "alt": alt_photo(p0, t, lang),
                      "w": taille[0], "h": taille[1]}
    else:
        # sans photo de terrain, l'orthophoto reste une vue du lieu : elle vaut
        # mieux que la vignette de marque, identique sur les 7 000 fiches.
        aerienne = vue_aerienne(t)
        if aerienne:
            couverture = {"url": aerienne, "alt": tr["aerienne_alt"](nom),
                          "w": 960, "h": 540}
            origines = [IGN_WMS.split("/wms")[0]]
    if couverture:
        lieu["image"] = couverture["url"]
    lignes = [entete(lang, titre, desc, chemin, alternatives, [lieu, fil], url_base,
                     image=couverture, preconnect=origines)]
    maillon_ville = (f'<a href="{r}{url_ville(lang, ville_slug)}">{E(ville)}</a> ›\n  '
                     if ville_slug and ville else "")
    lignes.append(f"""
<nav class="crumb"><a href="{r}{url_appli(lang)}">{E(tr['accueil'])}</a> ›
  <a href="{r}{url_dep(lang, t['dep'])}">{E(t.get('dep_nom') or t.get('dep') or '')}</a> ›
  {maillon_ville}{E(nom)}</nav>
<h1>{E(nom)}</h1>
<p class="loc">{E(adresse)}{f" · {E(t['dep_nom'])}" if t.get('dep_nom') else ''}</p>""")

    if t.get("note_moyenne"):
        lignes.append(f'<p class="rating">{etoiles(t["note_moyenne"], lang)} '
                      f'<span>{E(tr["sur_5"](fmt_note(t["note_moyenne"], lang), t["nb_avis"]))}</span></p>')

    lignes.append(f'<p class="lede">{resume(t, lang)}</p>')
    lignes.append(f"""<div class="actions">
  <a class="btn primary" href="{gmaps}" rel="nofollow noopener">{E(tr['itineraire'])}</a>
  <a class="btn" href="{gplace}" rel="nofollow noopener">{E(tr['horaires_google'])}</a>
  <a class="btn" href="{r}{url_appli(lang)}#site={E(t['id'])}">{E(tr['ouvrir_appli'])}</a>
</div>""")

    if t["photos"]:
        def figure(p, premiere):
            fichier = p.get("t") or p["f"]
            taille = dimensions_jpeg(os.path.join(ROOT, fichier))
            dims = f' width="{taille[0]}" height="{taille[1]}"' if taille else ""
            legende = (f'<figcaption>{E(p["l"])}'
                       + (f' <span>© {E(p["c"])}</span>' if p.get("c") else "")
                       + "</figcaption>") if p.get("l") else ""
            # la premiere image est le plus gros element affiche d'emblee : la
            # differer degrade le rendu percu et le classement qui en depend.
            charge = ('loading="eager" fetchpriority="high"' if premiere
                      else 'loading="lazy"')
            # la vignette s'affiche, le lien mene a la photo pleine taille
            return (f'<figure><a href="{r}{E(p["f"])}">'
                    f'<img {charge} src="{r}{E(fichier)}" '
                    f'alt="{E(alt_photo(p, t, lang))}"{dims}></a>{legende}</figure>')
        figures = "".join(figure(p, i == 0) for i, p in enumerate(t["photos"]))
        lignes.append(f'<h2>{E(tr["sec_photos"])}</h2><div class="gallery">{figures}</div>')
    else:
        # a defaut de photo de terrain, l'implantation vue du ciel (calculee
        # plus haut : c'est aussi la vignette de partage de la fiche)
        if aerienne:
            annee = t.get("ortho_annee")
            legende = (tr["aerienne_legende_datee"](annee) if annee
                       else tr["aerienne_legende"])
            lignes.append(
                f'<h2>{E(tr["sec_aerienne"])}</h2>'
                f'<figure class="aerial">'
                f'<img loading="eager" fetchpriority="high" src="{E(aerienne)}" '
                f'width="960" height="540" '
                f'alt="{E(tr["aerienne_alt"](nom))}">'
                f'<figcaption>{E(legende)} '
                f'<span>{E(tr["aerienne_credit"])}</span></figcaption></figure>')

    # L'appel a photographier, pose juste sous l'image — ou sous son absence.
    # C'est le seul instant ou le lecteur regarde CE stade-la : plus loin dans
    # la page, l'appel redevient une banniere qu'on ne lit pas. Le lien porte
    # l'identifiant, donc la contribution arrive deja rattachee a la fiche ;
    # sans lui, il faudrait demander « c'etait quel stade, deja ? ».
    avec = bool(t["photos"])
    # « 00 » est le code de repli des fiches sans departement : l'ecrire dans
    # l'intitule enverrait un numero qui ne designe rien.
    dep = t.get("dep") if t.get("dep") not in (None, "", "00") else None
    quoi = ", ".join(x for x in (nom, t.get("ville")) if x) + (f" ({dep})" if dep else "")
    lignes.append(
        f'<div class="appel">'
        f'<strong>{E(tr["photo_titre_avec"] if avec else tr["photo_titre_sans"])}</strong>'
        f'<p>{E(tr["photo_avec"] if avec else tr["photo_sans"])}</p>'
        f'<span class="boutons">'
        f'<a class="btn primary" rel="nofollow noopener" '
        f'href="https://github.com/{depot}/issues/new?template=photo.yml'
        f'&amp;id={E(t["id"])}&amp;nom={quote_plus(quoi)}">{E(tr["photo_bouton"])}</a>'
        f'<a class="btn" href="{r}{url_appli(lang)}#site={E(t["id"])}&amp;contribuer=photo">'
        f'{E(tr["photo_sans_compte"])}</a>'
        f'</span></div>')

    def kv(cle, valeur):
        return (f'<div class="kv"><dt>{E(cle)}</dt><dd>{E(str(valeur))}</dd></div>'
                if valeur not in (None, "", False) else "")

    piste = "".join([
        kv(tr["kv"]["revetement"], SOL[lang].get(t.get("surface")) if t.get("surface") else None),
        kv(tr["kv"]["developpement"], developpement_affiche(t, lang)),
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

    # Un site que le ministere ne connait pas n'a pas de cases a cocher : ses
    # booleens valent faux par defaut de saisie, pas par declaration. Ecrire
    # « Non » ferait passer un blanc pour un constat — on se tait a la place,
    # et la ligne reapparait des qu'un contributeur remplit le champ.
    declare = t.get("source") != SOURCE_COMMUNAUTE

    def oui_ou_non(actif, non=None):
        return tr["oui"] if actif else ((non or tr["non"]) if declare else None)

    acces = "".join([
        kv(tr["kv"]["acces_libre"], tr["oui"] if t["acces_libre"]
           else (tr["ouvert_horaires"] if t["ouvert_public"]
                 else (tr["non_reserve"] if declare else None))),
        kv(tr["kv"]["eclairage"], oui_ou_non(t["eclairage"])),
        kv(tr["kv"]["vestiaires"], oui_ou_non(t["vestiaires"])),
        kv(tr["kv"]["douches"], oui_ou_non(t["douches"])),
        kv(tr["kv"]["sanitaires"], oui_ou_non(t["sanitaires"])),
        kv(tr["kv"]["tribunes"], tr["places"](t["tribunes"]) if t.get("tribunes") else None),
        kv(tr["kv"]["type_site"], tr["enceinte_scolaire"] if t["scolaire"] else None),
        kv(tr["kv"]["horaires"], t.get("horaires")),
    ])
    if acces:
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


def page_departement(code, nom_dep, region, sites, lang, url_base, depot, villes=None):
    chemin = url_dep(lang, code)
    r = rel(chemin)
    tr = T[lang]
    titre = tr["dep_titre"].format(dep=nom_dep or code)
    desc = tr["dep_desc"].format(n=len(sites), dep=nom_dep or code, reg=region or "France")
    alternatives = {l: url_dep(l, code) for l in T}

    # Chaque entree porte le lieu lui-meme, pas seulement son lien : un agent
    # qui lit la page du departement y trouve deja commune, revetement et
    # coordonnees, sans avoir a ouvrir les 200 fiches une par une.
    def entree(i, s):
        lieu = {"@type": "SportsActivityLocation", "@id": f"{url_base}/{url_site(lang, s['id'])}#place",
                "name": nom_de(s, lang), "url": f"{url_base}/{url_site(lang, s['id'])}",
                "sport": "Athletics", "identifier": s["id"]}
        if s.get("ville"):
            lieu["address"] = {"@type": "PostalAddress", "addressLocality": s["ville"],
                               "addressRegion": nom_dep or code, "addressCountry": "FR"}
        if s.get("lat") is not None and s.get("lon") is not None:
            lieu["geo"] = {"@type": "GeoCoordinates",
                           "latitude": s["lat"], "longitude": s["lon"]}
        if s.get("surface"):
            lieu["additionalProperty"] = [{"@type": "PropertyValue",
                                           "name": tr["kv"]["revetement"],
                                           "value": SOL[lang].get(s["surface"], s["surface"])}]
        return {"@type": "ListItem", "position": i + 1, "item": lieu}

    liste_ld = {
        "@context": "https://schema.org", "@type": "ItemList",
        "name": titre, "numberOfItems": len(sites),
        "itemListOrder": "https://schema.org/ItemListUnordered",
        "itemListElement": [entree(i, s) for i, s in enumerate(sites)],
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
            # Le regroupement se fait sur le nom exact de la commune : tous les
            # sites du groupe partagent donc la meme page de ville, et le titre
            # du groupe est le seul lien qui y mene depuis le departement.
            sl = (villes or {}).get(s["id"])
            etiquette = (f'<a href="{r}{url_ville(lang, sl)}">{E(ville_courante or "")}</a>'
                         if sl else E(ville_courante or ""))
            lignes.append(f'<h2 class="ville">{etiquette}</h2><ul class="liste">')
        details = []
        tour, sur = tour_de_piste(s)
        if tour:
            details.append(f"{tour} m" if sur else f"{tour} m ?")
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


def page_contributeurs(communaute, par_id, lang, url_base, depot, maj):
    """La page qui rend visible qui tient ce jeu de donnees a jour.

    Un annuaire derive de donnees publiques ne coute rien a personne ; les
    photos et les avis, si. Les nommer et compter ce que chacun a apporte est
    la seule monnaie que ce projet puisse rendre — et la meilleure raison, pour
    le lecteur suivant, d'y ajouter la sienne."""
    chemin = url_contrib(lang)
    r = rel(chemin)
    tr = T[lang]
    alternatives = {l: url_contrib(l) for l in T}
    titre = f"{tr['contrib_titre']} — {tr['marque']}"
    top = communaute.get("top") or []
    recentes = communaute.get("recentes") or []
    # build_data.py a deja reconcilie les noms pour le classement ; on reprend
    # sa table plutot que de refaire — et de refaire differemment — la fusion.
    canon = {}
    for c in top:
        plein = c["n"]
        canon[plein.lower()] = plein
        for i in range(1, len(plein.split())):
            canon.setdefault(" ".join(plein.split()[:i]).lower(), plein)

    fil = {"@context": "https://schema.org", "@type": "BreadcrumbList",
           "itemListElement": [
               {"@type": "ListItem", "position": 1, "name": tr["accueil"],
                "item": f"{url_base}/{url_appli(lang)}"},
               {"@type": "ListItem", "position": 2, "name": tr["contrib_titre"],
                "item": f"{url_base}/{chemin}"}]}

    lignes = [entete(lang, titre, tr["contrib_desc"], chemin, alternatives, [fil], url_base)]
    lignes.append(f"<h1>{E(tr['contrib_titre'])}</h1>")
    lignes.append(f'<p class="lede">{E(tr["contrib_intro"])}</p>')

    if not top and not recentes:
        lignes.append(f'<p class="empty">{E(tr["contrib_vide"])}</p>')

    if top:
        lignes.append(f"<h2>{E(tr['contrib_classement'])}</h2>")
        lignes.append('<ol class="palmares">')
        for i, c in enumerate(top, 1):
            detail = " · ".join(filter(None, [
                tr["contrib_sites"](c["s"]),
                tr["contrib_photos"](c["p"]) if c.get("p") else "",
                tr["contrib_avis"](c["a"]) if c.get("a") else ""]))
            lignes.append(f'<li><span class="rang">{i}</span>'
                          f'<span><strong>{E(c["n"])}</strong>'
                          f'<span class="meta">{E(detail)}</span></span></li>')
        lignes.append("</ol>")

    if recentes:
        lignes.append(f"<h2>{E(tr['contrib_toutes'])}</h2>")
        lignes.append('<ul class="contributions">')
        for c in recentes:
            t = par_id.get(c["i"])
            if not t:
                continue
            nom = nom_de(t, lang)
            lieu = ", ".join(x for x in (t.get("ville"), t.get("dep_nom")) if x)
            bruts = ({p["c"] for p in t["photos"] if p.get("c")}
                     | {a["a"] for a in t["avis"] if a.get("a")})
            auteurs = sorted({canon.get(x.lower(), x) for x in bruts})
            detail = " · ".join(filter(None, [
                tr["contrib_photos"](len(t["photos"])) if t["photos"] else "",
                tr["contrib_avis"](len(t["avis"])) if t["avis"] else "",
                tr["contrib_par"](", ".join(auteurs)) if auteurs else "",
                tr["contrib_le"](fmt_date(c["d"], lang)) if c.get("d") else ""]))
            vignette = ""
            if t["photos"]:
                p = t["photos"][0]
                taille = dimensions_jpeg(os.path.join(ROOT, p.get("t") or p["f"]))
                dims = f' width="{taille[0]}" height="{taille[1]}"' if taille else ""
                vignette = (f'<img loading="lazy" src="{r}{E(p.get("t") or p["f"])}" '
                            f'alt="{E(alt_photo(p, t, lang))}"{dims}>')
            lignes.append(
                f'<li>{vignette}<span class="quoi">'
                f'<a href="{r}{url_site(lang, t["id"])}">{E(nom)}</a>'
                f'<span class="loc">{E(lieu)}</span>'
                f'<span class="meta">{E(detail)}</span></span></li>')
        lignes.append("</ul>")

    lignes.append(f'<div class="appel"><strong>{E(tr["contrib_appel"])}</strong>'
                  f'<p>{E(tr["contrib_appel_texte"])}</p>'
                  f'<a class="btn primary" href="https://github.com/{depot}'
                  f'/blob/master/CONTRIBUTING.md">{E(tr["contrib_appel_lien"])}</a></div>')
    lignes.append(pied(lang, chemin, url_base, depot))
    return "\n".join(lignes)


# ------------------------------------------------------------ confidentialite
# Le site mesure son audience depuis le 25 aout 2026. Une mesure sans cookie
# n'a pas besoin d'un bandeau, mais elle a besoin d'etre dite : cette page dit
# ce qui est enregistre, ce qui ne l'est pas, et pourquoi il n'y a rien a
# cliquer. Elle vit ici, comme les autres pages, parce qu'elle doit exister
# dans les deux langues et suivre le meme gabarit.
#
# REGLE : ce texte decrit le code publie, pas une intention. Si assets/matomo.js,
# logs/worker.js ou la liste des serveurs appeles par la page changent, cette
# page change le meme jour. Une politique de confidentialite qui a pris du
# retard sur le code est un mensonge, pas un document.
#
# `{depot}` est le depot GitHub ; aucune accolade ne doit apparaitre ailleurs
# dans ces textes, ils passent par str.format.
# assets/app.js assemble l'adresse a l'execution pour qu'elle n'apparaisse
# nulle part en clair dans le HTML, ou les robots collecteurs viendraient la
# lire. Cette page est lisible sans JavaScript : elle ne peut pas assembler.
# Elle ecrit donc l'adresse en toutes lettres mais desamorcee, et sans lien
# mailto — un humain comme un agent la reconstitue, un moissonneur naif non.
CONTACT_BOITE, CONTACT_DOMAINE = "ronanchardonneau", "gmail.com"

PRIVE = {
    "fr": [
        ("Ce qui est mesuré", """
<p>La mesure d'audience utilise <a href="https://matomo.org/" rel="noopener">Matomo</a>,
   hébergé en Europe. À l'ouverture d'une page, elle enregistre l'adresse de cette page,
   le site ou le moteur qui vous y a amené, un pays et une région déduits de l'adresse IP,
   le type d'appareil, le navigateur et sa langue, la taille de l'écran, le temps passé sur
   la page, et les liens sortants cliqués — OpenStreetMap, le site de la mairie, l'itinéraire.</p>
<p>L'adresse IP n'est pas conservée entière : ses deux derniers octets sont effacés avant
   l'enregistrement — <code>62.210.0.0</code> et non <code>62.210.x.y</code>. C'est ce tronçon
   qui sert à situer la visite dans un pays et une région ; il ne désigne personne. Vérifié le
   25 août 2026 dans les données elles-mêmes, pas seulement dans un réglage.</p>
<p>Ce que vous tapez dans la recherche est également enregistré, avec le nombre de résultats
   obtenus — une fois la frappe finie, jamais lettre à lettre. La raison est précise : une
   recherche qui ne rend rien désigne une piste absente de l'annuaire, et c'est la seule façon
   de l'apprendre. Cette case sert à trouver un stade : n'y écrivez rien qui vous concerne.</p>
<p>Un seul drapeau supplémentaire est enregistré, et seulement s'il est vrai :
   <code>navigator.webdriver</code>, que votre navigateur pose de lui-même lorsqu'il est
   conduit par un programme plutôt que par une personne. Il sert à distinguer les visites
   d'agents automatisés des vôtres. Rien ne va le chercher : c'est le navigateur qui
   l'annonce, et quand il vaut faux, rien n'est écrit — un blanc ne dit pas « humain », il
   dit qu'aucun signal n'a été vu. Aucune empreinte n'est calculée, ni de votre matériel, ni
   de votre façon de bouger la souris.</p>
<p>Rien là-dedans ne vous nomme, et rien ne relie deux visites entre elles : sans cookie ni
   identifiant conservé, vous revenez demain en parfait inconnu.</p>
<p>À quoi ça sert : ce projet pose une question précise — les agents IA lisent-ils cet
   annuaire, et envoient-ils des gens dessus ? Matomo répond pour la moitié humaine,
   en classant les arrivées venues de ChatGPT, Perplexity, Claude ou Gemini. Sans cette
   mesure, la réponse resterait une intuition.</p>"""),

        ("Pas de cookie, donc pas de bandeau", """
<p>La première instruction du traceur est <code>disableCookies()</code> : aucun cookie n'est
   déposé, rien n'est écrit ni lu sur votre appareil pour mesurer l'audience. C'est ce qui
   dispense de vous demander votre consentement — la loi l'exige pour accéder à votre
   terminal, ce que ce site ne fait pas. Le traitement lui-même repose sur l'intérêt
   légitime du responsable (article 6.1.f du RGPD) : savoir si ce qu'il publie est lu.</p>
<p>Un navigateur qui envoie l'en-tête <em>Do Not Track</em> n'est pas mesuré du tout :
   ni anonymisé, ni allégé — pas mesuré. On y perd quelques visites, on y gagne de pouvoir
   écrire cette phrase sans réserve.</p>
<p>Le réglage tient en trente lignes, et il est public :
   <a href="https://github.com/{depot}/blob/master/assets/matomo.js" rel="noopener">assets/matomo.js</a>.
   Le jour où un cookie y apparaîtrait, cette page le dirait le même jour.</p>"""),

        ("Ce que le site ne fait pas", """
<ul>
  <li>Aucun compte, aucun mot de passe, aucune inscription.</li>
  <li>Aucune publicité, et donc aucun traceur publicitaire.</li>
  <li>Aucune revente, aucun échange de données avec un tiers commercial.</li>
  <li>Aucune empreinte de navigateur (<em>fingerprinting</em>), aucun suivi d'un site à l'autre.</li>
  <li>Aucune adresse e-mail collectée à votre insu : vous n'en donnez une que si vous
      écrivez, et c'est alors pour vous répondre.</li>
</ul>"""),

        ("Votre position ne quitte pas votre appareil", """
<p>Le bouton « autour de moi » demande votre position au navigateur, qui vous la demande à
   son tour. Elle sert à trier la liste par distance, dans la page, sur votre appareil.
   Elle n'est envoyée nulle part : ni au site, ni à Matomo, ni à la carte. Refuser ne coûte
   que le tri par distance ; la recherche par ville ou par code postal donne le même annuaire.</p>"""),

        ("Ce qui reste sur votre appareil", """
<p>Pas de cookie, mais deux choses techniques, qui ne sont pas des identifiants :</p>
<ul>
  <li>un <strong>cache hors-ligne</strong> (<em>service worker</em>) qui garde les fichiers de
      l'application et les sites de l'annuaire, pour qu'il fonctionne dans un stade sans réseau ;</li>
  <li>une clé <code>reparation</code> dans la mémoire de l'onglet
      (<em>sessionStorage</em>), qui empêche l'application de se recharger en boucle après
      une mise à jour, et qui disparaît quand vous fermez l'onglet.</li>
</ul>
<p>Vider les données du site dans votre navigateur efface les deux.</p>"""),

        ("Les robots, eux, sont journalisés", """
<p>Le domaine passe par Cloudflare, et un petit programme y note le passage des robots
   d'exploration : Googlebot, GPTBot, ClaudeBot, PerplexityBot et les autres. C'est le seul
   endroit d'où on puisse les voir — un robot n'exécute pas JavaScript, aucune mesure posée
   dans la page ne l'atteint jamais.</p>
<p>Ce journal ne contient <strong>aucune visite humaine</strong> et <strong>aucune adresse
   IP</strong>. Une ligne, c'est : la date en UTC, le nom du robot, son <em>user-agent</em>,
   l'hôte, le chemin demandé, le type de page, le code de réponse, et le pays du centre de
   données d'où part la requête — qui désigne une machine, jamais une personne. Le code est
   lisible : <a href="https://github.com/{depot}/blob/master/logs/worker.js" rel="noopener">logs/worker.js</a>.</p>"""),

        ("Ce que votre navigateur demande à d'autres serveurs", """
<p>Afficher une carte ou une vue aérienne oblige votre navigateur à réclamer des fichiers
   ailleurs. Ces serveurs voient alors, comme tout serveur sollicité, votre adresse IP et
   votre navigateur. Aucun d'eux ne reçoit votre position ni la moindre donnée vous
   concernant de la part de ce site.</p>
<ul>
  <li><strong>GitHub Pages</strong> et <strong>Cloudflare</strong> — l'hébergement et la
      distribution des pages.</li>
  <li><strong>cdn.matomo.cloud</strong> et <strong>ronanchardonneau.matomo.cloud</strong> —
      la mesure d'audience décrite plus haut.</li>
  <li><strong>unpkg.com</strong> — Leaflet, la bibliothèque qui dessine la carte.</li>
  <li><strong>tile.openstreetmap.org</strong> — les tuiles du fond de carte, quand vous
      ouvrez l'onglet « carte ».</li>
  <li><strong>data.geopf.fr</strong> — les vues aériennes de l'IGN, affichées sur les fiches
      qui n'ont pas encore de photo. Les images ne sont pas stockées ici, elles sont demandées
      à la Géoplateforme au moment de l'affichage.</li>
  <li><strong>Google Maps</strong> — seulement si vous cliquez « Itinéraire » ou
      « Horaires » : vous quittez alors le site, et ce sont les règles de Google qui
      s'appliquent.</li>
</ul>"""),

        ("Contribuer, c'est publier", """
<p>Une photo, un avis ou une correction sont publiés sur le site sous licence ODbL, avec le
   crédit que vous indiquez. Ce crédit, c'est vous qui l'écrivez : un prénom, un nom complet
   ou un pseudonyme, à votre choix — c'est la seule chose de vous qui apparaîtra.</p>
<p>Deux chemins, et ils ne sont pas équivalents. Le <strong>formulaire GitHub</strong> crée
   une discussion publique sous votre compte GitHub, visible de tous. L'<strong>e-mail</strong>
   arrive dans une boîte privée : votre adresse sert à vous répondre, n'est jamais publiée
   ni utilisée pour autre chose.</p>
<p>Une contribution peut être retirée du site sur simple demande. Ce que d'autres en ont déjà
   repris au titre de la licence, en revanche, échappe au projet : c'est le prix de données
   librement réutilisables, et il vaut mieux le savoir avant d'envoyer.</p>"""),

        ("Vos droits, et à qui écrire", """
<p>Le RGPD vous donne un droit d'accès, de rectification, d'effacement et d'opposition.
   Pour les contributions — nom affiché, photos, avis, e-mail échangé — c'est simple : on
   retrouve, on corrige, on supprime.</p>
<p>Pour la mesure d'audience, il faut être honnête : puisqu'elle ne conserve aucun
   identifiant, rien ne permet de retrouver <em>vos</em> visites parmi les autres, ni de vous
   les montrer, ni de les effacer sélectivement. La seule façon de vous y soustraire est
   préventive : activez <em>Do Not Track</em> dans votre navigateur, et vous ne serez pas
   mesuré du tout.</p>
<p>Responsable du traitement : Ronan Chardonneau. Pour écrire :
   <code>BOITE (arobase) DOMAINE</code> — l'adresse n'est pas cliquable, pour la
   raison qui la fait absente partout ailleurs du HTML de ce site : les robots collecteurs
   la liraient. Vous pouvez aussi passer par le
   <a href="https://github.com/{depot}/issues" rel="noopener">dépôt GitHub</a>.</p>
<p>En cas de désaccord sur la façon dont tout cela est mené, vous pouvez saisir la
   <a href="https://www.cnil.fr/fr/plaintes" rel="noopener">CNIL</a>.</p>"""),
    ],
    "en": [
        ("What is measured", """
<p>Audience measurement runs on <a href="https://matomo.org/" rel="noopener">Matomo</a>,
   hosted in Europe. When a page opens, it records that page's address, the site or search
   engine you came from, a country and region derived from the IP address, the device type,
   the browser and its language, the screen size, the time spent on the page, and the outbound
   links clicked — OpenStreetMap, the town hall website, the directions link.</p>
<p>The IP address is not kept whole: its last two bytes are zeroed before storage —
   <code>62.210.0.0</code>, not <code>62.210.x.y</code>. That stub is what places the visit in a
   country and a region; it designates nobody. Checked on 25 August 2026 against the stored data
   itself, not merely against a setting.</p>
<p>What you type in the search box is recorded too, along with how many results it returned —
   once you stop typing, never letter by letter. The reason is precise: a search that returns
   nothing points at a track missing from the directory, and there is no other way to learn of
   it. That box is for finding a stadium: do not write anything about yourself in it.</p>
<p>One extra flag is recorded, and only when it is true: <code>navigator.webdriver</code>,
   which your browser sets by itself when it is driven by a program rather than by a person.
   It serves to tell automated agent visits apart from yours. Nothing goes looking for it: the
   browser announces it, and when it is false nothing is written — a blank does not say
   &laquo;&nbsp;human&nbsp;&raquo;, it says no signal was seen. No fingerprint is computed,
   neither of your hardware nor of the way you move the mouse.</p>
<p>None of this names you, and nothing ties two visits together: with no cookie and no stored
   identifier, you come back tomorrow as a complete stranger.</p>
<p>What it is for: this project asks one precise question — do AI agents read this directory,
   and do they send people to it? Matomo answers the human half, by sorting arrivals coming
   from ChatGPT, Perplexity, Claude or Gemini. Without the measurement, the answer would stay
   a hunch.</p>"""),

        ("No cookie, so no banner", """
<p>The tracker's first instruction is <code>disableCookies()</code>: no cookie is set, nothing
   is written to or read from your device in order to measure the audience. That is what makes
   a consent request unnecessary — the law requires it for accessing your terminal, which this
   site does not do. The processing itself rests on the controller's legitimate interest
   (GDPR article 6(1)(f)): knowing whether what he publishes is read.</p>
<p>A browser sending the <em>Do Not Track</em> header is not measured at all: not anonymised,
   not trimmed — not measured. It costs a few visits; it buys the right to write that sentence
   without a footnote.</p>
<p>The whole setting is thirty lines long, and it is public:
   <a href="https://github.com/{depot}/blob/master/assets/matomo.js" rel="noopener">assets/matomo.js</a>.
   The day a cookie appeared there, this page would say so the same day.</p>"""),

        ("What this site does not do", """
<ul>
  <li>No account, no password, no sign-up.</li>
  <li>No advertising, and therefore no advertising tracker.</li>
  <li>No selling, no exchange of data with a commercial third party.</li>
  <li>No browser fingerprinting, no cross-site tracking.</li>
  <li>No email address collected behind your back: you only give one by writing in, and it is
      then used to reply to you.</li>
</ul>"""),

        ("Your location never leaves your device", """
<p>The &laquo;&nbsp;near me&nbsp;&raquo; button asks the browser for your position, and the
   browser asks you. It is used to sort the list by distance, inside the page, on your device.
   It is sent nowhere: not to the site, not to Matomo, not to the map. Declining costs you the
   distance sort and nothing else; searching by town or postcode returns the same directory.</p>"""),

        ("What stays on your device", """
<p>No cookie, but two technical things, neither of which is an identifier:</p>
<ul>
  <li>an <strong>offline cache</strong> (a <em>service worker</em>) holding the app's files and
      the venues, so the directory still works in a stadium with no signal;</li>
  <li>a <code>reparation</code> key in the tab's memory (<em>sessionStorage</em>), which stops
      the app reloading in a loop after an update, and disappears when you close the tab.</li>
</ul>
<p>Clearing the site's data in your browser removes both.</p>"""),

        ("Robots, on the other hand, are logged", """
<p>The domain goes through Cloudflare, where a small program records the passage of crawlers:
   Googlebot, GPTBot, ClaudeBot, PerplexityBot and the rest. It is the only place they can be
   seen from — a crawler does not run JavaScript, so no in-page measurement ever reaches it.</p>
<p>That log holds <strong>no human visit</strong> and <strong>no IP address</strong>. One line
   is: the UTC timestamp, the robot's canonical name, its <em>user-agent</em>, the host, the
   requested path, the page type, the response code, and the country of the data centre the
   request comes from — which designates a machine, never a person. The code is there to read:
   <a href="https://github.com/{depot}/blob/master/logs/worker.js" rel="noopener">logs/worker.js</a>.</p>"""),

        ("What your browser requests from other servers", """
<p>Drawing a map or an aerial view forces your browser to fetch files elsewhere. Those servers
   then see, as any requested server does, your IP address and your browser. None of them
   receives your location, or any data about you from this site.</p>
<ul>
  <li><strong>GitHub Pages</strong> and <strong>Cloudflare</strong> — hosting and delivery of
      the pages.</li>
  <li><strong>cdn.matomo.cloud</strong> and <strong>ronanchardonneau.matomo.cloud</strong> —
      the audience measurement described above.</li>
  <li><strong>unpkg.com</strong> — Leaflet, the library that draws the map.</li>
  <li><strong>tile.openstreetmap.org</strong> — the base map tiles, once you open the map tab.</li>
  <li><strong>data.geopf.fr</strong> — the IGN aerial views shown on venues that have no photo
      yet. The images are not stored here; they are requested from the French Géoplateforme as
      the page is displayed.</li>
  <li><strong>Google Maps</strong> — only if you click &laquo;&nbsp;Directions&nbsp;&raquo; or
      &laquo;&nbsp;Opening hours&nbsp;&raquo;: you then leave this site, and Google's rules
      apply.</li>
</ul>"""),

        ("Contributing means publishing", """
<p>A photo, a review or a correction is published on the site under the ODbL licence, with the
   credit you give. You write that credit yourself: a first name, a full name or a pseudonym,
   as you prefer — it is the only thing about you that will appear.</p>
<p>Two routes, and they are not equivalent. The <strong>GitHub form</strong> opens a public
   thread under your GitHub account, visible to everyone. <strong>Email</strong> lands in a
   private inbox: your address is used to answer you, never published, never used for anything
   else.</p>
<p>A contribution can be taken off the site on request. What others have already reused under
   the licence, however, is beyond the project's reach: that is the price of freely reusable
   data, and it is better known before you send.</p>"""),

        ("Your rights, and who to write to", """
<p>The GDPR gives you rights of access, rectification, erasure and objection. For contributions
   — displayed name, photos, reviews, emails exchanged — this is straightforward: they can be
   found, corrected, deleted.</p>
<p>For audience measurement, honesty is due: since it keeps no identifier, nothing makes it
   possible to find <em>your</em> visits among the others, to show them to you, or to erase them
   selectively. The only way out is preventive: turn <em>Do Not Track</em> on in your browser,
   and you will not be measured at all.</p>
<p>Data controller: Ronan Chardonneau. To write: <code>BOITE (at) DOMAINE</code> —
   the address is not a clickable link, for the reason it appears nowhere else in this site's
   HTML: harvesters would read it. You can also go through the
   <a href="https://github.com/{depot}/issues" rel="noopener">GitHub repository</a>.</p>
<p>If you disagree with how any of this is handled, you may lodge a complaint with the French
   <a href="https://www.cnil.fr/en/home" rel="noopener">CNIL</a>.</p>"""),
    ],
}


def page_confidentialite(lang, url_base, depot, maj):
    """Ce que le site mesure, ce qu'il ne mesure pas, et pourquoi rien a cliquer.

    Une mesure d'audience sans cookie n'oblige a aucun bandeau ; elle n'exempte
    pas de dire ce qui est enregistre. Cette page est la contrepartie de la
    promesse faite partout ailleurs sur le site : elle est verifiable ligne a
    ligne, puisqu'elle renvoie au code qu'elle decrit."""
    chemin = url_prive(lang)
    r = rel(chemin)
    tr = T[lang]
    alternatives = {l: url_prive(l) for l in T}
    titre = f"{tr['prive_titre']} — {tr['marque']}"
    fil = {"@context": "https://schema.org", "@type": "BreadcrumbList",
           "itemListElement": [
               {"@type": "ListItem", "position": 1, "name": tr["accueil"],
                "item": f"{url_base}/{url_appli(lang)}"},
               {"@type": "ListItem", "position": 2, "name": tr["prive_titre"],
                "item": f"{url_base}/{chemin}"}]}

    lignes = [entete(lang, titre, tr["prive_desc"], chemin, alternatives, [fil], url_base)]
    lignes.append(f'<nav class="crumb"><a href="{r}{url_appli(lang)}">{E(tr["accueil"])}</a>'
                  f' › {E(tr["prive_titre"])}</nav>')
    lignes.append(f"<h1>{E(tr['prive_titre'])}</h1>")
    lignes.append(f'<p class="lede">{tr["prive_lede"]}</p>')
    lignes.append('<div class="prose">')
    for sous_titre, corps in PRIVE[lang]:
        lignes.append(f"<h2>{E(sous_titre)}</h2>")
        lignes.append(corps.format(depot=depot)
                      .replace("BOITE", CONTACT_BOITE)
                      .replace("DOMAINE", CONTACT_DOMAINE))
    lignes.append("</div>")
    lignes.append(f'<p class="src">{E(tr["prive_maj"](fmt_date(maj, lang)))}</p>')
    lignes.append(pied(lang, chemin, url_base, depot))
    return "\n".join(lignes)


def page_index(deps_tries, total, lang, url_base, depot, axes=()):
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

    # Les pages par critere n'etaient liees que les unes aux autres. L'annuaire
    # des departements est deja le hub du site : c'est la qu'elles se raccrochent.
    if axes:
        lignes.append(f'<h2>{E(tr["index_criteres"])}</h2>'
                      f'<p class="lede">{E(tr["index_criteres_intro"])}</p><div class="cols">')
        for crit in axes:
            lignes.append(f'<a href="{r}{url_critere(lang, crit["slug"][lang])}">'
                          f'{E(crit["titre"][lang].format(dep=""))} '
                          f'<span class="meta">({len(crit["sites"])})</span></a>')
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
    # Ces deux liens pointent vers des pages qui ont un segment different en
    # anglais : sans traduction du href, la coquille anglaise renverrait un
    # lecteur sans JavaScript sur une page qui n'existe pas.
    ('href="contributeurs/"', 'href="contributors/"'),
    ('href="confidentialite/"', 'href="privacy/"'),
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
    ('data-i18n="nav_contributeurs">Les contributeurs<',
     'data-i18n="nav_contributeurs">Contributors<'),
    ('data-i18n="nav_prive">Confidentialité<', 'data-i18n="nav_prive">Privacy<'),
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
    # Les noeuds de page du graphe JSON-LD : la description de la page et sa
    # FAQ n'ont de sens que dans la langue de la page qui les porte. Le reste
    # du graphe (site, auteur, jeu de donnees) vaut pour les deux langues et
    # reste tel quel.
    ("""    {
      "@type": "WebPage",
      "@id": "{BASE}/#page",
      "url": "{BASE}/",
      "name": "Où s'entraîner ? — Pistes d'athlétisme en France",
      "isPartOf": { "@id": "{BASE}/#site" },
      "inLanguage": "fr",
      "dateModified": "__MAJ__",
      "primaryImageOfPage": "{BASE}/assets/og.png",
      "mainEntity": { "@id": "{BASE}/#dataset" }
    },
    {
      "@type": "FAQPage",
      "@id": "{BASE}/#faq",
      "isPartOf": { "@id": "{BASE}/#page" },
      "inLanguage": "fr",
      "mainEntity": [
        {
          "@type": "Question",
          "name": "Peut-on s'entraîner librement sur une piste d'athlétisme ?",
          "acceptedAnswer": { "@type": "Answer", "text": "Cela dépend de l'installation. Une partie des stades est en accès libre permanent ; d'autres n'ouvrent au public qu'à certaines heures, en dehors des créneaux réservés aux clubs et aux scolaires ; d'autres encore restent fermés hors licence. Chaque fiche indique ce que déclare le gestionnaire, et le filtre « accès libre » ne garde que les sites ouverts. Cette information étant déclarative et rarement mise à jour, mieux vaut la vérifier auprès de la mairie ou du club avant de se déplacer." }
        },
        {
          "@type": "Question",
          "name": "Comment trouver la piste d'athlétisme la plus proche de chez moi ?",
          "acceptedAnswer": { "@type": "Answer", "text": "Tapez une ville, un code postal ou le nom d'un stade dans la recherche, ou touchez le bouton de géolocalisation pour classer les installations par distance depuis votre position. La vue carte affiche les mêmes résultats géographiquement, et l'annuaire par département permet de parcourir les installations sans JavaScript." }
        },
        {
          "@type": "Question",
          "name": "Quelle est la longueur d'une piste d'athlétisme ?",
          "acceptedAnswer": { "@type": "Answer", "text": "La piste de référence, celle des compétitions officielles, fait 400 mètres au couloir 1. Beaucoup d'équipements français sont plus courts : on trouve couramment des anneaux de 333 m, 300 m, 250 m ou 200 m, ainsi que des lignes droites isolées de 100 ou 120 m. Le développement réel est indiqué sur chaque fiche quand il est connu, ce qui change le calcul d'une séance fractionnée." }
        },
        {
          "@type": "Question",
          "name": "Quelle différence entre une piste en tartan et une piste en cendrée ?",
          "acceptedAnswer": { "@type": "Answer", "text": "Le tartan, nom courant des revêtements synthétiques en polyuréthane, est amortissant, praticable par tous les temps et compatible avec les pointes de compétition. La cendrée, surface en mâchefer damé, devient lourde sous la pluie et se déforme, mais reste plus douce pour l'appareil locomoteur. Le site distingue aussi les pistes en sable, en gazon, en bitume et les anneaux couverts." }
        },
        {
          "@type": "Question",
          "name": "D'où viennent ces données, et peut-on les réutiliser ?",
          "acceptedAnswer": { "@type": "Answer", "text": "La base est le recensement des équipements sportifs (Data ES) du ministère chargé des Sports, sous Licence Ouverte 2.0. Les corrections, les photos prises sur place et les avis viennent de contributeurs. Le jeu de données complet est téléchargeable en un seul fichier JSON et réutilisable librement, y compris commercialement, avec mention de la source." }
        }
      ]
    }
""",
     """    {
      "@type": "WebPage",
      "@id": "{BASE}/en/#page",
      "url": "{BASE}/en/",
      "name": "Where to train? — Athletics tracks in France",
      "isPartOf": { "@id": "{BASE}/#site" },
      "inLanguage": "en",
      "dateModified": "__MAJ__",
      "primaryImageOfPage": "{BASE}/assets/og.png",
      "mainEntity": { "@id": "{BASE}/#dataset" }
    },
    {
      "@type": "FAQPage",
      "@id": "{BASE}/en/#faq",
      "isPartOf": { "@id": "{BASE}/en/#page" },
      "inLanguage": "en",
      "mainEntity": [
        {
          "@type": "Question",
          "name": "Can anyone train on a French athletics track?",
          "acceptedAnswer": { "@type": "Answer", "text": "It depends on the venue. Some stadiums are open to all at any time; others open to the public only outside the slots booked by clubs and schools; others stay closed to non-members. Every page states what the operator declared, and the \u00ab free access \u00bb filter keeps only the open venues. Because that information is self-declared and rarely refreshed, check with the town hall or the local club before travelling." }
        },
        {
          "@type": "Question",
          "name": "How do I find the nearest athletics track?",
          "acceptedAnswer": { "@type": "Answer", "text": "Type a town, a postcode or a stadium name in the search box, or tap the location button to sort venues by distance from where you are. The map view shows the same results geographically, and the directory by department lets you browse every venue without JavaScript." }
        },
        {
          "@type": "Question",
          "name": "How long is an athletics track?",
          "acceptedAnswer": { "@type": "Answer", "text": "The reference track used in official competition is 400 metres in lane 1. Many French venues are shorter: loops of 333 m, 300 m, 250 m or 200 m are common, as are standalone straights of 100 or 120 m. Each page gives the actual lap length when it is known, which changes how you plan an interval session." }
        },
        {
          "@type": "Question",
          "name": "What is the difference between a tartan track and a cinder track?",
          "acceptedAnswer": { "@type": "Answer", "text": "Tartan, the common name for polyurethane synthetic surfaces, is cushioned, usable in any weather and takes competition spikes. Cinder, a rolled clinker surface, turns heavy in the rain and deforms, but is gentler on the joints. The directory also distinguishes sand, grass and asphalt tracks, and indoor loops." }
        },
        {
          "@type": "Question",
          "name": "Where does this data come from, and may I reuse it?",
          "acceptedAnswer": { "@type": "Answer", "text": "The base is the French sports ministry's census of sports facilities (Data ES), under Licence Ouverte 2.0. Corrections, on-site photos and reviews come from contributors. The whole dataset can be downloaded as a single JSON file and reused freely, including commercially, as long as the source is credited." }
        }
      ]
    }
"""),
    # Le contenu statique de l'accueil : sans lui, la coquille anglaise n'offre
    # a un moteur qu'une page vide, et sa FAQ ne correspondrait pas au balisage
    # FAQPage servi juste au-dessus.
    ("""    <section class="seo" aria-labelledby="seo-titre">
      <h2 id="seo-titre">L'annuaire des pistes d'athlétisme françaises</h2>
      <p><strong>Où s'entraîner&nbsp;?</strong> recense les 7&nbsp;100 installations d'athlétisme
        de France métropolitaine et d'outre-mer, dont environ 6&nbsp;500 disposent d'une piste.
        Pour chacune&nbsp;: le revêtement, le développement de la piste et son nombre de couloirs,
        les sautoirs en longueur, hauteur et perche, les aires de lancer, l'éclairage, les
        vestiaires et les conditions d'accès. Les données proviennent du recensement des
        équipements sportifs du ministère chargé des Sports, sous Licence Ouverte&nbsp;2.0, et
        sont complétées par les athlètes eux-mêmes.</p>

      <h3>Peut-on s'entraîner librement sur une piste d'athlétisme&nbsp;?</h3>
      <p>Cela dépend de l'installation. Une partie des stades est en accès libre permanent&nbsp;;
        d'autres n'ouvrent au public qu'à certaines heures, en dehors des créneaux réservés aux
        clubs et aux scolaires&nbsp;; d'autres encore restent fermés hors licence. Chaque fiche
        indique ce que déclare le gestionnaire, et le filtre «&nbsp;accès libre&nbsp;» ne garde
        que les sites ouverts. Cette information étant déclarative et rarement mise à jour,
        mieux vaut la vérifier auprès de la mairie ou du club avant de se déplacer.</p>

      <h3>Comment trouver la piste la plus proche de chez moi&nbsp;?</h3>
      <p>Tapez une ville, un code postal ou le nom d'un stade dans la recherche, ou touchez le
        bouton de géolocalisation pour classer les installations par distance depuis votre
        position. La vue carte affiche les mêmes résultats géographiquement, et l'annuaire par
        département permet de parcourir les installations sans JavaScript.</p>

      <h3>Quelle est la longueur d'une piste d'athlétisme&nbsp;?</h3>
      <p>La piste de référence, celle des compétitions officielles, fait 400&nbsp;mètres au
        couloir&nbsp;1. Beaucoup d'équipements français sont plus courts&nbsp;: on trouve
        couramment des anneaux de 333&nbsp;m, 300&nbsp;m, 250&nbsp;m ou 200&nbsp;m, ainsi que des
        lignes droites isolées de 100&nbsp;ou 120&nbsp;m. Le développement réel est indiqué sur
        chaque fiche quand il est connu, ce qui change le calcul d'une séance fractionnée.</p>

      <h3>Quelle différence entre une piste en tartan et une piste en cendrée&nbsp;?</h3>
      <p>Le tartan — nom courant des revêtements synthétiques en polyuréthane — est amortissant,
        praticable par tous les temps et compatible avec les pointes de compétition. La cendrée,
        surface en mâchefer damé, devient lourde sous la pluie et se déforme, mais reste plus
        douce pour l'appareil locomoteur. Le site distingue aussi les pistes en sable, en gazon,
        en bitume et les anneaux couverts.</p>

      <h3>D'où viennent ces données, et peut-on les réutiliser&nbsp;?</h3>
      <p>La base est le recensement des équipements sportifs (Data&nbsp;ES) du ministère chargé
        des Sports, sous Licence Ouverte&nbsp;2.0. Les corrections, les photos prises sur place
        et les avis viennent de contributeurs. Le jeu de données complet est téléchargeable en
        un seul fichier JSON et réutilisable librement, y compris commercialement, avec mention
        de la source.</p>

      <p class="seo-liens">
        <a href="data/tracks.json">Télécharger le jeu de données (JSON)</a> ·
        <a href="llms.txt">Description lisible par un agent</a> ·
        <a href="departments/">Parcourir par département</a>
      </p>
    </section>""",
     """    <section class="seo" aria-labelledby="seo-titre">
      <h2 id="seo-titre">The directory of French athletics tracks</h2>
      <p><strong>Where to train?</strong> lists the 7,100 athletics venues of mainland and
        overseas France, about 6,500 of which have a running track. For each one: the surface,
        the lap length and the number of lanes, the long jump, high jump and pole vault areas,
        the throwing circles, floodlighting, changing rooms and access conditions. The data comes
        from the French sports ministry's census of sports facilities, under Licence Ouverte&nbsp;2.0,
        and is corrected by the athletes who train there.</p>

      <h3>Can anyone train on a French athletics track?</h3>
      <p>It depends on the venue. Some stadiums are open to all at any time; others open to the
        public only outside the slots booked by clubs and schools; others stay closed to
        non-members. Every page states what the operator declared, and the
        &laquo;&nbsp;free access&nbsp;&raquo; filter keeps only the open venues. Because that
        information is self-declared and rarely refreshed, check with the town hall or the local
        club before travelling.</p>

      <h3>How do I find the nearest athletics track?</h3>
      <p>Type a town, a postcode or a stadium name in the search box, or tap the location button
        to sort venues by distance from where you are. The map view shows the same results
        geographically, and the directory by department lets you browse every venue without
        JavaScript.</p>

      <h3>How long is an athletics track?</h3>
      <p>The reference track used in official competition is 400&nbsp;metres in lane&nbsp;1. Many
        French venues are shorter: loops of 333&nbsp;m, 300&nbsp;m, 250&nbsp;m or 200&nbsp;m are
        common, as are standalone straights of 100&nbsp;or 120&nbsp;m. Each page gives the actual
        lap length when it is known, which changes how you plan an interval session.</p>

      <h3>What is the difference between a tartan track and a cinder track?</h3>
      <p>Tartan — the common name for polyurethane synthetic surfaces — is cushioned, usable in
        any weather and takes competition spikes. Cinder, a rolled clinker surface, turns heavy in
        the rain and deforms, but is gentler on the joints. The directory also distinguishes sand,
        grass and asphalt tracks, and indoor loops.</p>

      <h3>Where does this data come from, and may I reuse it?</h3>
      <p>The base is the French sports ministry's census of sports facilities (Data&nbsp;ES),
        under Licence Ouverte&nbsp;2.0. Corrections, on-site photos and reviews come from
        contributors. The whole dataset can be downloaded as a single JSON file and reused freely,
        including commercially, as long as the source is credited.</p>

      <p class="seo-liens">
        <a href="../data/tracks.json">Download the dataset (JSON)</a> ·
        <a href="../llms.txt">Agent-readable description</a> ·
        <a href="departments/">Browse by department</a>
      </p>
    </section>"""),
]


def coquilles(html_fr, url_base, maj):
    """Retourne (index.html francais, en/index.html anglais)."""
    fr = html_fr.replace(URL_DEFAUT, url_base)
    en = fr
    for avant, apres in COQUILLE_EN:
        avant = avant.replace("{BASE}", url_base)
        apres = apres.replace("{BASE}", url_base)
        if avant not in en:
            raise SystemExit(f"[ERREUR] index.html ne contient plus : {avant[:70]}…")
        en = en.replace(avant, apres)          # toutes les occurrences
    # La date de derniere generation, apres les substitutions : elle apparait
    # dans les deux coquilles. Un jeu de donnees dont la fraicheur n'est pas
    # datee est un jeu de donnees qu'un moteur suppose perime.
    fr, en = (h.replace("__MAJ__", maj) for h in (fr, en))
    # l'ordre des alternatives hreflang reste correct : elles sont absolues
    return fr, en


# ------------------------------------------------------------------- fichiers
def ecrire(chemin, contenu):
    os.makedirs(os.path.dirname(chemin), exist_ok=True)
    with open(chemin, "w", encoding="utf-8") as f:
        f.write(contenu)


# ------------------------------------------- pages par critere et par commune
# Un critere, c'est un axe que les gens tapent en clair : « piste de 400 m »,
# « stade en acces libre », « sautoir a la perche ». Chaque axe donne une page
# nationale — un carrefour qui repartit vers les departements — et une page par
# departement ou l'axe a de quoi dire quelque chose.
#
# Le produit cartesien de tous les axes par tous les departements ferait plus
# de 3 000 pages, vides pour la plupart. On part donc de la donnee : un critere
# n'existe que s'il a des sites, une intersection que si elle en a assez pour
# ne pas repeter la fiche.
MIN_INTERSECTION = 3
# 131 developpements distincts figurent au recensement, la plupart sur un seul
# site. Une longueur ne merite une page que si elle est courante.
MIN_LONGUEUR = 15
MIN_COULOIRS = 5
RAYON_VILLE_KM = 20.0
MAX_AUTOUR = 12

# « Lyon 3e Arrondissement » : Data ES ne connait pas Lyon, seulement ses
# arrondissements. Paris, Lyon et Marseille pesent 174 installations qui
# n'apparaitraient sous aucune page de commune.
ARRONDISSEMENT = re.compile(r"^(.+?)\s+\d+(?:er|e|eme|ème)\s+Arrondissement$", re.I)

AGRES_PARAM = {v: k for k, v in DISCIPLINES.items()}


def criteres(sites):
    """Les axes de page, deduits du recensement, dans l'ordre d'affichage.

    Chaque entree porte ses slugs (fr et en, figes : ce sont des URLs
    publiques), ses gabarits de titre et de description, ses sites, et le
    chemin de la facette d'API qui rend exactement la meme selection. Ce
    dernier lien est le pont entre la page et l'API : un agent qui atterrit sur
    la page decouvre qu'il existe une facon machine de la redemander."""
    out = []

    def ajoute(sl_fr, sl_en, titre, desc, retenus, api):
        if retenus:
            out.append({"slug": {"fr": sl_fr, "en": sl_en}, "titre": titre,
                        "desc": desc, "sites": retenus, "api": api})

    # --- developpement de l'anneau
    compte = {}
    for t in sites:
        if t.get("longueur_piste"):
            compte[t["longueur_piste"]] = compte.get(t["longueur_piste"], 0) + 1
    for m in sorted((v for v, n in compte.items() if n >= MIN_LONGUEUR), reverse=True):
        ajoute(f"{m}m", f"{m}m",
               {"fr": f"Pistes d'athlétisme de {m} m{{dep}}",
                "en": f"{m} m athletics tracks{{dep}}"},
               {"fr": f"Les {{n}} pistes d'athlétisme dont le ministère déclare un "
                      f"développement de {m} m{{dep}} : revêtement, couloirs, agrès, accès.",
                "en": f"The {{n}} athletics tracks recorded with a {m} m lap{{dep}}: "
                      f"surface, lanes, equipment, access."},
               [t for t in sites if t.get("longueur_piste") == m],
               f"length/{m}")

    # --- couloirs. Renseigne sur 112 sites : peu de pages, mais des pages
    # qui repondent a une question tres precise, donc tres qualifiee.
    for n in range(8, 1, -1):
        retenus = [t for t in sites if (t.get("couloirs") or 0) >= n]
        if len(retenus) < MIN_COULOIRS:
            continue
        ajoute(f"{n}-couloirs", f"{n}-lanes",
               {"fr": f"Pistes d'athlétisme d'au moins {n} couloirs{{dep}}",
                "en": f"Athletics tracks with {n} lanes or more{{dep}}"},
               {"fr": f"Les {{n}} pistes déclarant au moins {n} couloirs{{dep}}. "
                      f"Le nombre de couloirs n'est renseigné que sur une minorité de "
                      f"fiches : d'autres pistes en ont autant sans le déclarer.",
                "en": f"The {{n}} tracks declaring {n} lanes or more{{dep}}. Lane count "
                      f"is recorded on a minority of venues: others have as many "
                      f"without saying so."},
               retenus, f"lanes/{n}")

    # --- acces libre. `acces_libre` vaut vrai ou rien : la page ne parle que
    # des sites qui le declarent, et le dit.
    ajoute("acces-libre", "free-access",
           {"fr": "Pistes d'athlétisme en accès libre{dep}",
            "en": "Athletics tracks with free access{dep}"},
           {"fr": "Les {n} installations d'athlétisme déclarées librement accessibles{dep}. "
                  "Une fiche muette sur l'accès n'est pas une fiche fermée : elle est "
                  "muette, et n'apparaît pas ici.",
            "en": "The {n} athletics venues declared freely accessible{dep}. A venue "
                  "silent on access is not a closed venue: it is silent, and does not "
                  "appear here."},
           [t for t in sites if t.get("acces_libre")], "free-access")

    # --- disciplines, sur les agres declares seulement
    for agres in ORDRE_AGRES:
        param = AGRES_PARAM.get(agres)
        if not param:
            continue
        ajoute(agres, param.replace("_", "-"),
               {"fr": f"Pistes d'athlétisme avec {AGRES['fr'][agres].lower()}{{dep}}",
                "en": f"Athletics venues with {AGRES['en'][agres].lower()}{{dep}}"},
               {"fr": f"Les {{n}} installations dont le recensement déclare "
                      f"« {AGRES['fr'][agres]} »{{dep}} : piste, revêtement, accès.",
                "en": f"The {{n}} venues recorded with « {AGRES['en'][agres]} »{{dep}}: "
                      f"track, surface, access."},
               [t for t in sites if agres in (t.get("agres") or [])],
               f"discipline/{param}")

    # --- revetements
    for sol in SURFACE_EN:
        ajoute(sol, SURFACE_EN[sol],
               {"fr": f"Pistes d'athlétisme en {SOL['fr'][sol].lower()}{{dep}}",
                "en": f"{SOL['en'][sol]} athletics tracks{{dep}}"},
               {"fr": f"Les {{n}} pistes d'athlétisme dont le revêtement déclaré est "
                      f"« {SOL['fr'][sol]} »{{dep}} : développement, couloirs, agrès, accès.",
                "en": f"The {{n}} athletics tracks recorded with a « {SOL['en'][sol]} » "
                      f"surface{{dep}}: lap length, lanes, equipment, access."},
               [t for t in sites if t.get("surface") == sol],
               f"surface/{SURFACE_EN[sol]}")
    return out


def suffixe_lieu(lang, nom):
    if not nom:
        return {"fr": " en France", "en": " in France"}[lang]
    return (f" en {nom}" if lang == "fr" else f" in {nom}, France")


def item_ld(s, lang, url_base, nom_dep=None):
    """Une installation, telle qu'elle apparait dans un ItemList.

    La page porte le lieu lui-meme, pas seulement son lien : un agent qui lit
    la liste y trouve deja commune, coordonnees et revetement, sans ouvrir
    chaque fiche."""
    lieu = {"@type": "SportsActivityLocation",
            "@id": f"{url_base}/{url_site(lang, s['id'])}#place",
            "name": nom_de(s, lang), "url": f"{url_base}/{url_site(lang, s['id'])}",
            "sport": "Athletics", "identifier": s["id"]}
    if s.get("ville"):
        lieu["address"] = {"@type": "PostalAddress", "addressLocality": s["ville"],
                           "addressRegion": nom_dep or s.get("dep_nom") or "",
                           "addressCountry": "FR"}
    if s.get("lat") is not None and s.get("lon") is not None:
        lieu["geo"] = {"@type": "GeoCoordinates", "latitude": s["lat"], "longitude": s["lon"]}
    if s.get("surface"):
        lieu["additionalProperty"] = [{"@type": "PropertyValue",
                                       "name": T[lang]["kv"]["revetement"],
                                       "value": SOL[lang].get(s["surface"], s["surface"])}]
    return lieu


def resume_liste(s, lang):
    """La ligne de details sous le nom, dans une liste."""
    details = []
    tour, sur = tour_de_piste(s)
    if tour:
        details.append(f"{tour} m" if sur else f"{tour} m ?")
    if s.get("surface"):
        details.append(SOL[lang].get(s["surface"], s["surface"]))
    if s.get("couloirs"):
        details.append(f"{s['couloirs']} couloirs" if lang == "fr"
                       else f"{s['couloirs']} lanes")
    details += [AGRES[lang][a] for a in tri_agres(s["agres"]) if a in AGRES[lang]]
    return details


def liste_html(sites, lang, r, groupee=True):
    """Les sites, groupes par commune, comme sur la page de departement."""
    lignes, ville_courante = [], None
    for s in sites:
        if groupee and s.get("ville") != ville_courante:
            if ville_courante is not None:
                lignes.append("</ul>")
            ville_courante = s.get("ville")
            lignes.append(f'<h2 class="ville">{E(ville_courante or "")}</h2><ul class="liste">')
        elif not groupee and ville_courante is None:
            ville_courante = True
            lignes.append('<ul class="liste">')
        details = resume_liste(s, lang)
        if not groupee and s.get("ville"):
            details.insert(0, s["ville"])
        meta = f'<span class="meta">{E(" · ".join(details))}</span>' if details else ""
        lignes.append(f'<li><a href="{r}{url_site(lang, s["id"])}">'
                      f'{E(nom_de(s, lang))}{meta}</a></li>')
    if ville_courante is not None:
        lignes.append("</ul>")
    return "".join(lignes)


def bloc_api(lang, url_base, chemin_api, r):
    """Le pont entre la page et l'API : la meme selection, en JSON."""
    tr = T[lang]
    return (f'<section class="lede"><h2>{E(tr["crit_api"])}</h2>'
            f'<p>{E(tr["crit_api_texte"])}</p>'
            f'<p><code><a href="{url_base}/api/tracks/{chemin_api}.json">'
            f'/api/tracks/{E(chemin_api)}.json</a></code> · '
            f'<a href="{url_base}/openapi.json">openapi.json</a> · '
            f'<a href="{r}llms.txt">llms.txt</a></p></section>')


def page_critere(crit, lang, dep, sites, repartition, url_base, depot):
    """Page d'un critere, nationale (`dep` None) ou dans un departement.

    La page nationale est un carrefour : elle ne deroule pas 1 584 sites, elle
    repartit vers les departements. La page departementale porte la liste.
    C'est ce qui evite a la fois la page interminable et la page maigre."""
    cle = crit["slug"][lang]
    code, nom_dep = (dep if dep else (None, None))
    dep_slug = repartition["slug_dep"].get(code) if code else None
    chemin = url_critere(lang, cle, dep_slug)
    r = rel(chemin)
    tr = T[lang]
    suffixe = suffixe_lieu(lang, nom_dep)
    titre = crit["titre"][lang].format(dep=suffixe)
    desc = crit["desc"][lang].format(n=len(sites), dep=suffixe)
    autre_slug = crit["slug"][tr["autre"]]
    alternatives = {}
    for l in T:
        sl = crit["slug"][l]
        alternatives[l] = url_critere(l, sl, dep_slug)

    liste_ld = {
        "@context": "https://schema.org", "@type": "ItemList",
        "name": titre, "numberOfItems": len(sites),
        "itemListOrder": "https://schema.org/ItemListUnordered",
        "itemListElement": [{"@type": "ListItem", "position": i + 1,
                             "item": item_ld(s, lang, url_base, nom_dep)}
                            for i, s in enumerate(sites[:200])],
    }
    fil_items = [{"@type": "ListItem", "position": 1, "name": tr["accueil"],
                  "item": f"{url_base}/{url_appli(lang)}"}]
    if dep:
        fil_items.append({"@type": "ListItem", "position": 2,
                          "name": crit["titre"][lang].format(dep=suffixe_lieu(lang, None)),
                          "item": f"{url_base}/{url_critere(lang, cle)}"})
    fil_items.append({"@type": "ListItem", "position": len(fil_items) + 1,
                      "name": titre, "item": f"{url_base}/{chemin}"})
    fil = {"@context": "https://schema.org", "@type": "BreadcrumbList",
           "itemListElement": fil_items}

    lignes = [entete(lang, titre, desc, chemin, alternatives, [liste_ld, fil], url_base)]
    fil_html = f'<a href="{r}{url_appli(lang)}">{E(tr["accueil"])}</a> ›'
    if dep:
        fil_html += (f' <a href="{r}{url_critere(lang, cle)}">'
                     f'{E(crit["titre"][lang].format(dep=""))}</a> › {E(nom_dep or code)}')
    else:
        fil_html += f' {E(crit["titre"][lang].format(dep=""))}'
    lignes.append(f'''
<nav class="crumb">{fil_html}</nav>
<h1>{E(titre)}</h1>
<p class="loc">{E(tr["nb_sites"](len(sites)))}</p>
<p class="lede">{E(desc)}</p>''')

    if dep:
        lignes.append(liste_html(sites, lang, r))
        lignes.append(f'<p><a href="{r}{url_dep(lang, code)}">'
                      f'{E(tr["dep_titre"].format(dep=nom_dep or code))}</a></p>')
    else:
        # carrefour : les departements ou le critere existe, du plus fourni au
        # moins fourni. Un departement sans page dediee pointe vers sa liste.
        lignes.append(f'<h2>{E(tr["crit_partout"])}</h2><ul class="liste cols">')
        for code_d, n in repartition["par_dep"]:
            nom = repartition["nom_dep"].get(code_d) or code_d
            sl = repartition["slug_dep"].get(code_d)
            cible = (url_critere(lang, cle, sl) if n >= MIN_INTERSECTION and sl
                     else url_dep(lang, code_d))
            lignes.append(f'<li><a href="{r}{cible}">{E(nom)}'
                          f'<span class="meta">{E(tr["crit_dep_lien"](n))}</span></a></li>')
        lignes.append("</ul>")

    chemin_api = crit["api"] + (f"/{code}" if dep else "")
    lignes.append(bloc_api(lang, url_base, chemin_api, r))
    lignes.append(pied(lang, chemin, url_base, depot))
    return "".join(lignes)


def page_ville(ville, ville_slug, sites, autour, lang, url_base, depot):
    """Page d'une commune.

    2 604 des 3 847 communes du recensement n'ont qu'une installation. Une page
    qui se contenterait de la relister serait un doublon de la fiche. Elle
    porte donc aussi ce qu'il y a autour, dans RAYON_VILLE_KM : c'est ce qu'on
    veut vraiment savoir quand on cherche ou s'entrainer dans une commune qui
    n'a qu'un stade."""
    chemin = url_ville(lang, ville_slug)
    r = rel(chemin)
    tr = T[lang]
    titre = tr["ville_titre"](ville)
    desc = tr["ville_desc"](ville, len(sites))
    alternatives = {l: url_ville(l, ville_slug) for l in T}
    nom_dep = sites[0].get("dep_nom")

    liste_ld = {
        "@context": "https://schema.org", "@type": "ItemList",
        "name": titre, "numberOfItems": len(sites),
        "itemListOrder": "https://schema.org/ItemListUnordered",
        "itemListElement": [{"@type": "ListItem", "position": i + 1,
                             "item": item_ld(s, lang, url_base, nom_dep)}
                            for i, s in enumerate(sites)],
    }
    fil = {"@context": "https://schema.org", "@type": "BreadcrumbList",
           "itemListElement": [
               {"@type": "ListItem", "position": 1, "name": tr["accueil"],
                "item": f"{url_base}/{url_appli(lang)}"},
               {"@type": "ListItem", "position": 2, "name": nom_dep or "",
                "item": f"{url_base}/{url_dep(lang, sites[0].get('dep') or '00')}"},
               {"@type": "ListItem", "position": 3, "name": titre,
                "item": f"{url_base}/{chemin}"}]}

    lignes = [entete(lang, titre, desc, chemin, alternatives, [liste_ld, fil], url_base)]
    lignes.append(f'''
<nav class="crumb"><a href="{r}{url_appli(lang)}">{E(tr["accueil"])}</a> ›
  <a href="{r}{url_dep(lang, sites[0].get("dep") or "00")}">{E(nom_dep or "")}</a> ›
  {E(ville)}</nav>
<h1>{E(titre)}</h1>
<p class="loc">{E(nom_dep or "")} · {E(tr["nb_sites"](len(sites)))}</p>''')
    # Sur Paris, Lyon ou Marseille, la liste regroupe par arrondissement : 79
    # entrees a plat ne se lisent pas. Ailleurs, la commune est unique.
    par_arrondissement = len({s.get("ville") for s in sites}) > 1
    lignes.append(liste_html(sites, lang, r, groupee=par_arrondissement))

    lignes.append(f'<h2>{E(tr["ville_autour"])}</h2>')
    if autour:
        lignes.append('<ul class="liste">')
        for s, d in autour:
            details = [s.get("ville") or "", tr["a_km"](round(d))] + resume_liste(s, lang)
            lignes.append(f'<li><a href="{r}{url_site(lang, s["id"])}">'
                          f'{E(nom_de(s, lang))}'
                          f'<span class="meta">{E(" · ".join(x for x in details if x))}</span>'
                          f'</a></li>')
        lignes.append("</ul>")
    else:
        lignes.append(f'<p>{E(tr["ville_autour_vide"])}</p>')

    dep = sites[0].get("dep") or "00"
    lignes.append(bloc_api(lang, url_base, f"city/{dep}/{ville_slug_nu(ville_slug, dep)}", r))
    lignes.append(pied(lang, chemin, url_base, depot))
    return "".join(lignes)


def ville_slug_nu(ville_slug, dep):
    """Le slug de commune sans son suffixe de departement.

    Les 23 slugs partages entre plusieurs departements — Valence est dans la
    Drome et dans le Tarn-et-Garonne — portent leur code en suffixe dans l'URL
    de la page. La facette d'API, elle, est deja rangee par departement et n'en
    a pas besoin."""
    return ville_slug[:-(len(dep) + 1)] if ville_slug.endswith(f"-{dep}") else ville_slug


def sitemap(urls, url_base, maj):
    """Plan de site, extension images comprise.

    Une photo de terrain n'est atteignable qu'en suivant un lien depuis la
    fiche du site ; l'extension `image:` de sitemaps.org la declare
    directement, avec sa legende. C'est le moyen le plus direct de faire
    indexer par Google Images des photos qu'aucun lien externe ne pointe."""
    lignes = []
    for entree in urls:
        u, prio = entree[0], entree[1]
        images = entree[2] if len(entree) > 2 else ()
        blocs = "".join(
            f"<image:image><image:loc>{E(i['loc'])}</image:loc>"
            f"<image:title>{E(i['titre'])}</image:title>"
            f"<image:caption>{E(i['legende'])}</image:caption></image:image>"
            for i in images)
        lignes.append(f"  <url><loc>{url_base}/{u}</loc><lastmod>{maj}</lastmod>"
                      f"<changefreq>monthly</changefreq><priority>{prio}</priority>"
                      f"{blocs}</url>\n")
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"\n'
            '        xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">\n'
            f"{''.join(lignes)}</urlset>\n")


def sitemap_index(fichiers, url_base, maj):
    corps = "".join(f"  <sitemap><loc>{url_base}/{f}</loc><lastmod>{maj}</lastmod></sitemap>\n"
                    for f in fichiers)
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            f"{corps}</sitemapindex>\n")


def page_404(url_base, total):
    """Page servie par GitHub Pages pour toute URL inconnue.

    Sans elle, une fiche renommee ou un lien mal recopie tombe sur la page
    d'erreur nue de GitHub : ni marque, ni chemin de retour, et un robot qui
    n'y trouve aucun lien arrete de parcourir cette branche du site. Les URL
    y sont absolues, parce que le fichier est servi tel quel sous n'importe
    quel chemin, aussi profond soit-il."""
    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Page introuvable — Où s'entraîner ?</title>
<meta name="robots" content="noindex, follow">
<meta name="theme-color" content="#0f172a">
<link rel="icon" href="{url_base}/assets/icon.svg" type="image/svg+xml">
<link rel="stylesheet" href="{url_base}/assets/page.css?v=13">
<link rel="preconnect" href="https://cdn.matomo.cloud">
<link rel="preconnect" href="https://ronanchardonneau.matomo.cloud">
<script src="{url_base}/assets/matomo.js?v=3" defer></script>
</head>
<body>
<header class="page-bar">
  <a class="home" href="{url_base}/">
    <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 17c3.5-8 7-11 11-11 3 0 5 1.6 6 4" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"/><path d="M7 21c3-7 6-9.5 9.5-9.5" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" opacity=".5"/></svg>
    Où s'entraîner ?</a>
</header>
<main class="wrap">
<h1>Cette page n'existe pas</h1>
<p class="lede">L'adresse demandée ne correspond à aucune installation du site. Une fiche a pu
changer d'identifiant, ou le lien être incomplet. <span lang="en">This page does not exist.</span></p>
<h2>Où aller</h2>
<ul class="liste">
  <li><a href="{url_base}/">Chercher une piste sur la carte<span class="meta">{total} installations, recherche par ville ou code postal</span></a></li>
  <li><a href="{url_base}/departements/">Annuaire par département<span class="meta">Toutes les installations, département par département</span></a></li>
  <li><a href="{url_base}/en/" hreflang="en" lang="en">Read this site in English<span class="meta">Same directory, English pages</span></a></li>
</ul>
<p class="src">Un lien du site vous a mené ici&nbsp;?
<a href="https://github.com/Chardonneaur/pistes-athle/issues/new?template=correction.yml" rel="nofollow noopener">Signalez-le</a>.</p>
</main>
</body>
</html>
"""


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
            f"# Contrat de l'API, OpenAPI 3.1 : {url_base}/openapi.json\n"
            f"# Jeu de données complet : {url_base}/data/tracks.json\n\n"
            f"{blocs}\n\nSitemap: {url_base}/sitemap.xml\n")


def llms_txt(url_base, total, avec_piste, deps, maj, depot, api_url=None, axes=()):
    """Convention llms.txt : une page d'orientation pour les agents.

    `api_url` est le serveur de recherche, s'il tourne. Sans lui, on dit que la
    chaine de requete est inerte ici ; avec lui, on donne l'URL. Un llms.txt qui
    tairait le serveur de recherche laisserait l'agent composer a la main des
    conjonctions qu'une seule requete resout."""
    if api_url:
        interroger = f"""- **Recherche à paramètres combinables** : `{api_url}/api/tracks`.
  Tous les critères se combinent en conjonction (ET), et la recherche par rayon accepte des
  coordonnées quelconques — ce qu'aucun fichier pré-calculé ne peut offrir. Exemple :
  `{api_url}/api/tracks?lat=47.21&lon=-1.55&radius=20&free_access=true`
  / Combinable query parameters, including radius search around arbitrary coordinates.
- Ce miroir-ci est **statique** : la chaîne de requête y est ignorée par l'hébergeur. Les facettes
  ci-dessus et le serveur de recherche répondent aux mêmes questions — l'un fichier par fichier,
  l'autre en un appel. / This mirror is static; the search server above takes parameters."""
    else:
        interroger = """- Ce site est **statique** : l'hébergeur ignore la chaîne de requête, donc `api/tracks?city=Nantes`
  ne filtre rien. Utilisez les facettes, ou téléchargez `api/index.json`. Le document de capacités
  indique si un serveur de recherche à paramètres est déployé.
  / This host is static: query strings are ignored by the host. Use the facets, or download the
  index and filter locally."""
    # Les slugs de critere, en toutes lettres : c'est la liste que l'agent
    # doit lire au lieu de la deduire. Voir la section « Pages de recherche ».
    slugs_fr = ", ".join(f"`{c['slug']['fr']}`" for c in axes) or "(aucun)"
    slugs_en = ", ".join(f"`{c['slug']['en']}`" for c in axes) or "(none)"
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
- Les deux pages d'accueil portent une FAQ (accès libre, longueur d'un tour de piste,
  revêtements, provenance des données), balisée en JSON-LD `FAQPage`.
  / Both home pages carry a JSON-LD `FAQPage` covering access, lap length, surfaces and sourcing.
- [Annuaire par département]({url_base}/departements/) — les {len(deps)} départements.
- [Directory by department]({url_base}/en/departments/) — English version.
- [Confidentialité]({url_base}/confidentialite/) / [Privacy]({url_base}/en/privacy/) — ce que le
  site mesure (Matomo sans cookie), ce que le journal des robots enregistre, et les serveurs
  tiers que la page appelle. / what the site measures, what the crawler log records, and which
  third-party servers the page calls.
- Une page par installation / one page per venue:
  `{url_base}/site/<ID>/` (fr) et `{url_base}/en/track/<ID>/` (en), où `<ID>` est
  l'identifiant national de l'installation (champ `i` du JSON, ex. `I441310030`).
- Une page par département / one page per department:
  `{url_base}/departement/<CODE>/` (fr) et `{url_base}/en/department/<CODE>/` (en),
  où `<CODE>` est le code INSEE du département (ex. `44`, `2A`, `971`).
- Chaque page site porte un balisage JSON-LD `SportsActivityLocation` avec adresse, coordonnées,
  agrès, accès et avis. / Every venue page embeds JSON-LD.

## Interroger l'annuaire / Querying the directory

- [openapi.json]({url_base}/openapi.json) : le contrat complet, en OpenAPI 3.1 — paramètres de
  recherche, schéma des réponses, vocabulaires. / The full contract, OpenAPI 3.1.
- [api/tracks.json]({url_base}/api/tracks.json) : document de capacités. Il dit ce que cet hôte
  sait faire et quelles URL appeler. **À lire en premier.** / Capability document; read this first.
- [api/index.json]({url_base}/api/index.json) : les {fr_total} installations réduites aux champs
  filtrables, en un fichier (~1 Mo). De quoi faire soi-même n'importe quelle conjonction de
  critères. / The whole directory reduced to its filterable fields, in one file.
- Facettes pré-calculées, un fichier JSON par critère / pre-computed facets, one JSON file each:
  `api/tracks/<ID>.json` · `api/tracks/department/<CODE>.json` · `api/tracks/city/<DEP>/<SLUG>.json` ·
  `api/tracks/discipline/<DISCIPLINE>.json` (et `/<DEP>.json`) · `api/tracks/length/<METRES>.json` ·
  `api/tracks/surface/<REVETEMENT>.json` · `api/tracks/lanes/<N>.json` ·
  `api/tracks/free-access.json` · `api/tracks/reviewed.json` ·
  `api/geo/<LAT>/<LON>.json` (cellule de 0,1 degré).
{interroger}
- Deux règles de lecture / two reading rules: `acces_libre` vaut `true` ou `null`, **jamais**
  `false` — un blanc n'est pas un refus ; et les disciplines filtrent sur les agrès **déclarés**,
  ceux qu'un contributeur a déduits d'une orthophoto étant rendus à part.
  / `acces_libre` is never `false`, only `true` or `null`; discipline filters use declared
  equipment only.
- `nb_avis` fait exception : zéro y est un fait, pas un blanc. Cette base sait si quelqu'un a
  décrit un site, donc `has_reviews=false` est légitime là où `free_access=false` ne l'est pas.
  Les {fr_total} moins les 5 décrites forment la file d'attente de la contribution — croisez-la
  avec une commune ou un département pour savoir où aller voir.
  / `nb_avis` is the exception: zero is a fact, so `has_reviews=false` is meaningful.

## Pages de recherche / Search pages

- Par commune / by town: `{url_base}/ville/<SLUG>/` et `{url_base}/en/city/<SLUG>/`.
  Paris, Lyon et Marseille regroupent leurs arrondissements, que Data ES sépare.
  / Paris, Lyon and Marseille aggregate their arrondissements.
- Par critère / by criterion: `{url_base}/pistes/<CRITERE>/` et `{url_base}/en/tracks/<CRITERION>/`.
  La liste des critères est close : les voici tous, plutôt que des exemples. Une adresse
  déduite au lieu d'être lue ici mène à une 404 — vu le 25/08/2026, un agent a demandé
  `/criteres/piste-400m/`, qui n'a jamais existé, pour `/pistes/400m/`.
  / The list of criteria is closed; here it is in full rather than by example. A guessed
  address leads to a 404.
  fr: {slugs_fr}
  en: {slugs_en}
- Croisement avec un département / crossed with a department:
  `{url_base}/pistes/<CRITERE>/<DEPARTEMENT>/`. Seules les intersections comptant au moins trois
  installations existent : une page qui répéterait une seule fiche n'apporterait rien.
  / Only intersections with at least three venues are generated.
- Chaque page de recherche porte le lien vers la facette d'API qui rend la même sélection en JSON.
  / Every search page links to the API facet returning the same selection.

## Photos de terrain / Field photos

- Les photos sont prises sur place par des contributeurs, jamais générées ni reprises ailleurs.
  Elles vivent sous `{url_base}/data/photos/<ID>/`, nommées d'après leur sujet, le stade et la
  commune. / Photos are taken on site by contributors; filenames describe subject, venue and town.
- Chaque photo est déclarée en JSON-LD `ImageObject` sur la page de son site, avec sa légende,
  son auteur, ses dimensions et le lieu photographié, et listée dans le plan de site
  ([sitemap.xml]({url_base}/sitemap.xml)) via l'extension `image:`.
  / Each photo is described as an `ImageObject` and declared in the image sitemap.
- Licence des photos : [ODbL 1.0](https://opendatacommons.org/licenses/odbl/1-0/), avec le crédit
  de leur auteur — distincte de la Licence Ouverte qui couvre les données.
  / Photos are ODbL 1.0 with author credit, unlike the data itself.
- Une installation sans photo affiche à la place une orthophoto IGN (BD ORTHO®, Licence Ouverte
  2.0), datée de son millésime : elle montre l'implantation, pas l'état des agrès.
  / Venues without a photo show a dated IGN aerial view instead.

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
        fr, en = coquilles(f.read(), url_base, maj)
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

    par_id = {t["id"]: t for t in publiables}

    # --- axes de recherche : criteres, communes, et l'API qui rend les memes
    # selections en JSON. On part de la donnee : rien n'est genere a vide.
    noms_dep = {code: (liste[0].get("dep_nom") or code) for code, liste in par_dep.items()}
    slug_dep = {}
    for code, nom in noms_dep.items():
        sl = slug(nom) or code
        # Deux departements de meme slug s'ecraseraient l'un l'autre. Le code
        # INSEE tranche, et il est stable.
        if sl in slug_dep.values():
            sl = f"{sl}-{code}"
        slug_dep[code] = sl

    axes = criteres(publiables)
    for crit in axes:
        compte = {}
        for t in crit["sites"]:
            compte[t.get("dep") or "00"] = compte.get(t.get("dep") or "00", 0) + 1
        crit["repartition"] = {
            "par_dep": sorted(compte.items(), key=lambda kv: (-kv[1], noms_dep.get(kv[0], ""))),
            "nom_dep": noms_dep, "slug_dep": slug_dep}

    # Communes. 23 slugs sont partages par plusieurs departements — Valence est
    # dans la Drome et dans le Tarn-et-Garonne : on suffixe par le code.
    brut_villes = {}
    for t in publiables:
        sl = slug(t.get("ville") or "")
        if sl:
            brut_villes.setdefault(sl, {}).setdefault(t.get("dep") or "00", []).append(t)

    # Paris, Lyon et Marseille n'existent pas dans Data ES : le recensement ne
    # connait que « Lyon 3e Arrondissement ». Sans regroupement, la requete la
    # plus frequente du pays — « piste d'athletisme a Lyon » — ne tombe sur
    # aucune page. On ajoute donc la commune entiere, sans retirer les
    # arrondissements, qui restent la bonne reponse pour qui cherche precis.
    for ville_mere, code in (("Paris", "75"), ("Lyon", "69"), ("Marseille", "13")):
        tout = [t for t in publiables
                if (t.get("dep") or "") == code
                and ARRONDISSEMENT.match(t.get("ville") or "")
                and ARRONDISSEMENT.match(t["ville"]).group(1) == ville_mere]
        if tout:
            brut_villes.setdefault(slug(ville_mere), {})[code] = tout

    communes = []
    for sl, par_code in brut_villes.items():
        for code, liste in par_code.items():
            final = sl if len(par_code) == 1 else f"{sl}-{code}"
            liste.sort(key=lambda s: ((s.get("ville") or "").lower(),
                                      (s.get("nom") or "").lower()))
            mere = ARRONDISSEMENT.match(liste[0].get("ville") or "")
            nom = (mere.group(1) if mere and slug(mere.group(1)) == sl
                   else liste[0].get("ville") or sl)
            communes.append((final, nom, liste))

    # La page de commune de chaque site, pour que la fiche et la page du
    # departement puissent y renvoyer. Un site de Lyon appartient a deux pages :
    # son arrondissement et la commune mere. On garde la plus precise, celle
    # dont le slug est bien celui de la commune du recensement.
    ville_de_site = {}
    for final, _nom, liste in communes:
        for s in liste:
            sl = slug(s.get("ville") or "")
            precis = final in (sl, f"{sl}-{s.get('dep') or '00'}")
            if precis or s["id"] not in ville_de_site:
                ville_de_site[s["id"]] = final

    # Ce qu'il y a autour de chaque commune : grille grossiere puis distance
    # exacte, pour ne pas comparer 3 847 communes a 7 135 sites.
    grille = {}
    for t in publiables:
        grille.setdefault((round(t["lat"] / 0.25), round(t["lon"] / 0.25)), []).append(t)
    voisinage = {}
    for final, ville, liste in communes:
        lat = sum(s["lat"] for s in liste) / len(liste)
        lon = sum(s["lon"] for s in liste) / len(liste)
        ici = {s["id"] for s in liste}
        proches = []
        gy, gx = round(lat / 0.25), round(lon / 0.25)
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                for s in grille.get((gy + dy, gx + dx), ()):
                    if s["id"] in ici:
                        continue
                    d = distance(lat, lon, s["lat"], s["lon"])
                    if d <= RAYON_VILLE_KM:
                        proches.append((s, d))
        proches.sort(key=lambda p: p[1])
        voisinage[final] = proches[:MAX_AUTOUR]


    # --- generation
    urls = {"fr": [], "en": []}
    for lang in T:
        urls[lang].append((url_appli(lang), "1.0"))
        urls[lang].append((url_index(lang), "0.8"))
        urls[lang].append((url_contrib(lang), "0.7"))
        urls[lang].append((url_prive(lang), "0.3"))
        ecrire(os.path.join(out, url_prive(lang), "index.html"),
               page_confidentialite(lang, url_base, depot, maj))
        ecrire(os.path.join(out, url_contrib(lang), "index.html"),
               page_contributeurs(brut.get("communaute") or {}, par_id, lang,
                                  url_base, depot, maj))
        ecrire(os.path.join(out, url_index(lang), "index.html"),
               page_index(deps_tries, len(publiables), lang, url_base, depot, axes))
        for code, liste in par_dep.items():
            nom_dep = liste[0].get("dep_nom") or code
            region = liste[0].get("region") or ""
            ecrire(os.path.join(out, url_dep(lang, code), "index.html"),
                   page_departement(code, nom_dep, region, liste, lang, url_base, depot,
                                    ville_de_site))
            urls[lang].append((url_dep(lang, code), "0.7"))
        for crit in axes:
            cle = crit["slug"][lang]
            rep = crit["repartition"]
            crit["sites"].sort(key=lambda s: ((s.get("ville") or "").lower(),
                                              (s.get("nom") or "").lower()))
            ecrire(os.path.join(out, url_critere(lang, cle), "index.html"),
                   page_critere(crit, lang, None, crit["sites"], rep, url_base, depot))
            urls[lang].append((url_critere(lang, cle), "0.6"))
            for code, n in rep["par_dep"]:
                if n < MIN_INTERSECTION:
                    continue
                dedans = [s for s in crit["sites"] if (s.get("dep") or "00") == code]
                chemin = url_critere(lang, cle, rep["slug_dep"][code])
                ecrire(os.path.join(out, chemin, "index.html"),
                       page_critere(crit, lang, (code, noms_dep.get(code, code)),
                                    dedans, rep, url_base, depot))
                urls[lang].append((chemin, "0.5"))
        for final, ville, liste in communes:
            ecrire(os.path.join(out, url_ville(lang, final), "index.html"),
                   page_ville(ville, final, liste, voisinage[final], lang, url_base, depot))
            urls[lang].append((url_ville(lang, final), "0.6"))
        for t in publiables:
            ecrire(os.path.join(out, url_site(lang, t["id"]), "index.html"),
                   page_site(t, lang, voisins.get(t["id"], []), url_base, depot, maj,
                             ville_de_site.get(t["id"])))
            images = [{"loc": f"{url_base}/{p['f']}",
                       "titre": nom_de(t, lang),
                       "legende": alt_photo(p, t, lang)}
                      for p in (t.get("photos") or [])]
            urls[lang].append((url_site(lang, t["id"]), "0.6", images))


    # --- API statique, index compact et openapi.json
    stat_api = build_api.construire(out, publiables, deps, url_base, maj, depot,
                                    os.environ.get("API_URL"))
    # --- plan du site, robots, llms
    for lang in T:
        ecrire(os.path.join(out, f"sitemap-{lang}.xml"), sitemap(urls[lang], url_base, maj))
    ecrire(os.path.join(out, "sitemap.xml"),
           sitemap_index([f"sitemap-{l}.xml" for l in T], url_base, maj))
    domaine = domaine_personnalise(url_base)
    if domaine:
        ecrire(os.path.join(out, "CNAME"), domaine + "\n")
    ecrire(os.path.join(out, "robots.txt"), robots(url_base))
    ecrire(os.path.join(out, "404.html"), page_404(url_base, len(publiables)))
    avec_piste = sum(1 for t in publiables if t["piste"])
    ecrire(os.path.join(out, "llms.txt"),
           llms_txt(url_base, len(publiables), avec_piste, par_dep, maj, depot,
                    os.environ.get("API_URL"), axes))

    pages = sum(len(u) for u in urls.values())
    print(f"-> {out}")
    print(f"   {len(publiables)} sites x 2 langues, {len(par_dep)} departements, "
          f"{pages} URL au plan du site")
    print(f"   {len(axes)} criteres, {len(communes)} communes")
    print(f"   API : {stat_api['facettes']} facettes, {stat_api['cellules']} cellules geo, "
          f"openapi.json")
    print(f"   URL publique : {url_base}")


if __name__ == "__main__":
    main()
