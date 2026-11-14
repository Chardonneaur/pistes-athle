# Bibliothèques tierces, servies depuis ce dépôt

Leaflet et son extension de regroupement étaient chargés depuis `unpkg.com`.
Trois raisons de les avoir rapatriés ici :

- **chaîne d'approvisionnement** — un script tiers sans attribut `integrity`
  s'exécute avec tous les droits de la page. Un CDN compromis, ou seulement une
  version republiée sous le même numéro, et c'est notre page qui exécute autre
  chose. Le fichier est maintenant dans le dépôt, versionné, relisible ;
- **affichage** — les deux feuilles de style étaient dans le `<head>` et
  bloquaient le premier rendu le temps d'un DNS, d'un TLS et d'un téléchargement
  vers un autre domaine, pour une carte que la vue par défaut n'affiche pas ;
- **hors-ligne** — le cache du navigateur ne pouvait retenir ces fichiers qu'après
  une première visite réussie, ce qui rendait la promesse d'application installable
  dépendante d'un tiers.

Ils sont désormais chargés **à la demande**, à la première ouverture d'une carte
(`chargerLeaflet()` dans `assets/app.js`).

## Contenu

| Fichier | Version | Origine |
|---|---|---|
| `leaflet.js`, `leaflet.css`, `images/` | 1.9.4 | https://unpkg.com/leaflet@1.9.4/dist/ |
| `leaflet.markercluster.js`, `MarkerCluster.css` | 1.5.3 | https://unpkg.com/leaflet.markercluster@1.5.3/dist/ |

Licences : Leaflet et Leaflet.markercluster sont sous licence BSD 2 clauses.

## Empreintes

Relevées au rapatriement, le 2026-08-26. À revérifier lors d'une montée de version :
un fichier qui change sans que le numéro de version change est un signal, pas un détail.

```
db49d009c841f5ca34a888c96511ae936fd9f5533e90d8b2c4d57596f4e5641a  leaflet.js
a7837102824184820dfa198d1ebcd109ff6d0ff9a2672a074b9a1b4d147d04c6  leaflet.css
1e4e1d22972a3926f48598e0caf14e3fe7049835d428a344fed4f9e3665b3508  leaflet.markercluster.js
614dea0a98ff3f4ead74f04918f6b1d1b9ba435c25b5fc23b21a394d1e3e4d87  MarkerCluster.css
```

Pour mettre à jour :

```sh
cd assets/vendor
curl -sSfLO https://unpkg.com/leaflet@<version>/dist/leaflet.js
# … puis sha256sum, et mettre ce tableau à jour
```
