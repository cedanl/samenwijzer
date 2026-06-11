#!/usr/bin/env bash
# Start de FastAPI-app ("De digitale gids") lokaal.
#   - Draait uvicorn met --reload op poort 8504 (override met PORT=...).
#   - Vereist SESSION_SECRET + ALGEMEEN_WACHTWOORD in .env (ANTHROPIC_API_KEY voor de chat).
#
# Gebruik:
#   ./start.sh              # poort 8504, reload aan
#   PORT=9000 ./start.sh    # andere poort
#   ./start.sh --no-reload  # zonder auto-reload

set -euo pipefail

cd "$(dirname "$0")"

PORT="${PORT:-8504}"
RELOAD="--reload"
[[ "${1:-}" == "--no-reload" ]] && RELOAD=""

if [[ ! -f .env ]]; then
  echo "FOUT: geen .env in $(pwd) — kopieer .env.example of vul SESSION_SECRET + ALGEMEEN_WACHTWOORD in." >&2
  exit 1
fi

for key in SESSION_SECRET ALGEMEEN_WACHTWOORD; do
  if ! grep -qE "^${key}=.+" .env; then
    echo "FOUT: ${key} ontbreekt of is leeg in .env" >&2
    exit 1
  fi
done

echo "→ De digitale gids op http://localhost:${PORT}"
exec uv run uvicorn app_fastapi.main:app --port "${PORT}" ${RELOAD}
