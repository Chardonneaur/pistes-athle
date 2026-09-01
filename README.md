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
| `/ville/<COMMUNE-DÉLÉGUÉE>/` | les installations d'une commune fusionnée, sous son ancien nom — voir « Les communes qui ont disparu » |
| `/pistes/<CRITÈRE>/` et `/en/tracks/<CRITERION>/` | développement, couloirs, accès libre, discipline, revêtement |
| `/pistes/<CRITÈRE>/<DÉPARTEMENT>/` | le croisement des deux, quand il compte au moins trois installations |
| `/api/…` et `/openapi.json` | l'API statique et son contrat — voir « Interroger l'annuaire » |
| `/sitemap.xml` | index de plan de site (une entrée par langue, ~23 700 URL) |
| `/dates.json` | empreinte et date de dernière modification de chaque page — voir « Dater les pages » |
| `/robots.txt` | tout ouvert, robots d'IA compris, explicitement |
| `/<clé>.txt` | clé IndexNow, publique par construction — voir « Prévenir les moteurs » |
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

## Dater les pages

Une balise `<lastmod>` ne vaut que si la date bouge quand la page bouge. Dater les
23 842 URL du jour de la construction — ce que faisait la première version — revient
à annoncer à chaque déploiement que tout le site a changé : un moteur en déduit vite
que le signal ne décrit rien, et cesse d'en tenir compte. Sur un site de cette taille
et sans liens entrants, c'est le budget d'exploration qu'on y perd.

Chaque page est donc datée sur **son contenu**. À la construction, `build_site.py`
prend l'empreinte du HTML rendu — la date de construction neutralisée, sinon toutes
les empreintes changeraient à chaque fois — et la compare à celle de la version en
ligne. La date ne bouge que si l'empreinte a bougé.

Le journal des empreintes voyage avec le site, dans `/dates.json` : le site publié
porte sa propre mémoire, il n'y a rien à committer ni à conserver entre deux
constructions. La construction suivante le relit sur le site en ligne ; à défaut,
elle se rabat sur la construction locale précédente, et si les deux manquent elle
le dit et date tout du jour — le temps d'une construction.

En pratique, corriger un seul site redate une quarantaine d'URL et non 23 842 : sa
fiche, celles des sites voisins qui la citent, sa commune et les communes à moins de
20 km, son département, et les pages de critère où il apparaît.

## Les communes qui ont disparu

Annecy-le-Vieux a fusionné dans Annecy en 2017. Le recensement du ministère ne connaît
plus que « Annecy » : les quatre installations d'Annecy-le-Vieux y sont rattachées à la
commune nouvelle, et l'ancien nom n'apparaît nulle part. Personne, pourtant, n'a cessé
de chercher « piste d'athlétisme Annecy-le-Vieux ».

Le rattachement d'origine est pourtant dans les données, sans qu'il faille aller le
chercher ailleurs : **le numéro d'installation encode le code INSEE de la commune où
elle a été recensée**. `I740110013` porte 74011 — Annecy-le-Vieux — quand le champ
`insee` de la même ligne donne 74010, Annecy. Quand les deux diffèrent, l'installation
est dans une commune qui a fusionné depuis.

Le **nom**, lui, n'est nulle part dans Data ES ; l'[API géo de l'État](https://geo.api.gouv.fr/)
le rend. Comme le millésime des orthophotos, ce service n'est pas indispensable à la
construction : s'il ne répond pas, les fiches restent rattachées à la commune
d'aujourd'hui et rien ne casse.

Sur les 7 167 sites, **43 sont dans une commune fusionnée et 20 anciennes communes ont
pu être nommées** — Annecy-le-Vieux, Cran-Gevrier, Meythet, Seynod, Pierre-Bénite,
Pierrefitte-sur-Seine, Rocquencourt… Les 23 autres n'ont plus de commune déléguée
subsistante : Évry-Courcouronnes n'en a jamais créé, Les Sables-d'Olonne les a dissoutes
en 2019. L'API répond alors 404, et il n'y a pas d'autre nom à afficher — **on se tait
plutôt que d'inventer**.

Chaque commune déléguée nommée reçoit sa page, dans les deux langues, avec la même
mise en page qu'une commune : ses installations, celles à moins de 20 km, et un chapô
qui dit la fusion. La commune nouvelle, elle, gagne une section qui les liste. Une page
de commune déléguée n'a pas de bloc API : l'index est rangé par commune du recensement,
et le recensement ne connaît plus celle-ci.

Deux garde-fous : le slug d'une commune du recensement gagne toujours — deux pages sous
la même URL, c'est la page qui perd — et le fil d'Ariane d'une fiche pointe la commune
qui figure sur son adresse, pas l'ancienne.

## Suivre l'argent public

Le recensement du ministère est déclaratif, et rien n'oblige une commune à le tenir
à jour. Thonon-les-Bains en donne la mesure : le stade de Vongy y est décrit avec deux
terrains de football et des travaux datant de 2012, alors qu'une piste de huit couloirs
homologuée FFA y a été livrée en 2022. L'annuaire ne pouvait pas l'inventer.

Mais une piste, ça se paie. Depuis 2018, tout marché public au-dessus de 40 000 € doit
être publié en données ouvertes : les [DECP](https://data.economie.gouv.fr/) disent qui
a dépensé, quand, combien, et pour quel objet. `scripts/marches_publics.py` les balaie,
croise avec `data/tracks.json`, et rend une file de lecture en trois piles :

- **aucun site d'athlétisme recensé dans cette commune** — le cas Vongy ;
- **des sites, mais aucun avec piste** ;
- **des pistes recensées, mais plus anciennes que le marché** — la fiche est périmée.

**Ce que les DECP ne diront jamais**, et c'est la limite à garder en tête : le nombre de
couloirs, le revêtement, les agrès. L'objet du marché tient en une ligne de majuscules,
`PISTE D'ATHLÉTISME`, et le cahier des charges qui contient les détails vit sur le profil
d'acheteur pendant la consultation puis disparaît — rien ne l'archive, rien ne le
centralise. C'est un instrument de **datation et de détection, pas de description**.

Deux pièges, tous deux vérifiés sur les données :

1. **`lieuexecution_code` mélange codes INSEE et codes postaux.** Annecy saisit `74000`,
   son code postal, là où son code INSEE est `74010` ; Thonon saisit `74200`. Pire, un
   code postal saisi à la place de l'INSEE tombe parfois sur une vraie petite commune à
   l'autre bout du pays — d'où des lignes absurdes, un village de deux cents âmes qui
   refait une piste à 1,4 million. Le script croise donc avec l'**acheteur** (SIRET →
   nature juridique 7210 = commune) et refuse de conclure quand les deux se contredisent.
2. **Le rattachement par code échoue sur Paris, Lyon et Marseille** : le marché porte le
   code de la commune, l'annuaire range ses sites par arrondissement. Un rattrapage par
   le nom retrouve « Lyon 8e Arrondissement » derrière « Lyon ».

Le filet des codes CPV a été essayé puis rangé derrière `--large` : sur la Haute-Savoie
il ajoute des lots de peinture, des pumptracks et des courts de padel, et pas une piste
que l'objet du marché n'avait pas déjà nommée.

```bash
python3 scripts/marches_publics.py --dep 74 --depuis 2022-01-01
python3 scripts/marches_publics.py --depuis 2021-01-01 --montant-min 200000 --json .work/marches.json
```

Aucune ligne n'est une piste tant que personne ne l'a vue. La suite se joue sur le site
de la mairie — voir **[Ce que dit la mairie](docs/ce-que-dit-la-mairie.md)** — sur
l'orthophoto, puis sur place.

## Prévenir les moteurs — IndexNow

Cette datation sert une deuxième fois. Une fois le site déployé, `scripts/indexnow.py`
relit les plans de site **tels qu'ils viennent d'être publiés** et annonce à
[IndexNow](https://www.indexnow.org/) les URL datées du jour : exactement les pages
dont l'empreinte a changé. Bing, Yandex, Seznam et Naver se partagent la notification.
**Google ne lit pas ce protocole** — c'est un signal de plus, pas un remplaçant du plan
de site, et il vise surtout les agents qui s'appuient sur Bing.

L'annonce part **après** le déploiement, jamais avant : annoncer une page qui n'est pas
encore servie apprend au moteur que le signal ment. La clé, servie en clair à la racine
du site, n'est pas un secret mais une preuve de possession du domaine — elle a donc sa
place dans le dépôt, et surtout pas dans un secret GitHub où elle serait invisible à la
relecture tout en restant lisible sur le site.

Quatre situations où le script s'abstient et le dit, plutôt que d'envoyer à l'aveugle :

- **rien n'a changé** — aucune URL datée du jour ;
- **plus de 2 000 URL** — ce n'est plus une notification mais un réindexage. Le journal
  des dates a été perdu, ou le ministère a republié son jeu : arroser un moteur de
  milliers d'URL est le signal qui fait plafonner un domaine, et le plan de site fait
  déjà ce travail ;
- **le fichier de clé n'est pas servi** — l'annonce serait rejetée à l'autre bout ;
- **le site est publié dans un sous-dossier** — le cas d'un fork sur `github.io`, qui
  ne possède pas l'hôte et n'a rien à y annoncer.

Sans `--envoyer`, le script dit ce qu'il enverrait et n'envoie rien :

```bash
python3 scripts/indexnow.py --url https://pistes-athle.com
```

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
framework. Leaflet et Leaflet.markercluster sont servies depuis `assets/vendor/`,
et chargées seulement à la première ouverture d'une carte — voir le README qui s'y
trouve. Aucun script tiers ne s'exécute dans la page.

## Structure du dépôt

```
index.html                  coque de l'application (la version /en/ en est dérivée)
assets/app.js               logique : chargement, filtres, carte, fiches
assets/i18n.js              tous les libellés, français et anglais
assets/style.css            interface mobile-first, thème clair/sombre
assets/page.css             feuille de style des pages statiques
assets/manifest*.webmanifest  PWA, une par langue
assets/vendor/              Leaflet, servi depuis ce dépôt et chargé à la demande
sw.js                       service worker (hors-ligne)
scripts/build_data.py       Data ES + overrides -> data/tracks.json
scripts/build_site.py       -> _site/ : application FR/EN, pages par site, par
                            département, par commune et par critère, sitemaps,
                            robots.txt, llms.txt
scripts/build_api.py        -> _site/api/ : facettes JSON, index compact, openapi.json
api/worker.js               serveur de recherche /api/tracks?... (à déployer, optionnel)
scripts/validate_overrides.py  contrôle des contributions (utilisé par la CI)
scripts/indexnow.py         annonce à IndexNow les pages qui viennent de changer
scripts/optimize_photos.py  redimensionne les photos et efface leur EXIF
scripts/pistes_absentes.py  anneaux OSM que l'annuaire ignore : audit de couverture
scripts/marches_publics.py  marchés publics : les pistes payées mais pas recensées
scripts/lieux_a_regarder.py  toponymie + city-stades BD TOPO -> planches-contact
scripts/conseils_municipaux.py  délibérations des conseils municipaux : file de lecture
scripts/releve_gsc.py       relevé quotidien de la Search Console -> base pistes-athle-seo
scripts/dossier_gsc.py      monte le dossier d'une question relevée, écrit son verdict
scripts/generative_gsc.py   ce que l'IA générative de Google prend au trafic du site
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
