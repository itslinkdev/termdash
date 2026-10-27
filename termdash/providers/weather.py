"""Async Open-Meteo current conditions with a persistent last-good cache."""

import asyncio
from dataclasses import replace
from hashlib import sha256
import json
from math import isfinite
from pathlib import Path
import tempfile
from time import time

import httpx

from termdash.data import WeatherData
from termdash.paths import user_cache_dir


CACHE_TTL = 15 * 60
CONDITIONS = {
    0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Fog", 48: "Rime fog", 51: "Light drizzle", 53: "Moderate drizzle",
    55: "Dense drizzle", 56: "Light freezing drizzle", 57: "Freezing drizzle",
    61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
    66: "Light freezing rain", 67: "Heavy freezing rain", 71: "Slight snow",
    73: "Moderate snow", 75: "Heavy snow", 77: "Snow grains",
    80: "Slight rain showers", 81: "Rain showers", 82: "Violent rain showers",
    85: "Slight snow showers", 86: "Heavy snow showers", 95: "Thunderstorm",
    96: "Thunderstorm / hail", 97: "Heavy thunderstorm", 99: "Thunderstorm / heavy hail",
}


class WeatherError(RuntimeError):
    """Weather is unavailable and there is no usable cached sample."""


def number(value: object) -> float:
    if type(value) not in (int, float) or not isfinite(value):
        raise ValueError("weather response contains an invalid number")
    return float(value)


def parse_weather(current: dict, label: str) -> WeatherData:
    if not isinstance(label, str) or not label.strip():
        raise ValueError("weather response has no location name")
    temperature = number(current["temperature_2m"])
    humidity = number(current["relative_humidity_2m"])
    wind = number(current["wind_speed_10m"])
    code = number(current["weather_code"])
    if not 0 <= humidity <= 100 or not humidity.is_integer() or wind < 0 or not code.is_integer():
        raise ValueError("weather response has invalid humidity, wind, or condition")
    return WeatherData(temperature, CONDITIONS.get(int(code), f"Weather code {int(code)}"),
                       int(humidity), wind, label)


class WeatherProvider:
    def __init__(self, location: str, *, cache_dir: Path | None = None) -> None:
        self.location = location.strip()
        if len(self.location) < 2:
            raise ValueError("Weather location must have at least two characters")
        key = sha256(self.location.casefold().encode("utf-8")).hexdigest()[:16]
        directory = cache_dir if cache_dir is not None else user_cache_dir()
        self.cache_path = directory / f"weather-{key}.json"
        self._last_good: tuple[float, WeatherData] | None = None

    def read_cache(self) -> tuple[float, WeatherData] | None:
        if self._last_good is not None:
            return self._last_good
        try:
            payload = json.loads(self.cache_path.read_text(encoding="utf-8"))
            saved_at = number(payload["saved_at"])
            if payload["location"] != self.location or not 0 <= saved_at <= time():
                return None
            data = parse_weather(payload["current"], payload["name"])
            self._last_good = saved_at, data
            return self._last_good
        except (OSError, ValueError, KeyError, TypeError, OverflowError):
            return None

    def write_cache(self, current: dict, data: WeatherData) -> None:
        saved_at = time()
        self._last_good = saved_at, data
        temporary = None
        try:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", suffix=".tmp",
                                             dir=self.cache_path.parent, delete=False) as stream:
                temporary = Path(stream.name)
                json.dump({"saved_at": saved_at, "location": self.location,
                           "name": data.location,
                           "current": {key: current[key] for key in (
                               "temperature_2m", "relative_humidity_2m",
                               "wind_speed_10m", "weather_code",
                           )}}, stream, allow_nan=False)
            temporary.replace(self.cache_path)
        except OSError:
            # A read-only cache must not discard fresh weather or the in-memory fallback.
            pass
        finally:
            if temporary is not None:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError:
                    pass

    async def fetch(self) -> WeatherData:
        cached = self.read_cache()
        if cached is not None and 0 <= time() - cached[0] < CACHE_TTL:
            return cached[1]
        error = ""
        async with httpx.AsyncClient(timeout=5.0) as client:
            for attempt in range(3):
                try:
                    response = await client.get("https://geocoding-api.open-meteo.com/v1/search",
                                                params={"name": self.location, "count": 1,
                                                        "language": "en", "format": "json"})
                    response.raise_for_status()
                    results = response.json().get("results", [])
                    if not results:
                        raise ValueError(f"No city found for {self.location!r}")
                    city = results[0]
                    latitude, longitude = number(city["latitude"]), number(city["longitude"])
                    if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
                        raise ValueError("geocoding response has invalid coordinates")
                    label = city["name"]
                    if not isinstance(label, str) or not label.strip():
                        raise ValueError("geocoding response has no city name")
                    if city.get("country"):
                        label = f"{label}, {city['country']}"
                    response = await client.get("https://api.open-meteo.com/v1/forecast", params={
                        "latitude": latitude, "longitude": longitude,
                        "current": "temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m",
                        "temperature_unit": "celsius", "wind_speed_unit": "kmh",
                    })
                    response.raise_for_status()
                    current = response.json()["current"]
                    data = parse_weather(current, label)
                    self.write_cache(current, data)
                    return data
                except (httpx.HTTPError, ValueError, KeyError, TypeError, IndexError,
                        AttributeError, OverflowError) as exc:
                    error = f"{type(exc).__name__}: {exc}"
                    if attempt < 2:
                        await asyncio.sleep(0.5 * 2 ** attempt)
        if cached is not None:
            return replace(cached[1], stale=True, error=error)
        raise WeatherError(f"Weather unavailable for {self.location!r} after 3 attempts: {error}")
