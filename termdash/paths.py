"""Per-user paths without requiring another dependency."""

import os
from pathlib import Path
import sys


def user_config_dir() -> Path:
    if sys.platform == "win32":
        return Path(os.environ.get("APPDATA", Path.home() / "AppData/Roaming")) / "termdash"
    if sys.platform == "darwin":
        return Path.home() / "Library/Application Support/termdash"
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "termdash"


def user_cache_dir() -> Path:
    if sys.platform == "win32":
        return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local")) / "termdash"
    if sys.platform == "darwin":
        return Path.home() / "Library/Caches/termdash"
    return Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "termdash"
