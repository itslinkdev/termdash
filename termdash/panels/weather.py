from textual.app import ComposeResult
from textual.containers import Vertical
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Static

from termdash.data import WeatherData


class WeatherPanel(Widget):
    data = reactive(WeatherData)
    BORDER_TITLE = "02 / Weather"

    def compose(self) -> ComposeResult:
        yield Static(id="weather-location", classes="muted")
        with Vertical(id="weather-summary"):
            yield Static(id="weather-temperature", classes="metric")
            yield Static(id="weather-condition", classes="metric")
            yield Static(id="weather-wind")
            yield Static(id="weather-humidity")
        yield Static("Simulated forecast / metric", classes="muted")

    def watch_data(self, data: WeatherData) -> None:
        if not self.is_mounted:
            return
        values = {
            "weather-location": data.location,
            "weather-temperature": f"{data.temperature_c:.1f} °C",
            "weather-condition": data.condition,
            "weather-wind": f"Wind       {data.wind_kmh:.0f} km/h",
            "weather-humidity": f"Humidity   {data.humidity_percent}%",
        }
        for widget_id, value in values.items():
            self.query_one(f"#{widget_id}", Static).update(value)
