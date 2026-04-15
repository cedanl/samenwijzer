"""Tests voor whatsapp_store, whatsapp en scheduler."""

import sqlite3
from datetime import date
from unittest.mock import patch

import pandas as pd
import pytest

# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def tmp_db(tmp_path, monkeypatch):
    """Gebruik een tijdelijke SQLite-database en sleutelbestand voor elke test."""
    db_pad = tmp_path / "whatsapp.db"
    key_pad = tmp_path / ".whatsapp.key"
    monkeypatch.setattr("samenwijzer.whatsapp_store._DB_PAD", db_pad)
    monkeypatch.setattr("samenwijzer.whatsapp_store._KEY_PAD", key_pad)
    monkeypatch.setattr("samenwijzer.whatsapp_store._geinitialiseerd", set())
    yield db_pad


# ── whatsapp_store ─────────────────────────────────────────────────────────────


class TestTelefoonnummerOpslag:
    def test_registreer_en_ophalen(self):
        from samenwijzer.whatsapp_store import get_registratie, registreer_nummer

        registreer_nummer("100001", "+31612345678")
        reg = get_registratie("100001")

        assert reg is not None
        assert reg.studentnummer == "100001"
        assert not reg.opt_in
        assert not reg.geactiveerd

    def test_activeren(self):
        from samenwijzer.whatsapp_store import activeer_nummer, get_registratie, registreer_nummer

        registreer_nummer("100001", "+31612345678")
        activeer_nummer("100001")
        reg = get_registratie("100001")

        assert reg.opt_in
        assert reg.geactiveerd

    def test_heeft_actieve_registratie_na_activatie(self):
        from samenwijzer.whatsapp_store import (
            activeer_nummer,
            heeft_actieve_registratie,
            registreer_nummer,
        )

        registreer_nummer("100001", "+31612345678")
        assert not heeft_actieve_registratie("100001")
        activeer_nummer("100001")
        assert heeft_actieve_registratie("100001")

    def test_deactiveren(self):
        from samenwijzer.whatsapp_store import (
            activeer_nummer,
            deactiveer_nummer,
            heeft_actieve_registratie,
            registreer_nummer,
        )

        registreer_nummer("100001", "+31612345678")
        activeer_nummer("100001")
        deactiveer_nummer("100001")
        assert not heeft_actieve_registratie("100001")

    def test_stop_bericht_deactiveert_via_telefoon(self):
        from samenwijzer.whatsapp_store import (
            activeer_nummer,
            deactiveer_nummer_via_telefoon,
            heeft_actieve_registratie,
            registreer_nummer,
        )

        registreer_nummer("100001", "+31612345678")
        activeer_nummer("100001")
        assert heeft_actieve_registratie("100001")

        resultaat = deactiveer_nummer_via_telefoon("+31612345678")
        assert resultaat is True
        assert not heeft_actieve_registratie("100001")

    def test_stop_onbekend_nummer_geeft_false(self):
        from samenwijzer.whatsapp_store import deactiveer_nummer_via_telefoon

        assert deactiveer_nummer_via_telefoon("+31699999999") is False

    def test_get_studentnummer_voor_telefoon(self):
        from samenwijzer.whatsapp_store import (
            get_studentnummer_voor_telefoon,
            registreer_nummer,
        )

        registreer_nummer("100002", "+31698765432")
        assert get_studentnummer_voor_telefoon("+31698765432") == "100002"
        assert get_studentnummer_voor_telefoon("+31699999999") is None

    def test_get_actieve_registraties(self):
        from samenwijzer.whatsapp_store import (
            activeer_nummer,
            get_actieve_registraties,
            registreer_nummer,
        )

        registreer_nummer("100001", "+31611111111")
        registreer_nummer("100002", "+31622222222")
        activeer_nummer("100001")  # alleen 100001 actief

        actief = get_actieve_registraties()
        snrs = [snr for snr, _ in actief]
        assert "100001" in snrs
        assert "100002" not in snrs

    def test_nummers_worden_versleuteld_bewaard(self, tmp_db):
        from samenwijzer.whatsapp_store import registreer_nummer

        registreer_nummer("100001", "+31612345678")
        conn = sqlite3.connect(tmp_db)
        rij = conn.execute(
            "SELECT nummer_enc FROM telefoon_registraties WHERE studentnummer='100001'"
        ).fetchone()
        conn.close()
        assert rij is not None
        assert rij[0] != "+31612345678"  # niet in plaintext opgeslagen


class TestGespreksSessies:
    def test_sessie_opslaan_en_ophalen(self):
        from samenwijzer.whatsapp_store import WhatsappSessie, get_sessie, sla_sessie_op

        sessie = WhatsappSessie(
            from_number="+31612345678",
            stap="verificatie",
            uitgewisseld=0,
            context_json="[]",
            gestart_op="2026-04-14",
        )
        sla_sessie_op(sessie)
        opgehaald = get_sessie("+31612345678")

        assert opgehaald is not None
        assert opgehaald.stap == "verificatie"
        assert opgehaald.uitgewisseld == 0

    def test_sessie_bijwerken(self):
        from samenwijzer.whatsapp_store import WhatsappSessie, get_sessie, sla_sessie_op

        sessie = WhatsappSessie("+31612345678", "ai_gesprek", 0, "[]", "2026-04-14")
        sla_sessie_op(sessie)
        sessie.uitgewisseld = 2
        sla_sessie_op(sessie)

        assert get_sessie("+31612345678").uitgewisseld == 2

    def test_sessie_verwijderen(self):
        from samenwijzer.whatsapp_store import (
            WhatsappSessie,
            get_sessie,
            sla_sessie_op,
            verwijder_sessie,
        )

        sla_sessie_op(WhatsappSessie("+31612345678", "ai_gesprek", 0, "[]", None))
        verwijder_sessie("+31612345678")
        assert get_sessie("+31612345678") is None

    def test_voeg_bericht_toe(self):
        from samenwijzer.whatsapp_store import WhatsappSessie

        sessie = WhatsappSessie("+31612345678", "ai_gesprek", 0, "[]", None)
        sessie.voeg_bericht_toe("student", "Mijn stage loopt niet lekker")
        ctx = sessie.context()

        assert len(ctx) == 1
        assert ctx[0]["rol"] == "student"
        assert sessie.uitgewisseld == 1


# ── whatsapp.parseer_antwoord ─────────────────────────────────────────────────


class TestParseerAntwoord:
    def test_score_1(self):
        from samenwijzer.whatsapp import parseer_antwoord

        r = parseer_antwoord("1")
        assert r.soort == "score"
        assert r.score == 1

    def test_score_3(self):
        from samenwijzer.whatsapp import parseer_antwoord

        r = parseer_antwoord("3")
        assert r.soort == "score"
        assert r.score == 3

    def test_stop_varianten(self):
        from samenwijzer.whatsapp import parseer_antwoord

        for woord in ["stop", "STOP", "stoppen", "afmelden"]:
            assert parseer_antwoord(woord).soort == "stop"

    def test_ja_varianten(self):
        from samenwijzer.whatsapp import parseer_antwoord

        for woord in ["ja", "JA", "Ja", "ok", "oke"]:
            assert parseer_antwoord(woord).soort == "ja"

    def test_lange_tekst(self):
        from samenwijzer.whatsapp import parseer_antwoord

        r = parseer_antwoord("Mijn stage loopt niet goed")
        assert r.soort == "tekst"

    def test_onbekend(self):
        from samenwijzer.whatsapp import parseer_antwoord

        assert parseer_antwoord("xyz").soort == "onbekend"


# ── whatsapp.verwerk_inkomend_bericht ─────────────────────────────────────────


class TestVerwerkInkomendBericht:
    DATUM = date(2026, 4, 14)
    NUMMER = "+31612345678"
    SNR = "100001"

    def _registreer_actief(self):
        from samenwijzer.whatsapp_store import activeer_nummer, registreer_nummer

        registreer_nummer(self.SNR, self.NUMMER)
        activeer_nummer(self.SNR)

    def test_score_1_geeft_positief_antwoord(self):
        from samenwijzer.whatsapp import verwerk_inkomend_bericht

        self._registreer_actief()
        resultaat = verwerk_inkomend_bericht(self.NUMMER, "1", self.DATUM)

        assert resultaat.antwoord_tekst is not None
        assert "💪" in resultaat.antwoord_tekst
        assert resultaat.welzijns_check is not None
        assert resultaat.welzijns_check.antwoord == 1

    def test_score_2_maakt_welzijnscheck_en_start_gesprek(self):
        from samenwijzer.whatsapp import verwerk_inkomend_bericht
        from samenwijzer.whatsapp_store import get_sessie

        self._registreer_actief()
        resultaat = verwerk_inkomend_bericht(self.NUMMER, "2", self.DATUM)

        assert resultaat.welzijns_check is not None
        assert resultaat.welzijns_check.antwoord == 2
        sessie = get_sessie(self.NUMMER)
        assert sessie is not None
        assert sessie.stap == "ai_gesprek"

    def test_score_3_maakt_welzijnscheck(self):
        from samenwijzer.whatsapp import verwerk_inkomend_bericht

        self._registreer_actief()
        resultaat = verwerk_inkomend_bericht(self.NUMMER, "3", self.DATUM)

        assert resultaat.welzijns_check.antwoord == 3

    def test_stop_deactiveert_nummer(self):
        from samenwijzer.whatsapp import verwerk_inkomend_bericht
        from samenwijzer.whatsapp_store import heeft_actieve_registratie

        self._registreer_actief()
        resultaat = verwerk_inkomend_bericht(self.NUMMER, "stop", self.DATUM)

        assert "afgemeld" in resultaat.antwoord_tekst.lower()
        assert not heeft_actieve_registratie(self.SNR)

    def test_verificatie_ja_activeert(self):
        from samenwijzer.whatsapp import verwerk_inkomend_bericht
        from samenwijzer.whatsapp_store import (
            WhatsappSessie,
            heeft_actieve_registratie,
            registreer_nummer,
            sla_sessie_op,
        )

        registreer_nummer(self.SNR, self.NUMMER)
        sla_sessie_op(WhatsappSessie(self.NUMMER, "verificatie", 0, "[]", "2026-04-14"))

        verwerk_inkomend_bericht(self.NUMMER, "ja", self.DATUM)
        assert heeft_actieve_registratie(self.SNR)

    def test_verificatie_nee_activeert_niet(self):
        from samenwijzer.whatsapp import verwerk_inkomend_bericht
        from samenwijzer.whatsapp_store import (
            WhatsappSessie,
            heeft_actieve_registratie,
            registreer_nummer,
            sla_sessie_op,
        )

        registreer_nummer(self.SNR, self.NUMMER)
        sla_sessie_op(WhatsappSessie(self.NUMMER, "verificatie", 0, "[]", "2026-04-14"))

        verwerk_inkomend_bericht(self.NUMMER, "nee", self.DATUM)
        assert not heeft_actieve_registratie(self.SNR)

    def test_ai_gesprek_limiet_geeft_doorverwijzing(self):
        from samenwijzer.whatsapp import MAX_EXCHANGES, verwerk_inkomend_bericht
        from samenwijzer.whatsapp_store import WhatsappSessie, sla_sessie_op

        self._registreer_actief()
        sla_sessie_op(WhatsappSessie(self.NUMMER, "ai_gesprek", MAX_EXCHANGES, "[]", "2026-04-14"))

        with patch("samenwijzer.whatsapp._genereer_ai_reactie", return_value="Test reactie"):
            resultaat = verwerk_inkomend_bericht(self.NUMMER, "het gaat slecht", self.DATUM)

        assert resultaat.antwoord_tekst is not None
        tekst = resultaat.antwoord_tekst.lower()
        assert "mentor" in tekst or "app" in tekst

    def test_ai_gesprek_telt_uitwisselingen(self):
        from samenwijzer.whatsapp import verwerk_inkomend_bericht
        from samenwijzer.whatsapp_store import WhatsappSessie, get_sessie, sla_sessie_op

        self._registreer_actief()
        sla_sessie_op(WhatsappSessie(self.NUMMER, "ai_gesprek", 0, "[]", "2026-04-14"))

        with patch("samenwijzer.whatsapp._genereer_ai_reactie", return_value="Hoe bedoel je dat?"):
            verwerk_inkomend_bericht(self.NUMMER, "mijn stage loopt niet lekker", self.DATUM)

        sessie = get_sessie(self.NUMMER)
        assert sessie is not None
        assert sessie.uitgewisseld >= 1


# ── scheduler ─────────────────────────────────────────────────────────────────


class TestScheduler:
    def _maak_df(self) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "studentnummer": ["100001", "100002"],
                "naam": ["Jan Jansen", "Emma de Vries"],
            }
        )

    def test_dry_run_verstuurt_niets(self):
        from samenwijzer.scheduler import stuur_wekelijkse_checkins
        from samenwijzer.whatsapp_store import activeer_nummer, registreer_nummer

        registreer_nummer("100001", "+31611111111")
        activeer_nummer("100001")

        with patch("samenwijzer.scheduler.stuur_checkin") as mock_stuur:
            resultaat = stuur_wekelijkse_checkins(self._maak_df(), dry_run=True)

        mock_stuur.assert_not_called()
        assert resultaat["verstuurd"] == 1

    def test_alleen_actieve_nummers_ontvangen_bericht(self):
        from samenwijzer.scheduler import stuur_wekelijkse_checkins
        from samenwijzer.whatsapp_store import activeer_nummer, registreer_nummer

        registreer_nummer("100001", "+31611111111")
        activeer_nummer("100001")
        registreer_nummer("100002", "+31622222222")  # niet geactiveerd

        with patch("samenwijzer.scheduler.stuur_checkin") as mock_stuur:
            stuur_wekelijkse_checkins(self._maak_df())

        assert mock_stuur.call_count == 1
        args = mock_stuur.call_args
        assert args.kwargs["naam"] == "Jan Jansen"

    def test_student_niet_in_dataset_wordt_overgeslagen(self):
        from samenwijzer.scheduler import stuur_wekelijkse_checkins
        from samenwijzer.whatsapp_store import activeer_nummer, registreer_nummer

        registreer_nummer("999999", "+31699999999")
        activeer_nummer("999999")

        with patch("samenwijzer.scheduler.stuur_checkin") as mock_stuur:
            resultaat = stuur_wekelijkse_checkins(self._maak_df())

        mock_stuur.assert_not_called()
        assert resultaat["overgeslagen"] == 1

    def test_geen_registraties_geeft_nul_verstuurd(self):
        from samenwijzer.scheduler import stuur_wekelijkse_checkins

        resultaat = stuur_wekelijkse_checkins(self._maak_df())
        assert resultaat["verstuurd"] == 0

    def test_twilio_fout_wordt_geteld(self):
        from samenwijzer.scheduler import stuur_wekelijkse_checkins
        from samenwijzer.whatsapp_store import activeer_nummer, registreer_nummer

        registreer_nummer("100001", "+31611111111")
        activeer_nummer("100001")

        with patch("samenwijzer.scheduler.stuur_checkin", side_effect=Exception("Twilio down")):
            resultaat = stuur_wekelijkse_checkins(self._maak_df())

        assert resultaat["fouten"] == 1
        assert resultaat["verstuurd"] == 0


# ── whatsapp.sla_whatsapp_gesprek_op / laad_whatsapp_gesprek ──────────────────


class TestGesprekOpslag:
    DATUM = date(2026, 4, 14)
    SNR = "100001"

    def test_opslaan_en_laden(self, tmp_path, monkeypatch):
        import samenwijzer.whatsapp as wa_mod

        monkeypatch.setattr(wa_mod, "_GESPREKKEN_PAD", tmp_path)

        context = [
            {"rol": "student", "tekst": "Het gaat niet goed met mij"},
            {"rol": "coach", "tekst": "Wat bedoel je precies?"},
        ]
        wa_mod.sla_whatsapp_gesprek_op(self.SNR, context, self.DATUM)

        geladen = wa_mod.laad_whatsapp_gesprek(self.SNR)
        assert geladen is not None
        assert geladen["studentnummer"] == self.SNR
        assert geladen["datum"] == "2026-04-14"
        assert len(geladen["gesprek"]) == 2

    def test_laden_zonder_bestand_geeft_none(self, tmp_path, monkeypatch):
        import samenwijzer.whatsapp as wa_mod

        monkeypatch.setattr(wa_mod, "_GESPREKKEN_PAD", tmp_path)
        assert wa_mod.laad_whatsapp_gesprek("999999") is None

    def test_gesprek_opgeslagen_bij_doorverwijzing(self, tmp_path, monkeypatch):
        import samenwijzer.whatsapp as wa_mod  # noqa: PLC0415
        from samenwijzer.whatsapp import MAX_EXCHANGES, verwerk_inkomend_bericht  # noqa: PLC0415
        from samenwijzer.whatsapp_store import (  # noqa: PLC0415
            WhatsappSessie,
            activeer_nummer,
            registreer_nummer,
            sla_sessie_op,
        )

        monkeypatch.setattr(wa_mod, "_GESPREKKEN_PAD", tmp_path)

        registreer_nummer(self.SNR, "+31612345678")
        activeer_nummer(self.SNR)
        sla_sessie_op(
            WhatsappSessie("+31612345678", "ai_gesprek", MAX_EXCHANGES, "[]", "2026-04-14")
        )

        with patch("samenwijzer.whatsapp._genereer_ai_reactie", return_value="Test reactie"):
            verwerk_inkomend_bericht("+31612345678", "het gaat slecht", self.DATUM)

        assert wa_mod.laad_whatsapp_gesprek(self.SNR) is not None
