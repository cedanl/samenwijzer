from validatie_samenwijzer.chat import LAGE_RELEVANTIE_BERICHT, bouw_berichten


def test_bouw_berichten_zonder_chunks():
    history = []
    chunks = []
    berichten = bouw_berichten(
        chat_history=history,
        chunks=chunks,
        vraag="Hoeveel uren BPV?",
        opleiding="Verzorgende IG",
        instelling="Rijn IJssel",
    )
    # systeem + gebruiker
    assert berichten[0]["role"] == "user"
    assert "Hoeveel uren BPV?" in berichten[0]["content"]


def test_bouw_berichten_met_chunks():
    chunks = [
        {"tekst": "Minimaal 800 uur BPV.", "metadata": {"pagina": 14}, "distance": 0.2},
        {"tekst": "BPV wordt geregistreerd.", "metadata": {"pagina": 17}, "distance": 0.3},
    ]
    berichten = bouw_berichten(
        chat_history=[],
        chunks=chunks,
        vraag="Hoeveel uren?",
        opleiding="Verzorgende IG",
        instelling="Rijn IJssel",
    )
    content = berichten[0]["content"]
    assert "Minimaal 800 uur BPV." in content
    assert "BPV wordt geregistreerd." in content


def test_bouw_berichten_behoudt_history():
    history = [
        {"role": "user", "content": "Vraag 1"},
        {"role": "assistant", "content": "Antwoord 1"},
    ]
    berichten = bouw_berichten(
        chat_history=history,
        chunks=[],
        vraag="Vraag 2",
        opleiding="Kok",
        instelling="Da Vinci",
    )
    rollen = [b["role"] for b in berichten]
    assert rollen == ["user", "assistant", "user"]


def test_lage_relevantie_bericht_is_string():
    assert isinstance(LAGE_RELEVANTIE_BERICHT, str)
    assert len(LAGE_RELEVANTIE_BERICHT) > 10
