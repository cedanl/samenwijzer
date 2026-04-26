"""Persistentie voor WhatsApp telefoonregistraties en gesprekssessies.

Telefoonnummers worden versleuteld opgeslagen met Fernet (symmetrisch).
De encryptiesleutel komt uit de omgevingsvariabele WHATSAPP_ENCRYPT_KEY,
of wordt eenmalig gegenereerd en lokaal bewaard in data/02-prepared/.whatsapp.key.
"""

import json
import logging
import os
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

log = logging.getLogger(__name__)

_DB_PAD = Path(__file__).parent.parent.parent / "data" / "02-prepared" / "whatsapp.db"
_KEY_PAD = Path(__file__).parent.parent.parent / "data" / "02-prepared" / ".whatsapp.key"

_geinitialiseerd: set[Path] = set()


# ── Encryptie ─────────────────────────────────────────────────────────────────


def _sleutel() -> bytes:
    """Geef de Fernet-encryptiesleutel terug, of genereer er één."""
    env_key = os.getenv("WHATSAPP_ENCRYPT_KEY")
    if env_key:
        return env_key.encode()
    if _KEY_PAD.exists():
        return _KEY_PAD.read_bytes()
    key = Fernet.generate_key()
    _KEY_PAD.parent.mkdir(parents=True, exist_ok=True)
    _KEY_PAD.write_bytes(key)
    log.info("Nieuwe Fernet-sleutel aangemaakt op %s", _KEY_PAD)
    return key


def _fernet() -> Fernet:
    return Fernet(_sleutel())


def versleutel(tekst: str) -> str:
    return _fernet().encrypt(tekst.encode()).decode()


def ontsleutel(versleuteld: str) -> str:
    return _fernet().decrypt(versleuteld.encode()).decode()


# ── Database ──────────────────────────────────────────────────────────────────


def _verbinding() -> sqlite3.Connection:
    _DB_PAD.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(_DB_PAD)
    conn.row_factory = sqlite3.Row
    _initialiseer(conn)
    return conn


def _initialiseer(conn: sqlite3.Connection) -> None:
    if _DB_PAD in _geinitialiseerd:
        return
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS telefoon_registraties (
            studentnummer TEXT PRIMARY KEY,
            nummer_enc    TEXT NOT NULL,
            opt_in        INTEGER NOT NULL DEFAULT 0,
            geactiveerd   INTEGER NOT NULL DEFAULT 0,
            aangemeld_op  TEXT
        );
        CREATE TABLE IF NOT EXISTS whatsapp_sessies (
            from_number   TEXT PRIMARY KEY,
            stap          TEXT NOT NULL DEFAULT 'checkin',
            uitgewisseld  INTEGER NOT NULL DEFAULT 0,
            context_json  TEXT NOT NULL DEFAULT '[]',
            gestart_op    TEXT
        );
    """)
    conn.commit()
    _geinitialiseerd.add(_DB_PAD)


# ── Dataclasses ───────────────────────────────────────────────────────────────


@dataclass
class TelefoonnummerReg:
    studentnummer: str
    nummer_enc: str
    opt_in: bool
    geactiveerd: bool
    aangemeld_op: str | None


@dataclass
class WhatsappSessie:
    from_number: str
    stap: str
    uitgewisseld: int
    context_json: str
    gestart_op: str | None

    def context(self) -> list[dict]:
        """Geeft een mutable kopie van de gesprekshistorie; muteren raakt context_json niet."""
        return json.loads(self.context_json)

    def voeg_bericht_toe(self, rol: str, tekst: str) -> None:
        """Voeg een bericht toe aan de gesprekshistorie en verhoog de teller.

        Args:
            rol: Afzender van het bericht ('student' of 'coach').
            tekst: Berichttekst.
        """
        ctx = self.context()
        ctx.append({"rol": rol, "tekst": tekst})
        self.context_json = json.dumps(ctx)
        self.uitgewisseld += 1


# ── Telefoonregistraties ──────────────────────────────────────────────────────


def registreer_nummer(studentnummer: str, telefoonnummer: str) -> None:
    """Sla een telefoonnummer versleuteld op. Overschrijft bestaande registratie."""
    nummer_enc = versleutel(telefoonnummer)
    with _verbinding() as conn:
        conn.execute(
            """
            INSERT INTO telefoon_registraties
                (studentnummer, nummer_enc, opt_in, geactiveerd, aangemeld_op)
            VALUES (?, ?, 0, 0, ?)
            ON CONFLICT(studentnummer) DO UPDATE SET
                nummer_enc   = excluded.nummer_enc,
                opt_in       = 0,
                geactiveerd  = 0,
                aangemeld_op = excluded.aangemeld_op
        """,
            (studentnummer, nummer_enc, datetime.now().isoformat()),
        )


def activeer_nummer(studentnummer: str) -> None:
    """Activeer opt-in na succesvolle verificatie."""
    with _verbinding() as conn:
        conn.execute(
            """
            UPDATE telefoon_registraties
            SET opt_in=1, geactiveerd=1
            WHERE studentnummer=?
        """,
            (studentnummer,),
        )


def deactiveer_nummer(studentnummer: str) -> None:
    """Verwerk opt-out via de app."""
    with _verbinding() as conn:
        conn.execute(
            """
            UPDATE telefoon_registraties
            SET opt_in=0, geactiveerd=0
            WHERE studentnummer=?
        """,
            (studentnummer,),
        )


def get_registratie(studentnummer: str) -> TelefoonnummerReg | None:
    """Geef de telefoonregistratie voor een student, of None als die niet bestaat.

    Args:
        studentnummer: Uniek studentidentificatie.

    Returns:
        TelefoonnummerReg of None.
    """
    with _verbinding() as conn:
        rij = conn.execute(
            "SELECT * FROM telefoon_registraties WHERE studentnummer=?",
            (studentnummer,),
        ).fetchone()
    return TelefoonnummerReg(**dict(rij)) if rij else None


def heeft_actieve_registratie(studentnummer: str) -> bool:
    """Geeft True als de student een actieve opt-in heeft.

    Args:
        studentnummer: Uniek studentidentificatie.

    Returns:
        True als zowel geactiveerd als opt_in True zijn. Beide velden zijn nodig:
        geactiveerd kan gereset worden door opt-out terwijl opt_in de oorspronkelijke
        toestemming bijhoudt — alleen de combinatie garandeert een geldige opt-in.
    """
    reg = get_registratie(studentnummer)
    return reg is not None and bool(reg.geactiveerd) and bool(reg.opt_in)


def get_studentnummer_voor_telefoon(telefoonnummer: str) -> str | None:
    """Zoek studentnummer op basis van een telefoonnummer (decrypt-scan)."""
    with _verbinding() as conn:
        rijen = conn.execute(
            "SELECT studentnummer, nummer_enc FROM telefoon_registraties"
        ).fetchall()
    for rij in rijen:
        try:
            if ontsleutel(rij["nummer_enc"]) == telefoonnummer:
                return rij["studentnummer"]
        except InvalidToken:
            continue
    return None


def get_actieve_registraties() -> list[tuple[str, str]]:
    """Geef (studentnummer, telefoonnummer) paren voor alle actieve opt-ins."""
    with _verbinding() as conn:
        rijen = conn.execute("""
            SELECT studentnummer, nummer_enc
            FROM telefoon_registraties
            WHERE geactiveerd=1 AND opt_in=1
        """).fetchall()
    resultaten = []
    for rij in rijen:
        try:
            nummer = ontsleutel(rij["nummer_enc"])
            resultaten.append((rij["studentnummer"], nummer))
        except InvalidToken:
            log.warning("Kon telefoonnummer voor %s niet ontsleutelen", rij["studentnummer"])
    return resultaten


def deactiveer_nummer_via_telefoon(telefoonnummer: str) -> bool:
    """Verwerk STOP-bericht: deactiveer op basis van telefoonnummer. Geeft True bij succes."""
    snr = get_studentnummer_voor_telefoon(telefoonnummer)
    if snr:
        deactiveer_nummer(snr)
        return True
    return False


# ── Gesprekssessies ───────────────────────────────────────────────────────────


def get_sessie(from_number: str) -> WhatsappSessie | None:
    """Geef de actieve gesprekssessie voor een telefoonnummer, of None.

    Args:
        from_number: Telefoonnummer van de student (zonder 'whatsapp:'-prefix).

    Returns:
        WhatsappSessie of None.
    """
    with _verbinding() as conn:
        rij = conn.execute(
            "SELECT * FROM whatsapp_sessies WHERE from_number=?",
            (from_number,),
        ).fetchone()
    return WhatsappSessie(**dict(rij)) if rij else None


def sla_sessie_op(sessie: WhatsappSessie) -> None:
    """Sla een gesprekssessie op (insert of update op from_number)."""
    with _verbinding() as conn:
        conn.execute(
            """
            INSERT INTO whatsapp_sessies
                (from_number, stap, uitgewisseld, context_json, gestart_op)
            VALUES (:from_number, :stap, :uitgewisseld, :context_json, :gestart_op)
            ON CONFLICT(from_number) DO UPDATE SET
                stap         = excluded.stap,
                uitgewisseld = excluded.uitgewisseld,
                context_json = excluded.context_json
        """,
            asdict(sessie),
        )


def verwijder_sessie(from_number: str) -> None:
    """Verwijder de gesprekssessie voor een telefoonnummer.

    Args:
        from_number: Telefoonnummer van de student (zonder 'whatsapp:'-prefix).
    """
    with _verbinding() as conn:
        conn.execute("DELETE FROM whatsapp_sessies WHERE from_number=?", (from_number,))
