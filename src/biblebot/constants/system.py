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
PIPX_VENV_PATH = "%h/.local/pipx/venvs/matrix-biblebot/bin"
DEFAULT_CONFIG_PATH = "%h/.config/matrix-biblebot/config.yaml"
WORKING_DIRECTORY = "%h/.config/matrix-biblebot"
PATH_ENVIRONMENT = "%h/.local/bin:%h/.local/pipx/venvs/matrix-biblebot/bin:/usr/local/bin:/usr/bin:/bin"

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
