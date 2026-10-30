"""Het Gesprek: de server-side gesprekshistorie van één chat-sessie.

Eén module bezit de invariant die voorheen over sessie, routes en ``chat.py`` verdeeld was:

* de historie bewaart per beurt de **ruwe** modeltekst, inclusief de
  ``<!-- bronnen: … -->``-marker (strippen gebeurt pas aan de leesrand: het UI-beeld);
* het model krijgt altijd een geldige, alternerende berichtenlijst (geen lege of dubbele
  rollen, begint met ``user``, eindigt met de nieuwe vraag);
* een beurt wordt precies één keer vastgelegd — compleet of afgebroken — ook als de stream
  van een andere thread wordt afgebroken (heartbeat-timeout) terwijl de worker nog loopt.

UI-vrij en zonder AI-calls: alleen stdlib en de marker-helpers uit ``chat.py``.

Opslagvorm (``naar_lijst``/``van_lijst``) is de JSON-lijst ``[{"role", "content"}, …]`` die al
in ``sessies.db`` staat. Een afgebroken assistant-beurt krijgt er ``"afgebroken": true`` bij;
oudere sessies (zonder de sleutel) laden ongewijzigd, en oude code negeert de extra sleutel.
"""

from __future__ import annotations

import threading
from collections.abc import Iterable
from dataclasses import asdict, dataclass

from validatie_samenwijzer.bron_catalogus import BronRegister
from validatie_samenwijzer.chat import knip_bronnenregel, splits_bronnen

MAX_GESCHIEDENIS = 20  # 10 vraag/antwoord-paren (2 berichten per beurt)

# Wat het model ziet achter een afgebroken, gedeeltelijk antwoord.
_AFGEBROKEN_NOTITIE = "[antwoord afgebroken]"


@dataclass(frozen=True)
class Beurt:
    """Eén voltooide vraag/antwoord-beurt; ``antwoord`` is de ruwe modeltekst (mét marker)."""

    vraag: str
    antwoord: str


class Gesprek:
    """De geordende vraag/antwoord-historie van één chat-sessie."""

    def __init__(self, berichten: Iterable[dict] | None = None) -> None:
        self._berichten: list[dict] = [dict(b) for b in berichten or ()]

    # ── (de)serialisatie ──────────────────────────────────────────────────────────
    @classmethod
    def van_lijst(cls, lijst: Iterable[dict] | None) -> Gesprek:
        """Bouw een Gesprek uit de bewaarde JSON-lijst (``None`` of leeg → leeg Gesprek)."""
        return cls(lijst)

    def naar_lijst(self) -> list[dict]:
        """De opslagvorm: een kopie van de berichtenlijst, klaar voor ``json.dumps``."""
        return [dict(b) for b in self._berichten]

    # ── schrijven ─────────────────────────────────────────────────────────────────
    def voeg_beurt_toe(self, vraag: str, antwoord: str, *, afgebroken: bool = False) -> None:
        """Leg een vraag/antwoord-paar vast en kap de historie op ``MAX_GESCHIEDENIS``.

        ``antwoord`` is de ruwe modeltekst (mét marker); een leeg antwoord markeert een
        onbeantwoorde vraag (bv. de kies-beurt) en wordt door :meth:`berichten_voor_model`
        gesaneerd. Met ``afgebroken=True`` is ``antwoord`` een gedeeltelijk antwoord: de
        marker (of het begin ervan) wordt eruit geknipt.
        """
        self._berichten.append({"role": "user", "content": vraag})
        if afgebroken:
            self._berichten.append(
                {"role": "assistant", "content": knip_bronnenregel(antwoord), "afgebroken": True}
            )
        else:
            self._berichten.append({"role": "assistant", "content": antwoord})
        if len(self._berichten) > MAX_GESCHIEDENIS:
            self._berichten = self._berichten[-MAX_GESCHIEDENIS:]

    def begin_beurt(self, vraag: str) -> LopendeBeurt:
        """Start een streamende beurt; zie :class:`LopendeBeurt`."""
        return LopendeBeurt(self, vraag)

    def reset(self) -> None:
        """Wis de hele historie."""
        self._berichten = []

    # ── lezen ─────────────────────────────────────────────────────────────────────
    def __len__(self) -> int:
        return len(self._berichten)

    def __bool__(self) -> bool:
        return bool(self._berichten)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Gesprek) and self._berichten == other._berichten

    def __repr__(self) -> str:
        return f"Gesprek({len(self._berichten)} berichten)"

    def berichten_voor_model(self, nieuwe_vraag: str) -> list[dict]:
        """De berichtenlijst voor de API: gesaneerde historie plus de nieuwe vraag.

        Lege beurten (een mislukte AI-call) worden overgeslagen, twee dezelfde rollen op rij
        ingeklapt en een onbeantwoorde laatste user-beurt vervangen door de nieuwe vraag; zo
        blokkeert één gefaalde beurt de sessie niet (API 400 op lege/niet-alternerende content).
        Een afgebroken beurt met gedeeltelijk antwoord krijgt ``[antwoord afgebroken]`` erachter,
        zodat het model weet dat die beurt niet af was; zonder gedeelte telt hij als onbeantwoord.
        """
        berichten: list[dict] = []
        for bericht in self._berichten:
            inhoud = str(bericht.get("content", ""))
            if not inhoud.strip():
                continue  # lege/mislukte beurt overslaan
            if berichten and berichten[-1]["role"] == bericht["role"]:
                continue  # geen twee dezelfde rollen op rij
            if bericht.get("afgebroken"):
                inhoud = f"{inhoud.rstrip()}\n\n{_AFGEBROKEN_NOTITIE}"
            berichten.append({"role": bericht["role"], "content": inhoud})
        while berichten and berichten[0]["role"] != "user":
            berichten.pop(0)  # API verwacht een user-beurt als eerste
        if berichten and berichten[-1]["role"] == "user":
            berichten.pop()  # onbeantwoorde vraag → vervangen door de nieuwe
        berichten.append({"role": "user", "content": nieuwe_vraag})
        return berichten

    def view_voor_ui(self, register: BronRegister | Iterable[dict] | None = None) -> list[dict]:
        """De historie voor de browser (rehydratie bij page-load).

        Assistant-beurten krijgen de bronnenmarker eruit (``content``) en de geparste bronnen
        als ``bronnen``-lijst (altijd aanwezig, mag leeg zijn); een afgebroken beurt heeft
        daarbovenop ``"afgebroken": true``. User-beurten blijven ongewijzigd. ``register``
        werkt als bij :func:`chat.splits_bronnen`. Het Gesprek zelf blijft ongemoeid.
        """
        if register is not None and not isinstance(register, BronRegister):
            register = BronRegister.uit_dicts(register)
        uit: list[dict] = []
        for beurt in self._berichten:
            if beurt.get("role") == "assistant":
                tekst, bronnen = splits_bronnen(beurt.get("content", ""), register)
                item = {
                    "role": "assistant",
                    "content": tekst,
                    "bronnen": [asdict(b) for b in bronnen],
                }
                if beurt.get("afgebroken"):
                    item["afgebroken"] = True
                uit.append(item)
            else:
                uit.append({"role": beurt.get("role"), "content": beurt.get("content", "")})
        return uit

    def laatste_beurt(self) -> Beurt | None:
        """De laatste *voltooide* vraag/antwoord-beurt, of ``None``.

        ``None`` bij een lege historie, een onbeantwoorde of afgebroken laatste beurt, of een
        leeg antwoord — dan valt er niets zinnigs aan te vervolgen. ``antwoord`` is ruw (mét
        marker); de marker doet er voor het genereren van vervolgvragen niet toe.
        """
        if len(self._berichten) < 2:
            return None
        vraag, antwoord = self._berichten[-2], self._berichten[-1]
        if vraag.get("role") != "user" or antwoord.get("role") != "assistant":
            return None
        if antwoord.get("afgebroken") or not str(antwoord.get("content", "")).strip():
            return None
        return Beurt(str(vraag["content"]), str(antwoord["content"]))

    def context_tekst(self, nieuwe_vraag: str) -> str:
        """Alle user-beurten plus de nieuwe vraag, aan elkaar geplakt.

        Voor het scoren van OER-kandidaten: een vervolgbeurt ("2024", "Tandartsassistent, BOL")
        heeft de context van eerdere beurten nodig om te matchen. Bij lege historie is dit gelijk
        aan ``nieuwe_vraag``.
        """
        return " ".join(
            [str(b["content"]) for b in self._berichten if b.get("role") == "user"] + [nieuwe_vraag]
        )


class LopendeBeurt:
    """Een beurt in uitvoering: verzamelt het ruwe antwoord en legt hem één keer vast.

    De chat-stream draait in een worker-thread, terwijl de heartbeat-bewaking (event-loop) hem
    kan afbreken. ``rond_af`` en ``breek_af`` sluiten elkaar uit onder één lock: wie het eerst
    komt legt de beurt vast, de ander is een no-op en krijgt ``False``. Zo ontstaat geen
    dubbele beurt als een afgebroken worker later alsnog klaarkomt. De aanroeper die ``True``
    krijgt is verantwoordelijk voor het bewaren van de sessie.
    """

    def __init__(self, gesprek: Gesprek, vraag: str) -> None:
        self._gesprek = gesprek
        self.vraag = vraag
        self._delen: list[str] = []
        self._klaar = False
        self._lock = threading.Lock()

    def voeg_toe(self, tekst: str) -> None:
        """Voeg een ruw tekstfragment van het model toe (na afronden/afbreken genegeerd)."""
        with self._lock:
            if not self._klaar:
                self._delen.append(tekst)

    @property
    def antwoord(self) -> str:
        """Het tot nu toe verzamelde ruwe antwoord."""
        with self._lock:
            return "".join(self._delen)

    def rond_af(self) -> bool:
        """Leg de beurt compleet vast. ``False`` als hij al was afgebroken/afgerond."""
        with self._lock:
            if self._klaar:
                return False
            self._klaar = True
            self._gesprek.voeg_beurt_toe(self.vraag, "".join(self._delen))
            return True

    def breek_af(self) -> bool:
        """Leg vraag + gedeeltelijk antwoord vast als afgebroken. ``False`` als al vastgelegd."""
        with self._lock:
            if self._klaar:
                return False
            self._klaar = True
            self._gesprek.voeg_beurt_toe(self.vraag, "".join(self._delen), afgebroken=True)
            return True
