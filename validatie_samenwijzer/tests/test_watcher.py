"""Tests voor de OER-bestandswatcher."""

import time
from pathlib import Path
from unittest.mock import MagicMock

from validatie_samenwijzer.watcher import _DEBOUNCE_SECONDEN, _OerHandler


def test_wachtrij_leeg_voor_debounce():
    handler = _OerHandler()
    handler._registreer_pad(Path("oeren/talland_oeren/25908BOL2025.pdf"))
    assert handler.verwerk_wachtrij() == []


def test_wachtrij_gevuld_na_debounce():
    handler = _OerHandler()
    pad = Path("oeren/talland_oeren/25908BOL2025.pdf")
    handler._registreer_pad(pad)
    handler._wachtrij[str(pad)] -= _DEBOUNCE_SECONDEN + 0.1
    klaar = handler.verwerk_wachtrij()
    assert klaar == [pad]


def test_wachtrij_leeg_na_verwerken():
    handler = _OerHandler()
    pad = Path("oeren/talland_oeren/25908BOL2025.pdf")
    handler._registreer_pad(pad)
    handler._wachtrij[str(pad)] -= _DEBOUNCE_SECONDEN + 0.1
    handler.verwerk_wachtrij()
    assert handler.verwerk_wachtrij() == []


def test_niet_ondersteunde_extensie_genegeerd():
    handler = _OerHandler()
    handler._registreer_pad(Path("oeren/talland_oeren/readme.docx"))
    assert handler._wachtrij == {}


def test_on_created_registreert_bestand():
    handler = _OerHandler()
    event = MagicMock()
    event.is_directory = False
    event.src_path = "oeren/talland_oeren/25908BOL2025.pdf"
    handler.on_created(event)
    assert "oeren/talland_oeren/25908BOL2025.pdf" in handler._wachtrij


def test_on_moved_registreert_doelpad():
    handler = _OerHandler()
    event = MagicMock()
    event.is_directory = False
    event.src_path = "oeren/talland_oeren/oud.pdf"
    event.dest_path = "oeren/talland_oeren/25908BOL2025.pdf"
    handler.on_moved(event)
    assert "oeren/talland_oeren/25908BOL2025.pdf" in handler._wachtrij
    assert "oeren/talland_oeren/oud.pdf" not in handler._wachtrij


def test_dubbele_event_verlengt_debounce():
    handler = _OerHandler()
    pad = Path("oeren/talland_oeren/25908BOL2025.pdf")
    handler._registreer_pad(pad)
    handler._wachtrij[str(pad)] -= _DEBOUNCE_SECONDEN + 0.1
    handler._registreer_pad(pad)
    assert handler.verwerk_wachtrij() == []
