import httpx
import pytest


@pytest.fixture(autouse=True)
def no_real_http(monkeypatch):
    # Every test is offline unless it explicitly supplies a MockTransport.
    async def blocked(*args, **kwargs):
        raise AssertionError("Tests must not send real HTTP requests")

    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", blocked)
