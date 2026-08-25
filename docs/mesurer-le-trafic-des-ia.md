# Mesurer le trafic des IA

Ce projet avance une hypothèse : les agents IA explorent un annuaire structuré
beaucoup plus vite qu'un moteur de recherche ne l'indexe. Tant qu'on ne la
mesure pas, elle reste une intuition. Ce document décrit les trois instruments
posés pour la mesurer, ce que chacun voit — et surtout **ce qu'il ne voit pas**.

## Le piège : un traceur dans la page ne voit aucun robot

Le réflexe est de coller un bout de JavaScript dans le `<head>` et de considérer
l'affaire réglée. Elle ne l'est pas, et le raté est total plutôt que partiel.

Un agent IA qui vient lire une fiche envoie une requête HTTP, reçoit du HTML, le
lit, et s'en va. **Il n'exécute pas le JavaScript.** Pour lui, un traceur posé
dans la page n'existe simplement pas. Compter les IA avec un traceur de page,
c'est compter les poissons avec un filet à papillons : l'outil n'est pas
imprécis, il est hors sujet.

D'où une mesure en deux endroits, et trois journaux.

## Instrument 1 — `assets/matomo.js` : les humains envoyés par une IA

Chargé par toutes les pages du site. Il voit les **humains**, y compris — et
c'est là son intérêt ici — ceux qui arrivent après avoir lu une réponse de
ChatGPT, Perplexity, Claude ou Gemini. Matomo les reconnaît au référent et les
range dans **Acquisition › Assistants IA**.

Ce qu'il mesure : le clic, pas la lecture. Quelqu'un a demandé « où courir près
de Nantes ? », l'IA a cité l'annuaire, la personne a cliqué. C'est le bout
visible de la chaîne.

Configuration : sans cookie (`disableCookies`), « Do Not Track » respecté. Pas
de cookie, donc pas de bandeau de consentement — et la promesse de discrétion du
site reste tenable telle qu'elle est écrite.

Sa limite, à retenir : l'application est une page unique. Toute la navigation
dans la carte et les filtres se déroule sous une seule URL, `/`. Les pages
statiques (`/site/…`, `/departement/…`) sont mesurées finement ; l'usage de
l'application, non. C'est un choix, pas un oubli : mesurer chaque changement de
filtre noierait les rapports.

## Instrument 2 — `logs/worker.js` : les robots eux-mêmes

C'est la moitié qui compte pour l'hypothèse du projet, et la seule façon de
l'obtenir est de mesurer **avant** la page, là où la requête passe. Le site est
publié sur GitHub Pages, qui ne donne aucun log d'accès, mais `pistes-athle.com`
est servi à travers Cloudflare : un Worker s'intercale sur ce trajet.

**Un seul Worker, deux sorties.** Cloudflare n'admet qu'un Worker par route : la
mesure Matomo est donc greffée sur le journal des robots existant, pas posée à
côté. Les deux sorties sont indépendantes — une panne de Matomo n'empêche pas
l'écriture en base, et réciproquement.

| Sortie | Reçoit | Répond à |
|---|---|---|
| **Base D1** (`visites_robots`) | **tous** les robots, Googlebot compris | Qui a découvert le site en premier ? à quelle cadence ? quelle couverture ? |
| **Matomo** (`recMode=1`) | les **agents IA** seulement | Quelles pages les IA vont-elles chercher ? envoient-elles des gens ? |

D1 garde Googlebot et Bingbot parce que **la comparaison IA / moteur est tout le
sujet de l'étude**. Matomo ne les reçoit pas : ce sont des moteurs, pas des IA,
et les envoyer polluerait un rapport intitulé « Chatbots IA ».

`recMode=1` est le mode « sans visite » : il n'ouvre ni visite, ni session, ni
attribution. Les statistiques humaines restent intactes, les deux mesures ne se
mélangent jamais.

### Ce que Matomo accepte, et ce qu'il jette — vérifié le 25/08/2026

**Matomo écarte silencieusement tout hit dont l'user-agent n'est pas dans sa
liste de chatbots.** Sans erreur, sans trace : le hit part, il est accepté en
HTTP 200, et il n'apparaît nulle part.

La vérification était simple. Trois requêtes envoyées au même instant sur
`/departements/` :

```
D1     : Googlebot, GPTBot, ChatGPT-User   → les 3 ont atteint le Worker
Matomo : ChatGPT                            → GPTBot envoyé, puis jeté
```

Conséquence pratique, encodée dans `MATOMO_CORPUS="0"` :

| | Exemples | Matomo | D1 |
|---|---|---|---|
| **Agents** — cherchent une page **pour répondre à quelqu'un**, maintenant | `ChatGPT-User`, `Claude-User`, `Perplexity-User` | ✅ nommés | ✅ |
| **Robots de corpus** — constituent un fonds, décident si l'annuaire sera *citable* demain | `GPTBot`, `ClaudeBot`, `PerplexityBot`, `OAI-SearchBot` | ❌ jetés | ✅ |

Ce n'est pas une perte : D1 est de toute façon le seul des deux à savoir
répondre « qui a découvert le site en premier ». Envoyer les robots de corpus à
Matomo dépenserait une sous-requête par passage pour zéro donnée. La liste reste
dans `worker.js` pour documenter ce qui a été essayé, et pour le jour où Matomo
élargira la sienne.

### Un réglage à signaler

Le Worker envoie `/api/index.json` et `/llms.txt` à Matomo, que son réglage par
défaut écarterait comme fichiers statiques. Ce sont précisément les adresses
qu'un agent bien élevé demande en premier. Les exclure reviendrait à ne pas voir
ce qu'on cherche à mesurer. (La base D1, elle, garde tout, habillage compris.)

Les redirections (3xx) ne sont pas envoyées à Matomo : `www.pistes-athle.com`
renvoie un 301 vers l'apex, et compter les deux ferait deux lignes pour une
seule lecture. D1 les garde — un robot qui frappe `www` reste un fait.

## Une règle de conception : la mesure ne coûte jamais une page

Le Worker est sur le chemin de **toutes** les visites du site. Les deux sorties
partent dans `waitUntil()`, après l'envoi de la réponse, et chacune avale ses
propres pannes. Une mesure ratée est un trou dans un graphique ; une exception
serait une page blanche. On choisit le trou.

Les routes sont en `request_limit_fail_open` : au-delà des 100 000 requêtes/jour
du plan gratuit, les requêtes contournent le Worker au lieu de recevoir une page
d'erreur 1027. Le site ne peut pas tomber à cause de sa propre mesure.

## Vérifier une installation : la vue temps réel

Piège à connaître, il coûte une demi-heure de doute. Les rapports « Chatbots
IA » sont **archivés** : sur Matomo Cloud l'archivage passe par cron, et une
requête tout juste envoyée y affiche encore `0`. Ce zéro ne veut pas dire que la
mesure a échoué.

Deux méthodes d'API répondent, elles, **sans archivage** :

- `BotTracking.getAIChatbotsRealTime` — quels agents, combien de requêtes
- `BotTracking.getTopPageUrlsRealTime` — quelles pages ils sont venus lire

Ce sont elles qu'il faut interroger juste après un déploiement. Une requête de
contrôle sur le site suffit :

```sh
curl -s -o /dev/null -H 'user-agent: ChatGPT-User/1.0' \
  https://pistes-athle.com/departements/
```

puis la vue temps réel, qui doit faire apparaître `ChatGPT` avec cette URL. Le
rapport archivé suivra au prochain passage du cron.

## Où regarder

| Question | Où |
|---|---|
| Qui a découvert le site en premier ? | **D1** — `logs/README.md`, § Interroger |
| Quelle couverture chaque robot a-t-il atteinte ? | **D1** |
| Les IA lisent-elles le site, et lesquelles ? | Matomo › AI Assistants › **AI Chatbots** |
| Quelles pages lisent-elles ? | Matomo › AI Assistants › **Pages** |
| Que lisent-elles que les humains ignorent ? | Matomo › AI Assistants › **AI-Favoured Pages** |
| Envoient-elles des gens ? | Matomo › **AI Chatbots Overview**, colonne *Acquired visits* |
| Combien de visiteurs viennent d'une IA ? | Matomo › Acquisition › **Assistants IA** |
| Les robots tombent-ils sur des pages cassées ? | Matomo › **Broken Pages and Documents** |
| Une installation vient d'être déployée, marche-t-elle ? | `BotTracking.getAIChatbotsRealTime` |

Le rapport le plus intéressant côté Matomo est **AI-Favoured Pages** : les pages
que les IA vont chercher et que les humains ne demandent pas. C'est là que se lit
la différence entre ce qu'un annuaire *publie* et ce qu'une IA *utilise*.

## Analyser : par où commencer

### La première chose à savoir, sinon tout paraît cassé

**Les rapports IA de Matomo vont sembler presque vides, et c'est normal.**
Relevé du 25 août 2026, deux jours après la pose du journal D1 :

| | Requêtes en 2 jours | Visible dans Matomo |
|---|---:|---|
| ClaudeBot | 28 655 | ❌ |
| GPTBot | 28 483 | ❌ |
| GoogleOther | 2 334 | ❌ (moteur) |
| Googlebot | 2 089 | ❌ (moteur) |
| OAI-SearchBot | 34 | ❌ |
| **ChatGPT-User** | **8** | ✅ |
| **Claude-User** | **2** | ✅ |

Matomo voit **10 requêtes sur 61 600**, soit 0,016 %. Ce n'est pas un défaut de
réglage : ce sont les deux seuls agents à s'être déclarés comme agissant pour
quelqu'un. Tout le reste est de l'exploration de corpus, et Matomo ne la traite
pas. Ouvrir « AI Chatbots » en s'attendant au volume du crawl mène à conclure
que la mesure ne marche pas, alors qu'elle fait exactement son travail.

**Répartition des rôles**, à garder en tête à chaque question :

- **D1 répond au « combien » et au « qui est arrivé en premier ».** C'est
  l'instrument de l'étude.
- **Matomo répond au « et alors ? ».** Est-ce que ça rapporte quelqu'un ?

### Les cinq questions, et où les poser

**1. Est-ce qu'être lu par une IA amène quelqu'un ?**
`AI Assistants › AI Chatbots Overview`. La métrique qui compte est le
**Click-through rate** = *Acquired visits* ÷ *Requests*. C'est le seul chiffre
qui relie la lecture par une IA à une visite humaine. Tout le reste est du
volume.

**2. Quelles pages les IA vont-elles chercher que les humains ignorent ?**
`AI Assistants › AI-Favoured Pages`, à lire en regard de `Human-Favoured Pages`.
C'est le rapport le plus intéressant du lot, parce qu'il est le seul à comparer
deux populations sur le même contenu. Il dit l'écart entre ce que l'annuaire
*publie* et ce qu'une IA *utilise*.

**3. Les robots tombent-ils sur des pages cassées ?**
`AI Assistants › Broken Pages and Documents`. À surveiller après chaque
renommage d'identifiant : une fiche déplacée casse une citation déjà faite.

**4. Combien de visiteurs humains arrivent d'une IA ?**
`Acquisition › Assistants IA`. Côté segments, c'est là que ça devient
exploitable — ces visites-là sont de vraies visites :

```
referrerType==ai                 toutes les arrivées depuis une IA
referrerType==ai;referrerName==ChatGPT      depuis ChatGPT seulement
aiAgentName!=                    les visites portant un nom d'agent
```

Croiser `referrerType==ai` avec n'importe quel rapport de comportement répond à
« que font les gens envoyés par une IA, une fois arrivés ? » — profondeur,
pages de sortie, durée. C'est impossible côté robots, dont les requêtes
`recMode=1` ne créent pas de visite et échappent donc à tout segment.

**5. Ce que les IA explorent vraiment.**
Pas dans Matomo — dans D1. Relevé du 25 août, par gabarit de page :

| gabarit | corpus IA | agents IA | moteurs |
|---|---:|---:|---:|
| `/site/` | 14 320 | 2 | 716 |
| `/en/track/` | 14 300 | 0 | 357 |
| `/api/` | 9 292 | 0 | 30 |
| `/ville/` | 7 717 | 0 | 643 |
| `/en/city/` | 7 714 | 0 | 2 339 |

Deux faits s'y lisent, qu'aucun rapport Matomo ne donnera. D'abord `/api/` :
9 292 requêtes de robots IA contre 30 de moteurs. **L'API est lue presque
exclusivement par des IA** — c'est la validation la plus nette de l'hypothèse du
projet. Ensuite la version anglaise, explorée à parité avec la française par les
IA (14 300 contre 14 320), alors que les moteurs la traitent à part.

### Interroger par programme

Les rapports archivés se lisent avec `BotTracking.*` (voir la liste des méthodes
plus haut) et acceptent `period`/`date` comme n'importe quel rapport Matomo.
Attention à `period=range` avec `date=lastN` : N s'y compte en **jours** et rend
**un** agrégat, alors que `period=day&date=lastN` rend une ligne **par jour** —
c'est la seconde forme qu'il faut pour une courbe d'évolution.

### Le piège des premières semaines

Ne pas conclure sur un CTR calculé sur 10 requêtes. Le dénominateur des rapports
Matomo est minuscule tant que les agents conversationnels ne sont pas venus en
nombre, et un seul clic ferait passer le taux de 0 % à 10 %. Les volumes
exploitables sont dans D1 ; Matomo demandera des semaines avant de dire quelque
chose de stable sur l'acquisition.

### Ce que les 404 racontent : les adresses qu'une IA devine

C'est la requête la plus rentable de la base, et elle ne coûte rien :

```bash
npx wrangler d1 execute pistes-athle-logs --remote --command \
  "SELECT chemin, COUNT(*) n, GROUP_CONCAT(DISTINCT robot) robots
   FROM visites_robots WHERE statut = 404
   GROUP BY chemin ORDER BY n DESC LIMIT 20;"
```

Un agent qui répond à quelqu'un ne suit pas toujours un lien : il **déduit** une
adresse plausible. Quand il se trompe, le 404 ne lui apprend pas l'adresse
correcte — il lui apprend que le site n'a pas la réponse. Deux cas relevés le
25/08/2026, qui ne se corrigent pas de la même façon :

- **L'adresse inventée.** `/criteres/piste-400m/`, demandée par ChatGPT-User à
  06:31:47, puis par GPTBot **250 ms plus tard** sur la même mauvaise adresse :
  l'agent répond, le crawler de corpus repasse derrière. Le segment n'a jamais
  existé — les pages par critère sont sous `/pistes/` — et le slug non plus,
  c'est `400m`. Remède : une 301 dans le Worker, et la **liste complète** des
  slugs dans `llms.txt` plutôt que des exemples. Un agent ne devine que ce qu'on
  ne lui a pas dit.
- **Le lien réellement cassé.** `/en/contributeurs/`, pris par GPTBot *et*
  ClaudeBot : la coquille anglaise servait les liens en segments français.
  Corriger le gabarit ne suffit pas — un crawler garde l'adresse qu'il a lue.
  D'où la table `SEGMENTS_EN` du Worker, qui rattrape les visiteurs déjà partis
  avec la mauvaise.

Le reste du relevé est du bruit instructif : `/.env`, `/.env.production`,
`/.env.development` (ChatGPT-User, PerplexityBot, Bingbot — ils sondent les
fichiers de configuration ; il n'y a rien à trouver sur un site statique), et
onze demandes de la forme `/assets/${esc(BASE + p.f)}` — GPTBot lit `app.js`
**comme du texte**, y repère des chaînes qui ressemblent à des chemins, et
demande les gabarits non évalués. Rien à corriger, mais cela dit que le
JavaScript du site est lu comme du contenu.

### Le rythme, qui n'est pas celui d'un moteur

Trois jours de journal, par jour et par robot :

| | 23/08 | 24/08 | 25/08 |
|---|---:|---:|---:|
| ClaudeBot | 28 548 | 103 | 4 |
| GPTBot | 28 480 | 1 | 3 |
| GoogleOther | 1 185 | 921 | 300 |
| Googlebot | 204 | 1 436 | 499 |

ClaudeBot et GPTBot ont pris **le site entier le jour de sa découverte**,
~28 500 requêtes chacun pour 23 766 URL au plan de site, puis se sont tus.
Googlebot avance au contraire à rythme constant. Deux conséquences pratiques :
un chiffre mensuel moyen ne veut rien dire ici, et le quota gratuit du Worker
(100 000 requêtes/jour) est à portée — deux crawlers ont consommé 57 000
requêtes en une journée. Au-delà, les routes basculent en
`request_limit_fail_open` : le site reste debout, mais **le journal se tait**,
et c'est le jour d'une nouvelle découverte qu'on perdrait.

## Ce qui reste non mesuré

À dire franchement, parce que l'omission serait une affirmation fausse :

- **Les citations sans clic.** Une IA qui lit l'annuaire, s'en sert pour
  répondre, et ne fournit aucun lien : elle apparaît en requête robot, jamais en
  visite. C'est probablement le gros du volume, et il est invisible par
  construction.
- **Les agents qui ne se déclarent pas.** La détection se fait sur le
  *User-Agent*, une chaîne que rien n'oblige à être sincère. Ces journaux disent
  ce qu'un client a *affirmé* être, pas ce qu'il est.
- **`chardonneaur.github.io`.** Le Worker ne couvre que `pistes-athle.com` et
  `www.pistes-athle.com` ; une requête arrivant par l'adresse GitHub Pages
  échappe à Cloudflare, donc aux deux journaux.
- **L'usage de l'application.** Carte et filtres vivent sous une seule URL. La
  recherche fait exception depuis le 25/08/2026 : `assets/app.js` la déclare à
  Matomo (`trackSiteSearch`) une fois la frappe finie, avec son nombre de
  résultats. Une recherche qui ne rend rien désigne une piste absente de
  l'annuaire — c'est la seule donnée que ni le recensement ni OpenStreetMap ne
  contiennent. Elle est annoncée sur la page de confidentialité.
