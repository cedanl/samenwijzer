# Spec: instellingsbrede bron (examenreglement, begeleidingsbeleid)

**Status:** vastgesteld — drie ontwerpbeslissingen genomen (2026-06-02), klaar voor implementatie
**Datum:** 2026-06-02
**Aanleiding:** OER-drop Rijn IJssel (juni 2026) bevatte twee documenten die géén OER zijn maar
wél waardevolle context: `25-0070 Examenreglement mbo Rijn IJssel` en `25-0212 Beleidsnotitie
Studentbegeleiding en studentenwelzijn`. Deze zijn bij de KWIC/25122-verwerking bewust weggelaten
omdat er geen plek voor is in het huidige model.

---

## 1. Probleem

De chat kent drie bronnen, **allemaal crebo-gekoppeld**: OER (per opleiding), kwalificatiedossier
(landelijk per crebo), skills-taxonomie (per crebo). Sommige documenten gelden echter
**instellingsbreed** — voor álle opleidingen van één instelling, niet voor één crebo:

- **Examenreglement** — regels rond examinering, herkansingen, fraude, bezwaar, vrijstelling.
  Studenten stellen hier vaak vragen over ("hoe vaak mag ik herkansen?", "wat als ik te laat ben?").
  De OER verwijst er doorgaans naar maar herhaalt de regels niet.
- **Begeleidings-/welzijnsbeleid** — beleid rond studiebegeleiding, verzuim, doorverwijzing,
  studentenwelzijn. Relevant voor zowel studenten als mentoren.

Vandaag is er geen slot voor zulke documenten. Ze worden weggelaten → de chat kan een hele klasse
veelgestelde vragen niet onderbouwd beantwoorden, terwijl het bronmateriaal beschikbaar is.

## 2. Doel & niet-doelen

**Doel:** een vierde, **instelling-gekoppelde** bron die als aanvullende context meegaat in de
OER-chat, met dezelfde citatieplicht, zodat vragen over examen- en begeleidingsregels verifieerbaar
beantwoord worden.

**Niet-doelen:**
- Geen vervanging van OER/KD/skills — strikt aanvullend, en **ná** de OER in prioriteit.
- Geen nieuwe pagina of UI-flow; het haakt in op de bestaande chat (`bouw_systeem` /
  `bouw_gecombineerd_systeem`).
- Geen generieke document-management-feature. Eén afgebakend documenttype-paar (reglement + beleid),
  uitbreidbaar maar niet speculatief.
- Geen wijziging aan de crebo-gekoppelde bronnen.

**Verifieerbaar succescriterium:** een Rijn IJssel-student vraagt "hoe vaak mag ik een examen
herkansen?" en krijgt een antwoord met citaat uit het Examenreglement (bron + artikel + woordelijk
citaat), terwijl een student van een instelling zónder reglement exact dezelfde chat-ervaring houdt
als nu (geen lege blokken, geen errors).

## 3. Ontwerp

### 3.1 Data-laag

**Besluit: nieuwe tabel `instelling_documenten`** (instelling-gekoppeld, niet crebo).
```
instelling_documenten(
  id, instelling_id, soort TEXT,        -- 'examenreglement' | 'begeleidingsbeleid'
  titel, bestandspad, geindexeerd, toegevoegd_op
)
```
Spiegelt `oer_documenten`, herbruikt `geindexeerd`-semantiek en markitdown-conversie. Query's via
`db.py` (geen raw SQL in `app/`). Schoon, expliciet, en het maakt "welke instelling heeft wat"
eenvoudig te tonen op de beheerpagina ("3/6 instellingen hebben een examenreglement"). Verworpen
alternatief: mapconventie binnen de oeren-tree zonder tabel — minder infra, maar lookup/status
fragieler en `soort` impliciet in de bestandsnaam.

**Bestanden & sync:** PDF's leven in de gitignored `oeren/`-tree (of een aparte `instelling_bronnen/`),
markitdown-`.md` ernaast als chat-bron — net als OER/KD. Multi-machine: meeliften op de bestaande
Box-sync van `oeren/`.

### 3.2 Ingestie

Uitbreiding van `ingest.py`: een functie die per instelling de instellingsbrede bestanden inleest,
converteert naar markdown en registreert in `instelling_documenten`. Crebo-loze documenten, dus
géén `parseer_bestandsnaam`/`extraheer_kerntaken` — alleen tekst-conversie + registratie. De
`soort` komt uit map/bestandsnaam-conventie of een handmatige mapping.

### 3.3 Chat-integratie

Een vierde blok, parallel aan `_DOSSIER_BLOK_TEMPLATE`:

```
_INSTELLING_BLOK_TEMPLATE = "\n\n=== {soort_label} ({instelling}) ===\n{tekst}"
```
- `laad_instelling_bron_tekst(instelling_key, soort) -> str` (lege string als afwezig — zelfde
  patroon als `laad_kwalificatiedossier_tekst`).
- `bouw_systeem(...)` krijgt optionele `instelling_blok`-parameters; geappend ná `{skills_blok}`.
- Op chat-tijd is de instelling bekend (`oer_documenten.instelling_id`; in session `instelling`).
  Laden gebeurt op **instelling-key**, niet crebo.

**Prioriteit in de systeemprompt:** OER (leidend) → instellingsbron → KD → skills. Het
examenreglement staat qua geldigheid dichter bij de OER dan het landelijke KD, dus boven het KD.

> **Besluit: examenreglement overal, begeleidingsbeleid mentor-only.** Het examenreglement
> (hoogste vraagfrequentie) gaat mee in elke student- én mentor-chat; het begeleidingsbeleid laadt
> uitsluitend in de mentor-context (`5_begeleidingssessie.py`). Past het vraagpatroon én beperkt de
> student-kosten tot één groot extra document. Concreet: `bouw_systeem` krijgt het reglement-blok
> ongeacht rol, en alleen de mentor-aanroep voegt daarnaast het beleidsblok toe.

### 3.4 Citatieplicht

Uitbreiding van `_SYSTEEM_TEMPLATE` (en `_MULTI_SYSTEEM_TEMPLATE`): een instellingsbron is óók een
(semi-)juridisch document → bron + vindplaats + woordelijk citaat, net als de OER.

> Voorbeeld: *Volgens het Examenreglement van Rijn IJssel, artikel 6.3 "Herkansingen": "De student
> heeft recht op ten hoogste één herkansing per examenonderdeel."*

De bronnaam staat in de blok-kop ("Examenreglement", "Begeleidingsbeleid") zodat de LLM exact de
juiste bron citeert — geen verwarring met "de OER".

### 3.5 Caps & prompt-caching

Deze documenten zijn groot (Examenreglement ≈ 1,2 MB PDF, Beleidsnotitie ≈ 2,3 MB). Na
markdown-conversie naar schatting 100K–300K tekens. Nodig:
- `_MAX_INSTELLING_TEKST_TEKENS` — **definitieve waarde volgt uit de meting** (zie §4, besluit 3).
  Start de implementatie met een ruime placeholder (300_000, gelijk aan KD) en stel hem bij op
  basis van `meet_token_kosten.py` vóór brede uitrol.
- Het blok is **instelling-stabiel** (verandert niet per student/vraag) → ideaal voor prompt-caching;
  plaats het op een cache-vriendelijke, stabiele positie in de prompt.

## 4. Kostenimpact

Sonnet 4.6, full-document context. Het examenreglement voegt bij elke eerste vraag in een sessie
~100K–250K extra prompt-tekens toe — fors meer dan het KD (~40K). Grove schatting per sessie:
eerste vraag +$0.05–$0.12; vervolgvragen halen cache → marginaal. Met de aanbeveling uit beslissing
2 (begeleidingsbeleid alleen mentor) blijft de student-impact bij één extra groot document.

> **Besluit: meet eerst, dan cap kiezen.** Draai `scripts/meet_token_kosten.py` op het Rijn
> IJssel-reglement (fase 0, vóór de chat-integratie breed live gaat) en stel `_MAX_INSTELLING_
> TEKST_TEKENS` op echte cijfers in i.p.v. de schatting. Valt de eerste-vraag-kost te hoog uit,
> dan verlaag de cap of schakel het reglement naar on-demand laden (trefwoord/intent). Geen brede
> uitrol vóór deze meting.

## 5. Implementatieplan

Volgorde met verifieerbaar criterium per stap. De kostenmeting (fase 4) is een **gate**: geen brede
uitrol vóór het resultaat bekend is.

1. **Schema + db-laag** — tabel `instelling_documenten` + CRUD-functies in `db.py`
   (`voeg_instelling_document_toe`, `haal_instelling_document_op(instelling_id, soort)`).
   → *verify:* `init_db()` maakt de tabel; unit-test schrijft/leest een record.
2. **Ingestie** — uitbreiding `ingest.py`: lees instellingsbrede bestanden per instelling, converteer
   naar markdown, registreer met `soort`. Conventie voor map/bestandsnaam → `soort` vastleggen.
   → *verify:* Rijn IJssel-reglement + beleid staan in `instelling_documenten` met `geindexeerd=1`
   en `.md` naast de bron. Test: `test_ingest`-uitbreiding.
3. **Laad-helper** — `laad_instelling_bron_tekst(instelling_id_of_key, soort) -> str`, met
   `_MAX_INSTELLING_TEKST_TEKENS` (placeholder 300_000).
   → *verify:* geeft tekst voor Rijn IJssel; onbekende instelling/soort → lege string. Unit-test.
4. **Kostenmeting (GATE)** — `scripts/meet_token_kosten.py` op het reglement; stel de definitieve
   cap in. → *verify:* gemeten eerste-vraag-meerkost gedocumenteerd; cap-waarde vastgesteld.
5. **Chat-integratie + citatie** — vierde blok in `_SYSTEEM_TEMPLATE` + `_MULTI_SYSTEEM_TEMPLATE`;
   `bouw_systeem` voegt het reglement-blok toe (alle rollen) en, alléén voor de mentor-aanroep, het
   beleidsblok; citatie-instructie voor instellingsbronnen.
   → *verify:* templatetest dat blok + citatie-instructie aanwezig zijn en de blok-kop de juiste
   bronnaam draagt; instelling zónder bron levert lege blokken (geen errors).
6. **Beheerpagina-status** (optioneel) — dekking per instelling tonen.
7. **UI-smoke-test** — Rijn IJssel-student vraagt naar herkansingen → gegrond antwoord met
   reglement-citaat (bron + artikel + woordelijk citaat); mentor ziet daarnaast beleid; instelling
   zónder reglement = ongewijzigde ervaring.

## 6. Risico's

- **Kosten/latency** door grote documenten — gemitigeerd via caps, prompt-caching en mentor-only
  begeleidingsbeleid.
- **Citaat-vervuiling**: LLM verwart reglement met OER. Mitigatie: duidelijke blok-kop + expliciete
  bronnaam in de citatie-instructie.
- **Versiebeheer**: reglementen wijzigen jaarlijks; `toegevoegd_op` + re-ingest dekken dit, maar er
  is (net als bij OER) geen automatische verloop-detectie.
- **Scope-creep**: het model nodigt uit tot "elk instellingsdocument toevoegen". Bewust beperken
  tot de twee soorten; uitbreiden alleen op concrete vraag.

## 7. Vastgestelde beslissingen (2026-06-02)

1. **Opslag** → nieuwe tabel `instelling_documenten` (instelling-gekoppeld). [§3.1]
2. **Scope per rol** → examenreglement overal, begeleidingsbeleid mentor-only. [§3.3]
3. **Kosten** → meet eerst met `meet_token_kosten.py`, kies dan de cap; meting is een gate vóór
   brede uitrol. [§4, fase 4]

Ontwerp vastgesteld. Volgende stap: implementatie volgens §5, of eerst een aparte issue/PR-opzet
als je dat wilt.
