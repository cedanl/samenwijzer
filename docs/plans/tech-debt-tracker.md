# Tech Debt Tracker

| ID | Description | Domain | Priority | Opened |
|---|---|---|---|---|
| ~~TD-001~~ | ~~ResourceWarning: unclosed SQLite connections~~ — **gesloten 2026-04-11**: `_verbinding()` context manager toegevoegd met `conn.close()` in `finally`. | outreach_store | — | 2026-04-10 |
| ~~TD-002~~ | ~~0% coverage op `welzijn.py`, `coach.py`, `visualize.py`~~ — **gesloten 2026-04-11**: 52 tests toegevoegd met gemockte Anthropic SDK; alle drie op 100%. | testing | — | 2026-04-10 |
| ~~TD-003~~ | ~~Campagne en WelzijnsCheck CRUD niet afgedekt~~ — **gesloten 2026-04-11**: 16 tests toegevoegd; `outreach_store.py` op 97%. | testing | — | 2026-04-10 |
| ~~TD-004~~ | ~~SMTP env var inconsistency~~ — **gesloten 2026-04-11**: geverifieerd geen lingering `AFZENDER_EMAIL` referenties. `SMTP_AFZENDER` is de standaard. | outreach | — | 2026-04-10 |
| TD-005 | Desktop fixed-header nav-CSS in `validatie_samenwijzer/styles.py` is dood op Streamlit 1.56: de selector `.block-container > div > [data-testid="stHorizontalBlock"]:first-of-type` matcht niet meer (Streamlit voegde een `stLayoutWrapper` toe), dus de desktop-nav is `position:static` i.p.v. een sticky balk. Mobiel is in #157 gefixt via `:has([data-testid="stPageLink"])`; desktop wacht op dezelfde rewrite + her-verificatie van de content `padding-top`-offset. | validatie_samenwijzer / UI | laag | 2026-06-06 |
