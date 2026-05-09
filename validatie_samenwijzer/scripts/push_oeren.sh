#!/usr/bin/env bash
# Upload de lokale oeren/-tree naar Box (eenmalig per master-machine).
# Tegenhanger van sync_oeren.sh — alleen draaien op de machine waar je
# de meest actuele oeren hebt staan.
#
# Default doel:               box:samenwijzer/oeren
# Override via env-vars:
#   RCLONE_REMOTE=box
#   RCLONE_OEREN_PAD=samenwijzer/oeren
#   OEREN_PAD=../oeren
#
# Gebruik:
#   ./scripts/push_oeren.sh             # echte upload
#   ./scripts/push_oeren.sh --dry-run   # alleen tonen wat geüpload zou worden

set -euo pipefail

REMOTE="${RCLONE_REMOTE:-box}"
REMOTE_PAD="${RCLONE_OEREN_PAD:-samenwijzer/oeren}"
LOKAAL_PAD="${OEREN_PAD:-../oeren}"

DRY_RUN_FLAG=""
if [[ "${1:-}" == "--dry-run" ]]; then
    DRY_RUN_FLAG="--dry-run"
fi

if ! command -v rclone >/dev/null 2>&1; then
    echo "Fout: rclone is niet geïnstalleerd."
    exit 1
fi

if ! rclone listremotes | grep -qx "${REMOTE}:"; then
    echo "Fout: remote '${REMOTE}:' niet gevonden in rclone config."
    exit 1
fi

if [[ ! -d "${LOKAAL_PAD}" ]]; then
    echo "Fout: lokale map '${LOKAAL_PAD}' bestaat niet."
    exit 1
fi

n_lokaal=$(find "${LOKAAL_PAD}" -type f | wc -l)
echo "Upload ${LOKAAL_PAD}/  →  ${REMOTE}:${REMOTE_PAD}/   (${n_lokaal} bestanden)"
if [[ -n "${DRY_RUN_FLAG}" ]]; then
    echo "(DRY-RUN — er wordt niets daadwerkelijk geüpload)"
fi

rclone copy "${LOKAAL_PAD}" "${REMOTE}:${REMOTE_PAD}" \
    ${DRY_RUN_FLAG} \
    --progress \
    --transfers 8 \
    --checkers 16

echo ""
echo "Klaar."
