"""Samenwijzer huisstijl — dual-theme tokens, CSS-injectie en componentbibliotheek.

Twee thema's bovenop één gedeeld fundament:

* **student** — donker (#0F0F12) met lime-accent (#A8FF60), mobile-first, energiek.
* **docent**  — paper (#F0EBE1) met sage-accent (#6F8265), desktop, atelier-rustig.

Pagina's roepen :func:`inject_theme` aan met de huidige rol; de helpers
(:func:`hero`, :func:`stat_card`, :func:`badge`, :func:`alert`,
:func:`section_label`, :func:`action_tile`) renderen consistent in beide thema's.
"""

from __future__ import annotations

import streamlit as st

# ── Kleur-constanten (behouden voor backwards-compat met visualize/etc.) ──────
TERRACOTTA = "#c8785a"
ROZE_BG = "#f0d4d4"
ROZE_LICHT = "#fae8e8"
ZWART = "#1a1a1a"
ROOD = "#c0392b"
ORANJE = "#e67e22"
GROEN = "#27ae60"

# Nieuwe thema-accenten (voor gebruik in Altair/Plotly grafieken).
STUDENT_ACCENT = "#A8FF60"
STUDENT_ALERT = "#FF5E3A"
STUDENT_BG = "#0F0F12"
STUDENT_SURFACE = "#1A1A1F"
DOCENT_ACCENT = "#6F8265"
DOCENT_ALERT = "#B04A1A"
DOCENT_BG = "#F0EBE1"
DOCENT_SURFACE = "#FAF5EC"
DOCENT_INK = "#1F1D18"


# ── BASE CSS — fonts, reset, layout, en alle component-classes via tokens ─────
_BASE_CSS = """
@import url('https://api.fontshare.com/v2/css?f[]=satoshi@400,500,700,900&f[]=cabinet-grotesk@500,700,800&display=swap');
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&display=swap');

:root {
    --space-1: 4px;  --space-2: 8px;  --space-3: 12px;
    --space-4: 16px; --space-5: 24px; --space-6: 32px; --space-7: 48px;
    --font-display: 'Cabinet Grotesk', -apple-system, BlinkMacSystemFont, sans-serif;
    --font-body:    'Satoshi', -apple-system, BlinkMacSystemFont, sans-serif;
    --font-mono:    'JetBrains Mono', ui-monospace, SFMono-Regular, monospace;
    --ease: cubic-bezier(0.4, 0, 0.2, 1);
    --dur-fast: 150ms;
    --dur-base: 240ms;
}

/* Streamlit-chrome verbergen */
[data-testid="stHeader"],
[data-testid="stHeader"] > *,
header[data-testid="stHeader"] { display: none !important; }
[data-testid="stSidebar"],
[data-testid="stSidebarNav"],
[data-testid="stSidebarCollapsedControl"],
section[data-testid="stSidebar"] { display: none !important; }

[data-testid="stApp"] {
    background-color: var(--bg);
    color: var(--text);
    font-family: var(--font-body);
    font-weight: 500;
}

.block-container {
    padding-top: 68px !important;
    padding-bottom: 100px !important;
    max-width: 1100px;
    margin: 0 auto;
}

/* ── Typografie ───────────────────────────────────────────────────────────── */
h1, h2, h3, h4 {
    font-family: var(--font-display);
    font-weight: 800;
    letter-spacing: -0.025em;
    color: var(--text);
    margin: 0 0 var(--space-2);
}
h1 { font-size: 2.2rem; line-height: 1.1; }
h2 { font-size: 1.5rem; line-height: 1.15; }
h3 { font-size: 1.15rem; }
p, li { color: var(--text); line-height: 1.55; }

/* ── Vaste navigatiebalk ──────────────────────────────────────────────────── */
[data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"] [data-testid="stPageLink"]) {
    position: fixed !important;
    top: 0 !important; left: 0 !important; right: 0 !important;
    height: 52px !important;
    background: var(--nav-bg) !important;
    z-index: 9999 !important;
    padding: 0 24px !important;
    margin: 0 !important;
    max-width: none !important;
    box-shadow: none !important;
    align-items: center !important;
    gap: 18px !important;
}
[data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"] [data-testid="stPageLink"])
    [data-testid="stColumn"],
[data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"] [data-testid="stPageLink"])
    [data-testid="stVerticalBlock"],
[data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"] [data-testid="stPageLink"])
    [data-testid="element-container"] {
    flex: 0 0 auto !important;
    min-width: max-content !important;
    width: max-content !important;
    overflow: visible !important;
    background: transparent !important;
}
[data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"] [data-testid="stPageLink"])
    [data-testid="stColumn"]:nth-child(6) {
    flex: 1 1 auto !important;
    min-width: 0 !important;
    width: auto !important;
}

/* Nav-links in vaste header */
[data-testid="stPageLink"] { height: auto !important; padding: 0 !important; margin: 0 !important; }
[data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"] [data-testid="stPageLink"])
    [data-testid="stPageLink"] a {
    display: inline-block !important;
    background: transparent !important;
    border-radius: 6px !important;
    padding: 6px 12px !important;
    font-family: var(--font-body) !important;
    font-size: 12.5px !important;
    font-weight: 600 !important;
    color: var(--nav-link) !important;
    text-decoration: none !important;
    white-space: nowrap !important;
    letter-spacing: 0.02em !important;
    transition: background var(--dur-fast) var(--ease), color var(--dur-fast) var(--ease) !important;
}
[data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"] [data-testid="stPageLink"])
    [data-testid="stPageLink"] a:hover {
    background: var(--nav-link-hover-bg) !important;
    color: var(--nav-link-hover) !important;
}
[data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"] [data-testid="stPageLink"])
    [data-testid="stPageLink"] a div,
[data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"] [data-testid="stPageLink"])
    [data-testid="stPageLink"] a p,
[data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"] [data-testid="stPageLink"])
    [data-testid="stPageLink"] a span {
    overflow: visible !important; text-overflow: unset !important; white-space: nowrap !important;
    max-width: none !important; width: auto !important; color: inherit !important;
}
/* Elders op de pagina: page_link in body */
[data-testid="stPageLink"] a {
    display: inline-block !important;
    background: transparent !important; border-radius: 6px !important;
    padding: 4px 10px !important;
    font-family: var(--font-body) !important;
    font-size: 12.5px !important; font-weight: 600 !important;
    color: var(--text) !important; text-decoration: none !important;
    white-space: nowrap !important;
}
[data-testid="stPageLink"] a:hover { background: var(--surface-2) !important; }

/* ── Knoppen (primary / secondary, ook binnen st.form) ────────────────────── */
[data-testid="stBaseButton-primary"],
[data-testid="stBaseButton-primaryFormSubmit"],
[data-testid="stBaseButton-primary"] p,
[data-testid="stBaseButton-primary"] span,
[data-testid="stBaseButton-primaryFormSubmit"] p,
[data-testid="stBaseButton-primaryFormSubmit"] span {
    background-color: var(--btn-prim-bg) !important;
    color: var(--btn-prim-fg) !important;
    border: none !important;
    border-radius: var(--btn-radius) !important;
    font-family: var(--font-body) !important;
    font-weight: 700 !important;
    font-size: 13px !important;
    letter-spacing: 0.03em !important;
    transition: background var(--dur-fast) var(--ease), transform var(--dur-fast) var(--ease) !important;
}
[data-testid="stBaseButton-primary"]:hover,
[data-testid="stBaseButton-primaryFormSubmit"]:hover {
    background-color: var(--btn-prim-bg-hover) !important;
    transform: translateY(-1px);
}
[data-testid="stBaseButton-secondary"],
[data-testid="stBaseButton-secondaryFormSubmit"],
[data-testid="stBaseButton-secondary"] p,
[data-testid="stBaseButton-secondary"] span,
[data-testid="stBaseButton-secondaryFormSubmit"] p,
[data-testid="stBaseButton-secondaryFormSubmit"] span {
    background-color: var(--btn-sec-bg) !important;
    color: var(--btn-sec-fg) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--btn-radius) !important;
    font-family: var(--font-body) !important;
    font-weight: 700 !important;
    font-size: 13px !important;
    letter-spacing: 0.03em !important;
    box-shadow: none !important;
}
[data-testid="stBaseButton-secondary"]:hover,
[data-testid="stBaseButton-secondaryFormSubmit"]:hover {
    background-color: var(--surface-2) !important;
}

/* ── Container-border (st.container(border=True)) ─────────────────────────── */
[data-testid="stVerticalBlockBorderWrapper"] {
    background: var(--surface) !important;
    border-radius: var(--radius-md) !important;
    border: 1px solid var(--border) !important;
    box-shadow: var(--shadow);
    padding: var(--space-2) var(--space-3);
}

/* ── Inputs (selectbox, text input, text area, slider) ────────────────────── */
[data-testid="stSelectbox"] > div > div,
[data-testid="stTextInput"] input,
[data-testid="stTextArea"] textarea,
[data-testid="stNumberInput"] input,
[data-testid="stDateInput"] input {
    background: var(--surface) !important;
    color: var(--text) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--radius-sm) !important;
    font-family: var(--font-body) !important;
    font-size: 14px !important;
}
[data-testid="stTextInput"] input::placeholder,
[data-testid="stTextArea"] textarea::placeholder {
    color: var(--text-faint) !important;
}
[data-testid="stSlider"] [data-baseweb="slider"] [role="slider"] {
    background-color: var(--accent) !important;
    border-color: var(--accent) !important;
}

[data-testid="stBottom"] { background-color: var(--bg) !important; }
[data-testid="stBottomBlockContainer"] { background-color: var(--bg) !important; }

/* ── st.metric — gebruikt door legacy code; matchen we aan stat-card stijl ── */
[data-testid="stMetric"] {
    background: var(--surface);
    border-radius: var(--radius-md);
    border: 1px solid var(--border);
    padding: 16px 20px;
    box-shadow: var(--shadow);
}
[data-testid="stMetricLabel"] p {
    font-family: var(--font-mono) !important;
    font-size: 11px !important;
    font-weight: 500 !important;
    letter-spacing: 0.10em !important;
    text-transform: uppercase !important;
    color: var(--text-faint) !important;
}
[data-testid="stMetricValue"] {
    font-family: var(--font-display) !important;
    font-size: 2rem !important;
    font-weight: 800 !important;
    letter-spacing: -0.025em !important;
    color: var(--text) !important;
}
[data-testid="stMetricDelta"] svg { display: none; }
[data-testid="stMetricDelta"] > div {
    font-family: var(--font-mono) !important;
    font-size: 11px !important;
    font-weight: 500 !important;
}

/* ── Tabs ──────────────────────────────────────────────────────────────────── */
[data-testid="stTabs"] [role="tablist"] {
    border-bottom: 1px solid var(--border);
    gap: 4px;
}
[data-testid="stTabs"] button[role="tab"] {
    font-family: var(--font-body) !important;
    font-weight: 600 !important;
    font-size: 13px !important;
    color: var(--text-dim) !important;
    background: transparent !important;
    border: none !important;
    border-bottom: 2px solid transparent !important;
    border-radius: 0 !important;
    padding: 10px 16px !important;
    margin-bottom: -1px !important;
}
[data-testid="stTabs"] button[role="tab"][aria-selected="true"] {
    color: var(--accent-strong) !important;
    border-bottom-color: var(--accent) !important;
    background: transparent !important;
}

/* ── Expanders ────────────────────────────────────────────────────────────── */
[data-testid="stExpander"] {
    border: 1px solid var(--border) !important;
    border-radius: var(--radius-md) !important;
    background: var(--surface) !important;
}
[data-testid="stExpander"] summary {
    font-family: var(--font-body) !important;
    font-weight: 600 !important;
    font-size: 14px !important;
    color: var(--text) !important;
    padding: 12px 16px !important;
}
[data-testid="stExpander"] summary:hover { background: var(--surface-2) !important; }
[data-testid="stExpander"] summary [data-testid="stIconMaterial"] {
    color: var(--text-faint) !important;
}
[data-testid="stExpanderDetails"] {
    padding: var(--space-2) var(--space-4) var(--space-4) !important;
    border-top: 1px solid var(--border) !important;
}

/* ── Info/Warning/Error/Success banners ───────────────────────────────────── */
[data-testid="stAlertContainer"] {
    border-radius: var(--radius-md) !important;
    border: 1px solid var(--border) !important;
}

/* ── Altair/Plotly chart containers ───────────────────────────────────────── */
[data-testid="stArrowVegaLiteChart"],
[data-testid="stVegaLiteChart"],
[data-testid="stPlotlyChart"] {
    background: var(--surface) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--radius-md) !important;
    box-shadow: var(--shadow) !important;
    padding: 12px !important;
}

[data-testid="stVerticalBlock"],
[data-testid="stHorizontalBlock"],
[data-testid="element-container"],
[data-testid="stColumn"] { background: transparent; }

/* ─────────────────────────────────────────────────────────────────────────── */
/* Componenten — alles met sw- prefix om Streamlit-classes niet te raken      */
/* ─────────────────────────────────────────────────────────────────────────── */

/* ── sw-hero ───────────────────────────────────────────────────────────────── */
.sw-hero {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
    padding: var(--space-4) var(--space-5);
    margin: 0 0 var(--space-4);
    box-shadow: var(--shadow);
}
.sw-hero__name {
    font-family: var(--font-display) !important;
    font-weight: 800 !important;
    font-size: 1.9rem !important;
    letter-spacing: -0.03em !important;
    line-height: 1.05 !important;
    color: var(--text) !important;
    margin: 0 0 4px !important;
}
.sw-hero__name em {
    font-style: normal;
    color: var(--accent-strong);
}
.sw-hero__meta {
    font-family: var(--font-mono);
    font-size: 11px;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--text-faint);
    margin: 0 0 var(--space-3);
}
.sw-hero__badges { display: flex; flex-wrap: wrap; gap: 6px; }

/* ── sw-stat ──────────────────────────────────────────────────────────────── */
.sw-stat {
    display: flex; align-items: center; gap: var(--space-3);
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
    padding: var(--space-3) var(--space-4);
    box-shadow: var(--shadow);
    min-height: 88px;
}
.sw-stat__ring { width: 52px; height: 52px; flex-shrink: 0; }
.sw-stat__ring-bg { stroke: var(--ring-bg); stroke-width: 5; fill: none; }
.sw-stat__ring-fg { stroke: var(--accent); stroke-width: 5; fill: none; }
.sw-stat__ring-fg.alert { stroke: var(--alert); }
.sw-stat__body { flex: 1; min-width: 0; }
.sw-stat__label {
    font-family: var(--font-mono);
    font-size: 10.5px;
    letter-spacing: 0.10em;
    text-transform: uppercase;
    color: var(--text-faint);
    margin: 0 0 4px;
}
.sw-stat__value {
    font-family: var(--font-display) !important;
    font-weight: 800 !important;
    font-size: 1.9rem !important;
    letter-spacing: -0.025em !important;
    line-height: 1 !important;
    color: var(--text) !important;
    margin: 0 !important;
}
.sw-stat__value-sub {
    font-family: var(--font-display);
    font-size: 0.95rem;
    color: var(--text-dim);
    font-weight: 600;
}
.sw-stat__delta {
    font-family: var(--font-mono);
    font-size: 11px;
    margin: 4px 0 0;
    color: var(--accent-strong);
}
.sw-stat__delta.neg { color: var(--alert); }
.sw-stat__sub {
    font-family: var(--font-mono);
    font-size: 10.5px;
    color: var(--text-faint);
    margin: 2px 0 0;
    letter-spacing: 0.06em;
}

/* ── sw-badge ─────────────────────────────────────────────────────────────── */
.sw-badge {
    display: inline-block;
    padding: 4px 12px;
    border-radius: var(--badge-radius);
    font-family: var(--font-mono);
    font-size: 10.5px;
    font-weight: 500;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    white-space: nowrap;
    background: var(--surface-2);
    color: var(--text-dim);
    border: 1px solid var(--border);
}
.sw-badge--starter    { background: var(--badge-starter-bg);    color: var(--badge-starter-fg);    border-color: var(--badge-starter-border); }
.sw-badge--onderweg   { background: var(--badge-onderweg-bg);   color: var(--badge-onderweg-fg);   border-color: var(--badge-onderweg-border); }
.sw-badge--gevorderde { background: var(--badge-gev-bg);        color: var(--badge-gev-fg);        border-color: var(--badge-gev-border); }
.sw-badge--expert     { background: var(--badge-exp-bg);        color: var(--badge-exp-fg);        border-color: var(--badge-exp-border); }
.sw-badge--onschema   { background: var(--badge-ok-bg);         color: var(--badge-ok-fg);         border-color: var(--badge-ok-border); }
.sw-badge--urgent     { background: var(--badge-urg-bg);        color: var(--badge-urg-fg);        border-color: var(--badge-urg-border); }
.sw-badge--accent     { background: var(--accent); color: var(--bg); font-weight: 700; border-color: var(--accent); }

/* Outreach-statussen */
.sw-badge--niet-gecontacteerd { background: var(--badge-urg-bg); color: var(--badge-urg-fg); border-color: var(--badge-urg-border); }
.sw-badge--gecontacteerd      { background: var(--badge-starter-bg); color: var(--badge-starter-fg); border-color: var(--badge-starter-border); }
.sw-badge--gereageerd         { background: var(--badge-onderweg-bg); color: var(--badge-onderweg-fg); border-color: var(--badge-onderweg-border); }
.sw-badge--opgelost           { background: var(--badge-ok-bg); color: var(--badge-ok-fg); border-color: var(--badge-ok-border); }
.sw-badge--transitie          { background: var(--badge-exp-bg); color: var(--badge-exp-fg); border-color: var(--badge-exp-border); }

/* Welzijn-urgentie */
.sw-badge--urgentie-1 { background: var(--badge-ok-bg); color: var(--badge-ok-fg); border-color: var(--badge-ok-border); }
.sw-badge--urgentie-2 { background: var(--badge-starter-bg); color: var(--badge-starter-fg); border-color: var(--badge-starter-border); }
.sw-badge--urgentie-3 { background: var(--badge-urg-bg); color: var(--badge-urg-fg); border-color: var(--badge-urg-border); }

/* ── sw-alert ─────────────────────────────────────────────────────────────── */
.sw-alert {
    display: flex; align-items: center; gap: var(--space-3);
    padding: var(--space-3) var(--space-4);
    border-radius: var(--radius-md);
    margin: var(--space-3) 0;
    font-family: var(--font-body);
    font-size: 14px;
    font-weight: 600;
}
.sw-alert--info     { background: var(--surface-2); color: var(--text-dim); border: 1px solid var(--border); }
.sw-alert--warning  { background: var(--badge-starter-bg); color: var(--badge-starter-fg); border: 1px solid var(--badge-starter-border); }
.sw-alert--urgent   { background: var(--badge-urg-bg); color: var(--badge-urg-fg); border: 1px solid var(--badge-urg-border); }
.sw-alert__icon {
    width: 28px; height: 28px; flex-shrink: 0;
    border-radius: var(--radius-sm);
    background: currentColor; opacity: 0.85;
    display: flex; align-items: center; justify-content: center;
    color: var(--bg); font-weight: 800; font-size: 13px;
}

/* ── sw-label / sw-section-label ──────────────────────────────────────────── */
.sw-label {
    font-family: var(--font-mono);
    font-size: 10.5px;
    font-weight: 500;
    letter-spacing: 0.10em;
    text-transform: uppercase;
    color: var(--text-faint);
    margin: 0 0 var(--space-2);
}
.sw-label--warning { color: var(--alert); }

/* ── sw-tile (action tile op home) ────────────────────────────────────────── */
.sw-tile {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
    padding: var(--space-4);
    box-shadow: var(--shadow);
}
.sw-tile__icon {
    font-family: var(--font-mono);
    font-size: 10.5px;
    letter-spacing: 0.10em;
    text-transform: uppercase;
    color: var(--text-faint);
    margin: 0 0 6px;
}
.sw-tile__title {
    font-family: var(--font-display) !important;
    font-weight: 700 !important;
    font-size: 1.1rem !important;
    letter-spacing: -0.015em !important;
    line-height: 1.2 !important;
    color: var(--text) !important;
    margin: 0 0 4px !important;
}
.sw-tile__sub {
    font-family: var(--font-body);
    font-weight: 500;
    font-size: 12.5px;
    color: var(--text-dim);
    line-height: 1.4;
    margin: 0 0 var(--space-3);
}

/* ── sw-rule (subtiele scheidingslijn) ────────────────────────────────────── */
.sw-rule { height: 1px; background: var(--border); margin: var(--space-5) 0; border: none; }

/* ── Responsive ──────────────────────────────────────────────────────────── */
@media (max-width: 768px) {
    .block-container { padding-top: 62px !important; padding-left: 14px !important; padding-right: 14px !important; }
    h1 { font-size: 1.8rem; }
    .sw-hero__name { font-size: 1.6rem; }
    .sw-stat__value { font-size: 1.6rem; }
}
"""


# ── STUDENT theme — donker + lime ─────────────────────────────────────────────
_STUDENT_CSS = """
:root {
    --bg: #0F0F12;
    --surface: #1A1A1F;
    --surface-2: rgba(255,255,255,0.04);
    --border: rgba(255,255,255,0.08);
    --text: #FFFFFF;
    --text-dim: rgba(255,255,255,0.85);
    --text-faint: rgba(255,255,255,0.68);
    --accent: #A8FF60;
    --accent-strong: #A8FF60;
    --alert: #FF5E3A;
    --shadow: 0 4px 24px rgba(0,0,0,0.40);
    --radius-sm: 8px;
    --radius-md: 14px;
    --radius-lg: 22px;
    --badge-radius: 50px;
    --btn-radius: 50px;
    --ring-bg: rgba(255,255,255,0.10);

    /* nav */
    --nav-bg: #1A1A1F;
    --nav-link: rgba(255,255,255,0.78);
    --nav-link-hover-bg: rgba(168,255,96,0.18);
    --nav-link-hover: #A8FF60;

    /* buttons */
    --btn-prim-bg: #A8FF60;
    --btn-prim-fg: #0F0F12;
    --btn-prim-bg-hover: #BFFF7F;
    --btn-sec-bg: rgba(255,255,255,0.06);
    --btn-sec-fg: #FFFFFF;

    /* badges */
    --badge-starter-bg: rgba(255,94,58,0.15); --badge-starter-fg: #FF8E6E; --badge-starter-border: rgba(255,94,58,0.30);
    --badge-onderweg-bg: rgba(96,165,255,0.15); --badge-onderweg-fg: #84B8FF; --badge-onderweg-border: rgba(96,165,255,0.30);
    --badge-gev-bg: rgba(168,255,96,0.18); --badge-gev-fg: #A8FF60; --badge-gev-border: rgba(168,255,96,0.35);
    --badge-exp-bg: rgba(255,255,255,0.10); --badge-exp-fg: #FFFFFF; --badge-exp-border: rgba(255,255,255,0.30);
    --badge-ok-bg: rgba(168,255,96,0.15); --badge-ok-fg: #A8FF60; --badge-ok-border: rgba(168,255,96,0.30);
    --badge-urg-bg: rgba(255,94,58,0.15); --badge-urg-fg: #FF5E3A; --badge-urg-border: rgba(255,94,58,0.30);
}
/* Student-specific tweaks */
.sw-hero { background: linear-gradient(180deg, rgba(168,255,96,0.04), rgba(168,255,96,0.0)); border-color: rgba(168,255,96,0.18); }
.sw-stat { background: rgba(255,255,255,0.03); }
"""


# ── DOCENT theme — paper + sage ───────────────────────────────────────────────
_DOCENT_CSS = """
:root {
    --bg: #F0EBE1;
    --surface: #FAF5EC;
    --surface-2: #F5EFE1;
    --border: rgba(31,29,24,0.10);
    --text: #1F1D18;
    --text-dim: #5D5749;
    --text-faint: #6E6856;
    --accent: #6F8265;
    --accent-strong: #4D6044;
    --alert: #B04A1A;
    --shadow: 0 2px 12px rgba(31,29,24,0.06);
    --radius-sm: 6px;
    --radius-md: 12px;
    --radius-lg: 18px;
    --badge-radius: 6px;
    --btn-radius: 8px;
    --ring-bg: rgba(31,29,24,0.10);

    /* nav */
    --nav-bg: #1F1D18;
    --nav-link: rgba(250,245,236,0.55);
    --nav-link-hover-bg: rgba(111,130,101,0.30);
    --nav-link-hover: #D9E0D3;

    /* buttons */
    --btn-prim-bg: #1F1D18;
    --btn-prim-fg: #FAF5EC;
    --btn-prim-bg-hover: #2F2A20;
    --btn-sec-bg: #FAF5EC;
    --btn-sec-fg: #1F1D18;

    /* badges */
    --badge-starter-bg: #F5E0D3; --badge-starter-fg: #B04A1A; --badge-starter-border: #E8C9B3;
    --badge-onderweg-bg: #E6EBE2; --badge-onderweg-fg: #4D6044; --badge-onderweg-border: #D0D9C8;
    --badge-gev-bg: #DDE6D6; --badge-gev-fg: #3E5237; --badge-gev-border: #C5D4BA;
    --badge-exp-bg: #1F1D18; --badge-exp-fg: #FAF5EC; --badge-exp-border: #1F1D18;
    --badge-ok-bg: #DDE6D6; --badge-ok-fg: #3E5237; --badge-ok-border: #C5D4BA;
    --badge-urg-bg: #F5DCD0; --badge-urg-fg: #B04A1A; --badge-urg-border: #ECC3AC;
}
"""


def inject_theme(rol: str | None = None) -> None:
    """Injecteer base-CSS + thema-CSS in de pagina.

    Aanroepen direct ná ``st.set_page_config(...)``. Bij ontbrekende rol (login)
    valt de docent-stijl in als veilige default — paper-achtergrond werkt voor
    beide.

    Args:
        rol: ``"student"``, ``"docent"`` of ``None``.
    """
    theme = _STUDENT_CSS if rol == "student" else _DOCENT_CSS
    st.markdown(f"<style>{_BASE_CSS}{theme}</style>", unsafe_allow_html=True)


# Backwards-compat: CSS = docent-thema-bundle. Bestaande aanroepen blijven werken
# tot pagina's gemigreerd zijn naar inject_theme().
CSS = f"<style>{_BASE_CSS}{_DOCENT_CSS}</style>"


# ── Navigatie ─────────────────────────────────────────────────────────────────
_NAV_STUDENT = [
    ("Home", "main.py"),
    ("Voortgang", "pages/1_mijn_voortgang.py"),
    ("Groeidossier", "pages/6_groeidossier.py"),
    ("Leercoach", "pages/3_leercoach.py"),
    ("Welzijn", "pages/5_welzijn.py"),
]

_NAV_DOCENT = [
    ("Home", "main.py"),
    ("Groep", "pages/2_groepsoverzicht.py"),
    ("Groeidossier", "pages/6_groeidossier.py"),
    ("Outreach", "pages/4_outreach.py"),
    ("Leercoach", "pages/3_leercoach.py"),
]


def render_nav() -> None:
    """Render de bovenbalk via ``st.page_link``.

    Gebruikt Streamlit's client-side navigatie (HTML <a> zou een full reload
    triggeren en de sessie wissen). Aanroepen direct ná :func:`inject_theme`.
    """
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
    cols = st.columns([2] * n + [3, 2, 2])

    for i, (label, page) in enumerate(nav_items):
        with cols[i]:
            st.page_link(page, label=label)

    with cols[n + 1]:
        st.markdown(
            f'<div style="text-align:right;color:rgba(255,255,255,0.45);'
            f"font-size:11px;font-weight:600;padding-top:6px;"
            f"font-family:'JetBrains Mono',monospace;letter-spacing:0.08em;"
            f'text-transform:uppercase;">{gebruiker}</div>',
            unsafe_allow_html=True,
        )

    with cols[n + 2]:
        st.page_link("pages/uitloggen.py", label="Uitloggen")


# ── Footer ────────────────────────────────────────────────────────────────────
_FOOTER_HTML = """
<div style="
    position: fixed; bottom: 0; left: 0; right: 0;
    background-color: var(--bg);
    border-top: 1px solid var(--border);
    padding: 8px 24px; text-align: center;
    font-family: 'JetBrains Mono', monospace;
    font-size: 10px; color: var(--text-faint); line-height: 1.5; z-index: 999;">
    <img src="https://mirrors.creativecommons.org/presskit/icons/cc.svg" alt=""
         style="height:1.1em;vertical-align:middle;opacity:0.5;">
    <img src="https://mirrors.creativecommons.org/presskit/icons/by.svg" alt=""
         style="height:1.1em;vertical-align:middle;opacity:0.5;margin-right:6px;">
    CC BY-SA 4.0 · AI en data waarde(n)vol inzetten · CEDA 2026 Samenwijzer · Utrecht: Npuls
</div>
"""


def render_footer() -> None:
    """Render de CEDA/Npuls-credit onderaan de pagina."""
    st.markdown(_FOOTER_HTML, unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# Component-helpers — alle gebruik sw- prefix, alle thema-bewust via CSS-vars
# ─────────────────────────────────────────────────────────────────────────────


def _esc(text: str) -> str:
    """Minimale HTML-escape voor user-content in markdown blocks."""
    return (
        text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    )


def hero(
    naam: str,
    meta: str,
    badges: list[tuple[str, str]] | None = None,
    *,
    accent_naam: bool = False,
) -> None:
    """Render een hero-blok bovenaan een pagina.

    Args:
        naam: Naam of begroeting. Bij ``accent_naam=True`` wordt de tekst in de
            accent-kleur getoond (handig voor "Hey, **Lisa**" op student-home).
        meta: Sub-regel (cohort, opleiding, datum, etc.). Wordt mono-uppercase.
        badges: Optionele lijst van ``(kind, label)``-tuples — zie :func:`badge`
            voor toegestane kinds.
    """
    naam_html = f"<em>{_esc(naam)}</em>" if accent_naam else _esc(naam)
    badges_html = ""
    if badges:
        badges_html = (
            '<div class="sw-hero__badges">' + "".join(badge(k, t) for k, t in badges) + "</div>"
        )
    st.markdown(
        f'<div class="sw-hero">'
        f'<p class="sw-hero__name">{naam_html}</p>'
        f'<p class="sw-hero__meta">{_esc(meta)}</p>'
        f"{badges_html}"
        f"</div>",
        unsafe_allow_html=True,
    )


def stat_card(
    label: str,
    value: str,
    *,
    value_sub: str | None = None,
    delta: str | None = None,
    delta_negative: bool = False,
    sub: str | None = None,
    progress: float | None = None,
    alert_ring: bool = False,
) -> None:
    """Render een stat-kaart met optionele inline progress-ring.

    Args:
        label: Korte mono-label (bv. "Studievoortgang").
        value: Grote waarde (bv. ``"62%"`` of ``"42"``).
        value_sub: Subtiele suffix achter ``value`` (bv. ``"/ 60"``).
        delta: Klein delta-regeltje onder de waarde (bv. ``"+8% vs. cohort"``).
        delta_negative: Kleur het delta-regeltje in alert-kleur.
        sub: Extra mono-regel onderaan (bv. cohortnaam).
        progress: ``0.0``–``1.0`` voor de inline-ring; ``None`` = geen ring.
        alert_ring: Toon de ring in ``--alert`` ipv ``--accent``.
    """
    ring_html = ""
    if progress is not None:
        pct = max(0.0, min(1.0, progress))
        # circumference = 2*pi*r met r=20 ≈ 125.66
        offset = round(125.66 * (1 - pct), 1)
        ring_cls = "sw-stat__ring-fg alert" if alert_ring else "sw-stat__ring-fg"
        ring_html = (
            '<svg class="sw-stat__ring" viewBox="0 0 50 50">'
            '<circle cx="25" cy="25" r="20" class="sw-stat__ring-bg" />'
            f'<circle cx="25" cy="25" r="20" class="{ring_cls}" '
            f'stroke-dasharray="125.66" stroke-dashoffset="{offset}" '
            'stroke-linecap="round" transform="rotate(-90 25 25)" />'
            "</svg>"
        )
    value_sub_html = (
        f'<span class="sw-stat__value-sub">{_esc(value_sub)}</span>' if value_sub else ""
    )
    delta_cls = "sw-stat__delta neg" if delta_negative else "sw-stat__delta"
    delta_html = f'<p class="{delta_cls}">{_esc(delta)}</p>' if delta else ""
    sub_html = f'<p class="sw-stat__sub">{_esc(sub)}</p>' if sub else ""
    st.markdown(
        f'<div class="sw-stat">{ring_html}'
        f'<div class="sw-stat__body">'
        f'<p class="sw-stat__label">{_esc(label)}</p>'
        f'<p class="sw-stat__value">{_esc(value)}{value_sub_html}</p>'
        f"{delta_html}{sub_html}"
        f"</div></div>",
        unsafe_allow_html=True,
    )


def badge(kind: str, text: str) -> str:
    """Geef een badge als HTML-string voor inline gebruik.

    Toegestane ``kind``-waarden: ``starter``, ``onderweg``, ``gevorderde``,
    ``expert``, ``onschema``, ``urgent``, ``accent``, en de outreach-/welzijn-
    specifieke vormen ``niet-gecontacteerd``, ``gecontacteerd``, ``gereageerd``,
    ``opgelost``, ``transitie``, ``urgentie-1``, ``urgentie-2``, ``urgentie-3``.
    """
    return f'<span class="sw-badge sw-badge--{kind}">{_esc(text)}</span>'


def render_badge(kind: str, text: str) -> None:
    """Render een badge direct (wrapper rond :func:`badge`)."""
    st.markdown(badge(kind, text), unsafe_allow_html=True)


def alert(text: str, level: str = "info", *, icon: str | None = None) -> None:
    """Render een inline alert-balk.

    Args:
        text: Tekst in de balk.
        level: ``"info"``, ``"warning"`` of ``"urgent"``.
        icon: Optioneel één teken voor het ronde icoon vóór de tekst (bv. ``"!"``).
    """
    icon_html = f'<span class="sw-alert__icon">{_esc(icon)}</span>' if icon else ""
    st.markdown(
        f'<div class="sw-alert sw-alert--{level}">{icon_html}<span>{_esc(text)}</span></div>',
        unsafe_allow_html=True,
    )


def section_label(text: str, *, warning: bool = False) -> None:
    """Render een kleine mono-uppercase label-tekst (bv. boven een sectie)."""
    cls = "sw-label sw-label--warning" if warning else "sw-label"
    st.markdown(f'<p class="{cls}">{_esc(text)}</p>', unsafe_allow_html=True)


def action_tile(
    icon: str,
    titel: str,
    sub: str,
    page: str,
    *,
    key: str,
) -> None:
    """Render een klikbare home-actie-tile.

    Combineert een visuele kaart (icon/titel/sub) met een Streamlit-knop die
    via :func:`st.switch_page` navigeert. De knop draagt de pagina-redirect; de
    HTML-kaart toont de presentatie. Aanroepen binnen een ``st.container``.
    """
    st.markdown(
        f'<div class="sw-tile">'
        f'<p class="sw-tile__icon">{_esc(icon)}</p>'
        f'<p class="sw-tile__title">{_esc(titel)}</p>'
        f'<p class="sw-tile__sub">{_esc(sub)}</p>'
        f"</div>",
        unsafe_allow_html=True,
    )
    if st.button("OPEN", key=key, type="primary", use_container_width=True):
        st.switch_page(page)


def rule() -> None:
    """Subtiele scheidingslijn."""
    st.markdown('<hr class="sw-rule" />', unsafe_allow_html=True)
