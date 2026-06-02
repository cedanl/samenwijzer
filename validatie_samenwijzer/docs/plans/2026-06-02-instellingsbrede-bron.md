# Spec: instellingsbrede bron (examenreglement, begeleidingsbeleid)

**Status:** geïmplementeerd (stappen 1-5, 2026-06-02) — live voor student + mentor; publieke
multi-OER-pagina (stap 5b) + beheer-status (stap 6) staan nog open.
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

De PDF's ogen groot (Examenreglement ≈ 1,2 MB, Beleidsnotitie ≈ 2,3 MB), maar na
markdown-conversie blijkt de tekst klein (gemeten: ~37K tekens / ~12,5K tokens — zie §4). Nodig:
- `_MAX_INSTELLING_TEKST_TEKENS = 300_000` — **vastgesteld** na meting (§4); ruime veiligheidsrem
  die in de praktijk niet bindt.
- Het blok is **instelling-stabiel** (verandert niet per student/vraag) → ideaal voor prompt-caching;
  plaats het op een cache-vriendelijke, stabiele positie in de prompt.

## 4. Kostenimpact — gemeten (2026-06-02)

> **Gate: GEHAALD. Kosten acceptabel → door naar stap 5; cap blijft 300_000 tekens.**

Gemeten op het **Da Vinci-examenreglement 2026-2027** (representatief mbo-examenreglement; de Rijn
IJssel-PDF's waren niet meer beschikbaar — zie §5). Sonnet 4.6, `count_tokens`-API, Da Vinci-OER
als basis:

| Metriek | Waarde |
|---|---|
| Reglement na markdown-conversie | 36.911 tekens (PDF was 3,4 MB — PDF-grootte voorspelt md-grootte slecht) |
| Reglement-blok in tokens | **12.451 tokens** (~OER+KD-orde, niet de gevreesde 100K+) |
| Eerste vraag, vers input (+$3/M) | **+$0,037** |
| Eerste vraag, cache-write (+$3,75/M) | +$0,047 |
| Vervolgvraag, cache-read (+$0,30/M) | **+$0,004** |

De eerdere schatting (100K–300K tekens / +$0,05–0,12) was pessimistisch: een echt examenreglement
is tekstueel klein (~37K tekens, vergelijkbaar met een KD). Met begeleidingsbeleid mentor-only
(beslissing 2) en prompt-caching is de student-meerkost ~$0,04 bij de eerste vraag en
verwaarloosbaar daarna.

`_MAX_INSTELLING_TEKST_TEKENS` **blijft 300_000**: de cap bindt in de praktijk niet (ruim 20×
boven de gemeten omvang) en dient alleen als veiligheidsrem (~100K tokens worst-case). Geen
on-demand laden nodig.

> **Restrisico:** de Rijn IJssel-Beleidsnotitie (2,3 MB PDF) is niet gemeten; herhaal `count_tokens`
> bij de eerste echte instelling-bron-ingest om te bevestigen dat ook die binnen de orde blijft.
> De meting is reproduceerbaar via een `count_tokens`-vergelijking OER vs OER+bron.

## 5. Implementatieplan

Volgorde met verifieerbaar criterium per stap. De kostenmeting (fase 4) is een **gate**: geen brede
uitrol vóór het resultaat bekend is.

1. ✅ **Schema + db-laag** — tabel `instelling_documenten` + CRUD in `db.py`
   (`voeg_instelling_document_toe` upsert, `haal_instelling_document_op`,
   `markeer_instelling_document_geindexeerd`). *Geverifieerd: unit-tests groen.* (PR #117)
2. ✅ **Ingestie** — `ingest.py` `_verwerk_instelling_documenten`: leest `<map>/_instelling/<soort>.<ext>`,
   converteert naar markdown, registreert; ingehaakt in `main`. *Geverifieerd: test + echte
   Da Vinci-examenreglement-ingest.* (PR #117)
3. ✅ **Laad-helper** — `laad_instelling_bron_tekst(bestandspad)` (hergebruikt `laad_oer_tekst`,
   eigen cap). DB→pad-resolutie blijft de taak van de pagina (stap 5), consistent met `laad_oer_tekst`.
   *Geverifieerd: unit-tests groen.* (PR #117)
4. ✅ **Kostenmeting (GATE) — GEHAALD** — Da Vinci-examenreglement: 12.451 tokens, +$0,037 eerste
   vraag / +$0,004 cached. Cap vastgesteld op 300_000. Zie §4.
5. ✅ **Chat-integratie + citatie** — `bouw_systeem` krijgt `instelling_bronnen`
   (`Sequence[(label, tekst)]`), rendert blokken tussen OER en KD; `_SYSTEEM_TEMPLATE` +
   `_MULTI_SYSTEEM_TEMPLATE` beschrijven de bron + citatieplicht (regeling als APARTE bron, "citeer
   NOOIT als de OER"). Login (`main.py`) resolvet de bron-paden per rol: student → examenreglement;
   mentor → examenreglement + begeleidingsbeleid. Label-bron van waarheid: `INSTELLING_SOORTEN`.
   → *Geverifieerd:* templatetests (blok aanwezig/afwezig, lege tekst → geen blok, citatie
   onderscheidt van OER, multi per-OER); **live smoke-test** RI-student (examenreglement, citaten
   artikel 5.4.1-5.4.4) + RI-mentor (reglement+beleid geladen, gegrond antwoord, geen errors).
   **Bewust uitgesteld:** `0_oer_vraag.py` (publieke multi-OER) — `bouw_gecombineerd_systeem`
   ondersteunt `instelling_bronnen` per item, maar de per-OER-per-instelling resolutie in de pagina
   is nog niet gewired (hardste + laagste waarde). Aparte follow-up.
6. **Beheerpagina-status** (optioneel) — dekking per instelling tonen. *(open)*
7. **UI-smoke-test** — ✅ gedaan als onderdeel van stap 5 (zie hierboven). Resteert: publieke
   multi-OER-pagina zodra die gewired is.

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
