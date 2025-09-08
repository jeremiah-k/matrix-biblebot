"""
Logging utilities for Matrix BibleBot.

Provides rich console logging with timestamps and optional file logging,
similar to mmrelay's logging approach.
"""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from rich.console import Console
from rich.logging import RichHandler

from biblebot.constants.app import APP_DISPLAY_NAME
from biblebot.constants.logging import (
    COMPONENT_LOGGERS as _COMPONENT_LOGGERS,
    DEFAULT_LOG_BACKUP_COUNT,
    DEFAULT_LOG_SIZE_MB,
    LOG_SIZE_BYTES_MULTIPLIER,
)

# Initialize Rich console
console = Console()


# Global config variable that will be set from main
config = None

# Global variable to store the log file path
log_file_path = None

# Track if component debug logging has been configured
_component_debug_configured = False


def configure_component_debug_logging():
    """
    Configure log levels for external component loggers based on config["logging"]["debug"].

    Reads per-component entries under `config["logging"]["debug"]` and applies one of:
    - falsy or missing: silence the component by setting its loggers to CRITICAL+1
    - boolean True: enable DEBUG for the component's loggers
    - string: interpret as a logging level name (case-insensitive); invalid names fall back to DEBUG

    This function mutates the levels of loggers listed in _COMPONENT_LOGGERS and runs only once per process; no-op if called again or if global `config` is None.
    """
    global _component_debug_configured, config

    # Only configure once
    if _component_debug_configured or config is None:
        return

    debug_config = config.get("logging", {}).get("debug", {})

    for component, loggers in _COMPONENT_LOGGERS.items():
        component_config = debug_config.get(component)

        if component_config:
            # Component debug is enabled - check if it's a boolean or a log level
            # Default to DEBUG for all cases
            log_level = logging.DEBUG

            if isinstance(component_config, str):
                # If it's a string, try to parse it as a log level
                try:
                    log_level = getattr(logging, component_config.upper())
                except AttributeError:
                    # Invalid log level string, the default DEBUG will be used
                    pass

            for logger_name in loggers:
                logging.getLogger(logger_name).setLevel(log_level)
        else:
            # Component debug is disabled - completely suppress external library logging
            # Use a level higher than CRITICAL to effectively disable all messages
            for logger_name in loggers:
                logging.getLogger(logger_name).setLevel(logging.CRITICAL + 1)

    _component_debug_configured = True


def get_log_dir():
    """
    Return the default directory for application logs.

    This is the application's config directory with "logs" appended (i.e., get_config_dir() / "logs").

    Returns:
        pathlib.Path: Path to the logs directory (may not exist).
    """
    from biblebot.auth import get_config_dir

    return get_config_dir() / "logs"


def get_logger(name):
    """
    Create and configure a logger with console output and optional file logging.

    The logger uses Rich for colorized console output with timestamps and supports
    optional rotating file logging.

    Parameters:
        name (str): The name of the logger to create.

    Returns:
        logging.Logger: The configured logger instance.
    """
    logger = logging.getLogger(name=name)

    # Default to INFO level
    log_level = logging.INFO
    color_enabled = True

    # Try to get log level and color settings from config
    global config
    if config is not None and "logging" in config:
        if "level" in config["logging"]:
            try:
                log_level = getattr(logging, config["logging"]["level"].upper())
            except AttributeError:
                log_level = logging.INFO
        if "color_enabled" in config["logging"]:
            color_enabled = config["logging"]["color_enabled"]

    logger.setLevel(log_level)
    logger.propagate = False

    # Check if logger already has handlers to avoid duplicates
    if logger.handlers:
        return logger

    # Add handler for console logging (with or without colors)
    if color_enabled:
        # Use Rich handler with colors and timestamps
        console_handler = RichHandler(
            rich_tracebacks=True,
            console=console,
            show_time=True,
            show_level=True,
            show_path=False,
            markup=True,
            log_time_format="%Y-%m-%d %H:%M:%S",
            omit_repeated_times=False,
        )
        console_handler.setFormatter(logging.Formatter("%(name)s: %(message)s"))
    else:
        # Use standard handler without colors but with timestamps
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(
            logging.Formatter(
                fmt="%(asctime)s %(levelname)s:%(name)s:%(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
    logger.addHandler(console_handler)

    # Check if file logging is enabled (default to True)
    log_to_file = True
    if config is not None:
        log_to_file = config.get("logging", {}).get("log_to_file", True)

    if log_to_file:
        # Determine log file path
        if config is not None and config.get("logging", {}).get("filename"):
            log_file = Path(config["logging"]["filename"])
        else:
            # Default to standard log directory
            log_file = get_log_dir() / "biblebot.log"

        # Create log directory if it doesn't exist
        log_file.parent.mkdir(parents=True, exist_ok=True)

        # Store the log file path for later use
        if name == APP_DISPLAY_NAME:
            global log_file_path
            log_file_path = str(log_file)

        # Create a file handler for logging
        try:
            # Set up size-based log rotation
            max_bytes = DEFAULT_LOG_SIZE_MB * LOG_SIZE_BYTES_MULTIPLIER
            backup_count = DEFAULT_LOG_BACKUP_COUNT

            if config is not None and "logging" in config:
                # Accept MB (int/float) and bytes (str ending with 'B')
                val = config["logging"].get("max_log_size", None)
                if isinstance(val, (int, float)):
                    max_bytes = int(val * LOG_SIZE_BYTES_MULTIPLIER)
                elif isinstance(val, str) and val.lower().endswith("b"):
                    max_bytes = int(val[:-1])
                elif val is not None:
                    max_bytes = val
                backup_count = config["logging"].get("backup_count", backup_count)

            file_handler = RotatingFileHandler(
                log_file, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8"
            )

            file_handler.setFormatter(
                logging.Formatter(
                    fmt="%(asctime)s %(levelname)s:%(name)s:%(message)s",
                    datefmt="%Y-%m-%d %H:%M:%S",
                )
            )
            logger.addHandler(file_handler)

        except (OSError, PermissionError) as e:
            # If file logging fails, continue with console only
            console.print(
                f"[yellow]Warning: Could not create log file at {log_file}: {e}[/yellow]"
            )
            # Log with logging.exception for diagnostics
            logging.getLogger(__name__).debug(
                "File logging setup failed", exc_info=True
            )

    return logger


def configure_logging(config_dict=None):
    """
    Set the module-wide logging configuration and apply per-component debug settings.

    This stores the provided configuration dict in the module-level `config` variable (or clears it when None)
    and then applies component-specific debug levels by calling `configure_component_debug_logging()`.

    Parameters:
        config_dict (dict | None): Global configuration mapping for logging. Expected keys are the same
            logging keys consumed elsewhere in this module (for example: `"level"`, `"color_enabled"`,
            `"log_to_file"`, `"filename"`, `"max_log_size"`, `"backup_count"`, and a `"debug"` mapping
            for per-component overrides). If None, the global configuration is cleared.

    Returns:
        None
    """
    global config
    config = config_dict

    # Configure component debug logging (nio, etc.)
    configure_component_debug_logging()
