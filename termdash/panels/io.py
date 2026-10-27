from textual.app import ComposeResult
from textual.containers import Vertical
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import ProgressBar, Static

from termdash.data import IOData


class IOPanel(Widget):
    data = reactive(IOData)
    BORDER_TITLE = "04 / Network + disk"

    def compose(self) -> ComposeResult:
        for name in ("download", "upload", "disk"):
            with Vertical(classes="io-metric"):
                yield Static(id=f"{name}-label")
                yield ProgressBar(total=100, show_eta=False, show_percentage=False,
                                  id=f"{name}-bar")
        yield Static(id="io-scale", classes="muted")

    def watch_data(self, data: IOData) -> None:
        if not self.is_mounted:
            return
        metrics = (
            ("download", f"Down   {data.download_mbps:5.1f} Mb/s", data.download_mbps,
             data.capacity_mbps),
            ("upload", f"Up     {data.upload_mbps:5.1f} Mb/s", data.upload_mbps,
             data.capacity_mbps),
            ("disk", f"Disk   {data.disk_used_gib:.0f} / {data.disk_total_gib:.0f} GiB",
             data.disk_used_gib, data.disk_total_gib),
        )
        if data.download_bytes_per_second is not None:
            capacity = data.capacity_mbps * 1_000_000 / 8
            metrics = (
                ("download", f"Down   {data.download_bytes_per_second:.0f} B/s",
                 data.download_bytes_per_second, capacity),
                ("upload", f"Up     {data.upload_bytes_per_second:.0f} B/s",
                 data.upload_bytes_per_second or 0.0, capacity),
                metrics[2],
            )
        for name, label, used, total in metrics:
            self.query_one(f"#{name}-label", Static).update(label)
            self.query_one(f"#{name}-bar", ProgressBar).update(total=total, progress=used)
        self.query_one("#io-scale", Static).update(
            f"Scale / {data.capacity_mbps * 1_000_000 / 8:.0f} B/s"
            if data.download_bytes_per_second is not None
            else f"Link scale / {data.capacity_mbps:.0f} Mb/s"
        )
