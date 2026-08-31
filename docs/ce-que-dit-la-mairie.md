# Ce que dit la mairie

*Établi le 23 août 2026, en ouvrant le concept sur cinq communes de
Loire-Atlantique. Les chiffres cités sont ceux d'un échantillon de cinq
communes : ils disent que le chemin est praticable, pas encore ce qu'il rend à
l'échelle d'un département.*

> **Mesuré le 31 août 2026 sur 167 communes — et le rendement est nul.**
> Voir « [Ce que ça rend vraiment](#ce-que-ça-rend-vraiment-167-communes) » en fin
> de document avant de lancer une campagne. Le chemin est praticable, comme
> annoncé ; ce qu'il transporte ne remplit aucun champ.

Le [Recensement des Équipements Sportifs](https://equipements.sports.gouv.fr/)
décrit un **état**, et le décrit lentement. Il ne dit jamais qu'une piste vient
d'être refaite, qu'un sautoir a été commandé, qu'une enceinte a rouvert. Ces
choses-là, une seule source publique les porte, et elle les **date** : la
délibération du conseil municipal.

C'est ce que fait `scripts/conseils_municipaux.py`. Il ne remplit aucun champ.
Il fabrique une file de lecture.

```bash
python3 scripts/conseils_municipaux.py I441870004      # un site
python3 scripts/conseils_municipaux.py 44187           # une commune, par son code INSEE
python3 scripts/conseils_municipaux.py 44 --limite 20  # un departement, par tranches
```

## 1. Le chemin, entièrement en données ouvertes

Trois maillons, aucun compte à créer, aucune clé d'API.

### L'annuaire de l'administration

La DILA publie sur `api-lannuaire.service-public.fr` une fiche par mairie :
site internet, courriel, téléphone, horaires d'ouverture, le tout indexé par
code INSEE. C'est lui qui remplace la recherche à la main du site de la commune.

Sur les cinq communes de l'échantillon, **cinq avaient un site internet
renseigné**. C'est le maillon le plus solide de la chaîne.

### Le code INSEE, déjà dans nos identifiants

Il n'y a rien à géocoder pour un site du recensement : son identifiant *est*
composé du code INSEE. `I441870004` → `44187`, Saint-Père-en-Retz. Vérifié sur
toute la base. Seules les pistes contribuées (`c-…`), qui n'ont pas
d'identifiant ministère, demandent un appel à `geo.api.gouv.fr`.

### Le site de la commune

Ordres du jour, convocations, listes de délibérations, procès-verbaux :
presque toujours en PDF. Deux façons de les atteindre, dans cet ordre :

- **l'API des médias de WordPress** (`/wp-json/wp/v2/media?search=…`), quand la
  commune tourne sous WordPress — ce qui est fréquent. Elle liste les fichiers
  sans qu'on ait à explorer une seule page, et donne leur date de publication.
- **l'exploration des pages**, sinon : on suit les liens dont le texte ou
  l'adresse parle du conseil municipal, sur deux niveaux, quarante pages au
  maximum, en respectant `robots.txt`.

Sur les cinq communes, quatre publiaient des actes atteignables ainsi. La
cinquième, Aigrefeuille-sur-Maine, n'en publie aucun que l'exploration trouve.

## 2. Ce que le script cherche dans un PDF

Trois vocabulaires, qui ne pèsent pas le même poids.

| Vocabulaire | Exemples | Suffit seul ? |
|---|---|---|
| **piste** | athlétisme, cendrée, tartan, sautoir, lancer du poids, couloirs de course | **oui** — ces mots ne parlent que de nous |
| **stade** | stade, terrain d'honneur, équipements sportifs, vestiaires, tribunes | non |
| **travaux** | réfection, rénovation, maîtrise d'œuvre, DETR, déclassement, appel d'offres | non |

Un mot de **stade** ne compte qu'accompagné d'un mot de **travaux** : sans quoi
toute subvention au club de football remonterait. Le nom propre du stade, réduit
à ce qui l'identifie (« Complexe Sportif du Parc du Grand Fay » → « grand fay »),
obéit à la même règle — et pour une bonne raison, § 4.2.

## 3. Trois silences qui ne se valent pas

C'est le point qui décide de l'honnêteté de l'outil. Un écran vide peut vouloir
dire trois choses très différentes, et le script les nomme séparément :

1. **la commune n'a rien voté** — *n actes lus, séances du … au …, rien sur le
   stade*. C'est le seul silence qui apprenne quelque chose, et encore : il ne
   porte que sur les séances effectivement lues.
2. **la commune n'a rien publié** — pas de site, ou pas d'acte en PDF. On ne
   sait rien du tout.
3. **la commune a publié des PDF scannés** — pas de couche texte, rien à
   chercher dedans. Sur l'échantillon, **douze fichiers** dans ce cas, dont les
   deux listes de délibérations de la séance du 28 mai 2026 à Saint-Père-en-Retz.
   Le script les affiche avec leur URL et dit qu'il n'en sait rien : ils
   restent à ouvrir à l'œil.

C'est pourquoi la sortie annonce toujours **ce qui a été lu** avant ce qui a été
trouvé. « Rien voté » ne s'écrit jamais ; « rien voté aux séances des 2, 20 et
26 mars, 2 avril et 29 juin 2026 » s'écrit.

## 4. Les façons de se tromper

### 4.1 Une délibération dit un projet, pas un état

C'est la règle qui prime sur tout le reste, et elle prolonge le § 5.2 de
[trouver-les-pistes-manquantes.md](trouver-les-pistes-manquantes.md).

Un conseil municipal qui vote la réfection d'une piste vote une **intention**,
avec un calendrier qui glissera. Rien de ce que ce script trouve n'a sa place
dans un booléen, ni dans `renovation`, ni dans `surface`. Cela se raconte dans
`note`, avec la date de la séance et l'URL du document, et cela ne devient un
état que le jour où quelqu'un va voir.

### 4.2 Un toponyme désigne rarement une seule chose

À Ancenis-Saint-Géréon, « la Davrays » nomme le stade **et** la résidence pour
personnes âgées. Quatre délibérations du CCAS remontaient à ce titre — désignation
des membres de la commission d'admission, forfait autonomie, subvention CARSAT.
Aucune ne parle du stade.

D'où la règle du § 2 : le nom propre ne vaut qu'accompagné d'un mot de travaux.
Elle a fait disparaître les quatre.

### 4.3 Les mots courants du vocabulaire administratif

`marché` attrapait le marché d'approvisionnement du samedi matin, et sa
délégation de service public. Le lexique n'accepte donc plus que `marché
public`, `marché de travaux`, `marché de maîtrise`. Même prudence pour
`cession` et `acquisition`, qui ne comptent que suivis d'un complément.

### 4.4 La même délibération publiée cinq fois

Les mairies republient : `LISTE-DES-DELIBERATIONS.pdf`,
`LISTE-DES-DELIBERATIONS-1.pdf`, `-2`, `-3`, le même acte déposé en juin puis
en juillet. Le nom du fichier ne suffit donc ni à nommer la copie locale — deux
URL différentes s'écrasaient l'une l'autre dans le cache, et le même extrait
sortait dix fois — ni à reconnaître un doublon : c'est l'empreinte du texte
extrait qui tranche.

### 4.5 La date de séance n'est pas la date de publication

Un acte de la séance du 28 mai paraît le 15 juin. La date affichée est donc lue
dans le texte du document (« … EN CONSEIL MUNICIPAL DU 29 JUIN 2026 »), et le
nom du fichier ne sert qu'à défaut. Attention : `pdftotext -layout` colle
volontiers la première lettre de la ligne suivante au dernier mot d'une ligne
— on lit « du 29 juinl 2026 ». Les mois sont donc reconnus par leur début, pas
par le mot entier.

## 5. Ce que ça a donné

### Saint-Père-en-Retz — le stade du Parc du Grand Fay

Dix actes lus, séances du 2 mars au 29 juin 2026. **Aucune délibération sur la
piste**, sa réfection ou des travaux d'athlétisme. Les seules décisions touchant
aux équipements sportifs : deux conventions d'utilisation des équipements
sportifs communaux, avec le LEAP Saint-Gabriel Nantes Océan et avec la MFR,
approuvées à l'unanimité le 29 juin 2026 — sans que le document publié précise
quels équipements sont concernés.

Ce silence ne prouve rien à lui seul. Mais il ne contredit pas ce que la visite
du 23 août 2026 a constaté : une cendrée sans plus une seule ligne de couloir,
une ligne droite envahie de chardons, un bac de saut colonisé par l'herbe.

### Abbaretz — le stade municipal

Dix actes lus, séances du 19 septembre 2024 au 9 juillet 2026. Quatre passages,
dont trois qui parlent bel et bien du site, datés et sourcés : un avenant de 6 988 €
HT pour des tuyaux et regards au terrain en herbe du stade municipal (séance du
5 juin 2025), la finalisation des travaux du terrain de football (22 janvier
2026), un problème d'arrosage sur ce même terrain (11 juin 2026). Rien sur
l'anneau lui-même.

C'est le régime normal : le conseil parle du terrain de football, presque jamais
de la piste qui l'entoure. Une piste qui apparaît dans une délibération est
précisément l'événement qu'on cherche.

## 6. Ce qui reste à faire

- **Les PDF scannés.** Douze sur l'échantillon. Un OCR les ouvrirait, au prix
  d'une dépendance lourde et de fautes de lecture — à peser.
- **Les procès-verbaux, plutôt que les listes de délibérations.** La liste donne
  le titre voté ; le procès-verbal donne le débat, les montants, le calendrier.
  Abbaretz publie les deux, Saint-Père-en-Retz seulement la liste.
- **L'intercommunalité.** Un complexe sportif transféré à la communauté de
  communes ne passe plus en conseil municipal. Le script ne regarde pas encore
  de ce côté.
- **La périodicité.** Une délibération vaut le jour où elle est prise. Repasser
  sur les communes qui portent une piste, deux ou trois fois par an, est ce qui
  ferait de ce script autre chose qu'une curiosité.

---

Annuaire de l'administration, DILA — Licence Ouverte 2.0.
Base officielle des codes géographiques / geo.api.gouv.fr — Licence Ouverte 2.0.
Les délibérations restent la propriété des communes : on n'en cite que des extraits,
avec leur source.


## Ce que ça rend vraiment (167 communes)

Le paragraphe d'ouverture disait ne pas savoir ce que le chemin rendrait à
l'échelle. On sait maintenant. Le 31 août 2026, le script a été passé sur les
**167 communes** que désignait la file Search Console.

| | | |
|---|---|---|
| site de la mairie trouvé via l'annuaire DILA | 166 | **99 %** |
| actes PDF effectivement lus | 70 | 41 % |
| au moins un signal « stade » | 38 | 22 % |
| signaux parlant d'athlétisme ou de piste | 19 sur 326 | **5 %** |
| **faits écrivables dans une fiche** | **0** | **0 %** |

Pourquoi les autres se taisent : 84 communes ne publient aucun acte en PDF
(`robots.txt`, ou pas de rubrique), 12 n'en publient aucun de lisible, 1 n'a pas
de site connu de l'annuaire.

### Ce n'est pas un défaut du script, c'est la nature de la source

Les 19 signaux athlétisme étaient des subventions à des clubs, un transfert de
compétence intercommunale, une piste de VTT autour d'un city-stade, un terrain de
football synthétique. Aucun horaire, aucun revêtement, aucun agrès, aucune
condition d'accès.

C'est exactement ce que ce document annonce plus haut : **une délibération dit un
projet voté, pas un état constaté**. Elle est faite pour *dater un changement*. Or
les fiches ne manquent pas de dates — elles manquent d'états : un horaire affiché
sur un portail, un revêtement foulé, une enceinte trouvée ouverte un dimanche.

### L'OCR ne change rien

267 PDF scannés restaient illisibles, et il était tentant d'y voir le gisement
caché. Testé sur quatre communes : 42 PDF rendus lisibles, 12 signaux, **zéro sur
l'athlétisme**, et un texte de qualité médiocre (« *A devis TTC : Fonctionnement a
ferecementdescrang* »). Le silence est réel, pas caché. Inutile de refaire
l'expérience.

### Ce qu'il faut en garder

- **Ne pas relancer une campagne** sur ce canal pour combler `horaires`, `surface`,
  `agres` ou `acces_libre`. Le rendement mesuré est nul, et la raison est
  structurelle.
- **L'usage ciblé reste bon** : interroger une commune précise quand on soupçonne
  des travaux récents que Data ES ignore encore. C'est ce pour quoi le script a été
  écrit, et il le fait bien.
- **Le contact de la mairie sort à 99 %** — site, courriel, téléphone. C'est le seul
  rendement fiable. Attention : ce n'est pas le contact de l'installation, et
  écrire l'un pour l'autre serait faux.
