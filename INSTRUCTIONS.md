# INSTRUCTIONS.md

Hoe je de volledige Samenwijzer-omgeving opstart.

## Vereisten

- **Python 3.13** en **uv** geïnstalleerd
- **ngrok** voor lokale webhook-tests (`uv tool install ngrok`)
- Een `.env` in de projectroot (zie onderaan)

---

## 1. Dependencies installeren

```bash
uv sync
```

---

## 2. Data initialiseren (eerste keer)

Beide databronnen zijn gitignored en moeten lokaal gegenereerd worden. **Volgorde is verplicht** — de synthetische dataset leest instellingen uit `oeren.db`.

```bash
# Eerst: vul oeren.db vanuit de oeren/-PDFs
uv run python scripts/build_oer_catalog.py

# Daarna: genereer data/01-raw/synthetisch/studenten.csv (1000 studenten, seed=42)
uv run python scripts/generate_synthetisch_data.py
```

Vereist dat de `oeren/`-map met submappen per instelling lokaal aanwezig is.

---

## 3. Streamlit-app starten

```bash
uv run streamlit run app/main.py
```

Opent op **http://localhost:8501**.

Inloggen:
| Rol | Gebruikersnaam | Wachtwoord |
|---|---|---|
| Student | een studentnummer uit de dataset (bijv. `100001`) | `Welkom123` |
| Docent | een mentornaam uit de dataset (bijv. `M. de Vries`) | `Welkom123` |

---

## 4. WhatsApp webhook starten (alleen bij WhatsApp-functionaliteit)

De webhook is een aparte FastAPI-server die inkomende WhatsApp-berichten van Twilio ontvangt.
Start hem **naast** de Streamlit-app in een tweede terminal:

```bash
uv run uvicorn app.webhook:app --host 0.0.0.0 --port 8502
```

Controleer of hij draait:

```bash
curl http://localhost:8502/health
# {"status":"ok"}
```

### Ngrok tunnel (voor Twilio-koppeling)

Twilio heeft een publiek bereikbare URL nodig. Maak een tunnel naar poort 8502:

```bash
ngrok http 8502
```

Kopieer de `https://...ngrok-free.app`-URL en stel hem in op:
**Twilio Console → Messaging → Sandbox → "When a message comes in"**

```
https://<jouw-ngrok-url>/webhook/whatsapp
```

---

## 5. Wekelijkse check-in handmatig versturen (scheduler)

De scheduler draait normaal automatisch via GitHub Actions (elke maandag 08:00).
Lokaal testen:

```bash
# Dry run — logt berichten maar verstuurt niets
DRY_RUN=true uv run python -m samenwijzer.scheduler

# Echt versturen (vereist Twilio-credentials in .env)
uv run python -m samenwijzer.scheduler
```

---

## 6. Volledige opstartsvolgorde

Bij volledige lokale test met WhatsApp:

```
Terminal 1:  uv run streamlit run app/main.py
Terminal 2:  uv run uvicorn app.webhook:app --host 0.0.0.0 --port 8502
Terminal 3:  ngrok http 8502
```

Stel de ngrok-URL in Twilio in (stap 4), dan kun je een WhatsApp-bericht sturen naar het Twilio sandbox-nummer en de verwerking live volgen.

---

## .env-bestand

Maak `.env` aan in de projectroot (staat in `.gitignore`):

```
# Verplicht voor AI-functies
ANTHROPIC_API_KEY=sk-ant-...

# Optioneel — e-mail vanuit de outreach-pagina
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USER=noreply@example.com
SMTP_PASSWORD=...
SMTP_AFZENDER=noreply@example.com

# Optioneel — WhatsApp via Twilio
TWILIO_ACCOUNT_SID=...
TWILIO_AUTH_TOKEN=...
TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886
WHATSAPP_ENCRYPT_KEY=...   # leeg laten → wordt automatisch aangemaakt in data/02-prepared/.whatsapp.key
```

---

## Poorten op een rij

| Proces | Poort |
|---|---|
| Streamlit-app | 8501 |
| FastAPI webhook | 8502 |
