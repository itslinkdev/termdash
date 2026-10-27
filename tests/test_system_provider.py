from dataclasses import is_dataclass
from types import SimpleNamespace

import pytest

from termdash.data import DemoProvider
from termdash.providers.system import GIB, SystemProvider
from termdash.providers import system


class FakePsutil:
    network = SimpleNamespace(bytes_recv=1000, bytes_sent=200)

    def cpu_percent(self, *, interval, percpu):
        assert interval == 0.1
        assert percpu is True
        return [20.0, 60.0]

    def virtual_memory(self):
        return SimpleNamespace(percent=25.0, total=8 * GIB)

    def disk_usage(self, path):
        assert path == "test-disk"
        return SimpleNamespace(used=40 * GIB, total=100 * GIB)

    def net_io_counters(self):
        return self.network


@pytest.fixture
def metrics(monkeypatch):
    fake = FakePsutil()
    monkeypatch.setattr(system, "psutil", fake)
    ticks = iter(range(0, 1000, 2))
    monkeypatch.setattr(system, "monotonic", lambda: next(ticks))
    return fake, SystemProvider("test-disk")


def test_system_values_and_network_deltas(metrics):
    fake, provider = metrics
    first = provider.fetch()
    assert is_dataclass(first)
    assert first.system.cpu_per_core == (20.0, 60.0)
    assert first.system.cpu == (40.0,)
    assert first.system.memory == (25.0,)
    assert first.system.memory_total_gib == 8
    assert first.io.disk_used_gib == 40
    assert first.io.disk_total_gib == 100
    assert first.io.download_bytes_per_second == 0
    assert first.io.upload_bytes_per_second == 0

    fake.network = SimpleNamespace(bytes_recv=5000, bytes_sent=1200)
    second = provider.fetch()
    assert second.io.download_bytes_per_second == 2000
    assert second.io.upload_bytes_per_second == 500
    assert second.io.download_mbps == pytest.approx(0.016)


def test_reset_missing_counters_and_bounded_history(metrics):
    fake, provider = metrics
    provider.fetch()
    fake.network = SimpleNamespace(bytes_recv=0, bytes_sent=0)
    assert provider.fetch().io.download_bytes_per_second == 0
    fake.network = None
    assert provider.fetch().io.download_bytes_per_second == 0
    fake.network = SimpleNamespace(bytes_recv=10_000, bytes_sent=10_000)
    assert provider.fetch().io.download_bytes_per_second == 0
    for _ in range(60):
        sample = provider.fetch()
    assert len(sample.system.cpu) == len(sample.system.memory) == 48


def test_zero_elapsed_time(metrics, monkeypatch):
    fake, provider = metrics
    monkeypatch.setattr(system, "monotonic", lambda: 1.0)
    provider.fetch()
    fake.network = SimpleNamespace(bytes_recv=5000, bytes_sent=1200)
    assert provider.fetch().io.download_bytes_per_second == 0


def test_psutil_errors_propagate_to_worker(metrics, monkeypatch):
    fake, provider = metrics

    def denied(path):
        raise PermissionError("disk unavailable")

    monkeypatch.setattr(fake, "disk_usage", denied)
    with pytest.raises(PermissionError, match="disk unavailable"):
        provider.fetch()


def test_demo_fetch_keeps_snapshot_api():
    assert DemoProvider(seed=4).fetch() == DemoProvider(seed=4).snapshot()
