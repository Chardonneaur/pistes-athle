# Où s'entraîner ? — pistes-athle.com

Annuaire libre des **7 155 installations d'athlétisme françaises** : revêtement,
développement, couloirs, agrès, conditions d'accès, coordonnées.

**→ [pistes-athle.com](https://pistes-athle.com)**

## Ce dépôt

Il sert le site. La branche [`gh-pages`](../../tree/gh-pages) porte les pages
publiées, réécrites chaque jour ; elle n'a jamais qu'un commit, et son
historique n'a rien à raconter.

C'est ici que se signalent les erreurs et que s'ajoutent les fiches :
**[ouvrir un signalement](../../issues/new/choose)**. Aucune connaissance
technique n'est nécessaire — chaque formulaire pose ses questions en français.

Ce qu'on peut faire :

| | |
|---|---|
| [Corriger une fiche](../../issues/new?template=correction.yml) | un revêtement, une longueur, un nom |
| [Ajouter une piste absente](../../issues/new?template=ajout.yml) | elle existe, l'annuaire l'ignore |
| [Compléter une fiche](../../issues/new?template=complement.yml) | agrès, couloirs, accès |
| [Donner un avis](../../issues/new?template=avis.yml) | vous y courez, dites-en quelque chose |
| [Envoyer une photo](../../issues/new?template=photo.yml) | 7 129 fiches sur 7 155 n'en ont aucune |

Le détail est dans [CONTRIBUTING.md](CONTRIBUTING.md).

## Interroger l'annuaire

Le site sert sa propre API, sans clé ni inscription :

- [`/api/index.json`](https://pistes-athle.com/api/index.json) — les 7 155 installations en un fichier
- [`/openapi.json`](https://pistes-athle.com/openapi.json) — le contrat complet
- [`/llms.txt`](https://pistes-athle.com/llms.txt) — l'orientation, pour un agent

Deux règles à connaître avant d'interpréter une réponse :

1. `acces_libre` vaut `true` ou `null`, **jamais `false`**. 5 594 installations
   n'ont aucune information d'accès ; un blanc n'est pas un refus.
2. `agres_declares` vient de l'exploitant, `agres_probables` est déduit d'une
   orthophoto par un contributeur. Les deux ne se valent pas.

## Données et licence

Données du recensement des équipements sportifs du ministère des Sports,
complétées par les contributions reçues ici, sous
[Licence Ouverte 2.0](LICENSE-DATA). Le code du site est sous [MIT](LICENSE).

Les scripts de construction ne sont pas publiés.
