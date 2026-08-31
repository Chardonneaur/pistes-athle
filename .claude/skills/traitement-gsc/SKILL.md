---
name: traitement-gsc
description: >
  Traite la file des questions posées à Google avant d'arriver sur pistes-athle.com :
  choisit une question, monte son dossier, cherche une source citable, corrige la fiche
  ou constate qu'on ne peut rien écrire, puis ferme le dossier dans la base
  « pistes-athle-seo ». C'est l'étage 2 de la boucle décrite dans
  docs/releve-search-console.md. Utiliser dès que quelqu'un veut traiter la file
  Search Console, répondre aux requêtes des internautes, exploiter la Search Console,
  ou améliorer une fiche à partir de ce que les gens cherchent. Se déclenche aussi sur
  « la file GSC », « les requêtes Google », « étage 2 », « dossier_gsc ».
---

# Traiter une question venue de la Search Console

## Ce que cette compétence essaie de produire

L'étage 1 (`scripts/releve_gsc.py`) relève chaque matin ce que les gens ont tapé dans
Google avant d'atterrir sur le site, et le range en une ligne par **question**, pas par
formulation. Il ne juge rien.

Ici commence le jugement, et donc l'erreur possible. Le but n'est pas de « répondre à la
requête » : c'est de **savoir si le site peut répondre honnêtement**, et de fermer le
dossier dans les deux cas. Un dossier fermé sur « on ne peut rien écrire » vaut autant
qu'un dossier fermé sur une correction — c'est ce qui empêche la file de rouvrir chaque
matin le même sujet.

## La règle qui prime sur tout le reste

**Une requête est une question posée, jamais une réponse.**

On n'écrit dans une fiche que des faits déjà présents dans `data/tracks.json` ou
`data/overrides/`, ou tirés d'une source citable **et citée**. Jamais un revêtement, un
horaire, un agrès, une longueur ou un contact déduits du texte de la requête.

Quelqu'un qui tape « stade machin tartan » ne prouve pas que le stade est en tartan : il
demande s'il l'est. Écrire `surface: synthetique` là-dessus, c'est fabriquer une donnée
et la publier sous une licence ouverte. C'est la faute la plus grave que cette boucle
puisse commettre, et elle est facile — la requête *ressemble* à une réponse.

Corollaire, tiré de `docs/trouver-les-pistes-manquantes.md` § 5.2 : un champ vide ne dit
pas « non ». Ne jamais écrire `acces_libre: false` parce qu'on n'a pas trouvé. On omet
la clé.

## Le déroulé

### 1. Choisir une question

```bash
python3 scripts/dossier_gsc.py
```

La file sort déjà ordonnée par ce qu'il y a à gagner : les `existence` d'abord, puis les
questions déjà visibles sans être gagnées. Les fiches déjà dans le podium sont écartées
— il n'y a rien à y gagner, et le premier lot l'a montré : « stade de luminy » était en
position 1,0 et le dossier s'est fermé sur « rien à corriger ». `--tout` les remontre si
besoin.

Traiter **une question à la fois**, jusqu'à sa fermeture. Une file à moitié traitée sur
dix sujets est pire qu'un seul dossier fini : la mémoire de la boucle est dans les
statuts, pas dans la tête de celui qui travaille.

### 2. Monter le dossier

```bash
python3 scripts/dossier_gsc.py --dossier 'I420440023|fiche'
```

Le script affiche la fiche visée, ce que l'intention réclame, ce qui est renseigné et ce
qui ne l'est pas. **Lire cette sortie avant de chercher quoi que ce soit** : la moitié
des questions sont déjà satisfaites par la fiche, et le travail se réduit alors à
vérifier puis fermer.

Il affiche « non renseigné » et jamais « absent ». La nuance est toute la promesse du
site : un champ vide n'autorise à écrire ni la présence ni l'absence de la chose.

### 3. Chercher, dans cet ordre

Du plus fiable au moins fiable. S'arrêter dès qu'une source répond.

1. **Ce que le site sait déjà** — `data/tracks.json`, `data/overrides/<id>.json`. Une
   donnée peut être présente et mal affichée : c'est un bug, pas un manque.
2. **OpenStreetMap** — pour la géométrie et elle seule : développement de l'anneau,
   nombre de couloirs parfois, présence d'un sautoir. Se mesure avec
   `scripts/osm_longueurs.py`. Rappel : 400 m se mesure **à 30 cm de la lice**, jamais
   au bord extérieur de l'anneau.
3. **Le site officiel** de la commune ou du club — horaires, tarifs, créneaux, contact.
   C'est la seule source acceptable pour un horaire. `scripts/conseils_municipaux.py`
   et `docs/ce-que-dit-la-mairie.md` décrivent comment lire les délibérations.
4. **L'orthophoto IGN** — `scripts/ortho.py`, et `docs/lecture-orthophoto.md`. Elle
   donne une forme, un nombre de couloirs, la présence d'aires. Elle **ne donne jamais
   un revêtement** : l'enrobé pigmenté rouge est indiscernable du tartan vu du ciel.
   Tout ce qui en sort est `_probable` ou va dans `note` avec sa mention.

Ce qui n'est **pas** une source : la requête elle-même, un forum, la mémoire du modèle,
un autre annuaire de pistes, la vraisemblance.

### 4. Écrire — ou ne pas écrire

Si une source répond, la correction va dans `data/overrides/<id>.json`, selon les règles
et le vocabulaire de la compétence `contribution-piste` : clés autorisées uniquement,
toute clé sans réponse omise, jamais de `false` ni de `null` pour dire « je ne sais pas ».

La source se cite dans `note`, avec sa date :

> « Développement estimé à 250 m d'après le tracé de l'anneau dans OpenStreetMap
> (r3181302), non mesuré sur place. »

Une estimation ne devient jamais une mesure : `longueur_probable`, pas `longueur_piste`.

Puis la chaîne habituelle :

```bash
python3 scripts/validate_overrides.py       # doit sortir sans erreur
python3 scripts/build_data.py --offline
python3 scripts/build_site.py --out _site
```

et **relire `_site/site/<id>/index.html`** : c'est le seul endroit où l'on voit qu'une
phrase de `note` contredit un booléen.

### 5. Fermer le dossier

```bash
python3 scripts/dossier_gsc.py --fermer '<clé>' --statut <statut> --detail "..."
```

Quatre statuts terminaux, et un seul se rouvre un jour :

| statut | quand |
|---|---|
| `traite` | on a corrigé la fiche, **ou** on a vérifié qu'elle répondait déjà |
| `sans-source` | la question est légitime, aucune source citable n'existe |
| `candidat` | un lieu peut-être réel, versé dans `data/a-verifier.json` |
| `hors-sujet` | la requête ne parle pas d'une piste d'athlétisme |

`--detail` est obligatoire, et le script le refuse vide. Y écrire **ce qui a été fait ou
pourquoi rien ne l'a été**, pas un mot-clé. Un dossier fermé sur « rien trouvé » sans
dire où l'on a cherché sera rouvert et refait à l'identique.

Seul `sans-source` se rouvre, et à une condition stricte : impressions triplées **et**
plus de 90 jours, au cas où une source soit parue entre-temps.

Le gel des compteurs (`impressions_avant`, `position_avant`, `traite_le`) est écrit par
un déclencheur SQL, pas par le script — il n'y a rien à relever à la main. Le script
relit la ligne après coup et prévient si le gel n'a pas eu lieu.

### 6. La pull request

Si une fiche a changé, ouvrir une branche et une PR en suivant `CONTRIBUTING.md`.
Mettre l'URL de la PR dans `--detail` : c'est ce qui relie la question à ce qu'elle a
produit, et c'est ce qu'on relira dans six semaines pour savoir si la position a bougé.

Si rien n'a changé dans le dépôt, il n'y a pas de PR — fermer le dossier suffit.

## Les cas qui se traitent différemment

### `existence` — le signal le plus précieux, et le plus dangereux

Aucune fiche derrière la question : quelqu'un cherche un lieu que le recensement ignore
peut-être. Le dossier propose les candidats OSM de `data/a-verifier.json` dont la commune
recoupe la requête.

**Rien ne part dans `data/tracks.json`.** Les gens cherchent des pistes fermées,
démolies, ou situées dans la commune d'à côté. Une requête n'est pas une preuve
d'existence. Au mieux une ligne dans `data/a-verifier.json` avec sa source, statut
`candidat`, et la vérification viendra d'une visite ou d'une source officielle.

### `fiche` — le cas le plus fréquent, à 90 %

La personne a tapé le nom du stade. Elle ne pose pas de question précise : elle veut la
fiche. Le travail n'est donc pas de combler un champ désigné mais de **vérifier que la
fiche tient debout** — et, le plus souvent, de constater qu'il n'y a aucune source pour
la compléter davantage.

Ces dossiers se ferment souvent en `sans-source`, et c'est normal. Ce qui les débloquera
n'est pas une recherche en ligne mais une visite : la compétence `contribution-piste`,
et l'appel à contribution que porte la fiche.

### `ville:` et `dep:` — la donnée est ailleurs

La page commune ou département ne porte aucune donnée propre : elle liste les fiches. La
question se traite donc sur les fiches listées, que le dossier affiche avec leurs
manques. Fermer la question de la commune une fois les fiches traitées.

### `tarif` — presque toujours `sans-source`

Le modèle de données ne porte pas de tarif, et ce n'est pas un oubli : aucune source
ouverte ne le publie de façon stable, et il change tous les ans. Sauf si la page
officielle de l'installation le donne — auquel cas c'est `url` qu'on renseigne, pas un
prix qu'on recopie.

## Ce qu'il ne faut jamais faire

- Écrire un fait déduit de la requête.
- Écrire `false` ou `null` pour dire « je ne sais pas ».
- Promouvoir une estimation en mesure.
- Déduire un revêtement d'une couleur, sur orthophoto ou sur photo aérienne.
- Ajouter une piste à `data/tracks.json` sur la foi d'une requête.
- Fermer un dossier sans `--detail` lisible par quelqu'un d'autre.
- Traiter dix questions à moitié plutôt qu'une jusqu'au bout.
