"""Beheerpagina — DB-status, sync oeren, re-ingest, seed.

Beschermd via env-flag `BEHEER_ENABLED=true` zodat de pagina alleen op
ontwikkelmachines bereikbaar is. Subprocesses worden gestreamd zodat een
langlopende ingest de UI niet bevriest.
"""

from __future__ import annotations

import os
import shlex
import subprocess
import time
from collections import deque
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
from validatie_samenwijzer.styles import CSS, render_footer, render_nav  # noqa: E402

st.markdown(CSS, unsafe_allow_html=True)
render_nav()

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


_BUFFER_REGELS = 300
_PAINT_INTERVAL_S = 0.2


def _stream_lines(cmd: list[str], cwd: Path) -> Iterator[tuple[str, int | None]]:
    """Run cmd en yield (regel, returncode); returncode is None tot het proces eindigt."""
    proc = subprocess.Popen(  # noqa: S603 — input is uit hardcoded keuzes, niet user-text
        cmd,
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    if proc.stdout is None:
        raise RuntimeError("Popen leverde geen stdout op — kan output niet streamen.")
    for regel in iter(proc.stdout.readline, ""):
        yield regel, None
    proc.wait()
    yield f"\n[exit={proc.returncode}]\n", proc.returncode


def _run_in_placeholder(cmd: list[str], cwd: Path | None = None) -> None:
    """Toon live output van cmd in een code-block met scrollende tail."""
    cwd = cwd or _PROJECT_ROOT
    st.caption(f"$ {shlex.join(cmd)}  (cwd={cwd})")
    placeholder = st.empty()
    # deque voorkomt onbegrensde groei bij langlopende subprocesses (bv. een 30-min
    # bootstrap kan tienduizenden regels rclone-progress produceren).
    buffer: deque[str] = deque(maxlen=_BUFFER_REGELS)
    laatste_paint = 0.0
    returncode: int | None = None
    for regel, rc in _stream_lines(cmd, cwd):
        buffer.append(regel)
        if rc is not None:
            returncode = rc
        # Throttle: bij snel-producerende subprocessen zou per-regel re-rendering de
        # Streamlit-WebSocket overbelasten en de browser laten haperen.
        nu = time.monotonic()
        if nu - laatste_paint > _PAINT_INTERVAL_S or rc is not None:
            placeholder.code("".join(buffer), language="bash")
            laatste_paint = nu
    if returncode == 0:
        st.success(f"✅ Klaar (exit=0): `{shlex.join(cmd)}`")
    else:
        st.error(f"❌ Subprocess gefaald (exit={returncode}): `{shlex.join(cmd)}`")


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
            [
                {
                    "Instelling": r["display_naam"],
                    "Totaal OERs": r["totaal"],
                    "Geïndexeerd": r["geindexeerd"],
                }
                for r in rijen
            ],
            hide_index=True,
            use_container_width=False,
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
        n_pdf = n_md = 0
        for pad in oeren_pad.rglob("*"):
            if pad.suffix == ".pdf":
                n_pdf += 1
            elif pad.suffix == ".md":
                n_md += 1
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

    seed_keuze = st.radio(
        "Seed-data",
        options=["bulk", "minimal", "geen"],
        format_func=lambda v: {
            "bulk": "Bulk (~1000 studenten over alle OERs) — default",
            "minimal": "Minimaal (3 studenten + 2 mentoren, dev-demo)",
            "geen": "Geen seed-data aanmaken",
        }[v],
        index=0,
        horizontal=False,
    )
    skip_sync = st.checkbox(
        "Skip oeren-sync (oeren/ is al up-to-date)",
        value=False,
        help="Sla `rclone copy` over en gebruik wat lokaal staat.",
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
        if seed_keuze == "minimal":
            cmd.append("--seed-minimal")
        elif seed_keuze == "geen":
            cmd.append("--skip-seed")
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
        st.markdown("**Bulk (~1000 studenten)** — default werkdata")
        st.caption(
            "Verdeelt 1000 studenten over de top OERs van alle 5 instellingen "
            "met deterministische seed (RNG=2026). Vereist dat OERs eerst zijn geïngest."
        )
        if st.button("Run seed_bulk.py", type="primary"):
            _run_in_placeholder(["uv", "run", "python", "scripts/seed_bulk.py"])
    with col_b:
        st.markdown("**Minimaal (3 + 2)** — dev-demo")
        st.caption(
            "Hardcoded subset: 2 instellingen, 2 OERs, 3 studenten, 2 mentoren. "
            "Bedoeld voor handmatige UI-tests. Geen vervanging voor bulk-seed."
        )
        if st.button("Run seed.py"):
            _run_in_placeholder(["uv", "run", "python", "scripts/seed.py"])

render_footer()
