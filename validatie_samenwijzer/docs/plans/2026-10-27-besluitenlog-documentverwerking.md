# Besluitenlog: verwerking van aangeleverde projectdocumenten

**Datum:** 2026-10-27 · **Bron:** map "Use case SamenWijzer" (Curio, Deltion, Graafschap College, KW1C, Rijn IJssel,
Werkgroep) · **Doel:** bij vragen kunnen uitleggen wat wel/niet is meegenomen en waarom.
**Resultaat Box:** `samenwijzer/use-case-samenwijzer/` — 168 bestanden (115 MB), structuur zie README in Box.

## A. Bewust niet meegenomen

| # | Document | Instelling | Besluit | Reden | Vastgesteld door |
|---|---|---|---|---|---|
| 1 | "SLB - coach namen.pdf", "SLB coach namen (PGL).pdf" | KW1C | Niet in Box, niet geïndexeerd | Uitgeprinte e-mail met namen van personen (coaches); persoonsgegevens. Was al eerder bewust niet verwerkt. | Ed akkoord op privacy-uitgangspunt; leesagent |
| 2 | "Onderwijsinrichting I&C 2026_2027.xlsm" | Graafschap | Niet in Box, niet geïndexeerd | Bevat docentcodes en blad "Docentenlestaak" (personeelsgegevens), verborgen oude bladen (cohort 2013–2017), cryptische roosterstructuur. Heroverwegen als een versie zonder docentgegevens wordt aangeleverd. | Leesagent; Claude |
| 3 | "Format Inventarisatie tussenfases, kansen en risico's" (×5) | alle | Niet in Box | Ed: "houden we ons nu niet mee bezig, laat die maar uit het geheel". Bevat ook contactpersonen. | Ed |
| 4 | Deltion: verder niets | Deltion | Niets te uploaden | Alleen het formulier aangeleverd; Deltion wacht op een interne collega voor selectie. | Leesagent (werkgroepstukken) |

## B. Deels / aangepast

| # | Onderwerp | Besluit | Reden |
|---|---|---|---|
| 5 | Studentenstatuut KW1C (2 bestanden) | Eén geüpload ("Studentenstatuut.pdf"); "studentenstatuut-0126.pdf" overgeslagen | Byte-identiek (md5) in dezelfde map |
| 6 | Curio 25742 OER 2026 vs 2023 | Beide geüpload | Byte-identiek; de bestandsnaam draagt het cohort. **Navragen bij Curio** of dezelfde tekst voor twee cohorten is aangeleverd |
| 7 | Curio-map "Examenregelement" (34 bestanden) | Geplaatst in `4-examenplannen` | Inhoud zijn examenplannen per opleiding, geen examenreglementen |
| 8 | Curio OER 25797-2025 (stond in "Examenregelement") | Geplaatst in `1-oer`; origineel ongewijzigd | Is een OER, geen examenplan |
| 9 | NML-bestand "27054_oer_…zelfstandig-medewerker-leisure.pdf" | Geplaatst bij NML; naam niet aangepast | Is een nominale lijn (inhoud: crebo 25648), geen OER; originele namen blijven behouden |
| 10 | Werkgroepdocumenten | Wel geüpload naar `00-project` / `99-archief` | Projectdocumenten; bevatten organisatorische contactgegevens van deelnemers; archiefstukken (plan van aanpak mei 2026) zijn achterhaald (4 fases/RAG) |
| 11 | Eerder (handoff): persoonsgegevens in "Grof ontwerp challenges BBL4" | Gerediged in de eerder verwerkte versie | Privacy; de Box-versie is het aangeleverde origineel — **bij indexeren opnieuw redigeren** |

## C. Inhoudelijke keuzes

| # | Onderwerp | Besluit | Reden |
|---|---|---|---|
| 12 | KD 2016 (KW1C, Werkvoorbereider fabricage, cohort 2025) | **Wel meenemen**, naast de nieuwe KD | Ed: studenten van dat cohort studeren er nog op; alleen nuttig als een OER van dat cohort aanwezig is |
| 13 | Examenreglement vs examenplan | Reglement = instellingsbreed, examenplan = per opleiding/cohort | Ed + onderzoek |
| 14 | Vectorstore | Niet nu; optie A3 in de spec | Woordelijke citaatplicht; huidige set past met hybride aanpak; heroverweegt PR #33 |
| 15 | Rijn IJssel Xerte-OER's | Buiten fase 1–4 | Geen PDF; aparte ingestroute nodig |
| 16 | OCR KW1C studiegids 25779 (scan) | Ed installeert `tesseract` | Geen tekstlaag; de enige scan in de aangeleverde set |
