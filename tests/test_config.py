from pathlib import Path
import tomllib

import pytest

from termdash.config import ConfigError, DEFAULT_CONFIG, load_config, validate
from termdash import paths


def test_first_run_writes_commented_defaults_without_overwrite(tmp_path, monkeypatch):
    monkeypatch.setattr("termdash.config.user_config_dir", lambda: tmp_path / "settings")
    config = load_config()
    path = tmp_path / "settings/config.toml"
    assert path.read_text(encoding="utf-8") == DEFAULT_CONFIG
    assert "#" in DEFAULT_CONFIG
    assert config.location == "London"
    assert config.weather_interval == 900
    path.write_text('location = "Paris"\ntheme = "light"\nunits = "imperial"', encoding="utf-8")
    config = load_config()
    assert (config.location, config.theme, config.units) == ("Paris", "light", "imperial")
    assert path.read_text(encoding="utf-8").startswith('location = "Paris"')


def test_defaults_and_custom_values(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    config = validate(tomllib.loads(DEFAULT_CONFIG))
    assert config.repo == tmp_path
    assert config.system_interval == 2
    config = validate({"location": "  Rome  ", "git": {"repo": "~/project"},
                       "refresh": {"system": 0.25, "weather": 60}})
    assert config.location == "Rome"
    assert config.repo == Path.home() / "project"
    assert (config.system_interval, config.weather_interval) == (0.25, 60)


@pytest.mark.parametrize(("content", "error"), [
    ('theme = "blue"', "theme"),
    ('units = "kelvin"', "units"),
    ('location = " "', "location"),
    ('location = 42', "location"),
    ('refresh = 2', "tables"),
    ('git = "path"', "tables"),
    ('[refresh]\nsystem = 0', "refresh.system"),
    ('[refresh]\ngit = -1', "refresh.git"),
    ('[refresh]\nweather = nan', "refresh.weather"),
    ('[refresh]\ndemo = inf', "refresh.demo"),
    ('[refresh]\nweather = true', "refresh.weather"),
    ('[refresh]\ngit = "5"', "refresh.git"),
    ('[refresh]\ngit = ' + '9' * 400, "refresh.git"),
    ('[git]\nrepo = ""', "git.repo"),
    ('[git]\nrepo = 1', "git.repo"),
    ('[git]\nrepo = "a\\u0000b"', "git.repo"),
    ('[refresh]\nwetaher = 1', "wetaher"),
    ('[git]\npath = "."', "path"),
    ('typo = "value"', "typo"),
    ('location = [', "Invalid"),
])
def test_bad_config_reports_path_and_setting(tmp_path, content, error):
    path = tmp_path / "bad.toml"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(ConfigError) as caught:
        load_config(path)
    assert str(path) in str(caught.value)
    assert error.lower() in str(caught.value).lower()


def test_config_io_errors_are_clear(tmp_path):
    with pytest.raises(ConfigError, match="Config"):
        load_config(tmp_path)
    blocked = tmp_path / "file"
    blocked.write_text("not a directory")
    with pytest.raises(ConfigError, match="Config"):
        load_config(blocked / "config.toml")


@pytest.mark.parametrize(("platform", "config", "cache"), [
    ("linux", "/xdg-config/termdash", "/xdg-cache/termdash"),
    ("win32", "/roaming/termdash", "/local/termdash"),
    ("darwin", "~/Library/Application Support/termdash", "~/Library/Caches/termdash"),
])
def test_user_directories(monkeypatch, platform, config, cache):
    monkeypatch.setattr(paths.sys, "platform", platform)
    for name, value in {"APPDATA": "/roaming", "LOCALAPPDATA": "/local",
                        "XDG_CONFIG_HOME": "/xdg-config", "XDG_CACHE_HOME": "/xdg-cache"}.items():
        monkeypatch.setenv(name, value)
    assert paths.user_config_dir() == Path(config).expanduser()
    assert paths.user_cache_dir() == Path(cache).expanduser()
