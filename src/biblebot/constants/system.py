"""Constants for system paths, commands, and platform-specific operations."""

import shutil
from pathlib import Path

from .app import SERVICE_NAME

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

# System paths
SYSTEMD_USER_DIR = Path.home() / ".config" / "systemd" / "user"
LOCAL_SHARE_DIR = Path.home() / ".local" / "share"

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
