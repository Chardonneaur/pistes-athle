#!/usr/bin/env python3
"""
Etage 2 de la boucle Search Console : monter le dossier, puis fermer la question.

Ce script est la moitie BETE de l'etage 2, comme releve_gsc.py est la moitie bete
de l'etage 1. Il ne juge rien, n'ecrit dans aucune fiche, n'ouvre aucune pull
request. Il fait deux choses, toutes deux mecaniques :

  1. rassembler devant l'agent tout ce que le site sait deja sur une question —
     la ligne de la file, la fiche visee, les champs renseignes, les champs
     vides, l'override existant ;
  2. ecrire le verdict dans la base une fois le travail fait.

Le jugement — lire une source, decider si elle est citable, ecrire la fiche,
ouvrir la PR — est fait par l'agent, guide par .claude/skills/traitement-gsc/.

POURQUOI SEPARER, ENCORE. Le montage du dossier est la partie ou l'on se trompe
sans s'en rendre compte : croire qu'une fiche n'a pas d'horaires alors qu'on a
regarde le mauvais identifiant, ou traiter deux fois la meme question. Ce sont
des erreurs de lecture, pas de jugement, et un script les evite toutes. Ce qu'il
reste a l'agent est alors le seul vrai travail : trouver une source, ou constater
qu'il n'y en a pas.

LA REGLE QUI PRIME. Un champ vide ne dit pas « non », il ne dit rien. Ce script
affiche donc « non renseigne » et jamais « absent » : la nuance est toute la
promesse du site, et c'est celle qu'on perd en premier quand on resume.

Usage :
  python3 scripts/dossier_gsc.py                       # la file, par priorite
  python3 scripts/dossier_gsc.py --dossier I591830081\\|fiche
  python3 scripts/dossier_gsc.py --fermer <cle> --statut traite --detail "..."
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from build_api import slug                    # noqa: E402  (meme slug que le site)
from releve_gsc import D1                     # noqa: E402  (un seul transport D1)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TRACKS = os.path.join(ROOT, "data", "tracks.json")
A_VERIFIER = os.path.join(ROOT, "data", "a-verifier.json")
OVERRIDES = os.path.join(ROOT, "data", "overrides")
SITE = "https://pistes-athle.com"

STATUTS = ("traite", "sans-source", "candidat", "hors-sujet")

# Ce que chaque famille de question reclame, en clair.
#
# La colonne de droite n'est pas « les champs a remplir » : c'est « les champs
# qu'il faut regarder avant de dire quoi que ce soit ». Une question sur l'acces
# peut se resoudre en constatant que horaires est deja rempli et que la fiche
# repond donc deja — auquel cas il n'y a rien a ecrire, et c'est un « traite »
# parfaitement legitime.
CHAMPS_ATTENDUS = {
    "revetement": ["surface"],
    "couvert":    ["couvert"],
    "acces":      ["acces_libre", "ouvert_public", "acces_note", "horaires", "scolaire"],
    "horaires":   ["horaires", "eclairage", "acces_note"],
    "tarif":      ["acces_note", "url"],
    "agres":      ["agres", "agres_probables", "nb_sautoirs", "nb_aires_lancer"],
    "distance":   ["longueur_piste", "longueur_probable", "couloirs"],
    "contact":    ["url", "proprietaire", "gestionnaire", "adresse"],
    "photos":     ["photos"],
    # « fiche » est le nom du stade tape tel quel : la personne ne pose pas une
    # question precise, elle veut la fiche. Le travail est donc de verifier que
    # la fiche entiere tient debout, d'ou la liste large.
    "fiche":      ["surface", "longueur_piste", "longueur_probable", "couloirs",
                   "agres", "acces_libre", "horaires", "photos", "note"],
    # « existence » ne vise aucun champ : il n'y a pas de fiche a corriger, il y
    # a peut-etre un lieu que le recensement ignore. Voir --dossier.
    "existence":  [],
}

# Le tarif n'existe nulle part dans le modele de donnees, et ce n'est pas un
# oubli : aucune source ouverte ne le porte, et il change tous les ans. Une
# question de tarif ne peut donc se fermer qu'en « sans-source », sauf si la
# page officielle de l'installation le publie — auquel cas c'est « url ».
SANS_CHAMP = {"tarif"}


# ---------------------------------------------------------------------------
# Les donnees du site
# ---------------------------------------------------------------------------

def charge_tracks():
    """tracks.json, avec les cles rendues a leur nom long.

    Le fichier publie est compresse par un keymap (« s » pour « surface ») pour
    tenir dans le poids d'une page. Le relire ici sous sa forme courte
    obligerait a traduire mentalement a chaque lecture, et c'est exactement la
    ou l'on se trompe de champ.
    """
    with open(TRACKS, encoding="utf-8") as f:
        d = json.load(f)
    km = d["keymap"]
    tracks = [{km.get(k, k): v for k, v in t.items()} for t in d["tracks"]]
    return d, tracks


def override_de(oid):
    chemin = os.path.join(OVERRIDES, f"{oid}.json")
    if not os.path.exists(chemin):
        return None, chemin
    with open(chemin, encoding="utf-8") as f:
        return json.load(f), chemin


# tracks.json encode les booleens en 1/0 pour gagner des octets, et omet le 0.
# Les afficher tels quels donnerait « acces_libre 1 », qu'il faut retraduire a
# chaque lecture — donc se tromper un jour sur deux.
BOOLEENS = {"piste", "couvert", "eclairage", "acces_libre", "ouvert_public",
            "vestiaires", "douches", "sanitaires", "scolaire", "supprime"}
COMPTES = {"photos", "avis", "agres", "agres_probables"}


def valeur_lisible(champ, v):
    if v is None or v == "" or v == [] or v == {}:
        return None
    if champ in BOOLEENS:
        return "oui" if v else "non"
    if champ in COMPTES and isinstance(v, list):
        if champ in ("agres", "agres_probables"):
            return ", ".join(str(x) for x in v)
        return f"{len(v)} enregistree(s)"
    if isinstance(v, list):
        return ", ".join(str(x) for x in v)
    return str(v)


# ---------------------------------------------------------------------------
# La file
# ---------------------------------------------------------------------------

def file_priorisee(db, tout=False, limite=15):
    """Les questions qui attendent, la plus payante d'abord.

    L'ordre n'est pas « la meilleure position d'abord », qui remonterait les
    fiches deja premieres — celles ou il n'y a rien a gagner. Le cas s'est
    presente des le premier lot : « stade de luminy » etait en position 1,0, et
    le dossier s'est ferme sur « rien a corriger ». C'est du travail depense
    pour rien.

    L'ordre retenu :
      1. « existence » d'abord, toujours. Une question sans fiche derriere est
         peut-etre une piste que le recensement ignore : c'est le seul cas ou la
         boucle peut faire grandir l'annuaire, et non seulement le corriger.
      2. puis ce qui est deja visible sans etre gagne — position au-dela du
         podium, la ou quelques lignes deplacent vraiment quelque chose.
      3. a position egale, le plus d'impressions.
    """
    lignes = db.sql(
        "SELECT cle, cible, intention, requete, variantes, page, impressions,"
        " position, vu_le, rouvert_le, detail FROM requetes_gsc WHERE statut='file'")

    def rang(r):
        pos = r["position"] if r["position"] is not None else 999.0
        return (0 if r["intention"] == "existence" else 1,
                0 if (tout or pos > 3) else 1,
                pos, -r["impressions"])

    return sorted(lignes, key=rang)[:limite]


def montre_file(db, tout, limite):
    lignes = file_priorisee(db, tout=tout, limite=limite)
    if not lignes:
        print("La file est vide : toutes les questions relevees sont fermees.")
        return
    reste = db.sql("SELECT COUNT(*) AS n FROM requetes_gsc WHERE statut='file'")
    print(f"{reste[0]['n']} questions en file. Les {len(lignes)} plus payantes :\n")
    for r in lignes:
        pos = f"{r['position']:5.1f}" if r["position"] is not None else "    ?"
        marque = "!" if r["intention"] == "existence" else " "
        # Une question rouverte n'est pas une question neuve : elle a deja ete
        # jugee sans source, et la relire sans le savoir revient a refaire la
        # meme recherche pour rien.
        if r.get("rouvert_le"):
            marque = "R"
        print(f" {marque} {r['impressions']:4} imp  pos {pos}  {r['cle']}")
        print(f"      « {r['requete'][:70]} »"
              + (f"  (+{r['variantes'] - 1} formulations)" if r["variantes"] > 1 else ""))
        if r.get("rouvert_le"):
            print(f"      rouverte le {r['rouvert_le']}, deja fermee une fois : "
                  f"{(r.get('detail') or '')[:80]}")
    print("\nLe dossier d'une question :"
          "\n  python3 scripts/dossier_gsc.py --dossier '<cle>'")


# ---------------------------------------------------------------------------
# Le dossier d'une question
# ---------------------------------------------------------------------------

def dossier(db, cle):
    lignes = db.sql("SELECT * FROM requetes_gsc WHERE cle = ?", [cle])
    if not lignes:
        sys.exit(f"Aucune question sous la cle « {cle} ».\n"
                 "Les cles se lisent avec : python3 scripts/dossier_gsc.py")
    r = lignes[0]
    _, tracks = charge_tracks()

    print("=" * 72)
    print(f"  {r['cle']}")
    print("=" * 72)
    print(f"formulation   « {r['requete']} »"
          + (f"  (+{r['variantes'] - 1} autres)" if r["variantes"] > 1 else ""))
    print(f"impressions   {r['impressions']}   position {r['position']}")
    print(f"vue du        {r['vu_le']}  au  {r['revu_le']}")
    print(f"statut        {r['statut']}" + (f"  : {r['detail']}" if r.get("detail") else ""))
    if r.get("rouvert_le"):
        print(f"reouverture   le {r['rouvert_le']}, parce que les impressions ont triple")
        print( "              depuis la fermeture. Le verdict ci-dessus est l'ancien :")
        print( "              ce qui a change est ce que la question vaut, pas la source")
        print( "              disponible. Chercher plus loin que la derniere fois, ou")
        print( "              refermer en disant ce qui a ete tente en plus.")
    if r.get("page"):
        print(f"atterrissage  {r['page']}")

    cible, intention = r["cible"], r["intention"]
    print(f"\n-- ce que la question vise -------------------------------------------")

    if cible == "inconnu":
        dossier_inconnu(r)
    elif cible.startswith("ville:"):
        dossier_ville(cible[6:], tracks, intention)
    elif cible.startswith("dep:"):
        dossier_dep(cible[4:], tracks, intention)
    elif cible.startswith("critere:"):
        print(f"Une page de critere : {SITE}/pistes/{cible[8:]}/")
        print("Elle est construite, pas redigee : elle liste les fiches qui portent")
        print("le critere. La corriger passe donc par les fiches qu'elle liste, ou")
        print("par l'absence de fiches qui devraient y figurer.")
    else:
        dossier_fiche(cible, tracks, intention)

    print(f"\n-- fermer le dossier -------------------------------------------------")
    print(f"python3 scripts/dossier_gsc.py --fermer '{cle}' \\")
    print(f"    --statut <{'|'.join(STATUTS)}> --detail \"...\"")


def dossier_fiche(oid, tracks, intention):
    t = next((x for x in tracks if x.get("id") == oid), None)
    if t is None:
        print(f"L'identifiant {oid} n'est dans aucune fiche de data/tracks.json.")
        print("La page a peut-etre ete supprimee, ou l'identifiant a change.")
        print("A verifier avant toute chose : une question sur une fiche disparue")
        print("se ferme en « hors-sujet », pas en « sans-source ».")
        return

    print(f"{t.get('nom', '(sans nom)')} — {t.get('ville', '?')} ({t.get('dep') or t.get('cp', '?')})")
    print(f"{SITE}/site/{oid}/")

    ov, chemin = override_de(oid)
    rel = os.path.relpath(chemin, ROOT)
    if ov is None:
        print(f"\nAucune contribution : {rel} n'existe pas encore.")
    else:
        print(f"\nContribution existante : {rel}")
        if ov.get("photos"):
            print(f"  {len(ov['photos'])} photo(s)")
        if ov.get("avis"):
            print(f"  {len(ov['avis'])} avis")

    attendus = CHAMPS_ATTENDUS.get(intention, [])
    if intention in SANS_CHAMP:
        print(f"\nL'intention « {intention} » ne vise aucun champ du modele :")
        print("le site ne porte pas cette donnee, et aucune source ouverte ne la")
        print("publie de facon stable. Sauf page officielle qui la donne, ce")
        print("dossier se ferme en « sans-source ».")

    if attendus:
        print(f"\nCe que « {intention} » demande, et ce que la fiche en dit :\n")
        for champ in attendus:
            v = valeur_lisible(champ, t.get(champ))
            source = ""
            if ov and champ in ov:
                source = "  [contribution]"
            if v is None:
                print(f"  {champ:20} non renseigne{source}")
            else:
                print(f"  {champ:20} {v[:80]}{source}")
        print("\n« non renseigne » ne veut pas dire « absent ». Le champ se tait :")
        print("il n'autorise a ecrire ni la presence ni l'absence de la chose.")

    autres = [c for c in ("surface", "longueur_piste", "longueur_probable",
                          "couloirs", "agres", "acces_libre", "horaires",
                          "photos", "note", "avis")
              if c not in attendus and valeur_lisible(c, t.get(c)) is not None]
    if autres:
        print(f"\nEgalement renseigne sur cette fiche : {', '.join(autres)}")


def dossier_ville(ville_slug, tracks, intention):
    sites = [t for t in tracks if slug(t.get("ville") or "") == ville_slug]
    print(f"La page commune : {SITE}/ville/{ville_slug}/")
    if not sites:
        print(f"Aucune fiche ne se rattache au slug « {ville_slug} ».")
        print("Soit la page a disparu, soit le slug vient d'une commune deleguee.")
        return
    print(f"{len(sites)} fiche(s) dans cette commune :\n")
    attendus = CHAMPS_ATTENDUS.get(intention, [])
    for t in sites:
        manques = [c for c in attendus if valeur_lisible(c, t.get(c)) is None]
        etat = f"manque {', '.join(manques)}" if manques else "champs attendus renseignes"
        print(f"  {t.get('id'):24} {(t.get('nom') or '')[:38]:40} {etat}")
    print("\nUne question posee a l'echelle de la commune se traite fiche par fiche :")
    print("c'est la fiche qui porte la donnee, la page commune ne fait que la lister.")


def dossier_dep(code, tracks, intention):
    sites = [t for t in tracks if (t.get("dep") or (t.get("cp") or "")[:2]) == code]
    print(f"La page departement : {SITE}/departement/{code}/")
    print(f"{len(sites)} fiche(s) dans le departement.")
    attendus = CHAMPS_ATTENDUS.get(intention, [])
    if attendus:
        for champ in attendus:
            n = sum(1 for t in sites if valeur_lisible(champ, t.get(champ)) is not None)
            print(f"  {champ:20} renseigne sur {n}/{len(sites)}")
    print("\nUne question departementale ne se corrige pas sur la page du")
    print("departement : elle se corrige sur les fiches qui lui manquent.")


def dossier_inconnu(r):
    """La question la plus precieuse, et celle qui se traite le plus lentement.

    Aucune page d'atterrissage identifiable : personne n'a trouve de fiche. Si
    la requete nomme un lieu, c'est peut-etre une piste absente du recensement.

    Ce n'est PAS une preuve d'existence, et rien ici ne doit finir dans
    tracks.json. Les gens cherchent des pistes fermees, demolies, ou situees
    dans la commune d'a cote. Le seul aboutissement possible est une ligne dans
    data/a-verifier.json, avec sa source — statut « candidat ».
    """
    print("Aucune fiche derriere cette question : Google n'a rattache la requete")
    print("a aucune page identifiable du site.")
    q = slug(r["requete"])
    mots = [m for m in q.split("-") if len(m) > 3]
    print(f"\nMots cherchables dans la requete : {', '.join(mots) or '(aucun)'}")

    if not os.path.exists(A_VERIFIER):
        print("\ndata/a-verifier.json est absent : lancer scripts/pistes_absentes.py.")
        return
    with open(A_VERIFIER, encoding="utf-8") as f:
        cands = json.load(f).get("candidats", [])
    trouves = [c for c in cands
               if any(m in slug(c.get("commune") or "") for m in mots)]
    print(f"\n{len(cands)} candidats OSM non verifies dans data/a-verifier.json.")
    if trouves:
        print(f"{len(trouves)} dont la commune contient un mot de la requete :\n")
        for c in trouves[:10]:
            print(f"  {c['osm']:16} {c.get('commune', '?'):28} "
                  f"dep {c.get('dep', '??')}  perimetre {c.get('perimetre', '?')} m")
            print(f"    {c['url']}")
    else:
        print("Aucun candidat OSM ne correspond aux mots de la requete.")
    print("\nRappel : une requete n'est pas une preuve d'existence. Rien ne part")
    print("dans tracks.json. Au mieux une ligne dans data/a-verifier.json avec sa")
    print("source, et le dossier se ferme en « candidat ».")


# ---------------------------------------------------------------------------
# Fermer
# ---------------------------------------------------------------------------

def fermer(db, cle, statut, detail, forcer=False):
    lignes = db.sql("SELECT statut, impressions, position FROM requetes_gsc"
                    " WHERE cle = ?", [cle])
    if not lignes:
        sys.exit(f"Aucune question sous la cle « {cle} ».")
    actuel = lignes[0]["statut"]
    if actuel != "file" and not forcer:
        sys.exit(f"« {cle} » est deja en « {actuel} », donc deja ferme.\n"
                 "Le gel des valeurs d'avant a eu lieu ce jour-la : rouvrir puis\n"
                 "refermer l'ecraserait. Utiliser --forcer si c'est bien voulu.")
    if not detail or not detail.strip():
        sys.exit("--detail est obligatoire : un dossier ferme sans raison ecrite\n"
                 "est un dossier qu'il faudra rouvrir pour comprendre.")

    db.sql("UPDATE requetes_gsc SET statut = ?, detail = ? WHERE cle = ?",
           [statut, detail.strip(), cle])

    # Relecture plutot qu'affichage de ce qu'on croit avoir ecrit : le gel est
    # pose par un declencheur, donc par la base et non par ce script. Le seul
    # moyen de savoir qu'il a bien eu lieu est de le relire.
    apres = db.sql("SELECT statut, traite_le, impressions_avant, position_avant"
                   " FROM requetes_gsc WHERE cle = ?", [cle])[0]
    print(f"« {cle} » -> {apres['statut']}")
    print(f"  {detail.strip()[:120]}")
    if apres["traite_le"]:
        print(f"  gel du {apres['traite_le']} : {apres['impressions_avant']} impressions,"
              f" position {apres['position_avant']}")
    else:
        print("  ATTENTION : aucun gel enregistre. Le declencheur gel_au_traitement"
              " manque-t-il ?\n  Reappliquer logs/schema-requetes.sql.")

    reste = db.sql("SELECT COUNT(*) AS n FROM requetes_gsc WHERE statut='file'")
    print(f"  file restante : {reste[0]['n']}")


# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dossier", metavar="CLE",
                    help="tout ce que le site sait deja sur cette question")
    ap.add_argument("--fermer", metavar="CLE", help="ecrire le verdict d'un dossier")
    ap.add_argument("--statut", choices=STATUTS, help="avec --fermer")
    ap.add_argument("--detail", help="avec --fermer : la raison, ou l'URL de la PR")
    ap.add_argument("--forcer", action="store_true",
                    help="refermer un dossier deja ferme, en ecrasant son gel")
    ap.add_argument("--tout", action="store_true",
                    help="ne pas ecarter les questions deja dans le podium")
    ap.add_argument("--limite", type=int, default=15)
    args = ap.parse_args()

    db = D1()

    if args.fermer:
        if not args.statut:
            ap.error("--fermer demande --statut")
        fermer(db, args.fermer, args.statut, args.detail, args.forcer)
    elif args.dossier:
        dossier(db, args.dossier)
    else:
        montre_file(db, args.tout, args.limite)


if __name__ == "__main__":
    main()
