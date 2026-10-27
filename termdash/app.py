from datetime import datetime
from dataclasses import dataclass, field
from math import isfinite
from pathlib import Path
from threading import Event
from time import monotonic

from rich.text import Text
from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Grid, Horizontal, Vertical
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.message import Message
from textual.worker import Worker, get_current_worker
from textual.widgets import Static

from termdash.data import DemoProvider, GitData, Snapshot, SystemSnapshot
from termdash.providers import Provider
from termdash.providers.git import GitProvider
from termdash.providers.system import SystemProvider
from termdash.panels.git import GitPanel
from termdash.panels.io import IOPanel
from termdash.panels.system import SystemPanel
from termdash.panels.weather import WeatherPanel


@dataclass
class PollState:
    provider: Provider[Snapshot | SystemSnapshot | GitData]
    interval: float
    panels: tuple[str, ...]
    wake: Event = field(default_factory=Event)
    started_at: float = 0.0
    last_success: float | None = None
    error: str = ""
    worker: Worker | None = None


class ProviderResult(Message):
    def __init__(self, name: str, sample: Snapshot | SystemSnapshot | GitData | None = None,
                 error: str = "") -> None:
        super().__init__()
        self.name, self.sample, self.error = name, sample, error


class HelpScreen(ModalScreen):
    BINDINGS = [("escape", "dismiss", "Close"), ("?", "dismiss", "Close"),
                ("enter", "dismiss", "Close")]

    def compose(self) -> ComposeResult:
        with Vertical(id="help-box"):
            yield Static("termdash / keyboard help", classes="metric")
            yield Static("q   Quit dashboard")
            yield Static("t   Cycle dark / light / retro green")
            yield Static("r   Request provider refresh")
            yield Static("?   Open or close this help")
            yield Static("Providers refresh independently.")
            yield Static("Weather is always simulated.", classes="muted")
            yield Static("Esc or Enter to return", classes="muted")

    def on_mount(self) -> None:
        self.set_classes(self.app.theme_name)


class TermdashApp(App):
    CSS_PATH = "styles.tcss"
    TITLE = "termdash"
    ENABLE_COMMAND_PALETTE = False
    BINDINGS = [Binding("q", "quit", "Quit", priority=True),
                Binding("t", "cycle_theme", "Theme", priority=True),
                Binding("r", "refresh_data", "Refresh", priority=True),
                ("?", "help", "Help")]
    THEMES = ("dark", "light", "retro")
    theme_name = reactive("dark")

    def __init__(
        self, provider: Provider[Snapshot] | None = None, *,
        repo: str | Path | None = None,
        system_provider: Provider[SystemSnapshot] | None = None,
        git_provider: Provider[GitData] | None = None,
        system_interval: float = 2, git_interval: float = 5, demo_interval: float = 2,
    ) -> None:
        super().__init__()
        for interval in (system_interval, git_interval, demo_interval):
            if not isfinite(interval) or interval <= 0:
                raise ValueError("Provider intervals must be positive, finite seconds")
        self.demo_mode = provider is not None
        self.polls = {
            "demo": PollState(
                provider if provider is not None else DemoProvider(), demo_interval,
                ("system", "weather", "git", "io") if self.demo_mode else ("weather",),
            ),
        }
        if not self.demo_mode:
            self.polls["system"] = PollState(
                system_provider if system_provider is not None else SystemProvider(),
                system_interval, ("system", "io"),
            )
            self.polls["git"] = PollState(
                git_provider if git_provider is not None else GitProvider(repo),
                git_interval, ("git",),
            )
        self.mode_label: Static | None = None

    def compose(self) -> ComposeResult:
        with Horizontal(id="header"):
            yield Static("›_ termdash", id="title")
            yield Static(f"{'DEMO' if self.demo_mode else 'LIVE'} / dark",
                         id="mode", classes="muted")
            yield Static(id="clock")
        with Grid(id="panels"):
            yield SystemPanel(id="system", classes="panel")
            yield WeatherPanel(id="weather", classes="panel")
            yield GitPanel(id="git", classes="panel")
            yield IOPanel(id="io", classes="panel")
        with Horizontal(id="footer"):
            for hint in ("q quit", "t theme", "r refresh", "? help"):
                yield Static(hint, classes="key-hint")

    def on_mount(self) -> None:
        self.screen.set_classes(self.theme_name)
        # Keep widget references valid while help is on top and during shutdown.
        self.clock = self.query_one("#clock", Static)
        self.mode_label = self.query_one("#mode", Static)
        self.panels = {name: self.query_one(f"#{name}")
                       for name in ("system", "weather", "git", "io")}
        self.update_clock()
        for name, poll in self.polls.items():
            poll.started_at = monotonic()
            poll.worker = self.poll_provider(name, poll)
        self.update_badges()
        self.set_interval(1, self.update_clock)
        self.set_interval(0.2, self.update_badges)

    def on_unmount(self) -> None:
        for poll in self.polls.values():
            if poll.worker is not None:
                poll.worker.cancel()
            poll.wake.set()

    def update_clock(self) -> None:
        if self.clock.is_mounted:
            self.clock.update(datetime.now().astimezone().strftime("%H:%M:%S"))

    def action_refresh_data(self) -> None:
        for poll in self.polls.values():
            poll.wake.set()

    @work(thread=True, exit_on_error=False)
    def poll_provider(self, name: str, poll: PollState) -> None:
        worker = get_current_worker()
        while not worker.is_cancelled:
            try:
                result = ProviderResult(name, sample=poll.provider.fetch())
            except Exception as exc:
                result = ProviderResult(name, error=f"{type(exc).__name__}: {exc}")
            if worker.is_cancelled:
                return
            # post_message is thread-safe; only the handler below touches widgets.
            self.post_message(result)
            poll.wake.wait(poll.interval)
            poll.wake.clear()

    def on_provider_result(self, message: ProviderResult) -> None:
        # Results already queued at shutdown can outlive the panel's children.
        if not self.is_running:
            return
        poll = self.polls[message.name]
        poll.error = message.error
        if not message.error:
            sample = message.sample
            if isinstance(sample, Snapshot):
                self.panels["weather"].data = sample.weather
                if self.demo_mode:
                    self.panels["system"].data = sample.system
                    self.panels["git"].data = sample.git
                    self.panels["io"].data = sample.io
            elif isinstance(sample, SystemSnapshot):
                self.panels["system"].data = sample.system
                self.panels["io"].data = sample.io
            elif isinstance(sample, GitData):
                self.panels["git"].data = sample
            poll.last_success = monotonic()
        self.update_badges()

    def update_badges(self) -> None:
        now = monotonic()
        for name, poll in self.polls.items():
            age = now - (poll.last_success if poll.last_success is not None else poll.started_at)
            if poll.error:
                badge = "ERROR"
                detail = poll.error
            elif age > max(0.5, 2 * poll.interval):
                badge = "STALE"
                detail = "Waiting for fresh data; keeping the last successful sample."
            elif poll.last_success is None:
                badge, detail = "LOADING", "Waiting for the first sample."
            else:
                badge = "DEMO" if name == "demo" else "LIVE"
                detail = "Simulated data." if name == "demo" else "Local data."
            for panel_name in poll.panels:
                panel = self.panels[panel_name]
                panel.border_subtitle = Text(f"[{badge}]")
                panel.tooltip = Text(f"{detail}\nRefresh: {poll.interval:g}s after each fetch. "
                                     "Press r to retry sooner.")

    def action_cycle_theme(self) -> None:
        self.theme_name = self.THEMES[(self.THEMES.index(self.theme_name) + 1) % len(self.THEMES)]

    def watch_theme_name(self, name: str) -> None:
        for screen in self.screen_stack:
            screen.set_classes(name)
        if self.mode_label is not None:
            self.mode_label.update(f"{'DEMO' if self.demo_mode else 'LIVE'} / {name}")

    def action_help(self) -> None:
        self.push_screen(HelpScreen())
