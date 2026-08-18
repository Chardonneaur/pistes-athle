# Étude préalable — existant et cadre juridique

*Réalisée le 18 août 2026, avant l'écriture de la première ligne de code.*

## 1. Est-ce que ça existe déjà ?

Réponse courte : **des morceaux, oui ; l'application recherchée, non.**

| Ce qui existe | Ce que ça couvre | Ce qui manque |
|---|---|---|
| [equipements.sports.gouv.fr](https://equipements.sports.gouv.fr/) (Data ES, ministère) | Le référentiel officiel, tous sports confondus, avec une carte | Outil de gestion territoriale, pas de logique « athlète ». Aucun filtre par agrès, aucune notion de « je veux sauter à la perche ce soir » |
| [Carte des clubs de la FFA](https://www.athle.fr/asp.net/main.clubs/cartepole.aspx) | Les clubs affiliés, et un classement fédéral des stades | Orientée club et compétition. Le classement des installations n'est pas exposé au grand public sous forme exploitable |
| Cartes collaboratives Google My Maps « stades ouverts au public » | Quelques centaines de points, contribution possible | Couverture partielle, données non structurées, non réutilisables, dépendantes d'un compte Google |
| Annuaires généralistes (PagesJaunes, ville-data, sortiraparis…) | Adresses de stades | Aucune information sur les agrès ni le revêtement |
| [nalathletics.com](https://nalathletics.com/) (Royaume-Uni) | Carte d'aires de saut et de lancer avec adresses en 3 mots | Le concept le plus proche… mais limité au Royaume-Uni |
| Apps de suivi de performance (TrackThletics, Stryd, Garmin…) | Entraînement, chronos, puissance | Ne localisent pas d'infrastructures |

**Le créneau libre** : personne ne répond à « montre-moi, dans un rayon de 20 km,
les pistes en synthétique qui ont un sautoir à la perche et un accès libre ». C'est
précisément ce que fait cette application.

**Le complément à surveiller** : OpenStreetMap contient déjà des `leisure=track` +
`sport=athletics` et parfois des `long_jump` / `high_jump`. La couverture y est très
inégale mais la donnée est de meilleure qualité en zone urbaine. Une fusion
OSM × Data ES est la piste d'amélioration la plus évidente pour la suite.

## 2. Peut-on réutiliser légalement les données du ministère ?

**Oui, sans restriction d'usage, y compris commercial, à condition de citer la source.**

### La licence

Le jeu de données [« Recensement des équipements sportifs, espaces et sites de
pratiques »](https://www.data.gouv.fr/datasets/recensement-des-equipements-sportifs-espaces-et-sites-de-pratiques)
est publié par le **Ministère chargé des Sports** sous **Licence Ouverte / Open
Licence version 2.0** (Etalab). C'est confirmé aux deux bouts de la chaîne :

- métadonnée `license: lov2` sur la fiche data.gouv.fr ;
- métadonnée `license: "LICENCE OUVERTE 2.0"` renvoyée par l'API Opendatasoft de
  `equipements.sports.gouv.fr`.

La Licence Ouverte 2.0 accorde le droit de **reproduire, redistribuer, adapter,
transformer, exploiter commercialement** et de combiner avec d'autres sources.
Sa **seule** obligation est la mention de paternité : nom du producteur, source,
et date de dernière mise à jour.

### Comment l'obligation est respectée ici

- Mention sur chaque fiche de site dans l'application (« Source : Data ES —
  Licence Ouverte 2.0 »)
- Écran « À propos » avec les liens vers le producteur et le texte de la licence
- Champ `source` inscrit dans le fichier `data/tracks.json` généré
- Sections dédiées dans le [README](../README.md) et dans [LICENSE-DATA](../LICENSE-DATA)

### Deux points d'attention

1. **Droit *sui generis* des bases de données** — la Licence Ouverte 2.0 couvre
   explicitement ce droit pour les données du ministère : rien à craindre de ce
   côté. En revanche il s'applique pleinement aux annuaires commerciaux : ne jamais
   alimenter le projet en recopiant PagesJaunes ou un site équivalent.
2. **Données personnelles** — le RES contient des SIRET et des noms de propriétaires
   d'installations. Ils sont exclus de l'export publié par ce projet : ils n'ont
   aucune utilité pour un athlète et éviter de les republier simplifie la question
   RGPD.

### Modalités techniques

- API Opendatasoft ouverte, sans clé : `https://equipements.sports.gouv.fr/api/explore/v2.1/…`
- Mise à jour quotidienne côté ministère
- 333 000 équipements au total, dont **9 563** dans la famille « Équipement
  d'athlétisme », regroupés en **7 103 installations** dont **6 500 avec piste**

## 3. Ce que la donnée publique ne dit pas

C'est ce qui justifie l'ouverture aux contributions. Sur les 9 563 équipements
d'athlétisme recensés :

- **903** déclarent une « aire de saut » **sans préciser la discipline**, et
  **381** une « aire de lancer » dans le même flou ;
- seulement **28** mentionnent explicitement la **perche**, **140** la hauteur,
  **211** le poids — des chiffres très en dessous de la réalité de terrain ;
- le revêtement est renseigné pour 90 % des pistes, mais le vocabulaire est
  hétérogène (un seul équipement utilise le mot « Tartan », les autres disent
  « Synthétique (hors gazon) ») ;
- **rien** sur les horaires réels d'ouverture au public, les créneaux réservés aux
  clubs, ou l'état de la piste.

L'architecture retenue en tient compte : les données du ministère forment un socle
reconstruit à chaque déploiement, et les contributions de la communauté sont des
fichiers de surcharge appliqués par-dessus. Rien n'est jamais écrasé à la main
dans le jeu de données publié.
