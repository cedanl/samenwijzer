"""Bouw data/opleidingsnamen.json: crebo → nette kwalificatie-naam.

Bronnen (prioriteit): crebolijst.xlsx kolom 'Kwalificatie' (specifiek per crebo) →
mapping.json crebo_naar_dossier (brede dossier-naam). Crebo's zonder treffer worden
weggelaten; de runtime-resolver valt dan terug op schoon_opleiding_naam(). De bronnen
leven in de parent-repo (build-context = repo-root).

Draai vanuit validatie_samenwijzer/:
    uv run python scripts/build_opleidingsnamen.py
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import openpyxl

KD_PAD = Path(os.environ.get("KD_PAD", "../kwalificatiedossiers"))
UIT = Path(os.environ.get("OPLEIDINGSNAMEN_PAD", "data/opleidingsnamen.json"))


def _crebolijst_namen(xlsx: Path) -> dict[str, str]:
    wb = openpyxl.load_workbook(xlsx, read_only=True)
    rijen = list(wb.active.iter_rows(values_only=True))
    kop = next(
        i for i, r in enumerate(rijen) if r and "Opleidingscode" in r and "Kwalificatie" in r
    )
    kol = {v: j for j, v in enumerate(rijen[kop]) if v}
    ci, ck = kol["Opleidingscode"], kol["Kwalificatie"]
    out: dict[str, str] = {}
    for r in rijen[kop + 1 :]:
        code = str(r[ci]).strip() if r[ci] is not None else ""
        if not code.isdigit():  # sla titel-/herhaalde kop-rijen en lege regels over
            continue
        naam = (r[ck] or "").replace("\xa0", " ").strip()
        if naam:
            out[code] = naam
    return out


def _mapping_namen(pad: Path) -> dict[str, str]:
    data = json.loads(pad.read_text(encoding="utf-8"))
    return {
        str(k).strip(): str(v).replace("\xa0", " ").strip()
        for k, v in data.get("crebo_naar_dossier", {}).items()
        if v and str(k).strip().isdigit()
    }


def bouw() -> dict[str, str]:
    """crebolijst (specifiek) wint van mapping.json (breed)."""
    namen = _mapping_namen(KD_PAD / "mapping.json")
    namen.update(_crebolijst_namen(KD_PAD / "crebolijst.xlsx"))
    return dict(sorted(namen.items()))


if __name__ == "__main__":
    namen = bouw()
    UIT.write_text(json.dumps(namen, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{len(namen)} crebo-namen geschreven naar {UIT}")
