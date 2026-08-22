---
name: contribution-piste
description: >
  Mène l'entretien complet qui transforme une visite de terrain en fiche riche pour
  « Où s'entraîner ? » : questions ordonnées par valeur SEO et agents IA, écriture du
  fichier data/overrides/<id>.json, validation, photos. Utiliser dès que quelqu'un dit
  qu'il a vu, visité, photographié ou mesuré une piste d'athlétisme, ou veut ajouter,
  corriger ou compléter une fiche, ses agrès, son revêtement ou ses conditions d'accès.
  Se déclenche aussi sur « contribution », « j'ai visité », « nouvelle piste »,
  « ajouter un stade », « compléter une fiche ».
---

# Entretien de contribution — une piste d'athlétisme

## Ce que cette compétence essaie de produire

Data ES décrit 7 134 installations avec les mêmes vingt champs. N'importe qui peut
republier ces vingt champs : c'est du contenu dupliqué, et il ne classe pas.

Ce qui n'existe nulle part ailleurs, c'est **ce que quelqu'un a vu sur place**. L'état
du tartan, le portail ouvert le dimanche, le sautoir dont la bâche est crevée, le fait
que les 400 m annoncés en font 380. Ce sont ces phrases qui rendent une fiche unique, et
ce sont elles qu'un moteur génératif cite parce qu'il ne peut les trouver ailleurs.

L'entretien sert donc deux choses à la fois :

1. **remplir les champs structurés**, qui partent en JSON-LD et dans l'API — c'est ce
   qui rend la fiche *trouvable* et *filtrable* ;
2. **récolter la prose de première main**, qui n'entre dans aucun champ — c'est ce qui
   rend la fiche *irremplaçable*.

Les deux comptent. Une fiche qui n'a que la première est indexable et interchangeable ;
une fiche qui n'a que la seconde est jolie et introuvable.

## La règle qui prime sur le reste

**On n'écrit que ce que quelqu'un a vu, mesuré ou lu dans une source publique.**

Un blanc n'est pas un « non ». Si la personne ne sait pas si le stade a des vestiaires,
le champ n'existe pas — on ne met pas `false`. C'est la règle du § 5.2 de
`docs/trouver-les-pistes-manquantes.md`, et toute l'architecture du site en dépend :
`acces_libre` ne vaut jamais `false` dans l'API, et une fiche qui affirmerait une absence
non constatée casserait cette promesse.

Quand une réponse est une déduction et non une observation, elle va dans `note` avec la
mention de sa source (« d'après l'orthophoto IGN 2025, non vérifié sur place »), jamais
dans un champ structuré.

Ne jamais inventer une réponse à la place de la personne, ne jamais compléter « au
vraisemblable », ne jamais deviner un revêtement d'après une couleur — § 4.6 de la même
doc explique pourquoi c'est le piège le plus fréquent.

## Comment mener l'entretien

Poser les questions **par blocs**, avec l'outil de questions à choix quand les réponses
sont fermées, en texte libre sinon. Ne pas dérouler les quarante questions d'un coup :
un bloc, sa réponse, le bloc suivant. Toujours accepter « je ne sais pas » et passer.

Annoncer au début combien de blocs il reste, et rappeler qu'on peut s'arrêter à tout
moment — une fiche partielle vaut mieux qu'un entretien abandonné.

### Bloc 0 — De quoi parle-t-on

- Est-ce une **installation déjà au recensement** (elle a une fiche, donc un identifiant
  du type `I441310030`, affiché sur sa page) ou une **piste absente** (elle prendra un
  identifiant `c-nom-commune`) ?
- Si absente : nom, commune, adresse ou lieu-dit, et **coordonnées** — indispensables.
  Les proposer d'après l'orthophoto ou OpenStreetMap et les faire confirmer.
- **Quand y êtes-vous allé ?** La date sert à dater l'avis et à savoir ce que l'on
  compare à l'orthophoto.

Vérifier immédiatement si la piste existe déjà, sous un autre nom ou à quelques
centaines de mètres : `python3 scripts/pistes_absentes.py <dep>` et une recherche dans
`data/tracks.json` sur la commune. Le § 4.2 et le § 4.3 de la doc racontent deux cas où
une « découverte » était une fiche existante mal placée. Une contribution en double coûte
plus cher qu'une contribution manquante.

### Bloc 1 — L'anneau

Ce bloc alimente `additionalProperty` en JSON-LD et les pages `/pistes/400m/`,
`/pistes/synthetique/`, `/pistes/6-couloirs/`.

- **Développement** : combien de mètres pour un tour, au couloir 1 ? Demander si c'est
  **mesuré** (décamètre, montre GPS, plaque sur place) ou **estimé**. Mesuré →
  `longueur_piste`. Estimé → `longueur_probable`, et dire dans `note` d'où vient
  l'estimation. Ne jamais promouvoir une estimation en mesure.
- **Couloirs** : combien, et sont-ils **tracés** ou seulement suggérés ? Renseigné sur
  112 fiches seulement : chaque réponse ici a une valeur disproportionnée, c'est le champ
  le plus rare de la base.
- **Revêtement** : `synthetique` (tartan), `bitume`, `cendree`, `sable`, `gazon`,
  `naturel`, `interieur`. **Demander ce qu'on a foulé, pas la couleur vue du ciel** :
  l'enrobé coloré est indiscernable du tartan sur une orthophoto.
- **État** : fissures, mousse, flaques, marquage effacé, herbe dans les virages ? Ça ne
  rentre dans aucun champ — c'est pour `note`, et c'est exactement ce que personne
  d'autre n'écrit.
- Y a-t-il une **ligne droite** distincte de l'anneau ? Sa longueur ?
- L'anneau est-il **couvert** ou en plein air ?

### Bloc 2 — Les agrès, un par un

`agres` part en `amenityFeature` et alimente `/pistes/perche/`, `/pistes/javelot/`…
Vocabulaire strict : `longueur`, `triple`, `hauteur`, `perche`, `poids`, `disque`,
`marteau`, `javelot`, `steeple`.

Pour chacun, demander **présent / absent / je ne sais pas**, puis, pour ceux qui sont
présents, l'état :

- sautoirs : le tapis est-il en place ou rentré ? La bâche est-elle percée ? La planche
  d'appel est-elle lisible ? Combien de planches ?
- perche : les poteaux sont-ils montés ? Le bac est-il dégagé ?
- lancers : la cage est-elle en état, le filet troué ? Le cercle est-il fissuré ?
- steeple : la rivière est-elle en eau, la barrière fixe ?

Un agrès **vu mais inutilisable** reste un agrès : il va dans `agres`, et son état va
dans `note`. C'est une nuance qu'aucune base publique ne porte, et c'est précisément la
question que se pose l'athlète qui cherche où s'entraîner.

Si la personne a vu une aire de saut ou de lancer sans savoir laquelle, ne rien mettre
dans `agres` — le champ `agres_probables` existe pour ça, mais il est réservé aux
déductions d'orthophoto ; sur place, mieux vaut redemander.

### Bloc 3 — L'accès, le champ le plus utile et le plus périssable

- **A-t-on pu entrer ?** Portail ouvert, grillage, code, badge, gardien ?
- Si oui : `acces_libre: true`. **Si on n'a pas essayé ou qu'on ne sait pas : on ne met
  rien.** Ne jamais écrire `acces_libre: false` pour dire « je ne sais pas ».
- Y a-t-il un **panneau d'horaires** ? Le recopier tel quel dans `horaires` — aucune
  donnée ouverte ne porte cette information, c'est un différenciateur pur.
- Des **créneaux réservés** (club, scolaires, compétition) affichés ? → `acces_note`.
- L'installation est-elle dans une **enceinte scolaire** ? (`scolaire`)
- Vestiaires, douches, sanitaires, éclairage, tribunes : **vus ouverts** ? Un vestiaire
  fermé à clé n'est pas un vestiaire absent — le dire dans `acces_note` plutôt que de
  trancher le booléen.

### Bloc 4 — Les photos

Chaque photo devient un `ImageObject` en JSON-LD et une entrée du sitemap images.

- Demander les fichiers. Viser **trois à six** : la ligne droite, un virage, le sautoir,
  l'aire de lancer, le panneau d'accès, l'entrée.
- Pour chacune : **que montre-t-elle exactement ?** La légende doit décrire ce qu'on
  voit, pas répéter le nom du stade. « Le virage nord, tartan fissuré près de la corde »
  vaut dix fois « Piste de Machecoul ».
- Crédit : le nom de l'auteur.
- Nommer les fichiers d'après **leur sujet seul** : `01-ligne-droite.jpg`,
  `02-sautoir-perche.jpg`. `optimize_photos.py` y ajoute le nom du stade et la commune,
  qu'il lit dans `data/tracks.json`.
- Les passer par le script — il redimensionne, compresse, retire l'EXIF (dont la
  position GPS de l'appareil) et écrit dans `data/photos/<id>/` :

  ```bash
  python3 scripts/optimize_photos.py <id> ~/photos/piste/*.jpg
  ```

  Pour une **piste nouvelle**, l'identifiant `c-…` n'existe pas encore dans
  `data/tracks.json` : le script prévient et nomme les fichiers sans le stade ni la
  commune. Écrire l'override et lancer `build_data.py --offline` **avant** d'optimiser
  les photos, sinon leurs noms perdent le seul signal que Google Images ait en plus de
  l'attribut `alt`.

### Bloc 5 — L'avis, le morceau qui rapporte le plus

`avis` produit un `Review` en JSON-LD, et une note produit un `aggregateRating` — ce sont
les étoiles qui peuvent apparaître dans les résultats de recherche.

- **Note sur 5**, si la personne veut en donner une.
- **Le texte** : 1 200 caractères maximum. Poser la question de l'usage, pas de la
  qualité : *pour qui cette piste est-elle bien, et pour qui ne l'est-elle pas ?* Un
  débutant, un club, une séance de fractionné, des enfants ? Y retournerait-on ?
- Faire parler de ce qui ne se photographie pas : le vent, l'ombre, le bruit, la
  fréquentation à telle heure, le parking, la fontaine, le revêtement après la pluie.
- Signature et date.

Ne pas rédiger l'avis à la place de la personne. Le reformuler pour la clarté, oui ;
inventer une impression qu'elle n'a pas eue, jamais — c'est un faux témoignage, et c'est
aussi ce qui se repère le plus vite.

### Bloc 6 — La note de synthèse

`note` est le champ le plus libre et le plus précieux. Y écrire, en prose :

- ce que le recensement dit de faux ou ne dit pas ;
- l'origine de chaque estimation, avec sa source et sa date ;
- l'état général, ce qui est utilisable et ce qui ne l'est pas ;
- le contexte : à côté d'un city-stade, dans un parc, autour d'un terrain de football.

Toute affirmation déduite d'une image porte sa mention : *« déduit de l'orthophoto IGN,
non vérifié sur place »*.

## Écrire le fichier

`data/overrides/<id>.json`, un objet JSON, clés autorisées uniquement :

`id` · `nom` `adresse` `cp` `ville` `dep` `dep_nom` `region` `surface` `url` `horaires`
`acces_note` `note` — chaînes
`piste` `couvert` `eclairage` `acces_libre` `ouvert_public` `vestiaires` `douches`
`sanitaires` `scolaire` `supprime` — booléens
`couloirs` `longueur_piste` `longueur_probable` `tribunes` `annee` `renovation` — entiers
`lat` `lon` — nombres
`agres` `agres_probables` — listes
`photos` (`fichier`, `legende`, `credit`) · `avis` (`auteur`, `date`, `note`, `texte`)

Pour une piste nouvelle (`c-…`), `nom`, `ville`, `lat` et `lon` sont obligatoires.

**Omettre toute clé dont on n'a pas la réponse.** Ne pas écrire `false`, ne pas écrire
`null`, ne pas écrire `""`.

Puis, dans l'ordre :

```bash
python3 scripts/validate_overrides.py            # doit sortir sans erreur
python3 scripts/build_data.py --offline          # tracks.json, depuis le cache Data ES
python3 scripts/optimize_photos.py <id> <fichiers…>   # après build_data, cf. bloc 4
python3 scripts/validate_overrides.py            # à nouveau : il vérifie les photos
python3 scripts/build_data.py --offline
python3 scripts/build_site.py --out _site        # rend la fiche
```

L'aller-retour n'est pas une maladresse : `validate_overrides.py` vérifie que chaque
photo déclarée existe bien dans `data/photos/<id>/` et pèse moins de 400 Ko, et
`optimize_photos.py` a besoin que le site soit dans `tracks.json` pour nommer ses
fichiers.

Ouvrir `_site/site/<id>/index.html` et **relire la fiche produite** avant de committer :
c'est le seul moyen de voir qu'une phrase de `note` dit le contraire d'un booléen.

## Avant de conclure

Récapituler à la personne, en clair :

- ce qui a été écrit dans les champs structurés ;
- ce qui est parti en prose ;
- **ce qui est resté vide, et pourquoi** — c'est la liste de ce qu'il faudra regarder à
  la prochaine visite, et c'est aussi ce que `/api/tracks?has_reviews=false` sert à
  retrouver.

Proposer la branche, le commit et la pull request en suivant `CONTRIBUTING.md`.
