# Frontend

## Rules

- `app/main.py` is the sole entry point for the Streamlit UI.
- No business logic in the app layer — import from `src/samenwijzer/` only.
- Use `st.session_state` for state; never use global variables.
- Pages are split into separate files under `app/pages/`.

## Dual-theme design-systeem

`styles.py` exporteert twee thema's bovenop één gedeeld fundament. De rol uit
`st.session_state["rol"]` bepaalt welk thema geladen wordt:

| Thema | Doelgroep | Palet | Form | Devices |
|---|---|---|---|---|
| **student** | MBO-studenten 16–22 | donker `#0F0F12` + `#1A1A1F`, lime-accent `#A8FF60`, coral-alert `#FF5E3A` | pill-vormige badges + knoppen | mobile-first |
| **docent** | mentoren / docenten | paper `#F0EBE1` + `#FAF5EC`, sage-accent `#6F8265`, rust-alert `#B04A1A` | rechthoekige chips, ink primary | desktop |

Gedeeld fundament: Cabinet Grotesk display (700/800), Satoshi body (500/700),
JetBrains Mono labels, spacing-scale 4·8·12·16·24·32·48, motion 150/240ms ease-out.

WCAG AA contrast: alle text-tokens halen ≥4.5:1 op de eigen achtergrond.

## Component-helpers (`samenwijzer.styles`)

Eén plek voor alle herbruikbare HTML-blokken. Inline `st.markdown("<p style='…'>")`
voor onderdelen die een helper hebben is niet toegestaan — gebruik de helper
zodat beide thema's correct meebewegen.

| Helper | Doel |
|---|---|
| `inject_theme(rol)` | Base-CSS + thema-CSS injecteren op basis van `rol` (`"student"` / `"docent"` / `None` = docent-fallback). |
| `render_nav()` | Vaste header bovenaan; rol-bewust (student- of docent-nav). |
| `render_footer()` | CEDA/Npuls credit onderaan. |
| `hero(naam, meta, badges=[])` | Hero-blok bovenaan pagina; optionele lijst van `(kind, label)` badges. |
| `stat_card(label, value, *, value_sub, delta, delta_negative, sub, progress, alert_ring)` | Stat-card met optionele inline progress-ring (0.0–1.0). |
| `badge(kind, text)` | HTML-string voor inline gebruik (in `st.markdown`). Kinds: `starter`, `onderweg`, `gevorderde`, `expert`, `onschema`, `urgent`, `accent` + outreach- en welzijn-varianten. |
| `render_badge(kind, text)` | Wrapper rond `badge` die direct rendert. |
| `alert(text, level, *, icon)` | Inline alert-balk (`info` / `warning` / `urgent`). |
| `section_label(text, *, warning)` | Mono-uppercase label. |
| `action_tile(icon, titel, sub, page, *, key)` | Klikbare home-tegel (kaart + button + `switch_page`). |
| `rule()` | Subtiele scheidingslijn. |

## Pagina-template

Elke pagina volgt dit patroon:

```python
import streamlit as st
from samenwijzer.styles import hero, inject_theme, render_footer, render_nav

st.set_page_config(page_title="…", page_icon="📊", layout="wide")

if "df" not in st.session_state or "rol" not in st.session_state:
    inject_theme(None)
    st.warning("Ga eerst naar de [startpagina](/) om in te loggen.")
    st.stop()

df = st.session_state["df"]
rol = st.session_state["rol"]
inject_theme(rol)
render_nav()

# ... pagina-content via component-helpers ...

render_footer()
```

## Navigation

`render_nav()` rendert een `position:fixed; top:0; height:52px; z-index:9999`
horizontale balk via Streamlit's `st.page_link()` (client-side nav — HTML `<a>`
zou een full reload triggeren en de sessie wissen).

- **Student nav**: Home · Voortgang · Groeidossier · Leercoach · Welzijn
- **Docent nav**: Home · Groep · Groeidossier · Outreach · Leercoach

Uitloggen links to `/uitloggen` (`app/pages/uitloggen.py`), which clears
`st.session_state` and redirects to the home page.

Streamlit's native sidebar is volledig uitgeschakeld:
- `.streamlit/config.toml`: `showSidebarNavigation = false`
- CSS: `[data-testid="stSidebar"] { display: none !important; }`

## Access control patterns

**Docent-only page:**
```python
vereist_docent()              # stops page if rol ≠ "docent"
df = mentor_filter(df)        # filters to own students only
```

**Student-only page:**
```python
if st.session_state.get("rol") != "student":
    st.warning("...")
    st.stop()
studentnummer = st.session_state["studentnummer"]
```

## Thema-aware visualisaties

Elke functie in `visualize.py` accepteert een keyword-only `rol`-parameter
zodat Altair- en Plotly-charts in beide thema's correct renderen (bars,
backgrounds, axis-fonts, gridlines, legend-kleuren):

```python
st.altair_chart(werkproces_grafiek(wp_df, rol=rol), use_container_width=True)
st.plotly_chart(spinneweb_figuur(..., rol=rol), use_container_width=True)
```

Default zonder `rol` valt terug op het docent-paper-thema.

## Page inventory

| File | Icon | Access | Description |
|---|---|---|---|
| `main.py` | — | public | Split-screen login + rol-specifieke home (hero + stat-cards + action-tiles) |
| `1_mijn_voortgang.py` | 📊 | student/docent | Hero + 3 ring-stat-cards (voortgang/BSA/positie) + tabs Scores/Aandacht/Weekplan |
| `2_groepsoverzicht.py` | 👥 | docent | Hero + 4 stat-cards, filters, voortgang+welzijn-tabs |
| `3_leercoach.py` | 🎓 | student/docent | Hero met niveau-badge, AI tutor/lesmateriaal/oefentoets/feedback/rollenspel-tabs |
| `4_outreach.py` | 📬 | docent | Hero, werklijst met badge()-statussen, campagnes, effectiviteit (stat-cards) |
| `5_welzijn.py` | 💚 | student | Zacht ingangsmoment "Hoe gaat het, {voornaam}?" + check-formulier |
| `6_groeidossier.py` | 🌱 | student/docent | Hero, kerntaak-/werkproces-cards met statusbadges, spinneweb (thema-bewust) |
| `uitloggen.py` | — | — | Sessie wissen + redirect naar `/` |

## AI call conventions

- All streaming AI calls use `st.write_stream()`.
- Store the streamed result in `st.session_state` so re-renders don't re-trigger the API.
- Wrap in `st.spinner("…")` with a descriptive message.

## Streamlit-quirks

- **Form-submit-buttons** binnen `st.form` gebruiken testid
  `stBaseButton-primaryFormSubmit` / `…secondaryFormSubmit` (niet
  `stBaseButton-primary`). CSS in `styles.py` dekt beide.
- **Hot-reload van CSS** werkt niet altijd — bij wijzigingen in `styles.py` is
  een server-herstart (`pkill -f streamlit`) soms nodig. Page-reload alleen wist
  bovendien `st.session_state` en vereist nieuwe login.
- **Sessie reset bij Python-file-reload** — Streamlit herlaadt module-changes
  automatisch maar verliest dan `st.session_state`. Verwacht-gedrag.
