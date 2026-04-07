# Frontend

## Rules

- `app/main.py` is the sole entry point for the Streamlit UI.
- No business logic in the app layer — import from `src/samenwijzer/` only.
- Use `st.session_state` for state; never use global variables.
- Pages are split into separate files under `app/pages/` when the app grows.

## Conventions

- Use `st.set_page_config()` at the top of every page file.
- Error messages shown to users must be friendly (no raw stack traces).
- Loading states: use `st.spinner()` for AI calls > 1 second.
