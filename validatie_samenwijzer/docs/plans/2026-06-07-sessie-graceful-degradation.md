# Sessie-log 2026-06-07 — Graceful degradation (webzoeken) implementeren + web_fetch-fix

*Subproject: `validatie_samenwijzer` ("De digitale gids", `digitale-gids.fly.dev`).*
*Vervolg op de sessie van 2026-06-06 (Da Vinci-namen + Deltion + het degradatie-plan).*

## Scope

Het op 06-06 geschreven plan (`2026-06-06-graceful-degradation-webzoeken.md`) implementeren:
de chat mag, als de geladen documenten een vraag niet behandelen, gericht op de officiële
website van de instelling zoeken — met een ⚠️-waarschuwing + bron-URL, zonder de juridische
OER-citatieplicht te ondermijnen. Per fase geïmplementeerd, gedeployd en live geverifieerd.

## 1. Fase 1 — publieke pagina (PR #164)

- `chat.py`: `_INSTELLING_DOMEINEN` (geverifieerde officiële domeinen) + `web_zoek_domeinen()`;
  `genereer_antwoord(web_search_domeinen=…)` voegt de **`web_search_20250305`**-tool toe met
  `allowed_domains` + `max_uses=3`. Bewust de niet-dynamic-filtering-versie → geen
  code-execution-afhankelijkheid.
- Beide system-templates: conditioneel `{web_zoek_blok}` (uitzonderingsregel + verplichte
  ⚠️-balk + `Bron:`-URL + verbod op OER-stijl citaten voor webinfo).
- `0_oer_vraag.py` bedraad; session-key `pub_oer_domeinen`.
- **Domeinverificatie betaalde zich uit**: `utrecht` bleek **MBO Utrecht → mboutrecht.nl**
  (níet ROC MN/rocmn.nl), `talland → talland.nl` — uit OER-content + webcheck.
- Live geverifieerd (beide paden, publiek/gast).

## 2. Attributie-afspraak (geheugen)

Op verzoek van Ed: commits en PR's eindigen voortaan met **uitsluitend** de regel
"Ed de Feber, in nauwe samenwerking met Claude" — **geen** `Co-Authored-By`-trailer of
"Generated with"-regel meer (dat was dubbelop). Reflecteert de co-creatie, Ed voorop.
Vastgelegd in persoonlijk geheugen (`feedback_commit_attribution`).

## 3. Fase 1-status + E501-opruiming (PR #165)

Plan-status → "Fase 1 live"; twee lange Da Vinci-titelstrings in `tests/test_ingest.py`
(uit de 06-06-sessie) via concatenatie onder de regellengte → ruff schoon incl. `tests/`.

## 4. Fase 2 — student- & mentor-pagina's (PR #166)

- `main.py`: korte instelling-sleutel als `instelling_naam` in session_state (student via
  OER-join, mentor via instellingen-query) — die had de domeinmap nodig.
- `1_oer_assistent.py` (student) + `5_begeleidingssessie.py` (mentor): domeinen afleiden,
  `web_zoeken=True`, `web_search_domeinen` doorgeven.
- Live geverifieerd per rol.

## 5. web_fetch-betrouwbaarheidsfix (PR #167)

**Ed merkte een echte bug op**: student kreeg wél concrete open-dag-data, mentor niet —
zelfde pagina, zelfde code. Oorzaak: `web_search` geeft alleen **snippets**; of een feit
(datum) erin zit verschilt per zoekopdracht (student had geluk). Geen rolverschil.

- Fix: **`web_fetch_20250910`** toegevoegd naast `web_search` (beide gescoped via
  `allowed_domains`). web_fetch leest de **volledige paginatekst** → feiten missen niet meer.
  Geen code-execution-afhankelijkheid; `max_uses=2`, `max_content_tokens=30000`, citations aan;
  mag alleen URLs uit eerdere search-resultaten openen.
- Template: model opent nu de gevonden pagina (niet op snippets vertrouwen) en toont de
  ⚠️-balk **exact één keer** (verhelpt de eerder waargenomen dubbele balk).
- Hertest per rol (lokaal + live): student én mentor krijgen nu beide de volledige
  activiteitentabel met concrete data (12/16/25 juni, 8 juli) + één balk + `Bron:` davinci.nl.
  Normale OER-vraag blijft een schone OER-citatie zonder balk.

## 6. Plan-status bijgewerkt (PR #168)

Status → "Fase 1 + 2 + web_fetch live"; §8 markeert Fase 1/2 als gedaan, web_fetch onder
Fase 3 als gedaan; dynamic filtering blijft optioneel.

## Resultaat

Graceful degradation is **compleet en betrouwbaar live** voor publiek, student én mentor.
Alles per stap: ruff + 165 tests groen, CI groen, gemerged, Fly-deploy, live twee-paden-verificatie.

## Open (Fase 3, optioneel)

- Dynamic filtering (`web_search_20260209` / `web_fetch_20260209` + code-execution-tool) voor
  extra token-efficiëntie.
- Structurele citatie-bronkaartjes uit de server-side response (i.p.v. URL-in-tekst).
- `pause_turn`-resume-loop voor complexere zoekopdrachten.
- Domeinmap naar de DB als het aantal instellingen groeit.
- Token-/kostenmeting met `scripts/meet_token_kosten.py`.

## Werkwijze-notitie (valkuil)

Lokale Streamlit-herstart: `pkill -f "streamlit"` matcht z'n **eigen shell** (cmdline bevat
"streamlit") en breekt de rest van het commando af; en `nohup … & disown` overleefde de
tool-afronding niet betrouwbaar. Oplossing die wél werkte: de app starten via de
**harness-background** (Bash `run_in_command`/`run_in_background`), en kill in een **apart**
commando los van git-operaties.
