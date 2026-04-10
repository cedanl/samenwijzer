# Frontend

## Rules

- `app/main.py` is the sole entry point for the Streamlit UI.
- No business logic in the app layer — import from `src/samenwijzer/` only.
- Use `st.session_state` for state; never use global variables.
- Pages are split into separate files under `app/pages/`.

## Navigation

Navigation is a fixed HTML bar injected at the top of every page via `render_nav()` in
`src/samenwijzer/styles.py`. It renders as a `position:fixed; top:0; height:56px; z-index:9999`
`<div>` containing pill-styled `<a>` tags — one per nav item plus "Uitloggen".

- Student nav: Home · Mijn voortgang · Leercoach · Welzijn
- Docent nav: Home · Groepsoverzicht · Outreach · Leercoach

Uitloggen links to `/uitloggen` (`app/pages/uitloggen.py`), which clears session_state and
redirects to the home page via `st.switch_page("main.py")`.

Streamlit's native sidebar navigation is fully disabled:
- `.streamlit/config.toml`: `showSidebarNavigation = false`
- CSS: `[data-testid="stSidebar"] { display: none !important; }`

## Conventions

- Use `st.set_page_config()` at the top of every page file.
- Inject CSS via `st.markdown(CSS, unsafe_allow_html=True)` immediately after page config.
- Call `render_nav()` immediately after CSS injection (renders the fixed header bar).
- Call `render_footer()` at the bottom of every page.
- Error messages shown to users must be friendly (no raw stack traces).
- Loading states: use `st.spinner()` for AI calls > 1 second.
- No sidebar — the EduPulse house style forbids it.

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

## Page inventory

| File | Icon | Access | Description |
|---|---|---|---|
| `main.py` | — | public | Login + session init |
| `1_mijn_voortgang.py` | 📊 | student | BSA, kerntaken, werkprocessen |
| `2_groepsoverzicht.py` | 👥 | docent | Voortgang + welzijnschecks groep |
| `3_leercoach.py` | 🎓 | student | AI tutor, lesmateriaal, oefentoets |
| `4_outreach.py` | 📬 | docent | Werklijst, campagnes, effectiviteit |
| `5_welzijn.py` | 💚 | student | Self-assessment + AI-reactie |
| `uitloggen.py` | — | — | Sessie wissen + redirect naar `/` |

## AI call conventions

- All streaming AI calls use `st.write_stream()`.
- Store the streamed result in `st.session_state` so re-renders don't re-trigger the API.
- Wrap in `st.spinner("…")` with a descriptive message.
