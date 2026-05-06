"""OER Codex — juridisch-editorial typografie voor de OER-assistent.

Fraunces (display, drop caps) + Newsreader (body) + IBM Plex Mono (verwijzingen).
Warm parchment, inkt-zwart, bordeaux juridisch accent, ochre marginalia.
"""

# ── Codex-palet ────────────────────────────────────────────────────────────────
INKT = "#1A1410"          # body, koppen, nav-bg
PAPIER = "#F4EFE6"        # hoofdachtergrond — warm parchment
PAPIER_LICHT = "#FAF5E9"  # citatiekaders, raised surfaces
BORDEAUX = "#7A1828"      # juridisch zegelaccent
OCHRE = "#A88A5C"         # marginalia, ornamenten, hover-tints
HAARLIJN = "#D9CFB8"      # subtiele scheidingslijnen

# Backwards-compat aliassen — bestaande pagina's gebruiken deze nog
SLATE = INKT
AMBER = OCHRE
GROEN = "#2D7A4F"
ORANJE = "#D97706"
ROOD = BORDEAUX
GEEL_BRON = PAPIER_LICHT
GEEL_RAND = OCHRE
WIT = "#FFFFFF"

CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,400;0,9..144,500;0,9..144,600;0,9..144,700;1,9..144,400;1,9..144,500&family=Newsreader:ital,opsz,wght@0,6..72,400;0,6..72,500;0,6..72,600;1,6..72,400;1,6..72,500&family=IBM+Plex+Mono:wght@400;500&display=swap');

html, body, [class*="css"] {{
    font-family: 'Newsreader', 'Source Serif Pro', Georgia, serif;
    font-size: 17px;
    line-height: 1.62;
    background-color: {PAPIER};
    background-image: radial-gradient(rgba(168, 138, 92, 0.06) 1px, transparent 1px);
    background-size: 18px 18px;
    color: {INKT};
}}

h1, h2, h3, h4,
[data-testid="stMarkdown"] h1,
[data-testid="stMarkdown"] h2,
[data-testid="stMarkdown"] h3,
[data-testid="stMarkdown"] h4,
[data-testid="stMarkdownContainer"] h1,
[data-testid="stMarkdownContainer"] h2,
[data-testid="stMarkdownContainer"] h3,
[data-testid="stMarkdownContainer"] h4,
[data-testid="stHeadingWithActionElements"] h1,
[data-testid="stHeadingWithActionElements"] h2,
[data-testid="stHeadingWithActionElements"] h3 {{
    font-family: 'Fraunces', Georgia, serif !important;
    font-weight: 500 !important;
    color: {INKT} !important;
    letter-spacing: -0.012em !important;
}}

[data-testid="stMarkdown"] h1,
[data-testid="stMarkdownContainer"] h1,
[data-testid="stHeadingWithActionElements"] h1,
h1 {{
    font-size: 2.6rem !important;
    line-height: 1.05 !important;
    margin-bottom: 0.2em !important;
}}

[data-testid="stMarkdown"] h2,
[data-testid="stMarkdownContainer"] h2,
h2 {{
    font-size: 1.7rem !important;
    margin-top: 1.6em !important;
    margin-bottom: 0.35em !important;
}}

[data-testid="stMarkdown"] h3,
[data-testid="stMarkdownContainer"] h3,
h3 {{ font-size: 1.25rem !important; }}

a {{
    color: {BORDEAUX};
    text-decoration: underline;
    text-decoration-color: {OCHRE};
    text-underline-offset: 3px;
}}

[data-testid="stSidebar"],
[data-testid="stSidebarNav"],
[data-testid="stSidebarCollapsedControl"],
section[data-testid="stSidebar"] {{ display: none !important; }}

[data-testid="stHeader"],
header[data-testid="stHeader"] {{ display: none !important; }}

.block-container {{
    padding-top: 5rem !important;
    padding-bottom: 5rem !important;
    max-width: 820px;
    margin: 0 auto;
}}

/* ── Vaste navigatiebalk ────────────────────────────────────────────────── */
.block-container > div > [data-testid="stHorizontalBlock"]:first-of-type {{
    position: fixed !important;
    top: 0 !important; left: 0 !important; right: 0 !important;
    height: 50px !important;
    background: {INKT} !important;
    z-index: 9999 !important;
    padding: 0 28px !important;
    margin: 0 !important;
    max-width: none !important;
    border-bottom: 1px solid {BORDEAUX} !important;
    box-shadow: none !important;
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

.block-container > div > [data-testid="stHorizontalBlock"]:first-of-type
    [data-testid="stColumn"]:nth-last-child(2) {{
    flex: 1 1 auto !important;
    min-width: 0 !important;
}}

/* Nav-links — Fraunces small caps, geen knop-achtige badges */
.block-container > div > [data-testid="stHorizontalBlock"]:first-of-type
    [data-testid="stPageLink"] a {{
    display: inline-block !important;
    background: transparent !important;
    border: none !important;
    border-radius: 0 !important;
    padding: 6px 14px !important;
    font-family: 'Fraunces', serif !important;
    font-size: 14px !important;
    font-weight: 500 !important;
    font-variant-caps: all-small-caps !important;
    letter-spacing: 0.13em !important;
    color: rgba(244,239,230,0.65) !important;
    text-decoration: none !important;
    white-space: nowrap !important;
    box-shadow: none !important;
    transition: color 0.18s !important;
}}

.block-container > div > [data-testid="stHorizontalBlock"]:first-of-type
    [data-testid="stPageLink"] a:hover {{
    background: transparent !important;
    color: {PAPIER} !important;
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

/* Elders: page_link in document-tinten */
[data-testid="stPageLink"] a {{
    display: inline-block !important;
    background: transparent !important;
    border-radius: 2px !important;
    padding: 4px 10px !important;
    font-family: 'Fraunces', serif !important;
    font-size: 14px !important;
    font-weight: 500 !important;
    font-variant-caps: all-small-caps !important;
    letter-spacing: 0.10em !important;
    color: {INKT} !important;
    text-decoration: none !important;
    white-space: nowrap !important;
    box-shadow: none !important;
}}

[data-testid="stPageLink"] a:hover {{
    background: rgba(122,24,40,0.06) !important;
}}

/* ── Voortgangsbalk ─────────────────────────────────────────────────────── */
.progress-bar-bg {{
    background: rgba(26,20,16,0.10);
    border-radius: 0;
    height: 8px;
    margin: 5px 0;
    overflow: hidden;
}}
.progress-bar-fill {{
    height: 8px;
    background: {BORDEAUX};
    transition: width 0.4s ease;
}}

/* ── Bronkaartje (citatie-stijl) ────────────────────────────────────────── */
.bron-kaartje {{
    background: {PAPIER_LICHT};
    border-left: 2px solid {BORDEAUX};
    border-radius: 0;
    padding: 0.75rem 1.1rem;
    font-family: 'Newsreader', serif;
    font-size: 0.95rem;
    margin-bottom: 0.5rem;
    color: {INKT};
}}

/* ── Vraag/Antwoord als documentpassages — geen bubbles ─────────────────── */
.chat-vraag {{
    margin: 1.6rem 0 0.4rem 0;
    padding: 0 0 0 1rem;
    border: none;
    border-left: 2px solid {OCHRE};
    background: none;
    color: {INKT};
    font-family: 'Newsreader', serif;
    font-style: italic;
    font-size: 1.08rem;
    line-height: 1.55;
    max-width: 100%;
    border-radius: 0;
}}

.chat-vraag::before {{
    content: 'Vraag';
    display: block;
    font-style: normal;
    font-family: 'Fraunces', serif;
    font-variant-caps: all-small-caps;
    letter-spacing: 0.20em;
    font-size: 0.72rem;
    color: {OCHRE};
    margin-bottom: 0.25rem;
    font-weight: 500;
}}

.chat-antwoord {{
    margin: 0.4rem 0 1.8rem 0;
    padding: 0;
    border: none;
    background: none;
    color: {INKT};
    font-family: 'Newsreader', serif;
    font-size: 1rem;
    line-height: 1.7;
    border-radius: 0;
}}

.chat-antwoord::before {{
    content: 'Antwoord';
    display: block;
    font-family: 'Fraunces', serif;
    font-variant-caps: all-small-caps;
    letter-spacing: 0.20em;
    font-size: 0.72rem;
    color: {BORDEAUX};
    margin-bottom: 0.4rem;
    font-weight: 500;
}}

/* Drop cap op het eerste paragraaf van een antwoord */
.chat-antwoord > p:first-of-type::first-letter,
.chat-antwoord > div > p:first-of-type::first-letter {{
    font-family: 'Fraunces', serif;
    font-weight: 500;
    color: {BORDEAUX};
    float: left;
    font-size: 3.6em;
    line-height: 0.85;
    padding: 0.05em 0.16em 0 0;
    margin-top: 0.04em;
}}

/* Markdown-blockquotes binnen antwoorden → pull-quote citaten */
.chat-antwoord blockquote {{
    background: {PAPIER_LICHT};
    border-left: 3px solid {BORDEAUX};
    margin: 1rem 0;
    padding: 0.75rem 1.1rem;
    font-family: 'Newsreader', serif;
    font-style: italic;
    color: {INKT};
}}

.chat-antwoord blockquote p {{ margin: 0; }}

.chat-antwoord code {{
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.85em;
    background: rgba(168,138,92,0.14);
    padding: 1px 5px;
    border-radius: 2px;
    color: {INKT};
}}

/* ── Codex-helpers ──────────────────────────────────────────────────────── */
.oer-mark {{
    font-family: 'Fraunces', serif;
    font-style: italic;
    font-weight: 400;
    color: {OCHRE};
    font-size: 3.4rem;
    line-height: 1;
    letter-spacing: -0.04em;
    text-align: right;
}}

.oer-overtitel {{
    font-family: 'Fraunces', serif;
    font-variant-caps: all-small-caps;
    letter-spacing: 0.20em;
    font-size: 0.80rem;
    color: {OCHRE};
    margin-bottom: 0.3rem;
    font-weight: 500;
}}

.oer-ondertitel {{
    font-family: 'Newsreader', serif;
    font-style: italic;
    color: rgba(26,20,16,0.7);
    font-size: 1.05rem;
    margin-top: 0.2rem;
}}

.oer-ornament {{
    text-align: center;
    color: {OCHRE};
    font-size: 1.2rem;
    margin: 1.6rem 0 1.2rem 0;
    letter-spacing: 1em;
}}

.oer-meta {{
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.78rem;
    color: rgba(26,20,16,0.65);
    letter-spacing: 0.02em;
    line-height: 1.5;
}}

.oer-citaat {{
    background: {PAPIER_LICHT};
    border-left: 3px solid {BORDEAUX};
    margin: 1.2rem 0;
    padding: 0.9rem 1.2rem;
    font-family: 'Newsreader', serif;
    font-style: italic;
    color: {INKT};
}}

.oer-citaat-bron {{
    display: block;
    margin-top: 0.5rem;
    font-style: normal;
    font-variant-caps: all-small-caps;
    letter-spacing: 0.14em;
    font-size: 0.72rem;
    color: {OCHRE};
}}

/* ── Containers (st.container border=True) ────────────────────────────── */
[data-testid="stVerticalBlockBorderWrapper"] {{
    background: {PAPIER_LICHT} !important;
    border-radius: 0 !important;
    border: 1px solid {HAARLIJN} !important;
    box-shadow: none !important;
    padding: 6px 12px;
}}

/* ── Knoppen — sober, edition-stijl ────────────────────────────────────── */
[data-testid="stBaseButton-primary"],
[data-testid="stBaseButton-primary"] p,
[data-testid="stBaseButton-primary"] span {{
    background-color: {BORDEAUX} !important;
    color: {PAPIER} !important;
    border-radius: 2px !important;
    font-family: 'Fraunces', serif !important;
    font-variant-caps: all-small-caps !important;
    letter-spacing: 0.13em !important;
    font-size: 0.95rem !important;
    font-weight: 500 !important;
    border: 1px solid {BORDEAUX} !important;
    padding: 0.55rem 1.2rem !important;
    box-shadow: none !important;
}}

[data-testid="stBaseButton-primary"]:hover {{
    background-color: #5C111E !important;
    border-color: #5C111E !important;
}}

[data-testid="stBaseButton-secondary"],
[data-testid="stBaseButton-secondary"] p,
[data-testid="stBaseButton-secondary"] span {{
    background-color: transparent !important;
    color: {INKT} !important;
    border-radius: 2px !important;
    border: 1px solid {HAARLIJN} !important;
    font-family: 'Fraunces', serif !important;
    font-variant-caps: all-small-caps !important;
    letter-spacing: 0.10em !important;
    font-size: 0.92rem !important;
    font-weight: 500 !important;
    padding: 0.5rem 1rem !important;
}}

[data-testid="stBaseButton-secondary"]:hover {{
    background-color: {PAPIER_LICHT} !important;
    border-color: {OCHRE} !important;
    color: {INKT} !important;
}}

/* ── Form elements ─────────────────────────────────────────────────────── */
[data-testid="stTextInput"] input,
[data-testid="stTextArea"] textarea {{
    background: {PAPIER_LICHT} !important;
    border: 1px solid {HAARLIJN} !important;
    border-radius: 2px !important;
    font-family: 'Newsreader', serif !important;
    color: {INKT} !important;
}}

[data-testid="stTextInput"] input:focus,
[data-testid="stTextArea"] textarea:focus {{
    border-color: {BORDEAUX} !important;
    box-shadow: 0 0 0 1px {BORDEAUX} !important;
}}

/* ── Tabs ─────────────────────────────────────────────────────────────── */
[data-testid="stTabs"] [role="tab"] p {{
    font-family: 'Fraunces', serif !important;
    font-variant-caps: all-small-caps !important;
    letter-spacing: 0.13em !important;
    font-size: 0.95rem !important;
    font-weight: 500 !important;
    color: rgba(26,20,16,0.55) !important;
}}

[data-testid="stTabs"] [role="tab"][aria-selected="true"] p {{
    color: {BORDEAUX} !important;
}}

[data-testid="stTabs"] [data-baseweb="tab-highlight"] {{
    background: {BORDEAUX} !important;
}}

/* ── Chat-input ─────────────────────────────────────────────────────────── */
[data-testid="stBottom"],
[data-testid="stBottomBlockContainer"] {{
    background-color: {PAPIER} !important;
    border-top: 1px solid {HAARLIJN} !important;
}}

[data-testid="stChatInput"],
[data-testid="stChatInputTextArea"],
[data-testid="stChatInput"] textarea {{
    background: {PAPIER_LICHT} !important;
    border: 1px solid {HAARLIJN} !important;
    border-radius: 2px !important;
    font-family: 'Newsreader', serif !important;
    color: {INKT} !important;
}}

/* ── Footer — small caps met ornament ───────────────────────────────────── */
.footer {{
    position: fixed; bottom: 0; left: 0; right: 0;
    background: {PAPIER};
    border-top: 1px solid {HAARLIJN};
    padding: 0.55rem 1.5rem;
    font-family: 'Fraunces', serif;
    font-variant-caps: all-small-caps;
    letter-spacing: 0.20em;
    font-size: 0.72rem;
    color: rgba(26,20,16,0.55);
    text-align: center;
    z-index: 999;
}}

.footer::before, .footer::after {{
    content: ' ⸻ ';
    color: {OCHRE};
    letter-spacing: 0;
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


def _opleiding_naam(opleiding: str, crebo: str) -> str:
    """Extraheer leesbare naam uit het opleiding-veld en formatteer als 'Naam (crebo)'."""
    import re

    naam = re.sub(r"^\d+[_\s][A-Z]+[_\s]\d+[_\s]+", "", opleiding)  # strip CREBO_BOL_2025__
    naam = re.sub(rf"^{re.escape(crebo)}\s+", "", naam)  # strip leading crebo (met spatie)
    naam = re.sub(r"\bOER\s*\([^)]+\)\s*[-–]\s*", "", naam)  # strip "OER (OUD) - "
    naam = re.sub(rf"\b{re.escape(crebo)}\b\s*[-–]?\s*", "", naam)  # strip resterende crebo
    naam = re.sub(r"\s+\d+\s+(maanden|jaar)$", "", naam)  # strip " 36 maanden"
    naam = naam.strip()
    # Da Vinci filenaam-stijl (geen spaties): CREBOLEERWEGJAARExamenplan/MJP[-naam-cohort-jaar]
    if " " not in naam:
        naam = re.sub(rf"^{re.escape(crebo)}[A-Z]{{3}}\d{{4}}(?:Examenplan|MJP)[-_]?", "", naam)
        naam = re.sub(r"[-_]cohort[-_]\d{4}$", "", naam)
        naam = naam.replace("-", " ").replace("_", " ").strip()
    return f"{naam} ({crebo})" if naam else f"Opleiding {crebo}"


def render_student_info() -> None:
    """Render de student-identiteitsbalk onder de navigatie."""
    import streamlit as st

    naam = st.session_state.get("gebruiker_naam", "")
    leerweg = st.session_state.get("leerweg", "")
    opleiding = st.session_state.get("opleiding", "")
    crebo = st.session_state.get("crebo", "")
    instelling = st.session_state.get("instelling", "")
    opleiding_label = _opleiding_naam(opleiding, crebo) if opleiding and crebo else opleiding
    onderdelen = [x for x in [naam, leerweg, opleiding_label, instelling] if x]
    st.markdown(
        f'<p style="color:rgba(28,43,58,0.7);font-size:0.85rem;'
        f"font-family:'DM Sans',sans-serif;margin:0.4rem 0 0.8rem 0\">"
        f"{'&nbsp;&nbsp;|&nbsp;&nbsp;'.join(onderdelen)}</p>",
        unsafe_allow_html=True,
    )


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
