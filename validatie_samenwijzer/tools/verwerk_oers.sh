#!/usr/bin/env bash
# Volledige OER-verwerkingspipeline: hernoem → indexeer
#
# Gebruik:
#   ./tools/verwerk_oers.sh            # alles verwerken
#   ./tools/verwerk_oers.sh --preview  # alleen laten zien wat er hernoemd wordt

set -euo pipefail

PREVIEW=false
if [[ "${1:-}" == "--preview" ]]; then
    PREVIEW=true
fi

echo "=== Stap 1: bestandsnamen aanvullen met crebo/leerweg/cohort ==="
if $PREVIEW; then
    uv run python tools/rename_oers.py --dry-run
    echo ""
    echo "Preview klaar. Voer './tools/verwerk_oers.sh' uit om daadwerkelijk te verwerken."
    exit 0
fi

uv run python tools/rename_oers.py

echo ""
echo "=== Stap 2: OERs indexeren in vectordatabase ==="
uv run python -m validatie_samenwijzer.ingest --alles --reset

echo ""
echo "Klaar."
