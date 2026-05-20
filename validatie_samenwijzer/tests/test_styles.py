"""Tests voor de gedeelde voortgang-helpers in styles.py."""

import pytest

from validatie_samenwijzer.styles import (
    GROEN,
    ORANJE,
    ROOD,
    bepaal_kleur,
    render_progress_bar,
)


@pytest.mark.parametrize(
    ("score", "schaal", "verwacht"),
    [
        (70, "0-100", GROEN),
        (69, "0-100", ORANJE),
        (50, "0-100", ORANJE),
        (49, "0-100", ROOD),
        (0, "0-100", ROOD),
        (100, "0-100", GROEN),
        (0.70, "0-1", GROEN),
        (0.69, "0-1", ORANJE),
        (0.50, "0-1", ORANJE),
        (0.49, "0-1", ROOD),
    ],
)
def test_bepaal_kleur(score, schaal, verwacht):
    assert bepaal_kleur(score, schaal=schaal) == verwacht


def test_bepaal_kleur_default_schaal_is_0_100():
    assert bepaal_kleur(70) == GROEN
    assert bepaal_kleur(0.7) == ROOD  # 0.7 / 100 = 0.007 → ROOD bij default schaal


def test_render_progress_bar_0_100():
    html = render_progress_bar(72.4, GROEN)
    assert 'class="progress-bar-bg"' in html
    assert 'class="progress-bar-fill"' in html
    assert "width:72%" in html
    assert f"background:{GROEN}" in html


def test_render_progress_bar_0_1():
    html = render_progress_bar(0.724, ORANJE, schaal="0-1")
    assert "width:72%" in html
    assert f"background:{ORANJE}" in html
