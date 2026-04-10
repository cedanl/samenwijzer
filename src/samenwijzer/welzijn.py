"""Welzijnsmodule: AI-reactie op student self-assessment."""

import os
from collections.abc import Generator

import anthropic

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
    return _CATEGORIE_LABEL.get(categorie, categorie)


def urgentie_label(urgentie: int) -> str:
    return _URGENTIE_LABEL.get(urgentie, str(urgentie))


def _client(api_key: str | None = None) -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=api_key or os.environ.get("ANTHROPIC_API_KEY"))


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
