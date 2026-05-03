"""Converteer alle OER-PDFs naar Markdown via markitdown.

Gebruik:
    uv run python scripts/convert_oers_markdown.py
    uv run python scripts/convert_oers_markdown.py --preview      # droge run
    uv run python scripts/convert_oers_markdown.py --herconverteer  # overschrijf bestaande .md
    uv run python scripts/convert_oers_markdown.py --oeren-pad /pad/naar/oeren
"""

import argparse
import logging
import sys
import time
from pathlib import Path

logging.getLogger("pdfminer").setLevel(logging.ERROR)


def _formatteer_tijd(seconden: float) -> str:
    if seconden < 60:
        return f"{seconden:.0f}s"
    m, s = divmod(int(seconden), 60)
    return f"{m}m{s:02d}s"


def main() -> None:
    parser = argparse.ArgumentParser(description="Converteer OER-PDFs naar Markdown")
    parser.add_argument("--oeren-pad", default="oeren", help="Pad naar de oeren-map")
    parser.add_argument("--preview", action="store_true", help="Droge run — geen bestanden schrijven")
    parser.add_argument("--herconverteer", action="store_true", help="Overschrijf bestaande .md-bestanden")
    args = parser.parse_args()

    oeren_pad = Path(args.oeren_pad)
    if not oeren_pad.exists():
        print(f"Map niet gevonden: {oeren_pad}", file=sys.stderr)
        sys.exit(1)

    pdfs = sorted(oeren_pad.rglob("*.pdf"))
    totaal = len(pdfs)
    print(f"{totaal} PDF-bestanden gevonden in {oeren_pad}\n")

    if not totaal:
        print("Niets te doen.")
        return

    from markitdown import MarkItDown
    md_converter = MarkItDown()

    geconverteerd = overgeslagen = mislukt = 0
    start = time.monotonic()

    for i, pdf in enumerate(pdfs, start=1):
        md_pad = pdf.with_suffix(".md")
        prefix = f"[{i:>{len(str(totaal))}}/{totaal}]"

        if md_pad.exists() and not args.herconverteer:
            overgeslagen += 1
            # Stille skip — toon alleen als bijna klaar of elke 25 bestanden
            if i % 25 == 0 or i == totaal:
                verstreken = time.monotonic() - start
                print(f"{prefix} ... {overgeslagen} overgeslagen, {geconverteerd} geconverteerd "
                      f"({_formatteer_tijd(verstreken)} verstreken)", flush=True)
            continue

        if args.preview:
            print(f"{prefix} [preview] {pdf.name}", flush=True)
            geconverteerd += 1
            continue

        t0 = time.monotonic()
        try:
            print(f"{prefix} Converteren: {pdf.name} ...", end=" ", flush=True)
            resultaat = md_converter.convert(str(pdf))
            md_pad.write_text(resultaat.text_content, encoding="utf-8")
            duur = time.monotonic() - t0
            kb = md_pad.stat().st_size // 1024
            print(f"OK ({kb} KB, {duur:.1f}s)", flush=True)
            geconverteerd += 1
        except Exception as e:
            print(f"FOUT", flush=True)
            print(f"       {e}", file=sys.stderr, flush=True)
            mislukt += 1

    verstreken = time.monotonic() - start
    print(f"\nKlaar in {_formatteer_tijd(verstreken)} — "
          f"geconverteerd: {geconverteerd}, overgeslagen: {overgeslagen}, mislukt: {mislukt}")


if __name__ == "__main__":
    main()
