"""Guard: de vier hardgecodeerde instelling-lijsten moeten dezelfde keys hebben.

Een nieuwe instelling moet in álle definities verschijnen; ontbreekt ze in
``seed_bulk.INSTELLINGEN`` dan krijgt ze stil 0 studenten (zie CLAUDE.md).

De lijsten worden via AST uitgelezen i.p.v. geïmporteerd, omdat
``app/pages/9_beheer.py`` Streamlit-code op moduleniveau draait (set_page_config,
st.stop) en dus niet importeerbaar is, en omdat ``scripts/seed_bulk.py`` bij
import ``load_dotenv()`` + ``hash_wachtwoord`` uitvoert. AST-parsen heeft geen
side effects.
"""

import ast
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]


def _lees_toewijzing(pad: Path, naam: str):
    """Geef de literal-waarde van een toewijzing ``naam = ...`` via AST.

    Dekt zowel ``naam = ...`` (Assign) als ``naam: T = ...`` (AnnAssign).
    """
    tree = ast.parse(pad.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign):
            doelen = node.targets
        elif isinstance(node, ast.AnnAssign):
            doelen = [node.target]
        else:
            continue
        for doel in doelen:
            if isinstance(doel, ast.Name) and doel.id == naam:
                return ast.literal_eval(node.value)
    raise AssertionError(f"{naam} niet gevonden in {pad}")


def _instelling_keys() -> dict[str, set[str]]:
    ingest_pad = _ROOT / "src" / "validatie_samenwijzer" / "ingest.py"
    seed_pad = _ROOT / "scripts" / "seed_bulk.py"
    beheer_pad = _ROOT / "app" / "pages" / "9_beheer.py"

    return {
        # _MAP_NAAM: alleen keys vergelijken — de value rijn_ijssel->rijn_ijssel_oer
        # is een bewuste afwijking en valt buiten deze guard.
        "ingest._MAP_NAAM": set(_lees_toewijzing(ingest_pad, "_MAP_NAAM")),
        "ingest._INSTELLINGEN": set(_lees_toewijzing(ingest_pad, "_INSTELLINGEN")),
        "seed_bulk.INSTELLINGEN": {d["naam"] for d in _lees_toewijzing(seed_pad, "INSTELLINGEN")},
        "9_beheer._INSTELLING_KEYS": set(_lees_toewijzing(beheer_pad, "_INSTELLING_KEYS")),
    }


def test_instelling_lijsten_in_sync():
    keys = _instelling_keys()
    referentie_naam = "ingest._INSTELLINGEN"
    referentie = keys[referentie_naam]

    for naam, gevonden in keys.items():
        if naam == referentie_naam:
            continue
        ontbreekt = referentie - gevonden
        teveel = gevonden - referentie
        assert gevonden == referentie, (
            f"{naam} is niet in sync met {referentie_naam}. "
            f"ontbreekt={sorted(ontbreekt)}, teveel={sorted(teveel)}. "
            "Voeg nieuwe instellingen toe aan alle vier de definities "
            "(ingest._INSTELLINGEN, ingest._MAP_NAAM, seed_bulk.INSTELLINGEN, "
            "9_beheer._INSTELLING_KEYS)."
        )
