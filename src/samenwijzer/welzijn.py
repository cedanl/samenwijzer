"""Welzijnsmodule: AI-reactie op student self-assessment."""

import logging
import smtplib
from collections.abc import Generator

from samenwijzer._ai import _client
from samenwijzer.outreach import email_config_uit_env, verstuur_email

log = logging.getLogger(__name__)

_MODEL = "claude-sonnet-4-6"
_MAX_TOKENS = 512

CATEGORIEËN = ["studieplanning", "welzijn", "financiën", "werkplekleren", "overig"]

_CATEGORIE_LABEL: dict[str, str] = {
    "studieplanning": "Studieplanning & opdrachten",
    "welzijn": "Persoonlijk welzijn",
    "financiën": "Financiën",
    "werkplekleren": "Stage & werkplekleren",
    "overig": "Iets anders",
}

_URGENTIE_LABEL: dict[int, str] = {
    1: "Kan wachten",
    2: "Liefst snel",
    3: "Dringend",
}


def categorie_label(categorie: str) -> str:
    """Geef het leesbare label voor een hulpcategorie."""
    return _CATEGORIE_LABEL.get(categorie, categorie)


def urgentie_label(urgentie: int) -> str:
    """Geef het leesbare label voor een urgentieniveau (1–3)."""
    return _URGENTIE_LABEL.get(urgentie, str(urgentie))


def genereer_welzijnsreactie(
    voornaam: str,
    categorie: str,
    toelichting: str,
    urgentie: int,
    *,
    api_key: str | None = None,
) -> Generator[str]:
    """Stream een korte, bemoedigende reactie op een welzijnscheck.

    Args:
        voornaam: Voornaam van de student.
        categorie: Hulpcategorie (bijv. 'welzijn', 'studieplanning').
        toelichting: Optionele tekst die de student heeft toegevoegd.
        urgentie: 1 (kan wachten), 2 (liefst snel), 3 (dringend).

    Yields:
        Tekstfragmenten van de AI-reactie.
    """
    urgentie_tekst = _URGENTIE_LABEL.get(urgentie, "")
    toelichting_deel = f"\nDe student schrijft: '{toelichting}'" if toelichting.strip() else ""

    prompt = (
        f"Je bent een empathische digitale assistent voor MBO-studenten. "
        f"Een student genaamd {voornaam} heeft een welzijnscheck ingevuld.\n\n"
        f"Categorie: {_CATEGORIE_LABEL.get(categorie, categorie)}\n"
        f"Urgentie: {urgentie_tekst}{toelichting_deel}\n\n"
        f"Schrijf een korte (max. 80 woorden), warme reactie die:\n"
        f"1. De student erkent en valideert ('Goed dat je dit aangeeft…')\n"
        f"2. Aanmoedigt om hulp te zoeken bij de mentor of begeleider\n"
        f"3. Eindigt met een positieve noot\n"
        f"Spreek de student aan met '{voornaam}'. Geen opsomming — gewone zinnen."
    )

    with _client(api_key).messages.stream(
        model=_MODEL,
        max_tokens=_MAX_TOKENS,
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        yield from stream.text_stream


def stuur_welzijn_notificatie(
    student_naam: str,
    mentor_naam: str,
    categorie: str,
    urgentie: int,
    toelichting: str,
    timestamp: str,
) -> bool:
    """Stuur een e-mailnotificatie aan de mentor over een nieuwe welzijnscheck.

    Verstuurt alleen als SMTP én WELZIJN_NOTIFICATIE_EMAIL geconfigureerd zijn.
    Bij ontbrekende configuratie of SMTP-fout wordt stilzwijgend False teruggegeven.

    Args:
        student_naam: Volledige naam van de student.
        mentor_naam: Naam van de toegewezen mentor.
        categorie: Hulpcategorie van de check.
        urgentie: Urgentieniveau 1–3.
        toelichting: Optionele tekst van de student.
        timestamp: ISO-timestamp van de check.

    Returns:
        True als het e-mailbericht succesvol verstuurd is, anders False.
    """
    smtp = email_config_uit_env()
    notificatie_email = smtp["welzijn_notificatie_email"]
    smtp_klaar = all(smtp[k] for k in ("smtp_host", "smtp_user", "smtp_password"))

    if not (notificatie_email and smtp_klaar):
        return False

    urgentie_tekst = _URGENTIE_LABEL.get(urgentie, str(urgentie))
    categorie_tekst = _CATEGORIE_LABEL.get(categorie, categorie)
    datum = timestamp[:10]

    bericht_regels = [
        f"Een student heeft een welzijnscheck ingediend op {datum}.",
        "",
        f"Student:   {student_naam}",
        f"Mentor:    {mentor_naam}",
        f"Categorie: {categorie_tekst}",
        f"Urgentie:  {urgentie_tekst}",
    ]
    if toelichting.strip():
        bericht_regels += ["", "Toelichting van de student:", f"  {toelichting.strip()}"]
    bericht_regels += [
        "",
        "Log in op Samenwijzer om de check te bekijken en actie te ondernemen.",
    ]

    onderwerp = f"Welzijnscheck {student_naam} — {urgentie_tekst}"
    if urgentie == 3:
        onderwerp = f"⚠️ DRINGEND: {onderwerp}"

    try:
        verstuur_email(
            ontvanger_email=notificatie_email,
            onderwerp=onderwerp,
            bericht="\n".join(bericht_regels),
            smtp_host=smtp["smtp_host"],
            smtp_port=smtp["smtp_port"],
            smtp_user=smtp["smtp_user"],
            smtp_password=smtp["smtp_password"],
            afzender_email=smtp["afzender_email"],
        )
    except smtplib.SMTPException:
        log.exception("Welzijnsnotificatie niet verstuurd naar %s", notificatie_email)
        return False

    return True
