"""Tests voor de OER-bestandswatcher."""

from pathlib import Path
from unittest.mock import MagicMock

from validatie_samenwijzer import watcher
from validatie_samenwijzer.watcher import (
    _DEBOUNCE_SECONDEN,
    _crebos_uit_paden,
    _OerHandler,
    _reconcilieer_afgeleide_bronnen,
)


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


# ── Fase 2: reconciliatie-hook ────────────────────────────────────────────────


def test_crebos_uit_paden_dedupt(monkeypatch):
    """Meerdere bestanden van dezelfde crebo → één crebo (dedup)."""
    monkeypatch.setattr(
        watcher.ingest,
        "parseer_bestandsnaam",
        lambda naam: {"crebo": "25180"} if "kok" in naam.lower() else {"crebo": "25655"},
    )
    crebos = _crebos_uit_paden([Path("a_kok.pdf"), Path("b_kok.pdf"), Path("c_vpk.pdf")])
    assert crebos == {"25180", "25655"}


def test_crebos_uit_paden_skipt_zonder_crebo(monkeypatch):
    """Bestanden zonder crebo in de naam worden overgeslagen (--alles vangt ze op)."""
    monkeypatch.setattr(watcher.ingest, "parseer_bestandsnaam", lambda naam: None)
    assert _crebos_uit_paden([Path("rommel.pdf")]) == set()


def test_reconcilieer_roept_per_crebo(monkeypatch):
    aangeroepen = []
    monkeypatch.setattr(
        watcher, "werk_afgeleide_bronnen_bij", lambda crebo: aangeroepen.append(crebo)
    )
    _reconcilieer_afgeleide_bronnen({"25655", "25180"})
    assert sorted(aangeroepen) == ["25180", "25655"]


def test_reconcilieer_blijft_draaien_bij_fout(monkeypatch):
    """Een fout bij één crebo mag de watcher niet laten crashen of de rest blokkeren."""
    verwerkt = []

    def soms_stuk(crebo):
        if crebo == "25180":
            raise RuntimeError("boem")
        verwerkt.append(crebo)

    monkeypatch.setattr(watcher, "werk_afgeleide_bronnen_bij", soms_stuk)
    _reconcilieer_afgeleide_bronnen({"25180", "25655"})  # mag niet raisen
    assert verwerkt == ["25655"]
