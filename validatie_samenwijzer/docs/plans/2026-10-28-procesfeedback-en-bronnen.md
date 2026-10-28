# Spec: eerlijke procesfeedback tijdens het wachten + bronnenlijst onder het antwoord

**Datum:** 2026-10-28 · **Status:** vastgesteld (door Claude, op verzoek van Ed; open vragen onderaan)
· **Deploy:** ná de presentatie van 28-10 (prod blijft tot dan op v50).

## Aanleiding

Ed testte prod na PR #304 en zag twee dingen:

1. De wachtindicator zegt altijd "Studiegids lezen". Als het antwoord níet in de studiegids
   staat maar in een ander officieel document (of op de website), merkt de gebruiker dat pas
   aan de banner in het antwoord. Ed wil dat de gids dat als procesfeedback laat zien, in de
   geest van "staat niet in de studiegids, ik zoek nu in de andere officiële bronnen".
2. Naast het antwoord wil Ed de gebruikte bronnen zien, als nette titels (zonder extensie).

## Wat er écht gebeurt (randvoorwaarde voor eerlijkheid)

De chat stuurt **alle** bronnen in één prompt mee (OER, KD, skills, schooldocumenten; zie
`chat.py`, caps 500K/300K/50K/300K). Het model leest ze tegelijk — er is geen fase "eerst de
OER, dan de rest". Een statusmelding op een timer zou dus toneel zijn. Er zijn maar twee
eerlijke signalen:

- **Webzoek is een echt event.** Als het model `web_search`/`web_fetch` aanroept, komt dat als
  `server_tool_use`-contentblok in de stream, vóór de antwoordtekst.
- **"Niet in de studiegids" zegt het model zelf**, als eerste regel van het antwoord: de
  ℹ️-banner (`_SCHOOLDOC_DISCLAIMER`) of de ⚠️-webbanner (`_WEB_DISCLAIMER`). Die regels zijn
  woordelijk voorgeschreven en al machineherkenbaar (`dedup_disclaimer`).

Alles in deze spec is op die twee signalen gebouwd. Geen fases die niet bestaan.

## Ontwerp

### A. Statusfases in de stream

De backend stuurt SSE-events `{"status": "<code>"}`; de frontend vertaalt codes naar tekst
(zelfde patroon als `FOUT_TEKSTEN`). Codes:

| code | wanneer | tekst in de UI |
|---|---|---|
| `lezen` | direct bij start van een OER-chat | "Studiegids en officiële documenten lezen…" |
| `intake` | start van een intake-beurt (geen OER geladen) | "Opleiding zoeken…" |
| `web` | eerste `server_tool_use` met naam `web_search` of `web_fetch` | "Niet in de documenten gevonden — website van de school raadplegen…" |
| `schooldoc` | eerste antwoordtekst begint met `_SCHOOLDOC_DISCLAIMER` | "Niet in de studiegids — officieel schooldocument van de school gebruikt" |
| `webinfo` | eerste antwoordtekst begint met `_WEB_DISCLAIMER` | "Niet in de documenten — informatie van de schoolwebsite gebruikt" |

Gedrag in de UI: de statusregel staat **boven** de antwoordbubbel en blijft staan zolang de
stream loopt (tekst wordt eronder opgebouwd), zodat de melding niet wegflitst bij het eerste
tekstfragment. Bij `done` verdwijnt de statusregel; de banner in de antwoordtekst en de
bronnenlijst (B) nemen het over. Een statuscode die de frontend niet kent → negeren.

Implementatie: `genereer_antwoord` itereert over `stream`-events i.p.v. `stream.text_stream`
en yieldt naast `str` ook een `Status`-object (dataclass, één veld `code`). De route zet
`Status` om in een `status`-event en laat tekst ongemoeid. `dedup_disclaimer` en de
bronnen-parser (B) krijgen alleen de tekst. De `schooldoc`/`webinfo`-detectie zit in de
route-wrapper op de eerste ~200 tekens (prefix-match met `_prefix_staart` voor gesplitste
chunks). `lage_relevantie` stuurt geen status.

### B. Bronnenlijst onder het antwoord

Alleen het model weet welke bronnen het **gebruikt** heeft (de prompt bevat er tot ~15). De
lijst komt dus van het model, maar in een vast machineformaat dat de backend parseert en
stript; de frontend rendert altijd dezelfde chips. Het model mag de lijst niet vrij
opmaken.

**Formaat (laatste regel van elk antwoord in OER-modus):**

```
<!-- bronnen: studiegids|OER Kok BOL 2026; schooldocument|Studentenstatuut; website|curio.nl -->
```

- items gescheiden door `;`, per item `type|titel`;
- `type` ∈ {`studiegids`, `kwalificatiedossier`, `schooldocument`, `skills`, `website`};
- `titel` = de naam zoals die in de blokkop in de prompt staat (`=== OER … ===`, de kop uit
  `documenten._kop`, "Kwalificatiedossier …"), dus zonder extensie of slug; voor `website` het
  domein, met optioneel `|url` als derde veld;
- geen bronnen gebruikt (bv. "dat staat nergens") → regel weglaten.

**Backend (`chat.py`):** één pure functie `splits_bronnen(tekst) -> tuple[str, list[Bron]]`.
Validatie: onbekend type → item weg; titel gestript, max 80 tekens; max 6 items; dubbele
(type, titel) → één. Streaming: zodra de tekst `<!-- bronnen:` bevat (ook over chunk-grenzen,
via `_prefix_staart`) houdt de generator de rest vast; bij stream-einde wordt geparset en
`{"bronnen": [...]}` gestuurd i.p.v. tekst. Tekst ná de sluit-`-->` wordt gewoon doorgegeven.

**Geschiedenis:** de ruwe modeltekst (mét markerregel) blijft in `chat_history`. Het model ziet
zijn eigen eerdere bronnenregels dus terug als voorbeeld van het formaat. `/api/geschiedenis`
geeft per assistent-beurt `content` (gestript) + `bronnen` terug via dezelfde
`splits_bronnen`. Vangnet in de frontend: `renderMarkdown` laat een regel die begint met
`<!-- bronnen:` altijd weg, zodat een parse-fout nooit letterlijk in beeld komt (de renderer
escapet HTML, dus zonder vangnet zou de regel zichtbaar zijn).

**Frontend:** onder de antwoordbubbel een rij chips, label "Bronnen". Chip = type-label +
titel, bv. `Studiegids · OER Kok BOL 2026`, `Schooldocument · Studentenstatuut`,
`Website · curio.nl` (alleen deze laatste is een link, naar de meegegeven url, `rel=noopener`).
Alles via `textContent`, geen innerHTML. Type-labels: Studiegids, Kwalificatiedossier,
Schooldocument, Skills, Website. Geen chips bij lege lijst, intake en `lage_relevantie`.

De citaten mét vindplaats ín de tekst blijven ongewijzigd (juridische citatieplicht,
`_SYSTEEM_TEMPLATE`/`_MULTI_SYSTEEM_TEMPLATE`). De chips zijn een samenvatting, geen vervanging.

### C. Prompt

Toevoegen aan beide systeemtemplates (OER-modus), niet aan intake: een alinea "BRONNENREGEL"
met het exacte formaat, de vijf types, "titel = de naam uit de blokkop", "precies één regel,
helemaal onderaan", en "weglaten als je geen bron gebruikt hebt". Vacature-antwoorden krijgen
geen bronnenregel (de links staan al in de tekst).

## Besluiten

| # | Besluit | Reden |
|---|---|---|
| B1 | Statuscodes komen uit de backend, teksten uit de frontend | De backend weet de modus (oer/intake) en ziet de tool-events; UI-tekst hoort in de UI. Zelfde patroon als `FOUT_TEKSTEN`. |
| B2 | Alleen statussen op echte signalen (tool-event, bannerregel); geen timer-fases | Eerlijkheid. De gids mag niet suggereren dat hij sequentieel zoekt. |
| B3 | Statusregel blijft staan tijdens de hele stream, verdwijnt bij `done` | Anders flitst `schooldoc` weg bij het eerste tekstfragment. Daarna dragen banner + chips de boodschap. |
| B4 | Banner (ℹ️/⚠️) blijft in de antwoordtekst | Kleinste wijziging; staat ook in de bewaarde geschiedenis. Banner uit de tekst lichten is een aparte, latere keuze (zie open vragen). |
| B5 | Bronnenlijst door het model, in HTML-commentaarformaat, geparset en gestript door de backend | Alleen het model kent de gebruikte bronnen; vast formaat geeft consistente chips en voorkomt vrije opmaak. Commentaarsyntax is onzichtbaar als een vangnet faalt. |
| B6 | Titel zonder extensie, mét type-label | Een student heeft niets aan `.pdf`; het type-label maakt studiegids/schooldocument/website zichtbaar zonder extra tekst. |
| B7 | Markerregel blijft in `chat_history`, parse op de read-boundary | Eén parser voor stream én geschiedenis; het model ziet het formaat terug in zijn eigen beurten. |
| B8 | Deploy na de presentatie | Prompt + stream + frontend wijzigen tegelijk; geen verse versie een uur voor de demo. |

## Open vragen voor Ed

1. Banner uit de tekst lichten en als vaste regel boven het antwoord tonen (i.p.v. blockquote
   in de tekst)? Dan drie signalen → twee. Nu bewust buiten scope (B4).
2. Chips voor `studiegids` en `schooldocument` klikbaar maken naar "Mijn studiegids" /
   een documentweergave? Vereist een document-route die er nog niet is.
3. Informatieve documenten (examenplan, onderwijsplan) krijgen geen ℹ️-banner (openstaand sinds
   PR #304). Met chips is dat verdedigbaar: de chip toont wél "Schooldocument".

## Niet in scope

Streamlit-frontend (geretired), WhatsApp, het hoofdproject `app_fastapi/` van samenwijzer,
wijzigingen aan de documentselectie of -zichtbaarheid.

## Implementatieplan (TDD, één PR)

1. `chat.py`: `Status`-dataclass + `Bron`-dataclass; `splits_bronnen()` met tests
   (geldig, onbekend type, >6 items, dubbele, geen marker, tekst na marker, marker over
   chunk-grens).
2. `genereer_antwoord`: event-iteratie; test met een nep-stream die een `server_tool_use`
   content_block_start en tekst levert → yieldt `Status("web")` vóór de tekst.
3. Route `/api/chat`: `status`-events (`lezen`/`intake` direct; `web`; `schooldoc`/`webinfo`
   uit de eerste tekst), `bronnen`-event vóór `done`; `/api/geschiedenis` met `bronnen`.
   Tests via `TestClient` met gemockte generator.
4. Prompt: BRONNENREGEL-alinea in beide OER-templates; test dat de alinea in `bouw_systeem` en
   `bouw_gecombineerd_systeem` zit en níet in intake.
5. `chat.js` + `app.css`: `STATUS_TEKSTEN`, statusregel boven de bubbel, chips-rij, vangnet in
   `renderMarkdown`, rehydratie met `bronnen`.
6. Lokale UI-smoke (verplicht, CLAUDE.md): Landstede kluisjes (schooldoc-status + chips
   Studiegids/Schooldocument), Curio Kok kluiscontrole, Graafschap examenplan (geen banner, wél
   chips), een vraag die webzoek triggert (status `web` + chip Website), intake-beurt (status
   `intake`, geen chips), page-reload (chips blijven).
7. ruff + format + pytest groen; PR; na akkoord van Ed deploy (ná de presentatie).

## Succescriteria

- Bij een schooldocument-antwoord zie je tijdens het streamen een statusregel die zegt dat het
  niet in de studiegids staat; na afloop staan de gebruikte bronnen als chips eronder.
- Bij een webzoek verschijnt de status zodra het model de tool aanroept, niet op een timer.
- Geen `<!-- bronnen:` tekst ooit zichtbaar in de UI, ook niet na reload.
- Bestaande tests blijven groen; disclaimers worden nog steeds gededupliceerd.
