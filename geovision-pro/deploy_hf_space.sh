#!/usr/bin/env bash
# Push GeoVision Pro to a Hugging Face Space (Docker SDK) -> public phone-openable URL.
#
# Usage:
#   HF_TOKEN=hf_xxx ./deploy_hf_space.sh [ignored-username] [space-name]
#
# The owning username is resolved automatically from the token (whoami) so a
# typo / wrong casing in the input can no longer break the deploy. Needs a HF
# account + a *write* access token (https://huggingface.co/settings/tokens).
set -euo pipefail
cd "$(dirname "$0")"

: "${HF_TOKEN:?Set HF_TOKEN env var (a Hugging Face *write* token)}"
SPACE="${2:-geovision-pro}"

# --- resolve the real username that owns this token (authoritative) ---
WHO="$(curl -s -H "Authorization: Bearer ${HF_TOKEN}" https://huggingface.co/api/whoami-v2)"
USER="$(printf '%s' "$WHO" | jq -r '.name // empty' 2>/dev/null || true)"
if [ -z "$USER" ]; then
  echo "ERROR: Konnte mich mit HF_TOKEN nicht authentifizieren."
  echo "Antwort von Hugging Face: $WHO"
  echo "-> Prüfe, dass der Token gültig ist und die Rolle 'Write' hat."
  exit 1
fi
echo "==> Angemeldet bei Hugging Face als: ${USER}"
REPO="${USER}/${SPACE}"

# --- create the Space under the user's own namespace (no 'organization' field) ---
echo "==> Lege Space ${REPO} an (falls noch nicht vorhanden) ..."
RESP="$(curl -s -w $'\n%{http_code}' -X POST https://huggingface.co/api/repos/create \
  -H "Authorization: Bearer ${HF_TOKEN}" -H "Content-Type: application/json" \
  -d "{\"type\":\"space\",\"name\":\"${SPACE}\",\"sdk\":\"docker\",\"private\":false}")"
CODE="$(printf '%s' "$RESP" | tail -n1)"
BODY="$(printf '%s' "$RESP" | sed '$d')"
case "$CODE" in
  200|201) echo "    Space angelegt." ;;
  409)     echo "    Space existiert bereits — wird aktualisiert." ;;
  *)       echo "    WARNUNG: create-API antwortete HTTP ${CODE}: ${BODY}" ;;
esac

# --- assemble a clean repo and push it (this triggers the HF build) ---
TMP="$(mktemp -d)"
echo "==> Stelle Space-Inhalt in ${TMP} zusammen ..."
cp -r backend frontend Dockerfile .dockerignore "${TMP}/"
cp SPACE_README.md "${TMP}/README.md"

cd "${TMP}"
git init -q
git add -A
git -c user.email="deploy@geovision" -c user.name="deploy" commit -qm "Deploy GeoVision Pro"
git branch -M main
git remote add origin "https://${USER}:${HF_TOKEN}@huggingface.co/spaces/${REPO}"
echo "==> Pushe zum Space (startet den Build) ..."
git push -f origin main

echo ""
echo "----------------------------------------------------------------"
echo "Fertig! Deine Website (auf dem Handy öffenbar):"
echo "  Build/Status:  https://huggingface.co/spaces/${REPO}"
echo "  Die App:       https://${USER}-${SPACE}.hf.space"
echo "Erster Aufruf baut das Image (paar Minuten); erster Analyse-"
echo "Request lädt einmalig die Modelle."
echo "----------------------------------------------------------------"
