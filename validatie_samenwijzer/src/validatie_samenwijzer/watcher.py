"""OER-bestandswatcher: herindexeer + reconcilieer afgeleide bronnen bij wijzigingen.

Bij een wijziging in de OER-map wordt het bestand opnieuw geïngest en daarna worden de
afgeleide bronnen (kwalificatiedossier + skills) voor de betrokken crebo bijgewerkt via
``sync_afgeleid``. Dit is een latency-optimalisatie op een always-on machine; de
bootstrap/periodieke ``--alles`` blijft de bron van waarheid (zie het auto-sync-plan).

Twee bewuste grenzen:
- De reconciliatie draait **inline** in de event-loop; tijdens een grote reconcile wachten
  nieuwe events in de debounce-wachtrij (niet lossy, wél serieel). Bij een bulk-drop van veel
  verschillende crebo's kan dat minuten serieel werk zijn — gebruik dan liever ``bootstrap
  --alles`` (de echte bulk-route).
- Alleen bestanden met een crebo in de **naam** worden gereconcilieerd. Een hernoeming
  (``rename_oers.py``) is een move-event met de nieuwe naam, dus die wordt gedekt; een rauwe
  pre-rename Aeres/Utrecht-drop wordt wél geïngest maar krijgt zijn KD/skills pas via ``--alles``.
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from . import ingest
from .sync_afgeleid import werk_afgeleide_bronnen_bij

load_dotenv()

log = logging.getLogger(__name__)

_DEBOUNCE_SECONDEN = 5.0
_ONDERSTEUNDE_EXTENSIES = {".pdf", ".html", ".htm", ".md", ".txt"}


class _OerHandler(FileSystemEventHandler):
    """Registreert gewijzigde OER-bestanden en levert ze na de debounce-periode."""

    def __init__(self) -> None:
        self._wachtrij: dict[str, float] = {}

    def on_created(self, event: FileSystemEvent) -> None:
        self._registreer(event)

    def on_modified(self, event: FileSystemEvent) -> None:
        self._registreer(event)

    def on_moved(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            self._registreer_pad(Path(event.dest_path))

    def _registreer(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            self._registreer_pad(Path(event.src_path))

    def _registreer_pad(self, pad: Path) -> None:
        if pad.suffix.lower() in _ONDERSTEUNDE_EXTENSIES:
            self._wachtrij[str(pad)] = time.monotonic()

    def verwerk_wachtrij(self) -> list[Path]:
        """Geeft bestanden terug waarvoor de debounce verstreken is en verwijdert ze."""
        nu = time.monotonic()
        klaar = [Path(p) for p, t in self._wachtrij.items() if nu - t >= _DEBOUNCE_SECONDEN]
        for pad in klaar:
            del self._wachtrij[str(pad)]
        return klaar


def _ingesteer(pad: Path) -> bool:
    """Roep de ingest CLI aan voor één bestand met --reset; geeft True bij succes."""
    log.info("Herindexeren: '%s'...", pad.name)
    result = subprocess.run(
        [sys.executable, "-m", "validatie_samenwijzer.ingest", "--bestand", str(pad), "--reset"],
    )
    if result.returncode == 0:
        log.info("Herindexering geslaagd: '%s'", pad.name)
        return True
    log.error("Herindexering mislukt voor '%s' (exit %d)", pad.name, result.returncode)
    return False


def _crebos_uit_paden(paden: list[Path]) -> set[str]:
    """Bepaal de unieke crebo's voor een batch OER-bestanden (uit de bestandsnaam).

    Gededupt zodat een bulk-drop van veel bestanden van dezelfde opleiding maar één
    reconciliatie per crebo triggert. Bestanden zonder crebo in de naam worden
    overgeslagen — die vangt de periodieke/bootstrap ``--alles`` op.
    """
    crebos: set[str] = set()
    for pad in paden:
        info = ingest.parseer_bestandsnaam(pad.name)
        if info and info.get("crebo"):
            crebos.add(info["crebo"])
    return crebos


def _reconcilieer_afgeleide_bronnen(crebos: set[str]) -> None:
    """Werk KD + skills bij voor de gewijzigde crebo's (latency-optimalisatie)."""
    for crebo in sorted(crebos):
        log.info("Afgeleide bronnen (KD + skills) bijwerken voor crebo %s...", crebo)
        try:
            werk_afgeleide_bronnen_bij(crebo=crebo)
        except Exception as e:  # noqa: BLE001 — de watcher moet blijven draaien
            log.error("Reconciliatie mislukt voor crebo %s: %s", crebo, e)


def main() -> None:
    """Start de OER-bestandswatcher en herindexeer automatisch bij wijzigingen."""
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    parser = argparse.ArgumentParser(description="OER-bestandswatcher")
    parser.add_argument(
        "--oeren-pad",
        default=os.environ.get("OEREN_PAD", "oeren"),
        help="Map met OER-bestanden (default: oeren of $OEREN_PAD)",
    )
    args = parser.parse_args()

    oeren_pad = Path(args.oeren_pad)
    if not oeren_pad.exists():
        log.error("OER-map niet gevonden: %s", oeren_pad.resolve())
        sys.exit(1)

    handler = _OerHandler()
    observer = Observer()
    observer.schedule(handler, str(oeren_pad), recursive=True)
    observer.start()

    log.info("Watcher gestart — bewaakt '%s' (recursief)", oeren_pad.resolve())
    log.info("Ondersteunde extensies: %s", ", ".join(sorted(_ONDERSTEUNDE_EXTENSIES)))
    log.info("Debounce: %.0f seconden — stop met Ctrl+C", _DEBOUNCE_SECONDEN)

    try:
        while True:
            time.sleep(1)
            geslaagd = [pad for pad in handler.verwerk_wachtrij() if _ingesteer(pad)]
            if geslaagd:
                _reconcilieer_afgeleide_bronnen(_crebos_uit_paden(geslaagd))
    except KeyboardInterrupt:
        log.info("Watcher gestopt.")
    finally:
        observer.stop()
        observer.join()


if __name__ == "__main__":
    main()
