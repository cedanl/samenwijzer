"""Tests voor Task 1: `/api/vraag` scoort op opgetelde gesprekstekst (niet alleen de laatste vraag).

De app draait op een test-``AppDeps`` (``tests/conftest.py``): de OER's staan in een geseede
in-memory validatie-DB en de begin-sessie zit vast in de test-store (``maak_client(sessie=s)``),
zodat de test de toestand na de request op ``s`` afleest — deterministisch en onafhankelijk van
de echte database.
"""

from __future__ import annotations

from app_fastapi.sessie import Sessie
from validatie_samenwijzer.gesprek import Gesprek


def _seed_kok_en_banketbakker(seed) -> tuple[int, int]:
    """Twee OER's van dezelfde instelling, zonder onderscheidend opleidingswoord in de teksten
    hieronder — een instellingsmatch alleen levert dus een gelijkspel (kies-modus, geen intake)."""
    return (
        seed.oer("Kok", crebo="11111", leerweg="BOL", cohort="2025"),
        seed.oer("Banketbakker", crebo="22222", leerweg="BBL", cohort="2024"),
    )


def test_vraag_accumuleert_eerdere_gebruikersbeurten(seed, maak_client):
    """Een fragment zonder eigen match ("en dan?") vindt kandidaten via de instelling die in
    een eerdere user-beurt genoemd is — en de kale vraag (niet de optelsom) blijft
    `wachtende_vraag`."""
    _seed_kok_en_banketbakker(seed)
    s = Sessie(
        toegang=True,
        gesprek=Gesprek.van_lijst([{"role": "user", "content": "Ik zit op Talland College"}]),
    )

    r = maak_client(s).post("/api/vraag", json={"vraag": "en dan?"})

    assert r.status_code == 200
    body = r.json()
    assert body["modus"] == "kies"
    assert len(body["opties"]) == 2
    # Kale nieuwe vraag, niet de concatenatie van historie + vraag.
    assert s.wachtende_vraag == "en dan?"


def test_vraag_zonder_historie_matcht_niet_op_fragment_alleen(seed, maak_client):
    """Eerste beurt (geen chat_history): hetzelfde fragment matcht op zichzelf niets → intake.
    Bewijst dat het kies-resultaat hierboven echt uit de historie komt, niet uit "en dan?" zelf."""
    _seed_kok_en_banketbakker(seed)

    r = maak_client(Sessie(toegang=True)).post("/api/vraag", json={"vraag": "en dan?"})

    assert r.status_code == 200
    assert r.json()["modus"] == "intake"


def test_vraag_accumuleert_naar_eenduidige_match_laadt_direct(seed, maak_client, stub_context):
    """Seeded historie + vervolgfragment lossen samen op tot precies 1 kandidaat → modus
    "chat" met `oer_ids` gezet, en de kies-state (`wachtende_vraag`/`kandidaten`) van een
    eerdere ronde wordt niet per ongeluk laten staan (regressie voor Finding 1)."""
    kok, _ = _seed_kok_en_banketbakker(seed)
    stub_context(systeem="PROMPT")

    s = Sessie(
        toegang=True,
        gesprek=Gesprek.van_lijst(
            [{"role": "user", "content": "Ik zit op Talland College, ik doe Kok"}]
        ),
        # Stale kies-state uit een eerdere ronde die deze beurt zou moeten opruimen.
        wachtende_vraag="oude vraag",
    )

    r = maak_client(s).post("/api/vraag", json={"vraag": "en dan?"})

    assert r.status_code == 200
    body = r.json()
    assert body["modus"] == "chat"
    assert body["oer_ids"] == [kok]
    assert s.wachtende_vraag is None


def test_vraag_met_al_geladen_oer_blijft_shortcut_nemen(maak_client, monkeypatch):
    """Bestaande shortcut (OER al geladen) blijft ongewijzigd: geen scoring, direct chat."""
    import app_fastapi.main as m

    def _boom(*a, **k):
        raise AssertionError("identificeer_oer_kandidaten mag niet aangeroepen worden")

    monkeypatch.setattr(m, "identificeer_oer_kandidaten", _boom)

    s = Sessie(
        toegang=True,
        oer_systeem="PROMPT",
        oer_labels=["Talland College · Kok · BOL 2025"],
        oer_onleesbaar=False,
        gesprek=Gesprek.van_lijst([{"role": "user", "content": "Ik zit op Talland College"}]),
    )

    r = maak_client(s).post("/api/vraag", json={"vraag": "hoe zit het met herkansen?"})

    assert r.status_code == 200
    body = r.json()
    assert body["modus"] == "chat"
    assert body["labels"] == ["Talland College · Kok · BOL 2025"]


def test_kies_beurt_telt_mee_bij_genegeerde_picker(seed, maak_client, stub_context):
    """Regressie voor de #243-follow-up: de kies-beurt zelf ontbrak in `chat_history`, dus als
    de gebruiker de picker negeert en verder typt, mist de accumulatie de kandidaten-context.

    Nagebouwd naar de echte catalogus: "tandartsassistent" alleen levert meerdere kandidaten op
    (vier instellingen, kies-modus). Zonder de kies-beurt-fix ziet de vervolgvraag "in Nijmegen"
    alleen zichzelf en matcht op instellingsnaam alleen (alle ROC Nijmegen-OER's, kies-modus
    opnieuw). Mét de fix telt "tandartsassistent" nog mee en resolveert de combinatie naar
    precies de ROC Nijmegen-tandartsassistent-OER.
    """
    for inst, display in (
        ("talland", "Talland College"),
        ("curio", "Curio"),
        ("davinci", "Da Vinci College"),
    ):
        seed.oer("Tandartsassistent", crebo="25699", instelling=inst, display=display)
    nijmegen = {"instelling": "rocnijmegen", "display": "ROC Nijmegen"}
    doel = seed.oer("Tandartsassistent", crebo="25699", **nijmegen)
    seed.oer("Kok", crebo="25180", **nijmegen)
    seed.oer("Verzorgende IG", crebo="25655", **nijmegen)
    stub_context(systeem="PROMPT")

    s = Sessie(toegang=True)
    c = maak_client(s)
    r1 = c.post("/api/vraag", json={"vraag": "tandartsassistent"})
    assert r1.json()["modus"] == "kies"
    assert len(r1.json()["opties"]) > 1
    # De kies-beurt moet nu ook zelf als user-turn in de historie staan.
    assert {"role": "user", "content": "tandartsassistent"} in s.gesprek.naar_lijst()

    r2 = c.post("/api/vraag", json={"vraag": "in Nijmegen"})
    body = r2.json()
    assert body["modus"] == "chat", body
    assert body["oer_ids"] == [doel]


def test_vraag_partiele_enkele_kandidaat_geeft_kies(seed, maak_client, stub_context):
    """Eén kandidaat die slechts partieel matcht (de genoemde school biedt de opleiding niet aan,
    een andere school wél) → modus "kies" i.p.v. stil de verkeerde studiegids laden."""
    aeres = seed.oer(
        "25915_BOL_2026__vakbekwaam-medewerker-paardensport",
        crebo="25915", cohort="2026", instelling="aeres", display="Aeres MBO",
    )  # fmt: skip
    seed.oer(
        "25916_BOL_2025__Bedrijfsleider_paardensport",
        crebo="25916", cohort="2025", instelling="landstede", display="Landstede MBO",
    )  # fmt: skip
    geladen = stub_context(systeem="P", labels=["l"])

    r = maak_client(Sessie(toegang=True)).post(
        "/api/vraag", json={"vraag": "Bedrijfsleider paardensport bij Aeres, BOL 2025"}
    )

    assert r.status_code == 200
    assert r.json()["modus"] == "kies"
    assert geladen == []
    assert [o["id"] for o in r.json()["opties"]] == [aeres]


def test_kies_opties_tonen_schone_opleidingsnaam(seed, maak_client):
    """Regressie: de picker toonde de ruwe `opleiding`-string (een bestandsnaam met crebo,
    leerweg en cohort erin) i.p.v. de opgeschoonde naam die `/api/kies` wél teruggeeft."""
    seed.oer("25182_BOL_2025__25182BOLExamenplan2025-Zelfstandig-kok", crebo="11111")
    seed.oer(
        "25168_BOL_2025__25168BOL2025Examenplan-Gastheer-vrouw",
        crebo="22222", leerweg="BBL", cohort="2024",
    )  # fmt: skip

    opties = maak_client().post("/api/vraag", json={"vraag": "Talland College"}).json()["opties"]

    assert opties, "verwacht kies-modus met opties"
    for optie in opties:
        assert "_BOL_" not in optie["label"], f"ruwe bestandsnaam lekt naar de UI: {optie['label']}"
        assert "Examenplan" not in optie["label"]
