"""Load and validate the user's TOML settings before starting the dashboard."""

from dataclasses import dataclass
from math import isfinite
from pathlib import Path
import tomllib

from termdash.paths import user_config_dir


DEFAULT_CONFIG = '''# Weather city (the first Open-Meteo geocoding match is used).
location = "London"
# Weather display: "metric" (C, km/h) or "imperial" (F, mph).
units = "metric"
# Initial palette: "dark", "light", or "retro". The t key cycles palettes.
theme = "dark"

[refresh]
# Positive, finite delays in seconds, measured after each fetch completes.
system = 2
git = 5
weather = 900
demo = 2

[git]
# Relative paths use the launch directory; ~ expands to your home directory.
# Use forward slashes or TOML literal strings for Windows paths.
repo = "."
'''


class ConfigError(ValueError):
    """A config file cannot be read, created, or validated."""


@dataclass(frozen=True)
class Config:
    location: str = "London"
    units: str = "metric"
    theme: str = "dark"
    system_interval: float = 2
    git_interval: float = 5
    weather_interval: float = 900
    demo_interval: float = 2
    repo: Path | None = None


def check_keys(table: dict, allowed: set[str], name: str) -> None:
    unknown = table.keys() - allowed
    if unknown:
        raise ValueError(f"unknown {name} setting(s): {', '.join(sorted(unknown))}")


def validate(data: dict) -> Config:
    check_keys(data, {"location", "units", "theme", "refresh", "git"}, "top-level")
    location = data.get("location", "London")
    if not isinstance(location, str) or len(location.strip()) < 2:
        raise ValueError("location must be a city name of at least two characters")
    units = data.get("units", "metric")
    if units not in ("metric", "imperial"):
        raise ValueError('units must be "metric" or "imperial"')
    theme = data.get("theme", "dark")
    if theme not in ("dark", "light", "retro"):
        raise ValueError('theme must be "dark", "light", or "retro"')

    refresh = data.get("refresh", {})
    git = data.get("git", {})
    if not isinstance(refresh, dict) or not isinstance(git, dict):
        raise ValueError("refresh and git must be TOML tables")
    defaults = {"system": 2, "git": 5, "weather": 900, "demo": 2}
    check_keys(refresh, defaults.keys(), "refresh")
    check_keys(git, {"repo"}, "git")
    intervals = {}
    for name, default in defaults.items():
        value = refresh.get(name, default)
        try:
            seconds = float(value) if type(value) in (int, float) else float("nan")
        except OverflowError:
            seconds = float("inf")
        if not isfinite(seconds) or seconds <= 0:
            raise ValueError(f"refresh.{name} must be positive, finite seconds")
        intervals[f"{name}_interval"] = seconds

    repo = git.get("repo", ".")
    if not isinstance(repo, str) or not repo.strip() or "\0" in repo:
        raise ValueError("git.repo must be a non-empty path string")
    return Config(location=location.strip(), units=units, theme=theme,
                  repo=Path(repo).expanduser().resolve(), **intervals)


def load_config(path: Path | None = None) -> Config:
    path = path if path is not None else user_config_dir() / "config.toml"
    try:
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            try:
                # Never overwrite a config another process has just created.
                with path.open("x", encoding="utf-8") as stream:
                    stream.write(DEFAULT_CONFIG)
            except FileExistsError:
                pass
        with path.open("rb") as stream:
            return validate(tomllib.load(stream))
    except (OSError, ValueError, RuntimeError) as exc:
        raise ConfigError(f"Config {path}: {exc}") from exc
