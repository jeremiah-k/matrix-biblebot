"""Constants specific to the Matrix protocol and client."""

MIN_PRACTICAL_CHUNK_SIZE = 8  # Minimum reasonable chunk size for splitting
MAX_RATE_LIMIT_RETRIES = 3  # Maximum number of rate limit retries
DEFAULT_RETRY_AFTER_MS = 1000  # Default retry delay in milliseconds

# Placeholder room IDs to skip from sample config
_PLACEHOLDER_ROOM_IDS = frozenset({"#example:example.org", "!example:example.org"})

# Timeouts and limits (in milliseconds/seconds)
SYNC_TIMEOUT_MS = 30000
LOGIN_TIMEOUT_SEC = 30

# Device name for Matrix login
MATRIX_DEVICE_NAME = "biblebot"
