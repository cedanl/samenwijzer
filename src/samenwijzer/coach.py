"""AI Leercoach: gepersonaliseerd lesmateriaal, oefentoets, werkfeedback en rollenspel."""

from collections.abc import Generator
from dataclasses import dataclass, field
from os import environ

import anthropic

_MODEL = "claude-sonnet-4-6"
_MAX_TOKENS = 2048


def _client(api_key: str | None = None) -> anthropic.Anthropic:
    """Maak een Anthropic-client aan met de opgegeven of omgevings-API-sleutel."""
    return anthropic.Anthropic(api_key=api_key or environ.get("ANTHROPIC_API_KEY"))


def genereer_lesmateriaal(
    onderwerp: str,
    opleiding: str,
    leerpad: str,
    zwakste_kt: str = "",
    *,
    api_key: str | None = None,
) -> Generator[str]:
    """Stream gepersonaliseerd lesmateriaal over een onderwerp.

    Args:
        onderwerp: Het onderwerp of de kerntaak om uitleg over te genereren.
        opleiding: De opleiding van de student.
        leerpad: Het leerpadniveau (Starter/Onderweg/Gevorderde/Expert).
        zwakste_kt: Optionele naam van de zwakste kerntaak voor extra context.

    Yields:
        Tekstfragmenten van het gegenereerde lesmateriaal.
    """
    context = f"opleiding {opleiding}, leerpadniveau {leerpad}"
    if zwakste_kt:
        context += f", met extra aandacht voor {zwakste_kt}"

    prompt = (
        f"Maak uitgebreid lesmateriaal over het onderwerp: **{onderwerp}**.\n"
        f"De student volgt {context}.\n"
        "Gebruik eenvoudige MBO-taal met concrete voorbeelden uit het vakgebied. "
        "Structureer de tekst met kopjes. "
        "Voeg aan het einde 2-3 reflectievragen toe om begrip te toetsen."
    )

    client = _client(api_key)
    with client.messages.stream(
        model=_MODEL,
        max_tokens=_MAX_TOKENS,
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        yield from stream.text_stream


# ── Rollenspel ────────────────────────────────────────────────────────────────

SCENARIO_OPTIES: dict[str, str] = {
    "sollicitatie": "Sollicitatiegesprek — je solliciteert naar een stageplek of baan",
    "stagegesprek": "Stagegesprek — functioneringsgesprek met je stagebegeleider",
    "beroepssituatie": "Beroepssituatie — uitdagende situatie met cliënt, klant of collega",
}

_TEGENPARTIJ: dict[str, str] = {
    "sollicitatie": "werkgever",
    "stagegesprek": "stagebegeleider",
    "beroepssituatie": "gesprekspartner",
}


@dataclass
class RollenspelSessie:
    """Houdt de gespreksgeschiedenis en context van één rollenspelsessie bij."""

    scenario: str
    opleiding: str
    leerpad: str
    naam: str
    geschiedenis: list[dict] = field(default_factory=list)

    def tegenpartij(self) -> str:
        """Geef de rol die de AI speelt in dit scenario."""
        return _TEGENPARTIJ.get(self.scenario, "gesprekspartner")

    def reset(self) -> None:
        """Wis de gespreksgeschiedenis (behoudt scenario en studentcontext)."""
        self.geschiedenis.clear()


def _rollenspel_systeem_prompt(sessie: RollenspelSessie) -> str:
    """Genereer de systeemprompt voor het rollenspel."""
    scenario_label = SCENARIO_OPTIES.get(sessie.scenario, sessie.scenario)
    tegenpartij = sessie.tegenpartij()

    return (
        f"Je speelt de rol van {tegenpartij} in een rollenspel voor een MBO-student.\n\n"
        f"## Scenario\n{scenario_label}\n\n"
        f"## Studentprofiel\n"
        f"Naam: {sessie.naam}\n"
        f"Opleiding: {sessie.opleiding}\n"
        f"Niveau: {sessie.leerpad}\n\n"
        f"## Jouw rol als {tegenpartij}\n"
        "- Blijf volledig in karakter gedurende het gehele gesprek.\n"
        "- Reageer realistisch en constructief — niet te makkelijk, niet te intimiderend.\n"
        "- Stel vervolgvragen die de student uitdagen hun gedachten te verwoorden.\n"
        "- Geef GEEN feedback of meta-commentaar tijdens het gesprek; dat volgt achteraf.\n\n"
        "## Taal\n"
        "Antwoord in het Nederlands. Gebruik taal passend bij de rol en het MBO-niveau."
    )


def stuur_rollenspel_bericht(
    sessie: RollenspelSessie,
    bericht: str,
    *,
    api_key: str | None = None,
) -> Generator[str]:
    """Stuur een bericht naar de rollenspel-AI en stream de reactie terug.

    Args:
        sessie: De actieve RollenspelSessie (wordt bijgewerkt met het nieuwe bericht).
        bericht: De uitspraak of actie van de student.
        api_key: Optionele Anthropic API-sleutel.

    Yields:
        Tekstfragmenten van de reactie van de tegenpartij.
    """
    sessie.geschiedenis.append({"role": "user", "content": bericht})

    volledige_reactie: list[str] = []

    client = _client(api_key)
    with client.messages.stream(
        model=_MODEL,
        max_tokens=_MAX_TOKENS,
        system=_rollenspel_systeem_prompt(sessie),
        messages=sessie.geschiedenis,
    ) as stream:
        for fragment in stream.text_stream:
            volledige_reactie.append(fragment)
            yield fragment

    sessie.geschiedenis.append({"role": "assistant", "content": "".join(volledige_reactie)})


def genereer_rollenspel_feedback(
    sessie: RollenspelSessie,
    *,
    api_key: str | None = None,
) -> Generator[str]:
    """Stream een coaching-nabespreking van het afgeronde rollenspel.

    Args:
        sessie: De voltooide RollenspelSessie met gespreksgeschiedenis.
        api_key: Optionele Anthropic API-sleutel.

    Yields:
        Tekstfragmenten van de nabespreking.
    """
    gesprek = "\n".join(
        f"{'Student' if b['role'] == 'user' else sessie.tegenpartij().title()}: {b['content']}"
        for b in sessie.geschiedenis
    )

    prompt = (
        f"Hieronder staat een rollenspelgesprek dat een MBO-student ({sessie.opleiding}, "
        f"{sessie.leerpad}-niveau) heeft gevoerd als voorbereiding op: "
        f"{SCENARIO_OPTIES.get(sessie.scenario, sessie.scenario)}.\n\n"
        f"## Het gesprek\n{gesprek}\n\n"
        "## Jouw taak\n"
        "Geef een korte, constructieve nabespreking (max. 150 woorden) met:\n"
        "1. Wat ging er goed in het gesprek?\n"
        "2. Eén concreet verbeterpunt voor de volgende keer.\n"
        "3. Een aanmoediging.\n"
        "Spreek de student direct aan."
    )

    client = _client(api_key)
    with client.messages.stream(
        model=_MODEL,
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        yield from stream.text_stream


def genereer_oefentoets(
    onderwerp: str,
    opleiding: str,
    leerpad: str,
    *,
    api_key: str | None = None,
) -> str:
    """Genereer 5 multiple-choice vragen over een onderwerp.

    Returns:
        Volledige toekst inclusief antwoordsleutel na het scheidingsteken ANTWOORDEN:.
    """
    prompt = (
        f"Maak een oefentoets van precies 5 multiple-choice vragen over: **{onderwerp}**.\n"
        f"De student volgt {opleiding} op {leerpad}-niveau.\n"
        "Elke vraag heeft 4 antwoordopties (A, B, C, D).\n"
        "Gebruik dit formaat voor elke vraag:\n\n"
        "**Vraag 1:** [vraagtekst]\n"
        "A. [optie A]\n"
        "B. [optie B]\n"
        "C. [optie C]\n"
        "D. [optie D]\n\n"
        "Geef NA alle 5 vragen op een aparte regel de antwoordsleutel in exact dit formaat:\n"
        "ANTWOORDEN: 1=A, 2=C, 3=B, 4=D, 5=A"
    )

    client = _client(api_key)
    response = client.messages.create(
        model=_MODEL,
        max_tokens=_MAX_TOKENS,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text


def controleer_antwoorden(
    toets_tekst: str,
    antwoorden: dict[int, str],
    opleiding: str,
    leerpad: str,
    *,
    api_key: str | None = None,
) -> Generator[str]:
    """Stream feedback op de ingevulde toetsantwoorden.

    Args:
        toets_tekst: De volledige toekst inclusief antwoordsleutel.
        antwoorden: Dict met vraagnummer (1-5) als sleutel en gekozen optie (A-D) als waarde.
        opleiding: De opleiding van de student.
        leerpad: Het leerpadniveau van de student.

    Yields:
        Tekstfragmenten van de feedback.
    """
    antwoorden_tekst = ", ".join(f"Vraag {k}: {v}" for k, v in sorted(antwoorden.items()))

    prompt = (
        f"Dit is de oefentoets:\n{toets_tekst}\n\n"
        f"De student ({opleiding}, {leerpad}-niveau) gaf deze antwoorden: {antwoorden_tekst}\n\n"
        "Geef per vraag aan of het antwoord goed of fout is en leg kort uit waarom. "
        "Sluit af met het totaalaantal goede antwoorden en een motiverende opmerking."
    )

    client = _client(api_key)
    with client.messages.stream(
        model=_MODEL,
        max_tokens=_MAX_TOKENS,
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        yield from stream.text_stream


def genereer_weekplan(
    naam: str,
    opleiding: str,
    leerpad: str,
    voortgang: float,
    bsa_behaald: float,
    bsa_vereist: float,
    zwakste_kerntaak: str = "",
    zwakste_werkproces: str = "",
    *,
    api_key: str | None = None,
) -> Generator[str]:
    """Stream een gepersonaliseerd weekplan met concrete studieacties.

    Args:
        naam: Naam van de student.
        opleiding: De opleiding van de student.
        leerpad: Het leerpadniveau (Starter/Onderweg/Gevorderde/Expert).
        voortgang: Studievoortgang als getal tussen 0 en 1.
        bsa_behaald: Behaalde BSA-studiepunten.
        bsa_vereist: Vereiste BSA-studiepunten.
        zwakste_kerntaak: Label van de kerntaak met de laagste score.
        zwakste_werkproces: Label van het werkproces met de laagste score.
        api_key: Optionele Anthropic API-sleutel.

    Yields:
        Tekstfragmenten van het gegenereerde weekplan.
    """
    bsa_status = (
        f"BSA: {bsa_behaald:.0f} van {bsa_vereist:.0f} studiepunten behaald "
        f"({bsa_behaald / bsa_vereist * 100:.0f}%)"
        if bsa_vereist > 0
        else "BSA-status onbekend"
    )
    aandachtspunten = []
    if zwakste_kerntaak:
        aandachtspunten.append(f"zwakste kerntaak: {zwakste_kerntaak}")
    if zwakste_werkproces:
        aandachtspunten.append(f"zwakste werkproces: {zwakste_werkproces}")
    aandacht_tekst = "Aandachtspunten: " + " | ".join(aandachtspunten) if aandachtspunten else ""

    prompt = (
        f"Maak een concreet weekplan voor MBO-student {naam}.\n\n"
        f"## Studentprofiel\n"
        f"- Opleiding: {opleiding}\n"
        f"- Niveau: {leerpad}\n"
        f"- Studievoortgang: {voortgang * 100:.0f}%\n"
        f"- {bsa_status}\n"
        + (f"- {aandacht_tekst}\n" if aandacht_tekst else "")
        + "\n## Opdracht\n"
        "Genereer een weekplan met **5 tot 7 concrete studieacties** voor de komende week.\n"
        "Gebruik dit formaat:\n\n"
        "**Weekplan — [naam]**\n\n"
        "| Dag | Actie | Duur | Doel |\n"
        "|---|---|---|---|\n"
        "| Maandag | … | … | … |\n\n"
        "Voeg daarna 1-2 regels motiverende afsluiting toe.\n\n"
        "Regels:\n"
        "- Acties zijn specifiek en uitvoerbaar (geen vage tips)\n"
        "- Sluit aan op de zwakste kerntaak of werkproces als die bekend is\n"
        "- Pas de intensiteit aan op het niveau (Starter = rustig opbouwen, Expert = verdieping)\n"
        "- Gebruik eenvoudige MBO-taal\n"
        "- Schrijf in het Nederlands"
    )

    client = _client(api_key)
    with client.messages.stream(
        model=_MODEL,
        max_tokens=_MAX_TOKENS,
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        yield from stream.text_stream


def geef_feedback_op_werk(
    werk: str,
    opleiding: str,
    leerpad: str,
    *,
    api_key: str | None = None,
) -> Generator[str]:
    """Stream constructieve feedback op ingeleverd werk van een student.

    Args:
        werk: De tekst van het ingeleverde werk.
        opleiding: De opleiding van de student.
        leerpad: Het leerpadniveau van de student.

    Yields:
        Tekstfragmenten van de feedback.
    """
    prompt = (
        f"Geef constructieve feedback op het volgende werk van een MBO-student "
        f"({opleiding}, {leerpad}-niveau).\n\n"
        "Beoordeel achtereenvolgens: inhoud en vakkennis, structuur en opbouw, "
        "taalgebruik en leesbaarheid. "
        "Geef per onderdeel een concreet verbeterpunt. "
        "Sluit af met één positief punt dat de student kan vasthouden.\n\n"
        f"Werk van de student:\n{werk}"
    )

    client = _client(api_key)
    with client.messages.stream(
        model=_MODEL,
        max_tokens=_MAX_TOKENS,
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        yield from stream.text_stream
