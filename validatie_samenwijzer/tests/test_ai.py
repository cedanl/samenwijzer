"""De gedeelde Anthropic-client dwingt het gedocumenteerde 30s-timeout-contract af."""

import httpx

from validatie_samenwijzer import _ai


def test_client_heeft_timeout_en_retries():
    # api_key-tak → verse client, geen env-sleutel nodig.
    client = _ai._client(api_key="test-key")
    assert client.timeout == httpx.Timeout(30.0, connect=10.0)
    assert client.max_retries == 2
