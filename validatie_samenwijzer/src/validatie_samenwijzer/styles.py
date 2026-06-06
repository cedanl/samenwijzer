"""Validatie Samenwijzer — editorial / archief-stijl.

Warm papier + inkt + vermiljoen-accent, met markeerstift-geel als citaat-device.
Instrument Serif (display) + Hanken Grotesk (body) + JetBrains Mono (labels).
Bewuste afwijking van de CEDA/Npuls-huisstijl: de OER wordt behandeld als een
juridisch document dat leesbaar wordt gemaakt.
"""

from typing import Literal

# ── Palet ──────────────────────────────────────────────────────────────────
PAPER = "#f2ece0"  # paginabachtergrond — warm crème
PAPER_CARD = "#f8f3e9"  # cards, bubbles, surfaces
PAPER_DEEP = "#e7decc"  # progress-track, subtiele vullingen
INKT = "#211910"  # body, koppen — warme bijna-zwart
INKT_ZACHT = "#5e5343"  # secondary text
INKT_VAAG = "#8c8170"  # meta, labels, placeholders
VERMILJOEN = "#da3a1e"  # primair accent — links, knoppen, tab-highlight
VERMILJOEN_DONKER = "#b22c12"  # hover op primaire knop
MARKER = "#ffd84d"  # markeerstift — citaat-accent
MARKER_WAS = "rgba(255, 216, 77, 0.16)"  # citaat-achtergrond
LIJN = "rgba(33, 25, 16, 0.14)"  # borders, scheidingslijnen
LIJN_ZACHT = "rgba(33, 25, 16, 0.08)"  # subtiele lijnen

# Status-tinten — gebruikt in pagina's voor voortgang/risico-indicatoren.
# ORANJE is naar amber geschoven zodat de risico-status onderscheidbaar blijft
# van het vermiljoen-merkaccent (zelfde tintfamilie).
GROEN = "#27ae60"
ORANJE = "#c9881c"
ROOD = "#c0392b"

# SVG-ruis als data-uri — subtiele papier-grain over de hele app.
_GRAIN = (
    "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' "
    "width='160' height='160'%3E%3Cfilter id='n'%3E%3CfeTurbulence "
    "type='fractalNoise' baseFrequency='.9' numOctaves='3' stitchTiles='stitch'/"
    "%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/"
    '%3E%3C/svg%3E")'
)

CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=Hanken+Grotesk:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;700&display=swap');

html, body, [class*="css"] {{
    font-family: 'Hanken Grotesk', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    font-size: 16px;
    line-height: 1.55;
    background-color: {PAPER};
    color: {INKT};
}}

/* Streamlit's app-container heeft een eigen achtergrond die html/body overschrijft. */
[data-testid="stApp"],
[data-testid="stAppViewContainer"],
[data-testid="stMain"],
.stApp {{
    background-color: {PAPER} !important;
}}

/* ── Papier-grain over de hele app ──────────────────────────────────────── */
[data-testid="stAppViewContainer"]::before {{
    content: "";
    position: fixed;
    inset: 0;
    z-index: 9999;
    pointer-events: none;
    opacity: 0.045;
    mix-blend-mode: multiply;
    background-image: {_GRAIN};
}}

::selection {{ background: {MARKER}; color: {INKT}; }}

/* ── Koppen — Instrument Serif voor display (weight 400, géén synthetische
   bold), Hanken Grotesk voor functionele subkoppen ─────────────────────── */
h1, h2,
[data-testid="stMarkdown"] h1,
[data-testid="stMarkdown"] h2,
[data-testid="stMarkdownContainer"] h1,
[data-testid="stMarkdownContainer"] h2,
[data-testid="stHeadingWithActionElements"] h1,
[data-testid="stHeadingWithActionElements"] h2 {{
    font-family: 'Instrument Serif', Georgia, serif !important;
    font-weight: 400 !important;
    color: {INKT} !important;
    letter-spacing: -0.015em !important;
}}

h3, h4,
[data-testid="stMarkdown"] h3,
[data-testid="stMarkdown"] h4,
[data-testid="stMarkdownContainer"] h3,
[data-testid="stMarkdownContainer"] h4,
[data-testid="stHeadingWithActionElements"] h3 {{
    font-family: 'Hanken Grotesk', sans-serif !important;
    font-weight: 700 !important;
    color: {INKT} !important;
    letter-spacing: -0.01em !important;
}}

[data-testid="stMarkdown"] h1,
[data-testid="stMarkdownContainer"] h1,
[data-testid="stHeadingWithActionElements"] h1,
h1 {{
    font-size: 2.9rem !important;
    line-height: 1.02 !important;
    margin-bottom: 0.25em !important;
}}

[data-testid="stMarkdown"] h2,
[data-testid="stMarkdownContainer"] h2,
h2 {{
    font-size: 2rem !important;
    line-height: 1.05 !important;
    margin-top: 1.3em !important;
    margin-bottom: 0.35em !important;
}}

[data-testid="stMarkdown"] h3,
[data-testid="stMarkdownContainer"] h3,
h3 {{ font-size: 1.18rem !important; }}

a {{
    color: {VERMILJOEN};
    text-decoration: none;
    border-bottom: 1px solid {MARKER};
    transition: border-color 0.15s;
}}

a:hover {{
    border-bottom-color: {VERMILJOEN};
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

/* ── Vaste navigatiebalk — papier met grijze onderlijn ──────────────────── */
.block-container > div > [data-testid="stHorizontalBlock"]:first-of-type {{
    position: fixed !important;
    top: 0 !important; left: 0 !important; right: 0 !important;
    height: 56px !important;
    background: rgba(242, 236, 224, 0.85) !important;
    backdrop-filter: blur(8px) !important;
    z-index: 9998 !important;
    padding: 0 28px !important;
    margin: 0 !important;
    max-width: none !important;
    border-bottom: 1px solid {LIJN_ZACHT} !important;
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
    font-family: 'Hanken Grotesk', sans-serif !important;
    font-size: 14px !important;
    font-weight: 500 !important;
    color: {INKT_ZACHT} !important;
    text-decoration: none !important;
    white-space: nowrap !important;
    box-shadow: none !important;
    transition: color 0.15s, background 0.15s !important;
}}

.block-container > div > [data-testid="stHorizontalBlock"]:first-of-type
    [data-testid="stPageLink"] a:hover {{
    background: {PAPER_DEEP} !important;
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
    border: none !important;
    border-radius: 6px !important;
    padding: 6px 12px !important;
    font-family: 'Hanken Grotesk', sans-serif !important;
    font-size: 14px !important;
    font-weight: 500 !important;
    color: {INKT} !important;
    text-decoration: none !important;
    white-space: nowrap !important;
    box-shadow: none !important;
}}

[data-testid="stPageLink"] a:hover {{
    background: {PAPER_DEEP} !important;
}}

/* ── Mobiel: de nav blijft één rij. Zonder flex-wrap:nowrap wrappen de kolommen
   (brand + links) op smalle schermen naar meerdere rijen en duwen de content
   omlaag; nowrap + overflow-x:auto houdt ze op één horizontaal-scrollbare rij.
   De nav wordt geselecteerd via :has(stPageLink) i.p.v. een vast ouder-pad —
   Streamlit's DOM-nesting (stLayoutWrapper e.d.) verandert per versie, de
   inhoud (de paginalinks) niet. ──────────────────────────────────────────── */
@media (max-width: 640px) {{
    [data-testid="stHorizontalBlock"]:has([data-testid="stPageLink"]) {{
        flex-wrap: nowrap !important;
        overflow-x: auto !important;
        -webkit-overflow-scrolling: touch !important;
        gap: 2px !important;
        padding: 8px 12px !important;
    }}
    [data-testid="stHorizontalBlock"]:has([data-testid="stPageLink"]) [data-testid="stColumn"] {{
        flex: 0 0 auto !important;
        width: auto !important;
        min-width: fit-content !important;
    }}
    [data-testid="stHorizontalBlock"]:has([data-testid="stPageLink"]) [data-testid="stPageLink"] a {{
        min-height: 44px !important;
        display: inline-flex !important;
        align-items: center !important;
    }}
    .block-container {{ padding-top: 1.2rem !important; }}
    .sw-navbrand {{ font-size: 1.05rem; }}
    .sw-pagetitle {{ font-size: 2rem; }}
}}

/* ── Voortgangsbalk ─────────────────────────────────────────────────────── */
.progress-bar-bg {{
    background: {PAPER_DEEP};
    border-radius: 4px;
    height: 8px;
    margin: 5px 0;
    overflow: hidden;
}}
.progress-bar-fill {{
    height: 8px;
    background: {VERMILJOEN};
    border-radius: 4px;
    transition: width 0.4s ease;
}}
.werkproces-row {{
    padding-left: 1.5rem;
}}
.werkproces-label {{
    color: {INKT_ZACHT};
    font-size: 0.9rem;
}}
.werkproces-row .progress-bar-bg {{
    margin-left: 0;
}}

/* ── Bron-kaartje ───────────────────────────────────────────────────────── */
.bron-kaartje {{
    background: {PAPER_CARD};
    border-left: 3px solid {VERMILJOEN};
    border-radius: 4px;
    padding: 0.75rem 1.1rem;
    font-family: 'Hanken Grotesk', sans-serif;
    font-size: 0.95rem;
    margin-bottom: 0.5rem;
    color: {INKT};
}}

/* ── Chat-bubbles ───────────────────────────────────────────────────────── */
.chat-vraag {{
    margin: 1rem 0 0.4rem auto;
    padding: 11px 16px;
    background: {VERMILJOEN};
    border-radius: 16px 16px 4px 16px;
    color: #fff;
    font-family: 'Hanken Grotesk', sans-serif;
    font-size: 0.98rem;
    font-weight: 500;
    line-height: 1.5;
    max-width: 75%;
    width: fit-content;
}}

.chat-antwoord {{
    margin: 0.4rem auto 1.4rem 0;
    padding: 14px 18px;
    background: {PAPER_CARD};
    border: 1px solid {LIJN};
    border-radius: 16px 16px 16px 4px;
    color: {INKT};
    font-family: 'Hanken Grotesk', sans-serif;
    font-size: 1rem;
    line-height: 1.6;
    max-width: 90%;
}}

/* Citaat-pull-quote: markeerstift links-accent + lichte wash, serif cursief.
   Statische CSS (Streamlit voert geen geïnjecteerde JS uit). */
.chat-antwoord blockquote,
.oer-citaat {{
    background: {MARKER_WAS};
    border-left: 4px solid {MARKER};
    border-radius: 0 8px 8px 0;
    margin: 0.9rem 0;
    padding: 0.7rem 1.1rem;
    color: {INKT};
}}

.chat-antwoord blockquote p {{
    margin: 0;
    font-family: 'Instrument Serif', Georgia, serif;
    font-style: italic;
    font-size: 1.16rem;
    line-height: 1.4;
    color: {INKT};
}}

.chat-antwoord code {{
    font-family: 'JetBrains Mono', ui-monospace, Menlo, monospace;
    font-size: 0.82em;
    background: {PAPER_DEEP};
    padding: 1px 5px;
    border-radius: 4px;
    color: {INKT};
}}

/* ── Landingspagina-helpers ─────────────────────────────────────────────── */
.oer-overtitel {{
    font-family: 'JetBrains Mono', monospace;
    text-transform: uppercase;
    letter-spacing: 0.16em;
    font-size: 0.7rem;
    color: {VERMILJOEN};
    margin-bottom: 0.6rem;
    font-weight: 500;
}}

h1.oer-hero {{
    font-family: 'Instrument Serif', Georgia, serif !important;
    font-size: clamp(2.6rem, 5.5vw, 3.8rem) !important;
    line-height: 1.0 !important;
    letter-spacing: -0.02em !important;
    margin: 0 0 0.5rem 0 !important;
}}

.oer-hero .it {{
    font-family: 'Instrument Serif', Georgia, serif;
    font-style: italic;
    color: {VERMILJOEN};
}}

.oer-ondertitel {{
    font-family: 'Hanken Grotesk', sans-serif;
    color: {INKT_ZACHT};
    font-size: 1.1rem;
    margin-top: 0.2rem;
}}

.oer-meta {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.74rem;
    color: {INKT_VAAG};
    letter-spacing: 0.04em;
    line-height: 1.5;
}}

.oer-intro {{
    font-family: 'Hanken Grotesk', sans-serif;
    font-size: 1.08rem;
    line-height: 1.6;
    color: {INKT_ZACHT};
    max-width: 60ch;
}}

.oer-citaat-bron {{
    display: block;
    margin-top: 0.5rem;
    font-family: 'JetBrains Mono', monospace;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    font-size: 0.66rem;
    color: {VERMILJOEN};
    font-weight: 500;
}}

/* ── Login-hero (startpagina) — CSS-only animaties (Streamlit stript JS) ──── */
@keyframes sw-rise {{
    from {{ opacity: 0; transform: translateY(22px); }}
    to   {{ opacity: 1; transform: none; }}
}}
@keyframes sw-sweep {{
    from {{ background-size: 0% 40%; }}
    to   {{ background-size: 100% 40%; }}
}}
@keyframes sw-drift {{
    from {{ transform: translate3d(0, 0, 0) rotate(0deg); }}
    to   {{ transform: translate3d(4%, 3%, 0) rotate(8deg); }}
}}

.sw-hero {{
    position: relative;
    margin: 0.4rem 0 1.6rem;
    padding: 2.7rem 2.3rem 2.5rem;
    border-radius: 22px;
    overflow: hidden;
    background:
        radial-gradient(130% 150% at 0% 0%, rgba(218, 58, 30, 0.10), transparent 55%),
        radial-gradient(120% 160% at 100% 0%, rgba(255, 216, 77, 0.18), transparent 52%),
        {PAPER_CARD};
    border: 1px solid {LIJN};
}}
/* trage warme gloed die langzaam drift — geeft de hero leven zonder JS */
.sw-hero::after {{
    content: "";
    position: absolute;
    top: -50%; left: -50%; width: 200%; height: 200%;
    background: radial-gradient(38% 38% at 32% 30%, rgba(218, 58, 30, 0.07), transparent 70%);
    animation: sw-drift 16s ease-in-out infinite alternate;
    pointer-events: none;
}}
.sw-hero > * {{ position: relative; z-index: 1; }}

.sw-overline {{
    display: flex; align-items: center; gap: 0.6rem;
    font-family: 'JetBrains Mono', monospace;
    text-transform: uppercase;
    letter-spacing: 0.22em;
    font-size: 0.66rem;
    color: {VERMILJOEN};
    margin-bottom: 1rem;
    opacity: 0; animation: sw-rise 0.6s 0.05s ease forwards;
}}
.sw-overline::before {{
    content: ""; width: 26px; height: 1px; background: {VERMILJOEN}; flex: 0 0 auto;
}}

.sw-title {{
    font-family: 'Instrument Serif', Georgia, serif;
    font-weight: 400;
    font-size: clamp(2.9rem, 8vw, 4.6rem);
    line-height: 0.94;
    letter-spacing: -0.02em;
    color: {INKT};
    margin: 0;
    opacity: 0; animation: sw-rise 0.7s 0.12s ease forwards;
}}
.sw-title .fase {{ font-style: italic; color: {VERMILJOEN}; }}

.sw-tagline {{
    font-family: 'Hanken Grotesk', sans-serif;
    font-size: 1.12rem;
    line-height: 1.5;
    color: {INKT_ZACHT};
    max-width: 34em;
    margin: 1.1rem 0 0;
    opacity: 0; animation: sw-rise 0.7s 0.2s ease forwards;
}}
.sw-tagline b {{ color: {INKT}; font-weight: 600; }}

.sw-cite {{
    display: inline-block;
    margin-top: 1.6rem;
    background: {PAPER};
    border: 1px solid {LIJN};
    border-left: 4px solid {MARKER};
    border-radius: 0 10px 10px 0;
    padding: 0.7rem 1.1rem;
    opacity: 0; animation: sw-rise 0.7s 0.3s ease forwards;
}}
.sw-cite .src {{
    display: block;
    font-family: 'JetBrains Mono', monospace;
    text-transform: uppercase; letter-spacing: 0.12em;
    font-size: 0.56rem; color: {VERMILJOEN}; margin-bottom: 0.35rem;
}}
.sw-cite q {{
    font-family: 'Instrument Serif', Georgia, serif;
    font-style: italic; font-size: 1.14rem; color: {INKT};
    padding: 0 0.1em;
    background: linear-gradient({MARKER}, {MARKER}) no-repeat 0 86%;
    background-size: 0% 40%;
    animation: sw-sweep 0.9s 1s ease forwards;
}}
.sw-cite q::before {{ content: "\\201C"; }}
.sw-cite q::after {{ content: "\\201D"; }}

/* Respecteer prefers-reduced-motion: toon de eindstaat zonder animatie
   (anders blijven de op opacity:0 startende elementen onzichtbaar). */
@media (prefers-reduced-motion: reduce) {{
    .sw-overline, .sw-title, .sw-tagline, .sw-cite {{
        opacity: 1 !important; animation: none !important;
    }}
    .sw-cite q {{ background-size: 100% 40% !important; animation: none !important; }}
    .sw-hero::after {{ animation: none !important; }}
}}

/* ── Pagina-hero (post-login) + metadata-chips ──────────────────────────── */
.sw-pagehero {{
    margin: 0.2rem 0 1.3rem;
    padding: 0 0 1rem;
    border-bottom: 1px solid {LIJN};
}}
.sw-kicker {{
    display: flex; align-items: center; gap: 0.55rem;
    font-family: 'JetBrains Mono', monospace;
    text-transform: uppercase; letter-spacing: 0.16em;
    font-size: 0.66rem; color: {VERMILJOEN};
    margin-bottom: 0.5rem;
}}
.sw-kicker::before {{
    content: ""; width: 22px; height: 1px; background: {VERMILJOEN}; flex: 0 0 auto;
}}
.sw-pagetitle {{
    font-family: 'Instrument Serif', Georgia, serif;
    font-weight: 400;
    font-size: clamp(2rem, 4.2vw, 2.9rem);
    line-height: 1.0; letter-spacing: -0.015em;
    color: {INKT}; margin: 0;
}}
.sw-chips {{
    display: flex; flex-wrap: wrap; gap: 0.45rem; margin-top: 0.85rem;
}}
.sw-chip {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.68rem; letter-spacing: 0.03em;
    color: {INKT_ZACHT};
    background: {PAPER_DEEP};
    border-radius: 999px;
    padding: 0.28rem 0.7rem;
    white-space: nowrap;
}}
.sw-chip.accent {{
    color: {VERMILJOEN};
    background: transparent;
    border: 1px solid {VERMILJOEN};
}}

/* ── Nav-brand (app-naam in elke pagina-header) ─────────────────────────── */
.sw-navbrand {{
    font-family: 'Instrument Serif', Georgia, serif;
    font-size: 1.18rem; line-height: 1; color: {INKT};
    white-space: nowrap;
}}
.sw-navbrand em {{ font-style: italic; color: {VERMILJOEN}; }}

/* ── Containers (st.container border=True) ──────────────────────────────── */
[data-testid="stVerticalBlockBorderWrapper"] {{
    background: {PAPER_CARD} !important;
    border-radius: 12px !important;
    border: 1px solid {LIJN} !important;
    box-shadow: none !important;
    padding: 8px 14px;
}}

/* ── Knoppen ─────────────────────────────────────────────────────────────── */
/* Box-eigenschappen (border/radius/bg/padding) alléén op de knop zelf — niet op
   de p/span erbinnen, anders krijgen die hun eigen pill-border (concentrische
   ringen, op papier zichtbaar). Tekststyling wél op knop + p + span. */
[data-testid="stBaseButton-primary"] {{
    background-color: {VERMILJOEN} !important;
    border-radius: 50px !important;
    border: 1px solid {VERMILJOEN} !important;
    padding: 0.55rem 1.4rem !important;
    box-shadow: none !important;
}}

[data-testid="stBaseButton-primary"],
[data-testid="stBaseButton-primary"] p,
[data-testid="stBaseButton-primary"] span {{
    color: #fff !important;
    font-family: 'Hanken Grotesk', sans-serif !important;
    letter-spacing: 0.01em !important;
    font-size: 0.95rem !important;
    font-weight: 600 !important;
}}

[data-testid="stBaseButton-primary"]:hover {{
    background-color: {VERMILJOEN_DONKER} !important;
    border-color: {VERMILJOEN_DONKER} !important;
}}

[data-testid="stBaseButton-secondary"] {{
    background-color: {PAPER_CARD} !important;
    border-radius: 50px !important;
    border: 1px solid {LIJN} !important;
    padding: 0.5rem 1.2rem !important;
}}

[data-testid="stBaseButton-secondary"],
[data-testid="stBaseButton-secondary"] p,
[data-testid="stBaseButton-secondary"] span {{
    color: {INKT} !important;
    font-family: 'Hanken Grotesk', sans-serif !important;
    font-size: 0.92rem !important;
    font-weight: 500 !important;
}}

[data-testid="stBaseButton-secondary"]:hover {{
    background-color: {PAPER_DEEP} !important;
    border-color: {INKT} !important;
    color: {INKT} !important;
}}

/* ── Form elements ──────────────────────────────────────────────────────── */
[data-testid="stTextInput"] input,
[data-testid="stTextArea"] textarea {{
    background: {PAPER_CARD} !important;
    border: 1px solid {LIJN} !important;
    border-radius: 8px !important;
    font-family: 'Hanken Grotesk', sans-serif !important;
    color: {INKT} !important;
}}

[data-testid="stTextInput"] input:focus,
[data-testid="stTextArea"] textarea:focus {{
    border-color: {VERMILJOEN} !important;
    box-shadow: 0 0 0 3px {MARKER_WAS} !important;
}}

/* ── Tabs ───────────────────────────────────────────────────────────────── */
[data-testid="stTabs"] [role="tab"] p {{
    font-family: 'Hanken Grotesk', sans-serif !important;
    font-size: 0.95rem !important;
    font-weight: 500 !important;
    color: {INKT_ZACHT} !important;
}}

[data-testid="stTabs"] [role="tab"][aria-selected="true"] p {{
    color: {INKT} !important;
    font-weight: 600 !important;
}}

[data-testid="stTabs"] [data-baseweb="tab-highlight"] {{
    background: {VERMILJOEN} !important;
}}

/* ── Chat-input ─────────────────────────────────────────────────────────── */
[data-testid="stBottom"],
[data-testid="stBottomBlockContainer"] {{
    background-color: {PAPER} !important;
    border-top: 1px solid {LIJN} !important;
}}

[data-testid="stChatInput"],
[data-testid="stChatInputTextArea"],
[data-testid="stChatInput"] textarea {{
    background: {PAPER_CARD} !important;
    border: 1px solid {LIJN} !important;
    border-radius: 12px !important;
    font-family: 'Hanken Grotesk', sans-serif !important;
    color: {INKT} !important;
}}

[data-testid="stChatInput"]:focus-within {{
    border-color: {VERMILJOEN} !important;
}}

/* ── Footer ─────────────────────────────────────────────────────────────── */
.footer {{
    position: fixed; bottom: 0; left: 0; right: 0;
    background: {PAPER};
    border-top: 1px solid {LIJN};
    padding: 0.6rem 1.5rem;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.7rem;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: {INKT_VAAG};
    text-align: center;
    z-index: 999;
}}

/* Honoreer expliciete line-breaks (\\n) in button-labels zoals "Nieuw\\ngesprek".
   word-break + overflow-wrap voorkomen dat smalle columns letters losknippen. */
.stButton > button {{
    min-width: min-content;
}}
.stButton > button p {{
    white-space: pre-line;
    line-height: 1.15;
    word-break: keep-all;
    overflow-wrap: normal;
}}
</style>
"""

_NAV_STUDENT = [
    ("💬 Stel een vraag", "pages/1_oer_assistent.py"),
    ("📄 Mijn studiegids", "pages/2_mijn_oer.py"),
    ("📊 Mijn voortgang", "pages/3_mijn_voortgang.py"),
]

_NAV_MENTOR = [
    ("👥 Mijn studenten", "pages/4_mijn_studenten.py"),
    ("🎓 Begeleidingssessie", "pages/5_begeleidingssessie.py"),
]


_OPLEIDING_DROP = {
    "oer",
    "mjp",
    "examenplan",
    "examenplannen",
    "addendum",
    "vanaf",
    "cohort",
    "vg",
    "zw",
    "tt",
    "def",
    "vastgesteld",
    "concept",
    "maanden",
    "jaar",
}
_OPLEIDING_KLEIN = {"En", "In", "De", "Van", "Het", "Op", "Of", "Met", "Voor", "Naar", "Te"}


def schoon_opleiding_naam(opleiding: str, crebo: str = "") -> str:
    """Leesbare opleidingsnaam uit het ruwe opleiding-/bestandsnaam-veld.

    De strings verschillen sterk per instelling (Aeres 'Examenplannen X 25-26',
    Curio '25581_oer_00_2025_vg_bol_…', Da Vinci '25099BBL2025MJP-MachinistGrondverzet').
    Token-gebaseerde opschoning: split camelCase + cijfergrenzen, gooi structurele
    tokens weg (crebo, leerweg, jaar, cohort, 'examenplan', 'oer', 'mjp', 'vastgesteld',
    niveau-/versie-codes) en houd de mensleesbare naam over. Valt terug op
    'Opleiding {crebo}' als er geen naam overblijft (de crebo staat sowieso als chip).
    """
    import re

    s = opleiding or ""
    s = re.sub(r"(?<=[A-Z])(?=[A-Z][a-z])", " ", s)  # BOLExamenplan → BOL Examenplan
    s = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", s)  # camelCase → camel Case
    s = re.sub(r"(?<=[A-Za-z])(?=\d)", " ", s)  # Woord2025 → Woord 2025
    s = re.sub(r"(?<=\d)(?=[A-Za-z])", " ", s)  # 2025Examenplan → 2025 Examenplan
    s = s.replace("_", " ").replace("-", " ")

    tokens: list[str] = []
    for t in s.split():
        tl = t.lower()
        if tl in _OPLEIDING_DROP or (crebo and t == crebo):
            continue
        if re.fullmatch(r"(?:bol|bbl)+", tl):  # leerweg (evt. samengevoegd, bv. BOLBBL)
            continue
        if re.fullmatch(r"\d+", t):  # alle pure-cijfer tokens (jaar/crebo/datum/cohort/niveau)
            continue
        if re.fullmatch(r"v\d+|n[1-4]|n", tl):  # versie / niveau (ook losse 'n' na cijfer-split)
            continue
        tokens.append(t)

    naam = re.sub(r"\s+", " ", " ".join(tokens)).strip()
    # ingesloten lowercase instellings-prefix vóór de TitleCase-naam (seed-data)
    naam = re.sub(r"^(?:[a-z]{3,}\s+)+(?=[A-Z])", "", naam).strip()
    if not naam:
        return f"Opleiding {crebo}" if crebo else "Opleiding"
    if naam == naam.lower():  # volledig lowercase → titel-case
        naam = naam.title()
    woorden = naam.split()  # Nederlandse voegwoorden/lidwoorden klein (behalve eerste)
    return " ".join(
        w if i == 0 or w not in _OPLEIDING_KLEIN else w.lower() for i, w in enumerate(woorden)
    )


def _opleiding_naam(opleiding: str, crebo: str) -> str:
    """Leesbare naam geformatteerd als 'Naam (crebo)' — legacy-compat."""
    return f"{schoon_opleiding_naam(opleiding, crebo)} ({crebo})"


Schaal = Literal["0-1", "0-100"]


def bepaal_kleur(score: float, schaal: Schaal = "0-100") -> str:
    """GROEN/ORANJE/ROOD op basis van standaard voortgangsdrempels (0.7 / 0.5)."""
    pct = score if schaal == "0-1" else score / 100
    return GROEN if pct >= 0.7 else (ORANJE if pct >= 0.5 else ROOD)


def render_progress_bar(score: float, kleur: str, schaal: Schaal = "0-100") -> str:
    """HTML voor een voortgangsbalk; caller doet `st.markdown(..., unsafe_allow_html=True)`."""
    width = score * 100 if schaal == "0-1" else score
    return (
        f'<div class="progress-bar-bg"><div class="progress-bar-fill" '
        f'style="width:{width:.0f}%;background:{kleur}"></div></div>'
    )


def render_app_hero(
    titel: str, *, kicker: str = "", chips: list | None = None, titel_is_html: bool = False
) -> None:
    """Compacte pagina-hero: mono-kicker + serif-titel + metadata-chips.

    chips: lijst van strings of (tekst, accent_bool)-tuples. Tekst wordt ge-escaped;
    geef titel_is_html=True door voor een bewust opgemaakte titel (bv. cursief accent).
    """
    import html as _html

    import streamlit as st

    kicker_html = f'<div class="sw-kicker">{_html.escape(kicker)}</div>' if kicker else ""
    chip_html = ""
    for c in chips or []:
        tekst, accent = c if isinstance(c, tuple) else (c, False)
        if not tekst:
            continue
        cls = "sw-chip accent" if accent else "sw-chip"
        chip_html += f'<span class="{cls}">{_html.escape(str(tekst))}</span>'
    chips_blok = f'<div class="sw-chips">{chip_html}</div>' if chip_html else ""
    titel_html = titel if titel_is_html else _html.escape(titel)
    st.markdown(
        f'<div class="sw-pagehero">{kicker_html}'
        f'<h1 class="sw-pagetitle">{titel_html}</h1>{chips_blok}</div>',
        unsafe_allow_html=True,
    )


def render_student_info() -> None:
    """Student-identiteit als hero: naam (kicker) + opleiding (titel) + metadata-chips."""
    import streamlit as st

    naam = st.session_state.get("gebruiker_naam", "")
    leerweg = st.session_state.get("leerweg", "")
    opleiding = st.session_state.get("opleiding", "")
    crebo = st.session_state.get("crebo", "")
    instelling = st.session_state.get("instelling", "")
    studentnummer = st.session_state.get("studentnummer", "")

    titel = schoon_opleiding_naam(opleiding, crebo) if opleiding else "Mijn opleiding"
    kicker = " · ".join(x for x in [naam, studentnummer] if x)
    chips = [(f"Crebo {crebo}", True) if crebo else None, leerweg or None, instelling or None]
    render_app_hero(titel, kicker=kicker, chips=[c for c in chips if c])


def render_nav() -> None:
    """Render de vaste navigatiebalk bovenin: app-naam-brand + rolgebaseerde links."""
    import streamlit as st

    rol = st.session_state.get("rol")
    if not rol:
        return

    nav_items = _NAV_STUDENT if rol == "student" else _NAV_MENTOR

    cols = st.columns([3] + [2] * len(nav_items) + [1])
    with cols[0]:
        st.markdown(
            '<span class="sw-navbrand">De digitale <em>gids</em></span>',
            unsafe_allow_html=True,
        )
    for i, (label, page) in enumerate(nav_items):
        with cols[i + 1]:
            st.page_link(page, label=label)
    with cols[-1]:
        st.page_link("pages/uitloggen.py", label="🚪 Uitloggen")


def render_footer() -> None:
    """Render de vaste footer onderaan de pagina."""
    import streamlit as st

    st.markdown(
        '<div class="footer">De digitale gids · CEDA 2026 · Npuls</div>',
        unsafe_allow_html=True,
    )
