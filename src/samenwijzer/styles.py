"""EduPulse / Samenwijzer huisstijl — kleuren en CSS-injectie."""

# ── Kleuren ───────────────────────────────────────────────────────────────────
TERRACOTTA = "#c8785a"
ROZE_BG = "#f0d4d4"
ROZE_LICHT = "#fae8e8"
ZWART = "#1a1a1a"
ROOD = "#c0392b"
ORANJE = "#e67e22"
GROEN = "#27ae60"

# ── CSS ───────────────────────────────────────────────────────────────────────
FOOTER_HTML = """
<div style="
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    background-color: #ffffff;
    padding: 10px 24px;
    text-align: center;
    font-family: 'General Sans', sans-serif;
    font-size: 12px;
    color: #333;
    line-height: 1.7;
    z-index: 999;
">
    <p style="text-align:center; font-size:0.5rem; font-weight:500; color:#1a1a1a; font-family:'General Sans',sans-serif; margin:1px 0;"><br>
        <img src="https://mirrors.creativecommons.org/presskit/icons/cc.svg" alt="" style="max-width: 2em;max-height:3em;margin-left: .2em;"><img src="https://mirrors.creativecommons.org/presskit/icons/by.svg" alt="" style="max-width: 2em;max-height:3em;margin-left: .2em;"> Op deze analytics tool is de Creative Commons ShareAlike
        Naamsvermelding 4.0-licentie van toepassing. <br>Maak bij gebruik van dit werk
        vermelding van de volgende referentie: AI en data waarde(n)vol inzetten: CEDA
        2026 Samenwijzer. Utrecht: Npuls
    </p>
</div>
"""

_NAV_STUDENT = [
    ("📚 Home", "/"),
    ("📊 Mijn voortgang", "/mijn_voortgang"),
    ("🎓 Leercoach", "/leercoach"),
    ("💚 Welzijn", "/welzijn"),
]

_NAV_DOCENT = [
    ("📚 Home", "/"),
    ("👥 Groepsoverzicht", "/groepsoverzicht"),
    ("📬 Outreach", "/outreach"),
    ("🎓 Leercoach", "/leercoach"),
]

# Pill-stijl gedeeld door alle nav-items (inclusief uitloggen)
_PILL = (
    "display:inline-block;"
    "background:#ffffff;"
    "border-radius:50px;"
    "padding:7px 18px;"
    "font-size:13px;"
    "font-weight:700;"
    "color:#1a1a1a;"
    "text-decoration:none;"
    "white-space:nowrap;"
    "box-shadow:0 4px 16px rgba(0,0,0,0.13);"
    "letter-spacing:0.05em;"
    "font-family:'General Sans',sans-serif;"
    "transition:background 0.15s;"
)


def render_nav() -> None:
    """Render de vaste navigatiebalk bovenaan in de header-zone.

    Injecteert een HTML-div met position:fixed die de Streamlit-header
    vervangt. Alle items — inclusief Uitloggen — hebben dezelfde pill-stijl.
    Uitloggen navigeert naar /uitloggen, dat de sessie wist en terugkeert
    naar de startpagina.

    Aanroepen direct ná st.markdown(CSS, unsafe_allow_html=True).
    """
    import streamlit as st

    rol = st.session_state.get("rol")
    if not rol:
        return

    nav_items = _NAV_STUDENT if rol == "student" else _NAV_DOCENT
    gebruiker = (
        st.session_state.get("studentnummer", "")
        if rol == "student"
        else st.session_state.get("mentor_naam", "")
    )

    links = "".join(
        f'<a href="{url}" target="_self" style="{_PILL}">{label}</a>' for label, url in nav_items
    )

    uitloggen = f'<a href="/uitloggen" target="_self" style="{_PILL}">Uitloggen</a>'

    gebruiker_html = (
        f'<span style="color:#888;font-size:12px;font-weight:600;'
        f"white-space:nowrap;font-family:'General Sans',sans-serif;\">👤 {gebruiker}</span>"
    )

    st.markdown(
        f"""
<div style="
    position: fixed;
    top: 0; left: 0; right: 0;
    height: 56px;
    background: #ffffff;
    z-index: 9999;
    display: flex;
    align-items: center;
    padding: 0 24px;
    gap: 8px;
    box-shadow: 0 1px 0 rgba(0,0,0,0.08);
">
    {links}
    <div style="flex:1"></div>
    {gebruiker_html}
    {uitloggen}
</div>
""",
        unsafe_allow_html=True,
    )


def render_footer() -> None:
    """Render de huisstijl footer onderaan de pagina."""
    import streamlit as st

    st.markdown(FOOTER_HTML, unsafe_allow_html=True)


CSS = """
<style>
@import url('https://api.fontshare.com/v2/css?f[]=general-sans@400,500,600,700&display=swap');

[data-testid="stApp"] {
    background-color: #f0d4d4;
    font-family: 'General Sans', sans-serif;
    font-weight: 500;
}

/* Streamlit-header verbergen — vervangen door render_nav() */
[data-testid="stHeader"],
[data-testid="stHeader"] > *,
header[data-testid="stHeader"] { display: none !important; }

/* Sidebar volledig verbergen */
[data-testid="stSidebar"],
[data-testid="stSidebarNav"],
[data-testid="stSidebarCollapsedControl"],
section[data-testid="stSidebar"] { display: none !important; }

.block-container {
    padding-top: 72px !important;
    max-width: 900px;
    margin: 0 auto;
    padding-bottom: 80px !important;
}

h1 { font-size: 3.2rem; font-weight: 600; line-height: 1.15; }
p, li { color: #333; line-height: 1.6; }

[data-testid="stBaseButton-primary"],
[data-testid="stBaseButton-primary"] p,
[data-testid="stBaseButton-primary"] span {
    background-color: #1a1a1a !important;
    color: white !important;
    border-radius: 50px !important;
    font-weight: 700 !important;
    border: none !important;
    letter-spacing: 0.07em !important;
    font-size: 13px !important;
    white-space: nowrap !important;
}
[data-testid="stBaseButton-primary"]:hover { background-color: #333 !important; }

[data-testid="stBaseButton-secondary"],
[data-testid="stBaseButton-secondary"] p,
[data-testid="stBaseButton-secondary"] span {
    background-color: white !important;
    border-radius: 50px !important;
    border: none !important;
    box-shadow: 0 8px 24px rgba(0,0,0,0.20) !important;
    font-weight: 700 !important;
    letter-spacing: 0.05em !important;
    font-size: 13px !important;
    white-space: nowrap !important;
}
[data-testid="stBaseButton-secondary"]:hover {
    background-color: #e8c8c8 !important;
    box-shadow: 0 10px 28px rgba(0,0,0,0.25) !important;
}

[data-testid="stVerticalBlockBorderWrapper"] {
    background: white !important;
    border-radius: 20px !important;
    border: none !important;
    box-shadow: 0 4px 32px rgba(180,100,90,0.13);
    padding: 4px 8px;
}

[data-testid="stSelectbox"] > div > div {
    border-radius: 50px;
    border: 2px solid #1a1a1a;
    font-size: 13px;
    font-weight: 600;
    letter-spacing: 0.03em;
    background: white;
}

[data-testid="stBottom"]               { background-color: #ffffff !important; }
[data-testid="stBottomBlockContainer"] { background-color: #ffffff !important; }

[data-testid="stSlider"] [data-baseweb="slider"] [role="slider"] {
    background-color: #c8785a !important;
    border-color: #c8785a !important;
}
</style>
"""
