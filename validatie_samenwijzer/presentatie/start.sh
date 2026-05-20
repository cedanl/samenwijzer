#!/usr/bin/env bash
# Installeer (indien nodig) en start de Validatie Samenwijzer-presentatie in één commando.
set -euo pipefail

# Draai altijd vanuit de map waarin dit script staat
cd "$(dirname "$0")"

if ! command -v node >/dev/null 2>&1; then
  echo "Node.js is niet gevonden. Installeer Node (https://nodejs.org) en probeer opnieuw."
  exit 1
fi

# Dependencies alleen installeren als ze nog ontbreken
if [ ! -d node_modules ]; then
  echo "→ Dependencies installeren (eenmalig)…"
  npm install
fi

echo "→ Presentatie starten op http://localhost:3030 (Ctrl-C om te stoppen)…"
npm run dev
