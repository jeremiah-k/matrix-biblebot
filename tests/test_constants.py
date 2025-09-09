"""Test constants for BibleBot test suite."""

# Test configuration values
TEST_HOMESERVER = "https://matrix.org"
TEST_USER_ID = "@testbot:matrix.org"
TEST_ACCESS_TOKEN = "test_access_token"  # noqa: S105
TEST_DEVICE_ID = "TEST_DEVICE"
TEST_ROOM_ID = "!room:matrix.org"
TEST_ROOM_IDS = ["!room1:matrix.org", "!room2:matrix.org"]
TEST_RESOLVED_ROOM_ID = "!resolved:matrix.org"
TEST_WRONG_ROOM_ID = "!wrong:matrix.org"
TEST_UNKNOWN_ROOM_ID = "!unknown:matrix.org"

# Test API responses
TEST_BIBLE_TEXT = "Test verse"
TEST_BIBLE_REFERENCE = "John 3:16"
TEST_ESV_RESPONSE = {
    "passages": ["For God so loved the world..."],
    "canonical": "John 3:16",
}
TEST_KJV_RESPONSE = {"text": "For God so loved the world...", "reference": "John 3:16"}

# Test message content
TEST_MESSAGE_BODY = "John 3:16"
TEST_MESSAGE_SENDER = "@user:matrix.org"
TEST_MESSAGE_TIMESTAMP = 1234567890000

# Test file paths
TEST_CONFIG_FILE = "test_config.yaml"
TEST_ENV_FILE = "test.env"
TEST_CREDENTIALS_FILE = "test_credentials.json"
TEST_TEMP_FILE = "/tmp/temp_file"  # noqa: S108

# Test error messages
TEST_ERROR_MESSAGE = "Test error"
TEST_API_ERROR = "API Error"
TEST_SERVER_ERROR = "Server error"
TEST_TIMEOUT_ERROR = "Timeout error"

# Test service template
TEST_SERVICE_TEMPLATE = """[Unit]
Description=Matrix Bible Bot Service
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=%h/.local/bin/biblebot --config %h/.config/matrix-biblebot/config.yaml
WorkingDirectory=%h/.config/matrix-biblebot
Restart=on-failure
RestartSec=10
Environment=PYTHONUNBUFFERED=1
Environment=PATH=%h/.local/bin:%h/.local/pipx/venvs/matrix-biblebot/bin:/usr/local/bin:/usr/bin:/bin

[Install]
WantedBy=default.target
"""

# Test configuration YAML
TEST_CONFIG_YAML = {
    "matrix_homeserver": TEST_HOMESERVER,
    "matrix_user": TEST_USER_ID,
    "matrix_room_ids": TEST_ROOM_IDS,
    "matrix": {"e2ee": {"enabled": False}},
}

# Test credentials
TEST_CREDENTIALS = {
    "homeserver": TEST_HOMESERVER,
    "user_id": TEST_USER_ID,
    "access_token": TEST_ACCESS_TOKEN,
    "device_id": TEST_DEVICE_ID,
}

# Test environment variables
TEST_ENV_VARS = {
    "MATRIX_ACCESS_TOKEN": TEST_ACCESS_TOKEN,
    "ESV_API_KEY": "test_esv_key",
}

# Mock response data
MOCK_RESPONSE_DATA = {"text": "Test verse", "reference": "Test 1:1"}

# Test book abbreviations (subset for testing)
TEST_BOOK_ABBREVIATIONS = {
    "gen": "Genesis",
    "exo": "Exodus",
    "matt": "Matthew",
    "john": "John",
    "rev": "Revelation",
}

# Test Bible references
TEST_BIBLE_REFERENCES = [
    "John 3:16",
    "Genesis 1:1",
    "Matthew 5:3-12",
    "Psalm 23",
    "Romans 8:28",
]

# Test invalid references
TEST_INVALID_REFERENCES = [
    "Invalid 99:99",
    "NotABook 1:1",
    "123:456",
]

# Performance test constants
PERFORMANCE_TEST_ITERATIONS = 50
PERFORMANCE_TEST_CONCURRENT_REQUESTS = 20
PERFORMANCE_TEST_TIMEOUT = 10.0
PERFORMANCE_TEST_MEMORY_LIMIT_MB = 50

# Mock user agents and headers
TEST_USER_AGENT = "BibleBot/1.0.0"
TEST_HEADERS = {
    "User-Agent": TEST_USER_AGENT,
    "Content-Type": "application/json",
}

# Test timeouts
TEST_SHORT_TIMEOUT = 0.1
TEST_MEDIUM_TIMEOUT = 1.0
TEST_LONG_TIMEOUT = 5.0

# Test file permissions
TEST_FILE_PERMISSIONS = 0o600
TEST_DIR_PERMISSIONS = 0o700

# Test platform identifiers
TEST_PLATFORM_LINUX = "linux"
TEST_PLATFORM_DARWIN = "darwin"
TEST_PLATFORM_WINDOWS = "Windows"

# Test log messages
TEST_LOG_INFO = "Test info message"
TEST_LOG_WARNING = "Test warning message"
TEST_LOG_ERROR = "Test error message"
TEST_LOG_DEBUG = "Test debug message"

# Test CLI arguments
TEST_CLI_ARGS = [
    "--config",
    "test_config.yaml",
    "--log-level",
    "debug",
    "--yes",
]

# Test systemctl commands
TEST_SYSTEMCTL_START = "systemctl --user start biblebot.service"
TEST_SYSTEMCTL_STOP = "systemctl --user stop biblebot.service"
TEST_SYSTEMCTL_STATUS = "systemctl --user status biblebot.service"

# Test discovery responses
TEST_DISCOVERY_RESPONSE_URL = "https://matrix.org"
TEST_DISCOVERY_ERROR = "Discovery error"

# Test E2EE status responses
TEST_E2EE_STATUS_AVAILABLE = {
    "available": True,
    "dependencies_installed": True,
    "store_exists": True,
    "platform_supported": True,
    "error": None,
    "ready": True,
}

TEST_E2EE_STATUS_UNAVAILABLE = {
    "available": False,
    "dependencies_installed": False,
    "store_exists": False,
    "platform_supported": False,
    "error": "E2EE is not supported on Windows",
    "ready": False,
}

# Test cache values
TEST_CACHE_KEY = "test_key"
TEST_CACHE_VALUE = "test_value"
TEST_CACHE_TTL = 3600

# Test regex patterns
TEST_VERSE_PATTERN = r"^([\w\s]+?)(\d+[:]\d+[-]?\d*)\s*(kjv|esv)?$"

# Test API endpoints
TEST_API_ENDPOINT = "/test/endpoint"
TEST_API_BASE_URL = "https://api.test.com"

# Test Matrix event types
TEST_MATRIX_EVENT_TYPE = "m.room.message"
TEST_MATRIX_MSGTYPE = "m.text"

# Test reaction emojis
TEST_REACTION_SUCCESS = "✅"
TEST_REACTION_ERROR = "❌"
TEST_REACTION_PROCESSING = "⏳"
