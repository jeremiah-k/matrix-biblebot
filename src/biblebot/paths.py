"""Runtime path helpers for BibleBot.

This module centralizes filesystem path resolution for runtime artifacts.
When ``BIBLEBOT_HOME`` is set, BibleBot uses that directory as its runtime root.
Otherwise it falls back to the legacy XDG-compatible location:
``~/.config/matrix-biblebot`` (or ``$XDG_CONFIG_HOME/matrix-biblebot``).
"""

from __future__ import annotations

import os
from pathlib import Path

ENV_BIBLEBOT_HOME = "BIBLEBOT_HOME"
APP_CONFIG_DIRNAME = "matrix-biblebot"
_DEFAULT_CONFIG_FILENAME = "config.yaml"
_CREDENTIALS_FILENAME = "credentials.json"
_E2EE_STORE_DIRNAME = "e2ee-store"

__all__ = [
    "ENV_BIBLEBOT_HOME",
    "get_config_dir",
    "get_config_path",
    "get_credentials_path",
    "get_e2ee_store_dir",
    "get_home_dir",
]


def _legacy_config_dir() -> Path:
    """Return the legacy per-user config directory."""
    config_home = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return config_home / APP_CONFIG_DIRNAME


def get_home_dir() -> Path:
    """Return BibleBot's runtime home directory."""
    configured_home = os.environ.get(ENV_BIBLEBOT_HOME)
    if configured_home:
        return Path(configured_home).expanduser()
    return _legacy_config_dir()


def get_config_dir() -> Path:
    """Return the directory containing runtime config and state files."""
    return get_home_dir()


def get_config_path(filename: str = _DEFAULT_CONFIG_FILENAME) -> Path:
    """Return the full path to a config file under the runtime home directory."""
    return get_config_dir() / filename


def get_credentials_path() -> Path:
    """Return the full path to the credentials file."""
    return get_config_dir() / _CREDENTIALS_FILENAME


def get_e2ee_store_dir() -> Path:
    """Return the full path to the E2EE store directory."""
    return get_config_dir() / _E2EE_STORE_DIRNAME
