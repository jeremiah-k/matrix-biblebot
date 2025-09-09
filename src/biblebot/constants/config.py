"""Constants related to configuration files and keys."""

from biblebot.constants.system import _CONFIG_HOME

__all__ = [
    "CONFIG_DETECT_REFERENCES_ANYWHERE",
    "CONFIG_DIR",
    "CONFIG_DIR_PERMISSIONS",
    "CONFIG_KEY_MATRIX",
    "CONFIG_MATRIX_E2EE",
    "CONFIG_MATRIX_HOMESERVER",
    "CONFIG_MATRIX_ROOM_IDS",
    "CONFIG_MATRIX_SUBKEY_HOMESERVER",
    "CONFIG_MATRIX_SUBKEY_ROOM_IDS",
    "CONFIG_MATRIX_SUBKEY_USER",
    "CONFIG_MATRIX_USER",
    "CONFIG_PRESERVE_POETRY_FORMATTING",
    "CRED_KEY_ACCESS_TOKEN",
    "CRED_KEY_DEVICE_ID",
    "CRED_KEY_HOMESERVER",
    "CRED_KEY_USER_ID",
    "CREDENTIALS_FILE",
    "CREDENTIALS_FILE_PERMISSIONS",
    "DEFAULT_CONFIG_FILENAME",
    "DEFAULT_ENV_FILENAME",
    "E2EE_KEY_AVAILABLE",
    "E2EE_KEY_DEPENDENCIES_INSTALLED",
    "E2EE_KEY_ERROR",
    "E2EE_KEY_PLATFORM_SUPPORTED",
    "E2EE_KEY_READY",
    "E2EE_KEY_STORE_EXISTS",
    "E2EE_STORE_DIR",
    "ENV_ESV_API_KEY",
    "ENV_MATRIX_ACCESS_TOKEN",
    "ENV_USER",
    "ENV_USERNAME",
    "SAMPLE_CONFIG_FILENAME",
]

# Configuration paths
CONFIG_DIR = _CONFIG_HOME / "matrix-biblebot"
CREDENTIALS_FILE = CONFIG_DIR / "credentials.json"
E2EE_STORE_DIR = CONFIG_DIR / "e2ee-store"
DEFAULT_CONFIG_FILENAME = "config.yaml"
DEFAULT_ENV_FILENAME = (
    ".env"  # DEPRECATED: no longer generated; kept for env-loading fallback only
)

# Environment variable names
ENV_MATRIX_ACCESS_TOKEN = "MATRIX_ACCESS_TOKEN"  # nosec B105  # noqa: S105
ENV_ESV_API_KEY = "ESV_API_KEY"

# Configuration keys
CONFIG_KEY_MATRIX = "matrix"  # root section key

# Nested subkey constants for matrix section
CONFIG_MATRIX_SUBKEY_HOMESERVER = "homeserver"
CONFIG_MATRIX_SUBKEY_USER = "user"
CONFIG_MATRIX_SUBKEY_ROOM_IDS = "room_ids"
CONFIG_MATRIX_E2EE = "e2ee"

# DEPRECATED: Legacy flat keys - use nested structure instead
CONFIG_MATRIX_HOMESERVER = "matrix_homeserver"  # DEPRECATED: use CONFIG_KEY_MATRIX + CONFIG_MATRIX_SUBKEY_HOMESERVER
CONFIG_MATRIX_USER = (
    "matrix_user"  # DEPRECATED: use CONFIG_KEY_MATRIX + CONFIG_MATRIX_SUBKEY_USER
)
CONFIG_MATRIX_ROOM_IDS = "matrix_room_ids"  # DEPRECATED: use CONFIG_KEY_MATRIX + CONFIG_MATRIX_SUBKEY_ROOM_IDS

# Text formatting options
CONFIG_PRESERVE_POETRY_FORMATTING = "preserve_poetry_formatting"

# Message parsing options
CONFIG_DETECT_REFERENCES_ANYWHERE = "detect_references_anywhere"

# File permissions
CONFIG_DIR_PERMISSIONS = 0o700
CREDENTIALS_FILE_PERMISSIONS = 0o600


# Environment variable names for system
ENV_USER = "USER"
ENV_USERNAME = "USERNAME"

# File names
SAMPLE_CONFIG_FILENAME = "sample_config.yaml"

# JSON/Dict keys for credentials
CRED_KEY_HOMESERVER = "homeserver"
CRED_KEY_USER_ID = "user_id"
CRED_KEY_ACCESS_TOKEN = "access_token"  # nosec B105  # noqa: S105
CRED_KEY_DEVICE_ID = "device_id"

# E2EE status keys
E2EE_KEY_AVAILABLE = "available"
E2EE_KEY_DEPENDENCIES_INSTALLED = "dependencies_installed"
E2EE_KEY_STORE_EXISTS = "store_exists"
E2EE_KEY_PLATFORM_SUPPORTED = "platform_supported"
E2EE_KEY_ERROR = "error"
E2EE_KEY_READY = "ready"
