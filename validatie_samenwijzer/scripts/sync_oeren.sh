#!/usr/bin/env bash
# Synchroniseer de oeren/-tree vanuit Box (of een ander rclone-remote).
#
# Eenmalige setup per machine:
#   rclone config            # voeg een Box-remote toe (kies "box", OAuth-flow)
#   # noteer de gekozen remote-naam, bv. "box"
#
# Default remote/pad:        box:samenwijzer/oeren
# Override via env-vars:
#   RCLONE_REMOTE=box        # naam van de remote uit `rclone config`
#   RCLONE_OEREN_PAD=samenwijzer/oeren
#   OEREN_PAD=../oeren       # lokaal doel (default uit .env van dit subproject)

set -euo pipefail

REMOTE="${RCLONE_REMOTE:-box}"
REMOTE_PAD="${RCLONE_OEREN_PAD:-samenwijzer/oeren}"
LOKAAL_PAD="${OEREN_PAD:-../oeren}"

if ! command -v rclone >/dev/null 2>&1; then
    echo "Fout: rclone is niet geïnstalleerd. Installeer via:"
    echo "  curl https://rclone.org/install.sh | sudo bash"
    echo "  rclone config   # configureer een Box-remote"
    exit 1
fi

if ! rclone listremotes | grep -qx "${REMOTE}:"; then
    echo "Fout: remote '${REMOTE}:' niet gevonden in rclone config."
    echo "Beschikbare remotes:"
    rclone listremotes
    echo ""
    echo "Voer 'rclone config' uit en voeg een Box-remote toe."
    exit 1
fi

echo "Sync ${REMOTE}:${REMOTE_PAD}/  →  ${LOKAAL_PAD}/"
mkdir -p "${LOKAAL_PAD}"
rclone copy "${REMOTE}:${REMOTE_PAD}" "${LOKAAL_PAD}" \
    --progress \
    --transfers 8 \
    --checkers 16

echo ""
echo "Klaar. Aantal bestanden in ${LOKAAL_PAD}:"
find "${LOKAAL_PAD}" -type f | wc -l
