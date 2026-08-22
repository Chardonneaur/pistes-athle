# Trouver les pistes que le recensement ignore

*Établi entre le 20 et le 21 août 2026, en balayant la Loire-Atlantique puis le
Pays de Retz. Tous les chiffres cités sont des mesures, pas des estimations de
principe : ils sont reproductibles avec les commandes données ici.*

Le [Recensement des Équipements Sportifs](https://equipements.sports.gouv.fr/)
est **déclaratif**. Ce qu'une commune ne déclare pas n'existe pour personne, et
l'application ne peut pas l'inventer. Ce document dit comment chercher ce qui
manque, ce que chaque source voit et ne voit pas, et les sept manières dont la
méthode se trompe — toutes rencontrées en vrai.

## 1. Le cas qui a lancé la recherche

Au Clion-sur-Mer (Pornic), un anneau de quatre couloirs est peint autour du
city-stade, avenue des Sports. Data ES déclare **97 équipements** sur la commune,
répartis en 30 installations. Aucun ne le mentionne : le centre sportif du Clion
y figure avec ses courts de tennis, sa pétanque et son citystade, sans sa piste.

Ce n'est pas un oubli isolé. C'est le régime normal d'une base déclarative pour
un équipement qui ne coûte presque rien, qu'aucune fédération n'homologue et
qu'aucun club ne réclame.

## 2. Quatre sources, et ce que chacune rate

| Source | Voit | Ne voit pas |
|---|---|---|
| **Data ES** (ministère) | ce que les communes déclarent | tout le reste |
| **OpenStreetMap** | ce qu'un contributeur a tracé | les communes où personne n'a cartographié |
| **BD TOPO®** (IGN) | l'implantation, exhaustivement | la fonction : un anneau peint n'est pas un objet |
| **Terrain** | tout | ce qu'on n'a pas eu le temps d'aller voir |

Une source de plus ne remplace pas les autres : **les trois premières ratent les
mêmes petits anneaux**, et il faut les croiser.

### Data ES

`scripts/build_data.py` n'ingère que la famille `Equipement d'athlétisme`. Pour
savoir si une commune déclare *quelque chose* ailleurs, interroger l'API sans ce
filtre :

```bash
curl -s 'https://equipements.sports.gouv.fr/api/explore/v2.1/catalog/datasets/data-es/exports/json?where=new_code%3D%2244131%22&select=inst_nom,equip_nom,equip_type_name,equip_type_famille'
```

### OpenStreetMap

```bash
python3 scripts/pistes_absentes.py 44 --ortho .work/ortho44 --json .work/absentes-44.json
```

Le script liste les tracés de course cartographiés dans OSM, retire ceux qu'un
site de `data/tracks.json` revendique — point tombant dans la boucle, ou à moins
de 150 m — et affiche le reste avec sa commune, son adresse, l'équipement voisin
nommé, l'enceinte scolaire éventuelle, et la vue aérienne cadrée.

Il affiche aussi, depuis le § 5.1, **ce qu'il a écarté et pourquoi**. Sur la
Loire-Atlantique : 174 tracés exploitables, et **268 objets écartés** avant tout
examen. C'est dans ce tas que se cache ce qui manque — le § 5.1 raconte ce qu'on
y a trouvé en allant y voir.

### BD TOPO®

Inventaire IGN indépendant, interrogeable en WFS sur `data.geopf.fr`, couche
`BDTOPO_V3:terrain_de_sport`.

Le piège : `nature="Piste de sport"` + `nature_detaillee="Stade d'athlétisme"`
ne trouve que les grands stades. Sur le Pays de Retz, **les 5 trouvés étaient
déjà tous à l'annuaire**. Le gisement est ailleurs :
`nature="Petit terrain multi-sports"` — 84 objets sur les 38 communes, dont 48
explicitement `City-stade`. C'est autour de ceux-là qu'il faut chercher un
anneau.

```bash
curl -s --get 'https://data.geopf.fr/wfs/ows' \
  --data-urlencode 'SERVICE=WFS' --data-urlencode 'VERSION=2.0.0' \
  --data-urlencode 'REQUEST=GetFeature' \
  --data-urlencode 'TYPENAMES=BDTOPO_V3:terrain_de_sport' \
  --data-urlencode 'OUTPUTFORMAT=application/json' \
  --data-urlencode 'BBOX=-2.10,47.11,-2.08,47.13,CRS:84'
```

> ⚠️ Ne pas passer `SRSNAME` : la requête renvoie alors zéro objet, sans erreur.

### La toponymie

La plupart des complexes sportifs français sont *rue du
Stade*, *rue* ou *avenue des Sports*, ou portent un nom de sportif. Le constat
saute aux yeux dans les résultats de ce balayage : rue du Stade à Guenrouet,
Saint-Lumine-de-Coutais, Saint-Gildas-des-Bois, Cordemais et Arthon-en-Retz ;
avenue des Sports au Clion ; complexes Mickaël-Landreau, Yannick-Noah,
Christophe-Lemaître.

C'est le seul canal qui attrape un complexe dont **rien** n'est tagué.

`scripts/lieux_a_regarder.py` le croise avec les city-stades de la BD TOPO® et
produit directement les planches-contact :

```bash
python3 scripts/lieux_a_regarder.py 44 --deja .work/absentes-44.json \
        --planches .work/planches44 --json .work/lieux-44.json
```

Sur la Loire-Atlantique : 837 lieux au nom parlant dans OSM, 1 075 city-stades
BD TOPO, **706 lieux distincts** une fois retiré ce qui est hors département,
regroupé, et couvert par un site déjà connu à moins de 200 m. C'est une file
d'attente pour l'œil, pas une liste de pistes.

## 3. La méthode, en pratique

1. **Lister** les candidats d'une source (§ 2).
2. **Regarder** chacun sur l'orthophoto IGN. En planches-contact de 6 à 9
   vignettes : une piste se reconnaît à sa forme en une seconde, et 84 vignettes
   se lisent en dix planches.
3. **Trancher** avec la [clé de lecture](lecture-orthophoto.md), § 5 en
   particulier : présence de l'anneau, forme, développement, nature de
   l'intérieur, abandon. Ce sont les questions **structurelles**, celles où
   l'image est fiable.
4. **Vérifier que ce n'est pas déjà connu** autrement (§ 4).
5. **Écrire** la contribution — `CONTRIBUTING.md`, section « Ajouter une piste
   absente » — en portant la mention obligatoire *« déduit de l'orthophoto IGN,
   non vérifié sur place »* et en laissant vide tout ce qu'on ignore.
6. **Y aller**, avec un appareil photo et un décamètre. Rien de ce qui précède
   ne remplace cette étape.

La résolution n'est pas la limite : la BD ORTHO® est à **20 cm/pixel** et c'est
le fond natif. Demander une image plus fine ne fait que du sur-échantillonnage.

## 4. Les sept façons de se tromper

Toutes rencontrées, toutes documentées par un cas réel.

### 4.1 Le tracé OSM ouvert

La piste du complexe Mickaël-Landreau, à Arthon-en-Retz, est taguée
`leisure=track` dans OSM (`way/1429910955`) — et le script ne la voyait pas :
son auteur a arrêté son trait **à 52 m du point de départ**. Exiger une boucle
fermée, condition héritée d'`osm_longueurs.py` où elle est justifiée, éliminait
aussi toutes les lignes droites isolées que le ministère recense pourtant.

*Corrigé* : `traces()` accepte les tracés ouverts et les annonce comme tels.

### 4.2 Le point du ministère tombe à côté

Data ES place son point où il veut dans l'installation — sur le gymnase, à
l'entrée, parfois sur un bâtiment. Deux cas où le candidat n'était pas une piste
absente mais une piste **mal placée**, qui appelle une correction de coordonnées
et non une fiche en double :

- `I440790004` **lycée Briacé du Landreau** : point sur les bâtiments, à 212 m
  de l'anneau ;
- `I440350011` **complexe de la Coutancière** : le ministère déclare « Piste
  d'athlétisme **de la rivière** », OSM trace « Piste **de la Rivière** », 178 m
  d'écart. Le même objet.

**Avant d'ajouter, lire le libellé de l'équipement du site le plus proche.**
C'est ce qui distingue un doublon d'une découverte.

### 4.3 Déjà déclaré, sous un nom qu'on n'attendait pas

`I441610003`, Saint-Gildas-des-Bois, déclare « Piste d'athlétisme » **et**
« Piste d'athlétisme du city stade », aux mêmes coordonnées, à 184 m de l'anneau
OSM. L'installation en déclare deux, l'orthophoto en montre deux : impossible de
savoir laquelle le point désigne. **On n'y touche pas.**

### 4.4 Les faux positifs, toujours les mêmes

Onze des quarante candidats de Loire-Atlantique n'étaient pas des pistes :

| Ce que c'était | Signature à l'image |
|---|---|
| Circuit d'éducation routière | marquage routier, épingle à cheveux, panneaux |
| Pumptrack, BMX | tracé sinueux, bosses, pas de forme fermée régulière |
| Cheminement de parc | largeur irrégulière, courbes libres, mobilier autour |
| Voirie, parking | places matérialisées, débouché sur la route |
| Traces de fauche | parallèles dans un champ, sans revêtement |
| Sous couvert d'arbres | illisible : ne rien conclure, ni dans un sens ni dans l'autre |

### 4.5 L'image et le tag ne datent pas du même jour

- **Saint-Léger-les-Vignes** : OSM trace l'anneau en juillet 2026, l'orthophoto
  date d'avril 2025 et ne montre qu'une dalle nue. L'aménagement est postérieur
  à la prise de vue — on le retient, en le disant.
- **Haute-Goulaine** : OSM annonce `lanes=3` depuis décembre 2022, l'orthophoto
  **postérieure** ne montre aucun anneau. Contradiction non résolue — on ne
  retient pas.

Le millésime de l'orthophoto est affiché sur chaque fiche et rendu par
`build_data.annee_ortho()`. Le comparer à la date de l'objet OSM
(`https://api.openstreetmap.org/api/0.6/way/<id>.json`) est un réflexe à avoir.

### 4.6 Le revêtement ne se lit pas à la couleur

C'est la correction la plus importante apportée à
[`lecture-orthophoto.md`](lecture-orthophoto.md) § 5, qui donne cette lecture
pour sûre. Elle ne tient pas sur les petits anneaux :

- au **Clion-sur-Mer**, la bande est rouge vif ; le contributeur qui l'a foulée
  dit « ça reste du goudron » ;
- au **lycée Briacé du Landreau**, l'anneau est brun-rouge sur l'image et le
  ministère le déclare **bitume**.

L'enrobé coloré est indiscernable du tartan vu du ciel, et c'est justement le
revêtement de cette classe d'équipements. **Ne renseigner `surface` que si OSM
le tague ou si quelqu'un l'a vu.** Décrire la couleur dans `note`, pas dans la
donnée.

### 4.7 La ligne droite dessinée en surface

Le pendant du § 4.1. Un contributeur qui trace une ligne droite en *trait* est
compris ; celui qui la trace en *surface* — un quadrilatère long et étroit,
fermé — ne l'était pas : quatre points, donc « tracé trop grossier », et un
périmètre valant deux fois la longueur. Sur la Loire-Atlantique, 41 objets dans
ce cas, dont 12 assez longs pour compter.

*Corrigé* : `ruban()` reconnaît la forme et rend la longueur, pas le périmètre.
Détail et chiffres au § 5.1.1.

## 5. Deux règles de conduite

### 5.1 Un filtre qui écarte en silence ne se voit pas

C'est la leçon d'Arthon-en-Retz : le script rejetait la piste sans un mot, et
rien dans sa sortie ne signalait qu'il avait rejeté quoi que ce soit. Depuis, il
compte et affiche ses écarts par motif, avec des exemples :

```
268 objet(s) ecarte(s) avant meme d'etre examine(s) :
   139  sport declare autre que l'athletisme
    68  longueur hors des bornes 60-600 m
    55  sautoir ou aire de lancer (tag athletics)
     6  boucle trop grossiere (moins de 8 points)
```

Ce tableau porte déjà la correction du § 5.1.1. Avant elle il annonçait 269
objets, dont 66 « tracés trop grossiers » — et c'est en allant les regarder
qu'on a compris ce qu'ils étaient.

#### 5.1.1 Ce que contenaient les 66 « moins de 8 points »

*Les 66 ont été regardés un par un à l'orthophoto, tracé OSM superposé, le
22 août 2026.* Résultat, et il n'était pas celui qu'on attendait :

- **aucun n'était un anneau.** Le seuil `MIN_POINTS = 8` ne cachait pas une
  seule piste. Sa justification — *« une boucle de quatre ou cinq points est un
  rectangle, l'emprise du stade »* — se vérifie sur les trois seuls objets
  compacts du tas : l'emprise du stade d'athlétisme Muriel-Hurtis à
  Saint-Philbert-de-Grand-Lieu (`way/257351463` — l'anneau réel est tracé à
  l'intérieur), un triangle jeté sur le city-stade de Guenrouet
  (`way/717882302`, dont l'anneau voisin est déjà à l'annuaire), et une aire de
  lancer.
- **mais le tas n'était pas fait de rectangles.** 41 des 66 étaient des **lignes
  droites dessinées en surface** : un quadrilatère long et étroit, fermé, de
  quatre à sept points. Le compte de points les rejetait, et leur « périmètre »
  valait deux fois leur longueur — deux façons de se tromper sur le même objet.
  Or `traces()` accepte déjà la ligne droite quand elle est tracée en *trait*
  (§ 4.1) : c'est le même équipement, recensé par le ministère sous « Piste
  d'athlétisme isolée », perdu pour une question de style de saisie.
- **32 portaient un tag `athletics` de concours** (`long_jump`, `pole_vault`,
  `shot_put`…). Un sautoir n'est pas une piste, et l'objet le dit lui-même : le
  deviner à la taille était inutile.

Le seuil n'était donc pas faux — il était le mauvais critère. Il n'a pas été
abaissé : il a été **précédé** par un critère de forme, `ruban()`. On y cherche
le rectangle qui a la même aire *A* et le même périmètre *P* que la boucle ; sa
longueur vaut `P/4 + √((P/4)² − A)`. Un anneau n'a pas de solution — il enferme
plus d'aire qu'aucun rectangle de ce périmètre. Une emprise de stade en donne
une large. Une ligne droite en donne une étroite, et c'est sa longueur, pas son
périmètre. Un garde-fou complète : une ligne droite tient dans la diagonale de
sa boîte englobante, un sentier qui revient sur lui-même non.

Sur la Loire-Atlantique, ce changement fait passer le balayage OSM de 164 à 174
tracés exploitables : 7 lignes droites de plus rattachées à un site connu, et
**3 candidats de plus à regarder**, tous loin de tout site déclaré — Mouzeil
(`way/380425880`), Le Loroux-Bottereau (`way/1094046972`), Cordemais
(`way/188079241`). Le tas des « moins de 8 points » tombe de 66 à 6.

### 5.2 Une fiche n'affirme que ce que quelqu'un a déclaré ou vu

Un blanc n'est pas un « Non ». Une estimation n'est pas une mesure. Un site créé
par la communauté n'a pas de cases à cocher : ses booléens valent faux **par
défaut de saisie**, et la fiche ne les affiche donc pas. `longueur_probable`
plutôt que `longueur_piste`, `agres_probables` plutôt que `agres`, et rien du
tout quand on ne sait pas.

## 6. Ce que ça a donné

### Loire-Atlantique — balayage OpenStreetMap

| | |
|---|---:|
| Objets OSM reçus | 471 |
| Tracés exploitables | 164 |
| Déjà revendiqués par l'annuaire | 147 |
| Sans correspondance, examinés à l'orthophoto | 40 |
| → **pistes ajoutées** | **25** |
| → corrections de coordonnées | 2 |
| → déjà déclaré autrement | 1 |
| → faux positifs | 11 |

*Chiffres du balayage d'août 2026, avant le § 5.1.1 : le même balayage sort
aujourd'hui 174 tracés exploitables et trois candidats de plus.*

### Pays de Retz — balayage BD TOPO® des city-stades

38 communes (Pornic Agglo, Sud Retz Atlantique, Sud Estuaire, Grand Lieu).

| | |
|---|---:|
| « Stades d'athlétisme » BD TOPO | 5 — *tous déjà connus* |
| Petits terrains multi-sports examinés | 84 |
| → **pistes ajoutées** | **3** |
| Piste signalée par un lecteur, retrouvée dans OSM | 1 (Arthon-en-Retz) |

Les trois pistes trouvées par ce balayage — Saint-Philbert-de-Grand-Lieu
(complexe des Grenais), Touvois, Domaine du Collet aux Moutiers-en-Retz —
n'existent **ni dans Data ES ni dans OpenStreetMap**. Aucun outil interrogeant
l'une de ces deux bases ne pouvait les sortir.

## 7. Ce qui reste à faire

Suivi dans les [issues du dépôt](https://github.com/Chardonneaur/pistes-athle/issues),
étiquette `couverture`.

- [x] Outiller le canal toponymique — `scripts/lieux_a_regarder.py` ([#1](https://github.com/Chardonneaur/pistes-athle/issues/1))
- [ ] **Lire les 706 planches-contact de la Loire-Atlantique** ([#1](https://github.com/Chardonneaur/pistes-athle/issues/1))
- [x] Regarder les 66 tracés écartés pour « moins de 8 points » — § 5.1.1 ([#2](https://github.com/Chardonneaur/pistes-athle/issues/2))
- [ ] Aller voir les 3 lignes droites que `ruban()` a fait sortir (§ 5.1.1)
- [ ] Étendre le balayage aux départements voisins ([#3](https://github.com/Chardonneaur/pistes-athle/issues/3))
- [ ] Mesurer au décamètre les développements estimés ([#4](https://github.com/Chardonneaur/pistes-athle/issues/4))

---

*Sources et licences : Data ES, ministère chargé des Sports, Licence Ouverte
2.0 · © les contributeurs d'OpenStreetMap, ODbL · © IGN — BD ORTHO® et
BD TOPO®, Licence Ouverte 2.0 · Base Adresse Nationale, Licence Ouverte 2.0.*
