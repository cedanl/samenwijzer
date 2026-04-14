"""Wekelijkse verzending van WhatsApp check-ins.

Wordt aangeroepen vanuit de GitHub Actions cron-job (elke maandag 08:00).
Bij DRY_RUN=true worden berichten gelogd maar niet verstuurd.

Gebruik:
    uv run python -m samenwijzer.scheduler
"""

import logging
import os
import sys
from pathlib import Path

import pandas as pd

from samenwijzer.whatsapp import stuur_checkin
from samenwijzer.whatsapp_store import get_actieve_registraties

log = logging.getLogger(__name__)


def stuur_wekelijkse_checkins(df_studenten: pd.DataFrame, dry_run: bool = False) -> dict:
    """Stuur wekelijkse check-ins naar alle studenten met actieve opt-in.

    Args:
        df_studenten: Getransformeerd studenten-DataFrame met kolommen 'studentnummer' en 'naam'.
        dry_run: Wanneer True worden berichten gelogd maar niet verstuurd.

    Returns:
        Dict met 'verstuurd', 'overgeslagen' en 'fouten' tellers.
    """
    registraties = get_actieve_registraties()
    if not registraties:
        log.info("Geen actieve registraties gevonden — niets te versturen.")
        return {"verstuurd": 0, "overgeslagen": 0, "fouten": 0}

    snr_naar_naam: dict[str, str] = dict(
        zip(df_studenten["studentnummer"].astype(str), df_studenten["naam"])
    )

    verstuurd = overgeslagen = fouten = 0

    for studentnummer, telefoonnummer in registraties:
        naam = snr_naar_naam.get(studentnummer)
        if not naam:
            log.warning("Student %s niet gevonden in dataset — overgeslagen.", studentnummer)
            overgeslagen += 1
            continue

        if dry_run:
            log.info("[DRY RUN] Check-in voor %s (%s) → %s", naam, studentnummer, telefoonnummer)
            verstuurd += 1
            continue

        try:
            stuur_checkin(naam=naam, telefoonnummer=telefoonnummer)
            log.info("Check-in verstuurd naar %s (%s)", naam, studentnummer)
            verstuurd += 1
        except Exception:
            log.exception("Fout bij versturen naar %s (%s)", naam, studentnummer)
            fouten += 1

    log.info(
        "Verzending afgerond — verstuurd: %d, overgeslagen: %d, fouten: %d",
        verstuurd, overgeslagen, fouten,
    )
    return {"verstuurd": verstuurd, "overgeslagen": overgeslagen, "fouten": fouten}


def _main() -> None:
    """CLI-entrypoint voor GitHub Actions."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent.parent / ".env")

    from samenwijzer.prepare import load_berend_csv
    from samenwijzer.transform import transform_student_data

    dry_run = os.getenv("DRY_RUN", "false").lower() == "true"
    csv_pad = Path(__file__).parent.parent.parent / "data" / "01-raw" / "berend" / "studenten.csv"

    if not csv_pad.exists():
        log.error("Studentendata niet gevonden op %s", csv_pad)
        sys.exit(1)

    df = transform_student_data(load_berend_csv(csv_pad))
    resultaat = stuur_wekelijkse_checkins(df, dry_run=dry_run)

    if resultaat["fouten"] > 0:
        sys.exit(1)


if __name__ == "__main__":
    _main()
