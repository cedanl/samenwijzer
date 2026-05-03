from validatie_samenwijzer.chat import LAGE_RELEVANTIE_BERICHT, bouw_berichten, bouw_systeem


def test_bouw_berichten_nieuwe_vraag():
    berichten = bouw_berichten([], "Hoeveel uren BPV?")
    assert berichten[0]["role"] == "user"
    assert berichten[0]["content"] == "Hoeveel uren BPV?"


def test_bouw_berichten_behoudt_history():
    history = [
        {"role": "user", "content": "Vraag 1"},
        {"role": "assistant", "content": "Antwoord 1"},
    ]
    berichten = bouw_berichten(history, "Vraag 2")
    rollen = [b["role"] for b in berichten]
    assert rollen == ["user", "assistant", "user"]
    assert berichten[-1]["content"] == "Vraag 2"


def test_bouw_systeem_bevat_oer_tekst():
    systeem = bouw_systeem("Dit is de OER-tekst.", "Verzorgende IG", "Rijn IJssel")
    assert "Verzorgende IG" in systeem
    assert "Rijn IJssel" in systeem
    assert "Dit is de OER-tekst." in systeem


def test_bouw_systeem_leeg_bij_geen_tekst():
    systeem = bouw_systeem("", "Kok", "Da Vinci")
    # Lege oer_tekst → systeem mag worden aangemaakt maar is inhoudsloos
    assert "Kok" in systeem


def test_lage_relevantie_bericht_is_string():
    assert isinstance(LAGE_RELEVANTIE_BERICHT, str)
    assert len(LAGE_RELEVANTIE_BERICHT) > 10
