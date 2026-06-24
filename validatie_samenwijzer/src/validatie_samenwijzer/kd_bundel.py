"""KD-bundelmanifest: detecteer of de lokale SBB-bundel is gewijzigd of verouderd.

De kwalificatiedossiers komen uit een handmatig gedownloade s-bb-bundle (4 zips +
crebolijsten). Er was geen registratie van *welke* bundel we hebben, dus een verse
bundel werd niet als wijziging gezien. Dit module schrijft een manifest met de SHA256
per zip + het nieuwste crebolijst-jaar, en vergelijkt de live bundel daartegen.

Geen netwerk: alles werkt op de lokale (Box-gesyncte) bestanden. Een echte 'heeft SBB
een nieuwer jaar?'-check (upstream HEAD) is bewust buiten scope — het manifest surfaced
het crebolijst-jaar dat we hebben zodat een mens dat tegen s-bb.nl kan houden.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from datetime import UTC, datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# kwalificatiedossiers/ leeft in de repo-root (buiten het subproject); spiegelt
# sync_afgeleid._REPO_ROOT.
_KWAL_DIR = Path(__file__).resolve().parents[3] / "kwalificatiedossiers"
_MANIFEST_NAAM = "bundle_manifest.json"
_SBB_ZIPS = ("ae.zip", "fl.zip", "mr.zip", "sz.zip")
_JAAR_RE = re.compile(r"crebo_(\d{4})")


def _sha256(pad: Path) -> str:
    h = hashlib.sha256()
    with pad.open("rb") as f:
        for blok in iter(lambda: f.read(1 << 20), b""):
            h.update(blok)
    return h.hexdigest()


def huidige_zip_hashes(kwal_dir: Path = _KWAL_DIR) -> dict[str, str]:
    """SHA256 per aanwezige SBB-zip (ontbrekende zips worden overgeslagen)."""
    return {naam: _sha256(kwal_dir / naam) for naam in _SBB_ZIPS if (kwal_dir / naam).exists()}


def nieuwste_crebolijst_jaar(kwal_dir: Path = _KWAL_DIR) -> int | None:
    """Hoogste jaartal uit lijsten/crebo_<jaar>*.xlsx, of None als er geen zijn."""
    lijsten = kwal_dir / "lijsten"
    if not lijsten.exists():
        return None
    jaren = [int(m.group(1)) for p in lijsten.glob("crebo_*.xlsx") if (m := _JAAR_RE.match(p.name))]
    return max(jaren) if jaren else None


def schrijf_manifest(kwal_dir: Path = _KWAL_DIR, *, nu: str | None = None) -> dict:
    """Registreer de huidige bundel (zip-hashes + crebolijst-jaar) in het manifest."""
    manifest = {
        "crebolijst_jaar": nieuwste_crebolijst_jaar(kwal_dir),
        "zips": huidige_zip_hashes(kwal_dir),
        "gegenereerd_op": nu or datetime.now(UTC).isoformat(timespec="seconds"),
    }
    (kwal_dir / _MANIFEST_NAAM).write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return manifest


def lees_manifest(kwal_dir: Path = _KWAL_DIR) -> dict | None:
    pad = kwal_dir / _MANIFEST_NAAM
    if not pad.exists():
        return None
    try:
        return json.loads(pad.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def bundel_status(kwal_dir: Path = _KWAL_DIR) -> dict:
    """Vergelijk de live bundel met het manifest.

    toestand: 'geen_manifest' | 'gewijzigd' | 'in_sync'. Bij 'gewijzigd' bevat
    gewijzigde_zips de zips met een afwijkende hash (of toegevoegd/verdwenen).
    """
    jaar = nieuwste_crebolijst_jaar(kwal_dir)
    manifest = lees_manifest(kwal_dir)
    if manifest is None:
        return {"toestand": "geen_manifest", "crebolijst_jaar": jaar, "gewijzigde_zips": []}
    live = huidige_zip_hashes(kwal_dir)
    vorig = manifest.get("zips", {})
    gewijzigd = sorted(n for n in set(live) | set(vorig) if live.get(n) != vorig.get(n))
    return {
        "toestand": "gewijzigd" if gewijzigd else "in_sync",
        "crebolijst_jaar": jaar,
        "gewijzigde_zips": gewijzigd,
    }


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    m = schrijf_manifest()
    logger.info(
        "Manifest geschreven: crebolijst %s, %d zips.", m["crebolijst_jaar"], len(m["zips"])
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
