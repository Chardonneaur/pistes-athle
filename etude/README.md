# Journal de découverte

Un site de 23 762 pages, mis en ligne sur un domaine neuf le 23 août 2026, à
zéro crawl. Ce répertoire enregistre, jour après jour, **qui le découvre et
dans quel ordre** — Google d'un côté, les robots d'IA de l'autre.

La chronologie ne se reconstitue pas après coup. Search Console montre l'état
courant, pas la suite des états ; et un passage de robot non enregistré est
perdu pour toujours. D'où le relevé quotidien.

## Lancer le relevé

```bash
etude/releve.sh
```

En cron, tous les jours à 6 h :

```
0 6 * * * /home/ronan/athle/etude/releve.sh >> /home/ronan/athle/.work/releve.log 2>&1
```

## Les fichiers

| Fichier | Contenu | Source |
|---|---|---|
| `cohorte.txt` | les 14 URL suivies, une par gabarit de page, FR et EN | tirée une fois du plan de site |
| `indexation.csv` | l'état d'indexation de chaque URL de la cohorte, chaque jour | API URL Inspection |
| `sitemaps.csv` | plan lu ou non, URL soumises et indexées | API Sitemaps |
| `performance.csv` | clics et impressions par jour | API Search Analytics |
| `requetes.csv` | les requêtes qui amènent du monde, dans leur ordre d'apparition | API Search Analytics |
| `robots.csv` | par robot : passages, pages distinctes, **première visite** | base D1 alimentée par `logs/` |
| `citations.csv` | les passages qui ressemblent à une citation, un par ligne | base D1, via `citations.py` |

## Être exploré n'est pas être cité

`robots.csv` compte les passages ; `citations.csv` isole ceux qui disent quelque
chose d'un **usage**. Trois familles, par ordre de proximité avec une réponse
rendue à quelqu'un :

- **exploration** — la constitution d'un corpus : GPTBot, ClaudeBot, Googlebot.
  Ils passent une fois, prennent tout, et ne disent rien de l'usage.
- **index de réponse** — l'index propre au moteur de réponse, celui d'où les
  citations sont tirées : OAI-SearchBot, PerplexityBot, Claude-SearchBot. Y
  figurer est la *condition* d'être cité, ce n'en est pas la preuve.
- **à la demande** — la page est allée être lue *parce qu'un humain venait de
  poser une question* : ChatGPT-User, Claude-User, Perplexity-User,
  MistralAI-User. C'est le signal le plus proche d'une citation qu'un site
  puisse observer depuis ses propres journaux.

D'où le grain : l'exploration se compte, les deux autres familles s'énumèrent
une ligne par passage. Elles sont rares, et chacune désigne **une page** —
savoir quelle fiche un assistant est allé lire vaut plus que leur nombre.

Ce que cette mesure ne dit pas : elle voit la page *aller être lue*, pas la
réponse rendue. Un assistant peut citer de mémoire sans rien demander, et
peut demander sans citer. Une mesure directe — poser les questions et relever
les sources citées — demanderait une clé d'API par assistant.

## La cohorte ne se modifie pas

`cohorte.txt` fixe la population suivie : une URL par gabarit, tirée une seule
fois de manière reproductible. Suivre un échantillon différent chaque jour
comparerait des choses différentes, et l'inspection d'URL est contingentée à
2 000 appels par jour — on ne peut pas suivre les 23 762 pages.

Si la cohorte doit être retirée (nouveau gabarit de page, URL disparue) :

```bash
uv run --directory ~/gsc gsc-releve --site sc-domain:pistes-athle.com \
  --sortie ~/athle/etude --cohorte
```

En notant la date du changement : les séries d'avant et d'après ne se comparent
plus directement.

## Ce que la colonne `releve` sert à voir

Chaque ligne porte le jour où on l'a écrite, et non seulement le jour qu'elle
décrit. Search Console révise ses chiffres pendant deux à trois jours : la même
journée relevée trois jours de suite peut donner trois valeurs. Garder les trois
dit ce qu'on savait, et quand — ce qu'un écrasement effacerait.
