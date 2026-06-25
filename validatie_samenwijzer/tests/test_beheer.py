"""De bronactualiteit-taken in de beheer-allowlist zijn lijst-vorm (geen shell) en
draaien de bron_updates-module zoals de bestaande ingest-taak."""

from app_fastapi.main import _BEHEER_TAKEN


def test_bron_updates_taken_in_allowlist():
    assert _BEHEER_TAKEN["bron_updates"] == [
        "uv", "run", "python", "-m", "validatie_samenwijzer.bron_updates"
    ]
    assert _BEHEER_TAKEN["bron_updates_oer"] == [
        "uv", "run", "python", "-m", "validatie_samenwijzer.bron_updates", "--oer"
    ]


def test_bron_updates_taken_zijn_lijst_vorm():
    # Geen shell-string (injectie-veilig), spiegelt het ingest_alles-patroon.
    for taak in ("bron_updates", "bron_updates_oer"):
        cmd = _BEHEER_TAKEN[taak]
        assert isinstance(cmd, list) and all(isinstance(x, str) for x in cmd)
