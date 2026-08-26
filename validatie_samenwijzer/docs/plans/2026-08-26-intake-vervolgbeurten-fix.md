# Plan: intake-vervolgbeurten kunnen alsnog een OER laden

## Context

De publieke chat kent drie modi (chat/kies/intake). OER-identificatie
(`identificeer_oer_kandidaten`) draait alleen in `POST /api/vraag`, en de frontend roept die
route alleen aan bij de **eerste** vraag vanaf de landingspagina (`start()` in
`app_fastapi/static/app.js`). Vervolgberichten in de chat-overlay gaan via de `ovAsk`-handler
rechtstreeks naar `POST /api/chat`; zonder geladen OER valt die in de intake-tak
(`genereer_intake_antwoord`). Die intake-LLM verzamelt instelling/opleiding/leerweg/cohort maar
heeft géén brug terug naar identificatie — hij verzint dan "Ik ga de OER opzoeken… helaas geen
toegang", terwijl de OER bestaat. Doodlopende straat.

Fix in drie onafhankelijke taken (disjuncte bestanden):

## Global Constraints

- Subproject `validatie_samenwijzer/`: draai `uv`, `pytest`, `ruff` vanuit die map.
- Geen business logic in `app_fastapi/` verplaatsen: `identificeer_oer_kandidaten` blijft in
  `src/validatie_samenwijzer/chat.py`; de route mag hem alleen aanroepen.
- Chirurgische wijzigingen: geen refactors van aangrenzende code, match bestaande stijl.
- ruff: line-length 100, selectie E,F,I,N,W,UP. Lint + format moeten groen zijn.
- Alle bestaande tests (baseline: 277 passed) blijven groen.
- UI-teksten en prompts in het Nederlands.
- Commit NIET zelf — de coördinator commit na review.

## Task 1 — `/api/vraag`: scoor op opgetelde gesprekstekst

**Bestand:** `app_fastapi/main.py` (route `api_vraag`, regel ~177) + tests.

Nu scoort de route alleen op het losse `vraag`-veld. Een vervolgbeurt als "2024" of
"Tandartsassistent, BOL" heeft context uit eerdere beurten nodig.

**Wijziging:** in `api_vraag`, na de bestaande `s.oer_systeem`-shortcut: bouw de scoretekst als
concatenatie van alle **user**-beurten uit `s.chat_history` plus de nieuwe vraag:

```python
context_tekst = " ".join(
    [b["content"] for b in s.chat_history if b["role"] == "user"] + [vraag]
)
kandidaten = identificeer_oer_kandidaten(oers, context_tekst, min_score=1)
```

Verder niets aan de route veranderen. Bij lege historie is `context_tekst` gelijk aan `vraag`
(gedrag eerste beurt ongewijzigd). `s.wachtende_vraag` blijft de **kale** nieuwe `vraag` (niet de
concatenatie): dat is de vraag die na de picker gesteld wordt.

**Tests (TDD — eerst schrijven, rood zien, dan implementeren):** nieuw bestand
`tests/test_intake_vervolg.py`, patronen overnemen uit `tests/test_fastapi_poc.py` (TestClient,
sessie-cookies, fixtures/mocks; `tests/conftest.py` reset de `_ai`-client al).

1. *Vervolgbeurt met accumulatie:* seed een sessie waarvan `chat_history` een eerdere user-beurt
   bevat met instelling+opleiding-woorden die met de nieuwe vraag samen op precies één of
   meerdere kandidaten matchen (gebruik gemockte/gesynthetiseerde OER-rijen zoals bestaande
   tests dat doen, of de echte `data/validatie.db` als bestaande tests daarop leunen). POST
   `/api/vraag` met alleen een fragment ("cohort 2025", "BOL 2025") → verwacht modus `chat` of
   `kies`, niet `intake`.
2. *Eerste beurt ongewijzigd:* zonder historie, vraag zonder herkenbare instelling/opleiding →
   modus `intake`.
3. *OER al geladen:* bestaande shortcut blijft werken (modus `chat` met labels).

Seed de historie via de bestaande sessie-API (bijv. `get_sessie` op een request/cookie zoals
bestaande tests, of door eerst een gemockte `/api/chat`-beurt te doen) — geen private hacks als
het publiek kan.

## Task 2 — frontend: vervolgbeurten zonder OER via `/api/vraag` routeren

**Bestand:** `app_fastapi/static/app.js` (alleen dit bestand).

De `ovAsk`-submit-handler (regel ~176) doet nu altijd `addVraag` + `streamAntwoord`. Wijziging:
als er nog geen studiegids geladen is (`oerIds.length === 0`), route het bericht door dezelfde
modus-flow als `start()`:

1. `addVraag(thread, v)` (zoals nu).
2. POST `/api/vraag` met `{vraag: v}` (zelfde fetch-vorm als in `start()`).
3. `r.modus === "kies"` → `renderPicker()` en stop (de wachtende vraag wordt na de keuze
   server-side teruggegeven, zoals bij `start()`).
4. `r.modus === "chat"` → `oerIds = r.oer_ids || oerIds; setLabels(r.labels);
   setBanner(r.oer_onleesbaar);` en dan `streamAntwoord(thread, v)`.
5. `r.modus === "intake"` → `streamAntwoord(thread, v)` (huidig gedrag).

Als er wél een OER geladen is: huidig gedrag (direct `streamAntwoord`). Extraheer desgewenst een
kleine gedeelde helper voor stap 2-5 die ook `start()` gebruikt — maar houd de diff minimaal en
verander niets aan `start()`s overlay/hydratatie-gedrag. Geen andere handlers aanpassen.

Let op: statische assets worden gecachet (hard-refresh nodig bij handmatig testen); geen
JS-unittests in dit project — verificatie gebeurt door de coördinator via browser-smoke.

## Task 3 — intake-prompt: geen "ik ga het opzoeken"-claims

**Bestand:** `src/validatie_samenwijzer/chat.py`, constante `_INTAKE_SYSTEEM` (regel ~737).
Alleen deze string wijzigen.

Herschrijf de prompt zo dat de assistent:
- nog steeds vriendelijk en beknopt de vier velden uitvraagt (instelling, opleiding
  naam/crebo, leerweg BOL/BBL, cohort/startjaar);
- **nooit** beweert dat hij een OER/studiegids gaat "opzoeken", "laden" of "raadplegen", en
  nooit zegt dat een specifieke OER wel of niet in "het systeem" zit — hij kán niet zoeken;
- wanneer alle velden bekend zijn: de student vraagt het gesprek te herhalen met de gegevens in
  één bericht, óf te kiezen via de opleidingskiezer ("Of kies direct je opleiding" op de
  startpagina / de keuzelijst in het chatvenster) — dat is de route die de studiegids echt
  laadt;
- in het Nederlands blijft antwoorden.

Houd de prompt compact (vergelijkbare lengte als nu). Controleer met een grep of geen test op de
oude prompttekst asserteert; zo ja, werk die test bij.
