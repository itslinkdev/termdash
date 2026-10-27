from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Static

from termdash.data import WeatherData


class WeatherPanel(Widget):
    data = reactive(WeatherData)
    BORDER_TITLE = "02 / Weather"

    def __init__(self, *, units: str = "metric", **kwargs) -> None:
        super().__init__(**kwargs)
        self.units = units

    def compose(self) -> ComposeResult:
        yield Static(id="weather-location", classes="muted")
        with Vertical(id="weather-summary"):
            yield Static("--", id="weather-temperature", classes="metric")
            yield Static("Waiting for weather", id="weather-condition", classes="metric")
            yield Static("Wind       --", id="weather-wind")
            yield Static("Humidity   --", id="weather-humidity")
        yield Static(f"Open-Meteo / {self.units}", id="weather-source", classes="muted")

    def on_mount(self) -> None:
        self.call_after_refresh(lambda: self.watch_data(self.data))

    def watch_data(self, data: WeatherData) -> None:
        if not self.is_mounted:
            return
        temperature, wind = "--", "--"
        if data.temperature_c is not None:
            temperature = (f"{data.temperature_c * 9 / 5 + 32:.1f} °F" if self.units == "imperial"
                           else f"{data.temperature_c:.1f} °C")
        if data.wind_kmh is not None:
            wind = (f"{data.wind_kmh / 1.609344:.0f} mph" if self.units == "imperial"
                    else f"{data.wind_kmh:.0f} km/h")
        humidity = "--" if data.humidity_percent is None else f"{data.humidity_percent}%"
        values = {
            "weather-location": data.location,
            "weather-temperature": temperature,
            "weather-condition": data.condition,
            "weather-wind": f"Wind       {wind}",
            "weather-humidity": f"Humidity   {humidity}",
            "weather-source": f"{data.source} / {self.units}",
        }
        for widget_id, value in values.items():
            self.query_one(f"#{widget_id}", Static).update(Text(value))
