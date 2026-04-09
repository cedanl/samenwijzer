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
    background-color: #fae8e8;
    padding: 10px 24px;
    text-align: center;
    font-family: 'General Sans', sans-serif;
    font-size: 12px;
    color: #333;
    line-height: 1.7;
    z-index: 999;
">
    <span style="display:inline-block;width:17px;height:17px;border:1.5px solid #333;border-radius:50%;font-size:8px;font-weight:700;line-height:16px;text-align:center;margin-right:2px;vertical-align:middle;">CC</span><span style="display:inline-block;width:17px;height:17px;border:1.5px solid #333;border-radius:50%;font-size:11px;line-height:16px;text-align:center;margin-right:6px;vertical-align:middle;">i</span>Op deze analytics tool is de Creative Commons ShareAlike Naamsvermelding 4.0-licentie van toepassing.<br>
    Maak bij gebruik van dit werk vermelding van de volgende referentie: AI en data waarde(n)vol inzetten: CEDA 2026 Uitnodigingsregel – EduPlan. Utrecht: Npuls
</div>
"""

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
[data-testid="stHeader"] { background-color: #fae8e8 !important; }
[data-testid="stSidebarCollapsedControl"] { display: none; }

.block-container {
    padding-top: 4rem !important;
    max-width: 900px;
    margin: 0 auto;
    padding-bottom: 2rem;
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
}
[data-testid="stBaseButton-primary"]:hover { background-color: #333 !important; }

[data-testid="stBaseButton-secondary"] {
    background-color: white !important;
    border-radius: 50px !important;
    border: none !important;
    box-shadow: 0 8px 24px rgba(0,0,0,0.20) !important;
    font-weight: 700 !important;
    letter-spacing: 0.05em !important;
    font-size: 13px !important;
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

[data-testid="stBottom"]               { background-color: #fae8e8 !important; }
[data-testid="stBottomBlockContainer"] { background-color: #fae8e8 !important; }

/* Ruimte voor vaste footer */
.block-container { padding-bottom: 80px !important; }

[data-testid="stSlider"] [data-baseweb="slider"] [role="slider"] {
    background-color: #c8785a !important;
    border-color: #c8785a !important;
}
</style>
"""
