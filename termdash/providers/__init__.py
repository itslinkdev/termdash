"""Providers return immutable data, never widgets."""

from typing import Protocol, TypeVar

from termdash.data import GitData, Snapshot, SystemSnapshot, WeatherData


Sample = TypeVar("Sample", bound=Snapshot | SystemSnapshot | GitData | WeatherData, covariant=True)


class Provider(Protocol[Sample]):
    def fetch(self) -> Sample:
        """Read one sample; may raise an exception for the polling worker."""
        ...


class AsyncProvider(Protocol[Sample]):
    async def fetch(self) -> Sample:
        """Fetch without blocking the UI event loop."""
        ...
