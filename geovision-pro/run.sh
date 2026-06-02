#!/usr/bin/env bash
# GeoVision Pro — one-command local launcher.
# Usage: ./run.sh            (build + start, foreground)
#        ./run.sh -d         (build + start, background)
#        ./run.sh down       (stop and remove containers)
set -euo pipefail
cd "$(dirname "$0")"

if [ "${1:-}" = "down" ]; then
  docker compose down
  exit 0
fi

echo "==> Building & starting GeoVision Pro (db + backend + frontend) ..."
docker compose up --build "${@}"

cat <<'EOF'

----------------------------------------------------------------
GeoVision Pro läuft:
  • App (Frontend):   http://localhost:8080
  • API / Swagger:    http://localhost:8000/docs

Hinweis: Beim ERSTEN Analyse-Request lädt das Backend die Modelle
(GeoCLIP + StreetCLIP, mehrere hundert MB) von HuggingFace —
das dauert einmalig ein paar Minuten, danach sind sie gecached.

Stoppen:  ./run.sh down
----------------------------------------------------------------
EOF
