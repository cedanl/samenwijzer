#!/usr/bin/env bash
# Synchroniseer de kwalificatiedossiers/-tree vanuit Box (rclone).
#
# Default remote/pad:        box:samenwijzer/kwalificatiedossiers
# Override via env-vars:
#   RCLONE_REMOTE=box
#   RCLONE_KWALDOSSIERS_PAD=samenwijzer/kwalificatiedossiers
#   KWALDOSSIERS_LOKAAL=../kwalificatiedossiers
#
# Richting: standaard download (Box → lokaal). Voor een eerste upload van de
# lokaal opgebouwde set: `./sync_kwalificatiedossiers.sh --upload`.

set -euo pipefail

REMOTE="${RCLONE_REMOTE:-box}"
REMOTE_PAD="${RCLONE_KWALDOSSIERS_PAD:-samenwijzer/kwalificatiedossiers}"
LOKAAL_PAD="${KWALDOSSIERS_LOKAAL:-../kwalificatiedossiers}"

if ! command -v rclone >/dev/null 2>&1; then
    echo "Fout: rclone is niet geïnstalleerd. Installeer via:"
    echo "  curl https://rclone.org/install.sh | sudo bash"
    echo "  rclone config   # configureer een Box-remote"
    exit 1
fi

if ! rclone listremotes | grep -qx "${REMOTE}:"; then
    echo "Fout: remote '${REMOTE}:' niet gevonden in rclone config."
    rclone listremotes
    exit 1
fi

if [[ "${1:-}" == "--upload" ]]; then
    echo "Upload ${LOKAAL_PAD}/  →  ${REMOTE}:${REMOTE_PAD}/"
    rclone copy "${LOKAAL_PAD}" "${REMOTE}:${REMOTE_PAD}" \
        --progress --transfers 8 --checkers 16 \
        --exclude '*.zip' --exclude '_tmp.pdf'
    echo "Upload klaar."
else
    echo "Sync ${REMOTE}:${REMOTE_PAD}/  →  ${LOKAAL_PAD}/"
    mkdir -p "${LOKAAL_PAD}"
    rclone copy "${REMOTE}:${REMOTE_PAD}" "${LOKAAL_PAD}" \
        --progress --transfers 8 --checkers 16
    echo "Klaar. Aantal bestanden in ${LOKAAL_PAD}:"
    find "${LOKAAL_PAD}" -type f | wc -l
fi
