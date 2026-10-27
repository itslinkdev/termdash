import asyncio
from dataclasses import replace
import json

import httpx
import pytest

from termdash.providers import weather
from termdash.providers.weather import CACHE_TTL, WeatherError, WeatherProvider


CURRENT = {"temperature_2m": 20.5, "relative_humidity_2m": 62,
           "wind_speed_10m": 12.0, "weather_code": 2}
CITY = {"name": "London", "country": "United Kingdom", "latitude": 51.5, "longitude": -0.12}


@pytest.fixture
def network(monkeypatch):
    requests, delays = [], []
    def handler(request):
        return httpx.Response(200, json=(
            {"results": [CITY]} if "geocoding-api" in request.url.host else {"current": CURRENT}
        ))
    client = httpx.AsyncClient

    def make_client(**kwargs):
        assert kwargs["timeout"] == 5.0

        async def respond(request):
            requests.append(request)
            assert request.extensions["timeout"] == dict(connect=5, read=5, write=5, pool=5)
            return handler(request)

        return client(**kwargs, transport=httpx.MockTransport(respond))

    async def sleep(delay):
        delays.append(delay)

    monkeypatch.setattr(weather.httpx, "AsyncClient", make_client)
    monkeypatch.setattr(weather.asyncio, "sleep", sleep)

    # The setter lets each test change responses while keeping request assertions.
    def set_handler(callback):
        nonlocal handler
        handler = callback

    return requests, delays, set_handler


def test_live_weather_and_persistent_cache(tmp_path, network):
    requests, delays, _ = network
    provider = WeatherProvider("London", cache_dir=tmp_path)
    sample = asyncio.run(provider.fetch())
    assert sample.temperature_c == 20.5
    assert sample.humidity_percent == 62
    assert sample.wind_kmh == 12
    assert sample.condition == "Partly cloudy"
    assert sample.location == "London, United Kingdom"
    assert not sample.stale and not sample.error
    assert requests[0].url.params["name"] == "London"
    assert requests[1].url.path == "/v1/forecast"
    assert requests[1].url.params["temperature_unit"] == "celsius"
    assert requests[1].url.params["latitude"] == "51.5"
    assert len(requests) == 2 and delays == []
    payload = json.loads(provider.cache_path.read_text(encoding="utf-8"))
    assert payload["current"] == CURRENT
    assert payload["location"] == "London"
    assert asyncio.run(WeatherProvider("London", cache_dir=tmp_path).fetch()) == sample
    assert len(requests) == 2


def test_exact_ttl_boundary_refreshes(tmp_path, network, monkeypatch):
    now = 10_000.0
    monkeypatch.setattr(weather, "time", lambda: now)
    provider = WeatherProvider("London", cache_dir=tmp_path)
    original = asyncio.run(provider.fetch())
    now += CACHE_TTL - 0.01
    assert asyncio.run(provider.fetch()) == original
    assert len(network[0]) == 2
    now += 0.01
    asyncio.run(provider.fetch())
    assert len(network[0]) == 4


def test_timeout_retries_stale_cache_and_recovery(tmp_path, network, monkeypatch):
    requests, delays, set_handler = network
    now = 10_000.0
    monkeypatch.setattr(weather, "time", lambda: now)
    provider = WeatherProvider("London", cache_dir=tmp_path)
    good = asyncio.run(provider.fetch())
    contents = provider.cache_path.read_bytes()
    now += CACHE_TTL

    def timeout(request):
        raise httpx.ReadTimeout("connection timed out", request=request)

    set_handler(timeout)
    # A new process must be able to recover the last good disk sample too.
    provider = WeatherProvider("London", cache_dir=tmp_path)
    stale = asyncio.run(provider.fetch())
    assert stale.stale and "timed out" in stale.error
    assert replace(stale, stale=False, error="") == good
    assert len(requests) == 5 and delays == [0.5, 1.0]
    assert provider.cache_path.read_bytes() == contents
    set_handler(lambda request: httpx.Response(200, json=(
        {"results": [CITY]} if "geocoding-api" in request.url.host else
        {"current": {**CURRENT, "temperature_2m": 23}}
    )))
    recovered = asyncio.run(provider.fetch())
    assert recovered.temperature_c == 23 and not recovered.stale


@pytest.mark.parametrize("failure", ["http", "json", "missing", "city", "shape", "coordinates",
                                    "null", "nan", "bool", "humidity", "wind"])
def test_bad_responses_retry_without_creating_cache(tmp_path, network, failure):
    requests, delays, set_handler = network

    def respond(request):
        if failure == "http":
            return httpx.Response(503)
        if failure == "json":
            return httpx.Response(200, content=b"not json")
        if failure == "shape":
            return httpx.Response(200, json=[])
        if "geocoding-api" in request.url.host:
            if failure == "city":
                return httpx.Response(200, json={"results": []})
            if failure == "coordinates":
                return httpx.Response(200, json={"results": [{**CITY, "latitude": 200}]})
            return httpx.Response(200, json={"results": [CITY]})
        current = dict(CURRENT)
        if failure == "missing":
            current.pop("temperature_2m")
        if failure == "null":
            current["temperature_2m"] = None
        if failure == "bool":
            current["temperature_2m"] = True
        if failure == "nan":
            return httpx.Response(200, content=b'{"current":{"temperature_2m":NaN}}')
        if failure == "humidity":
            current["relative_humidity_2m"] = 101
        if failure == "wind":
            current["wind_speed_10m"] = -1
        return httpx.Response(200, json={"current": current})

    set_handler(respond)
    provider = WeatherProvider("London", cache_dir=tmp_path)
    with pytest.raises(WeatherError, match="after 3 attempts"):
        asyncio.run(provider.fetch())
    assert len(requests) in (3, 6)
    assert delays == [0.5, 1.0]
    assert not provider.cache_path.exists()


@pytest.mark.parametrize("contents", ["not JSON", "[]", "{}", '{"saved_at":null}'])
def test_corrupt_cache_does_not_block_live_weather(tmp_path, network, contents):
    provider = WeatherProvider("London", cache_dir=tmp_path)
    provider.cache_path.write_text(contents, encoding="utf-8")
    assert not asyncio.run(provider.fetch()).stale
    assert len(network[0]) == 2


def test_city_caches_are_separate_and_future_cache_is_ignored(tmp_path, network):
    london = WeatherProvider("London", cache_dir=tmp_path)
    paris = WeatherProvider("Paris", cache_dir=tmp_path)
    assert london.cache_path != paris.cache_path
    asyncio.run(london.fetch())
    payload = json.loads(london.cache_path.read_text(encoding="utf-8"))
    payload["saved_at"] = 10 ** 15
    london.cache_path.write_text(json.dumps(payload), encoding="utf-8")
    asyncio.run(WeatherProvider("London", cache_dir=tmp_path).fetch())
    assert len(network[0]) == 4


def test_read_only_cache_still_returns_live_then_stale_in_memory(tmp_path, network, monkeypatch):
    blocked = tmp_path / "file"
    blocked.write_text("not a directory")
    provider = WeatherProvider("London", cache_dir=blocked)
    now = 10_000.0
    monkeypatch.setattr(weather, "time", lambda: now)
    assert not asyncio.run(provider.fetch()).stale
    now += CACHE_TTL
    network[2](lambda request: httpx.Response(503))
    assert asyncio.run(provider.fetch()).stale


def test_default_cache_directory(tmp_path, monkeypatch):
    monkeypatch.setattr(weather, "user_cache_dir", lambda: tmp_path)
    assert WeatherProvider("London").cache_path.parent == tmp_path
