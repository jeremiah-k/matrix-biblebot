"""Application-level constants."""

__all__ = (
    "APP_DESCRIPTION",
    "APP_DISPLAY_NAME",
    "APP_NAME",
    "BIBLEBOT_HTTP_USER_AGENT",
    "CHAR_COMMA",
    "CHAR_DOT",
    "CHAR_SLASH",
    "DIR_SHARE",
    "DIR_TOOLS",
    "EXECUTABLE_NAME",
    "FILE_ENCODING_UTF8",
    "FILE_MODE_READ",
    "LOGGER_NAME",
    "PLATFORM_WINDOWS",
    "SERVICE_DESCRIPTION",
    "SERVICE_NAME",
    "SERVICE_RESTART_SEC",
)

# Application constants
APP_NAME = "matrix-biblebot"
APP_DISPLAY_NAME = "Matrix BibleBot"
APP_DESCRIPTION = "BibleBot for Matrix - A Bible verse bot with E2EE support"
LOGGER_NAME = "BibleBot"

# Service configuration
SERVICE_NAME = "biblebot.service"
SERVICE_DESCRIPTION = "Matrix Bible Bot Service"
SERVICE_RESTART_SEC = 10

# Setup and installation constants
EXECUTABLE_NAME = "biblebot"
DIR_TOOLS = "tools"
DIR_SHARE = "share"

# Platform names
PLATFORM_WINDOWS = "Windows"

# File encoding
FILE_ENCODING_UTF8 = "utf-8"

# String literals and characters
CHAR_DOT = "."
CHAR_SLASH = "/"
CHAR_COMMA = ", "

# File modes
FILE_MODE_READ = "r"

# HTTP User Agent
from importlib.metadata import PackageNotFoundError  # noqa: E402
from importlib.metadata import version as _pkg_version  # noqa: E402 - stdlib

try:
    _APP_VER = _pkg_version(APP_NAME)
except PackageNotFoundError:
    _APP_VER = "0.0.0-dev"

BIBLEBOT_HTTP_USER_AGENT = (
    f"{APP_NAME}/{_APP_VER} (+https://github.com/jeremiah-k/matrix-biblebot)"
)
