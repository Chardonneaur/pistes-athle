# Où s'entraîner ? — l'annuaire des pistes d'athlétisme françaises

Une application web mobile qui répond à une question toute bête que se posent les
athlètes, les entraîneurs et les coureurs : **où est la piste la plus proche, et
qu'est-ce qu'il y a dessus ?**

Pas seulement « il y a un stade ici », mais : la piste est-elle en synthétique ou
en cendrée ? Combien de couloirs ? Y a-t-il un sautoir à la perche ? Une aire de
lancer du poids ? Est-ce éclairé ? Peut-on y entrer sans licence ?

👉 **[Ouvrir l'application](https://chardonneaur.github.io/pistes-athle/)**

---

## Ce que fait l'application

- **7 100 sites d'athlétisme** en France métropolitaine et outre-mer, dont ~6 500 avec piste
- Tri **par distance** avec la géolocalisation, ou recherche par ville / code postal
- **Filtres par agrès** : perche, longueur, hauteur, poids, lancers longs, steeple
- **Filtres par revêtement** : synthétique (tartan), bitume, cendrée
- Filtres accès libre, éclairage, piste couverte, vestiaires, hors enceinte scolaire
- **Carte** avec regroupement des marqueurs, et fiche détaillée par site
- **Installable** sur l'écran d'accueil (PWA) et **consultable hors-ligne** une fois chargée
- 100 % statique : hébergé gratuitement sur GitHub Pages, aucun serveur, aucun tracker

> 📄 **[Étude préalable](docs/etude-prealable.md)** — pourquoi ce projet n'existe pas
> déjà, et pourquoi la réutilisation des données du ministère est juridiquement solide.

## D'où viennent les données

De **Data ES**, le [Recensement des équipements sportifs, espaces et sites de
pratiques](https://equipements.sports.gouv.fr/) du ministère chargé des Sports.

- **Licence Ouverte 2.0 (Etalab)** — réutilisation libre, y compris commerciale,
  sous réserve de mentionner la paternité. C'est fait dans l'application (fiche
  détail + écran « À propos ») et ici.
- Mise à jour quotidienne côté ministère ; ce dépôt la resynchronise chaque mois
  automatiquement (workflow `deploy.yml`).
- 9 563 équipements de la famille « Équipement d'athlétisme » sont agrégés par
  installation pour produire `data/tracks.json`.

### Les limites, en toute honnêteté

Les fiches sont **déclaratives** : elles sont remplies par les propriétaires des
installations, avec des libellés libres. Concrètement :

- 903 sites déclarent une « aire de saut » **sans dire laquelle** (longueur ? perche ?)
  et 381 une « aire de lancer » sans préciser la discipline. L'application les
  affiche en pointillés, comme des informations incertaines.
- Seuls 28 sites mentionnent explicitement la perche, alors qu'il y en a
  manifestement bien plus.
- Les conditions d'accès réelles (portail ouvert le dimanche, créneaux club)
  n'existent nulle part dans la donnée publique.

**C'est exactement là que la communauté apporte de la valeur** : chaque
contribution transforme un « aire de saut » anonyme en « sautoir à la perche,
accessible en semaine ».

## Contribuer

Trois portes d'entrée, de la plus simple à la plus technique :

1. **Sans rien connaître à GitHub** — depuis une fiche de l'application, cliquez sur
   *Signaler une erreur* ou *Compléter la fiche* : un formulaire GitHub pré-rempli
   s'ouvre. [Voir les formulaires](../../issues/new/choose).
2. **En modifiant un fichier depuis le navigateur** — ajoutez un petit fichier JSON
   dans `data/overrides/`. Voir **[CONTRIBUTING.md](CONTRIBUTING.md)**.
3. **En pull request classique** — clonez, éditez, `python3 scripts/validate_overrides.py`,
   poussez.

Toute PR touchant `data/overrides/` est validée automatiquement (syntaxe, valeurs
autorisées, cohérence géographique) et un résumé lisible est publié dans la PR.

## Développement local

```bash
git clone https://github.com/Chardonneaur/pistes-athle.git
cd pistes-athle

python3 scripts/build_data.py       # télécharge Data ES et génère data/tracks.json
python3 -m http.server 8000         # puis ouvrir http://localhost:8000
```

`build_data.py --offline` réutilise le cache `data/.res_raw.json` (pratique pour
itérer sans retélécharger 8 Mo).

Aucune dépendance : Python 3 de la bibliothèque standard, et du JavaScript sans
framework. Seules Leaflet et Leaflet.markercluster sont chargées depuis un CDN.

## Structure du dépôt

```
index.html                  coque de l'application
assets/app.js               logique : chargement, filtres, carte, fiches
assets/style.css            interface mobile-first, thème clair/sombre
sw.js                       service worker (hors-ligne)
scripts/build_data.py       Data ES + overrides -> data/tracks.json
scripts/validate_overrides.py  contrôle des contributions (utilisé par la CI)
data/overrides/*.json       contributions de la communauté
data/tracks.json            jeu de données publié (généré, non versionné)
.github/workflows/          construction, validation, déploiement Pages
```

## Mise en route du dépôt

1. Créez le dépôt sur GitHub et poussez ce dossier.
2. *Settings → Pages → Build and deployment → Source :* **GitHub Actions**.
3. L'application détecte automatiquement le dépôt depuis l'URL `*.github.io` pour
   générer les liens de contribution (constante `REPO_OVERRIDE` dans `assets/app.js`
   si vous renommez le dépôt).
4. Le premier push sur la branche par défaut construit et publie le site.

## Licences

- **Code** : [MIT](LICENSE)
- **Données issues de Data ES** : [Licence Ouverte 2.0](https://github.com/etalab/licence-ouverte/blob/master/LO.md)
  — © Ministère chargé des Sports
- **Contributions de la communauté** (`data/overrides/`) : [ODbL 1.0](LICENSE-DATA),
  pour que les corrections restent librement réutilisables
- **Fond de carte** : © contributeurs [OpenStreetMap](https://www.openstreetmap.org/copyright)

## Avertissement

Les informations sont fournies à titre indicatif. Vérifiez les conditions d'accès
auprès du gestionnaire ou du club local avant de vous déplacer : une piste
municipale peut être fermée, en travaux, ou réservée aux scolaires en journée.
