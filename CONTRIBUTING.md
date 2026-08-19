# Contribuer à l'annuaire

Merci ! Les données du ministère sont une base solide mais incomplète : ce sont les
gens qui s'entraînent sur ces pistes qui savent vraiment ce qu'il y a dessus.

## Sans compte GitHub

Vous n'êtes pas obligé d'avoir un compte : le
[formulaire du site](https://chardonneaur.github.io/pistes-athle/#contribuer) propose
d'envoyer la même contribution **par e-mail**, photos en pièces jointes. Le reste de
cette page décrit la voie GitHub, pour qui veut préparer directement le fichier de
données.

*You do not need a GitHub account: the
[form on the site](https://chardonneaur.github.io/pistes-athle/#contribuer) can send
the same contribution by email instead.*

## Le principe

`data/tracks.json` est **généré** : on ne le modifie jamais à la main. À chaque
construction, le script part des données du ministère puis applique par-dessus les
fichiers de `data/overrides/`. Une contribution = un petit fichier JSON qui dit
« pour ce site, voilà ce qui est vrai ».

## Corriger ou compléter un site existant

1. Ouvrez la fiche du site dans l'application et notez sa **référence**
   (en bas de la fiche, ex. `I352380090`).
2. Créez `data/overrides/I352380090.json` avec **uniquement les champs à changer** :

```json
{
  "id": "I352380090",
  "surface": "synthetique",
  "couloirs": 8,
  "agres": ["longueur", "triple", "hauteur", "perche", "poids"],
  "acces_libre": true,
  "horaires": "Lun-ven 8h-22h, samedi 9h-19h",
  "acces_note": "Perche accessible uniquement avec un encadrant du club."
}
```

Tout ce que vous ne mentionnez pas garde la valeur du ministère.

> ⚠️ Dès que vous renseignez `agres`, la liste **remplace** entièrement celle
> déduite automatiquement, et les mentions incertaines (« aire de saut ») sont
> effacées. Listez donc tous les agrès du site, pas seulement celui que vous ajoutez.

## Ajouter une piste absente

Choisissez un identifiant qui commence par `c-` (pour « communauté ») :

```json
{
  "id": "c-stade-des-trois-chenes-rennes",
  "nom": "Stade des Trois Chênes",
  "adresse": "12 rue du Stade",
  "cp": "35000",
  "ville": "Rennes",
  "dep": "35",
  "lat": 48.11982,
  "lon": -1.66423,
  "piste": true,
  "surface": "synthetique",
  "couloirs": 6,
  "longueur_piste": 400,
  "agres": ["longueur", "poids"],
  "acces_libre": true
}
```

`nom`, `ville`, `lat` et `lon` sont obligatoires pour une nouvelle piste.
Pour les coordonnées : clic droit sur le site dans Google Maps ou OpenStreetMap →
copier les coordonnées (latitude d'abord).

## Ajouter des photos

Les photos sont ce qui manque le plus : une image du sautoir à la perche vaut
mieux qu'une ligne « aire de saut ».

```bash
python3 scripts/optimize_photos.py I441310030 ~/photos/pornic/*.jpg
```

Le script redimensionne, compresse, **supprime les métadonnées EXIF (dont la
position GPS de votre téléphone)** et fabrique une vignette. Il écrit dans
`data/photos/<id>/` et vous affiche le bloc JSON à recopier :

```json
{
  "id": "I441310030",
  "photos": [
    { "fichier": "01-piste-et-terrain.jpg",
      "legende": "La piste synthétique et le terrain central engazonné",
      "credit": "Votre nom" }
  ]
}
```

Règles : JPEG uniquement, 400 Ko maximum par photo (le script s'en charge),
photos prises par vous, et **pas de personnes reconnaissables**. En les
proposant, vous acceptez leur publication sous ODbL avec votre crédit.

## Donner son avis

Un avis, c'est le retour de terrain que la donnée publique n'aura jamais :
l'état réel de la piste, les agrès utilisables, l'ambiance, l'accès.

```json
{
  "id": "I441310030",
  "avis": [
    {
      "auteur": "Ronan",
      "date": "2026-08-18",
      "note": 5,
      "texte": "Très belle piste. Tous les agrès sont là et en état : sautoir en longueur, perche, hauteur, aire de lancer du poids, et une cage pour le disque et le marteau."
    }
  ]
}
```

`texte` est obligatoire (1 200 caractères maximum), `note` va de 1 à 5, `date`
est au format `AAAA-MM-JJ`, `auteur` peut être un prénom, un pseudo ou un club —
laissez-le vide pour rester anonyme. La note affichée sur la fiche est la moyenne
de tous les avis.

Décrivez l'installation, pas les personnes : pas de nom d'entraîneur, pas de
règlement de comptes avec le club local.

## Supprimer un doublon ou un site disparu

```json
{ "id": "I352380090", "supprime": true }
```

Expliquez la raison dans la description de la pull request.

## Champs disponibles

| Champ | Type | Valeurs |
|---|---|---|
| `id` | texte | **obligatoire** — `I…` (référence ministère) ou `c-…` (nouveau site) |
| `nom` | texte | nom de l'installation |
| `adresse`, `cp`, `ville`, `dep` | texte | `dep` = code département, ex. `"35"`, `"2A"` |
| `lat`, `lon` | nombre | coordonnées décimales, à fournir ensemble |
| `piste` | booléen | présence d'une piste de course |
| `surface` | texte | `synthetique`, `bitume`, `cendree`, `sable`, `gazon`, `naturel`, `interieur` |
| `couloirs` | entier | nombre de couloirs |
| `longueur_piste` | entier | développement en mètres (`400`, `333`, `200`…) |
| `couvert` | booléen | piste indoor ou couverte |
| `agres` | liste | `longueur`, `triple`, `hauteur`, `perche`, `poids`, `disque`, `marteau`, `javelot`, `steeple` |
| `acces_libre` | booléen | on peut entrer et s'entraîner sans licence |
| `ouvert_public` | booléen | ouvert au public sur certains créneaux |
| `horaires` | texte | libre, ex. `"Lun-ven 8h-22h"` |
| `acces_note` | texte | précision sur l'accès (portail, badge, créneaux club…) |
| `eclairage`, `vestiaires`, `douches`, `sanitaires` | booléen | |
| `tribunes` | entier | nombre de places |
| `annee`, `renovation` | entier | année de mise en service / dernière rénovation |
| `scolaire` | booléen | site situé dans une enceinte scolaire |
| `url` | texte | page officielle, doit commencer par `https://` |
| `note` | texte | remarque libre affichée sur la fiche |
| `photos` | liste | objets `{fichier, legende, credit}` — voir plus haut |
| `avis` | liste | objets `{auteur, date, note, texte}` — voir plus haut |
| `supprime` | booléen | retire le site de l'annuaire |

## Vérifier avant d'envoyer

```bash
python3 scripts/validate_overrides.py   # syntaxe, valeurs, coordonnées
python3 scripts/build_data.py           # reconstruit le jeu de données complet
python3 -m http.server 8000             # et on regarde le résultat
```

La CI relance ces contrôles sur chaque pull request.

## Règles de bon sens

- **Décrivez ce que vous avez vu**, ou ce que dit une source publique (site de la
  mairie, du club, photo satellite). Ne recopiez pas de base de données protégée
  par un droit *sui generis* — par exemple un annuaire commercial.
- Une contribution par site : un fichier `data/overrides/<id>.json`.
- Les horaires très instables (créneaux club de la saison en cours) vieillissent
  mal ; préférez `acces_note` pour décrire une règle durable.
- En proposant une contribution, vous acceptez qu'elle soit publiée sous
  [ODbL 1.0](LICENSE-DATA).

## Envoyer sans passer par la ligne de commande

1. Ouvrez [`data/overrides/`](data/overrides/) sur GitHub → **Add file → Create new file**
2. Nommez le fichier `I352380090.json`, collez votre JSON
3. **Propose new file** → GitHub crée la branche et la pull request pour vous

Et si tout ça est trop compliqué : ouvrez simplement une
[issue](../../issues/new/choose), on s'occupe de la traduction en JSON.
