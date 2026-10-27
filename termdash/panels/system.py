from textual.app import ComposeResult
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Sparkline, Static

from termdash.data import SystemData


class SystemPanel(Widget):
    data = reactive(SystemData)
    BORDER_TITLE = "01 / CPU + memory"

    def compose(self) -> ComposeResult:
        yield Static("CPU", id="cpu-label", classes="metric")
        yield Sparkline(id="cpu-spark")
        yield Static("Memory", id="memory-label", classes="metric")
        yield Sparkline(id="memory-spark")
        yield Static("Waiting for readings", id="system-scale", classes="muted")

    def watch_data(self, data: SystemData) -> None:
        if not self.is_mounted:
            return
        cpu = data.cpu[-1] if data.cpu else 0
        memory = data.memory[-1] if data.memory else 0
        used = memory / 100 * data.memory_total_gib
        self.query_one("#cpu-label", Static).update(f"CPU        {cpu:5.1f}%")
        self.query_one("#memory-label", Static).update(
            f"Memory     {memory:5.1f}% / {used:.1f} GiB"
        )
        self.query_one("#cpu-spark", Sparkline).data = data.cpu_per_core or data.cpu
        self.query_one("#memory-spark", Sparkline).data = data.memory
        self.query_one("#system-scale", Static).update(
            f"{len(data.cpu_per_core)} cores / memory history" if data.cpu_per_core
            else f"{len(data.cpu)} samples / auto scale"
        )
