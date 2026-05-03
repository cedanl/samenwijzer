"""OER-bestandswatcher: herindexeer automatisch als OER-bestanden wijzigen."""

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


def _ingesteer(pad: Path) -> None:
    """Roep de ingest CLI aan voor één bestand met --reset (vervangt bestaande chunks)."""
    log.info("Herindexeren: '%s'...", pad.name)
    result = subprocess.run(
        [sys.executable, "-m", "validatie_samenwijzer.ingest", "--bestand", str(pad), "--reset"],
    )
    if result.returncode == 0:
        log.info("Herindexering geslaagd: '%s'", pad.name)
    else:
        log.error("Herindexering mislukt voor '%s' (exit %d)", pad.name, result.returncode)


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
            for pad in handler.verwerk_wachtrij():
                _ingesteer(pad)
    except KeyboardInterrupt:
        log.info("Watcher gestopt.")
    finally:
        observer.stop()
        observer.join()


if __name__ == "__main__":
    main()
