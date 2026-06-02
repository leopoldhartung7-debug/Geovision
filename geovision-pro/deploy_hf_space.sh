#!/usr/bin/env bash
# Push GeoVision Pro to a Hugging Face Space (Docker SDK) -> public phone-openable URL.
#
# Usage:
#   HF_TOKEN=hf_xxx ./deploy_hf_space.sh <hf-username> [space-name]
#
# Needs a HF account + a "write" access token (https://huggingface.co/settings/tokens).
# Creates the Space if it doesn't exist and pushes the single-container app.
set -euo pipefail
cd "$(dirname "$0")"

USER="${1:?Usage: HF_TOKEN=hf_xxx ./deploy_hf_space.sh <hf-username> [space-name]}"
SPACE="${2:-geovision-pro}"
: "${HF_TOKEN:?Set HF_TOKEN env var (a Hugging Face *write* token)}"
REPO="${USER}/${SPACE}"

echo "==> Creating Space ${REPO} (ignored if it already exists) ..."
curl -s -X POST https://huggingface.co/api/repos/create \
  -H "Authorization: Bearer ${HF_TOKEN}" -H "Content-Type: application/json" \
  -d "{\"type\":\"space\",\"name\":\"${SPACE}\",\"organization\":\"${USER}\",\"sdk\":\"docker\",\"private\":false}" \
  >/dev/null || true

TMP="$(mktemp -d)"
echo "==> Assembling Space repo in ${TMP} ..."
cp -r backend frontend Dockerfile .dockerignore "${TMP}/"
cp SPACE_README.md "${TMP}/README.md"

cd "${TMP}"
git init -q
git lfs install >/dev/null 2>&1 || true
git add -A
git -c user.email="deploy@geovision" -c user.name="deploy" commit -qm "Deploy GeoVision Pro"
git branch -M main
git remote add origin "https://${USER}:${HF_TOKEN}@huggingface.co/spaces/${REPO}"
echo "==> Pushing to Space (this triggers the build) ..."
git push -f origin main

echo ""
echo "----------------------------------------------------------------"
echo "Fertig! Deine Website (auf dem Handy öffenbar):"
echo "  https://huggingface.co/spaces/${REPO}     (Status/Build-Logs)"
echo "  https://${USER}-${SPACE}.hf.space          (die App selbst)"
echo "Der erste Aufruf baut das Image (paar Minuten); der erste"
echo "Analyse-Request lädt einmalig die Modelle."
echo "----------------------------------------------------------------"
