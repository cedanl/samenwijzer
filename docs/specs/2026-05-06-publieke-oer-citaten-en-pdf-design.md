# Publieke OER-pagina: verbatim citaten en PDF-bekijken

**Datum**: 2026-05-06
**Project**: validatie_samenwijzer
**Pagina**: `app/pages/0_oer_vraag.py`

## Doel

De publieke OER-vraag-pagina (zonder login) moet juridisch verifieerbare antwoorden
geven én de gebruiker direct toegang bieden tot het bron-PDF van de geraadpleegde OER.

Reden: een OER is een juridisch document. Een student of ouder die zonder in te
loggen een vraag stelt, moet (a) elke claim kunnen narekenen via een woordelijk
citaat met sectie/pagina-verwijzing, en (b) het bronbestand zelf kunnen openen.

## Scope

In scope:
1. Systeemprompts in `chat.py` aanscherpen — verbatim citaten + sectie/pagina
   verplicht stellen, voor zowel single- als multi-OER.
2. PDF-bekijkfunctie toevoegen aan `0_oer_vraag.py`, gemodelleerd naar de
   logged-in pagina `2_mijn_oer.py` (iframe, 800px hoog, download-knop).

Out of scope:
- Geen wijziging aan identificatie- of intake-flow.
- Geen wijziging aan `2_mijn_oer.py` (werkt al).
- Geen verbatim-quote opslag of citation-extraction op codeniveau — alle
  citatieplicht zit in de systeemprompt.

## Wijzigingen per bestand

### `src/validatie_samenwijzer/chat.py`

`_SYSTEEM_TEMPLATE` (single-OER) — voeg verbatim-quote vereiste toe:

```
Verwijs bij elke claim naar de sectie of het paginanummer uit de OER
en citeer de relevante passage woordelijk tussen aanhalingstekens
(bijv. 'Volgens sectie 3.2: "..."' of 'Op pagina 12 staat: "..."').
```

`_MULTI_SYSTEEM_TEMPLATE` (multi-OER) — vervang de zwakke regel
("Verwijs bij elke claim naar de betreffende OER…") door:

```
Verwijs bij elke claim naar de betreffende OER (gebruik de aanduiding
uit de koppen hieronder), de sectie of het paginanummer, én citeer
de relevante passage woordelijk tussen aanhalingstekens.
```

Geen Python-codewijziging nodig — alleen tekstaanpassingen in twee f-string
templates.

### `app/pages/0_oer_vraag.py`

**Session state**: voeg veld `pub_oer_paden: list[Path]` toe aan `_DEFAULTS`.
Vul dit op de twee plekken waar `pub_oer_systeem` wordt gezet:

1. In de keuzelijst-bevestiging (regel ~110-130): bewaar `Path(k["bestandspad"])`
   per geselecteerde kandidaat in dezelfde volgorde als `pub_oer_labels`.
2. Bij auto-match met één kandidaat (regel ~219-236): idem voor de enkele kandidaat.

**UI**: voeg vlak na de header (na de "✅ {labels}"-regel, vóór de chatgeschiedenis)
een rij knoppen toe — één per geladen OER:

```python
if st.session_state.pub_oer_paden:
    cols = st.columns(len(st.session_state.pub_oer_paden))
    for i, (col, pad) in enumerate(zip(cols, st.session_state.pub_oer_paden)):
        with col:
            if st.button(f"📄 Bekijk OER {i+1}", key=f"toon_oer_{i}",
                         use_container_width=True):
                st.session_state[f"pub_toon_oer_{i}"] = (
                    not st.session_state.get(f"pub_toon_oer_{i}", False)
                )
    for i, pad in enumerate(st.session_state.pub_oer_paden):
        if st.session_state.get(f"pub_toon_oer_{i}"):
            with st.expander(
                f"📄 {st.session_state.pub_oer_labels[i]}", expanded=True
            ):
                _render_oer_bestand(pad)  # iframe + download
```

**`_render_oer_bestand(pad)`**: lokale helper die de logica uit `2_mijn_oer.py`
spiegelt — PDF inline (800px iframe + download-knop), `.md` met `st.markdown`,
`.html` met `extraheer_tekst_html`, anders een waarschuwing. Geen DRY-extractie
naar een gedeelde module nu (YAGNI — twee callsites is geen herhalingspatroon).

**Reset**: `_reset()` zet `pub_oer_paden` terug op `[]` (al gedekt door
`_DEFAULTS`-loop omdat het een lijst is).

## Foutscenario's

| Scenario | Gedrag |
|---|---|
| `pad` bestaat niet op schijf | Waarschuwing in expander, geen iframe |
| Niet-PDF bestand (`.md`/`.html`) | Tekst-rendering zoals in `2_mijn_oer.py` |
| Onbekend bestandstype | Waarschuwing |
| Geen OER geladen | Knoppenrij wordt niet getoond (lijst is leeg) |

## Tests

`tests/test_chat.py` asserteert alleen dat OER-tekst, opleiding en instelling
in de systeemprompt voorkomen — niet op de specifieke verwijzings-/citaat-
instructies. De prompt-aanpassingen breken de bestaande tests dus niet en er
zijn geen nieuwe tests nodig. UI-rendering wordt niet via pytest gedekt
(Streamlit-pagina's hebben geen test-harness in dit subproject).

## Acceptatiecriteria

1. Antwoord op publieke OER-pagina bevat per claim: OER-aanduiding (bij multi),
   sectie/pagina, en woordelijk citaat tussen aanhalingstekens.
2. Na OER-selectie verschijnen knoppen "📄 Bekijk OER N" boven de chat.
3. Klik op de knop opent een expander met PDF-iframe (800px) en download-knop.
4. "Nieuw gesprek" wist OER-paden samen met de rest van de state.
5. `uv run --no-sync ruff check .` → 0 errors.
6. `uv run --no-sync pytest -q` → 59 tests pass (geen testaanpassing nodig).
