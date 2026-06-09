"""Converteer alle kwalificatiedossier-PDFs naar Markdown via markitdown.

Schrijft `<stem>.md` naast iedere `<stem>.pdf` (zelfde patroon als OER-pipeline).
Slaat bestaande .md-bestanden over zodat herstart idempotent is.
"""

from __future__ import annotations

import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PDF_DIR = ROOT / "kwalificatiedossiers" / "pdfs"


def converteer(pdf_pad: Path) -> tuple[Path, str]:
    """Converteer één PDF; return (pad, status). Wordt in worker-proces uitgevoerd."""

    md_pad = pdf_pad.with_suffix(".md")
    if md_pad.exists() and md_pad.stat().st_size > 100:
        return pdf_pad, "skip"
    try:
        from markitdown import MarkItDown

        resultaat = MarkItDown().convert(str(pdf_pad))
        md_pad.write_text(resultaat.text_content, encoding="utf-8")
        return pdf_pad, f"ok ({md_pad.stat().st_size} B)"
    except Exception as exc:
        return pdf_pad, f"FAIL: {exc}"


def main() -> int:
    pdfs = sorted(PDF_DIR.glob("*.pdf"))
    if not pdfs:
        print(f"Geen PDFs in {PDF_DIR}")
        return 1
    print(f"Te converteren: {len(pdfs)} PDFs")
    start = time.time()
    failures: list[tuple[Path, str]] = []
    voltooid = 0
    with ProcessPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(converteer, p): p for p in pdfs}
        for fut in as_completed(futures):
            pad, status = fut.result()
            voltooid += 1
            if status.startswith("FAIL"):
                failures.append((pad, status))
                print(f"  [{voltooid}/{len(pdfs)}] FAIL {pad.name}: {status}")
            elif voltooid % 20 == 0:
                elapsed = time.time() - start
                tempo = voltooid / elapsed
                print(f"  [{voltooid}/{len(pdfs)}] {status}  (~{tempo:.1f}/s)")
    print(f"\nKlaar in {time.time() - start:.0f}s. Failures: {len(failures)}")
    for pad, status in failures:
        print(f"  {pad.name}: {status}")
    return 0 if not failures else 2


if __name__ == "__main__":
    sys.exit(main())
