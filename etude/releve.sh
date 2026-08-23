#!/usr/bin/env bash
# Releve quotidien de la decouverte du site — les deux moitiees de la mesure.
#
#   Search Console : ce que Google a fait des pages (indexation, impressions)
#   D1 via le Worker : quels robots sont passes, et quand
#
# En cron, tous les jours a 6 h :
#   0 6 * * * /home/ronan/athle/etude/releve.sh >> /home/ronan/athle/.work/releve.log 2>&1
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1

echo "===== $(date -Is) ====="
uv run --directory "$HOME/gsc" gsc-releve \
  --site sc-domain:pistes-athle.com --sortie "$PWD/etude" || echo "!! releve Search Console en echec"
python3 etude/releve_robots.py --sortie etude || echo "!! releve robots en echec"
