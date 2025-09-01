"""Constants for BibleBot application."""

import re
from pathlib import Path

# Application constants
APP_NAME = "matrix-biblebot"
APP_DESCRIPTION = "BibleBot for Matrix - A Bible verse bot with E2EE support"
LOGGER_NAME = "BibleBot"

# Configuration paths
CONFIG_DIR = Path.home() / ".config" / APP_NAME
CREDENTIALS_FILE = CONFIG_DIR / "credentials.json"
E2EE_STORE_DIR = CONFIG_DIR / "e2ee-store"
DEFAULT_CONFIG_FILENAME = "config.yaml"
DEFAULT_ENV_FILENAME = ".env"

# Service configuration
SERVICE_NAME = "biblebot.service"
SERVICE_DESCRIPTION = "Matrix Bible Bot Service"
SERVICE_RESTART_SEC = 10

# API URLs and endpoints
ESV_API_URL = "https://api.esv.org/v3/passage/text/"
KJV_API_URL_TEMPLATE = "https://bible-api.com/{passage}?translation=kjv"

# Bible translation constants
DEFAULT_TRANSLATION = "kjv"
SUPPORTED_TRANSLATIONS = ["kjv", "esv"]

# Message formatting
REACTION_OK = "✅"
MESSAGE_SUFFIX = " 🕊️✝️"

# Timeouts and limits (in milliseconds/seconds)
SYNC_TIMEOUT_MS = 30000
LOGIN_TIMEOUT_SEC = 30
API_REQUEST_TIMEOUT_SEC = 10

# Environment variable names
ENV_MATRIX_ACCESS_TOKEN = "MATRIX_ACCESS_TOKEN"  # nosec B105
ENV_ESV_API_KEY = "ESV_API_KEY"

# Configuration keys
CONFIG_MATRIX_HOMESERVER = "matrix_homeserver"
CONFIG_MATRIX_USER = "matrix_user"
CONFIG_MATRIX_ROOM_IDS = "matrix_room_ids"
CONFIG_MATRIX_E2EE = "matrix"

# File permissions
CONFIG_DIR_PERMISSIONS = 0o700
CREDENTIALS_FILE_PERMISSIONS = 0o600

# Regular expression patterns
REFERENCE_PATTERNS = [
    re.compile(r"^([\w\s]+?)(\d+[:]\d+[-]?\d*)\s*(kjv|esv)?$", re.IGNORECASE)
]

# Required configuration keys
REQUIRED_CONFIG_KEYS = [
    CONFIG_MATRIX_HOMESERVER,
    CONFIG_MATRIX_USER,
    CONFIG_MATRIX_ROOM_IDS,
]

# Log levels
LOG_LEVELS = ["error", "warning", "info", "debug"]
DEFAULT_LOG_LEVEL = "info"

# CLI command names
CMD_CONFIG = "config"
CMD_AUTH = "auth"
CMD_SERVICE = "service"
CMD_GENERATE = "generate"
CMD_VALIDATE = "validate"
CMD_LOGIN = "login"
CMD_LOGOUT = "logout"
CMD_STATUS = "status"
CMD_INSTALL = "install"

# Legacy CLI flags (deprecated)
LEGACY_AUTH_LOGIN = "--auth-login"
LEGACY_AUTH_LOGOUT = "--auth-logout"
LEGACY_GENERATE_CONFIG = "--generate-config"
LEGACY_INSTALL_SERVICE = "--install-service"

# Error messages
ERROR_CONFIG_NOT_FOUND = "Config file not found"
ERROR_MISSING_CONFIG_KEYS = "Missing required config keys"
ERROR_INVALID_YAML = "Invalid YAML in config file"
ERROR_LOGIN_FAILED = "Login failed"
ERROR_NO_CREDENTIALS = "No credentials found"
ERROR_E2EE_NOT_SUPPORTED = (
    "E2EE is not supported on Windows due to python-olm limitations"
)
ERROR_E2EE_DEPS_MISSING = "E2EE dependencies not installed"

# Success messages
SUCCESS_CONFIG_GENERATED = "Configuration files generated successfully"
SUCCESS_LOGIN_COMPLETE = "Login completed successfully"
SUCCESS_LOGOUT_COMPLETE = "Logout completed successfully"
SUCCESS_SERVICE_INSTALLED = "Service installed successfully"

# Info messages
INFO_LOADING_ENV = "Loaded environment variables from"
INFO_NO_ENV_FILE = "No .env file found; relying on process environment"
INFO_API_KEY_FOUND = "Found API key for {} translation"
INFO_NO_API_KEY = "No API key found for {} translation"
INFO_RESOLVED_ALIAS = "Resolved alias {} to room ID {}"

# Warning messages
WARN_COULD_NOT_RESOLVE_ALIAS = "Could not resolve alias"
WARN_CONFIG_DIR_PERMS = "Could not set config dir perms to 0700"
WARN_OLD_MESSAGE = "Ignoring old message"

# Device name for Matrix login
MATRIX_DEVICE_NAME = "biblebot"

# Cache settings
CACHE_MAX_SIZE = 100
CACHE_TTL_SECONDS = 3600  # 1 hour

# Systemd paths and commands
SYSTEMD_USER_DIR = Path.home() / ".config" / "systemd" / "user"
SYSTEMCTL_COMMANDS = {
    "start": "systemctl --user start biblebot.service",
    "stop": "systemctl --user stop biblebot.service",
    "restart": "systemctl --user restart biblebot.service",
    "status": "systemctl --user status biblebot.service",
    "enable": "systemctl --user enable biblebot.service",
    "disable": "systemctl --user disable biblebot.service",
}
