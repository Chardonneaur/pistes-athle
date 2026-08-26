# Journal des robots

GitHub Pages ne donne aucun log d'accès. Or les robots d'exploration —
Googlebot comme GPTBot ou ClaudeBot — **n'exécutent pas de JavaScript** :
aucune mesure côté navigateur ne les voit jamais, et Search Console ne parle
que de Google. Ce Worker, posé devant le site depuis que le domaine passe par
Cloudflare, est le seul endroit d'où l'on puisse les observer.

Depuis le 25 août 2026, ce Worker alimente **deux** journaux à partir de la
même observation : la base D1 décrite ici, qui garde **tous** les robots parce
que la comparaison IA / moteur est le sujet de l'étude, et Matomo, qui ne reçoit
que les **agents IA** — voir [docs/mesurer-le-trafic-des-ia.md](../docs/mesurer-le-trafic-des-ia.md).
Les deux sorties sont indépendantes : une panne de l'une n'affecte pas l'autre.

## Ce qu'il journalise, et ce qu'il ignore

**Uniquement les robots.** Les visites humaines traversent sans laisser la
moindre trace : ni adresse IP, ni identifiant, ni chemin. Le site promet de
n'avoir aucun traceur, et cette promesse vaut plus que la donnée qu'on
gagnerait à la contourner.

Chaque passage de robot donne une ligne : horodatage UTC, nom canonique du
robot, user-agent brut tronqué, hôte, chemin, gabarit de page, code de réponse,
et le pays du centre de données d'où le robot interroge — qui ne désigne
personne.

## Sûreté

Le Worker est en travers de chaque requête du site : trois garde-fous.

- La réponse part **avant** l'écriture en base (`waitUntil`). Une base lente ne
  ralentit aucune page.
- Une panne de la base est avalée et tracée, jamais propagée au visiteur.
- Les deux routes sont en **`request_limit_fail_open`** : au-delà des 100 000
  requêtes/jour du plan gratuit, les requêtes contournent le Worker au lieu de
  recevoir une page d'erreur 1027. Le site ne peut pas tomber à cause du journal.

## Déployer

```bash
npx wrangler deploy --config logs/wrangler.jsonc
npx wrangler d1 execute pistes-athle-logs --remote --file logs/schema.sql
```

## Interroger

```bash
# Qui est passé, et combien de fois ?
npx wrangler d1 execute pistes-athle-logs --remote --command \
  "SELECT robot, COUNT(*) n, MIN(vu_le) premier, MAX(vu_le) dernier
   FROM visites_robots GROUP BY robot ORDER BY n DESC;"

# Quel gabarit de page chaque robot explore-t-il ?
npx wrangler d1 execute pistes-athle-logs --remote --command \
  "SELECT gabarit, robot, COUNT(*) n FROM visites_robots
   GROUP BY gabarit, robot ORDER BY n DESC LIMIT 40;"

# La question de l'étude : qui a découvert le site en premier ?
npx wrangler d1 execute pistes-athle-logs --remote --command \
  "SELECT robot, MIN(vu_le) decouverte, COUNT(DISTINCT chemin) pages
   FROM visites_robots GROUP BY robot ORDER BY decouverte;"

# Couverture : combien des 23 762 pages ont été vues, et par qui ?
npx wrangler d1 execute pistes-athle-logs --remote --command \
  "SELECT robot, COUNT(DISTINCT chemin) pages_distinctes
   FROM visites_robots GROUP BY robot ORDER BY pages_distinctes DESC;"
```

## Pourquoi Matomo ne remplace pas cette base

Vérifié le 25/08/2026 : Matomo **écarte silencieusement** tout hit dont
l'user-agent n'est pas dans sa liste de chatbots. Un `GPTBot` envoyé au même
instant qu'un `ChatGPT-User` n'apparaît nulle part dans ses rapports — les deux
figurent pourtant bien ici. Les robots de corpus (`GPTBot`, `ClaudeBot`,
`PerplexityBot`, `OAI-SearchBot`) ne sont donc mesurables **que** par cette
base, qui est de toute façon la seule des deux à savoir répondre « qui a
découvert le site en premier ».

## Ajouter un robot

`ROBOTS`, dans `worker.js`, associe un nom canonique à un fragment
d'user-agent en minuscules. **L'ordre compte** : `Google-Extended` est testé
avant `Googlebot`, sinon le premier tomberait dans le second.

Un user-agent se déclare, il ne se prouve pas : ces lignes disent ce qu'un
client a affirmé être, pas ce qu'il est. Pour Googlebot, seule une résolution
DNS inverse le confirmerait — inutile ici, où l'on compare des ordres d'arrivée.

## Le webhook GitHub — la contribution déposée

Le Worker porte une seconde route, sans rapport avec les robots :
`POST /_hooks/github`. Elle reçoit les webhooks du dépôt et en fait un
événement Matomo.

**Pourquoi.** L'objectif Matomo « Contribution engagée » compte les clics sur le
lien GitHub. Il ne sait pas si le formulaire a été rempli : `github.com` n'est
pas ce site. L'écart entre le clic et le dépôt est le seul chiffre qui dise si
l'appel à contribution échoue au clic ou au formulaire.

**Ce qui remonte**, et rien d'autre :

| Événement GitHub | Événement Matomo |
|---|---|
| `issues` / `opened` | `Contribution` / `Issue ouverte` / *étiquettes* |
| `pull_request` / `opened` | `Contribution` / `Pull request ouverte` / *titre* |
| `pull_request` / `closed` **et fusionnée** | `Contribution` / `Pull request fusionnée` / *titre* |

Une pull request fermée sans fusion n'est pas une contribution. Commentaires,
étoiles et pushes reçoivent un 204 et sont ignorés — un 4xx ferait rejouer la
livraison par GitHub.

L'objectif Matomo **« Contribution déposée »** (site 149) convertit sur la
catégorie d'événement `Contribution`.

**Sûreté.** La route vérifie `X-Hub-Signature-256` (HMAC-SHA256 du corps) par
comparaison à temps constant avant de regarder quoi que ce soit. Sans secret
configuré elle répond 503 : elle échoue fermée, jamais ouverte. Sans cette
vérification, quiconque connaît l'adresse gonflerait le chiffre.

**Ces hits créent une visite**, contrairement aux robots. Le mode `recMode=1`
n'ouvre pas de visite, et une conversion d'objectif est une propriété d'une
visite : en `recMode`, l'événement ne convertirait rien. Le prix est assumé —
quelques visites par mois qui ne sont pas des lectures de page. Elles portent
toutes l'identifiant utilisateur `github-webhook`, ce qui permet de les isoler
dans un segment ou de les effacer.

### Mettre en service

Deux gestes, dans cet ordre :

```bash
# 1. le secret, côté Cloudflare (générez-le : openssl rand -hex 32)
npx wrangler secret put GITHUB_WEBHOOK_SECRET --config logs/wrangler.jsonc
npx wrangler deploy --config logs/wrangler.jsonc

# 2. le webhook, côté dépôt — avec LE MÊME secret
gh api repos/Chardonneaur/pistes-athle/hooks -X POST \
  -f name=web -F active=true \
  -f 'events[]=issues' -f 'events[]=pull_request' \
  -f config[url]=https://pistes-athle.com/_hooks/github \
  -f config[content_type]=json \
  -f config[secret]="$SECRET"
```

GitHub envoie un `ping` à la création : une coche verte confirme que la
signature est acceptée.

### Tests

```bash
node --test logs/worker.test.mjs
```

Quinze cas : signature absente, forgée, de longueur différente, corps modifié
après signature, secret manquant, charge démesurée, JSON illisible, et le fait
qu'une page du site n'est pas interceptée par la route.

## Écouter les agents qui pilotent un navigateur

Un agent comme le mode agent de ChatGPT n'est pas un crawler : il conduit un
vrai navigateur, exécute le JavaScript et présente un user-agent de Chrome
ordinaire. `robot()` ne le voit pas.

**Constaté le 26 août 2026.** Une session agentique lit quatre pages du site.
Matomo la classe « accès direct », sans nom d'agent ; la base D1 n'en garde
aucune trace — alors que le Worker avait les quatre requêtes en main et les a
jetées. Ce qu'il y avait pourtant à voir : une IP dans la plage de Cloudflare,
une géolocalisation à Augsbourg avec un navigateur en `fr-fr`, une résolution
de `1364x1024` qu'aucun Mac ne rapporte, deux vues de l'accueil à une seconde
d'écart, et une recherche « Nantes » à zéro résultat suivie 52 secondes plus
tard de l'ouverture directe d'une fiche. Chaque signal est faible ; ensemble
ils ne laissent aucun doute.

La seule chose qui puisse **déclarer** un tel agent est la signature
[Web Bot Auth](https://datatracker.ietf.org/doc/draft-meunier-web-bot-auth-architecture/) :
les en-têtes `Signature`, `Signature-Input` et `Signature-Agent`, ce dernier
portant l'identité du mandant, `"https://chatgpt.com"`.

C'est ce que lit le plugin AIAgents de Matomo — mais il le lit sur la requête
**au traceur**, alors que l'agent signe ses requêtes **au site**. Sur un site
mesuré en JavaScript, sa détection ne peut donc pas se déclencher. Ici, si :
`journaliser()` accepte désormais un passage dès que `Signature-Agent` est
présent, quel que soit l'user-agent, et le range sous le nom du mandant.

Un signataire inconnu n'est pas ignoré : il ressort préfixé `signe:`, parce que
le but est justement de découvrir qui signe. Une liste fermée ne montrerait que
ce qu'on y a déjà mis.

**Rien n'est renvoyé à Matomo.** L'agent y est déjà compté par
`assets/matomo.js`, qu'il exécute : un second hit dédoublerait la visite. Le
jour où ce journal montrera que la signature arrive vraiment, il sera temps de
la relayer — et il faudra passer par la page, pas par une requête séparée.

Pour savoir ce que ça donne :

```sql
SELECT robot, COUNT(*) FROM visites_robots
WHERE robot LIKE 'signe:%' OR robot IN ('ChatGPT','Claude','Perplexity','Gemini')
GROUP BY robot ORDER BY 2 DESC;
```
