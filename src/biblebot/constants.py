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
    # Book + chapter:verse[-–verse] [translation]
    re.compile(
        r"^([\w\s]+?)\s+(\d+:\d+(?:[-\u2013]\d+)?)\s*(kjv|esv)?$", re.IGNORECASE
    ),
    # Book + chapter [translation]
    re.compile(r"^([\w\s]+?)\s+(\d+)\s*(kjv|esv)?$", re.IGNORECASE),
]

# Required configuration keys
REQUIRED_CONFIG_KEYS = [
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

# CLI messages
MSG_CONFIG_EXISTS = "A config or .env file already exists at:"
MSG_DELETE_EXISTING = "If you want to regenerate them, delete the existing files first."
MSG_EDIT_FILES = "Please edit these files with your Matrix credentials and API keys."
MSG_GENERATED_CONFIG = "Generated sample config file at: {}"
MSG_GENERATED_ENV = "Generated sample .env file at: {}"
MSG_NO_CONFIG_PROMPT = (
    "No config found. Generate sample config and .env here now? [y/N]: "
)
SUCCESS_LOGIN_COMPLETE = "Login completed successfully"
SUCCESS_LOGOUT_COMPLETE = "Logout completed successfully"

# Bot error messages
ERROR_NO_CREDENTIALS_AND_TOKEN = (
    "No credentials.json and no MATRIX_ACCESS_TOKEN found."  # nosec B105
)
ERROR_AUTH_INSTRUCTIONS = (
    "Run 'biblebot auth login' (preferred) or set MATRIX_ACCESS_TOKEN in .env"
)

# Default values
DEFAULT_CONFIG_FILENAME_MAIN = "config.yaml"

# Auth prompts
PROMPT_HOMESERVER = "Matrix homeserver (e.g. https://matrix.org): "
PROMPT_USERNAME = "Matrix username (e.g. @user:server.com): "

# Environment variable names for system
ENV_USER = "USER"
ENV_USERNAME = "USERNAME"

# File names
SAMPLE_CONFIG_FILENAME = "sample_config.yaml"

# JSON/Dict keys for credentials
CRED_KEY_HOMESERVER = "homeserver"
CRED_KEY_USER_ID = "user_id"
CRED_KEY_ACCESS_TOKEN = "access_token"  # nosec B105
CRED_KEY_DEVICE_ID = "device_id"

# E2EE status keys
E2EE_KEY_AVAILABLE = "available"
E2EE_KEY_DEPENDENCIES_INSTALLED = "dependencies_installed"
E2EE_KEY_STORE_EXISTS = "store_exists"
E2EE_KEY_PLATFORM_SUPPORTED = "platform_supported"
E2EE_KEY_ERROR = "error"
E2EE_KEY_READY = "ready"

# Platform names
PLATFORM_WINDOWS = "Windows"

# File encoding
FILE_ENCODING_UTF8 = "utf-8"

# Auth messages and prompts
MSG_E2EE_DEPS_NOT_FOUND = "E2EE dependencies not found"
MSG_SERVER_DISCOVERY_FAILED = "Server discovery failed; using provided homeserver URL"
PROMPT_LOGIN_AGAIN = (
    "Do you want to log in again? This will create a new device session. [y/N]: "
)

# Response prefixes
RESPONSE_YES_PREFIX = "y"

# Discovery API attribute
DISCOVERY_ATTR_HOMESERVER_URL = "homeserver_url"

# CLI argument names and descriptions
CLI_DESCRIPTION = "BibleBot for Matrix - A Bible verse bot with E2EE support"
CLI_ARG_CONFIG = "--config"
CLI_ARG_LOG_LEVEL = "--log-level"
CLI_ARG_VERSION = "--version"
CLI_ARG_YES_SHORT = "-y"
CLI_ARG_YES_LONG = "--yes"
CLI_ARG_GENERATE_CONFIG = "--generate-config"
CLI_ARG_INSTALL_SERVICE = "--install-service"

# CLI help messages
CLI_HELP_CONFIG = "Path to config file (default: {})"
CLI_HELP_LOG_LEVEL = "Set logging level (default: {})"
CLI_HELP_YES = (
    "Automatically agree to prompts (useful in CI/non-interactive environments)"
)
CLI_HELP_GENERATE_CONFIG = "Generate sample configuration files"
CLI_HELP_INSTALL_SERVICE = "Install systemd user service"

# CLI actions
CLI_ACTION_STORE_TRUE = "store_true"
CLI_ACTION_VERSION = "version"

# Setup and installation constants
EXECUTABLE_NAME = "biblebot"
WARNING_EXECUTABLE_NOT_FOUND = "Warning: Could not find biblebot executable in PATH. Using current Python interpreter."
DIR_TOOLS = "tools"
DIR_SHARE = "share"
SERVICE_FILE_NAME = "biblebot.service"
FILE_MODE_READ = "r"

# Systemctl commands
SYSTEMCTL_ARG_USER = "--user"
SYSTEMCTL_ARG_IS_ENABLED = "is-enabled"

# Generic error messages for security (don't expose internal API errors)
ERROR_PASSAGE_NOT_FOUND = "Error: The requested passage could not be found. Please check the book, chapter, and verse."

# String literals and characters
CHAR_DOT = "."
CHAR_SLASH = "/"
CHAR_COMMA = ", "

# Translation identifiers
TRANSLATION_ESV = "esv"
TRANSLATION_KJV = "kjv"

# API parameter names
API_PARAM_Q = "q"
API_PARAM_INCLUDE_HEADINGS = "include-headings"
API_PARAM_INCLUDE_FOOTNOTES = "include-footnotes"
API_PARAM_INCLUDE_VERSE_NUMBERS = "include-verse-numbers"
API_PARAM_FALSE = "false"

# Logger names
LOGGER_NIO = "nio"

# Warning messages
WARN_MATRIX_ACCESS_TOKEN_NOT_SET = "MATRIX_ACCESS_TOKEN not set; will rely on saved credentials.json if available"  # nosec B105
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
SYSTEMCTL_PATH = "/usr/bin/systemctl"
LOCAL_BIN_DIR = ".local"
LOCAL_SHARE_DIR = ".local"
CONFIG_SUBDIR = ".config"
PIPX_VENV_PATH = "%h/.local/pipx/venvs/matrix-biblebot/bin"
DEFAULT_CONFIG_PATH = "%h/.config/matrix-biblebot/config.yaml"
WORKING_DIRECTORY = "%h/.config/matrix-biblebot"
EXEC_START_TEMPLATE = (
    "%h/.local/bin/biblebot --config %h/.config/matrix-biblebot/config.yaml"
)
PATH_ENVIRONMENT = "%h/.local/bin:%h/.local/pipx/venvs/matrix-biblebot/bin:/usr/local/bin:/usr/bin:/bin"

SYSTEMCTL_COMMANDS = {
    "start": "systemctl --user start biblebot.service",
    "stop": "systemctl --user stop biblebot.service",
    "restart": "systemctl --user restart biblebot.service",
    "status": "systemctl --user status biblebot.service",
    "enable": "systemctl --user enable biblebot.service",
    "disable": "systemctl --user disable biblebot.service",
}

# Additional auth constants
WARN_E2EE_DEPS_NOT_FOUND_LOGIN = (
    "E2EE dependencies not found, proceeding without encryption for login."
)
URL_PREFIX_HTTP = "http://"
URL_PREFIX_HTTPS = "https://"
PROMPT_PASSWORD = "Password: "  # nosec B105
STATUS_KEY_ERROR = E2EE_KEY_ERROR
STATUS_KEY_AVAILABLE = E2EE_KEY_AVAILABLE
STATUS_KEY_PLATFORM_SUPPORTED = E2EE_KEY_PLATFORM_SUPPORTED

# CLI Messages for interactive mode
MSG_CONFIG_EXISTS = "Configuration files already exist:"
MSG_DELETE_EXISTING = "Delete existing files to regenerate them."
MSG_GENERATED_CONFIG = "Generated config file: {}"
MSG_GENERATED_ENV = "Generated .env file: {}"
MSG_EDIT_FILES = (
    "Please edit these files with your Matrix server details and credentials."
)
SUCCESS_CONFIG_GENERATED = "Configuration files generated successfully!"
