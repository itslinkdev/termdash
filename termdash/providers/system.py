"""Local system metrics; network rates use elapsed monotonic time."""

from pathlib import Path
from time import monotonic

import psutil

from termdash.data import IOData, SystemData, SystemSnapshot


GIB = 1024 ** 3


class SystemProvider:
    def __init__(self, disk_path: str | Path = Path.cwd().anchor) -> None:
        self.disk_path = str(disk_path)
        self.cpu: tuple[float, ...] = ()
        self.memory: tuple[float, ...] = ()
        self.previous_network: tuple[float, int, int] | None = None

    def fetch(self) -> SystemSnapshot:
        # A short measurement avoids psutil's meaningless first nonblocking CPU sample.
        cores = tuple(psutil.cpu_percent(interval=0.1, percpu=True))
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage(self.disk_path)
        network = psutil.net_io_counters()
        now = monotonic()
        download = upload = 0.0
        if network is not None:
            if self.previous_network is not None:
                previous_time, received, sent = self.previous_network
                elapsed = now - previous_time
                if elapsed > 0:
                    download = max(0, network.bytes_recv - received) / elapsed
                    upload = max(0, network.bytes_sent - sent) / elapsed
            self.previous_network = (now, network.bytes_recv, network.bytes_sent)
        else:
            self.previous_network = None

        self.cpu = (*self.cpu[-47:], sum(cores) / len(cores) if cores else 0.0)
        self.memory = (*self.memory[-47:], memory.percent)
        down_mbps, up_mbps = download * 8 / 1_000_000, upload * 8 / 1_000_000
        return SystemSnapshot(
            system=SystemData(self.cpu, self.memory, memory.total / GIB, cores),
            io=IOData(
                download_mbps=down_mbps,
                upload_mbps=up_mbps,
                capacity_mbps=max(1.0, down_mbps, up_mbps),
                disk_used_gib=disk.used / GIB,
                disk_total_gib=disk.total / GIB,
                download_bytes_per_second=download,
                upload_bytes_per_second=upload,
            ),
        )
