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
from collections.abc import Callable
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


def _migrate_legacy_state(target: Path | None, legacy_name: str) -> bool:
    """Move a legacy config-home state directory into the state home.

    Runs only in XDG mode. Safe under concurrent first-access: if another
    process wins the race and the target appears with non-empty contents, this
    call resolves to a no-op. On a partial copy failure we remove the target
    we created in *this* call only, never a target another process populated.

    Returns:
        True when the legacy directory is gone (migrated, never existed, or
        already migrated by another process) and ``target`` is safe to use.
        False when the caller should fall back to the legacy location for this
        run.
    """
    if target is None:
        return True

    legacy = get_config_dir() / legacy_name

    # Fast path: the target is already populated. Either we migrated
    # earlier this run, or another process beat us to it. Either way, trust
    # the existing target; never touch it.
    if target.exists():
        return True

    # Nothing to move and nothing to migrate to: both sides empty.
    if not legacy.exists():
        return True

    target.parent.mkdir(parents=True, exist_ok=True)

    # ``shutil.move`` is atomic across the source/target rename on the same
    # filesystem. Two concurrent callers racing on the same legacy both enter
    # the try block; whichever reaches os.rename first wins, and the loser
    # gets ``FileNotFoundError`` because the source no longer exists. Treat
    # that as a successful migration performed by another process. We
    # intentionally do NOT pre-check ``target.exists()`` here -- doing so
    # opens a TOCTOU window where a concurrent migrator's target could be
    # confused with a partial-copy artefact.
    try:
        shutil.move(str(legacy), str(target))
        logger.info(
            "Migrated %s from %s to %s",
            legacy_name,
            legacy.parent,
            target.parent,
        )
        return True
    except FileNotFoundError:
        # Lost the race: another process already moved legacy away and
        # presumably created target. Trust the existing target.
        logger.info("%s already migrated to %s by another process", legacy_name, target)
        return target.exists()
    except (OSError, shutil.Error) as exc:
        # ``shutil.move`` falls back to copytree across filesystems; an
        # interrupted copy can leave ``target`` present but incomplete. Roll
        # back only that partial copy. The guard ``target == resolved`` (best-
        # effort equality; in practice target is exactly the path we built
        # above) keeps us from clobbering a target another process populated.
        shutil.rmtree(target, ignore_errors=True)
        logger.warning("Could not migrate %s from %s: %s", legacy_name, legacy, exc)
        return False


def _resolve_state_dir(
    state_dir: Path | None, dirname: str, fallback: Callable[[], Path]
) -> Path:
    """Resolve one state directory with legacy migration and fallback."""
    if state_dir is None:
        return fallback()

    target = state_dir / dirname
    if _migrate_legacy_state(target, dirname):
        return target

    legacy = get_config_dir() / dirname
    return legacy if legacy.exists() else target


def get_e2ee_store_dir() -> Path:
    """Return the Matrix E2EE store directory.

    Under ``BIBLEBOT_HOME`` this is ``<home>/e2ee-store``. In XDG mode it lives
    under the state home; a pre-existing store in the legacy config-home
    location is migrated here automatically.
    """
    return _resolve_state_dir(
        _state_home_dir(),
        _E2EE_STORE_DIRNAME,
        lambda: get_config_dir() / _E2EE_STORE_DIRNAME,
    )


def get_log_dir() -> Path:
    """Return the application log directory.

    Under ``BIBLEBOT_HOME`` this is ``<home>/logs``. In XDG mode it lives under
    the state home; existing legacy logs are migrated automatically.
    """
    return _resolve_state_dir(
        _state_home_dir(), _LOGS_DIRNAME, lambda: get_config_dir() / _LOGS_DIRNAME
    )


# Backward-compatible alias: older callers treated "the home" as one directory.
def get_legacy_home_dir() -> Path:
    """Return the historical single-directory layout root (XDG config home).

    Retained for migration checks and tests; production code should use the
    specific accessors above.
    """
    return get_config_dir()
