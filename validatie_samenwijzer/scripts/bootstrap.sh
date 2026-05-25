#!/usr/bin/env bash
# Volledige machine-setup voor validatie_samenwijzer:
#   1. uv sync (incl. dev deps)
#   2. Sync oeren/ vanuit Box (rclone)
#   3. Sync kwalificatiedossiers/ vanuit Box (rclone)
#   4. ingest --alles (bouw oeren.db op)
#   5. seed_bulk.py (~1000 studenten over alle geïndexeerde OERs)
#
# --skip-sync slaat zowel oeren als kwalificatiedossiers over; voor afzonderlijke
# overslagen gebruik --skip-oeren-sync of --skip-kd-sync.
#
# Gebruik:
#   ./scripts/bootstrap.sh                # default
#   ./scripts/bootstrap.sh --skip-sync    # beide trees al lokaal
#   ./scripts/bootstrap.sh --skip-kd-sync # alleen oeren-sync
#   ./scripts/bootstrap.sh --skip-seed    # geen testdata aanmaken
#   ./scripts/bootstrap.sh --seed-minimal # i.p.v. bulk: alleen seed.py (dev-demo)

set -euo pipefail

SKIP_OEREN_SYNC=false
SKIP_KD_SYNC=false
SKIP_SEED=false
SEED_MINIMAL=false

for arg in "$@"; do
    case "$arg" in
        --skip-sync) SKIP_OEREN_SYNC=true; SKIP_KD_SYNC=true ;;
        --skip-oeren-sync) SKIP_OEREN_SYNC=true ;;
        --skip-kd-sync) SKIP_KD_SYNC=true ;;
        --skip-seed) SKIP_SEED=true ;;
        --seed-minimal) SEED_MINIMAL=true ;;
        *) echo "Onbekende optie: $arg"; exit 1 ;;
    esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}/.."

echo "=== 1. Dependencies (uv sync) ==="
uv sync --extra dev

if $SKIP_OEREN_SYNC; then
    echo ""
    echo "=== 2. Sync oeren/  (overgeslagen) ==="
else
    echo ""
    echo "=== 2. Sync oeren/ vanuit Box ==="
    "${SCRIPT_DIR}/sync_oeren.sh"
fi

if $SKIP_KD_SYNC; then
    echo ""
    echo "=== 3. Sync kwalificatiedossiers/  (overgeslagen) ==="
else
    echo ""
    echo "=== 3. Sync kwalificatiedossiers/ vanuit Box ==="
    "${SCRIPT_DIR}/sync_kwalificatiedossiers.sh"
fi

echo ""
echo "=== 4. OERs indexeren ==="
uv run python -m validatie_samenwijzer.ingest --alles

if $SKIP_SEED; then
    echo ""
    echo "=== 5. Seed-data  (overgeslagen via --skip-seed) ==="
elif $SEED_MINIMAL; then
    echo ""
    echo "=== 5. Minimale dev-seed (3 studenten + 2 mentoren) ==="
    uv run python scripts/seed.py
else
    echo ""
    echo "=== 5. Bulk-seed (~1000 studenten over alle geïndexeerde OERs) ==="
    uv run python scripts/seed_bulk.py
fi

echo ""
echo "Klaar. Start de app met:"
echo "  uv run streamlit run app/main.py"
