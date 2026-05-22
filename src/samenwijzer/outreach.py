"""Outreach-module: risicodetectie, AI-berichtgeneratie en e-mailverzending."""

import smtplib
from collections.abc import Generator
from dataclasses import dataclass
from email.mime.text import MIMEText
from os import environ

import pandas as pd

from samenwijzer._ai import MODEL, _client
from samenwijzer.outreach_store import Interventie, StudentStatus

_MAX_TOKENS = 1024

_GECONTACTEERD_STATUSSEN = ("gecontacteerd", "gereageerd", "opgelost")
_GEREAGEERD_STATUSSEN = ("gereageerd", "opgelost")


def at_risk_studenten(df: pd.DataFrame) -> pd.DataFrame:
    """Selecteer studenten die outreach-aandacht verdienen.

    Criteria (OR):
    - risico-vlag gezet in de brondata
    - voortgang < 0.40 (minder dan 40 % van de stof behaald)
    - bsa_behaald < 0.75 * bsa_vereist (meer dan 25 % achter op BSA-norm)

    Returns:
        DataFrame met alleen de at-risk studenten, gesorteerd op voortgang oplopend.
    """
    masker = (
        df["risico"] | (df["voortgang"] < 0.40) | (df["bsa_behaald"] < 0.75 * df["bsa_vereist"])
    )
    return df[masker].sort_values("voortgang").reset_index(drop=True)


def interventie_log(interventies: list[Interventie]) -> pd.DataFrame:
    """Bouw een interventie-log-DataFrame uit ruwe Interventie-records (voor weergave)."""
    return pd.DataFrame(
        [
            {
                "datum": iv.timestamp[:10],
                "student": iv.studentnummer,
                "mentor": iv.mentor,
                "status_voor": iv.status_voor,
                "status_na": iv.status_na,
                "voortgang": iv.voortgang_op_moment,
                "bsa_pct": iv.bsa_percentage_op_moment,
            }
            for iv in interventies
        ]
    )


def interventies_per_mentor(log_df: pd.DataFrame) -> pd.DataFrame:
    """Tel interventies en unieke studenten per mentor, aflopend gesorteerd.

    Returns:
        DataFrame met kolommen: mentor, interventies, uniek_studenten.
    """
    return (
        log_df.groupby("mentor")
        .agg(interventies=("student", "count"), uniek_studenten=("student", "nunique"))
        .reset_index()
        .sort_values("interventies", ascending=False)
    )


@dataclass
class EffectiviteitMetrics:
    """Outreach-trechter en conversieratio's (percentages 0–100)."""

    totaal_at_risk: int
    gecontacteerd: int
    gereageerd: int
    opgelost: int
    contact_rate: float
    respons_rate: float
    oplossing_rate: float


def bereken_effectiviteit(
    statussen: list[StudentStatus], totaal_at_risk: int
) -> EffectiviteitMetrics:
    """Bereken de outreach-trechter en conversieratio's uit de huidige studentstatussen."""
    gecontacteerd = sum(1 for s in statussen if s.status in _GECONTACTEERD_STATUSSEN)
    gereageerd = sum(1 for s in statussen if s.status in _GEREAGEERD_STATUSSEN)
    opgelost = sum(1 for s in statussen if s.status == "opgelost")
    return EffectiviteitMetrics(
        totaal_at_risk=totaal_at_risk,
        gecontacteerd=gecontacteerd,
        gereageerd=gereageerd,
        opgelost=opgelost,
        contact_rate=gecontacteerd / totaal_at_risk * 100 if totaal_at_risk else 0.0,
        respons_rate=gereageerd / gecontacteerd * 100 if gecontacteerd else 0.0,
        oplossing_rate=opgelost / gereageerd * 100 if gereageerd else 0.0,
    )


def genereer_outreach_bericht(
    student: pd.Series,
    mentor_naam: str,
    toon: str = "vriendelijk",
    *,
    verwijzing: dict[str, str] | None = None,
    api_key: str | None = None,
) -> Generator[str]:
    """Stream een gepersonaliseerd outreach-bericht voor de gegeven student.

    Args:
        student: Rij uit het studenten-DataFrame.
        mentor_naam: Naam van de mentor die het bericht verstuurt.
        toon: Gewenste toon — "vriendelijk", "zakelijk" of "motiverend".

    Yields:
        Tekstfragmenten van het gegenereerde bericht.
    """
    voortgang_pct = int(student["voortgang"] * 100)
    bsa_achterstand = int(student["bsa_vereist"] - student["bsa_behaald"])
    bsa_tekst = (
        f"{bsa_achterstand} studiepunten achter op de BSA-norm"
        if bsa_achterstand > 0
        else "op schema voor BSA"
    )

    verwijzing_tekst = ""
    if verwijzing:
        verwijzing_tekst = (
            f"\n- Verwijs de student naar: {verwijzing['rol']} ({verwijzing['toelichting']})"
        )

    prompt = (
        f"Je bent mentor {mentor_naam}. Schrijf een {toon} e-mailbericht aan een MBO-student "
        f"die extra ondersteuning nodig heeft.\n\n"
        f"Gegevens van de student:\n"
        f"- Naam: {student['naam']}\n"
        f"- Opleiding: {student['opleiding']}, niveau {student['niveau']}\n"
        f"- Studievoortgang: {voortgang_pct}%\n"
        f"- BSA-status: {bsa_tekst}\n\n"
        f"Richtlijnen:\n"
        f"- Begin met een persoonlijke aanhef (Beste {student['naam'].split()[0]},)\n"
        f"- Benoem concreet wat je ziet in de cijfers, zonder beschuldigend te zijn\n"
        f"- Bied aan om een afspraak te maken{verwijzing_tekst}\n"
        f"- Sluit af met je naam ({mentor_naam}) en de aansporing contact op te nemen\n"
        f"- Maximaal 150 woorden\n"
        f"- Geen subject-regel, alleen de berichttekst"
    )

    with _client(api_key).messages.stream(
        model=MODEL,
        max_tokens=_MAX_TOKENS,
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        yield from stream.text_stream


_VERWIJZINGEN: dict[str, dict[str, str]] = {
    "studieplanning": {
        "rol": "Studieloopbaanbegeleider (SLB-er)",
        "toelichting": "Helpt bij plannen, structuur en studieopdrachten.",
    },
    "welzijn": {
        "rol": "Studentendecaan / vertrouwenspersoon",
        "toelichting": "Voor persoonlijke problemen, stress of psychische klachten.",
    },
    "financiën": {
        "rol": "Financieel spreekuur",
        "toelichting": "Advies over studiefinanciering, toeslagen en schuldhulp.",
    },
    "werkplekleren": {
        "rol": "Praktijkbegeleider",
        "toelichting": "Begeleidt bij stage-uitdagingen en werkgerelateerde problemen.",
    },
    "overig": {
        "rol": "Mentor / SLB-er",
        "toelichting": "Bespreek de situatie en bekijk samen welke stap het best past.",
    },
}


def suggereer_verwijzing(categorie: str) -> dict[str, str]:
    """Geef een passende verwijzing op basis van de hulpcategorie.

    Args:
        categorie: Een van 'studieplanning', 'welzijn', 'financiën',
                   'werkplekleren' of 'overig'.

    Returns:
        Dict met 'rol' en 'toelichting'.
    """
    return _VERWIJZINGEN.get(categorie, _VERWIJZINGEN["overig"])


def email_config_uit_env() -> dict[str, str]:
    """Lees SMTP-configuratie uit omgevingsvariabelen.

    Verwacht: SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_AFZENDER.

    Returns:
        Dict met de SMTP-instellingen (lege strings als variabele ontbreekt).
    """
    return {
        "smtp_host": environ.get("SMTP_HOST", ""),
        "smtp_port": environ.get("SMTP_PORT", "587"),
        "smtp_user": environ.get("SMTP_USER", ""),
        "smtp_password": environ.get("SMTP_PASSWORD", ""),
        "afzender_email": environ.get("SMTP_AFZENDER", ""),
        "welzijn_notificatie_email": environ.get("WELZIJN_NOTIFICATIE_EMAIL", ""),
    }


def verstuur_email(
    ontvanger_email: str,
    onderwerp: str,
    bericht: str,
    *,
    smtp_host: str,
    smtp_port: int | str = 587,
    smtp_user: str,
    smtp_password: str,
    afzender_email: str,
) -> None:
    """Verstuur een e-mail via SMTP (STARTTLS).

    Args:
        ontvanger_email: E-mailadres van de ontvanger.
        onderwerp: Onderwerpregel.
        bericht: Platte tekst van het bericht.

    Raises:
        smtplib.SMTPException: Bij verbindings- of authenticatieproblemen.
    """
    msg = MIMEText(bericht, "plain", "utf-8")
    msg["Subject"] = onderwerp
    msg["From"] = afzender_email
    msg["To"] = ontvanger_email

    with smtplib.SMTP(smtp_host, int(smtp_port)) as server:
        server.starttls()
        server.login(smtp_user, smtp_password)
        server.sendmail(afzender_email, [ontvanger_email], msg.as_string())
