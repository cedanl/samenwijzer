"""Genereer synthetische Berend-dataset: 1000 MBO-studenten.

Uitvoer:
  data/01-raw/berend/studenten.csv
  data/01-raw/berend/oer_kerntaken.json

Gebruik:
  uv run python scripts/generate_berend_data.py
"""

import json
import random
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 42
rng = np.random.default_rng(SEED)
random.seed(SEED)

ROOT = Path(__file__).parent.parent
OUT_DIR = ROOT / "data" / "01-raw" / "berend"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ── Namen ─────────────────────────────────────────────────────────────────────

VOORNAMEN_M = [
    "Adam",
    "Amir",
    "Bram",
    "Bryan",
    "Daan",
    "David",
    "Dylan",
    "Elias",
    "Finn",
    "Hamza",
    "Ilias",
    "Jayden",
    "Jesse",
    "Joris",
    "Julian",
    "Kevin",
    "Lars",
    "Liam",
    "Lucas",
    "Luuk",
    "Max",
    "Mohamed",
    "Nathan",
    "Nick",
    "Noah",
    "Noel",
    "Oliver",
    "Owen",
    "Ramon",
    "Remi",
    "Ruben",
    "Sam",
    "Sander",
    "Sem",
    "Stefan",
    "Stijn",
    "Thomas",
    "Thijs",
    "Tim",
    "Tom",
    "Victor",
    "Wesley",
    "Wouter",
    "Xander",
    "Younes",
    "Yusuf",
]

VOORNAMEN_V = [
    "Amber",
    "Amy",
    "Anika",
    "Anna",
    "Bo",
    "Charlotte",
    "Demi",
    "Elena",
    "Elisa",
    "Emma",
    "Eva",
    "Fenna",
    "Fleur",
    "Hannah",
    "Iris",
    "Isabel",
    "Jana",
    "Jasmin",
    "Julia",
    "Julie",
    "Kim",
    "Laura",
    "Lena",
    "Lisa",
    "Lotte",
    "Luna",
    "Manon",
    "Maria",
    "Maya",
    "Mila",
    "Nina",
    "Nora",
    "Olivia",
    "Roos",
    "Sara",
    "Selin",
    "Senna",
    "Sofia",
    "Sofie",
    "Tess",
    "Yasmine",
    "Zoë",
]

ACHTERNAMEN = [
    "Bakker",
    "Berg",
    "Boer",
    "Bosch",
    "Brouwer",
    "de Groot",
    "de Jong",
    "de Vries",
    "Dekker",
    "Dijkstra",
    "Dijk",
    "Dubois",
    "El Amrani",
    "El Idrissi",
    "Geerts",
    "Hendriks",
    "Hermans",
    "Jacobs",
    "Jansen",
    "Janssen",
    "Karakus",
    "Kaya",
    "Koolen",
    "Kramer",
    "Laan",
    "Lammers",
    "Martens",
    "Meijer",
    "Mulder",
    "Nguyen",
    "Nijhuis",
    "Osman",
    "Peters",
    "Pieters",
    "Pijpers",
    "Poulsen",
    "Ramadan",
    "Sanders",
    "Scheepers",
    "Smeets",
    "Smit",
    "Snijders",
    "Stam",
    "Timmermans",
    "van Dam",
    "van den Berg",
    "van den Bosch",
    "van der Linden",
    "van der Meer",
    "van Dijk",
    "van Dongen",
    "van Leeuwen",
    "van Wijnen",
    "Vermeer",
    "Vermeulen",
    "Visser",
    "Willems",
    "Wolters",
    "Wouters",
    "Zijlstra",
]

MENTOR_NAMEN = [
    "Anke Visser",
    "Bart Hendriks",
    "Carla de Wit",
    "Dennis Smits",
    "Ellen Bakker",
    "Frank Jansen",
    "Greta Mulder",
    "Hans Dekker",
    "Inge Peters",
    "Jan Willems",
    "Karen Laan",
    "Leon Meijer",
    "Mirjam Scholten",
    "Niels van Dam",
    "Olga Brouwer",
]

# ── Opleidingen ───────────────────────────────────────────────────────────────

OPLEIDINGEN = [
    ("Zorg & Welzijn", [3, 4], 130),
    ("Economie", [3, 4], 120),
    ("Techniek", [2, 3, 4], 100),
    ("Gastheer/Gastvrouw", [3], 70),
    ("Junior Manager Logistiek", [3, 4], 80),
    ("Kapper", [3, 4], 60),
    ("Kok", [2, 3], 90),
    ("Metselaar", [2, 3], 60),
    ("Tandartsassistent", [4], 50),
    ("Verzorgende", [3], 90),
    ("Werktuigbouw", [3, 4], 150),
]

COHORT_LETTERS = ["A", "B", "C"]  # A = oudst

# ── OER kerntaken ─────────────────────────────────────────────────────────────

OER: dict = {
    "Zorg & Welzijn": {
        "kerntaken": [
            {"code": "kt_1", "naam": "Ondersteunen bij dagelijkse activiteiten"},
            {"code": "kt_2", "naam": "Verlenen van basis zorg en begeleiding"},
        ],
        "werkprocessen": [
            {"code": "wp_1_1", "naam": "Helpen bij persoonlijke verzorging"},
            {"code": "wp_1_2", "naam": "Begeleiden bij sociale participatie"},
            {"code": "wp_1_3", "naam": "Signaleren van veranderingen in welzijn"},
            {"code": "wp_2_1", "naam": "Uitvoeren van verpleegkundige handelingen"},
            {"code": "wp_2_2", "naam": "Bijhouden van zorgdossiers"},
            {"code": "wp_2_3", "naam": "Samenwerken in het zorgteam"},
        ],
    },
    "Economie": {
        "kerntaken": [
            {"code": "kt_1", "naam": "Uitvoeren van administratieve en financiële taken"},
            {"code": "kt_2", "naam": "Ondersteunen van commerciële processen"},
        ],
        "werkprocessen": [
            {"code": "wp_1_1", "naam": "Verwerken van financiële gegevens"},
            {"code": "wp_1_2", "naam": "Opstellen van offertes en facturen"},
            {"code": "wp_1_3", "naam": "Bijhouden van de administratie"},
            {"code": "wp_2_1", "naam": "Klantcontact en relatieonderhoud"},
            {"code": "wp_2_2", "naam": "Ondersteunen bij marketing en verkoop"},
            {"code": "wp_2_3", "naam": "Analyseren van bedrijfsgegevens"},
        ],
    },
    "Techniek": {
        "kerntaken": [
            {"code": "kt_1", "naam": "Installeren en onderhouden van technische systemen"},
            {"code": "kt_2", "naam": "Oplossen van storingen en fouten"},
        ],
        "werkprocessen": [
            {"code": "wp_1_1", "naam": "Monteren van componenten"},
            {"code": "wp_1_2", "naam": "Controleren van installaties"},
            {"code": "wp_1_3", "naam": "Uitvoeren van preventief onderhoud"},
            {"code": "wp_2_1", "naam": "Diagnosticeren van storingen"},
            {"code": "wp_2_2", "naam": "Herstellen van defecten"},
            {"code": "wp_2_3", "naam": "Rapporteren van werkzaamheden"},
        ],
    },
    "Gastheer/Gastvrouw": {
        "kerntaken": [
            {"code": "kt_1", "naam": "Ontvangen en begeleiden van gasten"},
            {"code": "kt_2", "naam": "Verzorgen van de gastenruimte en dienstverlening"},
        ],
        "werkprocessen": [
            {"code": "wp_1_1", "naam": "Verwelkomen en inchecken van gasten"},
            {"code": "wp_1_2", "naam": "Afhandelen van verzoeken en klachten"},
            {"code": "wp_1_3", "naam": "Adviseren over faciliteiten en activiteiten"},
            {"code": "wp_2_1", "naam": "Inrichten en schoonhouden van ruimten"},
            {"code": "wp_2_2", "naam": "Serveren van spijs en drank"},
            {"code": "wp_2_3", "naam": "Afrekenen en afsluiten van verblijf"},
        ],
    },
    "Junior Manager Logistiek": {
        "kerntaken": [
            {"code": "kt_1", "naam": "Plannen en coördineren van logistieke processen"},
            {"code": "kt_2", "naam": "Beheren van voorraden en transport"},
        ],
        "werkprocessen": [
            {"code": "wp_1_1", "naam": "Plannen van in- en uitgaande goederenstromen"},
            {"code": "wp_1_2", "naam": "Coördineren van magazijnwerkzaamheden"},
            {"code": "wp_1_3", "naam": "Bewaken van levertijden en kwaliteit"},
            {"code": "wp_2_1", "naam": "Beheren van voorraad en opslagruimte"},
            {"code": "wp_2_2", "naam": "Regelen van transport en distributie"},
            {"code": "wp_2_3", "naam": "Rapporteren van logistieke prestaties"},
        ],
    },
    "Kapper": {
        "kerntaken": [
            {"code": "kt_1", "naam": "Uitvoeren van haarbehandelingen"},
            {"code": "kt_2", "naam": "Adviseren en verzorgen van klanten"},
        ],
        "werkprocessen": [
            {"code": "wp_1_1", "naam": "Knippen en stylen van haar"},
            {"code": "wp_1_2", "naam": "Kleuren en permanenten"},
            {"code": "wp_1_3", "naam": "Behandelen van hoofdhuid en haar"},
            {"code": "wp_2_1", "naam": "Uitvoeren van intake en adviesgesprek"},
            {"code": "wp_2_2", "naam": "Verkopen van producten en diensten"},
            {"code": "wp_2_3", "naam": "Bijhouden van klantendossiers"},
        ],
    },
    "Kok": {
        "kerntaken": [
            {"code": "kt_1", "naam": "Bereiden van gerechten"},
            {"code": "kt_2", "naam": "Organiseren van de keuken en productie"},
        ],
        "werkprocessen": [
            {"code": "wp_1_1", "naam": "Voorbereiden van ingrediënten"},
            {"code": "wp_1_2", "naam": "Bereiden van warme en koude gerechten"},
            {"code": "wp_1_3", "naam": "Bewaken van kwaliteit en voedselveiligheid"},
            {"code": "wp_2_1", "naam": "Plannen van de mise en place"},
            {"code": "wp_2_2", "naam": "Beheren van voorraad en inkoop"},
            {"code": "wp_2_3", "naam": "Aansturen van keukenpersoneel"},
        ],
    },
    "Metselaar": {
        "kerntaken": [
            {"code": "kt_1", "naam": "Metselen van constructies en gevels"},
            {"code": "kt_2", "naam": "Werken met bouwmaterialen en gereedschappen"},
        ],
        "werkprocessen": [
            {"code": "wp_1_1", "naam": "Uitzetten en afwerken van metselwerk"},
            {"code": "wp_1_2", "naam": "Verwerken van voeg- en spijkermortels"},
            {"code": "wp_1_3", "naam": "Plaatsen van lateien en ankers"},
            {"code": "wp_2_1", "naam": "Lezen van tekeningen en bestek"},
            {"code": "wp_2_2", "naam": "Selecteren en verwerken van baksteen"},
            {"code": "wp_2_3", "naam": "Toepassen van veiligheidsvoorschriften"},
        ],
    },
    "Tandartsassistent": {
        "kerntaken": [
            {"code": "kt_1", "naam": "Assisteren bij tandheelkundige behandelingen"},
            {"code": "kt_2", "naam": "Verzorgen van patiënten en instrumentarium"},
        ],
        "werkprocessen": [
            {"code": "wp_1_1", "naam": "Klaarmaken van de behandelstoel en instrumenten"},
            {"code": "wp_1_2", "naam": "Assisteren bij vullingen en extracties"},
            {"code": "wp_1_3", "naam": "Maken van röntgenfoto's"},
            {"code": "wp_2_1", "naam": "Ontvangen en begeleiden van patiënten"},
            {"code": "wp_2_2", "naam": "Steriliseren en beheren van instrumentarium"},
            {"code": "wp_2_3", "naam": "Bijhouden van patiëntendossiers"},
        ],
    },
    "Verzorgende": {
        "kerntaken": [
            {"code": "kt_1", "naam": "Verlenen van persoonlijke verzorging"},
            {"code": "kt_2", "naam": "Ondersteunen van het dagelijks functioneren"},
        ],
        "werkprocessen": [
            {"code": "wp_1_1", "naam": "Wassen, kleden en verzorgen van cliënten"},
            {"code": "wp_1_2", "naam": "Toedienen van medicijnen"},
            {"code": "wp_1_3", "naam": "Verzorgen van wonden"},
            {"code": "wp_2_1", "naam": "Begeleiden bij huishoudelijke taken"},
            {"code": "wp_2_2", "naam": "Ondersteunen van sociale contacten"},
            {"code": "wp_2_3", "naam": "Rapporteren in zorgdossier"},
        ],
    },
    "Werktuigbouw": {
        "kerntaken": [
            {"code": "kt_1", "naam": "Vervaardigen van werktuigbouwkundige producten"},
            {"code": "kt_2", "naam": "Onderhouden en repareren van machines"},
        ],
        "werkprocessen": [
            {"code": "wp_1_1", "naam": "Draaien, frezen en slijpen van onderdelen"},
            {"code": "wp_1_2", "naam": "Lassen en verbinden van metalen"},
            {"code": "wp_1_3", "naam": "Controleren van maatvoering en toleranties"},
            {"code": "wp_2_1", "naam": "Reviseren van machines en installaties"},
            {"code": "wp_2_2", "naam": "Diagnosticeren van mechanische storingen"},
            {"code": "wp_2_3", "naam": "Opstellen van onderhoudsrapporten"},
        ],
    },
    "Overig": {
        "kerntaken": [
            {"code": "kt_1", "naam": "Uitvoeren van vaktaken"},
            {"code": "kt_2", "naam": "Samenwerken in een professionele omgeving"},
        ],
        "werkprocessen": [
            {"code": "wp_1_1", "naam": "Plannen en organiseren van werkzaamheden"},
            {"code": "wp_1_2", "naam": "Communiceren met collega's en klanten"},
            {"code": "wp_1_3", "naam": "Bewaken van kwaliteit en veiligheid"},
            {"code": "wp_2_1", "naam": "Samenwerken in teamverband"},
            {"code": "wp_2_2", "naam": "Reflecteren op eigen functioneren"},
            {"code": "wp_2_3", "naam": "Bijdragen aan verbetering van processen"},
        ],
    },
}

# ── Studenten genereren ───────────────────────────────────────────────────────


def genereer_naam(geslacht: int) -> str:
    voornaam = random.choice(VOORNAMEN_V if geslacht == 1 else VOORNAMEN_M)
    achternaam = random.choice(ACHTERNAMEN)
    return f"{voornaam} {achternaam}"


rows = []
studentnummer = 100001

for opleiding, niveaus, n_studenten in OPLEIDINGEN:
    for i in range(n_studenten):
        niveau = random.choice(niveaus)
        cohort_letter = random.choices(COHORT_LETTERS, weights=[0.3, 0.4, 0.3])[0]
        klas = f"{niveau}{cohort_letter}"

        geslacht = rng.integers(0, 2)
        naam = genereer_naam(int(geslacht))
        leeftijd = int(rng.integers(16, 25))
        mentor = random.choice(MENTOR_NAMEN)

        # Ongeoorloofd verzuim: rechtsscheve verdeling (meeste studenten hebben weinig)
        # Beta-verdeling geeft realistische spreiding
        absence_raw = float(rng.beta(1.5, 6.0)) * 55
        # Extra piek bij 0 (veel studenten hebben nauwelijks verzuim)
        if rng.random() < 0.35:
            absence_raw = float(rng.beta(1.0, 20.0)) * 8
        absence = round(absence_raw, 1)

        rows.append(
            {
                "Studentnummer": str(studentnummer),
                "Naam": naam,
                "Mentor": mentor,
                "Opleiding": opleiding,
                "StudentAge": leeftijd,
                "StudentGender": int(geslacht),
                "Klas": klas,
                "absence_unauthorized": absence,
            }
        )
        studentnummer += 1

df = pd.DataFrame(rows)

# Zorg dat mentors redelijk gelijkmatig verdeeld zijn per opleiding
# (her-wijs mentors op basis van klas zodat een mentor bij één opleiding past)
opleiding_mentor_map: dict[str, list[str]] = {}
all_mentors = list(MENTOR_NAMEN)
for idx, (opleiding, _, _) in enumerate(OPLEIDINGEN):
    start = idx % len(all_mentors)
    opleiding_mentor_map[opleiding] = all_mentors[start : start + 2] or all_mentors[:2]


def wijs_mentor(row: pd.Series) -> str:
    mentors = opleiding_mentor_map.get(row["Opleiding"], MENTOR_NAMEN[:2])
    # Gebruik studentnummer als seed voor consistente toewijzing
    idx = int(row["Studentnummer"]) % len(mentors)
    return mentors[idx]


df["Mentor"] = df.apply(wijs_mentor, axis=1)

# Sla op
csv_pad = OUT_DIR / "studenten.csv"
df.to_csv(csv_pad, index=False)
print(f"Opgeslagen: {csv_pad} ({len(df)} studenten)")

json_pad = OUT_DIR / "oer_kerntaken.json"
with json_pad.open("w", encoding="utf-8") as fh:
    json.dump(OER, fh, ensure_ascii=False, indent=2)
print(f"Opgeslagen: {json_pad}")

# Kort overzicht
print("\nVerdeling per opleiding:")
print(df.groupby("Opleiding")["Studentnummer"].count().to_string())
print(f"\nGemiddeld verzuim: {df['absence_unauthorized'].mean():.1f} uur")
print(f"Studenten met >30u verzuim: {(df['absence_unauthorized'] > 30).sum()}")
