# Trouver l'horaire d'ouverture d'une piste

## Pourquoi ce champ et pas un autre

Le 2 septembre 2026, sur 7 287 fiches, **neuf portaient un horaire** — 0,12 %. Ce
n'est pas un oubli de saisie : c'est qu'aucune donnée ouverte ne le publie. Data
ES ne connaît pas le champ. OpenStreetMap ne le porte presque jamais sur un
stade. Les délibérations des conseils municipaux ont été mesurées à **zéro fait
écrivable sur 167 communes** (`ce-que-dit-la-mairie.md`).

Or c'est ce que les gens demandent. Sur les requêtes que la Search Console
nomme, celles qui produisent des clics sont exploratoires — « piste athlétisme
castelginest » (CTR 29 %), « piste athlétisme libre d'accès » (position 4,
CTR 100 %) — jamais un nom de stade. Et les pages par critère, qui répondent à
« où et quand puis-je courir », ont **6,58 % de CTR contre 2,87 % pour les
fiches**, avec 42 pages contre 1 027.

Un horaire est donc le fait le plus rentable que ce site puisse écrire. C'est
aussi le plus dangereux : **un horaire faux est pire qu'un champ vide**, parce
qu'il envoie quelqu'un devant un portail fermé.

## Le canal qui rend

Ce n'est pas la délibération, c'est la **fiche d'équipement** que beaucoup de
villes publient dans leur annuaire. Sur 36 stades cherchés à la main le
2 septembre 2026, **neuf ont rendu un horaire — un sur quatre**.

`scripts/horaires_municipaux.py` en est la moitié bête : il trouve les pages,
en extrait les plages horaires avec leur phrase, les classe, et **n'écrit dans
aucune fiche**.

```bash
python3 scripts/horaires_municipaux.py I940160010
python3 scripts/horaires_municipaux.py 94 --limite 20 --json .work/horaires-94.json
```

### Trois canaux, du plus sûr au moins sûr

1. **La recherche WordPress** (`/wp-json/wp/v2/search`). C'est le meilleur, et
   pour une raison de fond : la page cherchée n'est presque jamais liée depuis
   l'accueil. Cachan range ses fiches sous `/annuaire-des-equipements/`,
   Challans sous `/point-d-interet/`, Saint-Médard sous `/points-interets/` —
   aucune n'apparaît dans les 32 liens de la page d'accueil de sa commune.
2. **L'URL devinée** : `<base>/<préfixe>/<nom-en-slug>/`, douze préfixes
   relevés à la main. C'est ce qui rattrape Cachan, dont le `wp-json` existe
   mais n'expose pas ce type de contenu.
3. **L'exploration** en profondeur 2 depuis l'accueil, en dernier recours.

## Le piège qui commande tout le reste

Sur les 36 stades cherchés à la main, il a fallu **écarter autant d'horaires
qu'on en a écrit** : ceux de l'accueil administratif de la mairie. « Lundi
14h-17h, mardi 8h30-12h30 et 14h-17h », c'est le secrétariat de Maurepas, pas
son parc des sports — et un agrégateur l'affichait comme l'horaire du stade.
Même piège à Franconville, Ermont, Feyzin, Troyes et Rosny.

Le classement écarte donc par défaut, et n'admet que ce qui porte un signe
positif :

| règle | pourquoi |
|---|---|
| un mot de mairie près de la plage → **écarté** | guichet, accueil, état civil, CCAS, urbanisme |
| pas de mot d'installation autour → **écarté** | piste, stade, terrain, gymnase, complexe |
| pas de mot d'ouverture ou d'accès → **écarté** | un tableau nu est un planning d'activités |
| pas de jour cité → **écarté** | une plage sans jour ne dit pas quand elle vaut |
| forme de journée de bureau → **écarté** | dans 8h-18h45, sans week-end |

Les deux fenêtres ne servent pas à la même chose. Ce qui **disqualifie** se lit
au plus près (220 caractères) : un « accueil de la mairie » six cents
caractères plus loin ne dit rien de cette plage-ci. Ce qui **qualifie** se lit
large (700 caractères), parce qu'un intitulé « Horaires d'ouverture de la piste
d'athlétisme au public » chapeaute souvent cinq ou six plages.

La forme de journée de bureau ne condamne jamais seule — une piste peut
n'ouvrir que de 9h à 17h. Elle n'est qu'un motif parmi cinq, et tout ce qui est
écarté reste affiché, pour qu'on puisse vérifier qu'on n'écarte pas trop.

## Ce que le script ne sait pas faire

**L'agglomération n'est pas explorée.** L'annuaire DILA donne le site de la
*mairie*. Or l'équipement est souvent géré par l'intercommunalité, qui a son
propre site : les horaires de Beauvais sont sur `beauvaisis.fr`, ceux de
Clamart dans un règlement intérieur de Vallée Sud - Grand Paris, ceux d'Ermont
et de Franconville sur `valparisis.fr`. Un silence d'ici veut dire « rien sur
le site de la mairie », **pas** « rien n'existe ».

**Certaines communes interdisent la visite, et c'est leur droit.** Beauvais et
Chamalières tournent sur un CMS dont le `robots.txt` porte `Disallow: /` pour
`User-agent: *`. Le script obéit et se tait — alors que leurs horaires sont
publics et ont été trouvés à la main le même jour.

**Une page peut mélanger deux équipements.** La fiche du complexe Robert
Monseau à Saint-Médard porte aussi le tableau horaire de la piscine. C'est la
règle « un mot d'ouverture en plus d'un mot de lieu » qui fait tomber le
tableau nu ; elle ne suffira pas toujours.

## Contrôle de recall, 2 septembre 2026

Six communes dont on savait, par une recherche à la main, qu'elles publient un
horaire :

| commune | résultat |
|---|---|
| Cachan | trouvé, par URL devinée |
| Gap | trouvé, par recherche WordPress |
| Saint-Médard-en-Jalles | trouvé — et plus riche que ce qui avait été écrit à la main : la page porte un planning saisonnier de la piste |
| Nice | la bonne page trouvée, mais l'extrait retenu est un avis de fermeture de tunnel |
| Beauvais | `robots.txt` interdit la visite |
| Chamalières | `robots.txt` interdit la visite |

Et un contrôle négatif : **Challans**, dont la page municipale annonce une mise
à disposition sans donner d'heures, ne rend rien — ce qui est le bon résultat.

## Ce qu'on en fait ensuite

La sortie est une **file de lecture**, pas un fait. Chaque candidat porte son
URL et sa phrase : il faut vérifier que la page parle bien de *cette*
installation, puis écrire dans `data/overrides/<id>.json` selon les règles de
la compétence `contribution-piste` — `horaires` pour la plage, `acces_note`
pour la réserve qui l'accompagne, `url` pour la page, et la source citée avec
sa date dans `note`.

Trois erreurs à ne pas commettre, toutes rencontrées le 2 septembre 2026 :

- **recopier l'horaire de l'accueil de la mairie.** C'est le piège principal.
- **écrire l'horaire d'une autre installation de la même commune.** Issy publie
  des créneaux publics pour la *Cité des Sports* ; le *Parc Municipal des
  Sports* est une autre fiche, à une autre adresse.
- **figer un horaire saisonnier.** La Ville de Paris publie les siens par
  périodes de quelques semaines. Les recopier les rendrait faux le mois
  suivant : la fiche renvoie à la page officielle et n'écrit que ce qui est
  stable.
