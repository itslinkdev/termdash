"""Providers do blocking work and return immutable data, never widgets."""

from typing import Protocol, TypeVar

from termdash.data import GitData, Snapshot, SystemSnapshot


Sample = TypeVar("Sample", bound=Snapshot | SystemSnapshot | GitData, covariant=True)


class Provider(Protocol[Sample]):
    def fetch(self) -> Sample:
        """Read one sample; may raise an exception for the polling worker."""
        ...
