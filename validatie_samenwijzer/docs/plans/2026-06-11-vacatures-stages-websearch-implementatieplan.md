# Vacatures & stages via web_search — Implementatieplan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Een ingelogde student én de publieke vraagpagina kunnen in de chat naar actuele vacatures/stages voor het beroep van hun opleiding vragen, beantwoord via de bestaande `web_search`/`web_fetch`-tools gescoped op Stagemarkt + Indeed (alleen crawlbare domeinen — zie spec).

**Architecture:** Hergebruik de bestaande Anthropic server-side tools; verbreed hun `allowed_domains` met de vacaturesites en voeg een prompt-blok (`_VACATURE_BLOK`) toe dat gate't wannéér/hóe het model die gebruikt. School-webzoek en vacaturezoek worden ontkoppeld zodat vacatures óók werken als de school geen scrapebaar domein heeft. Alles in `chat.py` (AI-isolatie-invariant) + een paar regels in `app_fastapi/context.py`.

**Tech Stack:** Python 3.13, Anthropic SDK (`web_search_20250305` / `web_fetch_20250910`), FastAPI, pytest.

**Spec:** `docs/plans/2026-06-11-vacatures-stages-websearch-design.md`

---

## File Structure

| Bestand | Verantwoordelijkheid | Wijziging |
|---|---|---|
| `src/validatie_samenwijzer/chat.py` | system-prompt-bouwers + tool-wiring | `_VACATURE_DOMEINEN`, `vacature_domeinen()`, `_VACATURE_DISCLAIMER`, `_VACATURE_BLOK`; `leerweg`+`vacatures` params in `bouw_systeem`; `vacatures` param in `bouw_gecombineerd_systeem`; `{leerweg_blok}`+`{vacature_blok}` in templates |
| `app_fastapi/context.py` | OER-context-orchestrator | union-domeinen + `vacatures=True` in `laad_context` |
| `tests/test_chat.py` | pure-functie tests | nieuwe tests voor `vacatures`/`leerweg` |
| `tests/test_fastapi_poc.py` | context/DB tests | nieuwe test voor vacature-domeinen |

`genereer_antwoord` en `app_fastapi/main.py` wijzigen **niet**: `genereer_antwoord` neemt al een `web_search_domeinen`-lijst en `/api/chat` geeft `s.domeinen` ongewijzigd door.

---

## Task 1: Constants + `_VACATURE_BLOK` + `bouw_systeem` (leerweg + vacatures)

**Files:**
- Modify: `src/validatie_samenwijzer/chat.py` (constanten na `web_zoek_domeinen`; template `_SYSTEEM_TEMPLATE`; functie `bouw_systeem`)
- Test: `tests/test_chat.py`

- [ ] **Step 1: Schrijf de falende tests**

Voeg toe aan `tests/test_chat.py` (importeer `bouw_systeem` staat al bovenaan):

```python
def test_bouw_systeem_vacatures_voegt_blok_toe():
    met = bouw_systeem("OER-tekst", "Kok", "Da Vinci", leerweg="BOL", vacatures=True)
    zonder = bouw_systeem("OER-tekst", "Kok", "Da Vinci", leerweg="BOL")
    assert "VACATURES & STAGES" in met
    assert "VACATURES & STAGES" not in zonder


def test_bouw_systeem_leerweg_in_prompt():
    systeem = bouw_systeem("OER-tekst", "Kok", "Da Vinci", leerweg="BOL")
    assert "Leerweg van deze opleiding: BOL" in systeem


def test_bouw_systeem_zonder_leerweg_geen_leerweg_regel():
    systeem = bouw_systeem("OER-tekst", "Kok", "Da Vinci")
    assert "Leerweg van deze opleiding" not in systeem
```

- [ ] **Step 2: Run de tests om te bevestigen dat ze falen**

Run: `uv run python -m pytest tests/test_chat.py::test_bouw_systeem_vacatures_voegt_blok_toe tests/test_chat.py::test_bouw_systeem_leerweg_in_prompt tests/test_chat.py::test_bouw_systeem_zonder_leerweg_geen_leerweg_regel -v`
Expected: FAIL — `bouw_systeem()` kent nog geen `leerweg`/`vacatures` kwargs (TypeError) en het blok bestaat niet.

- [ ] **Step 3: Voeg de constanten toe**

In `chat.py`, direct ná de functie `web_zoek_domeinen` (vlak vóór het commentaarblok van `_WEB_DISCLAIMER`), voeg toe:

```python
# Vacaturesites voor de vacature-/stagezoek (los van de school-webzoek). Stagemarkt =
# SBB (officiële erkende leerbedrijven/BPV); Indeed = reguliere vacatures. Alleen domeinen
# die de Anthropic-crawler toelaat — een geblokkeerd domein (bv. nationalevacaturebank.nl)
# geeft een 400 op de HELE web_search-call. Gescoped als allowed_domains op web_search/web_fetch.
_VACATURE_DOMEINEN = ["stagemarkt.nl", "indeed.nl"]


def vacature_domeinen() -> list[str]:
    """Vaste vacaturesites voor de vacature-/stagezoek (kopie, gesorteerd voor cache-stabiliteit)."""
    return sorted(_VACATURE_DOMEINEN)
```

- [ ] **Step 4: Voeg de disclaimer + het prompt-blok toe**

In `chat.py`, direct ná de definitie van `_WEB_ZOEK_BLOK` (vóór `_DOELGROEP_TOON`), voeg toe:

```python
# Instructie voor de vacature-/stagezoek. Alleen in de prompt als vacatures=True; gate't
# zelf op een EXPLICIETE vacaturevraag zodat een gewone OER-vraag ongemoeid blijft.
_VACATURE_DISCLAIMER = (
    "⚠️ Let op: onderstaande vacatures/stageplekken komen van externe sites (zoals "
    "Stagemarkt of Indeed), wisselen dagelijks en zijn géén officiële of bindende "
    "informatie van je opleiding — controleer altijd zelf en overleg met je "
    "stagebegeleider of SBB."
)
_VACATURE_BLOK = f"""

VACATURES & STAGES (alleen bij een expliciete vraag hierover). Vraagt de student naar
vacatures, banen of stage-/BPV-plekken voor het beroep van deze opleiding, dan mag je op
de vacaturesites zoeken (web_search) en een relevante pagina openen (web_fetch). Doe dit
ALLEEN bij zo'n expliciete vraag — niet bij OER-, examinerings- of begeleidingsvragen.
Stem de zoekopdracht af op vier dingen:
- BEROEP: uit de opleiding en het skills-blok hierboven.
- LEERWEG: bij BOL zoek je naar "stage"/"BPV-plek", bij BBL naar "leerbaan"/"BBL-plek".
- MBO-NIVEAU (1 t/m 4): lees dit uit de OER- of KD-tekst hierboven en neem het mee in de
  zoekopdracht (bv. "MBO niveau 3"); staat het er nergens, gebruik dan alleen beroep + leerweg.
- LOCATIE: staat er GEEN plaats in de vraag, vraag de student dan EERST in welke plaats of
  regio hij wil zoeken en zoek nog NIET; noemt hij wél een plaats, zoek dan in en rond die
  plaats (binnen ±10 km), of breder bij een regio.
Begin een vacature-antwoord (zodra je echt resultaten toont) met PRECIES deze ene
waarschuwingsregel — letterlijk, exact één keer, en zet er geen tweede variant (plat óf als
blockquote) vóór of ná:
{_VACATURE_DISCLAIMER}
Geef vacature-informatie NOOIT de vorm van een OER-citaat (geen "Volgens de OER", geen sectie-,
artikel- of paginanummer) en verzin nooit een vindplaats. Toon ELK gevonden resultaat als een
klikbare Markdown-link in de vorm [functietitel — werkgever, plaats](URL), met (waar bekend) het
niveau erbij — NOOIT een kale kop, tabelrij of bullet zonder link. Gebruik ALTIJD de echte URL uit
je zoek-/fetch-resultaten en verzin NOOIT een URL; heb je geen eigen URL voor een plek, link dan
naar de zoek-/filterpagina van die site. Vind je niets, zeg dat dan eerlijk — verzin geen
vacatures. Sluit af met de bron-URL('s)."""
```

- [ ] **Step 5: Voeg de placeholders toe aan `_SYSTEEM_TEMPLATE`**

In `chat.py`, de openingsregel van `_SYSTEEM_TEMPLATE`:

Van:
```
Je bent een onderwijs-assistent voor de opleiding {opleiding} bij {instelling}.
```
Naar:
```
Je bent een onderwijs-assistent voor de opleiding {opleiding} bij {instelling}.{leerweg_blok}
```

En de afsluitende regel van `_SYSTEEM_TEMPLATE`:

Van:
```
Antwoord in het Nederlands.{web_zoek_blok}{doelgroep_toon}
```
Naar:
```
Antwoord in het Nederlands.{web_zoek_blok}{vacature_blok}{doelgroep_toon}
```

> Let op: `Antwoord in het Nederlands.{web_zoek_blok}{doelgroep_toon}` komt **twee keer** voor (`_SYSTEEM_TEMPLATE` rond regel 159 én `_MULTI_SYSTEEM_TEMPLATE` rond regel 582). Pas hier **alleen** die in `_SYSTEEM_TEMPLATE` aan; de multi-template komt in Task 2.

- [ ] **Step 6: Breid `bouw_systeem` uit**

Signatuur — voeg twee kwargs toe ná `web_zoeken`:

```python
def bouw_systeem(
    oer_tekst: str,
    opleiding: str,
    instelling: str,
    dossier_tekst: str = "",
    crebo: str | None = None,
    skills_tekst: str = "",
    instelling_bronnen: Sequence[tuple[str, str]] = (),
    web_zoeken: bool = False,
    leerweg: str = "",
    vacatures: bool = False,
) -> str:
```

In de body, vlak vóór de `return _SYSTEEM_TEMPLATE.format(`, voeg toe:

```python
    leerweg_blok = f"\nLeerweg van deze opleiding: {leerweg}." if leerweg else ""
```

En in de `.format(...)`-aanroep, voeg twee keyword-argumenten toe (naast de bestaande):

```python
        leerweg_blok=leerweg_blok,
        vacature_blok=_VACATURE_BLOK if vacatures else "",
```

- [ ] **Step 7: Run de tests om te bevestigen dat ze slagen**

Run: `uv run python -m pytest tests/test_chat.py -v`
Expected: PASS — de drie nieuwe tests slagen én alle bestaande `bouw_systeem`-tests blijven groen (defaults `leerweg=""`, `vacatures=False` → geen gedragswijziging).

- [ ] **Step 8: Commit**

```bash
git add src/validatie_samenwijzer/chat.py tests/test_chat.py
git commit -m "feat(validatie): vacature-/stagezoek-blok + leerweg in single-OER-prompt

Ed de Feber, in nauwe samenwerking met Claude"
```

---

## Task 2: `vacatures`-param in `bouw_gecombineerd_systeem`

**Files:**
- Modify: `src/validatie_samenwijzer/chat.py` (functie `bouw_gecombineerd_systeem` + `_MULTI_SYSTEEM_TEMPLATE`)
- Test: `tests/test_chat.py`

- [ ] **Step 1: Schrijf de falende tests**

Voeg toe aan `tests/test_chat.py` (zorg dat `bouw_gecombineerd_systeem` geïmporteerd is bovenaan; zo niet, voeg toe aan de bestaande import uit `validatie_samenwijzer.chat`):

```python
def _vac_items():
    return [
        {"tekst": "OER A", "opleiding": "Kok", "display_naam": "Da Vinci",
         "leerweg": "BOL", "cohort": "2025", "crebo": "25180"},
        {"tekst": "OER B", "opleiding": "Kapper", "display_naam": "Rijn IJssel",
         "leerweg": "BBL", "cohort": "2025", "crebo": "25201"},
    ]


def test_bouw_gecombineerd_systeem_vacatures_multi():
    items = _vac_items()
    assert "VACATURES & STAGES" in bouw_gecombineerd_systeem(items, vacatures=True)
    assert "VACATURES & STAGES" not in bouw_gecombineerd_systeem(items)


def test_bouw_gecombineerd_systeem_vacatures_single_delegeert_met_leerweg():
    items = [{"tekst": "OER A", "opleiding": "Kok", "display_naam": "Da Vinci",
              "leerweg": "BBL", "cohort": "2025", "crebo": "25180"}]
    systeem = bouw_gecombineerd_systeem(items, vacatures=True)
    assert "VACATURES & STAGES" in systeem
    assert "Leerweg van deze opleiding: BBL" in systeem
```

- [ ] **Step 2: Run de tests om te bevestigen dat ze falen**

Run: `uv run python -m pytest tests/test_chat.py::test_bouw_gecombineerd_systeem_vacatures_multi tests/test_chat.py::test_bouw_gecombineerd_systeem_vacatures_single_delegeert_met_leerweg -v`
Expected: FAIL — `bouw_gecombineerd_systeem()` kent nog geen `vacatures`-kwarg (TypeError).

- [ ] **Step 3: Pas `_MULTI_SYSTEEM_TEMPLATE` aan**

De afsluitende regel van `_MULTI_SYSTEEM_TEMPLATE`:

Van:
```
Antwoord in het Nederlands.{web_zoek_blok}{doelgroep_toon}
```
Naar:
```
Antwoord in het Nederlands.{web_zoek_blok}{vacature_blok}{doelgroep_toon}
```

(De leerweg staat in de multi-template al in de blok-koppen `=== OER N: … · BOL 2025 ===`, dus daar is geen `leerweg_blok` nodig.)

- [ ] **Step 4: Breid `bouw_gecombineerd_systeem` uit**

Signatuur:

```python
def bouw_gecombineerd_systeem(
    oer_items: list[dict], web_zoeken: bool = False, vacatures: bool = False
) -> str:
```

In het single-OER-pad (`if len(oer_items) == 1:`) — geef `leerweg` en `vacatures` mee aan `bouw_systeem`:

```python
        return bouw_systeem(
            item["tekst"],
            item["opleiding"],
            item["display_naam"],
            dossier_tekst=item.get("dossier_tekst", ""),
            crebo=item.get("crebo"),
            skills_tekst=item.get("skills_tekst", ""),
            instelling_bronnen=item.get("instelling_bronnen", ()),
            web_zoeken=web_zoeken,
            leerweg=item.get("leerweg", ""),
            vacatures=vacatures,
        )
```

In de afsluitende `return _MULTI_SYSTEEM_TEMPLATE.format(...)`, voeg het keyword-argument toe:

```python
        vacature_blok=_VACATURE_BLOK if vacatures else "",
```

- [ ] **Step 5: Run de tests om te bevestigen dat ze slagen**

Run: `uv run python -m pytest tests/test_chat.py -v`
Expected: PASS — nieuwe tests groen, bestaande multi-OER-tests blijven groen (default `vacatures=False`).

- [ ] **Step 6: Commit**

```bash
git add src/validatie_samenwijzer/chat.py tests/test_chat.py
git commit -m "feat(validatie): vacatures-param in bouw_gecombineerd_systeem (single + multi)

Ed de Feber, in nauwe samenwerking met Claude"
```

---

## Task 3: Wire de vacature-domeinen in `laad_context`

**Files:**
- Modify: `app_fastapi/context.py` (import + functie `laad_context`)
- Test: `tests/test_fastapi_poc.py`

- [ ] **Step 1: Schrijf de falende test**

Voeg toe aan `tests/test_fastapi_poc.py` (de helper `_leesbare_oer_id()` bestaat al in dat bestand):

```python
def test_laad_context_bevat_vacature_domeinen():
    oer_id = _leesbare_oer_id()
    if oer_id is None:
        pytest.skip("Geen geïndexeerde OER met leesbare tekst beschikbaar (DB/oeren afwezig).")
    _systeem, _labels, domeinen, _ = laad_context([oer_id])
    for d in ("stagemarkt.nl", "indeed.nl"):
        assert d in domeinen
```

- [ ] **Step 2: Run de test om te bevestigen dat hij faalt (of skipt)**

Run: `uv run python -m pytest tests/test_fastapi_poc.py::test_laad_context_bevat_vacature_domeinen -v`
Expected: FAIL (de domeinen ontbreken) — óf SKIP als er lokaal geen geïndexeerde DB is. Bij SKIP: ga door; de assert wordt geverifieerd in de UI-smoke (Task 4). Als de test draait, moet hij eerst falen.

- [ ] **Step 3: Breid de import uit**

Bovenin `app_fastapi/context.py`, in de bestaande `from validatie_samenwijzer.chat import (` … `)`, voeg `vacature_domeinen` toe (alfabetisch tussen de bestaande namen):

```python
from validatie_samenwijzer.chat import (
    bouw_gecombineerd_systeem,
    laad_instelling_bron_tekst,
    laad_kwalificatiedossier_tekst,
    laad_oer_tekst,
    laad_skills_tekst,
    resolve_oer_pad,
    vacature_domeinen,
    web_zoek_domeinen,
)
```

- [ ] **Step 4: Pas de slotregels van `laad_context` aan**

Van:
```python
    if not items:
        return "", [], [], False
    domeinen = web_zoek_domeinen(items)
    systeem = bouw_gecombineerd_systeem(items, web_zoeken=bool(domeinen))
    return systeem, labels, domeinen, oer_onleesbaar
```
Naar:
```python
    if not items:
        return "", [], [], False
    school_domeinen = web_zoek_domeinen(items)
    # Vacaturezoek is altijd beschikbaar (beroep bekend via de OER/skills); het prompt-blok
    # gate't zelf op een expliciete vacaturevraag. Los van school_domeinen, zodat het ook
    # werkt bij een instelling zonder scrapebaar webdomein.
    systeem = bouw_gecombineerd_systeem(
        items, web_zoeken=bool(school_domeinen), vacatures=True
    )
    domeinen = sorted(set(school_domeinen) | set(vacature_domeinen()))
    return systeem, labels, domeinen, oer_onleesbaar
```

- [ ] **Step 5: Run de test om te bevestigen dat hij slaagt**

Run: `uv run python -m pytest tests/test_fastapi_poc.py -v`
Expected: PASS (of SKIP voor de DB-afhankelijke test als er geen DB is) — geen regressies in de overige context-tests.

- [ ] **Step 6: Commit**

```bash
git add app_fastapi/context.py tests/test_fastapi_poc.py
git commit -m "feat(validatie): activeer vacaturezoek-domeinen in laad_context

Ed de Feber, in nauwe samenwerking met Claude"
```

---

## Task 4: Volledige verificatie (tests + lint + UI-smoke)

**Files:** geen wijzigingen — alleen verifiëren.

- [ ] **Step 1: Volledige testsuite**

Run: `uv run python -m pytest`
Expected: alles groen (DB-afhankelijke vacature-domeinen-test mag skippen).

- [ ] **Step 2: Lint + format**

Run: `uv run ruff check src/ app_fastapi/ && uv run ruff format --check src/ app_fastapi/`
Expected: `All checks passed!` en geen format-diff. (Bij format-diff: `uv run ruff format src/ app_fastapi/` en opnieuw.)

- [ ] **Step 3: UI-smoke — publieke pagina (verplicht per CLAUDE.md)**

Start de app: `uv run uvicorn app_fastapi.main:app --port 8504` (achtergrond), open via de toegangspoort (`ALGEMEEN_WACHTWOORD`), ga naar `/` en stel via "Direct een vraag" een OER-vraag voor een kok-opleiding zodat de OER laadt; vraag dan: **"Zijn er stageplaatsen voor kok?"**
Verwacht: een antwoord dat begint met de vacature-disclaimer-regel, gevolgd door klikbare vacature-/stagelinks (Stagemarkt/Indeed), géén OER-citaatvorm.

- [ ] **Step 4: UI-smoke — studentpagina**

Log in als een kok-student (zie `gebruikers.txt`), ga naar `/student` en stel dezelfde vraag.
Verwacht: idem; de leerweg van die opleiding (BOL → stage, BBL → leerbaan) komt terug in de zoekrichting.

- [ ] **Step 5: UI-smoke — regressie**

Stel op `/student` een gewone OER-vraag, bv. **"Hoeveel studiepunten heb ik nodig voor mijn BSA?"**
Verwacht: een normaal OER-antwoord mét woordelijke citaten/blockquote en bronvermelding, **géén** vacatureblok of vacature-disclaimer.

- [ ] **Step 6: Eindcommit (alleen indien Step 2 een format-fix nodig had)**

```bash
git add -A
git commit -m "style(validatie): ruff format na vacaturezoek-feature

Ed de Feber, in nauwe samenwerking met Claude"
```

---

## Notities / bewust uitgesteld (YAGNI)

- **False-positive-filtering** (zoals "De Kok Staalbouw" die op bedrijfsnaam matchte) wordt alleen via prompt-instructie beperkt; harde herrangschikking/dedup in code is uitgesteld tot ná evaluatie van dit prototype (aanpak C uit de spec).
- **Locatie + niveau** zijn toegevoegd (prompt-gestuurd: plaats via de student vragen, niveau uit
  de OER/KD-tekst); harde code-filtering op afstand/niveau en salaris-parsing: niet in dit prototype.
- Mocht in Step 3 blijken dat `chat.js` Markdown-links niet klikbaar rendert, dan is dat een aparte follow-up — buiten scope van dit plan.
```
