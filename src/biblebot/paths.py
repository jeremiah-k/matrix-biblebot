"""Authoritative runtime paths for BibleBot.

``BIBLEBOT_HOME`` can place BibleBot's configuration and state under one
portable directory. Without it, paths retain the existing XDG-compatible
``~/.config/matrix-biblebot`` layout.
"""

from __future__ import annotations

import os
from pathlib import Path

APP_CONFIG_DIRNAME = "matrix-biblebot"
ENV_BIBLEBOT_HOME = "BIBLEBOT_HOME"

_CONFIG_FILENAME = "config.yaml"
_CREDENTIALS_FILENAME = "credentials.json"
_E2EE_STORE_DIRNAME = "e2ee-store"


def get_home_dir() -> Path:
    """Return the current runtime home without caching environment state."""
    configured_home = os.environ.get(ENV_BIBLEBOT_HOME)
    if configured_home:
        return Path(configured_home).expanduser().absolute()

    xdg_config_home = os.environ.get("XDG_CONFIG_HOME")
    config_home = (
        Path(xdg_config_home).expanduser()
        if xdg_config_home
        else Path.home() / ".config"
    )
    return config_home / APP_CONFIG_DIRNAME


def get_config_dir() -> Path:
    """Return the directory containing BibleBot configuration and state."""
    return get_home_dir()


def get_config_path() -> Path:
    """Return the default configuration file path."""
    return get_home_dir() / _CONFIG_FILENAME


def get_credentials_path() -> Path:
    """Return the persisted Matrix credentials path."""
    return get_home_dir() / _CREDENTIALS_FILENAME


def get_e2ee_store_dir() -> Path:
    """Return the Matrix E2EE store directory."""
    return get_home_dir() / _E2EE_STORE_DIRNAME
