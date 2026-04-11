"""Architectuurcontroles — importgrenzen en layervolgorde.

Regels (zie ARCHITECTURE.md):
  prepare → transform → analyze → {visualize, coach, tutor, welzijn,
                                    outreach, outreach_store, auth, styles, export}
                                 → app

Verboden:
  1. app/ importeert nooit rechtstreeks `anthropic` (alleen via de AI-modules).
  2. prepare.py importeert niet uit hogere lagen.
  3. transform.py importeert niet uit analyze of hogere lagen.
  4. analyze.py importeert niet uit coach/tutor/welzijn/outreach/app.
"""

import ast
from pathlib import Path


# ── helpers ───────────────────────────────────────────────────────────────────

ROOT = Path(__file__).parent.parent
SRC = ROOT / "src" / "samenwijzer"
APP = ROOT / "app"


def _importnamen(path: Path) -> list[str]:
    """Geef alle top-level geïmporteerde modulenamen terug (recursief voor packages)."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    namen: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                namen.append(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                namen.append(node.module.split(".")[0])
    return namen


def _samenwijzer_imports(path: Path) -> list[str]:
    """Geef de samenwijzer-submodules terug die dit bestand importeert."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module and node.module.startswith("samenwijzer."):
                # "samenwijzer.analyze" → "analyze"
                modules.append(node.module.split(".", 1)[1])
    return modules


def _app_bestanden() -> list[Path]:
    return list(APP.glob("**/*.py"))


# ── 1. app/ importeert nooit anthropic rechtstreeks ──────────────────────────


def test_app_importeert_geen_anthropic_rechtstreeks() -> None:
    overtreders: list[str] = []
    for pad in _app_bestanden():
        if "anthropic" in _importnamen(pad):
            overtreders.append(str(pad.relative_to(ROOT)))
    assert not overtreders, (
        "app/ mag anthropic niet rechtstreeks importeren — gebruik de AI-modules.\n"
        f"Overtreders: {overtreders}"
    )


# ── 2. prepare importeert niet uit hogere lagen ───────────────────────────────

_HOGER_DAN_PREPARE = {
    "transform",
    "analyze",
    "visualize",
    "coach",
    "tutor",
    "welzijn",
    "outreach",
    "outreach_store",
    "auth",
    "styles",
    "export",
}


def test_prepare_importeert_geen_hogere_laag() -> None:
    imports = _samenwijzer_imports(SRC / "prepare.py")
    schendingen = [i for i in imports if i in _HOGER_DAN_PREPARE]
    assert not schendingen, f"prepare.py importeert uit hogere laag: {schendingen}"


# ── 3. transform importeert niet uit analyze of hogere lagen ─────────────────

_HOGER_DAN_TRANSFORM = _HOGER_DAN_PREPARE - {"transform"}


def test_transform_importeert_geen_hogere_laag() -> None:
    imports = _samenwijzer_imports(SRC / "transform.py")
    schendingen = [i for i in imports if i in _HOGER_DAN_TRANSFORM]
    assert not schendingen, f"transform.py importeert uit hogere laag: {schendingen}"


# ── 4. analyze importeert niet uit AI-modules of app ─────────────────────────

_AI_MODULES = {"coach", "tutor", "welzijn", "outreach", "outreach_store"}


def test_analyze_importeert_geen_ai_modules() -> None:
    imports = _samenwijzer_imports(SRC / "analyze.py")
    schendingen = [i for i in imports if i in _AI_MODULES]
    assert not schendingen, f"analyze.py importeert uit AI-module: {schendingen}"


# ── 5. AI-modules importeren niet uit app ────────────────────────────────────

_AI_BESTANDEN = ["coach.py", "tutor.py", "welzijn.py", "outreach.py"]


def test_ai_modules_importeren_niet_uit_app() -> None:
    overtreders: list[str] = []
    for naam in _AI_BESTANDEN:
        imports = _importnamen(SRC / naam)
        if "streamlit" in imports or "app" in imports:
            overtreders.append(naam)
    assert not overtreders, f"AI-modules importeren uit app-laag: {overtreders}"
