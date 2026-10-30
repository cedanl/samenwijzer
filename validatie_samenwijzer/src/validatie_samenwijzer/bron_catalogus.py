"""Chat-bronnen: laden van bronbestanden en de bron-catalogus van een chat-sessie.

Eén plek die de naam van een chat-bron kent. Deze module weet hoe een chat-bron (OER,
kwalificatiedossier, skills-taxonomie, instellingsbreed document) van schijf komt en met welke
cap, hoe de kop van zo'n bron in de systeemprompt luidt, en welke titel het model in de
bronnenregel (``<!-- bronnen: ... -->``) mag gebruiken. Een ``BronCatalogus`` wordt eenmaal per
chat-sessie opgebouwd uit de geselecteerde OER's; zijn ``register()`` (JSON) gaat mee in de
sessie, zodat een ``BronRegister`` later de titels uit een modelantwoord kan herleiden zonder
de teksten opnieuw te laden.
"""

from __future__ import annotations

import json
import logging
import os
import re
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urlparse

from validatie_samenwijzer.db import SOORTEN
from validatie_samenwijzer.kd_versies import kd_map, kies_kd_pad
from validatie_samenwijzer.opleiding import schoon_opleiding_naam

if TYPE_CHECKING:  # documenten importeert de laders uit deze module
    from validatie_samenwijzer.documenten import GekozenDocument

logger = logging.getLogger(__name__)

_MAX_OER_TEKST_TEKENS = 500_000  # ruim voldoende voor elke OER binnen Sonnet 4.6 (1M context)
_MAX_DOSSIER_TEKST_TEKENS = 300_000
_MAX_SKILLS_TEKST_TEKENS = 50_000  # skills-blok is klein; cap als veiligheid
# Cap voor instellingsbrede documenten (examenreglement/begeleidingsbeleid). Ruime veiligheidsrem:
# een echt examenreglement meet ~37K tekens (~12,5K tokens), dus de cap bindt in de praktijk niet.
# Onderbouwing: docs/plans/2026-06-02-instellingsbrede-bron.md §4 (kostenmeting 2026-06-02).
_MAX_INSTELLING_TEKST_TEKENS = 300_000


# ── Bronladers ────────────────────────────────────────────────────────────────


def resolve_oer_pad(bestandspad: str) -> Path:
    """Maak een DB-`bestandspad` (relatief, bv. `oeren/talland_oeren/x.pdf`) absoluut.

    De DB bewaart paden onder de oeren/-tree. OEREN_PAD wijst naar die tree
    (default `oeren`, na de root-dedupe `../oeren` vanuit validatie_samenwijzer/).
    De parent van OEREN_PAD is de bovenliggende projectroot — daarmee wordt
    `oeren/...` correct geresolved naar het echte bestand.
    """
    pad = Path(bestandspad)
    if pad.is_absolute():
        return pad
    return Path(os.environ.get("OEREN_PAD", "oeren")).resolve().parent / pad


def laad_oer_tekst(bestandspad: Path, cap: int = _MAX_OER_TEKST_TEKENS) -> str:
    """Laad de tekst van een OER of instellingsbreed document voor gebruik als chatcontext.

    Prioriteit: .md-broertje (markitdown-kwaliteit) → .md zelf → PDF via pdfplumber.

    Args:
        bestandspad: Pad naar het bestand (PDF of Markdown).
        cap: maximum aantal tekens; instellingsbrede documenten geven
            ``_MAX_INSTELLING_TEKST_TEKENS`` mee.

    Returns:
        De tekst (gecapt), of lege string als niets beschikbaar is.
    """
    if not bestandspad.exists():
        # Probeer het .md-broertje ook als het bronbestand zelf ontbreekt
        md_pad = bestandspad.with_suffix(".md")
        if md_pad.exists():
            md_tekst = md_pad.read_text(encoding="utf-8", errors="replace")
            if md_tekst.strip():
                return md_tekst[:cap]
        return ""

    suffix = bestandspad.suffix.lower()

    if suffix == ".md":
        return bestandspad.read_text(encoding="utf-8", errors="replace")[:cap]

    if suffix == ".pdf":
        # Voorkeur: naastliggend .md-bestand van markitdown-conversie — maar alleen als
        # het écht inhoud heeft. Een leeg .md (bv. mislukte conversie van een gescande
        # PDF) mag de pdfplumber-fallback niet blokkeren.
        md_pad = bestandspad.with_suffix(".md")
        if md_pad.exists():
            md_tekst = md_pad.read_text(encoding="utf-8", errors="replace")
            if md_tekst.strip():
                return md_tekst[:cap]
        # Fallback: pdfplumber
        try:
            import pdfplumber

            tekst_delen = []
            with pdfplumber.open(str(bestandspad)) as pdf:
                for pagina in pdf.pages:
                    t = pagina.extract_text()
                    if t:
                        tekst_delen.append(t)
            return "\n\n".join(tekst_delen)[:cap]
        except Exception as e:
            logger.warning("PDF lezen mislukt voor '%s': %s", bestandspad, e)
            return ""

    return ""


def laad_kwalificatiedossier_tekst(crebo: str | None, cohort: str | int | None = None) -> str:
    """Laad de markdown-tekst van een kwalificatiedossier op crebo, of lege string.

    Met ``cohort`` wordt de KD-versie gekozen die voor dat cohort geldt (zie ``kd_versies``);
    zonder cohort of zonder match geldt het nieuwste (``<crebo>.md`` in ``kd_versies.kd_map()``).
    """
    if not crebo:
        return ""
    md_pad = kies_kd_pad(str(crebo), cohort) or kd_map() / f"{crebo}.md"
    if not md_pad.exists():
        return ""
    return md_pad.read_text(encoding="utf-8", errors="replace")[:_MAX_DOSSIER_TEKST_TEKENS]


def pad_skills(crebo: str) -> Path:
    """Pad naar het skills-taxonomie-artefact voor een crebo.

    Default: ``<subproject-root>/data/skills/<crebo>.json`` (gebouwd door
    ``scripts/build_skills_taxonomie.py``). Override via env-var ``SKILLS_PAD``.
    """
    base = os.environ.get("SKILLS_PAD")
    if base:
        directory = Path(base).resolve()
    else:
        # bron_catalogus.py → parents[2] = subproject-root → data/skills
        directory = Path(__file__).resolve().parents[2] / "data" / "skills"
    return directory / f"{crebo}.json"


def laad_skills_tekst(crebo: str | None) -> str:
    """Bouw het skills-tekstblok voor een crebo, of lege string als er geen artefact is.

    Leest het bron-agnostische JSON-artefact en formatteert het tot een leesbaar
    blok voor de systeemprompt. Lege string als het bestand ontbreekt of geen
    beroep gematcht is — de chat werkt dan zonder skills.
    """
    if not crebo:
        return ""
    json_pad = pad_skills(str(crebo))
    if not json_pad.exists():
        return ""
    try:
        data = json.loads(json_pad.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Skills-artefact onleesbaar voor crebo %s: %s", crebo, e)
        return ""

    beroep = data.get("beroep")
    if not beroep:
        return ""

    regels = [f'Beroep "{beroep["label"]}"']
    if beroep.get("definitie"):
        regels.append(beroep["definitie"])
    for categorie, kop in (
        ("essentieel", "Essentiële skills"),
        ("belangrijk", "Belangrijke skills"),
        ("optioneel", "Optionele skills"),
    ):
        labels = [s["label"] for s in data.get("skills", []) if s["categorie"] == categorie]
        if labels:
            regels.append(f"\n{kop}:")
            regels.extend(f"- {label}" for label in labels)

    bron = data.get("bron", "ESCO")
    tekst = "\n".join(regels)[:_MAX_SKILLS_TEKST_TEKENS]
    return (
        f"\n\n=== SKILLS-TAXONOMIE ({bron}) — beroep: {beroep['label']} ===\n"
        f"De skills die horen bij het beroep waarvoor deze opleiding opleidt. "
        f"Citeer deze skills uitsluitend als afkomstig van: {bron}.\n"
        f"{tekst}"
    )


# ── Bronnamen ─────────────────────────────────────────────────────────────────

BRON_TYPES: frozenset[str] = frozenset(
    {"studiegids", "kwalificatiedossier", "schooldocument", "skills", "website"}
)
_INFORMATIEF = " [INFORMATIEF]"


def document_kop(soort: str, titel: str, instelling: str = "") -> str:
    """Naam van een instellingsbreed of opleidingsgebonden document, zoals in de promptkop.

    Een achtervoegsel met de instellingsnaam (oude titels als "Examenreglement Curio") wordt
    weggelaten. Niet-juridische documenten krijgen `[INFORMATIEF]`: daarbij volstaat een
    bronvermelding en is een woordelijk citaat niet nodig.
    """
    info = SOORTEN[soort]
    naam = titel.removesuffix(f" {instelling}") if instelling else titel
    if naam == info.label:
        kop = info.label
    elif naam.startswith(f"{info.label} "):
        kop = f"{info.label} — {naam[len(info.label) + 1 :]}"
    else:
        kop = f"{info.label} — {naam}"
    return kop if info.juridisch else f"{kop}{_INFORMATIEF}"


@dataclass(frozen=True)
class Bron:
    """Eén chat-bron zoals die onder een antwoord genoemd wordt (de bronnen-chips).

    ``type`` is één van ``BRON_TYPES``. De identifiers zijn alleen gevuld als de titel via een
    catalogus/register herleid is: ``oer_id`` (studiegids; bij KD en skills de OER waar ze bij
    horen), ``doc_id`` (schooldocument) en ``crebo`` (kwalificatiedossier, skills).
    """

    type: str
    titel: str
    url: str | None = None
    doc_id: int | None = None
    oer_id: int | None = None
    crebo: str | None = None


def _norm(titel: str) -> str:
    """Vergelijkingsvorm van een titel: hoofdletterongevoelig, streepjes en witruimte gelijk,
    zonder `[INFORMATIEF]` en omringende aanhalingstekens."""
    t = titel.casefold().replace("[informatief]", "")
    t = re.sub(r"[‐-―−]", "-", t)
    t = " ".join(t.split())
    return t.strip(" \"'“”‘’")


def _host_hoort_bij(url: str, domein: str) -> bool:
    try:
        delen = urlparse(url)
        host = (delen.hostname or "").casefold()
    except ValueError:
        return False
    return delen.scheme in ("http", "https") and (host == domein or host.endswith(f".{domein}"))


@dataclass(frozen=True)
class BronRegister:
    """De bekende bronnen van een chat-sessie, zonder teksten: herleidt modeltitels."""

    bronnen: tuple[Bron, ...] = ()

    @classmethod
    def uit_dicts(cls, items: Iterable[dict]) -> BronRegister:
        """Herbouw uit ``BronCatalogus.register()``-uitvoer (bv. uit de sessie). Ongeldige
        items (onbekend type, geen titel) vallen weg."""
        bronnen = []
        for d in items:
            if not isinstance(d, dict) or d.get("type") not in BRON_TYPES or not d.get("titel"):
                continue
            bronnen.append(
                Bron(
                    d["type"],
                    str(d["titel"]),
                    doc_id=d.get("doc_id"),
                    oer_id=d.get("oer_id"),
                    crebo=d.get("crebo"),
                )
            )
        return cls(tuple(bronnen))

    def naar_dicts(self) -> list[dict]:
        """JSON-serialiseerbare vorm (zonder url) voor de server-side sessie."""
        return [
            {"type": b.type, "titel": b.titel, "doc_id": b.doc_id, "oer_id": b.oer_id,
             "crebo": b.crebo}
            for b in self.bronnen
        ]  # fmt: skip

    def resolve(self, titel: str, url: str | None = None) -> Bron | None:
        """Herleid een door het model geschreven titel naar een bekende bron, of None.

        Vergelijkt hoofdletter-/streepjesongevoelig. Een website-bron matcht op het domein
        (met of zonder ``www.``); een meegegeven url moet dan binnen dat domein liggen, anders
        is de bron onbekend. Andere bronnen krijgen geen url.
        """
        sleutel = _norm(titel).removeprefix("www.")
        for bron in self.bronnen:
            if _norm(bron.titel) != sleutel:
                continue
            if bron.type != "website":
                return bron
            if url is None:
                return bron
            if _host_hoort_bij(url, bron.titel.casefold()):
                return Bron(bron.type, bron.titel, url)
            return None
        return None


# ── Bron-catalogus ────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class OerInvoer:
    """Eén geselecteerde OER met de al geladen teksten van zijn chat-bronnen.

    ``instelling`` is de weergavenaam (``display_naam``), ``instelling_sleutel`` de korte
    registry-sleutel (``instellingen.naam``, voor de webzoek-domeinen). ``documenten`` zijn de
    voor deze OER gekozen documenten uit ``documenten.Selectie.per_oer``.
    """

    opleiding: str
    instelling: str
    oer_id: int | None = None
    instelling_sleutel: str = ""
    leerweg: str = ""
    cohort: str = ""
    crebo: str | None = None
    oer_tekst: str = ""
    kd_tekst: str = ""
    skills_tekst: str = ""
    documenten: Sequence[GekozenDocument] = ()

    def heeft_bron(self) -> bool:
        """Bruikbaar als chat-bron: leesbare OER, of anders een KD of document."""
        return bool(
            self.oer_tekst.strip() or self.kd_tekst or any(d.tekst for d in self.documenten)
        )


@dataclass(frozen=True)
class _Blok:
    kop: str  # complete kopregel ("=== … ==="); leeg als de tekst zijn kop zelf draagt
    tekst: str
    bron: Bron | None  # None: niet citeerbaar (onleesbare OER)


@dataclass(frozen=True)
class CatalogusOer:
    """Een OER in de catalogus: volgnummer (1-based), invoer, schone opleidingsnaam, blokken."""

    index: int
    invoer: OerInvoer
    opleiding: str
    blokken: tuple[_Blok, ...] = field(repr=False)

    @property
    def onleesbaar(self) -> bool:
        return not self.invoer.oer_tekst.strip()


_OER_ONLEESBAAR = (
    "(De OER van deze opleiding is niet machine-leesbaar; gebruik de aanvullende "
    "bronnen hieronder: het kwalificatiedossier en de instellingsregelingen.)"
)
_SKILLS_KOP = re.compile(
    r"=== SKILLS-TAXONOMIE \((?P<bron>[^)]+)\)(?: — beroep: (?P<beroep>.+?))? ==="
)


def _kop_oer(i: int, instelling: str, opleiding: str, leerweg: str, cohort: str) -> str:
    label = " · ".join(d for d in (instelling, opleiding, f"{leerweg} {cohort}".strip()) if d)
    return f"=== OER {i}: {label} ==="


def _kop_document(kop: str, instelling: str) -> str:
    return f"=== {kop.upper()} ({instelling}) ===" if instelling else f"=== {kop.upper()} ==="


def _kop_kd(i: int, crebo: str | None) -> str:
    return f"=== KWALIFICATIEDOSSIER {i} (Crebo {crebo or 'onbekend'}) ==="


def _skills_titel(skills_tekst: str) -> str:
    m = _SKILLS_KOP.search(skills_tekst)
    if not m:
        return "Skills-taxonomie"
    return f"{m['bron']} {m['beroep']}" if m["beroep"] else m["bron"]


def _maak_uniek(titels: list[str], achtervoegsels: list[tuple[str, ...]]) -> list[str]:
    """Maak titels uniek: botsende titels krijgen stap voor stap een achtervoegsel tussen haakjes
    (eerst de instelling, dan "OER i"); een laatste vangnet nummert wat dan nog botst."""
    uit = list(titels)
    for stap in range(max((len(a) for a in achtervoegsels), default=0)):
        tellingen = Counter(_norm(t) for t in uit)
        uit = [
            f"{t} ({a[stap]})" if tellingen[_norm(t)] > 1 and stap < len(a) and a[stap] else t
            for t, a in zip(uit, achtervoegsels, strict=True)
        ]
    tellingen = Counter(_norm(t) for t in uit)
    volgnummer: Counter[str] = Counter()
    for k, t in enumerate(uit):
        if tellingen[_norm(t)] > 1:
            volgnummer[_norm(t)] += 1
            uit[k] = f"{t} ({volgnummer[_norm(t)]})"
    return uit


@dataclass(frozen=True)
class BronCatalogus:
    """Alle chat-bronnen van één chat-sessie, met hun promptkoppen en markertitels.

    Bouw met :meth:`bouw`; OER's zonder enige bruikbare bron vallen dan weg. Elke citeerbare
    bron krijgt een unieke titel (``bronnen``); dezelfde koppen gelden in single- en multi-modus.
    """

    oers: tuple[CatalogusOer, ...] = ()

    @classmethod
    def bouw(cls, oers: Iterable[OerInvoer]) -> BronCatalogus:
        bruikbaar = [o for o in oers if o.heeft_bron()]

        # Eerst per OER de ruwe blokken met hun basistitel; daarna de titels uniek maken.
        ruw: list[tuple[int, OerInvoer, str, list[tuple[str, str, Bron | None]]]] = []
        basistitels: list[str] = []
        achtervoegsels: list[tuple[str, ...]] = []
        for i, o in enumerate(bruikbaar, 1):
            crebo = str(o.crebo) if o.crebo else None
            opleiding = schoon_opleiding_naam(o.opleiding, crebo or "")
            blokken: list[tuple[str, str, Bron | None]] = []
            kop_oer = _kop_oer(i, o.instelling, opleiding, o.leerweg, o.cohort)
            if o.oer_tekst.strip():
                titel = " ".join(f"OER {opleiding} {o.leerweg} {o.cohort}".split())
                blokken.append((kop_oer, o.oer_tekst, Bron("studiegids", titel, oer_id=o.oer_id)))
            else:
                blokken.append((kop_oer, _OER_ONLEESBAAR, None))
            for d in o.documenten:
                if d.tekst:
                    bron = Bron("schooldocument", d.kop.removesuffix(_INFORMATIEF), doc_id=d.doc_id)
                    blokken.append((_kop_document(d.kop, o.instelling), d.tekst, bron))
            if o.kd_tekst:
                titel = f"Kwalificatiedossier {crebo}" if crebo else "Kwalificatiedossier"
                bron = Bron("kwalificatiedossier", titel, oer_id=o.oer_id, crebo=crebo)
                blokken.append((_kop_kd(i, crebo), o.kd_tekst, bron))
            if o.skills_tekst:
                bron = Bron("skills", _skills_titel(o.skills_tekst), oer_id=o.oer_id, crebo=crebo)
                blokken.append(("", o.skills_tekst.lstrip("\n"), bron))
            for _, _, bron in blokken:
                if bron is not None:
                    # `|` en `;` zijn scheidingstekens in de bronnenregel.
                    basistitels.append(bron.titel.replace("|", "/").replace(";", ","))
                    achtervoegsels.append((o.instelling, f"OER {i}"))
            ruw.append((i, o, opleiding, blokken))

        titels = iter(_maak_uniek(basistitels, achtervoegsels))
        catalogus_oers = []
        for i, o, opleiding, blokken in ruw:
            definitief = tuple(
                _Blok(kop, tekst, None if bron is None else _met_titel(bron, next(titels)))
                for kop, tekst, bron in blokken
            )
            catalogus_oers.append(CatalogusOer(i, o, opleiding, definitief))
        return cls(tuple(catalogus_oers))

    @property
    def leeg(self) -> bool:
        return not self.oers

    @property
    def oer_onleesbaar(self) -> bool:
        """True als minstens één opgenomen OER geen leesbare tekst heeft (KD-fallback)."""
        return any(o.onleesbaar for o in self.oers)

    @property
    def instelling_sleutels(self) -> tuple[str, ...]:
        return tuple(o.invoer.instelling_sleutel for o in self.oers if o.invoer.instelling_sleutel)

    @property
    def bronnen(self) -> tuple[Bron, ...]:
        """De citeerbare bronnen in promptvolgorde, met unieke titels."""
        return tuple(b.bron for o in self.oers for b in o.blokken if b.bron is not None)

    def bronblokken(self) -> str:
        """Alle bronteksten met hun koppen, per OER; OER's gescheiden door een ``---``-regel."""
        return "\n\n---\n\n".join(
            "\n\n".join(f"{b.kop}\n{b.tekst}" if b.kop else b.tekst for b in o.blokken)
            for o in self.oers
        )

    def register(self, web_domeinen: Iterable[str] = ()) -> list[dict]:
        """JSON-serialiseerbaar register van de bronnen, om in de sessie te bewaren.

        ``web_domeinen`` (bv. ``Prompt.web_domeinen``) komen erbij als website-bronnen, zodat
        een webantwoord alleen URL's binnen de toegestane domeinen als bron kan noemen.
        """
        websites = tuple(Bron("website", d) for d in sorted(set(web_domeinen)))
        return BronRegister(self.bronnen + websites).naar_dicts()

    def resolve(self, titel: str) -> Bron | None:
        """Herleid een modeltitel naar een bron uit deze catalogus, of None."""
        return BronRegister(self.bronnen).resolve(titel)


def _met_titel(bron: Bron, titel: str) -> Bron:
    return Bron(bron.type, titel, bron.url, bron.doc_id, bron.oer_id, bron.crebo)
