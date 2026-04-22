"""EduPulse huisstijl CSS en navigatie voor validatie-samenwijzer."""

DONKERBLAUW = "#1a237e"
WIT = "#ffffff"
GRIJS_BG = "#f5f5f5"
GROEN = "#43a047"
ORANJE = "#fb8c00"
ROOD = "#c62828"
GEEL_BRON = "#fffde7"
GEEL_RAND = "#f0c040"

CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

html, body, [class*="css"] {{
    font-family: 'Inter', sans-serif;
    background-color: {WIT};
    color: #1a1a1a;
}}

/* Sidebar verbergen */
[data-testid="stSidebar"], [data-testid="collapsedControl"] {{
    display: none !important;
}}

/* Topbalk-ruimte */
.block-container {{
    padding-top: 5rem !important;
    padding-bottom: 4rem !important;
    max-width: 960px;
}}

/* Navigatiebalk */
.nav-bar {{
    position: fixed;
    top: 0; left: 0; right: 0;
    background: {DONKERBLAUW};
    color: {WIT};
    padding: 0.6rem 1.5rem;
    display: flex;
    align-items: center;
    gap: 0.5rem;
    z-index: 1000;
    font-size: 0.85rem;
}}

.nav-bar a {{
    color: {WIT};
    text-decoration: none;
    padding: 0.3rem 0.7rem;
    border-radius: 4px;
    white-space: nowrap;
}}

.nav-bar a:hover {{ background: rgba(255,255,255,0.15); }}
.nav-bar .nav-user {{ margin-left: auto; opacity: 0.75; font-size: 0.78rem; }}

/* Voortgangsbalk */
.progress-bar-bg {{
    background: #e0e0e0; border-radius: 6px; height: 8px; margin: 4px 0;
}}
.progress-bar-fill {{
    border-radius: 6px; height: 8px;
    background: {GROEN};
}}

/* Bronkaartje */
.bron-kaartje {{
    background: {GEEL_BRON};
    border: 1px solid {GEEL_RAND};
    border-radius: 8px;
    padding: 0.7rem 1rem;
    font-size: 0.82rem;
    margin-bottom: 0.4rem;
}}

/* Chat-bubbles */
.chat-vraag {{
    background: #e8eaf6;
    border-radius: 12px 12px 12px 0;
    padding: 0.7rem 1rem;
    margin-bottom: 0.3rem;
    max-width: 80%;
    font-size: 0.88rem;
}}
.chat-antwoord {{
    background: #e8f5e9;
    border-radius: 12px 12px 0 12px;
    padding: 0.7rem 1rem;
    margin-bottom: 0.3rem;
    font-size: 0.88rem;
}}

/* Footer */
.footer {{
    position: fixed; bottom: 0; left: 0; right: 0;
    background: {WIT};
    border-top: 1px solid #e0e0e0;
    padding: 0.4rem 1.5rem;
    font-size: 0.68rem;
    color: #888;
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


def render_nav() -> None:
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
            f'<span style="color:white;font-size:0.78rem">{gebruiker} · {opleiding}</span>',
            unsafe_allow_html=True,
        )
    with cols[-1]:
        st.page_link("pages/uitloggen.py", label="🚪")


def render_footer() -> None:
    import streamlit as st

    st.markdown(
        '<div class="footer">Samenwijzer OER-assistent · CEDA 2026 · Npuls</div>',
        unsafe_allow_html=True,
    )
