# Lire une orthophoto : reconnaître les agrès vus du ciel

*Établi le 20 août 2026, en croisant un schéma normalisé d'implantation, une vue
aérienne annotée, et six stades lus sur la BD ORTHO® de l'IGN — dont un stade
dont les agrès sont connus par des photos de terrain, qui a servi d'étalon.*

Ce document sert à produire des `agres_probables` de façon **reproductible et
honnête**. Il ne sert jamais à produire des `agres` : une orthophoto ne prouve
pas qu'un agrès existe encore, ni qu'il est utilisable.

> Rappel du contrat : dès qu'un contributeur voit le site de ses yeux, il écrit
> `agres`, et le build efface les `agres_probables` (`build_data.py`). La
> déduction par imagerie est un pis-aller qui doit s'effacer devant le terrain.

## 1. Où regarder — la géométrie standard

L'implantation d'un stade d'athlétisme est normalisée : on sait **où** chercher
avant de savoir **quoi** chercher.

| Agrès | Emplacement habituel |
|---|---|
| Longueur / triple | couloir d'élan **le long d'une ligne droite**, dans l'anneau, fosse à chaque extrémité |
| Perche | couloir d'élan **parallèle à l'autre ligne droite**, dans l'anneau, matelas au bout |
| Hauteur | **tablier en demi-lune** posé dans un virage, à l'intérieur de l'anneau |
| Poids | **cercle isolé, sans cage**, souvent hors de l'anneau ou en bord de virage |
| Disque / marteau | **cercle sous cage grillagée**, dans un virage ou hors de l'anneau |
| Javelot | couloir d'élan droit de ~30 m, aligné sur le grand axe, lancer vers le terrain |
| Steeple | **corde** de piste qui quitte le tracé du virage, et bac à eau |

Deux conséquences pratiques :

- une forme suspecte **au bon endroit** vaut bien plus qu'une forme suspecte
  ailleurs. Un rectangle beige au milieu du terrain n'est pas une fosse de saut ;
- disque et marteau **partagent cercle et cage**. Une cage ⇒ les deux, jamais un
  seul.

## 2. Quoi regarder — les signatures

Résolution de la BD ORTHO® : **20 cm/pixel**. Un cercle de lancer (2,1 m) fait
donc ~10 px, une fosse de sable (8 × 2,75 m) ~40 × 14 px. Tout est là, mais tout
est petit : il faut recadrer et agrandir, pas regarder la vue d'ensemble.

### Fiable — on peut conclure

**Cage de lancer** → `disque` + `marteau`. C'est la signature la moins
ambiguë : enceinte grillagée en U, panneaux de filet translucides gris-bleu, deux
ailes qui projettent une ombre nette en étoile, cercle pâle au centre. Rien
d'autre dans un stade n'a cette forme.

**Fosse de sable** → `longueur`. Rectangle beige clair franc, contraste fort avec
le gazon, à l'extrémité d'une bande d'élan plus pâle que la pelouse. **Deux
fosses opposées sur un même couloir** ⇒ ajouter `triple`.

**Tablier en demi-lune dans un virage** → `hauteur`. Grande surface de revêtement
de piste (rouge) qui déborde en éventail dans l'anneau, avec un matelas
rectangulaire posé dessus. C'est la forme la plus lisible après la cage.

**Cercle sur dalle carrée, sans cage** → `poids`. Dalle claire de ~3 × 3 m avec
un anneau sombre au centre ; parfois une rangée de plots blancs matérialisant le
secteur de chute.

### Indicatif — on note, on ne tranche pas

**Matelas bâché.** Contre-intuitivement, la bâche est *plus* visible que le
matelas : c'est un rectangle très saturé — vert sapin, bleu vif, blanc — de 5 à
10 m, posé en bord de piste ou sur un tablier. Elle dit qu'**un** sautoir existe,
pas lequel. Deux règles d'arbitrage, à énoncer comme telles :

- matelas **au bout d'une longue bande d'élan** dans l'anneau ⇒ plutôt `perche` ;
- matelas **sur un tablier en éventail** dans un virage ⇒ plutôt `hauteur` ;
- taille : ~6 × 4 m ⇒ hauteur, ~8 × 6 m et plus ⇒ perche.

**Bande d'élan seule**, sans fosse ni matelas : signale un sautoir, sans dire
lequel. À mentionner en `note`, pas en `agres_probables`.

### Non concluant — ne rien inférer

- **Javelot** : le couloir d'élan se distingue mal d'une rampe d'accès. Les deux
  sont des bandes droites qui traversent la piste en biais. Ne pas conclure sans
  arc de lancer visible.
- **Steeple** : le bac à eau se lit s'il est en eau (rectangle sombre net) et si
  la corde de détour est visible ; à sec et sans détour, il disparaît.
- **Triple** sans seconde fosse.
- Tout agrès **rangé hors saison** : les matelas rentrés ne laissent qu'une
  décoloration de la pelouse, indistinguable d'une usure.

## 3. La limite mesurée

Étalonnage sur **Pornic (I441310030)**, dont les six agrès sont établis par
photos de terrain : l'orthophoto n'en fait apparaître que deux (trois matelas
bâchés en bord de ligne droite). Le cercle de poids, la cage de disque et de
marteau — tous photographiés sur place — sont invisibles, hors cadre ou
postérieurs à la prise de vue.

**Le rappel est donc faible : un agrès sur trois environ.** L'absence d'un agrès
sur une orthophoto n'est jamais une information. La méthode ne vaut que dans un
sens : ce qu'on voit, on peut le proposer ; ce qu'on ne voit pas, on se tait.

Deuxième limite, structurelle : la date. Une orthophoto a souvent plusieurs
années (voir l'année affichée sur chaque fiche). Un agrès vu peut avoir été
déposé depuis, un agrès absent peut avoir été construit.

## 4. La méthode, en pratique

```bash
# la même URL que celle servie par l'application, à la résolution native
python3 scripts/ortho.py I440180009
```

1. Repérer l'anneau, ses deux lignes droites et ses deux virages.
2. Recadrer **chaque virage et chaque bord de ligne droite** séparément, et
   agrandir ×3 minimum. La vue d'ensemble ne suffit jamais.
3. Pour chaque forme trouvée : mesurer, la situer dans le tableau du §1, la
   confronter au §2.
4. N'écrire que les agrès des catégories « fiable » et « indicatif ».
5. Écrire ce qu'on a vu dans `note`, en nommant l'indice — pas la conclusion :
   « cage grillagée visible dans le virage sud », pas « il y a un marteau ».

Toute contribution issue de cette méthode porte, en `note`, la mention
**« déduit de l'orthophoto IGN, non vérifié sur place »**.

## 5. Ce que l'orthophoto fait mieux que les agrès

Lire les agrès est le plus difficile. La même image tranche sans effort des
questions **structurelles**, où elle est souvent plus juste que le recensement
du ministère :

- présence, forme et développement de l'anneau (400 m, 333 m, simple ligne droite) ;
- revêtement : le synthétique est rouge saturé et uni, la cendrée brun mat, le
  bitume gris ;
- nombre de couloirs, comptables dans la ligne droite ;
- nature de l'intérieur : gazon, synthétique, plateau bétonné, skatepark ;
- **abandon** : anneau sans marquage, végétation sur la piste, terrain non
  entretenu ;
- coordonnées manifestement fausses (le point tombe sur un toit ou une route).

C'est là qu'il faut commencer un département : les corrections structurelles sont
sûres, les agrès ne le sont pas.
