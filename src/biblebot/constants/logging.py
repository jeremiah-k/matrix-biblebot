"""Constants for logging configuration."""

__all__ = [
    "COMPONENT_LOGGERS",
    "DEFAULT_LOG_BACKUP_COUNT",
    "DEFAULT_LOG_LEVEL",
    "DEFAULT_LOG_SIZE_MB",
    "LOG_LEVELS",
    "LOG_LEVEL_STYLES",
    "LOG_SIZE_BYTES_MULTIPLIER",
    "LOGGER_NIO",
]

# Component loggers to suppress (similar to mmrelay)
COMPONENT_LOGGERS = {
    "matrix_nio": (
        "nio",
        "nio.client",
        "nio.http",
        "nio.crypto",
        "nio.responses",
        "nio.rooms",
    ),
    "aiohttp": ("aiohttp", "aiohttp.access"),
}

# Define custom log level styles
LOG_LEVEL_STYLES = {
    "DEBUG": "dim blue",
    "INFO": "green",
    "WARNING": "yellow",
    "ERROR": "bold red",
    "CRITICAL": "bold white on red",
}

# Default log settings
DEFAULT_LOG_SIZE_MB = 10
DEFAULT_LOG_BACKUP_COUNT = 5
LOG_SIZE_BYTES_MULTIPLIER = 1024 * 1024

# Log levels
LOG_LEVELS = ("critical", "error", "warning", "info", "debug")
DEFAULT_LOG_LEVEL = "info"

# Logger names
LOGGER_NIO = "nio"
