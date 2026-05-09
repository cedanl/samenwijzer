# Product Spec: Outreach & Welzijn

**Status:** gereed (geïmplementeerd 2026-04-10)
**Inspiratiebron:** Annie Advisor (annieadvisor.com) — proactieve studentondersteuning

## Probleemstelling

Slechts 1 op de 5 studenten die hulp nodig heeft, vraagt er actief om.
Mentoren missen signalen totdat voortgangsdata al ver achter is.

## Oplossingsrichting

Twee complementaire kanalen:
1. **Bottom-up** — student initieert (welzijnscheck)
2. **Top-down** — mentor initieert op het juiste moment (transitiemoment + campagne)

---

## Feature 1 — Student welzijnscheck (`5_welzijn.py`)

Student geeft zelf aan waar moeite mee is.

**Hulpcategorieën:**
| Code | Label |
|---|---|
| `studieplanning` | Studieplanning & opdrachten |
| `welzijn` | Persoonlijk welzijn |
| `financiën` | Financiën |
| `werkplekleren` | Stage & werkplekleren |
| `overig` | Iets anders |

**Urgentieniveaus:** 1 = kan wachten · 2 = liefst snel · 3 = dringend

**Stroom:**
1. Student vult categorie + optionele toelichting + urgentie in
2. `sla_welzijnscheck_op()` schrijft naar SQLite
3. AI (`genereer_welzijnsreactie()`) geeft directe empathische reactie
4. Mentor ziet check in groepsoverzicht met urgentie-icoon (🟢/🟡/🔴)

**Acceptatiecriteria:**
- [x] Student kan check invullen zonder auth-overhead
- [x] Mentor ziet recente checks in groepsoverzicht
- [x] AI-reactie wordt gestreamed (max. 80 woorden)
- [x] Eerdere checks zichtbaar voor student (laatste 5)

---

## Feature 2 — Transitiemoment-detectie (`analyze.py`)

Automatisch signaleren wanneer een student in een kritieke fase zit.

| Moment | Trigger |
|---|---|
| `bsa_risico` | `bsa_percentage < 0.60` |
| `bijna_klaar` | `voortgang >= 0.80` |

Getoond als badge in de outreach-werklijst.

**Acceptatiecriteria:**
- [x] Elke at-risk student krijgt een badge als een moment van toepassing is
- [x] `detecteer_transitiemoment()` is pure functie, eenvoudig te testen

---

## Feature 3 — Campagnebeheer (`4_outreach.py` tab Campagnes)

Mentoren maken gerichte outreach-campagnes aan per transitiemoment.

**Campagne-velden:** naam, transitiemoment, berichttemplate, aangemaakt door/op, status

**Lifecycle:** `actief` → `afgesloten`

**Acceptatiecriteria:**
- [x] Mentor kan campagne aanmaken via formulier
- [x] Actieve campagnes zichtbaar met template-expander
- [x] Campagne afsluiten via knop

---

## Feature 4 — Verwijslogica (`outreach.py`)

Bij het opstellen van een outreach-bericht kan de mentor een hulpcategorie kiezen.
`suggereer_verwijzing(categorie)` geeft de passende verwijzing terug.

| Categorie | Verwijzing |
|---|---|
| `studieplanning` | Studieloopbaanbegeleider (SLB-er) |
| `welzijn` | Studentendecaan / vertrouwenspersoon |
| `financiën` | Financieel spreekuur |
| `werkplekleren` | Praktijkbegeleider |
| `overig` | Mentor / SLB-er |

De verwijzing wordt optioneel meegenomen in `genereer_outreach_bericht()`.

**Acceptatiecriteria:**
- [x] Mentor kan verwijzing aan/uitzetten per student
- [x] AI-bericht vermeldt verwijzing als aangevinkt
- [x] Info-blok toont verwijsdetails vóór generatie

---

## Feature 5 — Effectiviteitsdashboard (`4_outreach.py` tab Effectiviteit)

Inzicht in wat outreach oplevert.

**Metrics:**
- Totaal interventies, contactratio, responsratio, opgelost %
- Statustrechter (at-risk → gecontacteerd → gereageerd → opgelost)
- Interventies per mentor

**Acceptatiecriteria:**
- [x] Metrics kloppen op basis van live SQLite-data
- [x] Statustrechter toont alle vier stadia
- [x] Volledige interventielog beschikbaar onderaan
