# Ontwerpbeslissingen — Validatie Samenwijzer

**Datum:** 2026-04-22 | **Sprint:** 1

| # | Beslissing | Keuze | Reden |
|---|---|---|---|
| 1 | Query-UX | Hybride: AI-antwoord + OER-bronpassages, doorvragen mogelijk | OER is juridisch bindend — bronnen altijd zichtbaar zodat fouten direct opvallen |
| 2 | Embeddings | OpenAI `text-embedding-3-small` | Sterkst op Nederlandse tekst; OpenAI key beschikbaar |
| 3 | Vectordatabase | ChromaDB persistent op schijf | Eenvoudig lokaal, geen externe service nodig |
| 4 | AI-model | Anthropic Claude Sonnet (`claude-sonnet-4-6`) | Al in gebruik in samenwijzer; AI-isolatie via `_ai._client()` |
| 5 | App-structuur | Standalone Streamlit in `validatie_samenwijzer/` | Sprint 1 afgebakend; patronen (db, login, styles) worden conceptueel hergebruikt |
| 6 | Database | SQLite met volledig datamodel | Production-ready fundament; zelfde patronen als samenwijzer |
| 7 | Ingestie | Losse CLI `ingest.py` | Niet elke app-start OER's herindexeren; bewuste trigger bij nieuwe OER's |
| 8 | PDF-extractie | `pdfplumber` | Behoudt tabellen en kolommen beter dan pypdf |
| 9 | Kerntaken/werkprocessen | Aparte tabellen `kerntaken` + `student_kerntaak_scores` | OER-agnostisch — echte namen uit het OER, geen hardcoded kt_1/kt_2 |
| 10 | Chat-layout | Boven/onder (aanpak A) | Mobile-first; werkt op alle schermbreedtes zonder sidebar |
| 11 | Mentor-flow | Student kiezen → begeleidingssessie (profiel + chat naast elkaar) | App is begeleidingstool tijdens 1-op-1 gesprek, niet een OER-browser |
| 12 | Toegangsfilter | ChromaDB `where`-filter op `oer_id` | Nooit post-filteren; student ziet alleen eigen OER, mentor ziet OER van actieve student |
| 13 | Chat-persistentie | Alleen `st.session_state`, geen DB | Buiten scope sprint 1 |
| 14 | Gebruikersbeheer | Seed-script voor testgebruikers | Beheerinterface buiten scope sprint 1 |
