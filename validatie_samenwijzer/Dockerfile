# Image voor de Fly-app "samenwijzer-fase-1".
# Build-context = repo-root (data leeft buiten het subproject in ../oeren en
# ../kwalificatiedossiers). Deploy daarom vanuit de repo-root met
#   flyctl deploy --config validatie_samenwijzer/fly.toml -a samenwijzer-fase-1
#
# Corpus wordt in het image gebakken (immutable, geen runtime-data-afhankelijkheid,
# geen Box/rclone op runtime). De app is read-only tegen validatie.db, dus geen volume nodig.
FROM python:3.13-slim

# uv voor reproduceerbare installs vanuit uv.lock
RUN pip install --no-cache-dir uv

WORKDIR /app/validatie_samenwijzer

# 1) Code + metadata + vooraf gebouwde validatie.db (in data/) + skills (data/skills)
COPY validatie_samenwijzer/ ./
# 2) Dependencies installeren uit de lockfile (zonder dev-groep)
RUN uv sync --frozen --no-dev

# 3) Read-only referentiedata. oeren/ bevat ook de 4 Box-only instellingen:
#    die staan lokaal op schijf, dus ze komen ALLEEN via dit image in de app
#    (niet publiek in git). KD: alleen .md (chat-bron) — pdf/zip uitgesloten via .dockerignore.
COPY oeren/ /app/oeren/
COPY kwalificatiedossiers/ /app/kwalificatiedossiers/

ENV OEREN_PAD=/app/oeren \
    KWALDOSSIERS_PAD=/app/kwalificatiedossiers/pdfs \
    SKILLS_PAD=/app/validatie_samenwijzer/data/skills \
    DB_PATH=/app/validatie_samenwijzer/data/validatie.db \
    BEHEER_ENABLED=false

EXPOSE 8080
CMD ["uv", "run", "--no-dev", "streamlit", "run", "app/main.py", \
     "--server.port=8080", "--server.address=0.0.0.0", "--server.headless=true"]
