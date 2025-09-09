"""Constants for system paths, commands, and platform-specific operations."""

import os
import shutil
from pathlib import Path

from biblebot.constants.app import SERVICE_NAME

__all__ = [
    "DEFAULT_CONFIG_PATH",
    "LOCAL_SHARE_DIR",
    "PATH_ENVIRONMENT",
    "PIPX_VENV_PATH",
    "SYSTEMCTL_ARG_IS_ENABLED",
    "SYSTEMCTL_ARG_USER",
    "SYSTEMCTL_COMMANDS",
    "SYSTEMCTL_PATH",
    "SYSTEMD_USER_DIR",
    "WORKING_DIRECTORY",
]

# XDG Base Directory Specification paths
_CONFIG_HOME = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
_DATA_HOME = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")

# System paths
SYSTEMD_USER_DIR = _CONFIG_HOME / "systemd" / "user"
LOCAL_SHARE_DIR = _DATA_HOME

# Systemctl configuration
SYSTEMCTL_PATH = shutil.which("systemctl")
SYSTEMCTL_ARG_USER = "--user"
SYSTEMCTL_ARG_IS_ENABLED = "is-enabled"

# Service paths and environment
# Filesystem-safe equivalents (expand %h to real home for Python use)
HOME = str(Path.home())
PIPX_VENV_PATH = "%h/.local/pipx/venvs/matrix-biblebot/bin"  # For systemd
PIPX_VENV_PATH_FS = f"{HOME}/.local/pipx/venvs/matrix-biblebot/bin"  # For Python
DEFAULT_CONFIG_PATH = "%h/.config/matrix-biblebot/config.yaml"  # For systemd
DEFAULT_CONFIG_PATH_FS = f"{HOME}/.config/matrix-biblebot/config.yaml"  # For Python
WORKING_DIRECTORY = "%h/.config/matrix-biblebot"  # For systemd
WORKING_DIRECTORY_FS = f"{HOME}/.config/matrix-biblebot"  # For Python
PATH_ENVIRONMENT = "%h/.local/bin:%h/.local/pipx/venvs/matrix-biblebot/bin:/usr/local/bin:/usr/bin:/bin"  # For systemd
PATH_ENVIRONMENT_FS = (
    f"{HOME}/.local/bin:{PIPX_VENV_PATH_FS}:/usr/local/bin:/usr/bin:/bin"  # For Python
)


def expand_percent_h(value: str) -> str:
    """
    Replace every occurrence of the systemd-style "%h" placeholder with the current user's home directory and return the resulting string.

    Parameters:
        value (str): Input string that may contain one or more "%h" placeholders.

    Returns:
        str: A new string with all "%h" occurrences replaced by the resolved HOME path.

    Notes:
        This performs a plain string replacement and does not process other systemd escape sequences.
    """
    return value.replace("%h", HOME)


# Systemctl commands
SYSTEMCTL_COMMANDS = (
    {}
    if SYSTEMCTL_PATH is None
    else {
        "start": [SYSTEMCTL_PATH, SYSTEMCTL_ARG_USER, "start", SERVICE_NAME],
        "stop": [SYSTEMCTL_PATH, SYSTEMCTL_ARG_USER, "stop", SERVICE_NAME],
        "restart": [SYSTEMCTL_PATH, SYSTEMCTL_ARG_USER, "restart", SERVICE_NAME],
        "status": [SYSTEMCTL_PATH, SYSTEMCTL_ARG_USER, "status", SERVICE_NAME],
        "enable": [SYSTEMCTL_PATH, SYSTEMCTL_ARG_USER, "enable", SERVICE_NAME],
        "disable": [SYSTEMCTL_PATH, SYSTEMCTL_ARG_USER, "disable", SERVICE_NAME],
    }
)
