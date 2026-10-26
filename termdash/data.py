"""Panel values and simulated snapshots; no machine or network access."""

from dataclasses import dataclass
from random import Random


@dataclass(frozen=True)
class SystemData:
    cpu: tuple[float, ...] = ()
    memory: tuple[float, ...] = ()
    memory_total_gib: float = 16.0


@dataclass(frozen=True)
class WeatherData:
    temperature_c: float = 19.0
    condition: str = "Partly cloudy"
    humidity_percent: int = 62
    wind_kmh: float = 11.0
    location: str = "Demo city"


@dataclass(frozen=True)
class GitData:
    branch: str = "demo/visual-layer"
    ahead: int = 2
    behind: int = 0
    files: tuple[tuple[str, str], ...] = ()
    additions: int = 0
    deletions: int = 0


@dataclass(frozen=True)
class IOData:
    download_mbps: float = 0.0
    upload_mbps: float = 0.0
    capacity_mbps: float = 100.0
    disk_used_gib: float = 148.0
    disk_total_gib: float = 256.0


@dataclass(frozen=True)
class Snapshot:
    system: SystemData
    weather: WeatherData
    git: GitData
    io: IOData


class DemoProvider:
    def __init__(self, seed: int | None = None) -> None:
        self.random = Random(seed)
        self.cpu = tuple(self.random.uniform(18, 48) for _ in range(48))
        self.memory = tuple(self.random.uniform(52, 55) for _ in range(48))
        self.temperature = 19.0
        self.download = 32.0
        self.upload = 8.0

    def _drift(self, value: float, step: float, low: float, high: float) -> float:
        return round(max(low, min(high, value + self.random.uniform(-step, step))), 1)

    def snapshot(self) -> Snapshot:
        self.cpu = (*self.cpu[1:], self._drift(self.cpu[-1], 9, 4, 96))
        self.memory = (*self.memory[1:], self._drift(self.memory[-1], 0.4, 30, 85))
        self.temperature = self._drift(self.temperature, 0.1, 17, 22)
        self.download = self._drift(self.download, 6, 0, 98)
        self.upload = self._drift(self.upload, 2, 0, 24)
        # Git changes slowly, so keep the demo files stable between samples.
        return Snapshot(
            system=SystemData(self.cpu, self.memory),
            weather=WeatherData(
                temperature_c=self.temperature,
                humidity_percent=self.random.randint(58, 65),
                wind_kmh=self.random.uniform(8, 14),
            ),
            git=GitData(
                files=(("M", "termdash/app.py"), ("A", "termdash/styles.tcss"),
                       ("?", "docs/preview.svg")),
                additions=84,
                deletions=12,
            ),
            io=IOData(self.download, self.upload),
        )
