"""Application-level constants."""

__all__ = [
    "APP_NAME",
    "APP_DISPLAY_NAME",
    "APP_DESCRIPTION",
    "LOGGER_NAME",
    "SERVICE_NAME",
    "SERVICE_DESCRIPTION",
    "SERVICE_RESTART_SEC",
    "EXECUTABLE_NAME",
    "DIR_TOOLS",
    "DIR_SHARE",
    "PLATFORM_WINDOWS",
    "FILE_ENCODING_UTF8",
    "CHAR_DOT",
    "CHAR_SLASH",
    "CHAR_COMMA",
    "FILE_MODE_READ",
]

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
