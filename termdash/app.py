from datetime import datetime

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Grid, Horizontal, Vertical
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widgets import Static

from termdash.data import DemoProvider
from termdash.panels.git import GitPanel
from termdash.panels.io import IOPanel
from termdash.panels.system import SystemPanel
from termdash.panels.weather import WeatherPanel


class HelpScreen(ModalScreen):
    BINDINGS = [("escape", "dismiss", "Close"), ("?", "dismiss", "Close"),
                ("enter", "dismiss", "Close")]

    def compose(self) -> ComposeResult:
        with Vertical(id="help-box"):
            yield Static("termdash / keyboard help", classes="metric")
            yield Static("q   Quit dashboard")
            yield Static("t   Cycle dark / light / retro green")
            yield Static("r   Refresh simulated values")
            yield Static("?   Open or close this help")
            yield Static("Values refresh every 2 seconds.")
            yield Static("All readings are simulated.", classes="muted")
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

    def __init__(self, provider: DemoProvider | None = None) -> None:
        super().__init__()
        self.provider = provider if provider is not None else DemoProvider()

    def compose(self) -> ComposeResult:
        with Horizontal(id="header"):
            yield Static("›_ termdash", id="title")
            yield Static("DEMO / dark", id="mode", classes="muted")
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
        self.update_clock()
        self.action_refresh_data()
        self.set_interval(1, self.update_clock)
        self.set_interval(2, self.action_refresh_data)

    def update_clock(self) -> None:
        self.query_one("#clock", Static).update(datetime.now().astimezone().strftime("%H:%M:%S"))

    def action_refresh_data(self) -> None:
        snapshot = self.provider.snapshot()
        self.query_one(SystemPanel).data = snapshot.system
        self.query_one(WeatherPanel).data = snapshot.weather
        self.query_one(GitPanel).data = snapshot.git
        self.query_one(IOPanel).data = snapshot.io

    def action_cycle_theme(self) -> None:
        self.theme_name = self.THEMES[(self.THEMES.index(self.theme_name) + 1) % len(self.THEMES)]

    def watch_theme_name(self, name: str) -> None:
        for screen in self.screen_stack:
            screen.set_classes(name)
        if self.is_running:
            self.query_one("#mode", Static).update(f"DEMO / {name}")

    def action_help(self) -> None:
        self.push_screen(HelpScreen())
