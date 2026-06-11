# Design: vacatures & stages via web_search (prototype)

**Datum:** 2026-06-11
**Status:** ontwerp goedgekeurd, klaar voor implementatieplan
**Scope:** klein, prototype — in-app, op zowel `/` (publiek) als `/student`.

## Probleem

Studenten/mentoren willen in de chat kunnen vragen "zijn er vacatures/stageplaatsen voor
mijn beroep?". De app kent het beroep al (via de skills-bron: crebo → beroep) en de leerweg
(BOL/BBL) uit de OER, maar heeft geen manier om actuele vacatures/stages te tonen.

## Niet-doel (YAGNI)

- Geen Indeed-MCP: die is gebonden aan een claude.ai-sessie-auth (interactieve connector) en
  daardoor niet beschikbaar voor de headless FastAPI-app op Fly. Een server-side MCP-connector of
  eigen jobs-API zou eigen hosting + auth vereisen; de bestaande `web_search` heeft dat niet nodig.
- Geen eigen `zoek_vacatures`-tool / tool-use-loop, geen herrangschikking/dedup in code, geen
  salaris-parsing. Dat kan later als het prototype bevalt.
- Locatie + niveau zijn **prompt-gestuurd** (geen harde code-filter): het model krijgt de plaats
  van de student en het niveau uit de OER/KD-tekst, en scoped de zoekquery daarop. ±10 km is een
  voorkeur die op de site-filters leunt, geen hard afgedwongen straal.

## Aanpak (gekozen: A — altijd beschikbaar, prompt-gestuurd)

Hergebruik de bestaande Anthropic server-side tools `web_search_20250305` + `web_fetch_20250910`.
Verbreed hun `allowed_domains` met de vacaturesites en voeg een prompt-blok toe dat het model
instrueert wannéér (alleen bij expliciete vacature-/stagevraag) en hóe het die mag gebruiken.
Het model beslist op basis van de vraag; geen brosse keyword-detectie in code.

Overwogen alternatieven: B (intent-detectie via trefwoorden in de route — bros), C (eigen
client-side `zoek_vacatures`-tool met code-filtering — te groot voor een prototype). A is het
kleinste dat end-to-end werkt en blijft binnen de AI-isolatie-invariant.

## Architectuur

Alles in `src/validatie_samenwijzer/chat.py` (de enige module met streaming-aanroepen) plus
een paar regels in `app_fastapi/context.py`. Geen nieuwe modules, geen tool-use-loop.

### Kerninzicht: ontkoppel school-webzoek van vacaturezoek

Nu gate't één vlag (`web_zoeken = bool(web_zoek_domeinen)`) zowel de tools als het
`_WEB_ZOEK_BLOK`. De vacaturefunctie moet óók werken als de school **geen** scrapebaar domein
heeft, dus de twee concerns worden onafhankelijk:

- `web_zoeken` (school) → injecteert `_WEB_ZOEK_BLOK`, scope = instelling-domeinen.
- `vacatures` (jobs) → injecteert `_VACATURE_BLOK`, scope = `_VACATURE_DOMEINEN`.
- De tools krijgen de **union** van beide actieve domeinensets als `allowed_domains`.

## Componenten

| Component | Bestand | Wijziging |
|---|---|---|
| `_VACATURE_DOMEINEN` | `chat.py` | nieuwe constante: `["stagemarkt.nl", "indeed.nl"]` (zie crawler-noot) |
| `_VACATURE_BLOK` | `chat.py` | nieuw prompt-blok (patroon van `_WEB_ZOEK_BLOK`) |
| `bouw_systeem` | `chat.py` | nieuwe param `vacatures: bool = False`; injecteert `_VACATURE_BLOK` |
| `bouw_gecombineerd_systeem` | `chat.py` | idem `vacatures: bool = False`, doorgegeven aan single-OER-pad |
| `laad_context` | `app_fastapi/context.py` | bereken union-domeinen, geef `vacatures=True` mee |

`genereer_antwoord` hoeft niet te wijzigen: het neemt al een `web_search_domeinen`-lijst en
scope't beide tools daarop. De route geeft de union (uit de sessie) ongewijzigd door.

## Data-flow

In `context.laad_context()` (na het bouwen van `items`):

```python
school_domeinen = web_zoek_domeinen(items)            # kan leeg zijn
systeem = bouw_gecombineerd_systeem(
    items, web_zoeken=bool(school_domeinen), vacatures=True)
domeinen = sorted(set(school_domeinen) | set(_VACATURE_DOMEINEN))
return systeem, labels, domeinen, oer_onleesbaar
```

`vacatures=True` zodra er ≥1 OER-context is (beroep bekend) → geldt op `/` én `/student`.
De union-domeinen gaan via de sessie (`s.domeinen`) naar `/api/chat`, dat ze ongewijzigd aan
`genereer_antwoord(web_search_domeinen=...)` doorgeeft.

## `_VACATURE_BLOK` — gedrag (presentatie zonder citatie-breuk)

Het blok schrijft voor:

1. Gebruik de vacaturesites **alleen** bij een expliciete vacature-/stagevraag — niet bij
   OER-/examen-/begeleidingsvragen.
2. Stem de zoekopdracht af op **vier dingen**:
   - **beroep** (uit de opleiding/skills hierboven);
   - **leerweg**: BOL → "stage / BPV-plek", BBL → "leerbaan / BBL-plek";
   - **MBO-niveau (1 t/m 4)**: gelezen uit de OER-/KD-tekst die al in de context staat (geen
     apart dataveld — de niveaus staan niet in de DB maar wél in de documenttekst); meegenomen
     in de query (bv. "MBO niveau 3"). Staat het nergens → terugvallen op beroep + leerweg;
   - **locatie**: staat er geen plaats in de vraag, dan vraagt het model **eerst** in welke
     plaats/regio de student wil zoeken (en zoekt nog niet); mét plaats → zoeken "in en rond
     `<plaats>` (±10 km)", breder bij een regio. (Bewuste keuze: locatie via de student vragen
     i.p.v. een instelling→stad-mapping — de DB heeft geen locatie, instellingen zijn vaak
     multi-campus, en een student zoekt z'n stage vaak bij z'n woonplaats.)
3. Begin het vacature-antwoord (zodra er echt resultaten zijn) met één vaste disclaimer-regel
   (externe bron, dagelijks wisselend, géén juridische bron, controleer zelf bij opleiding/SBB).
   Het model wordt geïnstrueerd 'm één keer te schrijven, maar als safety-net **dedupliceert de
   stream-filter `dedup_disclaimer` in code** elke herhaling (het model re-stateth de disclaimer
   soms ná de web_search-tool-call). De disclaimer-string bevat geen `> `-prefix.
4. **Nooit** in OER-citaatvorm ("Volgens de OER", geen artikel-/sectie-/paginanummer), geen
   verzonnen vindplaats.
5. **Elk** resultaat als een **klikbare Markdown-link** `[functietitel — werkgever, plaats](URL)`
   met (waar bekend) het niveau — nooit een kale kop/tabelrij zonder link. Gebruik **altijd** de
   echte URL uit de zoek-/fetch-resultaten en **verzin nooit een URL**; geen eigen URL voor een
   plek → link naar de zoek-/filterpagina van die site. Sluit af met de bron-URL('s).
6. Niets gevonden → eerlijk melden, geen verzonnen vacatures.

De bestaande citatieplicht voor OER/KD/examenreglement blijft volledig ongemoeid; dit is een
gescheiden, gelabeld blok.

## Leerweg in de prompt

Het `_VACATURE_BLOK` verwijst naar "de opleiding en leerweg hierboven". Bij implementatie
verifiëren dat de leerweg expliciet in de (multi-)OER-prompt staat; zo niet, toevoegen aan de
blok-header zodat het model erop kan filteren. (Beroep zit al in het skills-blok wanneer
beschikbaar.)

## Foutafhandeling

`max_uses` blijft 3 search / 2 fetch (binnen het 30s-streamcontract). Web_search-fouten
degraderen al gracieus in de bestaande stream-try/except.

**Crawler-toegankelijkheid (geleerd in de UI-smoke):** een `allowed_domain` dat de Anthropic
web-crawler blokkeert geeft een **400 op de hele `web_search`-call**, niet alleen op de zoekactie.
Omdat de vacaturedomeinen áltijd in de scope zitten, brak een niet-crawlbaar domein
(`nationalevacaturebank.nl`) elk chat-antwoord — ook gewone OER-vragen. Daarom bevat
`_VACATURE_DOMEINEN` **alléén geverifieerd-crawlbare domeinen** (`stagemarkt.nl`, `indeed.nl`).
Een nieuw vacaturedomein toevoegen vereist eerst een live check dat de crawler het toelaat.

## Succescriteria (verifieerbaar)

**Unit (`tests/test_chat.py`):**
- `bouw_systeem(..., vacatures=True)` bevat `_VACATURE_BLOK`; met `vacatures=False` niet.
- `bouw_gecombineerd_systeem(..., vacatures=True)` idem.
- Bestaande tests zonder `vacatures` blijven groen (default `False` → geen gedragswijziging).

**Unit (`tests/test_fastapi_poc.py` of context-test):**
- `laad_context([oer_id])` retourneert domeinen die de drie vacaturesites bevatten.

**UI-smoke (handmatig, verplicht per CLAUDE.md):**
- `/` → "zijn er stageplaatsen voor kok?" → gelabeld vacatureblok met apply-links + disclaimer.
- `/student` (kok-student) → idem.
- **Regressie**: een normale OER-vraag (bv. "hoeveel punten heb ik nodig voor mijn BSA?")
  antwoordt nog steeds mét OER-citaten en zónder vacatureblok.

## Open punten voor later (niet in dit prototype)

- De false-positive uit de demo ("De Kok Staalbouw" matchte op bedrijfsnaam) wordt hier alleen
  via prompt-instructie beperkt; harde code-filtering/herrangschikking is bewust uitgesteld
  (aanpak C) tot na evaluatie van het prototype.
- **Disclaimer-dubbeling (opgelost, code-niveau):** het model herhaalde de disclaimer soms ná de
  web_search-tool-call. Eerst prompt-getweakt (`> `-prefix weg + "exact één keer"), maar dat hield
  niet betrouwbaar. Definitieve fix: de stream-filter `dedup_disclaimer(chunks, disclaimer)` in
  `chat.py` laat de disclaimer **deterministisch hooguit één keer** door (buffert ≤ len-1 tekens om
  een over chunk-grenzen gesplitste herhaling te vangen). Unit-getest. Vangt verbatim-herhalingen;
  een geparafraseerde tweede variant zou 'm ontwijken, maar de instructie eist letterlijke tekst.
- **Per-resultaat-klikbaarheid is prompt-gestuurd**, dus zeer betrouwbaar maar niet 100%. Een harde
  garantie (elk gevonden resultaat gegarandeerd een klikbare, niet-gefabriceerde link) vergt
  structured output + rendering in `chat.js`; uitgesteld tot na evaluatie van het prototype.
