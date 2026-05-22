"""AI Tutor: vraag-en-antwoord-gesprekspartner via de Claude API.

De tutor beantwoordt vragen direct en duidelijk — vooral over de OER,
kerntaken, werkprocessen en leerstof. Letterlijke antwoorden op toetsvragen
of huiswerkopdrachten worden vermeden zodat de student het onderwerp zelf
leert begrijpen.
"""

from collections.abc import Generator
from dataclasses import dataclass, field
from typing import Literal

from anthropic.types import MessageParam

from samenwijzer._ai import MODEL, _client

_MAX_TOKENS = 2048


@dataclass
class StudentContext:
    """Context die de tutor krijgt over de student."""

    naam: str
    opleiding: str
    niveau: int
    voortgang: float
    kerntaak_focus: str = ""

    def als_tekst(self) -> str:
        """Geef de studentcontext terug als opgemaakte tekst voor de systeemprompt."""
        niveau_labels = {1: "starter", 2: "op weg", 3: "gevorderde", 4: "expert"}
        label = niveau_labels.get(self.niveau, "onbekend")
        tekst = (
            f"Naam: {self.naam}\n"
            f"Opleiding: {self.opleiding}\n"
            f"Niveau: {self.niveau} ({label})\n"
            f"Voortgang: {self.voortgang:.0%}"
        )
        if self.kerntaak_focus:
            tekst += f"\nHuidige focus: {self.kerntaak_focus}"
        return tekst


@dataclass
class TutorSessie:
    """Bewaart de gespreksgeschiedenis van één tutorsessie."""

    student: StudentContext
    geschiedenis: list[MessageParam] = field(default_factory=list)

    def voeg_toe(self, rol: Literal["user", "assistant"], inhoud: str) -> None:
        """Voeg een bericht toe aan de geschiedenis."""
        self.geschiedenis.append({"role": rol, "content": inhoud})

    def reset(self) -> None:
        """Wis de gespreksgeschiedenis (behoudt studentcontext)."""
        self.geschiedenis.clear()


def _systeem_prompt(student: StudentContext, oer_tekst: str = "") -> str:
    """Genereer de systeemprompt voor de tutor."""
    basis = f"""Je bent een persoonlijke AI-tutor voor MBO-studenten. Je beantwoordt
vragen direct en duidelijk, zodat de student snel begrijpt wat hij wil weten.

## Jouw rol
- Geef directe, heldere antwoorden — vooral op vragen over de OER, kerntaken,
  werkprocessen, opleiding, planning of leerstof.
- Gebruik de OER-tekst van de student als primaire bron en citeer concreet
  kerntaak- of werkprocesnamen waar dat helpt.
- Geef positieve, opbouwende feedback.
- Pas je taalgebruik aan het niveau van de student aan.

## Wat je NIET doet
- Letterlijke antwoorden voorzeggen op toetsvragen of huiswerkopdrachten —
  daar leert de student niet van. Help in plaats daarvan het onderwerp begrijpen
  door uit te leggen waar de vraag over gaat en welke OER-onderdelen relevant zijn.
- De student ontmoedigen of negatief beoordelen.

## Studentprofiel
{student.als_tekst()}

## Taal
Antwoord altijd in het Nederlands, tenzij de student expliciet in een andere taal schrijft.
Gebruik eenvoudige, heldere taal passend bij MBO-niveau {student.niveau}.
"""
    if oer_tekst:
        basis += f"\n## OER van de student\n{oer_tekst}"
    return basis


def stuur_bericht(
    sessie: TutorSessie,
    bericht: str,
    oer_tekst: str = "",
    *,
    api_key: str | None = None,
) -> Generator[str]:
    """Stuur een bericht naar de tutor en stream de reactie terug.

    Args:
        sessie: De actieve TutorSessie (wordt bijgewerkt met het nieuwe bericht).
        bericht: Het bericht van de student.
        oer_tekst: Volledige OER-tekst van de student voor extra context (optioneel).
        api_key: Optionele Anthropic API-sleutel; gebruikt ANTHROPIC_API_KEY als niet opgegeven.

    Yields:
        Tekstfragmenten van de reactie van de tutor (streaming).

    Raises:
        anthropic.APIError: Bij problemen met de API.
    """
    client = _client(api_key)

    sessie.voeg_toe("user", bericht)

    volledige_reactie: list[str] = []

    try:
        with client.messages.stream(
            model=MODEL,
            max_tokens=_MAX_TOKENS,
            system=[
                {
                    "type": "text",
                    "text": _systeem_prompt(sessie.student, oer_tekst),
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=sessie.geschiedenis,
        ) as stream:
            for fragment in stream.text_stream:
                volledige_reactie.append(fragment)
                yield fragment
    except Exception:
        # Houd de gespreksgeschiedenis consistent: het user-bericht weer verwijderen
        # voorkomt dat een volgende poging twee user-rollen op rij stuurt (= 400).
        if sessie.geschiedenis and sessie.geschiedenis[-1].get("role") == "user":
            sessie.geschiedenis.pop()
        raise

    sessie.voeg_toe("assistant", "".join(volledige_reactie))


def aanscherp_verantwoording(
    werkproces_label: str,
    kerntaak_label: str,
    opleiding: str,
    huidige_tekst: str,
    score: int,
    *,
    api_key: str | None = None,
) -> Generator[str]:
    """Laat de tutor een aangescherpte verantwoording suggereren.

    Args:
        werkproces_label: OER-label van het werkproces.
        kerntaak_label: OER-label van de bovenliggende kerntaak.
        opleiding: Opleidingsnaam van de student.
        huidige_tekst: De huidige verantwoording die de student heeft getypt.
        score: De zelf-gegeven score 0..100 voor dit werkproces.
        api_key: Optionele override; gebruikt ANTHROPIC_API_KEY als None.

    Yields:
        Tekstfragmenten van de aangescherpte versie (streaming).
    """
    client = _client(api_key)

    systeem = (
        "Je bent een leercoach voor een MBO-student. Help de student z'n eigen "
        "verantwoording aanscherpen. Schrijf in de ik-vorm van de student, in "
        "2 tot 4 zinnen, met concreet voorbeeldgedrag dat past bij de OER-formulering. "
        "Voeg geen kop, geen bullets, geen tussenkopjes toe — alleen lopende tekst."
    )
    gebruikersbericht = (
        f"Werkproces: {werkproces_label}\n"
        f"Kerntaak: {kerntaak_label}\n"
        f"Opleiding: {opleiding}\n"
        f"Zelf-gegeven score: {score}/100\n"
        f"Huidige verantwoording: {huidige_tekst or '(nog leeg)'}\n\n"
        "Geef een aangescherpte versie."
    )

    with client.messages.stream(
        model=MODEL,
        max_tokens=400,
        system=[{"type": "text", "text": systeem}],
        messages=[{"role": "user", "content": gebruikersbericht}],
    ) as stream:
        yield from stream.text_stream
