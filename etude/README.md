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
