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

# Bestandspaden relatief aan app/main.py — vereist door st.page_link()
_NAV_STUDENT = [
    ("📚 Home", "main.py"),
    ("📊 Mijn voortgang", "pages/1_mijn_voortgang.py"),
    ("🎓 Leercoach", "pages/3_leercoach.py"),
    ("💚 Welzijn", "pages/5_welzijn.py"),
]

_NAV_DOCENT = [
    ("📚 Home", "main.py"),
    ("👥 Groepsoverzicht", "pages/2_groepsoverzicht.py"),
    ("📬 Outreach", "pages/4_outreach.py"),
    ("🎓 Leercoach", "pages/3_leercoach.py"),
]


def render_nav() -> None:
    """Render de navigatiebalk bovenaan de pagina via st.page_link().

    Gebruikt Streamlit's eigen client-side navigatie zodat session_state
    bewaard blijft bij het wisselen van pagina. HTML-ankers (<a href="...">)
    starten een volledige herlaad en wissen de sessie — vandaar st.page_link().

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

    n = len(nav_items)
    # kolommen: nav-items | spatie | gebruikersnaam | uitloggen
    cols = st.columns([2] * n + [3, 2, 2])

    for i, (label, page) in enumerate(nav_items):
        with cols[i]:
            st.page_link(page, label=label)

    with cols[n + 1]:
        st.markdown(
            f'<div style="text-align:right;color:#888;font-size:12px;font-weight:600;'
            f"padding-top:8px;font-family:'General Sans',sans-serif;\">👤 {gebruiker}</div>",
            unsafe_allow_html=True,
        )

    with cols[n + 2]:
        st.page_link("pages/uitloggen.py", label="Uitloggen")


def render_footer() -> None:
    """Render de huisstijl footer onderaan de pagina."""
    import streamlit as st

    st.markdown(FOOTER_HTML, unsafe_allow_html=True)


CSS = """
<style>
@import url('https://api.fontshare.com/v2/css?f[]=general-sans@400,500,600,700&display=swap');

[data-testid="stApp"] {
    background-color: #ffffff;
    font-family: 'General Sans', sans-serif;
    font-weight: 500;
}

/* Streamlit-header verbergen */
[data-testid="stHeader"],
[data-testid="stHeader"] > *,
header[data-testid="stHeader"] { display: none !important; }

/* Sidebar volledig verbergen */
[data-testid="stSidebar"],
[data-testid="stSidebarNav"],
[data-testid="stSidebarCollapsedControl"],
section[data-testid="stSidebar"] { display: none !important; }

/* ── Vaste navigatiebalk ────────────────────────────────────────────────── */
/* De eerste stHorizontalBlock is altijd onze nav (render_nav() staat bovenaan).
   position:fixed haalt hem uit de flow en plakt hem tegen de bovenkant. */
.block-container > div > [data-testid="stHorizontalBlock"]:first-of-type {
    position: fixed !important;
    top: 0 !important;
    left: 0 !important;
    right: 0 !important;
    height: 56px !important;
    background: #ffffff !important;
    z-index: 9999 !important;
    padding: 0 24px !important;
    margin: 0 !important;
    max-width: none !important;
    box-shadow: 0 1px 0 rgba(0,0,0,0.08) !important;
    align-items: center !important;
    gap: 8px !important;
}

/* Nav-kolommen: auto-breedte zodat labels niet worden afgekapt of omslaan */
.block-container > div > [data-testid="stHorizontalBlock"]:first-of-type
    [data-testid="stColumn"] {
    flex: 0 0 auto !important;
    min-width: fit-content !important;
    width: auto !important;
    overflow: visible !important;
}

/* Spatie-kolom (5e kolom) vult de resterende ruimte op */
.block-container > div > [data-testid="stHorizontalBlock"]:first-of-type
    [data-testid="stColumn"]:nth-child(5) {
    flex: 1 1 auto !important;
    min-width: 0 !important;
}

.block-container {
    padding-top: 72px !important;
    max-width: 900px;
    margin: 0 auto;
    padding-bottom: 80px !important;
}

h1 { font-size: 3.2rem; font-weight: 600; line-height: 1.15; }
p, li { color: #333; line-height: 1.6; }

/* ── Navigatie — st.page_link als pill ──────────────────────────────────── */
[data-testid="stPageLink"] {
    height: auto !important;
    padding: 0 !important;
    margin: 0 !important;
}

[data-testid="stPageLink"] a {
    display: inline-block !important;
    background: #ffffff !important;
    border-radius: 50px !important;
    padding: 7px 18px !important;
    font-size: 13px !important;
    font-weight: 700 !important;
    color: #1a1a1a !important;
    text-decoration: none !important;
    white-space: nowrap !important;
    box-shadow: 0 4px 16px rgba(0,0,0,0.13) !important;
    letter-spacing: 0.05em !important;
    font-family: 'General Sans', sans-serif !important;
    transition: background 0.15s !important;
}

[data-testid="stPageLink"] a:hover {
    background: #f0f0f0 !important;
    text-decoration: none !important;
}

/* ── Knoppen ────────────────────────────────────────────────────────────── */
[data-testid="stBaseButton-primary"],
[data-testid="stBaseButton-primary"] p,
[data-testid="stBaseButton-primary"] span {
    background-color: #1a1a1a !important;
    color: white !important;
    border-radius: 50px !important;
    font-weight: 700 !important;
    border: none !important;
    letter-spacing: 0.04em !important;
    font-size: 13px !important;
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
    letter-spacing: 0.03em !important;
    font-size: 13px !important;
}
[data-testid="stBaseButton-secondary"]:hover {
    background-color: #f5f5f5 !important;
    box-shadow: 0 10px 28px rgba(0,0,0,0.25) !important;
}

[data-testid="stVerticalBlockBorderWrapper"] {
    background: white !important;
    border-radius: 20px !important;
    border: none !important;
    box-shadow: 0 4px 32px rgba(0,0,0,0.09);
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

/* ── st.metric() opmaak ─────────────────────────────────────────────────── */
[data-testid="stMetric"] { background:white; border-radius:16px; padding:16px 20px; box-shadow:0 4px 24px rgba(0,0,0,0.08); }
[data-testid="stMetricLabel"] p { font-size:0.68rem!important; font-weight:700!important; letter-spacing:0.10em!important; text-transform:uppercase!important; color:#999!important; }
[data-testid="stMetricValue"] { font-size:2.2rem!important; font-weight:700!important; color:#1a1a1a!important; }
[data-testid="stMetricDelta"] svg { display:none; }
[data-testid="stMetricDelta"]>div { font-size:0.82rem!important; font-weight:700!important; }

/* ── Tabs ────────────────────────────────────────────────────────────────── */
[data-testid="stTabs"] [role="tablist"] { border-bottom:2px solid #f0d4d4; gap:4px; }
[data-testid="stTabs"] button[role="tab"] { font-family:'General Sans',sans-serif!important; font-weight:600!important; font-size:13px!important; color:#888!important; border-radius:8px 8px 0 0!important; padding:8px 16px!important; border:none!important; background:transparent!important; }
[data-testid="stTabs"] button[role="tab"][aria-selected="true"] { color:#1a1a1a!important; background:white!important; border-bottom:2px solid #c8785a!important; }

/* ── Expanders ───────────────────────────────────────────────────────────── */
[data-testid="stExpander"] { border:1px solid #f0d4d4!important; border-radius:12px!important; background:white!important; }
[data-testid="stExpander"] summary { font-family:'General Sans',sans-serif!important; font-weight:600!important; font-size:0.9rem!important; color:#1a1a1a!important; padding:12px 16px!important; }
[data-testid="stExpander"] summary:hover { background:#fae8e8!important; border-radius:12px 12px 0 0!important; }

/* ── .stat-card ──────────────────────────────────────────────────────────── */
.stat-card { background:white; border-radius:16px; padding:20px 20px 16px; box-shadow:0 4px 24px rgba(0,0,0,0.08); }
.stat-card__label { font-size:0.68rem; font-weight:700; letter-spacing:0.10em; text-transform:uppercase; color:#999; margin:0 0 6px; }
.stat-card__value { font-size:2.4rem; font-weight:700; color:#1a1a1a; line-height:1; margin:0; }
.stat-card__sub { font-size:0.82rem; color:#bbb; font-weight:500; margin:4px 0 0; }
.stat-card__delta--pos { color:#27ae60; font-weight:700; font-size:0.85rem; }
.stat-card__delta--neg { color:#c0392b; font-weight:700; font-size:0.85rem; }

/* ── .badge ──────────────────────────────────────────────────────────────── */
.badge { display:inline-block; border-radius:50px; padding:4px 14px; font-size:0.75rem; font-weight:700; letter-spacing:0.06em; text-transform:uppercase; white-space:nowrap; }
.badge--starter    { background:#e67e2220; color:#e67e22; }
.badge--onderweg   { background:#3498db20; color:#3498db; }
.badge--gevorderde { background:#27ae6020; color:#27ae60; }
.badge--expert     { background:#c8785a22; color:#c8785a; }
.badge--niet-gecontacteerd { background:#e74c3c18; color:#c0392b; }
.badge--gecontacteerd      { background:#f39c1218; color:#e67e22; }
.badge--gereageerd         { background:#3498db18; color:#2980b9; }
.badge--opgelost           { background:#27ae6018; color:#27ae60; }
.badge--urgentie-1 { background:#27ae6018; color:#27ae60; }
.badge--urgentie-2 { background:#f39c1218; color:#e67e22; }
.badge--urgentie-3 { background:#e74c3c18; color:#c0392b; }
.badge--transitie  { background:#c8785a18; color:#c8785a; }

/* ── .hero-card ──────────────────────────────────────────────────────────── */
.hero-card { background:white; border-radius:20px; padding:28px 28px 24px; box-shadow:0 4px 32px rgba(0,0,0,0.09); margin-bottom:4px; }
.hero-card__naam { font-size:1.9rem; font-weight:700; color:#1a1a1a; margin:0 0 4px; line-height:1.2; }
.hero-card__meta { color:#888; font-size:0.88rem; margin:0 0 4px; }
.hero-card__mentor { color:#bbb; font-size:0.80rem; margin:0 0 14px; }

/* ── .section-label ──────────────────────────────────────────────────────── */
.section-label { font-size:0.68rem; font-weight:700; letter-spacing:0.10em; color:#999; text-transform:uppercase; margin:0 0 8px; }
.section-label--warning { color:#e67e22; }

/* ── .welzijn-intro / .check-item ────────────────────────────────────────── */
.welzijn-intro { background:linear-gradient(135deg,#fae8e8 0%,#f0d4d4 100%); border-radius:16px; padding:24px 28px; margin-bottom:20px; border-left:4px solid #c8785a; }
.welzijn-intro__title { font-size:1.1rem; font-weight:700; color:#1a1a1a; margin:0 0 6px; }
.welzijn-intro__body { color:#555; font-size:0.9rem; line-height:1.5; margin:0; }
.check-item { display:flex; align-items:baseline; gap:10px; padding:10px 0; border-bottom:1px solid #f0d4d440; }
.check-item__date { color:#aaa; font-size:0.78rem; min-width:80px; font-weight:600; }
.check-item__label { font-size:0.85rem; color:#1a1a1a; font-weight:600; }
.check-item__note { color:#888; font-size:0.82rem; font-style:italic; }

/* ── Leercoach reset-knop uitlijning ─────────────────────────────────────── */
[data-testid="stColumn"]:has([data-testid="stBaseButton-secondary"]) { display:flex; align-items:flex-end; }

/* ── Grafiek-kaartjes ────────────────────────────────────────────────────── */
[data-testid="stArrowVegaLiteChart"],
[data-testid="stVegaLiteChart"] {
    background: white !important;
    border-radius: 16px !important;
    box-shadow: 0 4px 20px rgba(0,0,0,0.09) !important;
    padding: 12px !important;
}

/* Zorg dat alle element-containers en kolommen wit blijven */
[data-testid="stVerticalBlock"],
[data-testid="stHorizontalBlock"],
[data-testid="element-container"],
[data-testid="stColumn"] {
    background: white !important;
}
</style>
"""
