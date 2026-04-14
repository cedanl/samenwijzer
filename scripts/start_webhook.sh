#!/usr/bin/env bash
# Start de FastAPI webhook + ngrok tunnel voor lokaal testen.
# Gebruik: bash scripts/start_webhook.sh

set -euo pipefail

cd "$(dirname "$0")/.."

# Laad .env zodat NGROK_AUTHTOKEN beschikbaar is
if [ -f .env ]; then
  export $(grep -v '^#' .env | xargs)
fi

PORT=8502

echo "▶ Webhook starten op poort $PORT..."
uv run uvicorn app.webhook:app --host 0.0.0.0 --port "$PORT" &
UVICORN_PID=$!

sleep 2

echo "▶ ngrok tunnel starten..."
ngrok http "$PORT" --log stdout &
NGROK_PID=$!

sleep 3

# Haal de publieke URL op via de ngrok API
PUBLIC_URL=$(curl -s http://localhost:4040/api/tunnels | python3 -c \
  "import sys,json; t=json.load(sys.stdin)['tunnels']; print(next(x['public_url'] for x in t if x['proto']=='https'))" \
  2>/dev/null || echo "")

if [ -n "$PUBLIC_URL" ]; then
  echo ""
  echo "✅ Webhook bereikbaar op:"
  echo "   $PUBLIC_URL/webhook/whatsapp"
  echo ""
  echo "👉 Kopieer deze URL naar Twilio Sandbox:"
  echo "   Messaging → Try it out → Sandbox Settings"
  echo "   'When a message comes in': $PUBLIC_URL/webhook/whatsapp"
  echo ""
else
  echo "⚠ Kon de ngrok URL niet ophalen. Kijk op http://localhost:4040"
fi

echo "Druk Ctrl+C om alles te stoppen."
wait $UVICORN_PID $NGROK_PID
