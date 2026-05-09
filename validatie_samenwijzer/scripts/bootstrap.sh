#!/usr/bin/env bash
# Volledige machine-setup voor validatie_samenwijzer:
#   1. Sync oeren/ vanuit Box (rclone)
#   2. uv sync (incl. dev deps)
#   3. ingest --alles (bouw oeren.db op)
#   4. seed.py (basis-accounts)
#
# Gebruik: ./scripts/bootstrap.sh [--skip-sync] [--skip-seed] [--seed-bulk]

set -euo pipefail

SKIP_SYNC=false
SKIP_SEED=false
SEED_BULK=false

for arg in "$@"; do
    case "$arg" in
        --skip-sync) SKIP_SYNC=true ;;
        --skip-seed) SKIP_SEED=true ;;
        --seed-bulk) SEED_BULK=true ;;
        *) echo "Onbekende optie: $arg"; exit 1 ;;
    esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}/.."

echo "=== 1. Dependencies (uv sync) ==="
uv sync --extra dev

if $SKIP_SYNC; then
    echo ""
    echo "=== 2. Sync oeren/  (overgeslagen via --skip-sync) ==="
else
    echo ""
    echo "=== 2. Sync oeren/ vanuit Box ==="
    "${SCRIPT_DIR}/sync_oeren.sh"
fi

echo ""
echo "=== 3. OERs indexeren ==="
uv run python -m validatie_samenwijzer.ingest --alles

if $SKIP_SEED; then
    echo ""
    echo "=== 4. Seed-data  (overgeslagen via --skip-seed) ==="
else
    echo ""
    echo "=== 4. Basis-accounts ==="
    uv run python scripts/seed.py
    if $SEED_BULK; then
        echo ""
        echo "=== 4b. Bulk-seed (~1000 studenten) ==="
        uv run python scripts/seed_bulk.py
    fi
fi

echo ""
echo "Klaar. Start de app met:"
echo "  uv run streamlit run app/main.py"
