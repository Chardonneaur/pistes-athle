# Relever la Search Console

Ce que les gens tapent dans Google avant d'arriver ici est la seule mesure
directe de ce qu'ils cherchent et que le site ne leur donne pas encore. Ce
document décrit la boucle qui transforme ces requêtes en travail, et surtout
ce qu'elle s'interdit.

## Deux étages, et pourquoi ils sont séparés

**L'étage 1 — le relevé.** `scripts/releve_gsc.py`, tous les jours à 7 h par
[`releve-gsc.yml`](../.github/workflows/releve-gsc.yml). Il lit la Search
Console, calcule une clé stable par question, l'écrit dans la base
`pistes-athle-seo`. Il ne juge rien, ne touche aucune fiche, n'envoie aucun
message. Du code déterministe, sans modèle.

**L'étage 2 — le traitement.** Un agent lit la file préparée, cherche des
sources, ouvre une pull request. C'est là qu'il y a du jugement, donc de
l'erreur possible, donc une relecture humaine. Il est lui-même coupé en deux :
[`scripts/dossier_gsc.py`](../scripts/dossier_gsc.py) monte le dossier et écrit
le verdict — du code, aucun jugement — et la compétence
[`traitement-gsc`](../.claude/skills/traitement-gsc/SKILL.md) porte les règles
de ce qu'on a le droit d'écrire.

La coupure n'est pas cosmétique. La mémoire de la boucle doit être la pièce la
plus fiable du montage : le jour où l'agent ne tourne pas, le relevé, lui, doit
avoir eu lieu. Une requête apparue ce jour-là et jamais relevée est perdue pour
de bon — et c'est exactement ce que la table sert à empêcher.

## Une ligne par question, pas par formulation

La clé est `<cible>|<intention>`.

- **cible** : déduite de la page d'atterrissage, que Google fournit déjà. Un
  identifiant de fiche (`I591830081`), `ville:<slug>`, `dep:<code>`,
  `critere:<chemin>`, ou `inconnu`. On ne devine jamais la commune dans le
  texte de la requête : les homonymes et les stades qui ne portent pas le nom
  de leur ville n'ajouteraient que des erreurs à un appariement déjà fait.
- **intention** : la famille de la question — `revetement`, `couvert`, `acces`,
  `horaires`, `tarif`, `agres`, `distance`, `contact`, `photos`, plus deux cas
  de repli qui sont en réalité les plus fréquents : `fiche` et `existence`.

« piste tartan lorient », « revêtement stade lorient » et « lorient piste
synthétique ? » donnent une seule clé. Sans cela, la longue traîne rouvrirait
chaque matin un dossier déjà traité — elle reformule sans fin, elle ne demande
pas autre chose. C'est cette normalisation qui rend tenable le déclenchement
**dès la première impression** : ce n'est pas le volume qui filtre, c'est la
mémoire.

## Ce que le relevé voit, et ce qu'il ne verra jamais

Constaté le 29 août 2026, sur `sc-domain:pistes-athle.com` :

| | |
|---|---|
| couples (requête, page) sur tout l'historique | **179** |
| questions distinctes après normalisation | **146** |
| dont « le nom d'un stade tapé tel quel » (`fiche`) | **130** |
| impressions nommées par Google | **325** |
| impressions réelles | **2 060** |

Deux faits à garder en tête. D'abord, **84 % des impressions viennent de
requêtes que Google refuse de nommer** : il anonymise les requêtes rares, et
aucune configuration ne lève ce plafond. La boucle travaille sur la partie
émergée, par construction. Ensuite, une fenêtre d'un seul jour rend **zéro
ligne** : Search Console accuse deux à trois jours de latence. D'où la fenêtre
glissante de sept jours, relevée quotidiennement.

## La dépense : zéro, et pourquoi ce n'est pas une promesse

C'est la question qui a failli faire abandonner le projet. Réponse détaillée,
poste par poste.

### Google — aucune facturation possible

L'API Search Console **n'a pas de tarif**. Elle n'est pas une API facturable :
dépasser ses quotas rend une erreur `429`, jamais une ligne de facture. Le
projet Google Cloud `piste-athle` n'a pas besoin d'un compte de facturation, et
**ne doit pas en avoir un** — c'est la garantie structurelle, vérifiable en une
minute sur `console.cloud.google.com/billing`. Sans compte de facturation
rattaché, Google ne peut rien prélever, quoi que fasse le script.

Consommation réelle : **un appel d'API par jour**. Le quota est de 1 200 par
minute.

### Cloudflare — le plan gratuit échoue, il ne facture pas

Le compte est sur le plan gratuit (c'est déjà écrit dans
[`logs/README.md`](../logs/README.md), à propos des 100 000 requêtes/jour du
Worker). Sur ce plan, atteindre une limite provoque une **erreur**, pas un
dépassement facturé. Les limites D1 sont de 5 Go de stockage, 5 millions de
lignes lues et 100 000 écrites par jour ; un passage en écrit quelques
dizaines, dans une base qui pèse quelques dizaines de kilo-octets.

Les écritures sont groupées par onze lignes : l'API D1 refuse plus de cent
paramètres liés par requête, et neuf colonnes par ligne en consomment
quatre-vingt-dix-neuf. Cette limite ne se voit pas en local — `wrangler`
interpole les valeurs au lieu de les lier — elle n'apparaît qu'à travers
l'API HTTP.

Le jeton d'API doit être créé avec **la seule permission `D1:Edit`**, et rien
d'autre : même compromis, il ne donne accès ni au DNS, ni aux Workers, ni au
domaine.

### GitHub Actions — gratuit et illimité

Le dépôt est public : les minutes ne sont ni comptées ni facturées. Le job est
malgré tout borné à `timeout-minutes: 5`.

### Les butoirs dans le script

Ce ne sont pas des optimisations, ce sont des arrêts nets. Le script quitte
avec un message plutôt que de continuer « juste un peu ». Ils sont deux ordres
de grandeur au-dessus du besoin constaté, et ne servent que le jour où quelque
chose dérape — une boucle qui se relance, un paramètre erroné.

| butoir | valeur | usage réel constaté |
|---|---|---|
| `MAX_APPELS_GSC` | 6 par exécution | 1 |
| `MAX_LIGNES` | 50 000 | 179 |
| `MAX_REQUETES_D1` | 120 par exécution | 14 |

## Mettre en place

Les identifiants Google existent déjà (`~/.config/gsc-mcp/token.json`, créé
pour le serveur MCP). Il suffit de les recopier en secrets du dépôt, plus un
jeton Cloudflare.

*Settings > Secrets and variables > Actions > New repository secret* :

| secret | où le trouver |
|---|---|
| `GSC_CLIENT_ID` | `client_id` dans `~/.config/gsc-mcp/token.json` |
| `GSC_CLIENT_SECRET` | `client_secret`, même fichier |
| `GSC_REFRESH_TOKEN` | `refresh_token`, même fichier |
| `CF_ACCOUNT_ID` | `npx wrangler whoami` |
| `CF_API_TOKEN` | à créer, permission `D1:Edit` seule |

L'identifiant de la base n'est pas un secret : il est en clair dans le
workflow, comme celui du journal des robots l'est dans `logs/wrangler.jsonc`.
Sans jeton, il ne donne accès à rien.

### L'application OAuth doit rester « En production »

C'est le piège qui a arrêté la boucle pendant deux jours, du 30 au 31 août 2026,
et rien dans ce document ne prévenait.

Une application OAuth dont l'écran de consentement est resté en mode **« Test »**
reçoit des refresh tokens qui **expirent au bout de sept jours**. Pas d'alerte,
pas de préavis : le huitième jour, Google répond `400` et le relevé s'arrête.
Le symptôme est celui d'un jeton révoqué, et il envoie chercher au mauvais
endroit — le jeton n'a pas été révoqué, il a atteint sa date.

Le projet `piste-athle` est donc publié **« In production »**, sur
[Google Auth Platform > Audience](https://console.cloud.google.com/auth/audience?project=piste-athle).
Il doit le rester. En production, le refresh token n'expire plus ; il ne meurt
que révoqué à la main, ou après six mois sans usage — le relevé tourne tous les
jours, ce cas ne se présentera pas.

Trois choses à savoir le jour où il faut ré-autoriser :

- Le bouton **Publish app** est sous *Google Auth Platform > Audience*, et non
  plus sous *APIs et services*. Il reste grisé tant que la page **Branding** ne
  porte pas la page d'accueil (`https://pistes-athle.com`), le lien de
  confidentialité (`https://pistes-athle.com/confidentialite/`) et le domaine
  autorisé (`pistes-athle.com`). Le formulaire ne dit pas lesquels manquent.
- La portée `auth/webmasters` est **sensible**, donc l'écran
  « Google n'a pas validé cette application » s'affiche à chaque autorisation.
  C'est attendu et sans conséquence : publier ne demande aucune vérification,
  seule la levée de cet écran en demanderait une. *Paramètres avancés* >
  *Accéder à Pistes Athlé*.
- **Publier ne ressuscite pas un jeton déjà mort.** Il faut refaire
  `uv run --directory ~/gsc gsc-mcp auth`, puis repousser le secret :

```bash
python3 -c "import json;print(json.load(open('$HOME/.config/gsc-mcp/token.json'))['refresh_token'],end='')" \
  | gh secret set GSC_REFRESH_TOKEN
```

La sortie de secours, si l'écran de consentement redevient un jour bloquant :
un **compte de service** ajouté comme utilisateur de la propriété dans Search
Console. Pas de consentement, pas d'expiration. Le serveur MCP le gère déjà
(`GSC_SERVICE_ACCOUNT`) ; `scripts/releve_gsc.py`, lui, ne sait faire que le
flux refresh token — il faudrait lui ajouter le JWT.

## S'en servir à la main

```bash
python3 scripts/releve_gsc.py --simulation   # lit Google, n'écrit rien
python3 scripts/releve_gsc.py                # fenêtre de 7 jours
python3 scripts/releve_gsc.py --amorcage     # tout l'historique, une fois
```

Sans variables d'environnement, le script retombe sur le jeton du serveur MCP
et sur `wrangler` : rien à configurer pour un essai sur la machine.

Lire la file :

```bash
python3 scripts/dossier_gsc.py                    # les questions les plus payantes
python3 scripts/dossier_gsc.py --dossier '<clé>'  # tout ce qu'on sait sur l'une
```

Le SQL direct reste possible pour ce que le script ne montre pas :

```bash
npx wrangler d1 execute pistes-athle-seo --remote --command \
  "SELECT cle, requete, impressions, position FROM requetes_gsc
   WHERE statut='file' ORDER BY intention='existence' DESC, position LIMIT 10;"
```

## Traiter une question

`scripts/dossier_gsc.py` est à l'étage 2 ce que `releve_gsc.py` est à l'étage 1 :
la moitié bête. Il rassemble devant l'agent la ligne de la file, la fiche visée,
les champs renseignés et ceux qui ne le sont pas, l'override existant — puis, le
travail fait, il écrit le verdict.

Ce partage n'est pas cosmétique non plus. Le montage du dossier est la partie où
l'on se trompe **sans s'en apercevoir** : regarder le mauvais identifiant,
croire qu'un champ manque alors qu'il est rempli, rouvrir une question déjà
close. Ce sont des erreurs de lecture, pas de jugement, et un script les évite
toutes. Ce qui reste à l'agent est alors le seul vrai travail — trouver une
source, ou constater qu'il n'y en a pas.

L'ordre de la file n'est pas « la meilleure position d'abord ». Les fiches déjà
dans le podium sont écartées : il n'y a rien à y gagner. Le premier lot l'a
montré — « stade de luminy » était en position 1,0, et son dossier s'est fermé
sur « rien à corriger ». Passent devant les `existence`, puis ce qui est déjà
visible sans être gagné.

Fermer un dossier :

```bash
python3 scripts/dossier_gsc.py --fermer '<clé>' \
    --statut traite --detail "ce qui a été fait, ou pourquoi rien ne l'a été"
```

| statut | quand |
|---|---|
| `traite` | la fiche a été corrigée, **ou** elle répondait déjà |
| `sans-source` | question légitime, aucune source citable |
| `candidat` | lieu peut-être réel, versé dans `data/a-verifier.json` |
| `hors-sujet` | la requête ne parle pas d'une piste d'athlétisme |

`--detail` est obligatoire, et le script refuse une chaîne vide : un dossier
fermé sans raison écrite est un dossier qu'il faudra rouvrir pour comprendre. Il
refuse aussi de refermer un dossier déjà clos, parce que le gel des compteurs
aurait lieu une seconde fois et écraserait le point de départ.

### Rouvrir ce qui a changé d'échelle

Un seul statut revient en file, `sans-source`, et c'est le relevé quotidien qui
le décide, sans intervention. Il faut d'abord que les impressions aient triplé
depuis le gel, puis que l'une des deux portes s'ouvre :

| porte | seuil | ce qu'elle attrape |
|---|---|---|
| l'échelle | 10 impressions | une demande qui explose en quelques jours |
| le temps | 90 jours | une source parue depuis, sur une question qui dure |

La première manquait, et elle a coûté cher. `complexe sportif pierre minssieux`
a été fermée le 31 août avec 2 impressions ; quatre jours plus tard elle en
avait 36, position 8,4, zéro clic, première requête du site en clics manqués.
La seule règle du temps la gardait fermée jusqu'à fin novembre. Un triplement
seul ne suffit pas non plus : de 1 à 3 impressions, c'est du bruit, d'où le
plancher.

Ce qui rouvre n'est pas la disponibilité d'une source, c'est **l'effort que la
question justifie**. Un « rien à écrire » prononcé quand elle valait deux
impressions n'engage plus à trente-six : il devient raisonnable d'appeler la
mairie, de lire l'orthophoto, ou de programmer une visite.

Le gel est refait à la réouverture. Sans cela, un dossier rouvert à 36
impressions garderait un gel à 2, se verrait triplé dès le lendemain et
rouvrirait chaque matin sans fin. `detail` n'est pas touché : le verdict
précédent est ce qui empêche de refaire la même recherche pour rien, et
`dossier_gsc.py` l'affiche en tête du dossier rouvert.

Les trois nombres sont en haut de `scripts/releve_gsc.py`
(`REOUVERTURE_FACTEUR`, `REOUVERTURE_PLANCHER`, `REOUVERTURE_JOURS`), avec le
raisonnement qui les fixe. Chaque relevé imprime ce qu'il a rouvert et le
compte dans `passages.note`.

## Savoir si tout cela sert à quelque chose

Fermer un dossier ne dit pas qu'on a bien fait. Trois colonnes gèlent donc
l'état de la question au moment où on la ferme — `impressions_avant`,
`position_avant`, `traite_le` — parce que le relevé quotidien écrase
`impressions` et `position` le lendemain matin. Sans ce gel, on saurait « la
position est de 3,1 » sans pouvoir dire d'où elle vient.

Le gel est écrit par un **déclencheur SQL**, au passage de `file` à un statut
terminal. Ce n'est pas une discipline à tenir : relever les valeurs d'avant est
exactement ce qu'on oublie, et cela ne se rattrape jamais.

La comparaison n'aura de sens qu'avec du recul — plusieurs semaines, et une
trentaine de dossiers fermés. Trois fiches ne feront jamais une conclusion.
D'ici là :

```bash
npx wrangler d1 execute pistes-athle-seo --remote --command \
  "SELECT cle, traite_le, position_avant, position,
          round(position_avant - position, 1) AS gagne
     FROM requetes_gsc
    WHERE statut='traite' AND julianday('now') - julianday(traite_le) > 30
    ORDER BY gagne DESC;"
```

Une position qui baisse est un gain. Si la colonne `gagne` reste autour de
zéro sur trente dossiers, c'est que le travail de l'étage 2 ne déplace rien —
et il vaudra mieux le savoir que le supposer.

## La règle qui prime sur tout le reste

L'étage 2 n'écrit dans une fiche **que** des faits déjà présents dans
`data/tracks.json` ou `data/overrides/`, ou tirés d'une source citable et
citée. Jamais un revêtement, un horaire, un agrès ou un contact déduit de la
requête elle-même. Une requête est une question posée, jamais une réponse.
Si la donnée manque, la fiche se tait et la question part en `sans-source`.

Un lieu sans fiche va dans `data/a-verifier.json` avec sa source, jamais dans
`tracks.json` : une requête n'est pas une preuve d'existence — les gens
cherchent des pistes fermées, démolies, ou situées dans la commune d'à côté.
Voir [trouver-les-pistes-manquantes.md](trouver-les-pistes-manquantes.md).

Ces règles ne sont pas seulement écrites ici : elles sont dans la compétence
[`traitement-gsc`](../.claude/skills/traitement-gsc/SKILL.md), qui se charge
d'elle-même quand on ouvre la file. Une règle qu'il faut penser à aller lire
est une règle qu'on oubliera.
