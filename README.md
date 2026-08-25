# Où s'entraîner ? — l'annuaire des pistes d'athlétisme françaises

Une application web mobile qui répond à une question toute bête que se posent les
athlètes, les entraîneurs et les coureurs : **où est la piste la plus proche, et
qu'est-ce qu'il y a dessus ?**

Pas seulement « il y a un stade ici », mais : la piste est-elle en synthétique ou
en cendrée ? Combien de couloirs ? Y a-t-il un sautoir à la perche ? Une aire de
lancer du poids ? Est-ce éclairé ? Peut-on y entrer sans licence ?

👉 **[Ouvrir l'application](https://chardonneaur.github.io/pistes-athle/)** ·
🇬🇧 **[English version](https://chardonneaur.github.io/pistes-athle/en/)**

---

## Ce que fait l'application

- **7 100 sites d'athlétisme** en France métropolitaine et outre-mer, dont ~6 500 avec piste
- Tri **par distance** avec la géolocalisation, ou recherche par ville / code postal
- **Filtres par agrès** : perche, longueur, hauteur, poids, lancers longs, steeple
- **Filtres par revêtement** : synthétique (tartan), bitume, cendrée
- **Filtre par département** : on y tape le numéro (`44`, `01`, `2A`), le nom ou un code
  postal (`44210`) ; la barre de recherche reconnaît aussi un département et le bascule
  dans son filtre
- Filtres accès libre, éclairage, piste couverte, vestiaires, hors enceinte scolaire
- **Photos et avis d'athlètes** : galerie par site, note sur 5, retours de terrain
- **Filtre par tour de piste** : 400 m, 333 m, 300 m, 250 m, 200 m — sur le
  développement déclaré par le ministère ou, à défaut, sur celui **estimé d'après
  le tracé OpenStreetMap de l'anneau** (`scripts/osm_longueurs.py`), affiché avec
  un « ? » et jamais présenté comme une mesure
- **Page contributeurs** (`/contributeurs/`, `/en/contributors/`) : le classement
  et toutes les contributions, avec leurs photos
- **Vitrine en page d'accueil** : les trois dernières contributions en photos, le
  classement des contributeurs, et un appel à contribuer — masqués dès qu'une
  recherche ou un filtre est actif
- **Photos indexables** : nom de fichier descriptif, `alt` situé, `ImageObject`
  JSON-LD avec auteur et licence ODbL, `og:image`, et déclaration au plan de site
  via l'extension `image:`
- **Vue aérienne** (orthophoto IGN, Licence Ouverte 2.0) sur les sites qui n'ont pas
  encore de photo, **avec son année de prise de vue** — de 2025 en Loire-Atlantique
  à 2004 à Wallis-et-Futuna : elle montre l'implantation, jamais l'état des agrès
- **Carte** avec regroupement des marqueurs, et fiche détaillée par site
- **Installable** sur l'écran d'accueil (PWA) et **consultable hors-ligne** une fois chargée
- **Bilingue français / anglais** : `/` en français, `/en/` en anglais, avec bascule dans l'en-tête
- **Une page HTML par site**, lisible sans JavaScript, pour les moteurs de recherche et les agents IA
- 100 % statique : hébergé gratuitement sur GitHub Pages, aucun serveur
- **Mesure d'audience sans cookie** (Matomo, hébergé en Europe) : aucun cookie déposé,
  aucun identifiant conservé, le refus « Do Not Track » respecté — donc aucun bandeau
  de consentement. Elle sert à répondre à une question précise : **les agents IA
  lisent-ils cet annuaire, et envoient-ils des gens dessus ?**

> 📄 **[Étude préalable](docs/etude-prealable.md)** — pourquoi ce projet n'existe pas
> déjà, et pourquoi la réutilisation des données du ministère est juridiquement solide.

> 🔍 **[Lire une orthophoto](docs/lecture-orthophoto.md)** — reconnaître un sautoir
> ou une cage de lancer vus du ciel, ce qu'on peut en conclure, et surtout ce qu'on
> ne peut pas : le rappel mesuré est d'un agrès sur trois.

> 🧭 **[Trouver les pistes que le recensement ignore](docs/trouver-les-pistes-manquantes.md)**
> — la méthode : quatre sources à croiser, six façons de se tromper, et ce que le
> balayage de la Loire-Atlantique et du Pays de Retz a donné.

> 📈 **[Mesurer le trafic des IA](docs/mesurer-le-trafic-des-ia.md)** — pourquoi un
> traceur posé dans la page ne voit *aucun* robot, les trois journaux qui couvrent
> chacun une population différente, et ce que Matomo accepte — ou jette en silence.

> 🏛️ **[Ce que dit la mairie](docs/ce-que-dit-la-mairie.md)** — dater un changement
> plutôt que décrire un état : lire les délibérations des conseils municipaux, et
> distinguer les trois silences qui n'ont pas le même sens.

## Bilingue, et trouvable

L'application est une page unique qui rend 7 100 sites en JavaScript : un moteur de
recherche ou un agent IA qui n'exécute pas le script n'y voit rien. Le déploiement
génère donc, à côté de l'application, un site entièrement statique :

| URL | Contenu |
|---|---|
| `/` et `/en/` | l'application (carte, filtres, recherche), en français et en anglais |
| `/site/<ID>/` et `/en/track/<ID>/` | une page HTML complète par installation, avec JSON-LD `SportsActivityLocation` |
| `/departement/<CODE>/` et `/en/department/<CODE>/` | les installations d'un département, groupées par commune |
| `/departements/` et `/en/departments/` | l'annuaire des 108 départements, groupés par région |
| `/contributeurs/` et `/en/contributors/` | le classement des contributeurs et toutes leurs contributions |
| `/confidentialite/` et `/en/privacy/` | ce qui est mesuré, ce qui ne l'est pas, et pourquoi il n'y a pas de bandeau |
| `/ville/<SLUG>/` et `/en/city/<SLUG>/` | les installations d'une commune, et celles à moins de 20 km |
| `/pistes/<CRITÈRE>/` et `/en/tracks/<CRITERION>/` | développement, couloirs, accès libre, discipline, revêtement |
| `/pistes/<CRITÈRE>/<DÉPARTEMENT>/` | le croisement des deux, quand il compte au moins trois installations |
| `/api/…` et `/openapi.json` | l'API statique et son contrat — voir « Interroger l'annuaire » |
| `/sitemap.xml` | index de plan de site (une entrée par langue, ~23 700 URL) |
| `/robots.txt` | tout ouvert, robots d'IA compris, explicitement |
| `/llms.txt` | description du site et du jeu de données pour un agent, avec le schéma des clés |

L'application accepte des liens partageables : `#carte` ouvre la carte, `#dep=44`
filtre sur un département et recadre la carte dessus, `#q=pornic` remplit la recherche
et `#site=I441310030` ouvre une fiche. Les pages de département pointent vers
`#carte&dep=<CODE>`.

Chaque page porte son `canonical`, ses alternatives `hreflang` fr / en / x-default et
son balisage Open Graph. Les fiches de site déclarent leurs équipements, leurs
coordonnées, leur note et leurs avis en JSON-LD.

Les libellés de l'interface vivent dans `assets/i18n.js` ; `<html lang>` décide de la
langue servie. Les pages statiques, elles, sont traduites à la génération par
`scripts/build_site.py`.

## Interroger l'annuaire

Un agent pouvait déjà **lire** le site : `llms.txt`, JSON-LD, `tracks.json`. Il ne
pouvait pas l'**interroger** — pour répondre à « une piste de 400 m en accès libre près
de Nantes », il fallait télécharger 1,5 Mo et filtrer soi-même. Trois couches y
répondent, de la plus simple à la plus puissante.

**Les facettes**, un fichier JSON par critère, générées par `scripts/build_api.py` :

```
/api/tracks/<ID>.json                     une installation
/api/tracks/department/<CODE>.json        un département
/api/tracks/city/<DEP>/<SLUG>.json        une commune
/api/tracks/discipline/<DISCIPLINE>.json  et /<DEP>.json pour le croisement
/api/tracks/length/<MÈTRES>.json          /api/tracks/surface/<REVÊTEMENT>.json
/api/tracks/lanes/<N>.json                /api/tracks/free-access.json
/api/tracks/reviewed.json                 les installations qu'un contributeur a décrites
/api/geo/<LAT>/<LON>.json                 cellule de 0,1° (~11 km), avec ses voisines
```

Une facette n'existe que si elle contient au moins une installation : on part de la
donnée, jamais du produit cartésien des vocabulaires.

**L'index compact**, `/api/index.json` : les 7 135 installations réduites aux seuls
champs sur lesquels on filtre, 1,0 Mo contre 1,5 Mo pour `tracks.json`. De quoi faire
soi-même n'importe quelle conjonction, en un téléchargement.

**Le serveur de recherche**, `api/worker.js`. GitHub Pages sert des fichiers statiques
et **ignore la chaîne de requête** : `/api/tracks?city=Nantes` ne peut pas filtrer ici.
Le worker comble exactement ce trou — paramètres combinables, recherche par rayon — en
lisant l'index publié par le build, donc sans jamais pouvoir en diverger :

```bash
npx wrangler deploy api/worker.js --name pistes-athle-api
API_URL=https://pistes-athle-api.<compte>.workers.dev python3 scripts/build_site.py
```

Sans `API_URL`, le site déclare qu'aucun serveur de recherche n'est disponible et
renvoie vers les facettes. Mieux vaut un agent qui sait qu'il doit filtrer lui-même
qu'un agent qui croit avoir filtré.

`/api/tracks.json` est le **document de capacités** : il dit lequel de ces chemins est
disponible sur cet hôte. C'est ce que `/api/tracks?...` renvoie quand la chaîne de
requête a été jetée par l'hébergeur — un 404 n'apprendrait rien à personne.

`/openapi.json` (OpenAPI 3.1) décrit le tout, et est généré : les vocabulaires sortent
du jeu de données et changent au rebuild mensuel.

### Deux règles de contrat

Elles viennent de la donnée, pas du confort, et un agent qui les ignore publie des
affirmations fausses.

`acces_libre` vaut `true` ou `null`, **jamais** `false`. 5 551 des 7 135 installations
n'ont aucune information d'accès : un blanc n'est pas un refus. C'est pourquoi
`free_access=false` renvoie une 400 plutôt qu'une liste.

Les filtres de discipline portent sur les agrès **déclarés** par l'exploitant. Ce qu'un
contributeur a déduit d'une orthophoto est rendu à part, dans `agres_probables`, et
`saut_indetermine` signifie « il y a un sautoir, on ne sait pas lequel ».

`nb_avis` est l'exception qui éclaire la règle : zéro y est un **fait**, pas un blanc.
Cette base sait si quelqu'un a décrit un site, puisque les avis sont les siens. Donc
`has_reviews=false` est légitime là où `free_access=false` ne l'est pas — et les 7 130
installations que personne n'a encore vues, croisées avec une commune ou un département,
sont exactement la file d'attente de la contribution :

```
/api/tracks?has_reviews=false&free_access=true&department=44   → 53 pistes à décrire
```

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

1. **Depuis l'application** — sur une fiche, *Donner mon avis*, *Signaler une erreur*
   ou *Compléter la fiche* ouvrent un formulaire pré-rempli avec le site concerné.
   Au moment d'envoyer, deux boutons, **et aucun compte n'est obligatoire** :
   - *Envoyer via GitHub* → ouvre le formulaire GitHub pré-rempli, où les photos se
     glissent-déposent directement ;
   - *Envoyer par e-mail* → compose un message pour le mainteneur, à envoyer depuis
     sa propre messagerie, photos en pièces jointes.

   Le formulaire est aussi accessible directement :
   [`/#contribuer`](https://chardonneaur.github.io/pistes-athle/#contribuer) — c'est le
   lien proposé dans les gabarits d'issues à qui n'a pas de compte GitHub.
2. **En modifiant un fichier depuis le navigateur** — ajoutez un petit fichier JSON
   dans `data/overrides/`. Voir **[CONTRIBUTING.md](CONTRIBUTING.md)**.
3. **En pull request classique** — clonez, éditez, `python3 scripts/validate_overrides.py`,
   poussez.

Toute PR touchant `data/overrides/` est validée automatiquement (syntaxe, valeurs
autorisées, cohérence géographique) et un résumé lisible est publié dans la PR.

### Recevoir les contributions par e-mail sans être noyé

Les messages envoyés depuis le formulaire portent un sujet préfixé `[Piste][Avis]`,
`[Piste][Correction]`, `[Piste][Complément]` ou `[Piste][Ajout]`, et un corps
structuré (type, site, référence, note, signature). Un filtre suffit à les ranger —
sous Gmail, `Paramètres → Filtres → Créer un filtre`, objet contenant `[Piste]`,
action « Appliquer le libellé » et « Ne jamais envoyer dans les spams ».

L'adresse n'apparaît nulle part en clair dans les pages : elle est assemblée à
l'exécution par `assets/app.js`, ce qui la met hors de portée des robots qui
moissonnent le HTML. Elle n'est pas non plus dans le dépôt : les gabarits d'issues
renvoient vers `/#contribuer`, pas vers une adresse.

Si le volume devenait ingérable, `ENVOI_ENDPOINT` dans `assets/app.js` est le point
d'accroche prévu pour basculer vers un service de formulaire (Formspree, Web3Forms)
sans toucher au reste du code.

## Développement local

```bash
git clone https://github.com/Chardonneaur/pistes-athle.git
cd pistes-athle

python3 scripts/build_data.py       # télécharge Data ES et génère data/tracks.json
python3 -m http.server 8000         # puis ouvrir http://localhost:8000
```

Pour vérifier le site tel qu'il sera publié — les deux langues et les pages statiques :

```bash
python3 scripts/build_site.py --out _site
cd _site && python3 -m http.server 8000
```

`build_site.py` déduit l'URL publique de `GITHUB_REPOSITORY` ; `--url https://exemple.org/base`
la force (utile pour un domaine personnalisé).

`build_data.py --offline` réutilise le cache `data/.res_raw.json` (pratique pour
itérer sans retélécharger 8 Mo).

Aucune dépendance : Python 3 de la bibliothèque standard, et du JavaScript sans
framework. Seules Leaflet et Leaflet.markercluster sont chargées depuis un CDN.

## Structure du dépôt

```
index.html                  coque de l'application (la version /en/ en est dérivée)
assets/app.js               logique : chargement, filtres, carte, fiches
assets/i18n.js              tous les libellés, français et anglais
assets/style.css            interface mobile-first, thème clair/sombre
assets/page.css             feuille de style des pages statiques
assets/manifest*.webmanifest  PWA, une par langue
sw.js                       service worker (hors-ligne)
scripts/build_data.py       Data ES + overrides -> data/tracks.json
scripts/build_site.py       -> _site/ : application FR/EN, pages par site, par
                            département, par commune et par critère, sitemaps,
                            robots.txt, llms.txt
scripts/build_api.py        -> _site/api/ : facettes JSON, index compact, openapi.json
api/worker.js               serveur de recherche /api/tracks?... (à déployer, optionnel)
scripts/validate_overrides.py  contrôle des contributions (utilisé par la CI)
scripts/optimize_photos.py  redimensionne les photos et efface leur EXIF
scripts/pistes_absentes.py  anneaux OSM que l'annuaire ignore : audit de couverture
scripts/lieux_a_regarder.py  toponymie + city-stades BD TOPO -> planches-contact
scripts/conseils_municipaux.py  délibérations des conseils municipaux : file de lecture
data/overrides/*.json       contributions de la communauté (corrections, avis, photos)
data/photos/<id>/           photos optimisées, une par site
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
5. Si vous utilisez un domaine personnalisé, définissez la variable d'environnement
   `SITE_URL` dans le workflow : les URL canoniques, le plan de site et le `llms.txt`
   la reprennent.

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
