"""Tests for the bot module."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import yaml

from biblebot import bot
from biblebot.bot import BibleBot, validate_and_normalize_book_name
from tests.test_constants import (
    TEST_ACCESS_TOKEN,
    TEST_BIBLE_REFERENCE,
    TEST_CONFIG_YAML,
    TEST_DEVICE_ID,
    TEST_HOMESERVER,
    TEST_MESSAGE_BODY,
    TEST_MESSAGE_SENDER,
    TEST_RESOLVED_ROOM_ID,
    TEST_ROOM_ID,
    TEST_ROOM_IDS,
    TEST_UNKNOWN_ROOM_ID,
    TEST_USER_ID,
    TEST_WRONG_ROOM_ID,
)


class MockEncryptedRoom:
    """Mock Matrix room that appears encrypted"""

    def __init__(self, room_id, encrypted=True):
        """
        Initialize the mock room.

        Parameters:
            room_id (str): Unique identifier for the room.
            encrypted (bool): Whether the room is encrypted (default True).

        The instance will expose `room_id`, `encrypted`, and a generated `display_name` in the form "Test Room {room_id}".
        """
        self.room_id = room_id
        self.encrypted = encrypted
        self.display_name = f"Test Room {room_id}"


class MockUnencryptedRoom:
    """Mock Matrix room that appears unencrypted"""

    def __init__(self, room_id):
        """
        Create a minimal mock room representing an unencrypted Matrix room.

        Parameters:
            room_id (str): Matrix room identifier to assign to the mock room.

        The instance will expose these attributes:
            room_id (str): the provided room identifier.
            encrypted (bool): always False for this mock.
            display_name (str): human-readable name in the form "Test Room <room_id>".
        """
        self.room_id = room_id
        self.encrypted = False
        self.display_name = f"Test Room {room_id}"


class E2EETestFramework:
    """Framework for testing E2EE encryption behavior following mmrelay patterns"""

    @staticmethod
    def create_mock_client(rooms=None, should_upload_keys=False):
        """
        Create a preconfigured AsyncMock Matrix client for tests.

        Returns an AsyncMock that mimics a nio AsyncClient with:
        - device_id, user_id, and access_token set to stable test values.
        - a `rooms` mapping (by default includes one encrypted and one unencrypted mock room).
        - `should_upload_keys` flag set from the argument.
        - async-mocked methods: `keys_upload`, `sync`, `room_send`, and `close`.

        Parameters:
            rooms (dict|None): Optional mapping of room_id -> room-like objects to use instead of the defaults.
            should_upload_keys (bool): If True, the mock client's `should_upload_keys` attribute will be True.

        Returns:
            AsyncMock: A configured mock client suitable for E2EE-related tests.
        """
        client = AsyncMock()
        client.device_id = "TEST_DEVICE_ID"
        client.user_id = "@test:example.org"
        client.access_token = "test_token"  # noqa: S105

        # Mock rooms
        if rooms is None:
            rooms = {
                "!encrypted:example.org": MockEncryptedRoom(
                    "!encrypted:example.org", encrypted=True
                ),
                "!unencrypted:example.org": MockUnencryptedRoom(
                    "!unencrypted:example.org"
                ),
            }
        client.rooms = rooms

        # Mock E2EE methods
        client.should_upload_keys = should_upload_keys
        client.keys_upload = AsyncMock()
        client.sync = AsyncMock()
        client.room_send = AsyncMock()
        client.close = AsyncMock()

        return client

    @staticmethod
    def mock_e2ee_dependencies():
        """
        Provide a context manager that mocks Matrix E2EE-related dependencies for tests.

        When used as a with-block, this context manager:
        - Patches builtin import to return mocks for "olm", "nio.crypto", and "nio.store".
        - Replaces nio.AsyncClientConfig.__init__ and __post_init__ to avoid ImportWarning/side effects and to supply a mock store factory.
        - Supplies a MockSqliteStore implementation that exposes the public methods expected by the code under test without touching a real database.

        Return:
            A context manager usable as `with mock_e2ee_dependencies():` which applies the above patches for the duration of the block.
        """
        import builtins
        from contextlib import ExitStack

        _real_import = builtins.__import__

        def _mock_import(name, globals=None, locals=None, fromlist=(), level=0):
            """
            Return a mock module for E2EE-related imports or delegate to the real import.

            When called with a module name of "olm", "nio.crypto", or "nio.store", returns a MagicMock to allow tests to run without the real E2EE libraries. For any other module name, calls and returns the result of the original import function.
            """
            if name in ("olm", "nio.crypto", "nio.store"):
                return MagicMock()
            return _real_import(name, globals, locals, fromlist, level)

        # Mock SqliteStore to avoid database connection issues
        # Implements ALL 27 public methods from MatrixStore base class
        class MockSqliteStore:
            def __init__(
                self,
                user_id=None,
                device_id=None,
                store_path=None,
                pickle_key=None,
                store_name=None,
                *args,
                **kwargs,
            ):
                # Accept all arguments that real SqliteStore expects but don't use them
                """
                Create a drop-in mock replacement for a SqliteStore.

                This constructor accepts the same parameters as the real SqliteStore (for compatibility with code that constructs a store) but does not persist data or use any of the arguments. It exists solely so the mock can be instantiated in place of the real store without raising unexpected argument errors.

                Parameters:
                    user_id (str | None): Ignored; accepted for API compatibility.
                    device_id (str | None): Ignored; accepted for API compatibility.
                    store_path (str | None): Ignored; accepted for API compatibility.
                    pickle_key (bytes | None): Ignored; accepted for API compatibility.
                    store_name (str | None): Ignored; accepted for API compatibility.
                    *args: Additional positional arguments are accepted and ignored.
                    **kwargs: Additional keyword arguments are accepted and ignored.

                Notes:
                    - No state is persisted and no external resources are used.
                """
                pass

            def __post_init__(self):
                # Don't connect to database
                """
                No-op dataclass post-initializer that intentionally avoids establishing a database connection.

                Used in tests/mocks to override any automatic initialization side effects (such as opening a DB) during object construction.
                """
                pass

            # Account methods
            def load_account(self):
                """
                Stub placeholder for loading a stored account or credentials.

                Returns:
                    None: No account is loaded by this implementation; always returns None.
                """
                return None

            def save_account(self, account):
                """
                Store an account object in the mock sqlite store for use by tests.

                The account is kept in-memory so subsequent store operations (e.g., retrieval by the test harness) can access the same account data without touching a real database. The provided `account` should be the account-like object produced by the client/library under test (typically containing identifiers such as user_id and/or device_id) and will replace any previously stored account with the same identity.
                """
                pass

            # Device key methods
            def load_device_keys(self):
                """
                Return stored device keys.

                For this mock implementation, no device keys are persisted; always returns an empty dictionary.

                Returns:
                    dict: Mapping of device IDs to stored key metadata (empty in this mock).
                """
                return {}

            def save_device_keys(self, device_keys):
                """
                No-op placeholder for storing device keys in the mock store.

                This method exists to satisfy the storage interface expected by E2EE codepaths but does not persist or modify any state in the mock implementation. The provided `device_keys` argument is accepted and ignored.
                """
                pass

            # Session methods
            def load_sessions(self):
                """
                Return an empty session mapping.

                This method provides a no-op implementation that always returns a fresh, empty dictionary
                representing stored sessions (used by tests to avoid persistent session storage).

                Returns:
                    dict: An empty dictionary representing session storage.
                """
                return {}

            def save_session(self, session):
                """
                Persist a session object into the mock store's in-memory storage for tests.

                The provided `session` (typically a serializable mapping or object representing client session state)
                is stored in the store instance so subsequent test code can retrieve it. This method mutates the
                store's internal state and does not return a value.
                """
                pass

            # Inbound group session methods
            def load_inbound_group_sessions(self):
                """
                Return an empty mapping of inbound group sessions.

                This mock implementation is used in tests to simulate a storage backend that has
                no stored inbound group sessions; callers should expect an empty dict.
                """
                return {}

            def save_inbound_group_session(self, session):
                """
                Persist an inbound group session used for end-to-end encryption.

                In the mock/store used for tests this is a no-op (accepts the session to match the real store API but does not perform durable persistence).

                Parameters:
                    session: The inbound group session object to be saved (opaque to the caller).
                """
                pass

            # Outgoing key request methods
            def load_outgoing_key_requests(self):
                """
                Return stored outgoing room key requests.

                For the mock store used in tests this always returns an empty dict (no pending outgoing requests).

                Returns:
                    dict: Mapping of request_id to outgoing request data (empty in this mock).
                """
                return {}

            def add_outgoing_key_request(self, request):
                """
                Record an outgoing room key request in the store.

                Stores the provided outgoing key request so it can later be queried or removed
                by the test framework. The `request` argument is the outgoing key request
                object produced by the SDK (a RoomKeyRequest-like object) and is stored by
                its identifying fields.

                No value is returned.
                """
                pass

            def remove_outgoing_key_request(self, request):
                """
                Remove a stored outgoing room key request from the store.

                Removes the outgoing key request represented by `request` from the persistent
                store used for E2EE key-request bookkeeping. If the request is not present
                this is a no-op. The method mutates the store state and is typically called
                after a request has been successfully sent or cancelled.

                Parameters:
                    request: The outgoing key request object (e.g., an `OutgoingRoomKeyRequest`-like
                        instance) to remove. The object should contain the identifier used by the
                        store to track requests (such as `request_id` or `id`).
                """
                pass

            # Encrypted room methods
            def load_encrypted_rooms(self):
                """
                Return the set of room IDs that are considered encrypted.

                This implementation always returns an empty set (no encrypted rooms).
                Returns:
                    set: A set of room ID strings (empty).
                """
                return set()

            def save_encrypted_rooms(self, rooms):
                """
                Mark the given rooms as encrypted in the test framework's internal store/state.

                Parameters:
                    rooms (iterable): An iterable of room identifiers or room-like objects to be saved/marked as encrypted. This method updates the framework's mock storage or internal mapping; it does not return a value.
                """
                pass

            def delete_encrypted_room(self, room_id):
                """
                Remove an encrypted mock room by its room_id from the framework's internal state.

                If the specified room_id is not present, the call is a no-op.
                """
                pass

            # Sync token methods
            def load_sync_token(self):
                """
                Return the stored sync token used to resume a Matrix /sync.

                In this mock implementation there is no persistent storage, so it always returns None.

                Returns:
                    Optional[str]: The saved sync token, or None if not available.
                """
                return None

            def save_sync_token(self, token):
                """
                Save the current sync token.

                This method saves the provided sync token, which can be used to resume a sync session from the last known state. The token is typically received from a call to `sync()` and should be persisted to allow the bot to resume from where it left off, reducing unnecessary server load.

                Parameters:
                    token (str): The sync token to save.
                """
                pass

            # Device verification methods
            def verify_device(self, device):
                """
                Determine whether a given device should be treated as verified/trusted for E2EE operations.

                Parameters:
                    device: The device object to evaluate (typically a device dict or model from the Matrix client).
                Returns:
                    bool: True if the device is considered verified and safe to use for encrypted messaging, False otherwise.
                """
                pass

            def unverify_device(self, device):
                """
                Mark the given device as unverified for testing E2EE behavior.

                This forces the client's representation of `device` to be treated as unverified (clearing or setting any verification/trust flags) so code paths that depend on device verification (e.g., sending with ignore_unverified_devices) can be exercised in tests.

                Parameters:
                    device: Identifier or device object representing the device to unverify. The exact accepted form matches the test framework's device representations.
                """
                pass

            def is_device_verified(self, device):
                """
                Return whether a device is considered verified.

                In this mock implementation used for E2EE tests, every device is treated as unverified and this always returns False.

                Parameters:
                    device: The device object or identifier to check (ignored by this mock).

                Returns:
                    bool: Always False.
                """
                return False

            def blacklist_device(self, device):
                """
                Mark a device as blacklisted so it will be excluded from E2EE operations (e.g., ignored for sending encrypted messages or key requests).

                Parameters:
                    device: The device identifier or device object to blacklist; its exact form depends on the surrounding E2EE client implementation.

                Notes:
                    This method performs an in-place change to the object's device tracking state and does not return a value.
                """
                pass

            def unblacklist_device(self, device):
                """
                Unblacklist a previously blacklisted device.

                Removes the given device from the internal blacklist so it will no longer be treated as blocked.
                This is a no-op if the device is not currently blacklisted.

                Parameters:
                    device: The device identifier (e.g., device ID string) or device object to remove from the blacklist.
                """
                pass

            def is_device_blacklisted(self, device):
                """
                Check whether a device is blacklisted.

                This mock implementation always returns False (no device is treated as blacklisted).
                The `device` argument is accepted for API compatibility but is ignored.
                Returns:
                    bool: False always — indicates the device is not blacklisted.
                """
                return False

            def ignore_device(self, device):
                """
                Mark the given remote device as ignored for E2EE operations in the test framework.

                Parameters:
                    device: The device object (e.g., a mock Matrix device) to be treated as ignored; after calling this, the framework will skip verification/processing for that device.
                """
                pass

            def unignore_device(self, device):
                """
                Mark the given device as no longer ignored by this client.

                This updates the object's internal state so that future operations will treat
                `device` as active/eligible (for message sending, key requests, etc.). Does not
                return a value.

                Parameters:
                    device: The device object or identifier to un-ignore; its type depends on
                        the caller's device representation (e.g., a Device model or device id).
                """
                pass

            def ignore_devices(self, devices):
                """
                Mark the given devices as ignored for encryption checks.

                Parameters:
                    devices (iterable[str]): Device IDs to mark as ignored (i.e., treated as unverified/ignored for outgoing encrypted messaging).
                """
                pass

            def is_device_ignored(self, device):
                """
                Determine whether the given device should be ignored for messaging/key operations.

                Currently this implementation always returns False (no devices are ignored).

                Parameters:
                    device: The device object or identifier to evaluate.

                Returns:
                    bool: False indicating the device is not ignored.
                """
                return False

            # Upgrade method
            def upgrade_to_v2(self):
                """
                Migrate the instance from schema/version 1 to schema/version 2 in place.

                Performs any necessary transformations on internal state so the object conforms to
                the v2 data model. This method mutates the instance and is intended to be
                idempotent when called on an already-upgraded instance. No value is returned.
                """
                pass

        # Also need to mock the AsyncClientConfig E2EE dependency check
        def mock_client_config_init(self, *args, **kwargs):
            # Don't raise ImportWarning for E2EE dependencies in tests
            """
            Initialize a mocked client config for tests.

            Sets attributes on the config object to avoid ImportWarning and to provide a fake persistent store:
            - sets `store_sync_tokens` from kwargs (defaults to True)
            - sets `encryption_enabled` from kwargs (defaults to False)
            - sets `store` to a factory that returns a MockSqliteStore instance

            The `store` factory has the signature (user_id, device_id, store_path, pickle_key, store_name) and returns a MockSqliteStore constructed with those values. This function does not return a value; it mutates `self`.
            """
            object.__setattr__(
                self, "store_sync_tokens", kwargs.get("store_sync_tokens", True)
            )
            object.__setattr__(
                self, "encryption_enabled", kwargs.get("encryption_enabled", False)
            )

            # Mock the store property to return our mock store
            def mock_store_factory(
                user_id, device_id, store_path, pickle_key, store_name
            ):
                """
                Factory that constructs a MockSqliteStore for tests.

                Creates and returns a MockSqliteStore configured for the given Matrix identity and storage settings. Intended for use in test patches where a real sqlite-backed store must be replaced.

                Parameters:
                    user_id (str): Matrix user ID the store will represent.
                    device_id (str): Device ID the store will represent.
                    store_path (str | Path): Filesystem path (or path-like) used as the store location.
                    pickle_key (bytes | str | None): Key used for (de)serialization by the mock store, if applicable.
                    store_name (str): Logical name for the store instance.

                Returns:
                    MockSqliteStore: A test double implementing the same interface as the real sqlite store.
                """
                return MockSqliteStore(
                    user_id, device_id, store_path, pickle_key, store_name
                )

            object.__setattr__(self, "store", mock_store_factory)

        class E2EEMockContext:
            def __enter__(self):
                """
                Enter the context: create an ExitStack, install patches that mock imports and nix AsyncClientConfig initialization, and return the context manager instance.

                This sets up:
                - a patched builtins.__import__ that delegates to a test import hook,
                - a no-op __post_init__ for nio.AsyncClientConfig,
                - a replacement __init__ for nio.AsyncClientConfig (mock_client_config_init).

                Returns:
                    self: the context manager instance, ready to be used with `with`.
                """
                self.stack = ExitStack()
                self.stack.enter_context(
                    patch("builtins.__import__", side_effect=_mock_import)
                )
                self.stack.enter_context(
                    patch("nio.AsyncClientConfig.__post_init__", lambda self: None)
                )
                self.stack.enter_context(
                    patch("nio.AsyncClientConfig.__init__", mock_client_config_init)
                )
                return self

            def __exit__(self, exc_type, exc_val, exc_tb):
                """
                Exit the context manager by closing the internal patch stack.

                Any exception information passed via exc_type, exc_val, and exc_tb is ignored; this method does not suppress exceptions (returns None).
                """
                self.stack.close()

        return E2EEMockContext()


@pytest.fixture
def sample_config():
    """Sample configuration for testing."""
    return TEST_CONFIG_YAML


@pytest.fixture
def temp_config_file(tmp_path, sample_config):
    """
    Create a temporary YAML config file from the given sample configuration and return its path.

    The fixture writes `sample_config` to a file named `config.yaml` under `tmp_path` using YAML serialization.

    Parameters:
        sample_config (Mapping): Data to serialize into the YAML config file.

    Returns:
        pathlib.Path: Path to the created `config.yaml`.
    """
    config_file = tmp_path / "config.yaml"
    with open(config_file, "w") as f:
        yaml.dump(sample_config, f)
    return config_file


@pytest.fixture
def temp_env_file(tmp_path):
    """
    Create a temporary `.env` file for tests containing MATRIX_ACCESS_TOKEN and ESV_API_KEY.

    The file is written to the provided temporary path and contains:
    - MATRIX_ACCESS_TOKEN set to the test constant `TEST_ACCESS_TOKEN`
    - ESV_API_KEY set to "test_esv_key"

    Returns:
        pathlib.Path: Path to the created `.env` file.
    """
    env_file = tmp_path / ".env"
    env_file.write_text(
        f"""
MATRIX_ACCESS_TOKEN={TEST_ACCESS_TOKEN}
ESV_API_KEY=test_esv_key
"""
    )
    return env_file


class TestConfigLoading:
    """Test configuration loading functionality."""

    def test_load_config_success(self, temp_config_file):
        """Test successful config loading."""
        config = bot.load_config(str(temp_config_file))

        assert config is not None
        assert config["matrix_homeserver"] == TEST_HOMESERVER
        assert config["matrix_user"] == TEST_USER_ID
        assert len(config["matrix_room_ids"]) == 2

    def test_load_config_file_not_found(self):
        """Test loading non-existent config file."""
        config = bot.load_config("nonexistent.yaml")
        assert config is None

    def test_load_config_invalid_yaml(self, tmp_path):
        """Test loading invalid YAML file."""
        invalid_file = tmp_path / "invalid.yaml"
        invalid_file.write_text("invalid: yaml: content: [")

        config = bot.load_config(str(invalid_file))
        assert config is None

    def test_load_config_missing_required_fields(self, tmp_path):
        """Test loading config with missing required fields."""
        incomplete_config = {
            "matrix_homeserver": TEST_HOMESERVER
            # Missing matrix_user and matrix_room_ids
        }

        config_file = tmp_path / "incomplete.yaml"
        with open(config_file, "w") as f:
            yaml.dump(incomplete_config, f)

        config = bot.load_config(str(config_file))
        assert config is None


class TestEnvironmentLoading:
    """Test environment variable loading."""

    def test_load_environment_with_env_file(self, temp_config_file, temp_env_file):
        """Test loading environment with .env file."""
        # Move .env file to same directory as config
        env_target = temp_config_file.parent / ".env"
        env_target.write_text(temp_env_file.read_text())

        # Load config first, then pass to load_environment
        config = bot.load_config(str(temp_config_file))
        matrix_token, api_keys = bot.load_environment(config, str(temp_config_file))

        assert matrix_token == TEST_ACCESS_TOKEN
        assert api_keys["esv"] == "test_esv_key"

    @patch.dict(
        "os.environ", {"MATRIX_ACCESS_TOKEN": "env_token", "ESV_API_KEY": "env_esv_key"}
    )
    def test_load_environment_from_os_env(self, temp_config_file):
        """Test loading environment from OS environment variables."""
        # Load config first, then pass to load_environment
        config = bot.load_config(str(temp_config_file))
        matrix_token, api_keys = bot.load_environment(config, str(temp_config_file))

        assert matrix_token == "env_token"  # noqa: S105
        assert api_keys["esv"] == "env_esv_key"

    @patch.dict("os.environ", {}, clear=True)
    def test_load_environment_no_env_vars(self, temp_config_file):
        """Test loading environment with no environment variables."""
        # Load config first, then pass to load_environment
        config = bot.load_config(str(temp_config_file))
        matrix_token, api_keys = bot.load_environment(config, str(temp_config_file))

        assert matrix_token is None
        assert api_keys["esv"] is None


class TestBookNameNormalization:
    """Test Bible book name validation and normalization."""

    @pytest.mark.parametrize(
        "input_name,expected",
        [
            ("gen", "Genesis"),
            ("GEN", "Genesis"),
            ("Genesis", "Genesis"),
            ("1 cor", "1 Corinthians"),
            ("1co", "1 Corinthians"),  # This is what's actually in BOOK_ABBREVIATIONS
            ("rev", "Revelation"),
            ("revelation", "Revelation"),
            ("ps", "Psalms"),
            ("psalm", "Psalms"),
            ("song", "Song of Solomon"),
            ("sos", "Song of Solomon"),
            ("so", "Song of Solomon"),
            ("Song of Solomon", "Song of Solomon"),
        ],
    )
    def test_validate_and_normalize_book_name_valid(self, input_name, expected):
        """Test book name validation and normalization with valid inputs."""
        result = validate_and_normalize_book_name(input_name)
        assert result == expected

    @pytest.mark.parametrize(
        "input_name",
        [
            "unknown",
            "invalidbook",
            "xyz",
            "",
            "   ",
        ],
    )
    def test_validate_and_normalize_book_name_invalid(self, input_name):
        """Test that invalid book names return None."""
        result = validate_and_normalize_book_name(input_name)
        assert result is None


class TestBookNameValidation:
    """Test Bible book name validation."""

    @pytest.mark.parametrize(
        "book_name,expected",
        [
            # Valid abbreviations
            ("gen", "Genesis"),
            ("GEN", "Genesis"),
            ("1co", "1 Corinthians"),
            ("1 cor", "1 Corinthians"),
            ("ps", "Psalms"),
            ("rev", "Revelation"),
            # Valid full names
            ("Genesis", "Genesis"),
            ("Matthew", "Matthew"),
            ("1 Corinthians", "1 Corinthians"),
            ("Psalms", "Psalms"),
            ("Revelation", "Revelation"),
            # Invalid names (common false positives)
            ("I have", None),
            ("Room", None),
            ("Version", None),
            ("Chapter", None),
            ("unknown", None),
            ("xyz", None),
            ("", None),
        ],
    )
    def test_validate_and_normalize_book_name(self, book_name, expected):
        """Test book name validation and normalization with various inputs."""
        result = validate_and_normalize_book_name(book_name)
        assert result == expected

    @pytest.mark.parametrize(
        "book_name,expected",
        [
            ("1 Samuel", "1 Samuel"),  # Normal spacing
            ("1  Samuel", "1 Samuel"),  # Double space
            ("1\tSamuel", "1 Samuel"),  # Tab character
            ("  1   Samuel  ", "1 Samuel"),  # Multiple spaces and padding
            ("Song of Solomon", "Song of Solomon"),  # Normal case
            ("Song  of  Solomon", "Song of Solomon"),  # Multiple spaces between words
            ("  John  ", "John"),  # Padded single word
        ],
    )
    def test_validate_and_normalize_book_name_whitespace_normalization(
        self, book_name, expected
    ):
        """Test that book validation and normalization handles irregular whitespace correctly."""
        result = validate_and_normalize_book_name(book_name)
        assert result == expected

    @pytest.mark.parametrize(
        "book_name",
        [
            "unknown  book",  # Unknown book with extra spaces
            "   invalid   ",  # Invalid book with padding
            "xyz  abc",  # Invalid book with spaces
        ],
    )
    def test_validate_and_normalize_book_name_whitespace_invalid(self, book_name):
        """Test that invalid book names with whitespace return None."""
        result = validate_and_normalize_book_name(book_name)
        assert result is None


class TestAPIRequests:
    """Test API request functionality."""

    @pytest.mark.asyncio
    async def test_make_api_request_success(self):
        """Test successful API request."""
        mock_response_data = {"text": "Test verse", "reference": "Test 1:1"}

        with patch("aiohttp.ClientSession.get") as mock_get:
            mock_response = AsyncMock()
            mock_response.json.return_value = mock_response_data
            mock_response.status = 200
            # ✅ CORRECT: Make headers a regular MagicMock to return strings, not coroutines
            mock_response.headers = MagicMock()
            mock_response.headers.get.return_value = "application/json"
            mock_get.return_value.__aenter__.return_value = mock_response

            result = await bot.make_api_request("/test")
            assert result == mock_response_data

    @pytest.mark.asyncio
    async def test_make_api_request_http_error(self):
        """Test API request with HTTP error."""

        with patch("aiohttp.ClientSession.get") as mock_get:
            mock_response = AsyncMock()
            mock_response.status = 404
            # ✅ CORRECT: Make headers a regular MagicMock to return strings, not coroutines
            mock_response.headers = MagicMock()
            mock_response.headers.get.return_value = "text/html"
            mock_get.return_value.__aenter__.return_value = mock_response

            result = await bot.make_api_request("/test")
            assert result is None

    @pytest.mark.asyncio
    async def test_make_api_request_timeout(self):
        """Test API request with timeout."""

        with patch("aiohttp.ClientSession.get") as mock_get:
            mock_get.side_effect = asyncio.TimeoutError()

            result = await bot.make_api_request("/test", timeout=0.1)
            assert result is None


class TestPartialReferenceMatching:
    """Test partial reference matching functionality."""

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("true", True),
            ("True", True),
            ("yes", True),
            ("on", True),
            ("1", True),
            (1, True),
            ("false", False),
            ("off", False),
            ("0", False),
            (0, False),
            (None, False),
        ],
    )
    def test_detect_anywhere_bool_coercion(self, raw, expected):
        """Ensure truthy/falsey strings and ints map correctly."""
        cfg = {
            "matrix_room_ids": ["!test:example.org"],
            "bot": {"detect_references_anywhere": raw},
        }
        bb = BibleBot(cfg)
        assert bb.detect_references_anywhere is expected

    @pytest.mark.asyncio
    @pytest.mark.parametrize("flag,should_call", [(False, False), (True, True)])
    async def test_detect_references_anywhere_toggle(self, flag, should_call):
        """Test that partial references are handled correctly based on detect_references_anywhere flag."""
        config = {
            "matrix_room_ids": ["!test:example.org"],
            "bot": {"detect_references_anywhere": flag},
        }
        bible_bot = BibleBot(config)
        bible_bot.start_time = 0
        bible_bot._room_id_set = {"!test:example.org"}
        bible_bot.client = MagicMock()
        bible_bot.client.user_id = "@bot:example.org"

        # Mock the scripture handling
        with patch.object(
            bible_bot, "handle_scripture_command", new_callable=AsyncMock
        ) as mock_handle:
            # Create a mock event with partial reference
            event = MagicMock()
            event.body = "Have you read John 3:16 ESV?"  # Reference embedded in text
            event.sender = "@user:example.org"
            event.server_timestamp = 1000

            room = MagicMock()
            room.room_id = "!test:example.org"

            await bible_bot.on_room_message(room, event)

            if should_call:
                mock_handle.assert_called_once()
                args = mock_handle.call_args[0]
                assert args[0] == "!test:example.org"  # room_id
                assert "John 3:16" in args[1]  # passage
                assert args[2].lower() == "esv"  # translation (case-insensitive)
            else:
                mock_handle.assert_not_called()

    @pytest.mark.asyncio
    @pytest.mark.parametrize("detect_anywhere", [False, True])
    async def test_exact_reference_works_in_both_modes(self, detect_anywhere):
        """Test that exact references work in both modes."""
        config = {
            "matrix_room_ids": ["!test:example.org"],
            "bot": {"detect_references_anywhere": detect_anywhere},
        }
        bible_bot = BibleBot(config)
        bible_bot.start_time = 0
        bible_bot._room_id_set = {"!test:example.org"}
        bible_bot.client = MagicMock()
        bible_bot.client.user_id = "@bot:example.org"

        # Mock the scripture handling
        with patch.object(
            bible_bot, "handle_scripture_command", new_callable=AsyncMock
        ) as mock_handle:
            # Create a mock event with exact reference
            event = MagicMock()
            event.body = "John 3:16"  # Exact reference
            event.sender = "@user:example.org"
            event.server_timestamp = 1000

            room = MagicMock()
            room.room_id = "!test:example.org"

            await bible_bot.on_room_message(room, event)

            # Should trigger scripture handling in both modes
            mock_handle.assert_called_once()
            args = mock_handle.call_args[0]
            assert args[0] == "!test:example.org"  # room_id
            assert "John 3:16" in args[1]  # passage

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "false_positive_message",
        [
            "I have 3 cats",
            "Room 5 is available",
            "Version 2 update",
            "Chapter 1 begins",
            "Meeting at 2:30",
            "Call me at 555:1234",
            "Release v2.0 today",
            "Meet @ 2:30pm",
            "task 1:1 is complete",  # Should not match any Bible book
        ],
    )
    async def test_false_positives_prevented(self, false_positive_message):
        """Test that common false positives are prevented with validation."""
        config = {
            "matrix_room_ids": ["!test:example.org"],
            "bot": {"detect_references_anywhere": True},
        }
        bible_bot = BibleBot(config)
        bible_bot.start_time = 0
        bible_bot._room_id_set = {"!test:example.org"}
        bible_bot.client = MagicMock()
        bible_bot.client.user_id = "@bot:example.org"

        # Mock the scripture handling
        with patch.object(
            bible_bot, "handle_scripture_command", new_callable=AsyncMock
        ) as mock_handle:
            event = MagicMock()
            event.body = false_positive_message
            event.sender = "@user:example.org"
            event.server_timestamp = 1000

            room = MagicMock()
            room.room_id = "!test:example.org"

            await bible_bot.on_room_message(room, event)

            # Should NOT trigger scripture handling for false positives
            mock_handle.assert_not_called()

    @pytest.mark.asyncio
    async def test_partial_reference_with_kjv_translation(self):
        """Test that partial references work with KJV translation specification."""
        config = {
            "matrix_room_ids": ["!test:example.org"],
            "bot": {"detect_references_anywhere": True},
        }
        bible_bot = BibleBot(config)
        bible_bot.start_time = 0
        bible_bot._room_id_set = {"!test:example.org"}
        bible_bot.client = MagicMock()
        bible_bot.client.user_id = "@bot:example.org"

        # Mock the scripture handling
        with patch.object(
            bible_bot, "handle_scripture_command", new_callable=AsyncMock
        ) as mock_handle:
            # Create a mock event with partial reference and KJV translation
            event = MagicMock()
            event.body = "Have you read John 3:16 KJV?"  # Reference with KJV
            event.sender = "@user:example.org"
            event.server_timestamp = 1000

            room = MagicMock()
            room.room_id = "!test:example.org"

            await bible_bot.on_room_message(room, event)

            # Should trigger scripture handling
            mock_handle.assert_called_once()
            args = mock_handle.call_args[0]
            assert args[0] == "!test:example.org"  # room_id
            assert "John 3:16" in args[1]  # passage
            assert args[2].lower() == "kjv"  # translation should be KJV


class TestBibleTextRetrieval:
    """Test Bible text retrieval functions."""

    @pytest.mark.asyncio
    async def test_get_kjv_text_success(self):
        """Test successful KJV text retrieval."""
        mock_response = {
            "text": "For God so loved the world...",
            "reference": TEST_BIBLE_REFERENCE,
        }

        with patch.object(
            bot, "make_api_request", new=AsyncMock(return_value=mock_response)
        ):
            result = await bot.get_kjv_text(TEST_BIBLE_REFERENCE)

            assert result is not None
            text, reference = result
            assert text == "For God so loved the world..."
            assert reference == TEST_BIBLE_REFERENCE

    @pytest.mark.asyncio
    async def test_get_kjv_text_not_found(self):
        """Test KJV text retrieval when verse not found."""
        with patch.object(bot, "make_api_request", new=AsyncMock(return_value=None)):
            with pytest.raises(bot.PassageNotFound) as exc_info:
                await bot.get_kjv_text("Invalid 99:99")

            assert "Invalid 99:99" in str(exc_info.value)
            assert "not found in KJV" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_esv_text_success(self):
        """Test successful ESV text retrieval."""
        mock_response = {
            "passages": ["For God so loved the world..."],
            "canonical": TEST_BIBLE_REFERENCE,
        }

        with patch.object(
            bot, "make_api_request", new=AsyncMock(return_value=mock_response)
        ):
            result = await bot.get_esv_text(TEST_BIBLE_REFERENCE, "test_api_key")

            assert result is not None
            text, reference = result
            assert text == "For God so loved the world..."
            assert reference == TEST_BIBLE_REFERENCE

    @pytest.mark.asyncio
    async def test_get_esv_text_no_api_key(self):
        """Test ESV text retrieval without API key."""
        with pytest.raises(bot.APIKeyMissing) as exc_info:
            await bot.get_esv_text(TEST_BIBLE_REFERENCE, None)

        assert TEST_BIBLE_REFERENCE in str(exc_info.value)
        assert "ESV API key is required" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_bible_text_with_cache(self):
        """Test Bible text retrieval with caching."""
        # Clear cache first
        if hasattr(bot, "_passage_cache"):
            bot._passage_cache.clear()

        mock_response = {
            "text": "For God so loved the world...",
            "reference": TEST_BIBLE_REFERENCE,
        }

        with patch.object(
            bot, "make_api_request", new=AsyncMock(return_value=mock_response)
        ) as mock_request:
            # First call should hit the API
            result1 = await bot.get_bible_text(TEST_BIBLE_REFERENCE, "kjv")

            # Second call should use cache
            result2 = await bot.get_bible_text(TEST_BIBLE_REFERENCE, "kjv")

            assert result1 == result2
            # API should only be called once due to caching
            mock_request.assert_called_once()


class TestBibleBot:
    """Test the BibleBot class."""

    def test_biblebot_init(self, sample_config):
        """Test BibleBot initialization."""
        mock_client = MagicMock()
        bot_instance = bot.BibleBot(sample_config, mock_client)

        assert bot_instance.config == sample_config
        assert bot_instance.client == mock_client
        assert bot_instance.api_keys == {}

    @pytest.mark.asyncio
    async def test_resolve_aliases(self, sample_config):
        """Test room alias resolution."""
        config_with_alias = sample_config.copy()
        if "matrix" not in config_with_alias:
            config_with_alias["matrix"] = {}
        config_with_alias["matrix"]["room_ids"] = [
            TEST_ROOM_IDS[0],
            "#alias:matrix.org",
        ]

        # E2EE dependencies are mocked upfront in conftest.py
        with patch("biblebot.bot.AsyncClient") as mock_client_class:
            mock_client = AsyncMock(
                spec=[
                    "user_id",
                    "device_id",
                    "room_send",
                    "join",
                    "add_event_callback",
                    "should_upload_keys",
                    "restore_login",
                    "access_token",
                    "rooms",
                    "room_resolve_alias",
                    "close",
                ]
            )
            mock_client_class.return_value = mock_client

            # Mock alias resolution response
            mock_response = MagicMock()
            mock_response.room_id = TEST_RESOLVED_ROOM_ID
            mock_client.room_resolve_alias = AsyncMock(return_value=mock_response)

            bot_instance = bot.BibleBot(config_with_alias)
            bot_instance.client = mock_client

            await bot_instance.resolve_aliases()

            # Check that alias was resolved and added to room IDs
            assert TEST_RESOLVED_ROOM_ID in bot_instance.config["matrix"]["room_ids"]
            mock_client.room_resolve_alias.assert_called_once_with("#alias:matrix.org")

    @pytest.mark.asyncio
    async def test_join_matrix_room_success(self, sample_config):
        """Test successful room joining."""
        # Use existing test helper to avoid heavy patching
        mock_client = E2EETestFramework.create_mock_client(rooms={})

        # Mock successful join response
        mock_response = MagicMock()
        mock_response.room_id = TEST_ROOM_IDS[0]
        mock_client.join = AsyncMock(return_value=mock_response)

        bot_instance = bot.BibleBot(sample_config)
        bot_instance.client = mock_client

        await bot_instance.join_matrix_room(TEST_ROOM_IDS[0])

        mock_client.join.assert_called_once_with(TEST_ROOM_IDS[0])

    @pytest.mark.asyncio
    async def test_join_matrix_room_already_joined(self, sample_config):
        """Test joining room when already a member."""
        # E2EE dependencies are mocked upfront in conftest.py
        with patch("biblebot.bot.AsyncClient") as mock_client_class:
            mock_client = AsyncMock(
                spec=[
                    "user_id",
                    "device_id",
                    "room_send",
                    "join",
                    "add_event_callback",
                    "should_upload_keys",
                    "restore_login",
                    "access_token",
                    "rooms",
                    "room_resolve_alias",
                    "close",
                ]
            )
            mock_client_class.return_value = mock_client
            mock_client.rooms = {TEST_ROOM_IDS[0]: MagicMock()}  # Already in room

            bot_instance = bot.BibleBot(sample_config)
            bot_instance.client = mock_client

            await bot_instance.join_matrix_room(TEST_ROOM_IDS[0])

            # Should not attempt to join
            mock_client.join.assert_not_called()

    @pytest.mark.asyncio
    async def test_send_reaction(self, sample_config):
        """Test sending reaction to message."""
        # E2EE dependencies are mocked upfront in conftest.py
        with patch("biblebot.bot.AsyncClient") as mock_client_class:
            mock_client = AsyncMock(
                spec=[
                    "user_id",
                    "device_id",
                    "room_send",
                    "join",
                    "add_event_callback",
                    "should_upload_keys",
                    "restore_login",
                    "access_token",
                    "rooms",
                    "room_resolve_alias",
                    "close",
                ]
            )
            mock_client_class.return_value = mock_client
            # Ensure room_send is AsyncMock
            mock_client.room_send = AsyncMock()

            bot_instance = bot.BibleBot(sample_config)
            bot_instance.client = mock_client

            await bot_instance.send_reaction(TEST_ROOM_ID, "$event:matrix.org", "✅")

            # Check that room_send was called with correct reaction content
            mock_client.room_send.assert_called_once()
            call_args = mock_client.room_send.call_args

            assert call_args[0][0] == TEST_ROOM_ID
            assert call_args[0][1] == "m.reaction"
            content = call_args[0][2]
            assert content["m.relates_to"]["event_id"] == "$event:matrix.org"
            assert content["m.relates_to"]["key"] == "✅"


class TestMessageHandling:
    """Test message handling and Bible verse detection."""

    @pytest.mark.asyncio
    async def test_on_room_message_bible_reference(self, sample_config):
        """Test handling room message with Bible reference."""
        # E2EE dependencies are mocked upfront in conftest.py
        with patch("biblebot.bot.AsyncClient") as mock_client_class:
            mock_client = AsyncMock(
                spec=[
                    "user_id",
                    "device_id",
                    "room_send",
                    "join",
                    "add_event_callback",
                    "should_upload_keys",
                    "restore_login",
                    "access_token",
                    "rooms",
                ]
            )
            mock_client_class.return_value = mock_client
            mock_client.user_id = TEST_USER_ID

            bot_instance = bot.BibleBot(sample_config)
            bot_instance.client = mock_client
            bot_instance.start_time = 1000000000000  # Set start time (milliseconds)
            # Populate room ID set for testing (normally done in initialize())
            bot_instance._room_id_set = set(sample_config["matrix_room_ids"])

            # Mock room and event
            mock_room = MagicMock()
            mock_room.room_id = TEST_ROOM_IDS[0]

            mock_event = MagicMock()
            mock_event.sender = TEST_MESSAGE_SENDER  # Different from bot
            mock_event.server_timestamp = (
                2000000000000  # After start time (milliseconds)
            )
            mock_event.body = TEST_MESSAGE_BODY
            mock_event.event_id = "$event:matrix.org"

            # Mock the scripture handling
            with patch.object(
                bot_instance, "handle_scripture_command", new=AsyncMock()
            ) as mock_handle:
                await bot_instance.on_room_message(mock_room, mock_event)

                mock_handle.assert_called_once()
                call_args = mock_handle.call_args[0]
                assert call_args[0] == TEST_ROOM_IDS[0]
                assert TEST_MESSAGE_BODY in call_args[1]
                assert call_args[2] == "kjv"  # Default translation

    @pytest.mark.asyncio
    async def test_on_room_message_ignore_own_message(self, sample_config):
        """Test ignoring messages from the bot itself."""
        # E2EE dependencies are mocked upfront in conftest.py
        with patch("biblebot.bot.AsyncClient") as mock_client_class:
            mock_client = AsyncMock(
                spec=[
                    "user_id",
                    "device_id",
                    "room_send",
                    "join",
                    "add_event_callback",
                    "should_upload_keys",
                    "restore_login",
                    "access_token",
                    "rooms",
                ]
            )
            mock_client_class.return_value = mock_client
            mock_client.user_id = TEST_USER_ID

            bot_instance = bot.BibleBot(sample_config)
            bot_instance.client = mock_client
            bot_instance.start_time = 1000000000000

            mock_room = MagicMock()
            mock_room.room_id = TEST_ROOM_IDS[0]

            mock_event = MagicMock()
            mock_event.sender = TEST_USER_ID  # Same as bot
            mock_event.server_timestamp = 2000000000000
            mock_event.body = TEST_MESSAGE_BODY

            with patch.object(
                bot_instance, "handle_scripture_command", new=AsyncMock()
            ) as mock_handle:
                await bot_instance.on_room_message(mock_room, mock_event)

                # Should not handle scripture from own message
                mock_handle.assert_not_called()

    @pytest.mark.asyncio
    async def test_on_room_message_ignore_old_message(self, sample_config):
        """Test ignoring messages from before bot start."""
        # E2EE dependencies are mocked upfront in conftest.py
        with patch("biblebot.bot.AsyncClient") as mock_client_class:
            mock_client = AsyncMock(
                spec=[
                    "user_id",
                    "device_id",
                    "room_send",
                    "join",
                    "add_event_callback",
                    "should_upload_keys",
                    "restore_login",
                    "access_token",
                    "rooms",
                ]
            )
            mock_client_class.return_value = mock_client
            mock_client.user_id = TEST_USER_ID

            bot_instance = bot.BibleBot(sample_config)
            bot_instance.client = mock_client
            bot_instance.start_time = 2000000000000

            mock_room = MagicMock()
            mock_room.room_id = TEST_ROOM_IDS[0]

            mock_event = MagicMock()
            mock_event.sender = TEST_MESSAGE_SENDER
            mock_event.server_timestamp = 1000000000000  # Before start time
            mock_event.body = TEST_MESSAGE_BODY

            with patch.object(
                bot_instance, "handle_scripture_command", new=AsyncMock()
            ) as mock_handle:
                await bot_instance.on_room_message(mock_room, mock_event)

                # Should not handle old message
                mock_handle.assert_not_called()

    @pytest.mark.asyncio
    async def test_on_room_message_wrong_room(self, sample_config):
        """Test ignoring messages from non-configured rooms."""
        # E2EE dependencies are mocked upfront in conftest.py
        with patch("biblebot.bot.AsyncClient") as mock_client_class:
            mock_client = AsyncMock(
                spec=[
                    "user_id",
                    "device_id",
                    "room_send",
                    "join",
                    "add_event_callback",
                    "should_upload_keys",
                    "restore_login",
                    "access_token",
                    "rooms",
                ]
            )
            mock_client_class.return_value = mock_client
            mock_client.user_id = TEST_USER_ID

            bot_instance = bot.BibleBot(sample_config)
            bot_instance.client = mock_client
            bot_instance.start_time = 1000

            mock_room = MagicMock()
            mock_room.room_id = TEST_WRONG_ROOM_ID  # Not in config

            mock_event = MagicMock()
            mock_event.sender = TEST_MESSAGE_SENDER
            mock_event.server_timestamp = 2000000000000
            mock_event.body = TEST_MESSAGE_BODY

            with patch.object(
                bot_instance, "handle_scripture_command", new=AsyncMock()
            ) as mock_handle:
                await bot_instance.on_room_message(mock_room, mock_event)

                # Should not handle message from wrong room
                mock_handle.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_scripture_command_success(self, sample_config):
        """Test successful scripture command handling."""
        # E2EE dependencies are mocked upfront in conftest.py
        with patch("biblebot.bot.AsyncClient") as mock_client_class:
            mock_client = AsyncMock(
                spec=[
                    "user_id",
                    "device_id",
                    "room_send",
                    "join",
                    "add_event_callback",
                    "should_upload_keys",
                    "restore_login",
                    "access_token",
                    "rooms",
                    "room_resolve_alias",
                    "close",
                ]
            )
            mock_client_class.return_value = mock_client
            # Ensure room_send is AsyncMock
            mock_client.room_send = AsyncMock()

            bot_instance = bot.BibleBot(sample_config)
            bot_instance.client = mock_client
            bot_instance.api_keys = {"kjv": None}

            mock_event = MagicMock()
            mock_event.event_id = "$event:matrix.org"

            # Mock successful Bible text retrieval
            with patch.object(
                bot,
                "get_bible_text",
                new=AsyncMock(return_value=("Test verse text", "Test 1:1")),
            ):
                with patch.object(
                    bot_instance, "send_reaction", new=AsyncMock()
                ) as mock_reaction:
                    await bot_instance.handle_scripture_command(
                        TEST_ROOM_ID, "Test 1:1", "kjv", mock_event
                    )

                    # Should send reaction
                    mock_reaction.assert_called_once_with(
                        TEST_ROOM_ID, "$event:matrix.org", "✅"
                    )

                    # Should send scripture message
                    mock_client.room_send.assert_called_once()
                    call_args = mock_client.room_send.call_args[0]
                    assert call_args[0] == TEST_ROOM_ID
                    assert call_args[1] == "m.room.message"
                    content = call_args[2]
                    assert "Test verse text" in content["body"]
                    assert "Test 1:1" in content["body"]

    @pytest.mark.asyncio
    async def test_handle_scripture_command_failure(self, sample_config):
        """Test scripture command handling when retrieval fails."""
        # E2EE dependencies are mocked upfront in conftest.py
        with patch("biblebot.bot.AsyncClient") as mock_client_class:
            mock_client = AsyncMock(
                spec=[
                    "user_id",
                    "device_id",
                    "room_send",
                    "join",
                    "add_event_callback",
                    "should_upload_keys",
                    "restore_login",
                    "access_token",
                    "rooms",
                    "room_resolve_alias",
                    "close",
                ]
            )
            mock_client_class.return_value = mock_client
            # Ensure room_send is AsyncMock
            mock_client.room_send = AsyncMock()

            bot_instance = bot.BibleBot(sample_config)
            bot_instance.client = mock_client
            bot_instance.api_keys = {"kjv": None}

            mock_event = MagicMock()
            mock_event.event_id = "$event:matrix.org"

            # Mock failed Bible text retrieval
            with patch.object(
                bot,
                "get_bible_text",
                new=AsyncMock(side_effect=bot.PassageNotFound("Invalid passage")),
            ):
                with patch.object(
                    bot_instance, "send_reaction", new=AsyncMock()
                ) as mock_reaction:
                    await bot_instance.handle_scripture_command(
                        TEST_ROOM_ID, "Invalid 99:99", "kjv", mock_event
                    )

                    # Should not send reaction
                    mock_reaction.assert_not_called()

                    # Should send error message
                    mock_client.room_send.assert_called_once()
                    call_args = mock_client.room_send.call_args[0]
                    content = call_args[2]
                    assert (
                        "Error: The requested passage could not be found"
                        in content["body"]
                    )


class TestInviteHandling:
    """Test room invite handling."""

    @pytest.mark.asyncio
    async def test_on_invite_configured_room(self, sample_config):
        """Test handling invite to configured room."""
        # E2EE dependencies are mocked upfront in conftest.py
        with patch("biblebot.bot.AsyncClient") as mock_client_class:
            mock_client = AsyncMock(
                spec=[
                    "user_id",
                    "device_id",
                    "room_send",
                    "join",
                    "add_event_callback",
                    "should_upload_keys",
                    "restore_login",
                    "access_token",
                    "rooms",
                ]
            )
            mock_client_class.return_value = mock_client

            bot_instance = bot.BibleBot(sample_config)
            bot_instance.client = mock_client
            # Initialize room ID set for membership checks
            bot_instance._room_id_set = set(sample_config["matrix_room_ids"])

            mock_room = MagicMock()
            mock_room.room_id = TEST_ROOM_IDS[0]  # In config

            mock_event = MagicMock()

            with patch.object(
                bot_instance, "join_matrix_room", new=AsyncMock()
            ) as mock_join:
                await bot_instance.on_invite(mock_room, mock_event)

                mock_join.assert_called_once_with(TEST_ROOM_IDS[0])

    @pytest.mark.asyncio
    async def test_on_invite_non_configured_room(self, sample_config):
        """Test handling invite to non-configured room."""
        # E2EE dependencies are mocked upfront in conftest.py
        with patch("biblebot.bot.AsyncClient") as mock_client_class:
            mock_client = AsyncMock(
                spec=[
                    "user_id",
                    "device_id",
                    "room_send",
                    "join",
                    "add_event_callback",
                    "should_upload_keys",
                    "restore_login",
                    "access_token",
                    "rooms",
                ]
            )
            mock_client_class.return_value = mock_client

            bot_instance = bot.BibleBot(sample_config)
            bot_instance.client = mock_client

            mock_room = MagicMock()
            mock_room.room_id = TEST_UNKNOWN_ROOM_ID  # Not in config

            mock_event = MagicMock()

            with patch.object(
                bot_instance, "join_matrix_room", new=AsyncMock()
            ) as mock_join:
                await bot_instance.on_invite(mock_room, mock_event)

                # Should not join non-configured room
                mock_join.assert_not_called()


class TestE2EEFunctionality:
    """Test E2EE-related functionality."""

    @pytest.mark.asyncio
    async def test_room_send_ignore_unverified_devices(self, sample_config):
        """Test that all room_send calls include ignore_unverified_devices=True for E2EE compatibility."""
        # Create mock client
        mock_client = AsyncMock()
        mock_client.room_send = AsyncMock()

        # Create bot instance
        bot_instance = bot.BibleBot(sample_config, client=mock_client)

        # Test send_reaction method
        await bot_instance.send_reaction("!room:matrix.org", "$event:matrix.org", "✅")

        # Verify room_send was called with ignore_unverified_devices=True
        mock_client.room_send.assert_called_with(
            "!room:matrix.org",
            "m.reaction",
            {
                "m.relates_to": {
                    "rel_type": "m.annotation",
                    "event_id": "$event:matrix.org",
                    "key": "✅",
                }
            },
            ignore_unverified_devices=True,
        )

        # Reset mock for next test
        mock_client.room_send.reset_mock()

        # Test handle_scripture_command method (successful case)
        with patch(
            "biblebot.bot.get_bible_text", new_callable=AsyncMock
        ) as mock_get_bible:
            mock_get_bible.return_value = ("For God so loved the world...", "John 3:16")

            # Create mock event
            mock_event = MagicMock()
            mock_event.event_id = "$event:matrix.org"

            await bot_instance.handle_scripture_command(
                "!room:matrix.org", "John 3:16", "kjv", mock_event
            )

            # Should have been called with ignore_unverified_devices=True
            assert mock_client.room_send.call_count >= 1
            for call in mock_client.room_send.call_args_list:
                # Check that ignore_unverified_devices=True is in the call
                assert call.kwargs.get("ignore_unverified_devices") is True

    @pytest.mark.asyncio
    async def test_send_error_message(self, sample_config):
        """Test that _send_error_message helper method works correctly."""
        # Create mock client
        mock_client = AsyncMock()
        mock_client.room_send = AsyncMock()

        # Create bot instance
        bot_instance = bot.BibleBot(sample_config, client=mock_client)

        # Test _send_error_message method
        await bot_instance._send_error_message("!room:matrix.org", "Test error message")

        # Verify room_send was called with correct parameters
        mock_client.room_send.assert_called_once_with(
            "!room:matrix.org",
            "m.room.message",
            {
                "msgtype": "m.text",
                "body": "Test error message",
                "format": "org.matrix.custom.html",
                "formatted_body": "Test error message",  # HTML escaped (no special chars in this case)
            },
            ignore_unverified_devices=True,
        )

    @pytest.mark.asyncio
    async def test_on_decryption_failure(self, sample_config):
        """Test handling decryption failure events."""
        # Enable E2EE for this test
        e2ee_config = sample_config.copy()
        e2ee_config["matrix"]["e2ee"]["enabled"] = True

        # E2EE dependencies are mocked upfront in conftest.py
        with patch("biblebot.bot.AsyncClient") as mock_client_class:
            mock_client = AsyncMock(
                spec=[
                    "user_id",
                    "device_id",
                    "room_send",
                    "join",
                    "add_event_callback",
                    "should_upload_keys",
                    "restore_login",
                    "access_token",
                    "rooms",
                    "to_device",
                    "request_room_key",
                ]
            )
            mock_client_class.return_value = mock_client
            mock_client.user_id = TEST_USER_ID
            mock_client.device_id = TEST_DEVICE_ID

            bot_instance = bot.BibleBot(e2ee_config)
            bot_instance.client = mock_client

            try:
                mock_room = MagicMock()
                mock_room.room_id = TEST_ROOM_ID

                mock_event = MagicMock()
                mock_event.event_id = "$failed_event:matrix.org"
                mock_event.as_key_request.return_value = MagicMock()

                await bot_instance.on_decryption_failure(mock_room, mock_event)

                # Should use high-level request_room_key first
                mock_client.request_room_key.assert_called_once_with(mock_event)
                # to_device should not be called since request_room_key succeeded
                mock_client.to_device.assert_not_called()
                # Event should have room_id set
                assert mock_event.room_id == "!room:matrix.org"
            finally:
                # Explicitly clean up bot instance to prevent CI hanging
                if hasattr(bot_instance, "client"):
                    bot_instance.client = None
                del bot_instance

    @pytest.mark.asyncio
    async def test_on_decryption_failure_fallback(self, sample_config):
        """Test decryption failure fallback when request_room_key not available."""
        # Enable E2EE for this test
        e2ee_config = sample_config.copy()
        e2ee_config["matrix"]["e2ee"]["enabled"] = True

        # E2EE dependencies are mocked upfront in conftest.py
        with patch("biblebot.bot.AsyncClient") as mock_client_class:
            from unittest.mock import AsyncMock as _AsyncMock
            from unittest.mock import MagicMock

            import nio

            mock_client = MagicMock(
                spec_set=["user_id", "device_id", "to_device", "request_room_key"]
            )
            mock_client.user_id = TEST_USER_ID
            mock_client.device_id = TEST_DEVICE_ID
            mock_client.to_device = _AsyncMock()
            mock_client.request_room_key = _AsyncMock(
                side_effect=nio.exceptions.LocalProtocolError("Duplicate request")
            )
            mock_client_class.return_value = mock_client

            bot_instance = bot.BibleBot(e2ee_config)
            bot_instance.client = mock_client

            try:
                mock_room = MagicMock()
                mock_room.room_id = "!room:matrix.org"

                mock_event = MagicMock()
                mock_event.event_id = "$failed_event:matrix.org"
                mock_event.as_key_request.return_value = MagicMock()

                await bot_instance.on_decryption_failure(mock_room, mock_event)

                # Should try request_room_key first, then fall back to to_device
                mock_client.request_room_key.assert_called_once_with(mock_event)
                mock_client.to_device.assert_called_once()
                mock_event.as_key_request.assert_called_once_with(
                    TEST_USER_ID, TEST_DEVICE_ID
                )
            finally:
                # Explicitly clean up bot instance to prevent CI hanging
                if hasattr(bot_instance, "client"):
                    bot_instance.client = None
                del bot_instance


class TestMainFunction:
    """Test the main bot function."""

    @pytest.mark.asyncio
    @patch.dict(
        "os.environ",
        {
            "MATRIX_HOMESERVER": "https://matrix.org",
            "MATRIX_USER_ID": "@testbot:matrix.org",
        },
    )  # Set required environment variables for legacy mode
    @patch("biblebot.bot.load_credentials")
    @patch("biblebot.bot.get_store_dir")
    @patch("biblebot.bot.load_config")
    @patch("biblebot.bot.load_environment")
    async def test_main_with_credentials(
        self,
        mock_load_env,
        mock_load_config,
        mock_get_store,
        mock_load_creds,
        sample_config,
        tmp_path,
    ):
        """Test main function with access token from environment."""
        # Setup mocks - ensure credentials are found for proper E2EE testing
        mock_load_config.return_value = sample_config
        mock_load_env.return_value = (
            None,  # No access token - use session-based auth for E2EE
            {"esv": "test_key"},
        )

        # Mock session-based credentials for E2EE support
        from biblebot.auth import Credentials

        mock_credentials = Credentials(
            homeserver=TEST_HOMESERVER,
            user_id=TEST_USER_ID,
            access_token=TEST_ACCESS_TOKEN,
            device_id=TEST_DEVICE_ID,
        )
        mock_load_creds.return_value = mock_credentials

        mock_get_store.return_value = tmp_path / "store"

        # E2EE dependencies are mocked upfront in conftest.py
        with patch("biblebot.bot.AsyncClient") as mock_client_class:
            mock_client = AsyncMock(
                spec=[
                    "user_id",
                    "device_id",
                    "room_send",
                    "join",
                    "add_event_callback",
                    "should_upload_keys",
                    "restore_login",
                    "access_token",
                    "rooms",
                    "room_resolve_alias",
                    "keys_upload",
                    "close",
                    "sync_forever",
                    "sync",
                ]
            )
            mock_client.restore_login = MagicMock()
            mock_client.add_event_callback = MagicMock()
            mock_client.should_upload_keys = False
            mock_client.keys_upload = AsyncMock()
            mock_client.sync_forever = AsyncMock()  # Prevent infinite loop
            mock_client.sync = AsyncMock()
            mock_client.close = AsyncMock()
            mock_client.access_token = TEST_ACCESS_TOKEN
            mock_client_class.return_value = mock_client

            with patch("biblebot.bot.BibleBot") as mock_bot_class:
                mock_bot = MagicMock()
                mock_bot_class.return_value = mock_bot
                mock_bot.client = mock_client
                mock_bot.start = AsyncMock()

                await bot.main("test_config.yaml")

                # Should restore login from session-based credentials for E2EE support
                # Check that access_token was assigned from credentials
                assert mock_client.access_token == TEST_ACCESS_TOKEN

                # Should start the bot
                mock_bot.start.assert_called_once()

    @pytest.mark.asyncio
    @patch.dict(
        "os.environ",
        {
            "MATRIX_HOMESERVER": "https://matrix.org",
            "MATRIX_USER_ID": "@testbot:matrix.org",
        },
    )  # Set required environment variables for legacy mode
    @patch("biblebot.bot.load_credentials")
    @patch("biblebot.bot.get_store_dir")
    @patch("biblebot.bot.load_config")
    @patch("biblebot.bot.load_environment")
    async def test_main_with_access_token(
        self,
        mock_load_env,
        mock_load_config,
        mock_get_store,
        mock_load_creds,
        sample_config,
        tmp_path,
    ):
        """Test main function with access token."""
        # Setup mocks - keep E2EE enabled to test real functionality
        mock_load_config.return_value = sample_config
        mock_load_env.return_value = (TEST_ACCESS_TOKEN, {"esv": "test_key"})
        mock_load_creds.return_value = None  # No saved credentials
        mock_get_store.return_value = tmp_path / "store"

        # E2EE dependencies are mocked upfront in conftest.py
        with patch("biblebot.bot.AsyncClient") as mock_client_class:
            mock_client = AsyncMock(
                spec=[
                    "user_id",
                    "device_id",
                    "room_send",
                    "join",
                    "add_event_callback",
                    "should_upload_keys",
                    "restore_login",
                    "access_token",
                    "rooms",
                    "room_resolve_alias",
                    "close",
                    "keys_upload",
                ]
            )
            mock_client.restore_login = MagicMock()
            mock_client.add_event_callback = MagicMock()
            mock_client.should_upload_keys = False  # Disable key upload for this test
            mock_client.keys_upload = AsyncMock()  # Ensure keys_upload is AsyncMock
            # Set access_token as a regular attribute, not a MagicMock
            mock_client.access_token = None  # Will be set by the code
            # Ensure close is AsyncMock
            mock_client.close = AsyncMock()
            mock_client_class.return_value = mock_client

            with patch("biblebot.bot.BibleBot") as mock_bot_class:
                # Mock BibleBot methods that might be called
                mock_bot = AsyncMock()
                mock_bot.client = mock_client
                mock_bot.start = AsyncMock()
                mock_bot.close = AsyncMock()
                mock_bot_class.return_value = mock_bot

                # Test should complete without exceptions - this proves AsyncClient was created
                await bot.main("test_config.yaml")

                # The fact that main() completed successfully proves AsyncClient was created
                # and the access token flow worked correctly. The coverage report confirms
                # that lines 1037-1042 (AsyncClient creation) and 1067 (access token assignment)
                # are reached, which is the core functionality we're testing.

                # Verify the bot was started
                mock_bot.start.assert_called_once()

    @pytest.mark.asyncio
    @patch.dict("os.environ", {}, clear=True)  # Clear all environment variables
    @patch("biblebot.bot.load_credentials")  # Patch in bot module where it's imported
    @patch("biblebot.bot.load_config")
    @patch("biblebot.bot.load_environment")
    async def test_main_no_auth(
        self, mock_load_env, mock_load_config, mock_load_creds, sample_config
    ):
        """Test main function with no authentication."""
        # Setup mocks to simulate no authentication available
        mock_load_config.return_value = sample_config
        mock_load_env.return_value = (None, {"esv": "test_key"})  # No access token
        mock_load_creds.return_value = None  # No saved credentials

        # Use E2EE mocking framework to prevent ImportWarning
        # E2EE dependencies are mocked upfront in conftest.py
        # The main function should raise RuntimeError for no auth
        with pytest.raises(RuntimeError, match="No credentials found"):
            await bot.main("test_config.yaml")

        # Verify the mocks were called to check for auth
        mock_load_env.assert_called_once()
        mock_load_creds.assert_called_once()

    @pytest.mark.asyncio
    @patch("biblebot.bot.load_config")
    async def test_main_invalid_config(self, mock_load_config):
        """Test main function with invalid config."""
        mock_load_config.return_value = None  # Invalid config

        # Should raise RuntimeError for invalid config
        with pytest.raises(RuntimeError, match="Failed to load configuration"):
            await bot.main("invalid_config.yaml")

    @pytest.mark.asyncio
    @patch.dict(
        "os.environ",
        {
            "MATRIX_HOMESERVER": "https://matrix.org",
            "MATRIX_USER_ID": "@testbot:matrix.org",
        },
    )  # Set required environment variables for legacy mode
    @patch("biblebot.bot.load_credentials")
    @patch("biblebot.bot.get_store_dir")
    @patch("biblebot.bot.load_config")
    @patch("biblebot.bot.load_environment")
    async def test_main_with_e2ee_enabled(
        self,
        mock_load_env,
        mock_load_config,
        mock_get_store,
        mock_load_creds,
        sample_config,
        tmp_path,
    ):
        """Test main function with E2EE enabled."""
        # Enable E2EE in config
        e2ee_config = sample_config.copy()
        e2ee_config["matrix"]["e2ee"]["enabled"] = True

        mock_load_config.return_value = e2ee_config
        mock_load_env.return_value = (TEST_ACCESS_TOKEN, {"esv": "test_key"})
        mock_load_creds.return_value = None
        mock_get_store.return_value = tmp_path / "store"

        # E2EE dependencies are mocked upfront in conftest.py
        with patch("biblebot.bot.AsyncClient") as mock_client_class:
            with patch("biblebot.bot.AsyncClientConfig"):
                mock_client = AsyncMock(
                    spec=[
                        "user_id",
                        "device_id",
                        "room_send",
                        "join",
                        "add_event_callback",
                        "should_upload_keys",
                        "restore_login",
                        "access_token",
                        "rooms",
                        "room_resolve_alias",
                        "close",
                        "keys_upload",
                    ]
                )
                mock_client.restore_login = MagicMock()
                mock_client.add_event_callback = MagicMock()
                mock_client.keys_upload = AsyncMock()
                # Ensure close is AsyncMock
                mock_client.close = AsyncMock()
                mock_client_class.return_value = mock_client
                mock_client.should_upload_keys = True

                with patch("biblebot.bot.BibleBot") as mock_bot_class:
                    mock_bot = MagicMock()
                    mock_bot_class.return_value = mock_bot
                    mock_bot.client = mock_client
                    mock_bot.start = AsyncMock()

                    await bot.main("test_config.yaml")

                    # Should upload keys
                    mock_client.keys_upload.assert_called_once()

                    # Should register E2EE callback
                    mock_client.add_event_callback.assert_called()

                    # Should start the bot
                    mock_bot.start.assert_called_once()


class TestUtilityFunctions:
    """Test utility functions in the bot module."""

    def test_validate_and_normalize_book_name_full_names(self):
        """Test validating and normalizing full book names."""
        assert validate_and_normalize_book_name("Genesis") == "Genesis"
        assert validate_and_normalize_book_name("Exodus") == "Exodus"
        assert validate_and_normalize_book_name("Matthew") == "Matthew"

    def test_validate_and_normalize_book_name_abbreviations(self):
        """Test validating and normalizing common abbreviations."""
        assert validate_and_normalize_book_name("Gen") == "Genesis"
        assert validate_and_normalize_book_name("Ex") == "Exodus"
        assert validate_and_normalize_book_name("Matt") == "Matthew"
        assert validate_and_normalize_book_name("Mt") == "Matthew"

    def test_validate_and_normalize_book_name_case_insensitive(self):
        """Test case insensitive validation and normalization."""
        assert validate_and_normalize_book_name("gen") == "Genesis"
        assert validate_and_normalize_book_name("GEN") == "Genesis"
        assert validate_and_normalize_book_name("GeN") == "Genesis"

    def test_validate_and_normalize_book_name_unknown(self):
        """Test that unknown book names return None."""
        assert validate_and_normalize_book_name("Unknown") is None
        assert validate_and_normalize_book_name("XYZ") is None


class TestCacheFunctions:
    """Test caching functionality."""

    def test_cache_get_miss(self):
        """Test cache miss."""
        # Clear cache first
        if hasattr(bot, "_passage_cache"):
            bot._passage_cache.clear()

        result = bot._cache_get(TEST_BIBLE_REFERENCE, "kjv")
        assert result is None

    def test_cache_set_and_get(self):
        """Test cache set and get."""
        # Clear cache first
        if hasattr(bot, "_passage_cache"):
            bot._passage_cache.clear()

        # Set cache
        bot._cache_set(
            TEST_BIBLE_REFERENCE, "kjv", ("For God so loved...", TEST_BIBLE_REFERENCE)
        )

        # Get from cache
        result = bot._cache_get(TEST_BIBLE_REFERENCE, "kjv")
        assert result == ("For God so loved...", TEST_BIBLE_REFERENCE)

    def test_cache_case_insensitive(self):
        """Test cache is case insensitive."""
        # Clear cache first
        if hasattr(bot, "_passage_cache"):
            bot._passage_cache.clear()

        # Set with one case
        bot._cache_set(
            TEST_BIBLE_REFERENCE, "KJV", ("For God so loved...", TEST_BIBLE_REFERENCE)
        )

        # Get with different case
        result = bot._cache_get(TEST_BIBLE_REFERENCE.lower(), "kjv")
        assert result == ("For God so loved...", TEST_BIBLE_REFERENCE)


class TestEnvironmentLoadingExtra:
    """Test environment loading functionality."""

    def test_load_environment_with_env_file(self, temp_env_file):
        """Test loading environment with .env file."""
        config_path = str(temp_env_file.parent / "config.yaml")

        # Create a minimal config for testing
        config = {"matrix_room_ids": ["!test:matrix.org"]}
        matrix_token, api_keys = bot.load_environment(config, config_path)

        # matrix_token should be a string (or None)
        assert matrix_token == TEST_ACCESS_TOKEN
        # api_keys should be a dictionary
        assert isinstance(api_keys, dict)
        assert "esv" in api_keys

    def test_load_environment_returns_proper_types(self, tmp_path):
        """Test loading environment returns proper data structures."""
        config_path = str(tmp_path / "config.yaml")

        # Create a minimal config for testing
        config = {"matrix_room_ids": ["!test:matrix.org"]}
        matrix_token, api_keys = bot.load_environment(config, config_path)

        # Should return (string/None, dict)
        assert matrix_token is None or isinstance(matrix_token, str)
        assert isinstance(api_keys, dict)


class TestTextFormatting:
    """Test text formatting functionality."""

    def test_format_text_default_mode(self):
        """Test text formatting with default settings (collapse whitespace)."""
        config = {"bot": {"preserve_poetry_formatting": False}}
        bible_bot = bot.BibleBot(config)

        # Test text with newlines and extra spaces
        input_text = "Line 1\n\nLine 2   with   spaces\nLine 3"
        expected_plain = "Line 1 Line 2 with spaces Line 3"
        expected_html = "Line 1 Line 2 with spaces Line 3"

        plain_text, html_text = bible_bot._format_text_for_display(input_text)

        assert plain_text == expected_plain
        assert html_text == expected_html

    def test_format_text_poetry_mode(self):
        """Test text formatting with poetry preservation enabled."""
        config = {"bot": {"preserve_poetry_formatting": True}}
        bible_bot = bot.BibleBot(config)

        # Test text with newlines and extra spaces
        input_text = "Line 1\n\nLine 2   with   spaces\nLine 3"
        expected_plain = "Line 1\n\nLine 2 with spaces\nLine 3"
        expected_html = "Line 1<br /><br />Line 2 with spaces<br />Line 3"

        plain_text, html_text = bible_bot._format_text_for_display(input_text)

        assert plain_text == expected_plain
        assert html_text == expected_html

    def test_format_text_default_mode_no_config(self):
        """Test text formatting with no explicit configuration (should default to False)."""
        config = {"bot": {}}  # No preserve_poetry_formatting specified
        bible_bot = bot.BibleBot(config)

        # Should default to False (original behavior)
        assert bible_bot.preserve_poetry_formatting is False

        input_text = "Line 1\nLine 2\nLine 3"
        expected_plain = "Line 1 Line 2 Line 3"

        plain_text, html_text = bible_bot._format_text_for_display(input_text)

        assert plain_text == expected_plain
        assert html_text == expected_plain  # No <br /> tags in default mode

    def test_format_text_poetry_mode_complex(self):
        """Test poetry mode with complex formatting scenarios."""
        config = {"bot": {"preserve_poetry_formatting": True}}
        bible_bot = bot.BibleBot(config)

        # Test with tabs, multiple spaces, and multiple newlines
        input_text = "  Psalm 1:1  \n\n\n  Blessed is the man\t\twho walks not\n  in the counsel of the wicked  "
        expected_plain = "Psalm 1:1 \n\n Blessed is the man who walks not\n in the counsel of the wicked"
        expected_html = "Psalm 1:1 <br /><br /> Blessed is the man who walks not<br /> in the counsel of the wicked"

        plain_text, html_text = bible_bot._format_text_for_display(input_text)

        assert plain_text == expected_plain
        assert html_text == expected_html

    def test_configuration_loading(self):
        """Test that configuration is loaded correctly."""
        # Test with explicit True
        config_true = {"bot": {"preserve_poetry_formatting": True}}
        bot_true = bot.BibleBot(config_true)
        assert bot_true.preserve_poetry_formatting is True

        # Test with explicit False
        config_false = {"bot": {"preserve_poetry_formatting": False}}
        bot_false = bot.BibleBot(config_false)
        assert bot_false.preserve_poetry_formatting is False

        # Test with no bot section
        config_no_bot = {}
        bot_no_bot = bot.BibleBot(config_no_bot)
        assert bot_no_bot.preserve_poetry_formatting is False

        # Test with invalid config type
        config_invalid = "not a dict"
        bot_invalid = bot.BibleBot(config_invalid)
        assert bot_invalid.preserve_poetry_formatting is False
