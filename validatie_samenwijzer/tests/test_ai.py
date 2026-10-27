"""De gedeelde Anthropic-client dwingt het gedocumenteerde 30s-timeout-contract af."""

import httpx

from validatie_samenwijzer import _ai


def test_client_heeft_timeout_en_retries():
    # api_key-tak → verse client, geen env-sleutel nodig.
    client = _ai._client(api_key="test-key")
    assert client.timeout == httpx.Timeout(30.0, connect=10.0)
    assert client.max_retries == 2


def test_client_zonder_workspace_id_stuurt_geen_header(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_WORKSPACE_ID", raising=False)
    client = _ai._client(api_key="test-key")
    assert "anthropic-workspace-id" not in client.default_headers


def test_client_met_workspace_id_stuurt_header(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_WORKSPACE_ID", "wrkspc_test")
    client = _ai._client(api_key="test-key")
    assert client.default_headers["anthropic-workspace-id"] == "wrkspc_test"
