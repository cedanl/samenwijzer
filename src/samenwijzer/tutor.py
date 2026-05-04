"""AI Tutor: Socratische gesprekspartner via de Claude API.

De tutor moedigt studenten aan zelf antwoorden te formuleren.
Hij stelt verdiepende vragen, verbindt ideeën en biedt oefeningen aan
waar nodig — maar geeft nooit direct het antwoord.
"""

from collections.abc import Generator
from dataclasses import dataclass, field

from samenwijzer._ai import _client

_MODEL = "claude-sonnet-4-6"
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
    geschiedenis: list[dict] = field(default_factory=list)

    def voeg_toe(self, rol: str, inhoud: str) -> None:
        """Voeg een bericht toe aan de geschiedenis."""
        self.geschiedenis.append({"role": rol, "content": inhoud})

    def reset(self) -> None:
        """Wis de gespreksgeschiedenis (behoudt studentcontext)."""
        self.geschiedenis.clear()


def _systeem_prompt(student: StudentContext, oer_tekst: str = "") -> str:
    """Genereer de systeemprompt voor de Socratische tutor."""
    basis = f"""Je bent een persoonlijke AI-tutor voor MBO-studenten. Je begeleidt studenten
Socratisch: je moedigt hen aan zelf antwoorden te formuleren en goed na te denken over problemen.

## Jouw rol
- Stel verdiepende vragen in plaats van direct antwoorden te geven.
- Verbind ideeën van de student met elkaar en met de leerstof.
- Bied gerichte oefeningen aan als een student ergens mee worstelt.
- Geef positieve, opbouwende feedback op de redenering van de student.
- Pas je taalgebruik aan het niveau van de student aan.

## Wat je NIET doet
- Directe antwoorden geven op toetsvragen of opdrachten.
- De student ontmoedigen of negatief beoordelen.
- Meer dan twee vervolgvragen tegelijk stellen.

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

    with client.messages.stream(
        model=_MODEL,
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

    sessie.voeg_toe("assistant", "".join(volledige_reactie))
