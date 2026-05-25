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


def _run_in_placeholder(cmd: list[str], cwd: Path | None = None) -> None:
    """Toon live output van cmd in een code-block met scrollende tail."""
    cwd = cwd or _PROJECT_ROOT
    st.caption(f"$ {shlex.join(cmd)}  (cwd={cwd})")
    placeholder = st.empty()
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
    # Bounded buffer: een 30-min bootstrap kan tienduizenden rclone-regels produceren.
    buffer: deque[str] = deque(maxlen=_BUFFER_REGELS)
    laatste_paint = 0.0
    for regel in iter(proc.stdout.readline, ""):
        buffer.append(regel)
        # Throttle: per-regel rerender zou de Streamlit-WebSocket overbelasten.
        nu = time.monotonic()
        if nu - laatste_paint > _PAINT_INTERVAL_S:
            placeholder.code("".join(buffer), language="bash")
            laatste_paint = nu
    proc.wait()
    buffer.append(f"\n[exit={proc.returncode}]\n")
    placeholder.code("".join(buffer), language="bash")
    if proc.returncode == 0:
        st.success(f"✅ Klaar (exit=0): `{shlex.join(cmd)}`")
    else:
        st.error(f"❌ Subprocess gefaald (exit={proc.returncode}): `{shlex.join(cmd)}`")


# ── Pagina-header ──────────────────────────────────────────────────────────────
st.title("🛠 Beheer")
st.caption(
    "Tools voor lokaal database-beheer: synchroniseer OERs en "
    "kwalificatiedossiers vanuit Box, herindexeer bestanden, regenereer "
    "testdata en bekijk DB-status. Subprocesses draaien op deze machine en "
    "kunnen meerdere minuten duren."
)

tab_status, tab_bootstrap, tab_sync, tab_ingest, tab_kd, tab_seed = st.tabs(
    [
        "📊 Status",
        "🚀 Bootstrap",
        "☁️ Sync oeren",
        "🗄 Re-ingest",
        "📚 Kwalificatiedossiers",
        "🌱 Seed",
    ]
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

    st.subheader("Kwalificatiedossiers (aanvullende AI-bron)")
    kd_pad = Path(
        os.environ.get(
            "KWALDOSSIERS_PAD",
            str(_PROJECT_ROOT.parent / "kwalificatiedossiers" / "pdfs"),
        )
    )
    if not kd_pad.is_absolute():
        kd_pad = (_PROJECT_ROOT / kd_pad).resolve()
    if kd_pad.exists():
        kd_pdfs = {p.stem for p in kd_pad.glob("*.pdf")}
        kd_mds = {p.stem for p in kd_pad.glob("*.md")}
        db_crebos = {
            r["crebo"]
            for r in conn.execute(
                "SELECT DISTINCT crebo FROM oer_documenten WHERE crebo IS NOT NULL"
            ).fetchall()
        }
        gedekt = db_crebos & kd_mds
        ontbreekt = db_crebos - kd_mds
        n_db = len(db_crebos)
        pct = (len(gedekt) / n_db * 100) if n_db else 0.0
        st.write(
            f"📁 `{kd_pad}` — {len(kd_pdfs)} PDFs, {len(kd_mds)} markdown-bestanden"
        )
        st.write(
            f"🎯 **Coverage**: {len(gedekt)}/{n_db} crebo's in DB hebben een "
            f"KD-markdown ({pct:.0f}%)"
        )
        if ontbreekt:
            with st.expander(f"⚠️ {len(ontbreekt)} crebo's zonder KD-markdown"):
                st.code(", ".join(sorted(ontbreekt)))
    else:
        st.warning(
            f"Map `{kd_pad}` niet gevonden — draai sync of download in de "
            "Kwalificatiedossiers-tab."
        )

# ── Tab: Bootstrap ─────────────────────────────────────────────────────────────
with tab_bootstrap:
    st.subheader("🚀 Volledige machine-setup")
    st.caption(
        "Eén klik = `uv sync` → `rclone copy oeren/` → `rclone copy "
        "kwalificatiedossiers/` → `ingest --alles` → `seed`. "
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

# ── Tab: Kwalificatiedossiers ──────────────────────────────────────────────────
with tab_kd:
    st.subheader("📚 Kwalificatiedossiers (landelijke aanvullende bron)")
    st.caption(
        "De OER blijft leidend; deze landelijke kwalificatiedossiers worden "
        "alleen geraadpleegd als de OER een onderwerp niet of onvoldoende "
        "behandelt. Bestanden leven in `kwalificatiedossiers/` (gitignored) "
        "en synchroniseren via Box, parallel aan `oeren/`."
    )

    col_sync, col_convert, col_download = st.columns(3)

    with col_sync:
        st.markdown("**☁️ Sync vanuit Box**")
        st.caption(
            "Spiegelt `box:samenwijzer/kwalificatiedossiers/` naar lokaal via "
            "`scripts/sync_kwalificatiedossiers.sh`. Snelste pad voor nieuwe "
            "machines."
        )
        if st.button("Start sync", type="primary", key="kd_sync"):
            _run_in_placeholder(["bash", "scripts/sync_kwalificatiedossiers.sh"])

    with col_convert:
        st.markdown("**📝 Re-convert PDFs → markdown**")
        st.caption(
            "Draait `scripts/convert_kwalificatiedossiers_md.py` (markitdown, "
            "8 workers parallel). Bestaande `.md`-bestanden worden "
            "overgeslagen — verwijder ze handmatig voor een schone "
            "herconversie."
        )
        if st.button("Start conversie", key="kd_convert"):
            _run_in_placeholder(
                ["uv", "run", "python", "scripts/convert_kwalificatiedossiers_md.py"]
            )

    with col_download:
        st.markdown("**⬇️ Herbouw uit s-bb.nl**")
        st.caption(
            "Volledige rebuild: download crebolijsten + bron-zips van s-bb en "
            "kopieer PDFs per crebo. Bestaande PDFs worden overschreven. "
            "Alleen nodig bij een nieuwe s-bb-herziening."
        )
        bevestig_kd = st.checkbox(
            "Ja, ik wil PDFs opnieuw downloaden",
            value=False,
            key="kd_download_bevestig",
        )
        if st.button("Start rebuild", disabled=not bevestig_kd, key="kd_download"):
            _run_in_placeholder(
                [
                    "uv",
                    "run",
                    "--with",
                    "openpyxl",
                    "python",
                    "scripts/download_kwalificatiedossiers.py",
                ]
            )

    st.divider()
    st.markdown("**Upload lokale wijzigingen naar Box**")
    st.caption(
        "Gebruik dit alleen nadat je de PDF/MD-set hebt herbouwd op deze "
        "machine en andere machines de nieuwe versie moeten kunnen syncen. "
        "Skipt de bron-zips automatisch."
    )
    if st.button("Upload naar Box", key="kd_upload"):
        _run_in_placeholder(
            ["bash", "scripts/sync_kwalificatiedossiers.sh", "--upload"]
        )


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
