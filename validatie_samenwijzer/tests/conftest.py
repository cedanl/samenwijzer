"""Globale pytest-fixtures.

App-tests bouwen hun eigen ``AppDeps`` (in-memory validatie-DB en sessie-store, nep-AI-client)
en een ``TestClient`` op ``maak_app(deps)`` — geen env, geen echte DB, geen gepatchte globals.
"""

import os
from pathlib import Path

import pytest

# Alleen nodig om ``app_fastapi.main`` te kunnen importeren: die bouwt bij import de
# productie-``app`` via ``AppDeps.uit_env()`` (fail-closed). Tests gebruiken die app niet.
os.environ.setdefault("SESSION_SECRET", "test-secret")
os.environ.setdefault("ALGEMEEN_WACHTWOORD", "test-pw")

from app_fastapi.deps import AppDeps, ValidatieDb  # noqa: E402
from app_fastapi.sessie import Sessie, SessieStore  # noqa: E402
from validatie_samenwijzer import db, opleiding  # noqa: E402
from validatie_samenwijzer.auth import hash_wachtwoord  # noqa: E402

TEST_WACHTWOORD = "test-pw"
NEP_CLIENT = object()  # wat de standaard-nep-``ai_client`` teruggeeft; genereer_* zijn gestubd


@pytest.fixture(autouse=True)
def _reset_crebo_namen_cache():
    """Voorkom dat de lru_cache van de crebo→naam-lookup tussen tests lekt.

    test_opleiding_namen monkeypatcht ``OPLEIDINGSNAMEN_PAD`` naar tijdelijke bestanden;
    zonder reset houdt een latere test (bv. opleidingen_boom) een lege/verkeerde lookup vast.
    """
    opleiding.laad_crebo_namen.cache_clear()
    yield
    opleiding.laad_crebo_namen.cache_clear()


class TelStore(SessieStore):
    """In-memory sessie-store die elke ``bewaar`` noteert en optioneel één vaste sessie laadt.

    Met ``vast`` geeft ``laad`` voor elke sid hetzelfde ``Sessie``-object terug: de test zet de
    begintoestand en leest na de request de (in-place) gemuteerde toestand af.
    """

    def __init__(self, vast: Sessie | None = None, **kw) -> None:
        super().__init__(":memory:", **kw)
        self.vast = vast
        self.bewaard: list[str] = []

    def laad(self, sid: str) -> Sessie | None:
        return self.vast if self.vast is not None else super().laad(sid)

    def bewaar(self, sid: str, sessie: Sessie) -> None:
        self.bewaard.append(sid)
        super().bewaar(sid, sessie)


@pytest.fixture
def validatie_db():
    """Lege, gemigreerde in-memory validatie-DB; seed via de ``conn``/``seed``-fixtures."""
    vdb = ValidatieDb(":memory:")
    with vdb.verbinding():
        pass  # migreert het schema
    yield vdb
    vdb.sluit()


@pytest.fixture
def conn(validatie_db):
    """De (gedeelde) verbinding van de in-memory validatie-DB."""
    with validatie_db.verbinding() as c:
        yield c


@pytest.fixture
def maak_deps(validatie_db):
    """Bouw een test-``AppDeps`` op de in-memory DB; ``sessie=`` zet een vaste sessie,
    overige keyword-argumenten overschrijven velden (bv. ``ai_client``, ``beheer_enabled``)."""
    stores: list[SessieStore] = []

    def _maak(sessie: Sessie | None = None, **kw) -> AppDeps:
        stores.append(TelStore(vast=sessie))
        velden = {
            "session_secret": "test-secret",
            "algemeen_wachtwoord": TEST_WACHTWOORD,
            "validatie_db": validatie_db,
            "sessie_store": stores[-1],
            "ai_client": lambda: NEP_CLIENT,
            "cookie_https_only": False,
        }
        velden.update(kw)
        return AppDeps(**velden)

    yield _maak
    for store in stores:
        store.sluit()


@pytest.fixture
def maak_client(maak_deps):
    """``maak_client(sessie=None, toegang=True, deps=None, **deps_velden)`` → ``TestClient``.

    Standaard al door de toegangspoort (gedeeld wachtwoord). De deps zijn bereikbaar via
    ``client.app.state.deps`` (bv. ``.sessie_store.bewaard``).
    """
    from fastapi.testclient import TestClient

    from app_fastapi.main import maak_app

    def _maak(sessie: Sessie | None = None, *, toegang: bool = True, deps=None, **kw):
        deps = deps or maak_deps(sessie, **kw)
        c = TestClient(maak_app(deps))
        if toegang:
            c.post("/toegang", data={"wachtwoord": deps.algemeen_wachtwoord})
        return c

    return _maak


@pytest.fixture
def client(maak_client):
    """``TestClient`` op een verse test-app, al door de toegangspoort."""
    return maak_client()


@pytest.fixture
def seed(conn, tmp_path):
    """Seed-helpers voor de in-memory DB: ``seed.oer(...)``, ``seed.mentor(...)``,
    ``seed.student(...)``. ``tekst=`` schrijft het OER-bestand (markdown) in ``tmp_path``."""

    class _Seed:
        map: Path = tmp_path

        def instelling(self, naam: str = "talland", display: str = "Talland College") -> int:
            return db.voeg_instelling_toe(conn, naam, display)

        def oer(
            self,
            opleiding: str = "Kok",
            *,
            crebo: str = "99001",
            cohort: str = "2025",
            leerweg: str = "BOL",
            instelling: str = "talland",
            display: str = "Talland College",
            tekst: str | None = None,
            geindexeerd: bool = True,
        ) -> int:
            inst = self.instelling(instelling, display)
            pad = tmp_path / f"{instelling}_{crebo}_{leerweg}_{cohort}_{opleiding}.md"
            if tekst is not None:
                pad.write_text(tekst, encoding="utf-8")
            oer_id = db.voeg_oer_document_toe(
                conn, inst, opleiding, crebo, cohort, leerweg, str(pad)
            )
            if geindexeerd:
                db.markeer_geindexeerd(conn, oer_id)
            return oer_id

        def mentor(self, naam: str = "Mentor Een", instelling: str = "talland") -> int:
            inst = self.instelling(instelling)
            return db.voeg_mentor_toe(conn, naam, hash_wachtwoord("Welkom123"), inst)

        def student(self, studentnummer: str, oer_id: int, mentor_id: int | None) -> int:
            oer = db.get_oer_document_by_id(conn, oer_id)
            return db.voeg_student_toe(
                conn, studentnummer, f"Student {studentnummer}", hash_wachtwoord("Welkom123"),
                oer["instelling_id"], oer_id, mentor_id, 17, "v", "1A", 0.6, 40.0, 60.0, 2.0,
                1.0, "vmbo", "zorg", False,
            )  # fmt: skip

    return _Seed()


@pytest.fixture
def stub_context(monkeypatch):
    """Vervang ``app_fastapi.main.laad_context`` door een stub die een ``ChatContext`` geeft.

    ``stub_context(systeem="SYS", labels=["l"], domeinen=[], melding="")`` stubt standaard ook
    de id-guard van ``/api/kies`` (``data.geldige_oer_ids``), zodat tests geen echte,
    geïndexeerde OER-id's nodig hebben; ``stub_guard=False`` laat de echte guard staan;
    ``bron_register`` zet het ``BronCatalogus.register()``-register van de context.
    Geeft de lijst terug waarin elke aanroep (oer_ids) wordt vastgelegd.
    """

    def _stub(
        systeem="SYS",
        labels=None,
        domeinen=None,
        oer_onleesbaar=False,
        melding="",
        stub_guard=True,
        bron_register=None,
    ):
        import app_fastapi.main as m
        from app_fastapi.context import ChatContext

        aanroepen: list[list[int]] = []

        def _laad(conn, oer_ids, *a, **k):
            aanroepen.append(list(oer_ids))
            return ChatContext(
                systeem,
                ["label"] if labels is None else labels,
                [] if domeinen is None else domeinen,
                oer_onleesbaar,
                melding,
                list(oer_ids),
                list(bron_register or []),
            )

        monkeypatch.setattr(m, "laad_context", _laad)
        if stub_guard:
            monkeypatch.setattr(m.data, "geldige_oer_ids", lambda conn, ids: list(ids)[:3])
        return aanroepen

    return _stub
