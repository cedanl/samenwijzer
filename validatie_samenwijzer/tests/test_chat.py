import json
import sys
import types

from validatie_samenwijzer.chat import (
    LAGE_RELEVANTIE_BERICHT,
    bouw_berichten,
    bouw_gecombineerd_systeem,
    bouw_systeem,
    dedup_disclaimer,
    identificeer_oer_kandidaten,
    laad_instelling_bron_tekst,
    laad_kwalificatiedossier_tekst,
    laad_oer_tekst,
    laad_skills_tekst,
    pad_kwalificatiedossier,
    pad_skills,
    web_zoek_domeinen,
)


def _fake_pdfplumber(tekst: str):
    """Minimale pdfplumber-vervanger die één pagina met vaste tekst teruggeeft."""

    class _Page:
        def extract_text(self):
            return tekst

    class _PDF:
        pages = [_Page()]

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    return types.SimpleNamespace(open=lambda _p: _PDF())


def test_laad_oer_tekst_valt_terug_op_pdf_bij_leeg_md(tmp_path, monkeypatch):
    """Een leeg/whitespace-only .md-broertje mag de pdfplumber-fallback niet blokkeren
    (gescande PDF met mislukte markitdown-conversie)."""
    pdf = tmp_path / "25690_BOL_2025__MJP.pdf"
    pdf.write_bytes(b"%PDF-1.4 dummy")
    (tmp_path / "25690_BOL_2025__MJP.md").write_text("   \n", encoding="utf-8")
    monkeypatch.setitem(sys.modules, "pdfplumber", _fake_pdfplumber("Tekst uit de PDF"))

    assert laad_oer_tekst(pdf) == "Tekst uit de PDF"


def test_laad_oer_tekst_geeft_voorrang_aan_gevuld_md(tmp_path, monkeypatch):
    """Een gevuld .md-broertje wint van de PDF-fallback."""
    pdf = tmp_path / "25690_BOL_2025__MJP.pdf"
    pdf.write_bytes(b"%PDF-1.4 dummy")
    (tmp_path / "25690_BOL_2025__MJP.md").write_text("Echte MD-inhoud", encoding="utf-8")
    monkeypatch.setitem(sys.modules, "pdfplumber", _fake_pdfplumber("Mag niet gebruikt worden"))

    assert laad_oer_tekst(pdf) == "Echte MD-inhoud"


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


def test_bouw_berichten_filtert_lege_assistant_turn():
    # Een mislukte AI-call kan een lege assistant-turn achterlaten; die mag de
    # API niet bereiken (zou een 400 geven en de hele sessie blokkeren).
    history = [
        {"role": "user", "content": "Vraag 1"},
        {"role": "assistant", "content": ""},
    ]
    berichten = bouw_berichten(history, "Vraag 2")
    assert all(str(b["content"]).strip() for b in berichten)
    assert berichten == [{"role": "user", "content": "Vraag 2"}]


def test_bouw_berichten_vervangt_onbeantwoorde_user_turn():
    history = [
        {"role": "user", "content": "Vraag 1"},
        {"role": "assistant", "content": "Antwoord 1"},
        {"role": "user", "content": "Vraag 2"},  # onbeantwoord (stream faalde)
    ]
    berichten = bouw_berichten(history, "Vraag 3")
    rollen = [b["role"] for b in berichten]
    assert rollen == ["user", "assistant", "user"]
    assert berichten[-1]["content"] == "Vraag 3"


def test_bouw_berichten_cascade_blijft_geldig():
    # Twee mislukte beurten op rij: resultaat moet alternerend zijn en met user
    # beginnen, zonder lege content.
    history = [
        {"role": "user", "content": "Vraag 1"},
        {"role": "assistant", "content": ""},
        {"role": "user", "content": "Vraag 2"},
        {"role": "assistant", "content": ""},
    ]
    berichten = bouw_berichten(history, "Vraag 3")
    rollen = [b["role"] for b in berichten]
    assert berichten[0]["role"] == "user"
    assert all(rollen[i] != rollen[i + 1] for i in range(len(rollen) - 1))
    assert all(str(b["content"]).strip() for b in berichten)
    assert berichten[-1]["content"] == "Vraag 3"


def test_messages_met_cache_zet_breakpoint_op_laatste():
    from validatie_samenwijzer.chat import _messages_met_cache

    berichten = [
        {"role": "user", "content": "Vraag 1"},
        {"role": "assistant", "content": "Antwoord 1"},
        {"role": "user", "content": "Vraag 2"},
    ]
    resultaat = _messages_met_cache(berichten)
    # Alleen de laatste beurt krijgt een cache-breakpoint, in blok-vorm.
    assert resultaat[-1]["content"][0]["cache_control"] == {"type": "ephemeral", "ttl": "1h"}
    # Eerdere beurten blijven ongemoeid (platte string-content).
    assert resultaat[0]["content"] == "Vraag 1"


def test_bouw_systeem_bevat_oer_tekst():
    systeem = bouw_systeem("Dit is de OER-tekst.", "Verzorgende IG", "Rijn IJssel")
    assert "Verzorgende IG" in systeem
    assert "Rijn IJssel" in systeem
    assert "Dit is de OER-tekst." in systeem


def test_bouw_systeem_leeg_bij_geen_tekst():
    systeem = bouw_systeem("", "Kok", "Da Vinci")
    # Lege oer_tekst → systeem mag worden aangemaakt maar is inhoudsloos
    assert "Kok" in systeem


def test_bouw_systeem_schoont_ruwe_opleidingsnaam():
    """Een ruwe bestandsnaam-stem moet als leesbare naam in de prompt komen."""
    systeem = bouw_systeem(
        "OER-tekst",
        "25642_BBL_2025__25642BBL2025Examenplan-hairstylist-dame-cohort-2025",
        "Da Vinci",
        crebo="25642",
    )
    assert "Hairstylist Dame" in systeem
    assert "25642BBL2025Examenplan" not in systeem


def test_bouw_systeem_onleesbare_oer_gebruikt_kd_modus():
    systeem = bouw_systeem("", "Kok", "Da Vinci", dossier_tekst="KD-INHOUD-HIER", crebo="25180")
    assert "KD-INHOUD-HIER" in systeem  # KD-blok aanwezig
    assert "niet machine-leesbaar" in systeem  # onleesbaar-modus framing
    assert "Dit is het leidende, schoolspecifieke document" not in systeem  # normale framing weg


def test_bouw_systeem_leesbare_oer_blijft_normale_modus():
    systeem = bouw_systeem("ECHTE OER-TEKST", "Kok", "Da Vinci", dossier_tekst="KD", crebo="25180")
    assert "ECHTE OER-TEKST" in systeem
    assert "Dit is het leidende, schoolspecifieke document" in systeem  # normale framing
    assert "niet machine-leesbaar" not in systeem


def test_bouw_systeem_bevat_doelgroep_instructie_naast_citatieplicht():
    """De MBO niveau 1-4-uitleg staat in de prompt, NAAST de woordelijke citatieplicht."""
    systeem = bouw_systeem("OER-tekst", "Kok", "Da Vinci")
    assert "DOELGROEP & TOON" in systeem
    assert "niveau 1 t/m 4" in systeem
    assert "In gewone taal:" in systeem
    # De citatieplicht blijft onverkort gelden (uitleg vervangt het citaat niet).
    assert "WOORDELIJK citeren" in systeem
    assert "verander een citaat NOOIT" in systeem


def test_bouw_gecombineerd_meervoudig_bevat_doelgroep_instructie():
    oers = [
        _oer_item(tekst="Tekst A", opleiding="Kok", display_naam="Da Vinci"),
        _oer_item(tekst="Tekst B", opleiding="Verzorgende IG", display_naam="Rijn IJssel"),
    ]
    systeem = bouw_gecombineerd_systeem(oers)
    assert "DOELGROEP & TOON" in systeem
    assert "niveau 1 t/m 4" in systeem


def test_lage_relevantie_bericht_is_string():
    assert isinstance(LAGE_RELEVANTIE_BERICHT, str)
    assert len(LAGE_RELEVANTIE_BERICHT) > 10


# ── Webzoek-fallback (graceful degradation) ───────────────────────────────────


def test_web_zoek_domeinen_mapt_dedupt_en_sorteert():
    items = [{"naam": "utrecht"}, {"naam": "davinci"}, {"naam": "davinci"}]
    assert web_zoek_domeinen(items) == ["davinci.nl", "mboutrecht.nl"]


def test_web_zoek_domeinen_negeert_onbekende_instelling():
    assert web_zoek_domeinen([{"naam": "onbekend"}, {}]) == []


def test_elke_instelling_heeft_web_domein():
    """Guard: elke onboardde instelling moet een web-search-domein hebben.

    Anders krijgen studenten van die instelling stil geen webzoek-fallback naar de
    eigen schoolsite (graceful degradation) als het antwoord niet in de documenten staat.
    """
    from validatie_samenwijzer.chat import _INSTELLING_DOMEINEN
    from validatie_samenwijzer.ingest import _INSTELLINGEN

    ontbreekt = set(_INSTELLINGEN) - set(_INSTELLING_DOMEINEN)
    assert not ontbreekt, f"Instellingen zonder web-search-domein: {sorted(ontbreekt)}"


def test_bouw_systeem_web_zoeken_voegt_instructie_en_disclaimer_toe():
    met = bouw_systeem("OER", "Kok", "Da Vinci", web_zoeken=True)
    assert "WEBZOEKEN" in met
    assert "officiële website van de instelling" in met
    assert "dit staat niet in de officiële studiegids" in met


def test_bouw_systeem_zonder_web_zoeken_heeft_geen_webblok():
    zonder = bouw_systeem("OER", "Kok", "Da Vinci")
    assert "WEBZOEKEN" not in zonder


def test_bouw_systeem_vacatures_voegt_blok_toe():
    met = bouw_systeem("OER-tekst", "Kok", "Da Vinci", leerweg="BOL", vacatures=True)
    zonder = bouw_systeem("OER-tekst", "Kok", "Da Vinci", leerweg="BOL")
    assert "VACATURES & STAGES" in met
    assert "VACATURES & STAGES" not in zonder


def test_bouw_systeem_vacatures_blok_bevat_niveau_en_locatie():
    met = bouw_systeem("OER-tekst", "Kok", "Da Vinci", leerweg="BOL", vacatures=True)
    assert "MBO-NIVEAU" in met  # zoekt op opleidingsniveau (uit de OER/KD-tekst)
    assert "±10 km" in met and "LOCATIE" in met  # vraagt om plaats + straal


def test_bouw_systeem_vacatures_blok_eist_klikbare_links():
    met = bouw_systeem("OER-tekst", "Kok", "Da Vinci", leerweg="BOL", vacatures=True)
    assert "klikbare Markdown-link" in met  # elk resultaat klikbaar
    assert "verzin NOOIT een URL" in met  # geen gefabriceerde links


_DISC = "⚠️ Let op: externe bron."


def test_dedup_disclaimer_laat_enkel_voorkomen_ongemoeid():
    chunks = ["Hallo ", _DISC, " en de rest"]
    assert "".join(dedup_disclaimer(chunks, _DISC)) == f"Hallo {_DISC} en de rest"


def test_dedup_disclaimer_verwijdert_herhaling():
    chunks = [_DISC, " tussentekst ", _DISC, " slot"]
    # Eerste blijft, tweede weg.
    assert "".join(dedup_disclaimer(chunks, _DISC)) == f"{_DISC} tussentekst  slot"


def test_dedup_disclaimer_herhaling_gesplitst_over_chunks():
    # De tweede disclaimer arriveert in stukjes verdeeld over meerdere chunks.
    mid = len(_DISC) // 2
    chunks = [_DISC, " x ", _DISC[:mid], _DISC[mid:], " y"]
    assert "".join(dedup_disclaimer(chunks, _DISC)) == f"{_DISC} x  y"


def test_dedup_disclaimer_zonder_voorkomen_is_passthrough():
    chunks = ["geen ", "disclaimer ", "hier"]
    assert "".join(dedup_disclaimer(chunks, _DISC)) == "geen disclaimer hier"


def test_bouw_systeem_leerweg_in_prompt():
    systeem = bouw_systeem("OER-tekst", "Kok", "Da Vinci", leerweg="BOL")
    assert "Leerweg van deze opleiding: BOL" in systeem


def test_bouw_systeem_zonder_leerweg_geen_leerweg_regel():
    systeem = bouw_systeem("OER-tekst", "Kok", "Da Vinci")
    assert "Leerweg van deze opleiding" not in systeem


def _vac_items():
    return [
        {"tekst": "OER A", "opleiding": "Kok", "display_naam": "Da Vinci",
         "leerweg": "BOL", "cohort": "2025", "crebo": "25180"},
        {"tekst": "OER B", "opleiding": "Kapper", "display_naam": "Rijn IJssel",
         "leerweg": "BBL", "cohort": "2025", "crebo": "25201"},
    ]


def test_bouw_gecombineerd_systeem_vacatures_multi():
    items = _vac_items()
    assert "VACATURES & STAGES" in bouw_gecombineerd_systeem(items, vacatures=True)
    assert "VACATURES & STAGES" not in bouw_gecombineerd_systeem(items)


def test_bouw_gecombineerd_systeem_vacatures_single_delegeert_met_leerweg():
    items = [{"tekst": "OER A", "opleiding": "Kok", "display_naam": "Da Vinci",
              "leerweg": "BBL", "cohort": "2025", "crebo": "25180"}]
    systeem = bouw_gecombineerd_systeem(items, vacatures=True)
    assert "VACATURES & STAGES" in systeem
    assert "Leerweg van deze opleiding: BBL" in systeem


def test_bouw_gecombineerd_systeem_meervoudig_web_zoeken():
    items = [
        {
            "tekst": "A",
            "opleiding": "Kok",
            "display_naam": "Da Vinci",
            "leerweg": "BOL",
            "cohort": "2025",
        },
        {
            "tekst": "B",
            "opleiding": "Kapper",
            "display_naam": "Rijn IJssel",
            "leerweg": "BBL",
            "cohort": "2025",
        },
    ]
    assert "WEBZOEKEN" in bouw_gecombineerd_systeem(items, web_zoeken=True)
    assert "WEBZOEKEN" not in bouw_gecombineerd_systeem(items)


# ── bouw_gecombineerd_systeem ─────────────────────────────────────────────────


def _oer_item(**overrides):
    base = {
        "tekst": "OER-inhoud",
        "opleiding": "Verzorgende IG",
        "display_naam": "Rijn IJssel",
        "leerweg": "BOL",
        "cohort": "2025",
    }
    return {**base, **overrides}


def test_bouw_gecombineerd_systeem_enkel_delegeert_naar_bouw_systeem():
    item = _oer_item(tekst="Tekst A", opleiding="Kok", display_naam="Da Vinci")
    systeem = bouw_gecombineerd_systeem([item])
    # De single-OER-delegatie geeft nu ook de leerweg door (item["leerweg"] == "BOL").
    assert systeem == bouw_systeem("Tekst A", "Kok", "Da Vinci", leerweg="BOL")


def test_bouw_gecombineerd_systeem_meervoudig_bevat_alle_oers():
    items = [
        _oer_item(tekst="Tekst A", opleiding="Kok", display_naam="Da Vinci"),
        _oer_item(tekst="Tekst B", opleiding="Verzorgende IG", display_naam="Rijn IJssel"),
    ]
    systeem = bouw_gecombineerd_systeem(items)
    assert "OER 1" in systeem and "OER 2" in systeem
    assert "Tekst A" in systeem and "Tekst B" in systeem
    assert "Da Vinci" in systeem and "Rijn IJssel" in systeem
    assert "Kok" in systeem and "Verzorgende IG" in systeem


def test_bouw_gecombineerd_meervoudig_neemt_oer_loos_item_op_via_kd():
    items = [
        _oer_item(tekst="ECHTE OER 1", opleiding="Kok", display_naam="Da Vinci"),
        _oer_item(
            tekst="",  # onleesbare OER
            opleiding="Gastheer",
            display_naam="Da Vinci",
            leerweg="BBL",
            crebo="25168",
            dossier_tekst="KD-GASTHEER-INHOUD",
        ),
    ]
    systeem = bouw_gecombineerd_systeem(items)
    assert "ECHTE OER 1" in systeem
    assert "KD-GASTHEER-INHOUD" in systeem  # OER-loos item tóch opgenomen via KD
    assert "niet machine-leesbaar" in systeem  # notitie bij het OER-loze blok


# ── identificeer_oer_kandidaten ───────────────────────────────────────────────


def _oer_row(**overrides):
    base = {
        "id": 1,
        "opleiding": "Verzorgende IG",
        "display_naam": "Rijn IJssel",
        "leerweg": "BOL",
        "cohort": "2025",
        "crebo": "25655",
        "bestandspad": "oeren/x.pdf",
    }
    return {**base, **overrides}


def test_identificeer_crebo_geeft_hoogste_score():
    oers = [
        _oer_row(id=1, crebo="25655"),
        _oer_row(id=2, crebo="25170"),
    ]
    resultaat = identificeer_oer_kandidaten(oers, "Ik zoek info over crebo 25655")
    assert resultaat[0]["id"] == 1
    assert resultaat[0]["_score"] >= 3


def test_identificeer_leerweg_en_cohort_tellen_mee():
    oers = [_oer_row(leerweg="BOL", cohort="2025")]
    resultaat = identificeer_oer_kandidaten(oers, "BOL 2025 informatie graag")
    # leerweg (+2) + cohort (+2) = 4
    assert resultaat[0]["_score"] >= 4


def test_identificeer_leerweg_case_insensitive():
    oers = [_oer_row(leerweg="BBL")]
    resultaat = identificeer_oer_kandidaten(oers, "ik volg de bbl-route")
    assert resultaat[0]["_score"] >= 2


def test_identificeer_expliciete_instelling_wint_bij_gelijk_crebo():
    """Een genoemde instelling overstemt de OER van een ándere instelling met
    hetzelfde crebo maar een 'schonere' (los geschreven) opleidingsnaam (kwic-bug)."""
    oers = [
        # kwic: opleidingsnaam aaneengeplakt in de bestandsnaam → matcht geen losse woorden
        _oer_row(
            id=1,
            naam="kwic",
            display_naam="Koning Willem I College",
            crebo="25122",
            opleiding="25122_BBL_2025__Examenplan_25122Werkvoorbereiderfabricage",
        ),
        # talland: nette losse opleidingsnaam → scoort op opleidingswoorden
        _oer_row(
            id=2,
            naam="talland",
            display_naam="Talland",
            crebo="25122",
            opleiding="2021 - 25122 VG OER Werkvoorbereider fabricage",
        ),
    ]
    for vraag in (
        "Werkvoorbereider fabricage bij kwic",
        "Werkvoorbereider fabricage Koning Willem",
    ):
        resultaat = identificeer_oer_kandidaten(oers, vraag, min_score=1)
        assert resultaat[0]["id"] == 1, vraag


def test_identificeer_instelling_alias_kw1c():
    """De merknaam-afkorting 'KW1C' (niet af te leiden uit sleutel 'kwic') matcht via alias."""
    oers = [
        _oer_row(
            id=1,
            naam="kwic",
            display_naam="Koning Willem I College",
            crebo="25122",
            opleiding="25122_BBL_2025__Examenplan_25122Werkvoorbereiderfabricage",
        ),
        _oer_row(
            id=2,
            naam="talland",
            display_naam="Talland",
            crebo="25122",
            opleiding="2021 - 25122 VG OER Werkvoorbereider fabricage",
        ),
    ]
    resultaat = identificeer_oer_kandidaten(oers, "KW1C werkvoorbereider fabricage", min_score=1)
    assert resultaat[0]["id"] == 1


def test_identificeer_opleiding_filtert_instelling_only_matches_weg():
    """Vraag noemt instelling + opleiding → alleen de opleiding-OER's van die instelling.

    Regressie: 'software developer bij Graafschap' leverde voorheen álle Graafschap-OER's
    op (instellingsmatch +3 op elke OER). Nu vallen de OER's zónder identiteitssignaal
    (geen crebo/opleidingswoord-match) binnen die instelling weg.
    """
    oers = [
        _oer_row(
            id=1,
            naam="graafschap",
            display_naam="Graafschap College",
            crebo="25998",
            opleiding="25998 Software developer BOL 2025",
        ),
        _oer_row(
            id=2,
            naam="graafschap",
            display_naam="Graafschap College",
            crebo="25999",
            opleiding="25999 Medewerker ICT BOL 2025",
        ),
        _oer_row(
            id=3,
            naam="graafschap",
            display_naam="Graafschap College",
            crebo="27016",
            opleiding="27016 ICT system engineer BBL 2025",
        ),
    ]
    resultaat = identificeer_oer_kandidaten(oers, "software developer bij Graafschap", min_score=1)
    assert [r["id"] for r in resultaat] == [1]


def test_identificeer_genoemde_instelling_filtert_andere_scholen_weg():
    """Vraag noemt een instelling → OER's van ándere scholen vallen weg.

    Regressie: 'software developer bij Graafschap' leverde ook de software-developer-OER's
    van Curio/Deltion/ROC Utrecht op (opleidingswoord-match +2). Een publieke 'welke
    studiegids is van jou'-vraag hoort alleen de genoemde school te tonen.
    """
    oers = [
        _oer_row(
            id=1,
            naam="graafschap",
            display_naam="Graafschap College",
            crebo="25998",
            opleiding="25998 Software developer BOL 2025",
        ),
        _oer_row(
            id=2,
            naam="curio",
            display_naam="Curio",
            crebo="25998",
            opleiding="25998 Software developer BOL 2025",
        ),
        _oer_row(
            id=3,
            naam="utrecht",
            display_naam="ROC Utrecht",
            crebo="25998",
            opleiding="Software developer",
        ),
    ]
    resultaat = identificeer_oer_kandidaten(oers, "software developer bij Graafschap", min_score=1)
    assert [r["id"] for r in resultaat] == [1]


def test_identificeer_zonder_instelling_blijven_alle_scholen():
    """Geen instelling genoemd → opleiding-match over alle scholen blijft staan."""
    oers = [
        _oer_row(
            id=1,
            naam="graafschap",
            display_naam="Graafschap College",
            crebo="25998",
            opleiding="25998 Software developer BOL 2025",
        ),
        _oer_row(
            id=2,
            naam="curio",
            display_naam="Curio",
            crebo="25998",
            opleiding="25998 Software developer BOL 2025",
        ),
    ]
    resultaat = identificeer_oer_kandidaten(oers, "software developer", min_score=1)
    assert {r["id"] for r in resultaat} == {1, 2}


def test_identificeer_kale_instelling_houdt_hele_groep():
    """Kale instellingsvraag (geen opleiding) → toon alle OER's van die instelling."""
    oers = [
        _oer_row(
            id=1,
            naam="graafschap",
            display_naam="Graafschap College",
            crebo="25998",
            opleiding="25998 Software developer BOL 2025",
        ),
        _oer_row(
            id=2,
            naam="graafschap",
            display_naam="Graafschap College",
            crebo="25999",
            opleiding="25999 Medewerker ICT BOL 2025",
        ),
    ]
    resultaat = identificeer_oer_kandidaten(oers, "iets over Graafschap", min_score=1)
    assert {r["id"] for r in resultaat} == {1, 2}


def test_identificeer_instellingsslug_in_opleiding_telt_niet_als_identiteit():
    """De instellingsnaam in de bestandsnaam mag geen opleiding-identiteit geven.

    Regressie (Talland-naamgeving): de opleiding-strings embedden de instellingsslug
    ('..._talland-Business-Services'), waardoor het query-woord 'Talland' als
    opleidingswoord matchte op élke OER → identiteit +1 op alle 206, zodat de
    opleidingsfilter niets meer wegfilterde. De instellingsnaam is het instelling-signaal,
    niet het opleiding-signaal; 'assistent bij Talland' hoort alleen de assistent-OER over
    te houden, niet ook Business-Services.
    """
    oers = [
        _oer_row(
            id=1,
            naam="talland",
            display_naam="Talland College",
            crebo="25742",
            opleiding="25742_BOL_2025__talland-Assistent-horeca-voeding",
        ),
        _oer_row(
            id=2,
            naam="talland",
            display_naam="Talland College",
            crebo="23296",
            opleiding="23296_BOL_2025__talland-Business-Services",
        ),
    ]
    resultaat = identificeer_oer_kandidaten(oers, "assistent bij Talland College", min_score=1)
    assert [r["id"] for r in resultaat] == [1]


def test_identificeer_houdt_alleen_sterkste_opleiding_tier_per_instelling():
    """Binnen een school overstemt de sterkste opleiding-match de zwakkere.

    'assistent horeca bij Talland' matcht 'Assistent-horeca' (twee woorden, identiteit 2)
    sterker dan een OER met losse 'assistent' of losse 'horeca' (identiteit 1). Alleen de
    top-tier blijft staan; gelijke top-tiers blijven samen in beeld (gelijkspel-dropdown).
    """
    oers = [
        _oer_row(
            id=1,
            naam="talland",
            display_naam="Talland College",
            crebo="25742",
            opleiding="25742_BOL_2025__talland-Assistent-horeca-voeding",
        ),
        _oer_row(
            id=2,
            naam="talland",
            display_naam="Talland College",
            crebo="25184",
            opleiding="25184_BOL_2025__talland-Managerondernemer-horeca",
        ),
        _oer_row(
            id=3,
            naam="talland",
            display_naam="Talland College",
            crebo="25741",
            opleiding="25741_BOL_2025__talland-Assistent-dienstverlening-Entree",
        ),
    ]
    resultaat = identificeer_oer_kandidaten(
        oers, "assistent horeca bij Talland College", min_score=1
    )
    assert [r["id"] for r in resultaat] == [1]


def test_identificeer_gelijke_top_tier_blijven_samen():
    """Twee opleidingen met dezelfde (hoogste) identiteit blijven beide staan."""
    oers = [
        _oer_row(
            id=1,
            naam="talland",
            display_naam="Talland College",
            crebo="25742",
            opleiding="25742_BOL_2025__talland-Assistent-horeca-voeding",
        ),
        _oer_row(
            id=2,
            naam="talland",
            display_naam="Talland College",
            crebo="25742",
            opleiding="25742_BBL_2025__talland-Assistent-horeca-voeding",
        ),
    ]
    resultaat = identificeer_oer_kandidaten(
        oers, "assistent horeca bij Talland College", min_score=1
    )
    assert {r["id"] for r in resultaat} == {1, 2}


# ── kwalificatiedossier ───────────────────────────────────────────────────────


def test_bouw_systeem_met_dossier_bevat_beide_bronnen():
    systeem = bouw_systeem(
        "OER-tekst hier.",
        "Kok",
        "Da Vinci",
        dossier_tekst="Kerntaak 1: bereid maaltijden.",
        crebo="25180",
    )
    assert "OER-tekst hier." in systeem
    assert "Kerntaak 1: bereid maaltijden." in systeem
    assert "KWALIFICATIEDOSSIER" in systeem
    assert "25180" in systeem


def test_bouw_systeem_zonder_dossier_heeft_geen_kd_blok():
    systeem = bouw_systeem("OER-tekst", "Kok", "Da Vinci")
    assert "KWALIFICATIEDOSSIER" not in systeem


def test_bouw_systeem_met_instelling_bron_bevat_blok():
    systeem = bouw_systeem(
        "OER-tekst",
        "ICT",
        "Rijn IJssel",
        instelling_bronnen=[("Examenreglement", "Artikel 6.3: één herkansing.")],
    )
    assert "=== EXAMENREGLEMENT (Rijn IJssel) ===" in systeem
    assert "Artikel 6.3: één herkansing." in systeem


def test_bouw_systeem_instelling_citatie_onderscheidt_van_oer():
    """De citatie-instructie moet de regeling als aparte bron behandelen, niet als de OER."""
    systeem = bouw_systeem("OER-tekst", "ICT", "Rijn IJssel")
    assert "Volgens het Examenreglement" in systeem
    assert 'citeer een regeling NOOIT als "de OER"' in systeem


def test_citatieplicht_eist_markdown_blockquote():
    """Het woordelijk citaat moet als markdown-blockquote (eigen regel met '> ')
    worden opgemaakt, zodat de .chat-antwoord blockquote-CSS het als pull-quote
    rendert. Geldt voor zowel de single- als de multi-OER-systeemprompt."""
    single = bouw_systeem("OER-tekst", "ICT", "Rijn IJssel")
    multi = bouw_gecombineerd_systeem(
        [_oer_item(tekst="A", display_naam="X"), _oer_item(tekst="B", display_naam="Y")]
    )
    for systeem in (single, multi):
        assert "markdown-blockquote" in systeem
        assert '> "' in systeem


def test_bouw_systeem_zonder_instelling_bron_geen_blok():
    systeem = bouw_systeem("OER-tekst", "Kok", "Da Vinci")
    assert "=== EXAMENREGLEMENT" not in systeem
    assert "=== BEGELEIDINGS" not in systeem


def test_bouw_systeem_lege_instelling_bron_tekst_geen_blok():
    systeem = bouw_systeem(
        "OER-tekst", "Kok", "Da Vinci", instelling_bronnen=[("Examenreglement", "")]
    )
    assert "=== EXAMENREGLEMENT" not in systeem


def test_bouw_systeem_meerdere_instelling_bronnen():
    systeem = bouw_systeem(
        "OER-tekst",
        "ICT",
        "Rijn IJssel",
        instelling_bronnen=[
            ("Examenreglement", "reglement-tekst"),
            ("Begeleidings- en welzijnsbeleid", "beleid-tekst"),
        ],
    )
    assert "=== EXAMENREGLEMENT (Rijn IJssel) ===" in systeem
    assert "=== BEGELEIDINGS- EN WELZIJNSBELEID (Rijn IJssel) ===" in systeem
    assert "reglement-tekst" in systeem
    assert "beleid-tekst" in systeem


def test_bouw_gecombineerd_systeem_includeert_instelling_bron_per_oer():
    items = [
        {
            "tekst": "OER A",
            "opleiding": "ICT",
            "display_naam": "Rijn IJssel",
            "leerweg": "BOL",
            "cohort": "2025",
            "instelling_bronnen": [("Examenreglement", "reglement A")],
        },
        {
            "tekst": "OER B",
            "opleiding": "Kok",
            "display_naam": "Da Vinci",
            "leerweg": "BBL",
            "cohort": "2025",
        },
    ]
    systeem = bouw_gecombineerd_systeem(items)
    assert "EXAMENREGLEMENT 1 (Rijn IJssel)" in systeem
    assert "reglement A" in systeem


def test_laad_instelling_bron_leeg_zonder_pad():
    assert laad_instelling_bron_tekst(None) == ""
    assert laad_instelling_bron_tekst("") == ""


def test_laad_instelling_bron_leest_bestaande_md(tmp_path):
    md = tmp_path / "examenreglement.md"
    md.write_text("Artikel 6.3 Herkansingen: ten hoogste één herkansing.", encoding="utf-8")
    assert "Herkansingen" in laad_instelling_bron_tekst(md)
    assert "Herkansingen" in laad_instelling_bron_tekst(str(md))


def test_laad_instelling_bron_leeg_bij_ontbrekend_bestand(tmp_path):
    assert laad_instelling_bron_tekst(tmp_path / "bestaat_niet.pdf") == ""


def test_laad_instelling_bron_cap(tmp_path, monkeypatch):
    import validatie_samenwijzer.chat as chat_mod

    monkeypatch.setattr(chat_mod, "_MAX_INSTELLING_TEKST_TEKENS", 10)
    md = tmp_path / "begeleidingsbeleid.md"
    md.write_text("x" * 100, encoding="utf-8")
    assert len(laad_instelling_bron_tekst(md)) == 10


def test_laad_kwalificatiedossier_leeg_zonder_crebo():
    assert laad_kwalificatiedossier_tekst(None) == ""
    assert laad_kwalificatiedossier_tekst("") == ""


def test_laad_kwalificatiedossier_leest_bestaande_md(tmp_path, monkeypatch):
    monkeypatch.setenv("KWALDOSSIERS_PAD", str(tmp_path))
    (tmp_path / "12345.md").write_text("Dossier-inhoud voor crebo 12345.")
    assert "Dossier-inhoud" in laad_kwalificatiedossier_tekst("12345")


def test_pad_kwalificatiedossier_respecteert_env(tmp_path, monkeypatch):
    monkeypatch.setenv("KWALDOSSIERS_PAD", str(tmp_path))
    assert pad_kwalificatiedossier("99999") == tmp_path / "99999.md"


def test_bouw_gecombineerd_systeem_includeert_dossier_per_oer():
    items = [
        {
            "tekst": "OER A",
            "opleiding": "Kok",
            "display_naam": "Da Vinci",
            "leerweg": "BOL",
            "cohort": "2025",
            "crebo": "25180",
            "dossier_tekst": "KD-tekst voor Kok.",
        },
        {
            "tekst": "OER B",
            "opleiding": "Verzorgende IG",
            "display_naam": "Rijn IJssel",
            "leerweg": "BOL",
            "cohort": "2025",
        },
    ]
    systeem = bouw_gecombineerd_systeem(items)
    assert "KD-tekst voor Kok." in systeem
    assert "KWALIFICATIEDOSSIER 1" in systeem
    assert "25180" in systeem
    # tweede OER heeft geen dossier — geen KD 2 blok
    assert "KWALIFICATIEDOSSIER 2" not in systeem


# ── skills-taxonomie ──────────────────────────────────────────────────────────


def _schrijf_skills(tmp_path, crebo, beroep="kok", skills=None):
    data = {
        "crebo": crebo,
        "opleiding": "OER Kok",
        "bron": "ESCO",
        "beroep": None if beroep is None else {"label": beroep, "uri": "u", "definitie": "Koks..."},
        "match_methode": "llm-keuze",
        "kandidaten": [],
        "skills": skills
        if skills is not None
        else [{"label": "kooktechnieken gebruiken", "uri": "u1", "categorie": "essentieel"}],
    }
    (tmp_path / f"{crebo}.json").write_text(json.dumps(data), encoding="utf-8")


def test_pad_skills_respecteert_env(tmp_path, monkeypatch):
    monkeypatch.setenv("SKILLS_PAD", str(tmp_path))
    assert pad_skills("25180") == tmp_path / "25180.json"


def test_laad_skills_leeg_zonder_crebo():
    assert laad_skills_tekst(None) == ""
    assert laad_skills_tekst("") == ""


def test_laad_skills_formatteert_blok(tmp_path, monkeypatch):
    monkeypatch.setenv("SKILLS_PAD", str(tmp_path))
    _schrijf_skills(tmp_path, "25180")
    blok = laad_skills_tekst("25180")
    assert "SKILLS-TAXONOMIE (ESCO)" in blok
    assert "kok" in blok
    assert "kooktechnieken gebruiken" in blok
    assert "Essentiële skills" in blok


def test_laad_skills_toont_belangrijk_categorie(tmp_path, monkeypatch):
    """CompetentNL-bron levert een 'belangrijk'-categorie naast essentieel."""
    monkeypatch.setenv("SKILLS_PAD", str(tmp_path))
    skills = [
        {"label": "Samenwerken", "uri": "u1", "categorie": "essentieel"},
        {"label": "Engels spreken", "uri": "u2", "categorie": "belangrijk"},
    ]
    _schrijf_skills(tmp_path, "25180", beroep="Kok", skills=skills)
    blok = laad_skills_tekst("25180")
    assert "Essentiële skills" in blok and "Samenwerken" in blok
    assert "Belangrijke skills" in blok and "Engels spreken" in blok


def test_laad_skills_leeg_bij_geen_beroep(tmp_path, monkeypatch):
    monkeypatch.setenv("SKILLS_PAD", str(tmp_path))
    _schrijf_skills(tmp_path, "25250", beroep=None)
    assert laad_skills_tekst("25250") == ""


def test_laad_skills_leeg_bij_ontbrekend_bestand(tmp_path, monkeypatch):
    monkeypatch.setenv("SKILLS_PAD", str(tmp_path))
    assert laad_skills_tekst("00000") == ""


def test_bouw_systeem_includeert_skills_blok():
    systeem = bouw_systeem(
        "OER-tekst",
        "Kok",
        "Da Vinci",
        skills_tekst="\n\n=== SKILLS-TAXONOMIE (ESCO) — beroep: kok ===\nskills hier",
    )
    assert "SKILLS-TAXONOMIE (ESCO)" in systeem
    assert "skills hier" in systeem


def test_bouw_systeem_zonder_skills_geen_blok():
    systeem = bouw_systeem("OER-tekst", "Kok", "Da Vinci")
    assert "SKILLS-TAXONOMIE (ESCO) — beroep" not in systeem


def test_bouw_gecombineerd_systeem_includeert_skills_per_oer():
    items = [
        {
            "tekst": "OER A",
            "opleiding": "Kok",
            "display_naam": "Da Vinci",
            "leerweg": "BOL",
            "cohort": "2025",
            "crebo": "25180",
            "skills_tekst": "\n\n=== SKILLS-TAXONOMIE (ESCO) — beroep: kok ===\nkooktechnieken",
        },
    ]
    systeem = bouw_gecombineerd_systeem(items)
    assert "SKILLS-TAXONOMIE (ESCO)" in systeem
    assert "kooktechnieken" in systeem


def test_identificeer_opleiding_woorden_max_2():
    oers = [_oer_row(opleiding="Verzorgende IG zorg medewerker")]
    # Drie matchende woorden (>3 chars: verzorgende, zorg, medewerker)
    # maar score is gecapt op 2
    resultaat = identificeer_oer_kandidaten(oers, "verzorgende zorg medewerker info", min_score=0)
    # Score ≤ 2 + 0 (geen leerweg/cohort match) + 0 (display_naam 'Rijn'/'IJssel' niet in tekst)
    assert resultaat[0]["_score"] == 2


def test_identificeer_camelcase_split_in_opleiding():
    oers = [_oer_row(opleiding="VerzorgendeIG")]
    resultaat = identificeer_oer_kandidaten(oers, "verzorgende info")
    # CamelCase moet "Verzorgende" matchen ondanks aanlopen aan "IG"
    assert resultaat[0]["_score"] >= 1


def test_identificeer_jaartal_telt_alleen_als_cohort():
    """2025 in de tekst telt alleen via cohort (+2), niet ook via opleidingswoorden."""
    oers = [_oer_row(opleiding="Cohort 2025 traject", cohort="2025", leerweg="BOL")]
    resultaat = identificeer_oer_kandidaten(oers, "2025")
    # cohort: +2, opleidingswoorden: 'cohort'/'traject' niet in tekst, '2025' uitgesloten als digit
    assert resultaat[0]["_score"] == 2


def test_identificeer_generieke_woorden_negeren_in_display_naam():
    oers = [_oer_row(display_naam="Da Vinci College")]
    resultaat = identificeer_oer_kandidaten(oers, "college informatie graag")
    # 'college' is generiek → telt niet
    assert resultaat[0]["_score"] == 0


def test_identificeer_filtert_op_min_score():
    oers = [
        _oer_row(id=1, crebo="11111", leerweg="BOL", cohort="2024", opleiding="Onbekend"),
        _oer_row(id=2, crebo="22222", leerweg="BBL", cohort="2025", opleiding="Onbekend"),
    ]
    # Tekst matcht alleen oer 2 op leerweg+cohort = 4 punten
    resultaat = identificeer_oer_kandidaten(oers, "BBL 2025", min_score=3)
    assert len(resultaat) == 1
    assert resultaat[0]["id"] == 2


def test_identificeer_woord_match_geen_substring():
    """'zorg' in opleidingsnaam mag niet als substring matchen op 'verzorgende'.

    Regressie: typen van 'Verzorgende' op de publieke OER-pagina leverde
    voorheen ook OERs als 'Helpende-zorg-en-welzijn' op (false-positive
    via substring 'zorg' in 'verzorgende').
    """
    oers = [
        _oer_row(id=1, opleiding="Verzorgende IG"),
        _oer_row(id=2, opleiding="Helpende-zorg-en-welzijn"),
        _oer_row(id=3, opleiding="Begeleider maatschappelijke zorg"),
    ]
    resultaat = identificeer_oer_kandidaten(oers, "Verzorgende", min_score=1)
    assert len(resultaat) == 1
    assert resultaat[0]["id"] == 1


def test_identificeer_sorteert_op_score_aflopend():
    oers = [
        _oer_row(id=1, crebo="11111", leerweg="BBL"),  # match: niets
        _oer_row(id=2, crebo="22222", leerweg="BBL"),  # match: leerweg (+2)
        _oer_row(id=3, crebo="33333", leerweg="BBL"),  # match: crebo (+3) + leerweg (+2)
    ]
    resultaat = identificeer_oer_kandidaten(oers, "33333 BBL", min_score=0)
    scores = [r["_score"] for r in resultaat]
    assert scores == sorted(scores, reverse=True)
    assert resultaat[0]["id"] == 3
