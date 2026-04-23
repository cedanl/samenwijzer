"""Warm Schrift huisstijl — Fraunces + DM Sans, warm papier, leien navigatie."""

SLATE = "#1C2B3A"
AMBER = "#C4813A"
PAPIER = "#FAFAF5"
GROEN = "#2D7A4F"
ORANJE = "#D97706"
ROOD = "#B91C1C"
GEEL_BRON = "#FEF3C7"
GEEL_RAND = "#D97706"

# Exports die pagina's gebruiken voor kleuren in inline styles
WIT = "#FFFFFF"

CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,400;0,9..144,600;0,9..144,700;1,9..144,400&family=DM+Sans:wght@400;500;600&display=swap');

html, body, [class*="css"] {{
    font-family: 'DM Sans', sans-serif;
    background-color: {PAPIER};
    color: #1C2B3A;
}}

h1, h2, h3 {{
    font-family: 'Fraunces', serif;
    font-weight: 600;
    color: {SLATE};
}}

/* Sidebar verbergen */
[data-testid="stSidebar"],
[data-testid="stSidebarNav"],
[data-testid="stSidebarCollapsedControl"],
section[data-testid="stSidebar"] {{ display: none !important; }}

/* Streamlit-header verbergen */
[data-testid="stHeader"],
header[data-testid="stHeader"] {{ display: none !important; }}

/* Content-ruimte */
.block-container {{
    padding-top: 5rem !important;
    padding-bottom: 5rem !important;
    max-width: 980px;
    margin: 0 auto;
}}

/* ── Vaste navigatiebalk ────────────────────────────────────────────────── */
.block-container > div > [data-testid="stHorizontalBlock"]:first-of-type {{
    position: fixed !important;
    top: 0 !important; left: 0 !important; right: 0 !important;
    height: 54px !important;
    background: {SLATE} !important;
    z-index: 9999 !important;
    padding: 0 28px !important;
    margin: 0 !important;
    max-width: none !important;
    box-shadow: 0 2px 16px rgba(0,0,0,0.18) !important;
    align-items: center !important;
    gap: 2px !important;
}}

.block-container > div > [data-testid="stHorizontalBlock"]:first-of-type
    [data-testid="stColumn"],
.block-container > div > [data-testid="stHorizontalBlock"]:first-of-type
    [data-testid="stVerticalBlock"],
.block-container > div > [data-testid="stHorizontalBlock"]:first-of-type
    [data-testid="element-container"] {{
    flex: 0 0 auto !important;
    min-width: fit-content !important;
    width: auto !important;
    overflow: visible !important;
    background: transparent !important;
}}

/* Spatie-kolom vult resterende ruimte */
.block-container > div > [data-testid="stHorizontalBlock"]:first-of-type
    [data-testid="stColumn"]:nth-last-child(2) {{
    flex: 1 1 auto !important;
    min-width: 0 !important;
}}

/* Nav-links */
.block-container > div > [data-testid="stHorizontalBlock"]:first-of-type
    [data-testid="stPageLink"] a {{
    display: inline-block !important;
    background: transparent !important;
    border-radius: 5px !important;
    padding: 6px 13px !important;
    font-size: 13px !important;
    font-weight: 600 !important;
    color: rgba(255,255,255,0.75) !important;
    text-decoration: none !important;
    white-space: nowrap !important;
    box-shadow: none !important;
    letter-spacing: 0.03em !important;
    font-family: 'DM Sans', sans-serif !important;
    transition: background 0.15s, color 0.15s !important;
}}

.block-container > div > [data-testid="stHorizontalBlock"]:first-of-type
    [data-testid="stPageLink"] a:hover {{
    background: rgba(255,255,255,0.10) !important;
    color: #ffffff !important;
}}

.block-container > div > [data-testid="stHorizontalBlock"]:first-of-type
    [data-testid="stPageLink"] a div,
.block-container > div > [data-testid="stHorizontalBlock"]:first-of-type
    [data-testid="stPageLink"] a p,
.block-container > div > [data-testid="stHorizontalBlock"]:first-of-type
    [data-testid="stPageLink"] a span {{
    overflow: visible !important;
    text-overflow: unset !important;
    white-space: nowrap !important;
    max-width: none !important;
    width: auto !important;
    color: inherit !important;
}}

/* Elders op pagina: neutrale page_link stijl */
[data-testid="stPageLink"] a {{
    display: inline-block !important;
    background: transparent !important;
    border-radius: 5px !important;
    padding: 4px 10px !important;
    font-size: 13px !important;
    font-weight: 600 !important;
    color: {SLATE} !important;
    text-decoration: none !important;
    white-space: nowrap !important;
    box-shadow: none !important;
    font-family: 'DM Sans', sans-serif !important;
}}

[data-testid="stPageLink"] a:hover {{
    background: rgba(28,43,58,0.06) !important;
}}

/* ── Voortgangsbalk ─────────────────────────────────────────────────────── */
.progress-bar-bg {{
    background: rgba(28,43,58,0.10);
    border-radius: 8px;
    height: 10px;
    margin: 5px 0;
    overflow: hidden;
}}
.progress-bar-fill {{
    border-radius: 8px;
    height: 10px;
    background: linear-gradient(90deg, {GROEN} 0%, #3ea868 100%);
    transition: width 0.4s ease;
}}

/* ── Bronkaartje ────────────────────────────────────────────────────────── */
.bron-kaartje {{
    background: {GEEL_BRON};
    border-left: 3px solid {AMBER};
    border-radius: 0 8px 8px 0;
    padding: 0.65rem 1rem;
    font-size: 0.82rem;
    margin-bottom: 0.5rem;
    color: #1C2B3A;
}}

/* ── Chat-bubbles ───────────────────────────────────────────────────────── */
.chat-vraag {{
    background: #EEF2FF;
    border: 1px solid #C7D2FE;
    border-radius: 14px 14px 14px 3px;
    padding: 0.75rem 1.1rem;
    margin-bottom: 0.4rem;
    max-width: 82%;
    font-size: 0.88rem;
    color: #1C2B3A;
    line-height: 1.55;
}}
.chat-antwoord {{
    background: #F7F3EC;
    border: 1px solid #E8DFC8;
    border-radius: 14px 14px 3px 14px;
    padding: 0.75rem 1.1rem;
    margin-bottom: 0.5rem;
    font-size: 0.88rem;
    color: #1C2B3A;
    line-height: 1.6;
}}

/* ── Kaartjes (st.container border=True) ────────────────────────────────── */
[data-testid="stVerticalBlockBorderWrapper"] {{
    background: #FFFFFF !important;
    border-radius: 14px !important;
    border: 1px solid rgba(28,43,58,0.10) !important;
    box-shadow: 0 2px 16px rgba(28,43,58,0.06);
    padding: 4px 8px;
}}

/* ── Knoppen ────────────────────────────────────────────────────────────── */
[data-testid="stBaseButton-primary"],
[data-testid="stBaseButton-primary"] p,
[data-testid="stBaseButton-primary"] span {{
    background-color: {SLATE} !important;
    color: white !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
    border: none !important;
    font-family: 'DM Sans', sans-serif !important;
    font-size: 13px !important;
}}

[data-testid="stBaseButton-primary"]:hover {{
    background-color: #253444 !important;
}}

[data-testid="stBaseButton-secondary"],
[data-testid="stBaseButton-secondary"] p,
[data-testid="stBaseButton-secondary"] span {{
    background-color: {PAPIER} !important;
    border-radius: 8px !important;
    border: 1px solid rgba(28,43,58,0.18) !important;
    font-weight: 600 !important;
    font-size: 13px !important;
    font-family: 'DM Sans', sans-serif !important;
}}

/* ── Chat-input ─────────────────────────────────────────────────────────── */
[data-testid="stBottom"],
[data-testid="stBottomBlockContainer"] {{
    background-color: {PAPIER} !important;
}}

/* ── Footer ─────────────────────────────────────────────────────────────── */
.footer {{
    position: fixed; bottom: 0; left: 0; right: 0;
    background: {PAPIER};
    border-top: 1px solid rgba(28,43,58,0.10);
    padding: 0.45rem 1.5rem;
    font-size: 0.68rem;
    color: rgba(28,43,58,0.45);
    text-align: center;
    z-index: 999;
    font-family: 'DM Sans', sans-serif;
}}
</style>
"""

_NAV_STUDENT = [
    ("💬 OER-assistent", "pages/1_oer_assistent.py"),
    ("📄 Mijn OER", "pages/2_mijn_oer.py"),
    ("📊 Mijn voortgang", "pages/3_mijn_voortgang.py"),
]

_NAV_MENTOR = [
    ("👥 Mijn studenten", "pages/4_mijn_studenten.py"),
    ("🎓 Begeleidingssessie", "pages/5_begeleidingssessie.py"),
]


def render_nav() -> None:
    """Render de vaste navigatiebalk bovenin op basis van de sessierol."""
    import streamlit as st

    rol = st.session_state.get("rol")
    if not rol:
        return

    nav_items = _NAV_STUDENT if rol == "student" else _NAV_MENTOR
    gebruiker = st.session_state.get("gebruiker_naam", "")
    opleiding = st.session_state.get("opleiding", "")

    cols = st.columns([2] * len(nav_items) + [4, 1])
    for i, (label, page) in enumerate(nav_items):
        with cols[i]:
            st.page_link(page, label=label)
    with cols[-2]:
        st.markdown(
            f'<span style="color:rgba(255,255,255,0.6);font-size:0.78rem;'
            f"font-family:'DM Sans',sans-serif\">{gebruiker} · {opleiding}</span>",
            unsafe_allow_html=True,
        )
    with cols[-1]:
        st.page_link("pages/uitloggen.py", label="🚪")


def render_footer() -> None:
    """Render de vaste footer onderaan de pagina."""
    import streamlit as st

    st.markdown(
        '<div class="footer">Samenwijzer OER-assistent · CEDA 2026 · Npuls</div>',
        unsafe_allow_html=True,
    )
