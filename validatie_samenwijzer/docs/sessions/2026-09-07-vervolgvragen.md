# Sessielog 2026-09-07 — klikbare vervolgvragen (PR #255, digitale-gids v31)

## Doel
Na elk chatantwoord direct 3 klikbare vervolgvragen tonen, naast het gewone invoerveld.
Fan-out met twee sonnet-subagents (backend / frontend), regie + integratie + smoke centraal.

## Resultaat
- `chat.genereer_vervolgvragen()` — Haiku 4.5, niet-streaming, JSON-array; best-effort (nooit
  raisen, `[]` bij API-/parsefout), dedup + cap 4 + trunc 140. Via `_ai._client()`.
- `POST /api/vervolgvragen` — leest laatste beurt uit de sessie; read-only, uitgezonderd van de
  middleware-bewaar (lost-update, zelfde reden als `/api/chat`). Alleen actief met geladen OER;
  intake-modus toont bewust geen chips.
- `chat.js` `toonVervolgvragen()` — skeleton-pills → `.vervolg-chip` (textContent); klik of
  handmatig typen verwijdert oude chips. `app.css` `.vervolg-*` (mono-label, hover-lift,
  shimmer, staggered fade-in, reduced-motion, full-width ≤560px).
- Bevinding frontend-agent: de donkere `.bubble-a` (app.css ~121) stylet alleen de statische
  demo-band; échte chat is in beide contexten licht → één thema-variant.
- 12 tests (295 groen). Smoke lokaal + live: student `/student`, publieke overlay, desktop 1280,
  mobiel; 0 console-errors (behalve pre-existing `favicon.ico` 404).
- CLAUDE.md: webzoek-invariant (5e instelling-lijst `_INSTELLING_DOMEINEN`, niet in sync-test).

## Observaties (niet gefixt)
- Kandidaatscoring koos bij "Bedrijfsleider paardensport, BOL 2025" de OER van *Vakbekwaam
  medewerker paardensport 2026* (enige Aeres-paard-OER) — het model meldt dat netjes, maar de
  chips volgen dan de "buiten bereik"-tekst. Pre-existing gedrag van `identificeer_oer_kandidaten`.
- `ruff format --check` flagt `db.py` + `oer_catalogus.py` op main (pre-existing).
- `/favicon.ico` 404 op prod.

## Kosten/latency
Chips verschijnen ~10–22 s na de vraag (stream + Haiku-call); Haiku-call zelf ~1–2 s.
