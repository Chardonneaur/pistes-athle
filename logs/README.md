# Journal des robots

GitHub Pages ne donne aucun log d'accès. Or les robots d'exploration —
Googlebot comme GPTBot ou ClaudeBot — **n'exécutent pas de JavaScript** :
aucune mesure côté navigateur ne les voit jamais, et Search Console ne parle
que de Google. Ce Worker, posé devant le site depuis que le domaine passe par
Cloudflare, est le seul endroit d'où l'on puisse les observer.

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

## Ajouter un robot

`ROBOTS`, dans `worker.js`, associe un nom canonique à un fragment
d'user-agent en minuscules. **L'ordre compte** : `Google-Extended` est testé
avant `Googlebot`, sinon le premier tomberait dans le second.

Un user-agent se déclare, il ne se prouve pas : ces lignes disent ce qu'un
client a affirmé être, pas ce qu'il est. Pour Googlebot, seule une résolution
DNS inverse le confirmerait — inutile ici, où l'on compare des ordres d'arrivée.
