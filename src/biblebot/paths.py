"""Authoritative runtime paths for BibleBot.

``BIBLEBOT_HOME`` can place all BibleBot state under one portable directory.
Without it, paths follow the XDG Base Directory Specification:

- configuration (config.yaml, credentials.json) lives under the config home
  (``XDG_CONFIG_HOME`` or ``~/.config``);
- runtime state (the E2EE crypto store and logs) lives under the state home
  (``XDG_STATE_HOME`` or ``~/.local/state``), because crypto keys and logs are
  runtime state rather than user-edited configuration.

Legacy layouts that kept everything under the config home are migrated
automatically on first access of a state path.
"""

from __future__ import annotations

import logging
import os
import shutil
from pathlib import Path

APP_CONFIG_DIRNAME = "matrix-biblebot"
ENV_BIBLEBOT_HOME = "BIBLEBOT_HOME"

_CONFIG_FILENAME = "config.yaml"
_CREDENTIALS_FILENAME = "credentials.json"
_E2EE_STORE_DIRNAME = "e2ee-store"
_LOGS_DIRNAME = "logs"

logger = logging.getLogger(__name__)


def _xdg_dir(env_var: str, default: Path) -> Path:
    """Return an XDG base directory, honoring ``env_var`` when set."""
    configured = os.environ.get(env_var)
    if configured:
        return Path(configured).expanduser()
    return default


def get_home_dir() -> Path:
    """Return the portable runtime home, or the XDG config home fallback."""
    configured_home = os.environ.get(ENV_BIBLEBOT_HOME)
    if configured_home:
        return Path(configured_home).expanduser().absolute()
    return _xdg_dir("XDG_CONFIG_HOME", Path.home() / ".config") / APP_CONFIG_DIRNAME


def _state_home_dir() -> Path | None:
    """Return the state-home app directory, or None in BIBLEBOT_HOME mode."""
    if os.environ.get(ENV_BIBLEBOT_HOME):
        return None
    return _xdg_dir("XDG_STATE_HOME", Path.home() / ".local" / "state") / (
        APP_CONFIG_DIRNAME
    )


def get_config_dir() -> Path:
    """Return the directory containing BibleBot configuration."""
    return get_home_dir()


def get_config_path() -> Path:
    """Return the default configuration file path."""
    return get_config_dir() / _CONFIG_FILENAME


def get_credentials_path() -> Path:
    """Return the persisted Matrix credentials path."""
    return get_config_dir() / _CREDENTIALS_FILENAME


def _migrate_legacy_state(target: Path, legacy_name: str) -> None:
    """Move a legacy config-home state directory into the state home.

    Runs only in XDG mode when the target does not exist yet and the old
    config-home location does. The move is a real ``shutil.move`` so keys and
    logs are never left behind or duplicated; failures are logged and leave
    both paths untouched so startup can proceed against the legacy location on
    the next attempt.
    """
    if target is None or target.exists():
        return

    legacy = get_config_dir() / legacy_name
    if not legacy.exists():
        return

    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(legacy), str(target))
        logger.info(
            "Migrated %s from %s to %s",
            legacy_name,
            legacy.parent,
            target.parent,
        )
    except OSError as exc:  # pragma: no cover - filesystem failure path
        logger.warning("Could not migrate %s from %s: %s", legacy_name, legacy, exc)


def get_e2ee_store_dir() -> Path:
    """Return the Matrix E2EE store directory.

    Under ``BIBLEBOT_HOME`` this is ``<home>/e2ee-store``. In XDG mode it lives
    under the state home; a pre-existing store in the legacy config-home
    location is migrated here automatically.
    """
    state_dir = _state_home_dir()
    if state_dir is None:
        return get_config_dir() / _E2EE_STORE_DIRNAME

    target = state_dir / _E2EE_STORE_DIRNAME
    if not target.exists():
        _migrate_legacy_state(target, _E2EE_STORE_DIRNAME)
    # If migration failed, fall back to the legacy location for this run.
    if target.exists():
        return target
    legacy = get_config_dir() / _E2EE_STORE_DIRNAME
    return legacy if legacy.exists() else target


def get_log_dir() -> Path:
    """Return the application log directory.

    Under ``BIBLEBOT_HOME`` this is ``<home>/logs``. In XDG mode it lives under
    the state home; existing legacy logs are migrated automatically.
    """
    state_dir = _state_home_dir()
    if state_dir is None:
        return get_config_dir() / _LOGS_DIRNAME

    target = state_dir / _LOGS_DIRNAME
    if not target.exists():
        _migrate_legacy_state(target, _LOGS_DIRNAME)
    if target.exists():
        return target
    legacy = get_config_dir() / _LOGS_DIRNAME
    return legacy if legacy.exists() else target


# Backward-compatible alias: older callers treated "the home" as one directory.
def get_legacy_home_dir() -> Path:
    """Return the historical single-directory layout root (XDG config home).

    Retained for migration checks and tests; production code should use the
    specific accessors above.
    """
    return get_config_dir()
