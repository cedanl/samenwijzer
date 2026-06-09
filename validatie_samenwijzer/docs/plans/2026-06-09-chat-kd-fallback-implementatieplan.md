# Chat-KD-fallback bij onleesbare OER — Implementatieplan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Laat de chat antwoorden op basis van het kwalificatiedossier en instellingsregelingen wanneer de OER-fulltext onleesbaar is (gescande OER's), met zichtbare melding en correcte citatie, i.p.v. `LAGE_RELEVANTIE_BERICHT`.

**Architecture:** Aanpak A uit de spec. `chat.bouw_systeem` krijgt een "OER-onleesbaar"-modus (drie template-placeholders met elk twee varianten) en blíjft altijd een prompt bouwen (contract ongewijzigd). `bouw_gecombineerd_systeem` neemt OER-loze-maar-KD/bron-items tóch op. De drie chatpagina's verruimen hun afhaak-gate van `if oer_tekst` naar "is er een bruikbare bron?" en tonen een `st.info`-banner als de OER onleesbaar is.

**Tech Stack:** Python 3.13, Streamlit, pytest. Alle commando's vanuit `validatie_samenwijzer/`.

**Spec:** `docs/plans/2026-06-09-chat-kd-fallback-onleesbare-oer.md`

---

## File Structure

- `src/validatie_samenwijzer/chat.py` — `_SYSTEEM_TEMPLATE` herstructureren naar 3 placeholders + variant-constanten; `bouw_systeem` modus-keuze; `bouw_gecombineerd_systeem` OER-loze items + `_MULTI_SYSTEEM_TEMPLATE`-zin. (Kernlogica.)
- `app/pages/1_oer_assistent.py` — gate + `oer_onleesbaar`-flag + banner. (Student.)
- `app/pages/5_begeleidingssessie.py` — idem. (Mentor.)
- `app/pages/0_oer_vraag.py` — twee item-build-paden verruimen + flag + banner. (Publiek, multi-OER.)
- `tests/test_chat.py` — unit-tests (bestaat al).
- `CLAUDE.md` — korte notitie bij de OER-chat-flow.

---

## Task 1: `bouw_systeem` — OER-onleesbaar-modus

**Files:**
- Modify: `src/validatie_samenwijzer/chat.py` (`_SYSTEEM_TEMPLATE` ~88-150, `bouw_systeem` ~337-374)
- Test: `tests/test_chat.py`

- [ ] **Step 1: Schrijf de falende tests**

Voeg toe aan `tests/test_chat.py` (onder de bestaande `bouw_systeem`-tests, bv. na regel 156):

```python
def test_bouw_systeem_onleesbare_oer_gebruikt_kd_modus():
    systeem = bouw_systeem("", "Kok", "Da Vinci", dossier_tekst="KD-INHOUD-HIER", crebo="25180")
    assert "KD-INHOUD-HIER" in systeem  # KD-blok aanwezig
    assert "niet machine-leesbaar" in systeem  # onleesbaar-modus framing
    assert "Dit is het leidende, schoolspecifieke document" not in systeem  # normale framing weg


def test_bouw_systeem_leesbare_oer_blijft_normale_modus():
    systeem = bouw_systeem("ECHTE OER-TEKST", "Kok", "Da Vinci", dossier_tekst="KD", crebo="25180")
    assert "ECHTE OER-TEKST" in systeem
    assert "Dit is het leidende, schoolspecifieke document" in systeem  # normale framing
    assert "niet machine-leesbaar" not in systeem
```

- [ ] **Step 2: Run de tests, verifieer dat ze falen**

Run: `uv run python -m pytest tests/test_chat.py -k "onleesbare_oer or leesbare_oer" -v`
Expected: FAIL (`niet machine-leesbaar` zit nog niet in de prompt; normale framing nog altijd aanwezig).

- [ ] **Step 3: Herstructureer het template + voeg variant-constanten toe**

In `src/validatie_samenwijzer/chat.py`, vervang in `_SYSTEEM_TEMPLATE` (regels 91-93) het PRIMAIRE-BRON-blok en (regels 101-104) het KD-instructieblok door placeholders, en de OER-sectie (regels 149-150) door een placeholder. Het template wordt:

Vervang dit fragment:
```python
PRIMAIRE BRON — de Onderwijs- en Examenregeling (OER) van deze opleiding.
Dit is het leidende, schoolspecifieke document. Beantwoord vragen primair op
basis van de OER.
```
door:
```python
{primaire_bron}
```

Vervang dit fragment:
```python
AANVULLENDE BRON — het landelijke kwalificatiedossier (KD). Raadpleeg het KD
alléén als de OER het onderwerp niet of onvoldoende behandelt. Geef niet
onnodig een tweede antwoord uit het KD als de OER de vraag al beantwoordt —
de OER is leidend.
```
door:
```python
{kd_instructie}
```

Vervang de laatste twee regels:
```python
=== ONDERWIJS- EN EXAMENREGELING (OER) ===
{oer_tekst}{instelling_blok}{dossier_blok}{skills_blok}"""
```
door:
```python
{oer_sectie}{instelling_blok}{dossier_blok}{skills_blok}"""
```

Voeg direct ná `_SYSTEEM_TEMPLATE` (vóór `_DOSSIER_BLOK_TEMPLATE`, regel ~152) deze constanten toe:

```python
# Twee modi voor de bronhiërarchie: normaal (OER leidend) en onleesbaar (gescande OER
# zonder tekstlaag → KD/regelingen als hoofdbron). Zie spec 2026-06-09-chat-kd-fallback.
_PRIMAIRE_BRON_OER = """\
PRIMAIRE BRON — de Onderwijs- en Examenregeling (OER) van deze opleiding.
Dit is het leidende, schoolspecifieke document. Beantwoord vragen primair op
basis van de OER."""

_PRIMAIRE_BRON_GEEN_OER = """\
LET OP — de OER van deze opleiding is niet machine-leesbaar en dus NIET
beschikbaar als bron. Baseer je antwoord volledig op de aanvullende bronnen
hieronder (instellingsbrede regelingen en het kwalificatiedossier)."""

_KD_INSTRUCTIE_OER = """\
AANVULLENDE BRON — het landelijke kwalificatiedossier (KD). Raadpleeg het KD
alléén als de OER het onderwerp niet of onvoldoende behandelt. Geef niet
onnodig een tweede antwoord uit het KD als de OER de vraag al beantwoordt —
de OER is leidend."""

_KD_INSTRUCTIE_GEEN_OER = """\
HOOFDBRON — het landelijke kwalificatiedossier (KD). Omdat de OER ontbreekt is
het KD je hoofdbron voor opleidings- en beroepsinhoud. Citeer het KD direct met
bron, vindplaats en woordelijk citaat; gebruik NIET de inleider "De OER
beschrijft dit niet"."""

_OER_SECTIE_OER = "=== ONDERWIJS- EN EXAMENREGELING (OER) ===\n{oer_tekst}"
_OER_SECTIE_GEEN_OER = (
    "=== ONDERWIJS- EN EXAMENREGELING (OER) ===\n"
    "(De OER van deze opleiding is niet machine-leesbaar; gebruik de aanvullende "
    "bronnen hieronder.)"
)
```

- [ ] **Step 4: Pas `bouw_systeem` aan om de modus te kiezen**

Vervang in `bouw_systeem` de `return _SYSTEEM_TEMPLATE.format(...)` (regels 366-374) door:

```python
    oer_onleesbaar = not oer_tekst.strip()
    oer_sectie = (
        _OER_SECTIE_GEEN_OER
        if oer_onleesbaar
        else _OER_SECTIE_OER.format(oer_tekst=oer_tekst)
    )
    return _SYSTEEM_TEMPLATE.format(
        opleiding=opleiding,
        instelling=instelling,
        primaire_bron=_PRIMAIRE_BRON_GEEN_OER if oer_onleesbaar else _PRIMAIRE_BRON_OER,
        kd_instructie=_KD_INSTRUCTIE_GEEN_OER if oer_onleesbaar else _KD_INSTRUCTIE_OER,
        oer_sectie=oer_sectie,
        instelling_blok=_instelling_blok(instelling, instelling_bronnen),
        dossier_blok=dossier_blok,
        skills_blok=skills_tekst,
        web_zoek_blok=_WEB_ZOEK_BLOK if web_zoeken else "",
    )
```

Let op: `oer_tekst` is geen `.format`-argument meer (zit nu in `oer_sectie`).

- [ ] **Step 5: Run de nieuwe tests + bestaande bouw_systeem-tests**

Run: `uv run python -m pytest tests/test_chat.py -k "bouw_systeem" -v`
Expected: PASS — incl. de nieuwe twee én de bestaande (`test_bouw_systeem_bevat_oer_tekst`, `test_bouw_systeem_leeg_bij_geen_tekst`, `test_bouw_systeem_met_dossier_bevat_beide_bronnen`, etc.).

- [ ] **Step 6: Commit**

```bash
git add src/validatie_samenwijzer/chat.py tests/test_chat.py
git commit -m "feat(validatie): bouw_systeem krijgt OER-onleesbaar-modus (KD als hoofdbron)"
```

---

## Task 2: `bouw_gecombineerd_systeem` — OER-loze items opnemen

**Files:**
- Modify: `src/validatie_samenwijzer/chat.py` (`_MULTI_SYSTEEM_TEMPLATE` ~482-533, `bouw_gecombineerd_systeem` ~536-580)
- Test: `tests/test_chat.py`

- [ ] **Step 1: Schrijf de falende test**

Voeg toe aan `tests/test_chat.py` (bij de `bouw_gecombineerd_systeem`-tests, na regel ~233):

```python
def test_bouw_gecombineerd_meervoudig_neemt_oer_loos_item_op_via_kd():
    items = [
        {
            "tekst": "ECHTE OER 1",
            "opleiding": "Kok",
            "display_naam": "Da Vinci",
            "leerweg": "BOL",
            "cohort": "2025",
            "crebo": "25180",
        },
        {
            "tekst": "",  # onleesbare OER
            "opleiding": "Gastheer",
            "display_naam": "Da Vinci",
            "leerweg": "BBL",
            "cohort": "2025",
            "crebo": "25168",
            "dossier_tekst": "KD-GASTHEER-INHOUD",
        },
    ]
    systeem = bouw_gecombineerd_systeem(items)
    assert "ECHTE OER 1" in systeem
    assert "KD-GASTHEER-INHOUD" in systeem  # OER-loos item tóch opgenomen via KD
    assert "niet machine-leesbaar" in systeem  # notitie bij het OER-loze blok
```

- [ ] **Step 2: Run de test, verifieer dat hij faalt**

Run: `uv run python -m pytest tests/test_chat.py -k "oer_loos_item_op_via_kd" -v`
Expected: FAIL (het OER-loze item wordt nu via `if dossier_tekst`/`item['tekst']` wél meegenomen in de loop, maar de "niet machine-leesbaar"-notitie ontbreekt; assert op die zin faalt).

- [ ] **Step 3: Pas de per-item-blokopbouw aan**

In `bouw_gecombineerd_systeem`, vervang de OER-blok-opbouw (regel 564):

```python
        oer_blok = f"=== OER {i}: {label} ===\n\n{item['tekst']}"
```
door:
```python
        oer_inhoud = item["tekst"] if item["tekst"].strip() else (
            "(De OER van deze opleiding is niet machine-leesbaar; gebruik het "
            "bijbehorende kwalificatiedossier / de instellingsregelingen hieronder.)"
        )
        oer_blok = f"=== OER {i}: {label} ===\n\n{oer_inhoud}"
```

- [ ] **Step 4: Voeg één zin toe aan `_MULTI_SYSTEEM_TEMPLATE`**

In `_MULTI_SYSTEEM_TEMPLATE`, na de regel `AANVULLENDE BRON — de KDs (landelijke eisen, kerntaken, werkprocessen).` ... `de OER is leidend.` (regels 492-495), voeg een nieuwe regel toe direct ná `de OER is leidend.`:

```python
Staat bij een OER dat deze niet machine-leesbaar is, gebruik dan voor díe
opleiding het bijbehorende KD en de instellingsregelingen als hoofdbron.
```

- [ ] **Step 5: Run de test + alle gecombineerd-tests**

Run: `uv run python -m pytest tests/test_chat.py -k "gecombineerd" -v`
Expected: PASS — incl. bestaande (`test_bouw_gecombineerd_systeem_meervoudig_bevat_alle_oers`, `..._enkel_delegeert_naar_bouw_systeem`, `..._includeert_instelling_bron_per_oer`).

- [ ] **Step 6: Commit**

```bash
git add src/validatie_samenwijzer/chat.py tests/test_chat.py
git commit -m "feat(validatie): multi-OER-prompt neemt onleesbare OER op via KD"
```

---

## Task 3: `1_oer_assistent.py` — gate + flag + banner (student)

**Files:**
- Modify: `app/pages/1_oer_assistent.py` (~58-82 init, ~100-103 afhaak)

- [ ] **Step 1: Verruim de gate en zet de onleesbaar-flag**

Vervang (regels 58-82):

```python
if "oer_systeem" not in st.session_state:
    # Laad OER + instellingsregeling(en) + kwalificatiedossier eenmalig per sessie
    oer_tekst = laad_oer_tekst(resolve_oer_pad(bestandspad)) if bestandspad else ""
    dossier_tekst = laad_kwalificatiedossier_tekst(crebo)
    skills_tekst = laad_skills_tekst(crebo)
    instelling_bronnen = [
        (label, laad_instelling_bron_tekst(resolve_oer_pad(pad)))
        for label, pad in st.session_state.get("instelling_bron_paden", [])
    ]
    domeinen = web_zoek_domeinen([{"naam": instelling_naam}]) if instelling_naam else []
    st.session_state.oer_domeinen = domeinen
    st.session_state.oer_systeem = (
        bouw_systeem(
            oer_tekst,
            opleiding,
            instelling,
            dossier_tekst=dossier_tekst,
            crebo=crebo,
            skills_tekst=skills_tekst,
            instelling_bronnen=instelling_bronnen,
            web_zoeken=bool(domeinen),
        )
        if oer_tekst
        else ""
    )
```

door:

```python
if "oer_systeem" not in st.session_state:
    # Laad OER + instellingsregeling(en) + kwalificatiedossier eenmalig per sessie
    oer_tekst = laad_oer_tekst(resolve_oer_pad(bestandspad)) if bestandspad else ""
    dossier_tekst = laad_kwalificatiedossier_tekst(crebo)
    skills_tekst = laad_skills_tekst(crebo)
    instelling_bronnen = [
        (label, laad_instelling_bron_tekst(resolve_oer_pad(pad)))
        for label, pad in st.session_state.get("instelling_bron_paden", [])
    ]
    domeinen = web_zoek_domeinen([{"naam": instelling_naam}]) if instelling_naam else []
    st.session_state.oer_domeinen = domeinen
    # Antwoord zodra er een bruikbare bron is — ook als de OER zelf onleesbaar is
    # (gescande PDF) maar het KD of een instellingsregeling het onderwerp dekt.
    heeft_bron = bool(oer_tekst.strip() or dossier_tekst or instelling_bronnen)
    st.session_state.oer_onleesbaar = heeft_bron and not oer_tekst.strip()
    st.session_state.oer_systeem = (
        bouw_systeem(
            oer_tekst,
            opleiding,
            instelling,
            dossier_tekst=dossier_tekst,
            crebo=crebo,
            skills_tekst=skills_tekst,
            instelling_bronnen=instelling_bronnen,
            web_zoeken=bool(domeinen),
        )
        if heeft_bron
        else ""
    )
```

- [ ] **Step 2: Toon de banner boven de chat**

Voeg direct ná het `if "oer_systeem" not in st.session_state:`-blok (vóór de `for i, bericht ...`-lus op regel 84) toe:

```python
if st.session_state.get("oer_onleesbaar"):
    st.info(
        "De OER van jouw opleiding is niet machine-leesbaar; antwoorden komen "
        "uit het landelijke kwalificatiedossier en de instellingsregelingen."
    )
```

- [ ] **Step 3: UI-rooktest student**

Start de app lokaal in de achtergrond:
Run: `uv run streamlit run app/main.py` (poort 8503)
Log in als een student wiens OER onleesbaar is (zie Task 6 voor het koppelen van een testaccount aan crebo 25168). Verwacht: de blauwe banner staat boven de chat; een vraag levert een antwoord met "Volgens het kwalificatiedossier…" i.p.v. de lage-relevantie-melding. Controleer ook een student met een leesbare OER: géén banner.

- [ ] **Step 4: Commit**

```bash
git add app/pages/1_oer_assistent.py
git commit -m "feat(validatie): student-chat valt terug op KD bij onleesbare OER + banner"
```

---

## Task 4: `5_begeleidingssessie.py` — gate + flag + banner (mentor)

**Files:**
- Modify: `app/pages/5_begeleidingssessie.py` (~160-187 init, ~206-208 afhaak)

- [ ] **Step 1: Verruim de gate en zet de onleesbaar-flag**

Vervang (regels 174-187):

```python
            st.session_state.oer_systeem = (
                bouw_systeem(
                    oer_tekst,
                    opleiding,
                    instelling,
                    dossier_tekst=dossier_tekst,
                    crebo=crebo,
                    skills_tekst=skills_tekst,
                    instelling_bronnen=instelling_bronnen,
                    web_zoeken=bool(domeinen),
                )
                if oer_tekst
                else ""
            )
```

door:

```python
            heeft_bron = bool(oer_tekst.strip() or dossier_tekst or instelling_bronnen)
            st.session_state.oer_onleesbaar = heeft_bron and not oer_tekst.strip()
            st.session_state.oer_systeem = (
                bouw_systeem(
                    oer_tekst,
                    opleiding,
                    instelling,
                    dossier_tekst=dossier_tekst,
                    crebo=crebo,
                    skills_tekst=skills_tekst,
                    instelling_bronnen=instelling_bronnen,
                    web_zoeken=bool(domeinen),
                )
                if heeft_bron
                else ""
            )
```

- [ ] **Step 2: Toon de banner boven de chat**

Voeg direct ná het `if "oer_systeem" not in st.session_state:`-blok (vóór de `for i, bericht ...`-lus op regel 189) toe, op dezelfde inspringing als de `for`-lus (binnen `with tab_chat:`):

```python
        if st.session_state.get("oer_onleesbaar"):
            st.info(
                "De OER van deze student is niet machine-leesbaar; antwoorden "
                "komen uit het landelijke kwalificatiedossier en de "
                "instellingsregelingen."
            )
```

- [ ] **Step 3: UI-rooktest mentor**

Met de app draaiend: log in als mentor, open een begeleidingssessie van een student met een onleesbare OER. Verwacht: banner in de chat-tab; chatvraag → KD-onderbouwd antwoord. Een student met leesbare OER: geen banner.

- [ ] **Step 4: Commit**

```bash
git add app/pages/5_begeleidingssessie.py
git commit -m "feat(validatie): mentor-chat valt terug op KD bij onleesbare OER + banner"
```

---

## Task 5: `0_oer_vraag.py` — beide item-build-paden + flag + banner (publiek)

**Files:**
- Modify: `app/pages/0_oer_vraag.py` (selectie-pad ~233-263, intake-pad ~335-363, banner-render bij de chat)

- [ ] **Step 1: Verruim het selectie-pad (bevestig-knop)**

Vervang (regels 233-256):

```python
        for lbl in geselecteerd:
            k = opties[lbl]
            pad = resolve_oer_pad(k["bestandspad"])
            tekst = laad_oer_tekst(pad)
            if tekst:
                oer_items.append(
                    {
                        "tekst": tekst,
                        "opleiding": k["opleiding"],
                        "display_naam": k["display_naam"],
                        "naam": k["naam"],
                        "leerweg": k["leerweg"],
                        "cohort": k["cohort"],
                        "crebo": k.get("crebo", ""),
                        "dossier_tekst": laad_kwalificatiedossier_tekst(k.get("crebo")),
                        "skills_tekst": laad_skills_tekst(k.get("crebo")),
                        "instelling_bronnen": _examenreglement_bron(k["instelling_id"]),
                    }
                )
                labels.append(_label(k))
                paden.append(pad)

        if not oer_items:
            st.error("Geen van de geselecteerde studiegidsen kon worden geladen.")
```

door:

```python
        onleesbaar = False
        for lbl in geselecteerd:
            k = opties[lbl]
            pad = resolve_oer_pad(k["bestandspad"])
            tekst = laad_oer_tekst(pad)
            dossier_tekst = laad_kwalificatiedossier_tekst(k.get("crebo"))
            instelling_bronnen = _examenreglement_bron(k["instelling_id"])
            # Neem een OER ook op als de fulltext onleesbaar is maar het KD of een
            # instellingsregeling het onderwerp dekt.
            if tekst or dossier_tekst or instelling_bronnen:
                if not tekst:
                    onleesbaar = True
                oer_items.append(
                    {
                        "tekst": tekst,
                        "opleiding": k["opleiding"],
                        "display_naam": k["display_naam"],
                        "naam": k["naam"],
                        "leerweg": k["leerweg"],
                        "cohort": k["cohort"],
                        "crebo": k.get("crebo", ""),
                        "dossier_tekst": dossier_tekst,
                        "skills_tekst": laad_skills_tekst(k.get("crebo")),
                        "instelling_bronnen": instelling_bronnen,
                    }
                )
                labels.append(_label(k))
                paden.append(pad)

        if not oer_items:
            st.error("Geen van de geselecteerde studiegidsen kon worden geladen.")
```

- [ ] **Step 2: Sla de onleesbaar-flag op in het selectie-pad**

In hetzelfde blok, ná `st.session_state.pub_oer_domeinen = domeinen` (regel 264), voeg toe:

```python
            st.session_state.pub_oer_onleesbaar = onleesbaar
```

- [ ] **Step 3: Verruim het intake-pad (auto-load bij één top-match)**

Vervang (regels 337-353):

```python
        pad = resolve_oer_pad(k["bestandspad"])
        tekst = laad_oer_tekst(pad)
        if tekst:
            oer_items = [
                {
                    "tekst": tekst,
                    "opleiding": k["opleiding"],
                    "display_naam": k["display_naam"],
                    "naam": k["naam"],
                    "leerweg": k["leerweg"],
                    "cohort": k["cohort"],
                    "crebo": k.get("crebo", ""),
                    "dossier_tekst": laad_kwalificatiedossier_tekst(k.get("crebo")),
                    "skills_tekst": laad_skills_tekst(k.get("crebo")),
                    "instelling_bronnen": _examenreglement_bron(k["instelling_id"]),
                }
            ]
```

door:

```python
        pad = resolve_oer_pad(k["bestandspad"])
        tekst = laad_oer_tekst(pad)
        dossier_tekst = laad_kwalificatiedossier_tekst(k.get("crebo"))
        instelling_bronnen = _examenreglement_bron(k["instelling_id"])
        if tekst or dossier_tekst or instelling_bronnen:
            st.session_state.pub_oer_onleesbaar = not bool(tekst)
            oer_items = [
                {
                    "tekst": tekst,
                    "opleiding": k["opleiding"],
                    "display_naam": k["display_naam"],
                    "naam": k["naam"],
                    "leerweg": k["leerweg"],
                    "cohort": k["cohort"],
                    "crebo": k.get("crebo", ""),
                    "dossier_tekst": dossier_tekst,
                    "skills_tekst": laad_skills_tekst(k.get("crebo")),
                    "instelling_bronnen": instelling_bronnen,
                }
            ]
```

Let op: het `else:`-blok (regels 380-382, `antwoord = LAGE_RELEVANTIE_BERICHT; st.info(antwoord)`) blijft ongewijzigd — dat dekt nu het echt-niets-geval (geen OER-tekst én geen KD én geen bron).

- [ ] **Step 4: Toon de banner bij de actieve OER-chat**

Zoek de plek waar de publieke chat met geladen OER's wordt gerenderd (waar `st.session_state.pub_oer_labels` / de "📄 Bekijk OER"-knoppen worden getoond). Voeg direct vóór de chat-invoer een banner toe:

```python
if st.session_state.get("pub_oer_onleesbaar"):
    st.info(
        "De OER van deze opleiding is niet machine-leesbaar; antwoorden komen "
        "uit het landelijke kwalificatiedossier en de instellingsregelingen."
    )
```

Bepaal de exacte regel met:
Run: `grep -n "pub_oer_labels\|Bekijk OER\|pub_oer_systeem" app/pages/0_oer_vraag.py`
Plaats de banner in het render-blok dat draait wanneer `pub_oer_systeem` actief is, vóór `st.chat_input`.

- [ ] **Step 5: UI-rooktest publieke pagina**

Met de app draaiend, ga naar de publieke `0_oer_vraag`-pagina (geen login). Selecteer/vraag naar een opleiding met een onleesbare OER (Da Vinci crebo 25168). Verwacht: banner boven de chat; antwoord met KD-citatie. Controleer een leesbare OER: geen banner. Controleer een opleiding zónder enige bron (indien aanwezig): nog steeds `LAGE_RELEVANTIE_BERICHT`.

- [ ] **Step 6: Commit**

```bash
git add app/pages/0_oer_vraag.py
git commit -m "feat(validatie): publieke OER-chat valt terug op KD bij onleesbare OER + banner"
```

---

## Task 6: Testdata, volledige verificatie + docs

**Files:**
- Modify: `CLAUDE.md` (OER-chat-flow-sectie)
- Tijdelijk: DB-koppeling testaccount (niet committen — DB is gitignored)

- [ ] **Step 1: Koppel tijdelijk een testaccount aan een onleesbare OER**

Voor de UI-smoke-test bestaat er nog geen student op de 13 onleesbare OER's. Koppel lokaal een bestaand testaccount aan de onleesbare Da Vinci-OER (crebo 25168). Zoek de oer_id en een davinci-student, en herwijs die student:

Run:
```bash
uv run --project . python -c "
import sqlite3
c = sqlite3.connect('data/validatie.db')
oer = c.execute(\"SELECT id FROM oer_documenten WHERE crebo='25168' AND bestandspad LIKE '%davinci%' LIMIT 1\").fetchone()
stu = c.execute(\"SELECT id, studentnummer FROM studenten WHERE instelling_id=2 LIMIT 1\").fetchone()
print('oer_id', oer, 'student', stu)
"
```
Noteer het oer_id en studentnummer; herwijs daarna handmatig (alleen lokaal, voor de test):
```bash
uv run --project . python -c "
import sqlite3
c = sqlite3.connect('data/validatie.db')
c.execute('UPDATE studenten SET oer_id=? WHERE studentnummer=?', (<OER_ID>, '<STUDENTNUMMER>'))
c.commit(); print('herwezen')
"
```
> Dit is een lokale, niet-gecommitte testingreep. Zet 'm na de test terug of negeer (DB is gitignored en wordt bij deploy uit de gebakken image gehaald — productie raakt dit niet).

- [ ] **Step 2: Volledige UI-smoke-test (lokaal)**

Met `uv run streamlit run app/main.py`:
- Student `<STUDENTNUMMER>` / `Welkom123` → `1_oer_assistent`: banner zichtbaar, chatvraag ("Wat is een herkansing?") → antwoord met "Volgens het kwalificatiedossier…" of "Volgens het Examenreglement…", géén `LAGE_RELEVANTIE_BERICHT`.
- Een student met leesbare OER → géén banner, normale OER-citaten (regressie).
- Publieke pagina `0_oer_vraag` → vraag over crebo 25168 → banner + KD-antwoord.

- [ ] **Step 3: Volledige testsuite + lint**

Run: `uv run python -m pytest`
Expected: alle tests groen (incl. de nieuwe in test_chat.py).
Run: `uv run ruff check src/ app/ tests/ && uv run ruff format --check src/ app/ tests/`
Expected: schoon.

- [ ] **Step 4: Documenteer in CLAUDE.md**

Voeg in `CLAUDE.md`, in de "OER-chat-flow"-sectie (bij de beschrijving van `bouw_systeem`/`laad_oer_tekst`), een korte alinea toe:

```markdown
**OER-onleesbaar-modus**: is de OER-fulltext leeg (gescande PDF zonder tekstlaag), dan bouwt
`bouw_systeem` de prompt in een aangepaste modus die het kwalificatiedossier + instellingsregelingen
als hoofdbron neemt (i.p.v. de OER) en de citatie-instructie daarop aanpast. De chatpagina's
antwoorden zolang er een KD óf instellingsbron is en tonen dan een `st.info`-banner dat de OER niet
machine-leesbaar is. Alleen zónder enige bron volgt nog `LAGE_RELEVANTIE_BERICHT`. Spec:
`docs/plans/2026-06-09-chat-kd-fallback-onleesbare-oer.md`.
```

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md
git commit -m "docs(validatie): documenteer OER-onleesbaar-modus in chat-flow"
```

- [ ] **Step 6: PR**

```bash
git push -u origin feat/validatie-chat-kd-fallback
gh pr create --repo cedanl/samenwijzer --base main --head feat/validatie-chat-kd-fallback \
  --title "feat(validatie): chat-KD-fallback bij onleesbare OER" \
  --body "Implementeert deel 1 van #180: de chat antwoordt op basis van KD/instellingsregelingen wanneer de OER-fulltext onleesbaar is, met zichtbare banner en correcte citatie i.p.v. LAGE_RELEVANTIE_BERICHT. Spec + plan in docs/plans/. Refs #180."
```

---

## Self-Review (uitgevoerd bij het schrijven)

- **Spec-dekking:** trigger (KD óf instellingsbron) → Task 3/4/5 `heeft_bron`. Transparantie/banner → Task 3/4/5 `st.info`. Onleesbaar-modus template → Task 1. Multi-OER → Task 2/5. Tests → Task 1/2 unit + Task 6 UI. Testdata-aandachtspunt → Task 6 Step 1. ✓
- **Placeholders:** geen TBD/TODO; alle code-stappen tonen echte code. ✓
- **Type/naam-consistentie:** `heeft_bron`, `oer_onleesbaar` (1/5-pagina's), `pub_oer_onleesbaar` (publiek), constanten `_PRIMAIRE_BRON_OER/_GEEN_OER`, `_KD_INSTRUCTIE_OER/_GEEN_OER`, `_OER_SECTIE_OER/_GEEN_OER`, placeholders `{primaire_bron}`/`{kd_instructie}`/`{oer_sectie}` consistent tussen Task 1-definitie en gebruik. ✓
- **Contract:** `bouw_systeem` blijft altijd bouwen → bestaande `test_bouw_systeem_leeg_bij_geen_tekst` blijft groen (Task 1 Step 5). ✓
