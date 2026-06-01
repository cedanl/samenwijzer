# Dual-theme UI redesign — design spec

**Status:** approved — proceeding to implementation
**Date:** 2026-05-25
**Branch:** `redesign/dual-theme-ui`

## Doel

Volledige interface-redesign van Samenwijzer zodat de app aansluit bij de werkelijke
gebruiksvorm van twee zeer verschillende doelgroepen:

- **MBO-studenten (16–22 jaar)** — mobiel-first, dagelijks gebruik, energie + motivatie.
- **Mentoren/docenten** — desktop, beslis-tooling, data-dichtheid, professioneel kalm.

Eén codebase, twee thema's, gedeeld component-systeem.

## Vastgelegde keuzes (uit brainstorm)

| Onderwerp | Keuze |
|---|---|
| Scope | Volledige app: login, home, 6 pagina's, nav, footer, alle componenten |
| Brand-vrijheid | Vrij — nieuwe richting (CEDA-footer/credit blijft) |
| Primair device | Student: mobiel · Docent: desktop |
| Student-richting | "Mobile-Native Energy" (donker + lime + coral) |
| Docent-richting | "Soft Nordic" (paper #F0EBE1 + sage + rust) |
| Gedeelde display-font | Cabinet Grotesk 700/800 |
| Gedeelde body-font | Satoshi 500/700 |
| Gedeelde label/mono | JetBrains Mono 400/700 |

## Design tokens

### Student-thema (`data-theme="student"`)

```css
--bg:        #0F0F12   /* ink */
--surface:   #1A1A1F   /* paper-on-dark */
--surface-2: rgba(255,255,255,0.04)
--border:    rgba(255,255,255,0.08)
--text:      #FFFFFF
--text-dim:  rgba(255,255,255,0.55)
--text-faint:rgba(255,255,255,0.40)
--accent:    #A8FF60   /* lime — success, energy, primary CTA */
--alert:     #FF5E3A   /* coral — aandacht, urgentie */
--radius-sm: 8px
--radius-md: 14px
--radius-lg: 22px      /* iets ronder dan docent */
```

### Docent-thema (`data-theme="docent"`)

```css
--bg:        #F0EBE1   /* nordic paper */
--surface:   #FAF5EC   /* card */
--surface-2: #F5EFE1   /* table head */
--border:    rgba(31,29,24,0.08)
--text:      #1F1D18   /* near-black warm */
--text-dim:  #6A6354
--text-faint:#8A8270
--accent:    #6F8265   /* sage — primary action, positief */
--alert:     #B04A1A   /* rust — aandacht, risico */
--radius-sm: 6px
--radius-md: 12px
--radius-lg: 18px
```

### Gedeeld

```css
--space: 4 8 12 16 24 32 48
--type-scale-ratio: 1.25
--ease: cubic-bezier(0.4, 0, 0.2, 1)
--duration-fast: 150ms
--duration-base: 240ms

--font-display: 'Cabinet Grotesk', -apple-system, sans-serif
--font-body:    'Satoshi', -apple-system, sans-serif
--font-mono:    'JetBrains Mono', ui-monospace, monospace
```

## Architectuur

### Theme-switch in Streamlit

`styles.py` exporteert:

- `BASE_CSS` — alle gedeelde tokens, reset, fonts, typografie-scale, motion.
- `THEME_CSS_STUDENT` — student-tokens overschrijven base + student-specifieke component-tweaks.
- `THEME_CSS_DOCENT` — docent-tokens + docent-specifieke tweaks.
- `inject_theme(rol)` — helper die `st.markdown(BASE_CSS + THEME_CSS_<rol>, unsafe_allow_html=True)` aanroept op basis van `st.session_state["rol"]`. Bij ontbreken (login) → docent-thema als default (paper achtergrond werkt voor beide).

Elke pagina vervangt het huidige `st.markdown(CSS, unsafe_allow_html=True)` patroon door
`inject_theme()` direct na `st.set_page_config`.

### Component-helpers (in `styles.py`)

Eén plek voor alle herbruikbare HTML-blokken — elimineert de inline `<p style="...">`
strings die nu door 6 pagina's verspreid zitten:

| Helper | Doel |
|---|---|
| `inject_theme(rol)` | Theme-CSS op basis van rol injecteren |
| `render_nav()` | Bestaand — top-navigation (al rol-bewust) |
| `render_footer()` | Bestaand — CEDA-credit blijft |
| `hero(naam, meta, badges=[])` | Hero-blok bovenaan pagina (greet + meta + badges) |
| `stat(label, value, delta=None, progress=None)` | Stat-card met optionele inline ring |
| `badge(kind, text)` | Pill (student) of chip (docent), kind ∈ {starter/onderweg/gevorderd/expert/urgent/onschema/...} |
| `alert(text, level)` | Inline alert-bar (level ∈ {info, warning, urgent}) |
| `action_tile(icon, titel, sub)` | Klikbare actie-tile voor home-pagina |
| `section_label(text)` | Mono uppercase label-tekst |

### Page-niveau aanpassingen

| Pagina | Belangrijkste wijzigingen |
|---|---|
| `app/main.py` login | Split-screen: linker helft donker (student), rechter paper (docent). Eén formulier per kant. |
| `app/main.py` home (student) | Greet + streak + 2 progress-rings + alert-bar + 3 action-tiles |
| `app/main.py` home (docent) | Welkom + 4-cell summary-grid (op-schema/aandacht/urgent/rank) + 4 action-tiles |
| `app/pages/1_mijn_voortgang.py` | Hero → 3 ring-stat-cards (stacked op mobiel, in grid op desktop) → tabs (Scores/Aandacht/Weekplan) |
| `app/pages/2_groepsoverzicht.py` | Filter-chips → dichte tabel-rijen met inline mini-bar + status-chip + ago-stamp |
| `app/pages/3_leercoach.py` | Chat-interface met thema-specifieke message-bubbles |
| `app/pages/4_outreach.py` | Cards-rijen voor open outreach + effectiviteit-tab met clean panels |
| `app/pages/5_welzijn.py` | Zachte ingang: open vraag in groot serif/grotesk, 4 categorie-tiles met emoji+label, optionele tekst, één primary CTA |
| `app/pages/6_groeidossier.py` | Werkproces-cards met statusbadges (concept/ingediend/goedgekeurd), inline spinneweb (Plotly) blijft maar krijgt thema-kleuren |

### Iconografie

Emoji als icon-vervanger wordt afgebouwd voor docent-rol (te informeel). Student-rol
houdt selectief emoji voor warmte (streak 🔥, welzijn-categorieën). Op termijn een
SVG-iconset; voor deze redesign accepteren we de hybride.

### Motion (zachte basisset)

- Page-load: 200ms fade-in op `block-container` (cubic ease-out)
- Hover op tiles/buttons: 150ms background-shift
- Stat-card ring: 600ms ease-out draw-on op eerste render via CSS `stroke-dashoffset` animatie
- Geen scroll-triggers, geen complex JS — Streamlit-vriendelijk

## Implementatie-aanpak

1. Spec wegschrijven (dit document) + committen.
2. `styles.py` herbouwen — tokens + theme-switch + component-helpers.
3. `app/main.py` login + home herbouwen op nieuwe helpers.
4. Elk van pages/1..6 sequentieel: inline HTML vervangen door helpers, thema toepassen.
5. `tests/test_architecture.py` updaten als import-grenzen veranderen (verwacht: nee).
6. `ruff check --fix`, `ruff format`, `pytest`, `ty check`.
7. Browser smoke test via chrome-devtools-mcp met test-accounts uit `gebruikers.txt`:
   - student (Lisa van Dijk 12345 of gelijkwaardig)
   - docent (mentor uit Verpleegkunde N4)
   - doorlopen: login → home → voortgang → welzijn (student); home → groep → outreach (docent)
8. CLAUDE.md UI-conventies sectie updaten.
9. PR openen via `gh pr create`.

## Out-of-scope

- WhatsApp-webhook UI (geen UI)
- Scheduler / cron-jobs
- Validatie_samenwijzer subproject (eigen `CLAUDE.md`, eigen redesign-traject)
- Backend / data-laag / AI-modules — alleen presentation layer
- Volledige SVG-iconset (apart project)
- Dark-mode toggle voor docent of light-mode voor student (rol IS het thema)

## Succescriterium

- Alle 6 pagina's + login + home tonen het nieuwe thema correct per rol.
- Geen `st.markdown("<p style='...'>")` inline-HTML meer in `app/pages/*.py` voor onderdelen die een component hebben.
- `pytest` + `ruff` + `ty` schoon.
- Browser smoke test: student-flow én docent-flow doorlopen zonder visuele breuken.
- Bestaande tests blijven groen (architectuurtest, business-logic tests onaangetast).
