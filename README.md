# Samenwijzer

Python/Streamlit app die AI en Data gebruikt om MBO-studenten te ondersteunen bij het leren.

**Doelgroepen:** studenten (voortgang, AI-tutor, welzijnscheck) en docenten/mentoren
(groepsoverzicht, outreach, campagnebeheer).

## Functies

### Voor studenten
- **Mijn voortgang** — voortgang per kerntaak en werkproces, BSA-status, cohortpositie
- **Leercoach** — AI-tutor (Socratisch), gepersonaliseerd lesmateriaal, oefentoetsen, werkfeedback
- **Welzijnscheck** — self-assessment (studieplanning, welzijn, financiën, stage); AI-reactie + signaal naar mentor

### Voor docenten/mentoren
- **Groepsoverzicht** — voortgang eigen studenten, risicosignalering, welzijnschecks, peer matching
- **Outreach** — werklijst at-risk studenten, AI-berichtgeneratie met verwijslogica, e-mailverzending
- **Campagnes** — gerichte outreach per transitiemoment (BSA-risico, bijna klaar)
- **Effectiviteit** — contactratio, responsratio, statustrechter, interventies per mentor

## Installation

```bash
# Requires uv (https://docs.astral.sh/uv/)
uv sync
```

Maak een `.env` in de projectroot aan:

```
ANTHROPIC_API_KEY=sk-ant-...

# Optioneel — voor e-mailverzending vanuit de outreach-pagina:
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USER=noreply@example.com
SMTP_PASSWORD=...
SMTP_AFZENDER=noreply@example.com
```

## Usage

```bash
uv run streamlit run app/main.py
```

Open http://localhost:8501 in your browser.

Inloggen: wachtwoord **Welkom123** (geldt voor zowel student als docent).

## Development

### Devcontainer

Open the repository in VS Code and choose **Reopen in Container**.

### Tests

```bash
uv run pytest
```

### Linting

```bash
uv run ruff check src/ app/
uv run ruff format src/ app/
```

### Type checking

```bash
uv run ty check
```

## License

MIT
