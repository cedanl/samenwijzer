"""Beheerpagina — DB-status, sync oeren, re-ingest, seed.

Beschermd via env-flag `BEHEER_ENABLED=true` zodat de pagina alleen op
ontwikkelmachines bereikbaar is. Subprocesses worden gestreamd zodat een
langlopende ingest de UI niet bevriest.
"""

from __future__ import annotations

import os
import shlex
import subprocess
from collections.abc import Iterator
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(page_title="Beheer — Samenwijzer", page_icon="🛠", layout="wide")

from validatie_samenwijzer.db import (  # noqa: E402
    get_connection,
    init_db,
    laatste_ingest_run,
)
from validatie_samenwijzer.styles import CSS, render_footer  # noqa: E402

st.markdown(CSS, unsafe_allow_html=True)

# ── Toegangscontrole ───────────────────────────────────────────────────────────
if os.environ.get("BEHEER_ENABLED", "").lower() != "true":
    st.error(
        "🛠 Beheerpagina is niet ingeschakeld op deze machine. "
        "Zet `BEHEER_ENABLED=true` in `.env` om toegang te krijgen."
    )
    st.stop()

# ── Helpers ───────────────────────────────────────────────────────────────────
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_INSTELLING_KEYS = ["aeres", "davinci", "rijn_ijssel", "talland", "utrecht"]


def _stream_lines(cmd: list[str], cwd: Path) -> Iterator[str]:
    """Run cmd en yield stdout-regels live."""
    proc = subprocess.Popen(  # noqa: S603 — input is uit hardcoded keuzes, niet user-text
        cmd,
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    assert proc.stdout is not None
    yield from iter(proc.stdout.readline, "")
    proc.wait()
    yield f"\n[exit={proc.returncode}]\n"


def _run_in_placeholder(cmd: list[str], cwd: Path | None = None) -> None:
    """Toon live output van cmd in een code-block met scrollende tail."""
    cwd = cwd or _PROJECT_ROOT
    st.caption(f"$ {shlex.join(cmd)}  (cwd={cwd})")
    placeholder = st.empty()
    buffer: list[str] = []
    for regel in _stream_lines(cmd, cwd):
        buffer.append(regel)
        placeholder.code("".join(buffer[-300:]), language="bash")


# ── Pagina-header ──────────────────────────────────────────────────────────────
st.title("🛠 Beheer")
st.caption(
    "Tools voor lokaal database-beheer: synchroniseer OERs vanuit Box, "
    "herindexeer bestanden, regenereer testdata en bekijk DB-status. "
    "Subprocesses draaien op deze machine en kunnen meerdere minuten duren."
)

tab_status, tab_bootstrap, tab_sync, tab_ingest, tab_seed = st.tabs(
    ["📊 Status", "🚀 Bootstrap", "☁️ Sync oeren", "🗄 Re-ingest", "🌱 Seed"]
)

# ── Tab: Status ────────────────────────────────────────────────────────────────
with tab_status:
    # Verse connectie zodat na een ingest-subprocess de nieuwe rijen direct
    # zichtbaar zijn (de gecachte connectie van `_db.get_conn()` houdt vast
    # aan een transactie-snapshot vóór de subprocess-commit).
    db_path = Path(os.environ.get("DB_PATH", "data/validatie.db"))
    if not db_path.is_absolute():
        db_path = _PROJECT_ROOT / db_path
    conn = get_connection(db_path)
    init_db(conn)

    st.subheader("Database-status")

    rijen = conn.execute(
        """
        SELECT i.display_naam,
               COUNT(*)                                AS totaal,
               SUM(CASE WHEN o.geindexeerd=1 THEN 1 ELSE 0 END) AS geindexeerd
          FROM oer_documenten o
          JOIN instellingen i ON i.id = o.instelling_id
         GROUP BY i.display_naam
         ORDER BY i.display_naam
        """
    ).fetchall()
    if rijen:
        st.dataframe(
            [{"Instelling": r["display_naam"], "Totaal OERs": r["totaal"],
              "Geïndexeerd": r["geindexeerd"]} for r in rijen],
            hide_index=True, use_container_width=False,
        )
    else:
        st.info("Geen OERs in DB. Draai eerst een ingest.")

    laatste = laatste_ingest_run(conn)
    if laatste:
        st.markdown(
            f"**Laatste ingest**: `{laatste['scope']}` op {laatste['tijdstip']} "
            f"({laatste['n_oers']} OERs, {laatste['n_kerntaken']} kerntaken, "
            f"{laatste['duur_seconden']:.1f}s)"
        )
    else:
        st.markdown("**Laatste ingest**: nog geen run geregistreerd.")

    st.subheader("Bestanden op schijf")
    oeren_pad = Path(os.environ.get("OEREN_PAD", "../oeren"))
    if not oeren_pad.is_absolute():
        oeren_pad = (_PROJECT_ROOT / oeren_pad).resolve()
    if oeren_pad.exists():
        n_pdf = sum(1 for _ in oeren_pad.rglob("*.pdf"))
        n_md = sum(1 for _ in oeren_pad.rglob("*.md"))
        st.write(f"📁 `{oeren_pad}` — {n_pdf} PDFs, {n_md} markdown-bestanden")
    else:
        st.warning(f"Map `{oeren_pad}` niet gevonden — draai eerst sync.")

# ── Tab: Bootstrap ─────────────────────────────────────────────────────────────
with tab_bootstrap:
    st.subheader("🚀 Volledige machine-setup")
    st.caption(
        "Eén klik = `uv sync` → `rclone copy` (Box) → `ingest --alles` → `seed`. "
        "Gebruik dit op een nieuwe machine of als je de DB volledig wil herbouwen."
    )
    st.warning(
        "Duur: 10–30 minuten afhankelijk van Box-bandbreedte en aantal OERs. "
        "Tijdens de run is de app niet bruikbaar; subprocess-output verschijnt hieronder."
    )

    col_skip_sync, col_skip_seed, col_bulk = st.columns(3)
    with col_skip_sync:
        skip_sync = st.checkbox(
            "Skip sync",
            value=False,
            help="Sla `rclone copy` over (oeren/ is al up-to-date).",
        )
    with col_skip_seed:
        skip_seed = st.checkbox(
            "Skip seed",
            value=False,
            help="Geen testaccounts aanmaken.",
        )
    with col_bulk:
        seed_bulk = st.checkbox(
            "Seed bulk (~1000 studenten)",
            value=False,
            help="Naast basis-accounts ook `seed_bulk.py` draaien.",
        )

    bevestig = st.checkbox(
        "Ja, ik weet dat dit de DB volledig herbouwt",
        value=False,
        key="bootstrap_bevestig",
    )

    if st.button("Start bootstrap", type="primary", disabled=not bevestig):
        cmd = ["bash", "scripts/bootstrap.sh"]
        if skip_sync:
            cmd.append("--skip-sync")
        if skip_seed:
            cmd.append("--skip-seed")
        if seed_bulk:
            cmd.append("--seed-bulk")
        _run_in_placeholder(cmd)


# ── Tab: Sync oeren ────────────────────────────────────────────────────────────
with tab_sync:
    st.subheader("☁️ Sync oeren/ vanuit Box")
    st.caption(
        "Roept `scripts/sync_oeren.sh` aan dat met `rclone copy` de centrale Box-folder "
        "spiegelt naar lokaal. Vereist eenmalig `rclone config` op deze machine."
    )
    if st.button("Start sync", type="primary"):
        _run_in_placeholder(["bash", "scripts/sync_oeren.sh"])

# ── Tab: Re-ingest ─────────────────────────────────────────────────────────────
with tab_ingest:
    st.subheader("🗄 Re-ingest OERs")
    col1, col2 = st.columns(2)
    with col1:
        scope = st.selectbox(
            "Scope",
            options=["alles", *_INSTELLING_KEYS],
            help="`alles` herwerkt alle 5 instellingen (~10-30 min).",
        )
    with col2:
        reset = st.checkbox(
            "--reset (herindexeer ook al-geïndexeerde OERs)",
            value=False,
            help="Forceert PDF-conversie + kerntaak-extractie opnieuw.",
        )

    if st.button("Start ingest", type="primary"):
        cmd = ["uv", "run", "python", "-m", "validatie_samenwijzer.ingest"]
        if scope == "alles":
            cmd.append("--alles")
        else:
            cmd.extend(["--instelling", scope])
        if reset:
            cmd.append("--reset")
        _run_in_placeholder(cmd)

# ── Tab: Seed ──────────────────────────────────────────────────────────────────
with tab_seed:
    st.subheader("🌱 Testdata regenereren")
    st.warning(
        "Seed-scripts overschrijven studenten- en mentor-tabellen. "
        "Gebruik dit niet op een gedeelde DB."
    )

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("**Basis (3 studenten + 2 mentoren)**")
        if st.button("Run seed.py"):
            _run_in_placeholder(["uv", "run", "python", "scripts/seed.py"])
    with col_b:
        st.markdown("**Bulk (~1000 studenten over alle OERs)**")
        st.caption("Vereist dat OERs eerst zijn geïngest.")
        if st.button("Run seed_bulk.py"):
            _run_in_placeholder(["uv", "run", "python", "scripts/seed_bulk.py"])

render_footer()
