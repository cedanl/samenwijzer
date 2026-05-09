#!/usr/bin/env bash
# Verifieer dat een bootstrap-run de verwachte DB heeft opgeleverd.
#
# De ingest- en seed-scripts zijn deterministisch (vaste RNG-seed), dus de
# counts hieronder moeten op élke machine identiek zijn — mits dezelfde git
# commit + dezelfde oeren/-tree uit Box.
#
# Gebruik:
#   ./scripts/check_bootstrap.sh
# Exit-code: 0 als alles klopt, 1 als één of meer checks falen.

set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

uv run python <<'PYEOF'
import os
import sys
from pathlib import Path

os.environ.setdefault("OEREN_PAD", "../oeren")

from validatie_samenwijzer._db import get_conn
from validatie_samenwijzer.chat import resolve_oer_pad

# Verwachte waarden: vastgelegd op de master-machine na een succesvolle
# bootstrap. Wijzig deze alleen als er bewust nieuwe OERs of seed-aanpassingen
# in main zijn gemerged.
EXPECTED_OERS = {
    "Aeres MBO":        (29, 29),    # totaal, geïndexeerd
    "Da Vinci College": (68, 68),    # zombie rows opgeruimd door seed_bulk._reset_database
    "ROC Utrecht":      (111, 111),
    "Rijn IJssel":      (50, 50),
    "Talland":          (238, 238),
}
EXPECTED_KERNTAKEN = 2483
EXPECTED_STUDENTEN = 600
EXPECTED_MENTOREN = 30
EXPECTED_MENTOR_OER = 30

GROEN = "\033[32m"
ROOD = "\033[31m"
GEEL = "\033[33m"
RESET = "\033[0m"


def check(label: str, actual, expected, *, exact: bool = True) -> bool:
    if exact:
        ok = actual == expected
    else:
        ok = actual >= expected
    kleur = GROEN if ok else ROOD
    teken = "✓" if ok else "✗"
    cmp = "=" if exact else "≥"
    print(f"  {kleur}{teken}{RESET} {label:35} {actual} (verwacht {cmp} {expected})")
    return ok


conn = get_conn()
resultaten = []

print("OERs per instelling:")
per_inst = {}
for r in conn.execute(
    """SELECT i.display_naam, COUNT(*) totaal,
              SUM(CASE WHEN geindexeerd=1 THEN 1 ELSE 0 END) geindexeerd
       FROM oer_documenten o JOIN instellingen i ON o.instelling_id=i.id
       GROUP BY i.display_naam"""
).fetchall():
    per_inst[r["display_naam"]] = (r["totaal"], r["geindexeerd"])

for inst, (exp_t, exp_g) in EXPECTED_OERS.items():
    actual = per_inst.get(inst, (0, 0))
    ok = actual == (exp_t, exp_g)
    kleur = GROEN if ok else ROOD
    teken = "✓" if ok else "✗"
    print(f"  {kleur}{teken}{RESET} {inst:20} totaal={actual[0]:3d} geïndexeerd={actual[1]:3d}  (verwacht {exp_t}/{exp_g})")
    resultaten.append(ok)

print()
print("Totalen:")
n_kt = conn.execute("SELECT COUNT(*) FROM kerntaken").fetchone()[0]
n_studenten = conn.execute("SELECT COUNT(*) FROM studenten").fetchone()[0]
n_mentoren = conn.execute("SELECT COUNT(*) FROM mentoren").fetchone()[0]
n_mentor_oer = conn.execute("SELECT COUNT(*) FROM mentor_oer").fetchone()[0]

resultaten.append(check("kerntaken", n_kt, EXPECTED_KERNTAKEN))
resultaten.append(check("studenten", n_studenten, EXPECTED_STUDENTEN))
resultaten.append(check("mentoren", n_mentoren, EXPECTED_MENTOREN))
resultaten.append(check("mentor_oer-koppelingen", n_mentor_oer, EXPECTED_MENTOR_OER))

print()
print("Bestanden op schijf:")
ontbrekend = []
totaal = 0
for r in conn.execute("SELECT bestandspad FROM oer_documenten WHERE geindexeerd=1").fetchall():
    totaal += 1
    pad = resolve_oer_pad(r["bestandspad"])
    if not pad.exists():
        ontbrekend.append(str(pad))
ok_files = len(ontbrekend) == 0
kleur = GROEN if ok_files else ROOD
teken = "✓" if ok_files else "✗"
print(f"  {kleur}{teken}{RESET} OER-bestanden ({totaal - len(ontbrekend)}/{totaal} aanwezig op schijf)")
if ontbrekend:
    print(f"    {GEEL}Ontbrekend (eerste 5):{RESET}")
    for p in ontbrekend[:5]:
        print(f"      {p}")
resultaten.append(ok_files)

print()
if all(resultaten):
    print(f"{GROEN}✅ Alle checks groen — bootstrap is succesvol.{RESET}")
    sys.exit(0)
else:
    n_fail = sum(1 for r in resultaten if not r)
    print(f"{ROOD}❌ {n_fail} check(s) gefaald. Re-run bootstrap of bekijk de details hierboven.{RESET}")
    sys.exit(1)
PYEOF
