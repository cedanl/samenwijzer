"""Gedeelde test-helpers voor samenwijzer."""

from collections.abc import Generator
from unittest.mock import MagicMock

import numpy as np
import pandas as pd

from samenwijzer.transform import transform_student_data


def mock_stream(tekst: str) -> MagicMock:
    """Bouw een mock-stream die tekst als één fragment yieldt."""
    mock = MagicMock()
    mock.__enter__ = MagicMock(return_value=mock)
    mock.__exit__ = MagicMock(return_value=False)
    mock.text_stream = iter([tekst])
    return mock


def mock_stream_fragmenten(fragmenten: list[str]) -> MagicMock:
    """Mock-stream die meerdere tekstfragmenten yieldt."""
    mock = MagicMock()
    mock.__enter__ = MagicMock(return_value=mock)
    mock.__exit__ = MagicMock(return_value=False)
    mock.text_stream = iter(fragmenten)
    return mock


def mock_stream_met_fout(fragmenten: list[str], fout: Exception) -> MagicMock:
    """Mock-stream die fragmenten yieldt en daarna een uitzondering gooit."""

    def _gen() -> Generator[str]:
        yield from fragmenten
        raise fout

    mock = MagicMock()
    mock.__enter__ = MagicMock(return_value=mock)
    mock.__exit__ = MagicMock(return_value=False)
    mock.text_stream = _gen()
    return mock


def maak_grote_df(n: int = 1000) -> pd.DataFrame:
    """Genereer een getransformeerd DataFrame met n studenten voor schaaltests."""
    rng = np.random.default_rng(42)
    opleidingen = ["Verzorgende IG", "ICT-beheerder", "Medewerker marketing"]
    raw = pd.DataFrame(
        {
            "studentnummer": [f"S{i:04d}" for i in range(n)],
            "naam": [f"Student {i}" for i in range(n)],
            "mentor": [f"Mentor {i % 10}" for i in range(n)],
            "opleiding": [opleidingen[i % 3] for i in range(n)],
            "crebo": ["25491"] * n,
            "niveau": pd.array(rng.integers(2, 5, size=n), dtype="Int64"),
            "leerweg": ["BOL" if i % 3 != 0 else "BBL" for i in range(n)],
            "cohort": ["2024-2025"] * n,
            "leeftijd": pd.array(rng.integers(17, 25, size=n), dtype="Int64"),
            "geslacht": ["V" if i % 2 == 0 else "M" for i in range(n)],
            "bsa_behaald": rng.uniform(0, 60, size=n).tolist(),
            "bsa_vereist": [60.0] * n,
            "voortgang": rng.uniform(0, 1, size=n).tolist(),
            "kt1_begeleiden": rng.uniform(0, 100, size=n).tolist(),
            "wp1_1_intake": rng.uniform(0, 100, size=n).tolist(),
        }
    )
    return transform_student_data(raw)
