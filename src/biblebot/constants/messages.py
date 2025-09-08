"""Constants for message formatting, errors, and CLI output."""

from pathlib import Path

from .app import SERVICE_NAME

FALLBACK_MESSAGE_TOO_LONG = "[Message too long]"
TRUNCATION_INDICATOR = "..."  # Indicator for truncated text
REFERENCE_SEPARATOR_LEN = 3  # Length of " - " separator

# Message formatting
REACTION_OK = "✅"
MESSAGE_SUFFIX = " 🕊️✝️"

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
SUCCESS_CONFIG_GENERATED = "Configuration file generated successfully"

# CLI messages
MSG_CONFIG_EXISTS = "A config file already exists at:"
MSG_DELETE_EXISTING = "If you want to regenerate it, delete the existing file first."
MSG_EDIT_FILES = "Please edit the config file with your Matrix room IDs and then run 'biblebot auth login'."
MSG_GENERATED_CONFIG = "Generated sample config file at: {}"
MSG_NO_CONFIG_PROMPT = (
    "No config found. Generate a sample config file here now? [y/N]: "
)
SUCCESS_LOGIN_COMPLETE = "Login completed successfully"
SUCCESS_LOGOUT_COMPLETE = "Logout completed successfully"

# Bot error messages
ERROR_NO_CREDENTIALS_AND_TOKEN = (
    "No credentials.json and no MATRIX_ACCESS_TOKEN found."  # nosec B105  # noqa: S105
)
ERROR_AUTH_INSTRUCTIONS = (
    "Run 'biblebot auth login' (preferred) or set MATRIX_ACCESS_TOKEN in .env"
)

# Auth prompts
PROMPT_HOMESERVER = "Matrix homeserver (e.g. matrix.org): "
PROMPT_USERNAME = "Matrix username (just the username part, e.g. myusername): "

# Auth messages and prompts
MSG_E2EE_DEPS_NOT_FOUND = "E2EE dependencies not found"
MSG_SERVER_DISCOVERY_FAILED = "Server discovery failed; using provided homeserver URL"
PROMPT_LOGIN_AGAIN = (
    "Do you want to log in again? This will create a new device session. [y/N]: "
)

# Response prefixes
RESPONSE_YES_PREFIX = "y"

# CLI command names
CMD_CONFIG = "config"
CMD_AUTH = "auth"
CMD_SERVICE = "service"
CMD_GENERATE = "generate"
CMD_CHECK = "check"
CMD_LOGIN = "login"
CMD_LOGOUT = "logout"
CMD_STATUS = "status"
CMD_INSTALL = "install"

# CLI argument names and descriptions
CLI_DESCRIPTION = "BibleBot for Matrix - A Bible verse bot with E2EE support"
CLI_ARG_CONFIG = "--config"
CLI_ARG_LOG_LEVEL = "--log-level"
CLI_ARG_VERSION = "--version"
CLI_ARG_YES_SHORT = "-y"
CLI_ARG_YES_LONG = "--yes"

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

# Warning messages
WARNING_EXECUTABLE_NOT_FOUND = "Warning: Could not find biblebot executable in PATH. Using current Python interpreter."

# Systemctl commands
SYSTEMCTL_ARG_USER = "--user"
SYSTEMCTL_ARG_IS_ENABLED = "is-enabled"

# Generic error messages for security (don't expose internal API errors)
ERROR_PASSAGE_NOT_FOUND = "Error: The requested passage could not be found. Please check the book, chapter, and verse."

# Warning messages
WARN_MATRIX_ACCESS_TOKEN_NOT_SET = "MATRIX_ACCESS_TOKEN not set; will rely on saved credentials.json if available"  # nosec B105  # noqa: S105
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

# Systemd paths and commands
SYSTEMD_USER_DIR = Path.home() / ".config" / "systemd" / "user"
SYSTEMCTL_PATH = "/usr/bin/systemctl"
LOCAL_BIN_DIR = ".local"
LOCAL_SHARE_DIR = ".local"
CONFIG_SUBDIR = ".config"
PIPX_VENV_PATH = "%h/.local/pipx/venvs/matrix-biblebot/bin"
DEFAULT_CONFIG_PATH = "%h/.config/matrix-biblebot/config.yaml"
WORKING_DIRECTORY = "%h/.config/matrix-biblebot"
EXEC_START_TEMPLATE = f"%h/{LOCAL_BIN_DIR}/bin/biblebot --config {DEFAULT_CONFIG_PATH}"
PATH_ENVIRONMENT = "%h/.local/bin:%h/.local/pipx/venvs/matrix-biblebot/bin:/usr/local/bin:/usr/bin:/bin"

SYSTEMCTL_COMMANDS = {
    "start": f"{SYSTEMCTL_PATH} {SYSTEMCTL_ARG_USER} start {SERVICE_NAME}",
    "stop": f"{SYSTEMCTL_PATH} {SYSTEMCTL_ARG_USER} stop {SERVICE_NAME}",
    "restart": f"{SYSTEMCTL_PATH} {SYSTEMCTL_ARG_USER} restart {SERVICE_NAME}",
    "status": f"{SYSTEMCTL_PATH} {SYSTEMCTL_ARG_USER} status {SERVICE_NAME}",
    "enable": f"{SYSTEMCTL_PATH} {SYSTEMCTL_ARG_USER} enable {SERVICE_NAME}",
    "disable": f"{SYSTEMCTL_PATH} {SYSTEMCTL_ARG_USER} disable {SERVICE_NAME}",
}


# Additional auth constants
WARN_E2EE_DEPS_NOT_FOUND_LOGIN = (
    "E2EE dependencies not found, proceeding without encryption for login."
)
PROMPT_PASSWORD = "Password: "  # nosec B105  # noqa: S105
