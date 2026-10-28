# Procesfeedback + bronnenlijst — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eerlijke statusmeldingen tijdens het streamen (alleen op echte signalen) en een rij bronchips onder elk OER-antwoord, geparset uit een vaste markerregel van het model.

**Architecture:** `chat.py` krijgt twee dataclasses (`Status`, `Bron`) en drie pure helpers (`splits_bronnen`, `strip_bronnenregel`, `status_uit_tekstbegin`); `genereer_antwoord` itereert over SDK-events i.p.v. `text_stream` en yieldt `Status("web")` bij een `server_tool_use`-blok. De route `/api/chat` vertaalt dat naar SSE-events `status`/`bronnen`; `/api/geschiedenis` levert per assistent-beurt `content` (gestript) + `bronnen`. De frontend (`chat.js`/`app.css`) vertaalt statuscodes naar tekst (patroon `FOUT_TEKSTEN`) en rendert chips via `textContent`.

**Tech Stack:** Python 3 / FastAPI / anthropic SDK streaming, vanilla JS, pytest + `TestClient`.

**Spec:** `docs/plans/2026-10-28-procesfeedback-en-bronnen.md`

## Global Constraints

- AI-calls alleen via `_ai._client()`; `chat.py` blijft de enige streaming-module (CLAUDE.md).
- Geen business logic in `app_fastapi/`: parsen/strippen/detecteren leeft in `chat.py`; de route plakt alleen SSE-events.
- Statuscodes exact: `lezen`, `intake`, `web`, `schooldoc`, `webinfo`. Onbekende code → frontend negeert.
- Bron-types exact: `studiegids`, `kwalificatiedossier`, `schooldocument`, `skills`, `website`. Onbekend type → item weg.
- Markerformaat: `<!-- bronnen: type|titel; type|titel|url -->`, laatste regel; titel gestript, max 80 tekens; max 6 items; dubbele `(type, titel)` → één.
- Ruwe modeltekst (mét marker) blijft in `chat_history`; strippen alleen op de read-boundary (`/api/chat`-stream en `/api/geschiedenis`).
- Geen `<!-- bronnen:` ooit zichtbaar in de UI; chips alleen via `textContent`; alleen `website`-chips zijn links (`rel="noopener noreferrer"`, `target="_blank"`).
- Geen chips/statusregel bij `lage_relevantie`; intake stuurt alleen status `intake`.
- Bestaande disclaimer-dedup blijft werken; `dedup_disclaimer` laat niet-`str`-items (Status) ongemoeid passeren.
- Lint/format/tests lokaal groen (`ruff check`, `ruff format`, `pytest`); UI-smoke verplicht vóór "klaar".
- Deploy pas na expliciet akkoord van Ed (spec B8).

## Review Focus

1. Marker gesplitst over chunk-grenzen (`<!-- bro` + `nnen: … -->`): niets van de marker mag als tekst lekken. → test in Task 2 (`strip_bronnenregel`).
2. Marker aanwezig maar sluit-`-->` ontbreekt (stream afgekapt door `max_tokens`): de rest wordt vastgehouden en verdwijnt; `splits_bronnen` levert dan géén bronnen en tekst tot aan de marker. → test in Task 1 en Task 2.
3. Model zet de marker níet onderaan maar midden in de tekst, met tekst erna: tekst erna gewoon doorgeven, marker weg. → test in Task 1 (`splits_bronnen`) en Task 2.
4. Antwoord begint met een ander blockquote dan de disclaimer (bv. een citaat `> "De student…"`): geen `schooldoc`/`webinfo`-status. → test in Task 3 (`status_uit_tekstbegin`).
5. `server_tool_use`-blok met een andere tool-naam dan `web_search`/`web_fetch` (toekomstige tools): geen `web`-status. → test in Task 4.

---

### Task 1: `Bron` + `splits_bronnen`

**Files:**
- Modify: `src/validatie_samenwijzer/chat.py` (na `_prefix_staart`, regel ~612)
- Test: `tests/test_chat.py`

**Interfaces:**
- Produces:
  - `@dataclass(frozen=True) class Bron: type: str; titel: str; url: str | None = None`
  - `BRON_TYPES: frozenset[str] = {"studiegids", "kwalificatiedossier", "schooldocument", "skills", "website"}`
  - `_BRONNEN_MARKER = "<!-- bronnen:"`, `_BRONNEN_SLUIT = "-->"`
  - `splits_bronnen(tekst: str) -> tuple[str, list[Bron]]` — tekst zonder markerregel (rstrip op het stuk vóór de marker, tekst ná `-->` ongewijzigd erachter geplakt), plus gevalideerde lijst.

- [ ] **Step 1: Write the failing tests**

```python
from validatie_samenwijzer.chat import Bron, splits_bronnen


def test_splits_bronnen_geldig():
    tekst = "Antwoord.\n\n<!-- bronnen: studiegids|OER Kok BOL 2026; schooldocument|Studentenstatuut; website|curio.nl|https://curio.nl/x -->"
    schoon, bronnen = splits_bronnen(tekst)
    assert schoon == "Antwoord."
    assert bronnen == [
        Bron("studiegids", "OER Kok BOL 2026"),
        Bron("schooldocument", "Studentenstatuut"),
        Bron("website", "curio.nl", "https://curio.nl/x"),
    ]


def test_splits_bronnen_zonder_marker_is_passthrough():
    assert splits_bronnen("Gewoon antwoord.") == ("Gewoon antwoord.", [])


def test_splits_bronnen_onbekend_type_valt_weg():
    _, bronnen = splits_bronnen("x\n<!-- bronnen: folder|Brochure; skills|ESCO kok -->")
    assert bronnen == [Bron("skills", "ESCO kok")]


def test_splits_bronnen_dedupt_en_kapt_op_zes():
    items = "; ".join(f"studiegids|Doc {i}" for i in range(8)) + "; studiegids|Doc 0"
    _, bronnen = splits_bronnen(f"x\n<!-- bronnen: {items} -->")
    assert [b.titel for b in bronnen] == [f"Doc {i}" for i in range(6)]


def test_splits_bronnen_stript_en_kapt_titel_op_80():
    _, bronnen = splits_bronnen("x\n<!-- bronnen: studiegids|   " + "a" * 100 + "   -->")
    assert bronnen[0].titel == "a" * 80


def test_splits_bronnen_tekst_na_marker_blijft():
    schoon, bronnen = splits_bronnen("Voor.\n<!-- bronnen: studiegids|OER -->\nNa.")
    assert schoon == "Voor.\nNa."
    assert bronnen == [Bron("studiegids", "OER")]


def test_splits_bronnen_zonder_sluiting_geeft_geen_bronnen():
    schoon, bronnen = splits_bronnen("Voor.\n<!-- bronnen: studiegids|OER")
    assert schoon == "Voor."
    assert bronnen == []


def test_splits_bronnen_lege_items_worden_overgeslagen():
    _, bronnen = splits_bronnen("x\n<!-- bronnen: ; studiegids|OER;; website| -->")
    assert bronnen == [Bron("studiegids", "OER")]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run python -m pytest tests/test_chat.py -k splits_bronnen -v`
Expected: FAIL with `ImportError: cannot import name 'Bron'`

- [ ] **Step 3: Implement `Bron`, `BRON_TYPES`, `splits_bronnen` in `chat.py`**

Zoek `_BRONNEN_MARKER` met `str.find`; zonder sluiting: tekst vóór marker (rstrip), lege lijst. Items splitsen op `;`, velden op `|` (max 3 velden); `website`-item met leeg derde veld → `url=None`; lege titel → item weg. Dedup op `(type, titel)` met behoud van volgorde; daarna `[:6]`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run python -m pytest tests/test_chat.py -k splits_bronnen -v`
Expected: 8 PASS

- [ ] **Step 5: Commit**

```bash
git checkout -b feat/procesfeedback-bronnen
git add src/validatie_samenwijzer/chat.py tests/test_chat.py
git commit -m "feat(validatie): Bron-dataclass + splits_bronnen voor de bronnenregel"
```

---

### Task 2: `strip_bronnenregel` (streaming vasthouden)

**Files:**
- Modify: `src/validatie_samenwijzer/chat.py` (direct na `splits_bronnen`)
- Test: `tests/test_chat.py`

**Interfaces:**
- Consumes: `_BRONNEN_MARKER`, `_BRONNEN_SLUIT`, `_prefix_staart` (Task 1 / bestaand).
- Produces: `strip_bronnenregel(chunks: Iterable[str | Status]) -> Generator[str | Status]` — geeft tekst door, houdt een mogelijke marker-prefix vast (`_prefix_staart(buf, _BRONNEN_MARKER)`), laat alles tussen marker en `-->` (inclusief) weg, geeft tekst ná `-->` weer door; bij stream-einde zonder sluiting verdwijnt de vastgehouden rest. Niet-`str`-items passeren direct. (`Status` komt in Task 4; definieer het hier alvast als `@dataclass(frozen=True) class Status: code: str` zodat de type-hint klopt.)

- [ ] **Step 1: Write the failing tests**

```python
from validatie_samenwijzer.chat import Status, strip_bronnenregel


def test_strip_bronnenregel_laat_marker_weg():
    out = "".join(strip_bronnenregel(["Antwoord.\n\n<!-- bronnen: studiegids|OER -->"]))
    assert out == "Antwoord.\n\n"


def test_strip_bronnenregel_marker_over_chunkgrens():
    chunks = ["Antwoord.\n<!-- bro", "nnen: studiegids|OER ", "-->"]
    assert "".join(strip_bronnenregel(chunks)) == "Antwoord.\n"


def test_strip_bronnenregel_houdt_gewone_tekst_niet_vast():
    gen = strip_bronnenregel(iter(["Hallo ", "wereld"]))
    assert next(gen) == "Hallo "


def test_strip_bronnenregel_tekst_na_sluiting_gaat_door():
    chunks = ["Voor.\n<!-- bronnen: studiegids|OER -->\nNa."]
    assert "".join(strip_bronnenregel(chunks)) == "Voor.\n\nNa."


def test_strip_bronnenregel_zonder_sluiting_verdwijnt_rest():
    assert "".join(strip_bronnenregel(["Voor.\n<!-- bronnen: studiegids|OE"])) == "Voor.\n"


def test_strip_bronnenregel_laat_status_passeren():
    items = list(strip_bronnenregel([Status("web"), "tekst"]))
    assert items == [Status("web"), "tekst"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run python -m pytest tests/test_chat.py -k strip_bronnenregel -v`
Expected: FAIL with `ImportError: cannot import name 'Status'`

- [ ] **Step 3: Implement `Status` en `strip_bronnenregel` in `chat.py`**

Zelfde buffer-patroon als `dedup_disclaimer`: toestand `in_marker: bool`; buiten de marker yield je `buf[:len(buf) - _prefix_staart(buf, _BRONNEN_MARKER)]` en houdt de staart vast; zodra `_BRONNEN_MARKER` in `buf` staat → tekst ervoor yielden, `in_marker=True`; binnen de marker zoeken naar `_BRONNEN_SLUIT`, daarna `in_marker=False` en de rest normaal verwerken.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run python -m pytest tests/test_chat.py -k strip_bronnenregel -v`
Expected: 6 PASS

- [ ] **Step 5: Commit**

```bash
git add src/validatie_samenwijzer/chat.py tests/test_chat.py
git commit -m "feat(validatie): strip_bronnenregel houdt de bronnenmarker uit de stream"
```

---

### Task 3: `status_uit_tekstbegin` + `dedup_disclaimer` laat Status door

**Files:**
- Modify: `src/validatie_samenwijzer/chat.py` (`dedup_disclaimer` regel ~575; nieuwe helper erna)
- Test: `tests/test_chat.py`

**Interfaces:**
- Consumes: `_SCHOOLDOC_DISCLAIMER`, `_WEB_DISCLAIMER`, `Status`.
- Produces:
  - `status_uit_tekstbegin(tekst: str) -> str | None` — `"schooldoc"` als `tekst.startswith(_SCHOOLDOC_DISCLAIMER)`, `"webinfo"` bij `_WEB_DISCLAIMER`, anders `None`. (De route roept dit alleen aan zolang `len(antwoord) < 200` en nog geen status gemeld is.)
  - `dedup_disclaimer(chunks: Iterable[str | Status], disclaimer: str) -> Generator[str | Status]` — niet-`str`-items worden direct geyield (vóór eventueel gebufferde tekst; de volgorde status↔tekst is niet significant).

- [ ] **Step 1: Write the failing tests**

```python
from validatie_samenwijzer.chat import (
    _SCHOOLDOC_DISCLAIMER, _WEB_DISCLAIMER, Status, dedup_disclaimer, status_uit_tekstbegin,
)


def test_status_uit_tekstbegin_schooldoc():
    assert status_uit_tekstbegin(_SCHOOLDOC_DISCLAIMER + "\n\nAntwoord") == "schooldoc"


def test_status_uit_tekstbegin_webinfo():
    assert status_uit_tekstbegin(_WEB_DISCLAIMER + "\n\nAntwoord") == "webinfo"


def test_status_uit_tekstbegin_onvolledige_prefix_is_none():
    assert status_uit_tekstbegin(_SCHOOLDOC_DISCLAIMER[:20]) is None


def test_status_uit_tekstbegin_ander_blockquote_is_none():
    assert status_uit_tekstbegin('> "De student ontvangt uiterlijk in juli…"') is None


def test_dedup_disclaimer_laat_status_passeren():
    out = list(dedup_disclaimer([Status("web"), "abc"], "DISCLAIMER"))
    assert Status("web") in out and "".join(x for x in out if isinstance(x, str)) == "abc"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run python -m pytest tests/test_chat.py -k "status_uit_tekstbegin or laat_status" -v`
Expected: FAIL (`ImportError` voor `status_uit_tekstbegin`; `TypeError` in `dedup_disclaimer` bij `buf += Status`)

- [ ] **Step 3: Implement**

In `dedup_disclaimer`: bovenaan de for-lus `if not isinstance(chunk, str): yield chunk; continue`. Voeg `status_uit_tekstbegin` toe.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run python -m pytest tests/test_chat.py -v`
Expected: alle PASS (ook de bestaande dedup-tests)

- [ ] **Step 5: Commit**

```bash
git add src/validatie_samenwijzer/chat.py tests/test_chat.py
git commit -m "feat(validatie): status_uit_tekstbegin + Status-passthrough in dedup_disclaimer"
```

---

### Task 4: `genereer_antwoord` itereert events en yieldt `Status("web")`

**Files:**
- Modify: `src/validatie_samenwijzer/chat.py:614-681` (`genereer_antwoord`)
- Test: `tests/test_chat.py`

**Interfaces:**
- Consumes: `Status`, `dedup_disclaimer` (Task 3).
- Produces: `genereer_antwoord(...) -> Generator[str | Status]`. Nieuwe interne `_stream_items(stream) -> Generator[str | Status]`: SDK-event `type == "text"` → `event.text`; `type == "content_block_start"` met `event.content_block.type == "server_tool_use"` en `event.content_block.name in ("web_search", "web_fetch")` → `Status("web")`, hooguit één keer per antwoord; andere events negeren.

- [ ] **Step 1: Write the failing tests**

```python
from contextlib import contextmanager
from types import SimpleNamespace as NS

from validatie_samenwijzer.chat import Status, genereer_antwoord


def _nep_client(events):
    @contextmanager
    def _stream(**_kw):
        yield iter(events)

    return NS(messages=NS(stream=_stream))


def test_genereer_antwoord_yieldt_web_status_voor_tekst():
    events = [
        NS(type="message_start"),
        NS(type="content_block_start", content_block=NS(type="server_tool_use", name="web_search")),
        NS(type="content_block_start", content_block=NS(type="server_tool_use", name="web_fetch")),
        NS(type="content_block_start", content_block=NS(type="text")),
        NS(type="text", text="Hallo "),
        NS(type="text", text="wereld"),
    ]
    out = list(genereer_antwoord(_nep_client(events), "sys", [{"role": "user", "content": "q"}]))
    assert out[0] == Status("web")
    assert out.count(Status("web")) == 1
    assert "".join(x for x in out if isinstance(x, str)) == "Hallo wereld"


def test_genereer_antwoord_zonder_tool_geen_status():
    events = [NS(type="text", text="A"), NS(type="text", text="B")]
    out = list(genereer_antwoord(_nep_client(events), "sys", [{"role": "user", "content": "q"}]))
    assert out == ["A", "B"]


def test_genereer_antwoord_onbekende_servertool_geen_status():
    events = [
        NS(type="content_block_start", content_block=NS(type="server_tool_use", name="code_execution")),
        NS(type="text", text="A"),
    ]
    out = list(genereer_antwoord(_nep_client(events), "sys", [{"role": "user", "content": "q"}]))
    assert out == ["A"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run python -m pytest tests/test_chat.py -k genereer_antwoord -v`
Expected: FAIL (`AttributeError: 'list_iterator' object has no attribute 'text_stream'` of vergelijkbaar)

- [ ] **Step 3: Implement**

Vervang `stream.text_stream` in de dedup-keten door `_stream_items(stream)`; docstring-`Yields` bijwerken ("tekst-fragmenten en `Status`-objecten").

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run python -m pytest tests/test_chat.py -v`
Expected: alle PASS

- [ ] **Step 5: Commit**

```bash
git add src/validatie_samenwijzer/chat.py tests/test_chat.py
git commit -m "feat(validatie): genereer_antwoord meldt webzoek als Status-event"
```

---

### Task 5: Prompt — BRONNENREGEL-alinea in beide OER-templates

**Files:**
- Modify: `src/validatie_samenwijzer/chat.py` (`_SYSTEEM_TEMPLATE` ~194-262, `_MULTI_SYSTEEM_TEMPLATE` ~685-750, `bouw_systeem`, `bouw_gecombineerd_systeem`)
- Test: `tests/test_chat.py`

**Interfaces:**
- Produces: `_BRONNENREGEL_BLOK: str` (module-constante), ingevoegd via placeholder `{bronnenregel}` direct vóór `{web_zoek_blok}` in beide templates. Niet in `_INTAKE_SYSTEEM`.

- [ ] **Step 1: Write the failing tests**

```python
from validatie_samenwijzer.chat import (
    _INTAKE_SYSTEEM, bouw_gecombineerd_systeem, bouw_systeem,
)


def test_bouw_systeem_bevat_bronnenregel_instructie():
    s = bouw_systeem("OER-tekst", "Kok", "Curio")
    assert "BRONNENREGEL" in s and "<!-- bronnen:" in s
    for t in ("studiegids", "kwalificatiedossier", "schooldocument", "skills", "website"):
        assert t in s


def test_bouw_gecombineerd_meervoudig_bevat_bronnenregel():
    items = [
        {"tekst": "A", "opleiding": "Kok", "display_naam": "Curio", "leerweg": "BOL", "cohort": "2026"},
        {"tekst": "B", "opleiding": "Kok", "display_naam": "Landstede", "leerweg": "BOL", "cohort": "2026"},
    ]
    assert "BRONNENREGEL" in bouw_gecombineerd_systeem(items)


def test_intake_systeem_heeft_geen_bronnenregel():
    assert "BRONNENREGEL" not in _INTAKE_SYSTEEM
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run python -m pytest tests/test_chat.py -k bronnenregel -v`
Expected: 2 FAIL (`assert "BRONNENREGEL" in s`), 1 PASS

- [ ] **Step 3: Implement `_BRONNENREGEL_BLOK`**

Exacte copy (spec C):

```
BRONNENREGEL. Sluit elk antwoord waarin je een bron gebruikt af met PRECIES één regel,
helemaal onderaan, in dit machineformaat (de gebruiker ziet deze regel niet; hij wordt
omgezet in nette bronvermeldingen):
<!-- bronnen: type|titel; type|titel -->
- type is één van: studiegids, kwalificatiedossier, schooldocument, skills, website.
- titel is de naam uit de blokkop hierboven, zonder [INFORMATIEF] en zonder de
  instellingsnaam tussen haakjes, in gewone hoofdletters (bv. "Examenreglement",
  "Protocol kluiscontrole"). Voor de studiegids: "OER <opleiding>" (bij meerdere OER's de
  naam uit de kop "OER N: …"). Voor het KD: "Kwalificatiedossier <crebo>". Voor skills:
  de bronnaam uit de kop (ESCO of CompetentNL). Voor website: het domein, gevolgd door
  |<volledige url> als derde veld.
- Noem alleen bronnen die je in dít antwoord daadwerkelijk gebruikt hebt; maximaal 6.
- Heb je geen bron gebruikt (bv. "dat staat nergens in de bronnen"), laat de regel dan weg.
- Vacature-antwoorden krijgen geen bronnenregel (de links staan al in de tekst).
```

Voeg `bronnenregel=_BRONNENREGEL_BLOK` toe aan beide `.format(...)`-aanroepen.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run python -m pytest tests/test_chat.py -v`
Expected: alle PASS

- [ ] **Step 5: Commit**

```bash
git add src/validatie_samenwijzer/chat.py tests/test_chat.py
git commit -m "feat(validatie): BRONNENREGEL-instructie in de OER-systeemprompts"
```

---

### Task 6: Route `/api/chat` — `status`- en `bronnen`-events; `/api/geschiedenis` met bronnen

**Files:**
- Modify: `app_fastapi/main.py:307-366` (`api_chat`), `:422-425` (`api_geschiedenis`)
- Modify: `src/validatie_samenwijzer/chat.py` (nieuwe helper `geschiedenis_voor_ui`)
- Test: `tests/test_fastapi_poc.py`

**Interfaces:**
- Consumes: `Status`, `strip_bronnenregel`, `splits_bronnen`, `status_uit_tekstbegin`, `genereer_antwoord` (Tasks 1-4).
- Produces:
  - SSE-events in deze volgorde: `{"status": "lezen"|"intake"}` als eerste event (niet bij `lage_relevantie`); `{"status": "web"}` zodra `Status("web")` uit de generator komt; `{"status": "schooldoc"|"webinfo"}` zodra `status_uit_tekstbegin(antwoord)` niet-`None` is (alleen checken zolang `len(antwoord) < 200` en nog niets gemeld); `{"chunk": …}` voor gestripte tekst; `{"bronnen": [{"type","titel","url"}, …]}` vóór `{"done": true}` alleen in modus `oer` én bij niet-lege lijst.
  - `chat.geschiedenis_voor_ui(chat_history: list[dict]) -> list[dict]` — per beurt `{"role", "content"}`; voor `assistant`-beurten `content` gestript via `splits_bronnen` plus `"bronnen": [asdict(b), …]` (altijd aanwezig, mag leeg zijn). `chat_history` zelf blijft ongewijzigd (ruwe tekst mét marker).
  - `/api/geschiedenis` → `{"beurten": geschiedenis_voor_ui(s.chat_history)}`.

- [ ] **Step 1: Write the failing tests** (in `tests/test_fastapi_poc.py`, naast `test_chat_logt_timing_zonder_vraagtekst`; zelfde `_WW`-skip en `_client()`-patroon)

```python
def _events(tekst: str) -> list[dict]:
    import json
    return [json.loads(line[6:]) for line in tekst.splitlines() if line.startswith("data: ")]


def test_chat_stuurt_status_lezen_bronnen_en_stript_marker(monkeypatch):
    if not _WW:
        pytest.skip("ALGEMEEN_WACHTWOORD niet gezet.")
    import app_fastapi.main as m
    from validatie_samenwijzer.chat import Status

    monkeypatch.setattr(m, "laad_context_met_melding", lambda ids, *a, **k: ("SYS", ["label"], [], False, ""))
    monkeypatch.setattr(
        m, "genereer_antwoord",
        lambda *a, **k: iter([Status("web"), "Antwoord.\n\n<!-- bro", "nnen: studiegids|OER Kok; website|curio.nl|https://curio.nl -->"]),
    )
    c = _client()
    c.post("/api/kies", json={"oer_ids": [1]})
    ev = _events(c.post("/api/chat", json={"vraag": "kluisjes?"}).text)
    assert ev[0] == {"status": "lezen"}
    assert {"status": "web"} in ev
    assert "".join(e["chunk"] for e in ev if "chunk" in e) == "Antwoord.\n\n"
    assert ev[-2] == {"bronnen": [
        {"type": "studiegids", "titel": "OER Kok", "url": None},
        {"type": "website", "titel": "curio.nl", "url": "https://curio.nl"},
    ]}
    assert ev[-1] == {"done": True}
    # ruwe tekst mét marker in de historie; geschiedenis-API stript en levert bronnen
    g = c.get("/api/geschiedenis").json()["beurten"]
    assert g[-1]["content"] == "Antwoord." and g[-1]["bronnen"][0]["titel"] == "OER Kok"
    assert "<!-- bronnen:" not in c.get("/api/geschiedenis").text


def test_chat_meldt_schooldoc_status_uit_tekstbegin(monkeypatch):
    if not _WW:
        pytest.skip("ALGEMEEN_WACHTWOORD niet gezet.")
    import app_fastapi.main as m
    from validatie_samenwijzer.chat import _SCHOOLDOC_DISCLAIMER

    monkeypatch.setattr(m, "laad_context_met_melding", lambda ids, *a, **k: ("SYS", ["label"], [], False, ""))
    helft = len(_SCHOOLDOC_DISCLAIMER) // 2
    monkeypatch.setattr(
        m, "genereer_antwoord",
        lambda *a, **k: iter([_SCHOOLDOC_DISCLAIMER[:helft], _SCHOOLDOC_DISCLAIMER[helft:], "\n\nAntwoord"]),
    )
    c = _client()
    c.post("/api/kies", json={"oer_ids": [1]})
    ev = _events(c.post("/api/chat", json={"vraag": "statuut?"}).text)
    statussen = [e["status"] for e in ev if "status" in e]
    assert statussen == ["lezen", "schooldoc"]
    assert not any("bronnen" in e for e in ev)


def test_chat_intake_stuurt_status_intake_zonder_bronnen(monkeypatch):
    if not _WW:
        pytest.skip("ALGEMEEN_WACHTWOORD niet gezet.")
    import app_fastapi.main as m

    monkeypatch.setattr(m, "genereer_intake_antwoord", lambda *a, **k: iter(["Welke school?"]))
    ev = _events(_client().post("/api/chat", json={"vraag": "hoi"}).text)
    assert ev[0] == {"status": "intake"}
    assert not any("bronnen" in e for e in ev)


def test_chat_lage_relevantie_stuurt_geen_status(monkeypatch):
    if not _WW:
        pytest.skip("ALGEMEEN_WACHTWOORD niet gezet.")
    import app_fastapi.main as m

    monkeypatch.setattr(m, "laad_context_met_melding", lambda ids, *a, **k: ("", [], [], False, ""))
    monkeypatch.setattr(m, "ai_client", lambda: (_ for _ in ()).throw(AssertionError("AI niet aanroepen")))
    c = _client()
    c.post("/api/kies", json={"oer_ids": [1]})
    ev = _events(c.post("/api/chat", json={"vraag": "x"}).text)
    assert not any("status" in e for e in ev)
```

En in `tests/test_chat.py`:

```python
from validatie_samenwijzer.chat import geschiedenis_voor_ui


def test_geschiedenis_voor_ui_stript_en_laat_history_heel():
    hist = [
        {"role": "user", "content": "v"},
        {"role": "assistant", "content": "a\n<!-- bronnen: studiegids|OER -->"},
    ]
    ui = geschiedenis_voor_ui(hist)
    assert ui[0] == {"role": "user", "content": "v"}
    assert ui[1] == {"role": "assistant", "content": "a", "bronnen": [{"type": "studiegids", "titel": "OER", "url": None}]}
    assert hist[1]["content"].endswith("-->")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run python -m pytest tests/test_fastapi_poc.py -k "status or bronnen or intake_stuurt or lage_relevantie_stuurt" tests/test_chat.py -k geschiedenis_voor_ui -v`
Expected: FAIL (`ev[0] == {"status": "lezen"}` faalt; `ImportError` voor `geschiedenis_voor_ui`)

- [ ] **Step 3: Implement**

In `api_chat.stream()`: na modus-bepaling `yield status-event` voor `oer`/`intake`; wikkel `gen` in `strip_bronnenregel(gen)`; in de lus `if isinstance(item, Status): yield status-event; continue`; `ruw += item` (ongestript, voor historie) **en** tekst-chunk yielden; na elke chunk `status_uit_tekstbegin(ruw)`-check zoals in Interfaces. Let op: `strip_bronnenregel` wijzigt de tekst, dus bouw `ruw` op uit de **ongestripte** generator — wikkel daarom `gen` als volgt: `gen_ruw = genereer_antwoord(...)`; `def _tap(): for x in gen_ruw: if isinstance(x, str): ruw_delen.append(x); yield x` en voer `strip_bronnenregel(_tap())` naar de lus. Historie: `s.voeg_beurt_toe(vraag, "".join(ruw_delen))`. `ttft_s` blijft op de eerste tekst-chunk. Vóór `done`: `_, bronnen = splits_bronnen(ruw)`; als `modus == "oer"` en `bronnen` → `yield {"bronnen": [asdict(b) for b in bronnen]}`. Log-regel: `bronnen=%d` toevoegen.

`api_geschiedenis`: `JSONResponse({"beurten": geschiedenis_voor_ui(get_sessie(request).chat_history)})`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run python -m pytest tests/test_fastapi_poc.py tests/test_chat.py tests/test_intake_vervolg.py -v`
Expected: alle PASS (ook `test_chat_logt_timing_zonder_vraagtekst`, `test_api_geschiedenis_geeft_beurten`)

- [ ] **Step 5: Commit**

```bash
git add app_fastapi/main.py src/validatie_samenwijzer/chat.py tests/test_fastapi_poc.py tests/test_chat.py
git commit -m "feat(validatie): status- en bronnen-events in /api/chat, bronnen in /api/geschiedenis"
```

---

### Task 7: Frontend — statusregel, bronchips, vangnet, rehydratie

**Files:**
- Modify: `app_fastapi/static/chat.js:31-36` (`renderMarkdown`), `:91-105` (`FOUT_TEKSTEN`, `rehydrateer`), `:107-149` (`streamAntwoord`)
- Modify: `app_fastapi/static/app.css` (bij `.wacht-indicator` ~201 en `.vervolg-chip` ~186)
- Test: geen JS-testrunner; verificatie via Task 8 (UI-smoke). Optioneel: `tests/test_fastapi_poc.py::test_chat_js_bevat_status_en_bron_teksten` (leest het bestand en checkt dat `STATUS_TEKSTEN` de vijf codes en `BRON_TYPE_LABELS` de vijf types bevat).

**Interfaces:**
- Consumes: SSE-events `status`, `chunk`, `bronnen`, `done`, `error` (Task 6); `/api/geschiedenis`-beurten met `bronnen`.
- Produces (JS, module-scope in `chat.js`):
  - `const STATUS_TEKSTEN = { lezen: "Studiegids en officiële documenten lezen…", intake: "Opleiding zoeken…", web: "Niet in de documenten gevonden — website van de school raadplegen…", schooldoc: "Niet in de studiegids — officieel schooldocument van de school gebruikt", webinfo: "Niet in de documenten — informatie van de schoolwebsite gebruikt" }`
  - `const BRON_TYPE_LABELS = { studiegids: "Studiegids", kwalificatiedossier: "Kwalificatiedossier", schooldocument: "Schooldocument", skills: "Skills", website: "Website" }`
  - `function addBronnen(thread, bronnen)` — `div.bronnen` met `span.bronnen-label` ("Bronnen") + per item `span.bron-chip` (of `a.bron-chip` voor `website` met `href=url`, `target="_blank"`, `rel="noopener noreferrer"`, alleen als `url` begint met `http://`/`https://`); inhoud `span.bron-type` (label) + tekst `" · " + titel`, alles via `textContent`. Lege/onbekende lijst → niets. Onbekend type → item overslaan.
  - `function maakStatusRegel()` → `div.status-regel` met `span.status-tekst` (default "Even geduld") + drie `span.wacht-punt`; `function zetStatus(el, code)` → zet `status-tekst` alleen als `STATUS_TEKSTEN[code]` bestaat.

- [ ] **Step 1: Write the failing test** (optioneel maar aanbevolen, in `tests/test_fastapi_poc.py`)

```python
def test_chat_js_bevat_status_en_bron_teksten():
    from pathlib import Path
    js = Path("app_fastapi/static/chat.js").read_text(encoding="utf-8")
    for code in ("lezen", "intake", "web", "schooldoc", "webinfo"):
        assert f"{code}:" in js
    for t in ("Studiegids", "Kwalificatiedossier", "Schooldocument", "Skills", "Website"):
        assert f'"{t}"' in js
    assert "<!-- bronnen:" in js  # vangnet in renderMarkdown
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/test_fastapi_poc.py -k chat_js -v`
Expected: FAIL

- [ ] **Step 3: Implement `chat.js`**

- `renderMarkdown`: na `.split("\n")` → `.filter((l) => !l.trimStart().startsWith("<!-- bronnen:"))`.
- `streamAntwoord`: statusregel vóór de bubbel invoegen (`thread.appendChild(status)` vóór `node`); bubbel start leeg met `aria-busy`; `ev.status` → `zetStatus`; `ev.chunk` → als nu; `ev.bronnen` → bewaar in lokale `bronnen`; na de lus `status.remove()`; bij succes (`acc && !fout`) `addBronnen(thread, bronnen)` vóór `toonVervolgvragen`. Bij `error`/catch ook `status.remove()`.
- `rehydrateer`: `else { addAntwoord(thread, b.content); addBronnen(thread, b.bronnen || []); }`.
- Verwijder de oude inline `wacht-indicator`-HTML uit de bubbel (de statusregel vervangt hem).

- [ ] **Step 4: Implement `app.css`**

```css
.status-regel { display: inline-flex; align-items: center; gap: .35em; align-self: flex-start; color: var(--ink-faint); font-style: italic; font-size: .92rem; margin: 0 0 -.4rem .4rem; }
.bronnen { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; align-self: flex-start; max-width: 94%; margin-top: -.3rem; }
.bronnen-label { font-family: "JetBrains Mono", ui-monospace, Consolas, monospace; font-size: .68rem; letter-spacing: .08em; text-transform: uppercase; color: var(--ink-faint); margin-right: 4px; }
.bron-chip { font-size: .8rem; color: var(--ink); border: 1px solid var(--line); border-radius: 999px; padding: .3rem .8rem; text-decoration: none; }
.bron-chip .bron-type { color: var(--ink-soft); }
a.bron-chip:hover { border-color: var(--vermilion); }
```

Hergebruik `.wacht-punt` voor de puntjes. `.wacht-indicator` mag blijven staan (wordt niet meer gebruikt in `chat.js`; alleen verwijderen als `grep -rn wacht-indicator app_fastapi/` geen andere treffers geeft).

- [ ] **Step 5: Run test + lint**

Run: `uv run python -m pytest tests/test_fastapi_poc.py -k chat_js -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add app_fastapi/static/chat.js app_fastapi/static/app.css tests/test_fastapi_poc.py
git commit -m "feat(validatie): statusregel tijdens streamen + bronchips onder het antwoord"
```

---

### Task 8: Lint, volledige tests, UI-smoke, PR

**Files:**
- Geen nieuwe; verifieert Tasks 1-7.

- [ ] **Step 1: Lint + format + alle tests**

Run (vanuit `validatie_samenwijzer/`):
```bash
uv run ruff check --fix src/ app_fastapi/ scripts/ && uv run ruff format src/ app_fastapi/ scripts/
uv run python -m pytest -q
```
Expected: ruff 0 fouten; pytest alle PASS. Bij format-wijzigingen: `git commit -am "style: ruff format"`.

- [ ] **Step 2: Start de app en doorloop de UI-smoke** (CLAUDE.md: verplicht)

Run: `./start.sh` (poort 8504). Via browser-automatisering (chrome-devtools-mcp of playwright), toegang met `ALGEMEEN_WACHTWOORD` uit `.env`. Scenario's en verwacht gedrag:

| # | Scenario | Verwacht |
|---|---|---|
| 1 | Landstede, vraag "Mag ik mijn kluisje open laten?" (schooldocument) | statusregel `lezen` → `schooldoc` blijft staan tot `done`; daarna chips incl. `Schooldocument · …` |
| 2 | Curio Kok, "kluiscontrole" | chips tonen `Schooldocument · Protocol kluiscontrole` (geen `.pdf`) |
| 3 | Graafschap, examenplan-vraag | geen ℹ️-banner, wél chip `Schooldocument · Examenplan …` |
| 4 | Vraag die webzoek triggert (bv. "wanneer is de open dag?") | status `web` verschijnt vóór de eerste tekst; chip `Website · <domein>` is een link |
| 5 | Nieuw gesprek, vrije vraag zonder opleiding (intake) | status `intake`; geen chips |
| 6 | Page-reload na scenario 1 | chips staan er nog; nergens `<!-- bronnen:` zichtbaar |

Maak per scenario een screenshot in de scratchpad en controleer de DOM op `<!-- bronnen:` (`document.body.innerText.includes("<!-- bronnen:") === false`).

- [ ] **Step 3: Fix wat de smoke oplevert**, met een test per gevonden bug (TDD), en commit.

- [ ] **Step 4: Open de PR** (nooit direct naar `main`; `gh pr edit`/`merge` falen → REST via `gh api`)

```bash
git push -u origin feat/procesfeedback-bronnen
gh pr create --title "feat(validatie): procesfeedback tijdens streamen + bronnenlijst onder het antwoord" --body-file <pr-body>
```
PR-body: samenvatting van spec A/B/C, smoke-resultaten (tabel hierboven ingevuld), open vragen 1-3 uit de spec, en de attributieregel uit de systeemreminder.

- [ ] **Step 5: Merge + deploy alleen na expliciet akkoord van Ed** (spec B8)

```bash
gh api -X PUT repos/{owner}/{repo}/pulls/<N>/merge -f merge_method=squash
cd .. && flyctl deploy -a digitale-gids --remote-only
```
Daarna prod-smoke scenario 1 en 4 herhalen op https://digitale-gids.fly.dev.
