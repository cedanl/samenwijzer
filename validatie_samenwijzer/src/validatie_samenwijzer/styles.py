"""Validatie Samenwijzer — moderne, student-vriendelijke stijl.

Wit + grijs + zacht oranje (terracotta) op basis van de CEDA-huisstijl,
met witte achtergrond en lucht in plaats van de roze CEDA-achtergrond.
General Sans typografie, geen serif, geen drop caps.
"""

# ── Palet ──────────────────────────────────────────────────────────────────
WIT = "#ffffff"
MIST = "#fafafa"               # cards, citatie-blokjes, hover-tints
LIJN = "#e5e5e7"               # borders, scheidingslijnen
GRIJS_TEKST = "#6b7280"        # secondary text, labels, meta
INKT = "#1a1a1a"               # body, koppen
TERRACOTTA = "#c8785a"         # primaire accent — links, knoppen, tab-highlight
TERRACOTTA_LICHT = "#fae3d6"   # vraag-bubble, focus-glow
TERRACOTTA_DONKER = "#a85f44"  # hover op primaire knop

# Status-tinten — gebruikt in pagina's voor voortgang/risico-indicatoren
GROEN = "#27ae60"
ORANJE = "#e67e22"
ROOD = "#c0392b"

CSS = f"""
<style>
@import url('https://api.fontshare.com/v2/css?f[]=general-sans@400,500,600,700&display=swap');

html, body, [class*="css"] {{
    font-family: 'General Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    font-size: 16px;
    line-height: 1.55;
    background-color: {WIT};
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
    font-family: 'General Sans', sans-serif !important;
    font-weight: 600 !important;
    color: {INKT} !important;
    letter-spacing: -0.01em !important;
}}

[data-testid="stMarkdown"] h1,
[data-testid="stMarkdownContainer"] h1,
[data-testid="stHeadingWithActionElements"] h1,
h1 {{
    font-size: 2.4rem !important;
    line-height: 1.15 !important;
    margin-bottom: 0.3em !important;
}}

[data-testid="stMarkdown"] h2,
[data-testid="stMarkdownContainer"] h2,
h2 {{
    font-size: 1.5rem !important;
    margin-top: 1.4em !important;
    margin-bottom: 0.4em !important;
}}

[data-testid="stMarkdown"] h3,
[data-testid="stMarkdownContainer"] h3,
h3 {{ font-size: 1.15rem !important; }}

a {{
    color: {TERRACOTTA};
    text-decoration: none;
    border-bottom: 1px solid {TERRACOTTA_LICHT};
    transition: border-color 0.15s;
}}

a:hover {{
    border-bottom-color: {TERRACOTTA};
}}

[data-testid="stSidebar"],
[data-testid="stSidebarNav"],
[data-testid="stSidebarCollapsedControl"],
section[data-testid="stSidebar"] {{ display: none !important; }}

[data-testid="stHeader"],
header[data-testid="stHeader"] {{ display: none !important; }}

.block-container {{
    padding-top: 4.5rem !important;
    padding-bottom: 5rem !important;
    max-width: 860px;
    margin: 0 auto;
}}

/* ── Vaste navigatiebalk — wit met grijze onderlijn ─────────────────────── */
.block-container > div > [data-testid="stHorizontalBlock"]:first-of-type {{
    position: fixed !important;
    top: 0 !important; left: 0 !important; right: 0 !important;
    height: 56px !important;
    background: {WIT} !important;
    z-index: 9999 !important;
    padding: 0 28px !important;
    margin: 0 !important;
    max-width: none !important;
    border-bottom: 1px solid {LIJN} !important;
    box-shadow: none !important;
    align-items: center !important;
    gap: 4px !important;
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

.block-container > div > [data-testid="stHorizontalBlock"]:first-of-type
    [data-testid="stPageLink"] a {{
    display: inline-block !important;
    background: transparent !important;
    border: none !important;
    border-radius: 6px !important;
    padding: 8px 14px !important;
    font-family: 'General Sans', sans-serif !important;
    font-size: 14px !important;
    font-weight: 500 !important;
    color: {GRIJS_TEKST} !important;
    text-decoration: none !important;
    white-space: nowrap !important;
    box-shadow: none !important;
    transition: color 0.15s, background 0.15s !important;
}}

.block-container > div > [data-testid="stHorizontalBlock"]:first-of-type
    [data-testid="stPageLink"] a:hover {{
    background: {MIST} !important;
    color: {INKT} !important;
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

[data-testid="stPageLink"] a {{
    display: inline-block !important;
    background: transparent !important;
    border-radius: 6px !important;
    padding: 6px 12px !important;
    font-family: 'General Sans', sans-serif !important;
    font-size: 14px !important;
    font-weight: 500 !important;
    color: {INKT} !important;
    text-decoration: none !important;
    white-space: nowrap !important;
    box-shadow: none !important;
}}

[data-testid="stPageLink"] a:hover {{
    background: {MIST} !important;
}}

/* ── Voortgangsbalk ─────────────────────────────────────────────────────── */
.progress-bar-bg {{
    background: {LIJN};
    border-radius: 4px;
    height: 8px;
    margin: 5px 0;
    overflow: hidden;
}}
.progress-bar-fill {{
    height: 8px;
    background: {TERRACOTTA};
    border-radius: 4px;
    transition: width 0.4s ease;
}}

/* ── Bron-kaartje ───────────────────────────────────────────────────────── */
.bron-kaartje {{
    background: {MIST};
    border-left: 3px solid {TERRACOTTA};
    border-radius: 4px;
    padding: 0.75rem 1.1rem;
    font-family: 'General Sans', sans-serif;
    font-size: 0.95rem;
    margin-bottom: 0.5rem;
    color: {INKT};
}}

/* ── Chat-bubbles ───────────────────────────────────────────────────────── */
.chat-vraag {{
    margin: 1rem 0 0.4rem auto;
    padding: 10px 14px;
    background: {TERRACOTTA_LICHT};
    border-radius: 16px 16px 4px 16px;
    color: {INKT};
    font-family: 'General Sans', sans-serif;
    font-size: 0.98rem;
    line-height: 1.5;
    max-width: 75%;
    width: fit-content;
}}

.chat-antwoord {{
    margin: 0.4rem auto 1.4rem 0;
    padding: 12px 16px;
    background: {WIT};
    border: 1px solid {LIJN};
    border-radius: 16px 16px 16px 4px;
    color: {INKT};
    font-family: 'General Sans', sans-serif;
    font-size: 1rem;
    line-height: 1.6;
    max-width: 90%;
}}

.chat-antwoord blockquote {{
    background: {MIST};
    border-left: 3px solid {TERRACOTTA};
    border-radius: 4px;
    margin: 0.8rem 0;
    padding: 0.6rem 1rem;
    font-family: 'General Sans', sans-serif;
    color: {INKT};
}}

.chat-antwoord blockquote p {{ margin: 0; }}

.chat-antwoord code {{
    font-family: ui-monospace, 'SF Mono', Menlo, monospace;
    font-size: 0.85em;
    background: {MIST};
    padding: 1px 5px;
    border-radius: 4px;
    color: {INKT};
}}

/* ── Landingspagina-helpers ─────────────────────────────────────────────── */
.oer-mark {{
    font-family: 'General Sans', sans-serif;
    font-weight: 600;
    color: {TERRACOTTA};
    font-size: 3.4rem;
    line-height: 1;
    letter-spacing: -0.02em;
    text-align: right;
}}

.oer-overtitel {{
    font-family: 'General Sans', sans-serif;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    font-size: 0.78rem;
    color: {GRIJS_TEKST};
    margin-bottom: 0.3rem;
    font-weight: 600;
}}

.oer-ondertitel {{
    font-family: 'General Sans', sans-serif;
    color: {GRIJS_TEKST};
    font-size: 1.05rem;
    margin-top: 0.2rem;
}}

.oer-ornament {{
    text-align: center;
    color: {TERRACOTTA};
    font-size: 1.1rem;
    margin: 1.4rem 0 1rem 0;
    letter-spacing: 0.6em;
}}

.oer-meta {{
    font-family: ui-monospace, 'SF Mono', Menlo, monospace;
    font-size: 0.78rem;
    color: {GRIJS_TEKST};
    letter-spacing: 0.02em;
    line-height: 1.5;
}}

.oer-intro {{
    font-family: 'General Sans', sans-serif;
    font-size: 1.05rem;
    line-height: 1.6;
    color: {GRIJS_TEKST};
    max-width: 60ch;
}}

.oer-citaat {{
    background: {MIST};
    border-left: 3px solid {TERRACOTTA};
    border-radius: 4px;
    margin: 1.2rem 0;
    padding: 0.9rem 1.2rem;
    font-family: 'General Sans', sans-serif;
    color: {INKT};
}}

.oer-citaat-bron {{
    display: block;
    margin-top: 0.5rem;
    text-transform: uppercase;
    letter-spacing: 0.10em;
    font-size: 0.72rem;
    color: {GRIJS_TEKST};
    font-weight: 600;
}}

/* ── Containers (st.container border=True) ──────────────────────────────── */
[data-testid="stVerticalBlockBorderWrapper"] {{
    background: {WIT} !important;
    border-radius: 12px !important;
    border: 1px solid {LIJN} !important;
    box-shadow: none !important;
    padding: 8px 14px;
}}

/* ── Knoppen ─────────────────────────────────────────────────────────────── */
[data-testid="stBaseButton-primary"],
[data-testid="stBaseButton-primary"] p,
[data-testid="stBaseButton-primary"] span {{
    background-color: {TERRACOTTA} !important;
    color: {WIT} !important;
    border-radius: 50px !important;
    font-family: 'General Sans', sans-serif !important;
    letter-spacing: 0.02em !important;
    font-size: 0.95rem !important;
    font-weight: 600 !important;
    border: 1px solid {TERRACOTTA} !important;
    padding: 0.55rem 1.4rem !important;
    box-shadow: none !important;
}}

[data-testid="stBaseButton-primary"]:hover {{
    background-color: {TERRACOTTA_DONKER} !important;
    border-color: {TERRACOTTA_DONKER} !important;
}}

[data-testid="stBaseButton-secondary"],
[data-testid="stBaseButton-secondary"] p,
[data-testid="stBaseButton-secondary"] span {{
    background-color: {WIT} !important;
    color: {INKT} !important;
    border-radius: 50px !important;
    border: 1px solid {LIJN} !important;
    font-family: 'General Sans', sans-serif !important;
    font-size: 0.92rem !important;
    font-weight: 500 !important;
    padding: 0.5rem 1.2rem !important;
}}

[data-testid="stBaseButton-secondary"]:hover {{
    background-color: {MIST} !important;
    border-color: {GRIJS_TEKST} !important;
    color: {INKT} !important;
}}

/* ── Form elements ──────────────────────────────────────────────────────── */
[data-testid="stTextInput"] input,
[data-testid="stTextArea"] textarea {{
    background: {WIT} !important;
    border: 1px solid {LIJN} !important;
    border-radius: 8px !important;
    font-family: 'General Sans', sans-serif !important;
    color: {INKT} !important;
}}

[data-testid="stTextInput"] input:focus,
[data-testid="stTextArea"] textarea:focus {{
    border-color: {TERRACOTTA} !important;
    box-shadow: 0 0 0 3px {TERRACOTTA_LICHT} !important;
}}

/* ── Tabs ───────────────────────────────────────────────────────────────── */
[data-testid="stTabs"] [role="tab"] p {{
    font-family: 'General Sans', sans-serif !important;
    font-size: 0.95rem !important;
    font-weight: 500 !important;
    color: {GRIJS_TEKST} !important;
}}

[data-testid="stTabs"] [role="tab"][aria-selected="true"] p {{
    color: {INKT} !important;
    font-weight: 600 !important;
}}

[data-testid="stTabs"] [data-baseweb="tab-highlight"] {{
    background: {TERRACOTTA} !important;
}}

/* ── Chat-input ─────────────────────────────────────────────────────────── */
[data-testid="stBottom"],
[data-testid="stBottomBlockContainer"] {{
    background-color: {WIT} !important;
    border-top: 1px solid {LIJN} !important;
}}

[data-testid="stChatInput"],
[data-testid="stChatInputTextArea"],
[data-testid="stChatInput"] textarea {{
    background: {WIT} !important;
    border: 1px solid {LIJN} !important;
    border-radius: 12px !important;
    font-family: 'General Sans', sans-serif !important;
    color: {INKT} !important;
}}

/* ── Footer ─────────────────────────────────────────────────────────────── */
.footer {{
    position: fixed; bottom: 0; left: 0; right: 0;
    background: {WIT};
    border-top: 1px solid {LIJN};
    padding: 0.6rem 1.5rem;
    font-family: 'General Sans', sans-serif;
    font-size: 0.78rem;
    color: {GRIJS_TEKST};
    text-align: center;
    z-index: 999;
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
        f'<p style="color:{GRIJS_TEKST};font-size:0.85rem;'
        f"font-family:'General Sans',sans-serif;margin:0.4rem 0 0.8rem 0\">"
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
            f'<span style="color:{GRIJS_TEKST};font-size:0.78rem;'
            f"font-family:'General Sans',sans-serif\">{gebruiker} · {opleiding}</span>",
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
