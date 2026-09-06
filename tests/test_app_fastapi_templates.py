"""De vega-runtime in de chart-templates moet bij de geïnstalleerde Altair-versie passen.

Altair schrijft een `$schema` van vega-lite vX in de chart-JSON; laadt de pagina een
oudere runtime, dan waarschuwt vega-embed in de console. Altair N ⇒ vega-lite N + vega N +
vega-embed N+1.
"""

import re
from pathlib import Path

import altair as alt
import pytest

CHART_TEMPLATES = ("voortgang.html", "groepsoverzicht.html")
_TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "app_fastapi" / "templates"
_CDN = re.compile(r"cdn\.jsdelivr\.net/npm/(vega|vega-lite|vega-embed)@(\d+)\.\d+\.\d+\"")


@pytest.mark.parametrize("naam", CHART_TEMPLATES)
def test_vega_runtime_gepind_op_altair_versie(naam: str) -> None:
    altair_major = int(alt.__version__.split(".")[0])
    verwacht = {
        "vega": altair_major,
        "vega-lite": altair_major,
        "vega-embed": altair_major + 1,
    }
    treffers = _CDN.findall((_TEMPLATE_DIR / naam).read_text())
    assert {pakket: int(major) for pakket, major in treffers} == verwacht
