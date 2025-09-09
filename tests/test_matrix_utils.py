from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from biblebot.auth import load_credentials, save_credentials
from biblebot.bot import BibleBot


@pytest.fixture
def mock_room():
    """
    Create a MagicMock representing a Matrix room for tests.

    Returns:
        MagicMock: Mock room object with `room_id` set to "!room:matrix.org".
    """
    mock_room = MagicMock()
    mock_room.room_id = "!room:matrix.org"
    return mock_room


@pytest.fixture
def mock_event():
    """
    Create a MagicMock representing a Matrix room message event for tests.

    The mock has these attributes set:
    - sender: "@user:matrix.org"
    - body: "John 3:16"
    - source: {"content": {"body": "John 3:16"}} (raw event content)
    - server_timestamp: 1234567890000
    - event_id: "$event123"

    Use this fixture to simulate an incoming room message requesting a verse.
    """
    mock_event = MagicMock()
    mock_event.sender = "@user:matrix.org"
    mock_event.body = "John 3:16"
    mock_event.source = {"content": {"body": "John 3:16"}}
    mock_event.server_timestamp = 1234567890000
    mock_event.event_id = "$event123"
    return mock_event


@pytest.fixture
def test_config():
    """Test configuration fixture with Matrix settings."""
    return {
        "matrix": {
            "homeserver": "https://matrix.org",
            "bot_user_id": "@biblebot:matrix.org",
            "access_token": "notasecret",  # test-only
            "room_ids": ["!room:matrix.org"],
        },
        "bible_api": {"base_url": "https://api.scripture.api.bible"},
    }


@pytest.fixture
def mock_bible_bot():
    """
    Create a MagicMock that mimics a BibleBot for tests.

    The mock is applied with spec=BibleBot and pre-populated with a minimal
    config useful for message-handling tests:
    - matrix.bot_user_id set to "@biblebot:matrix.org"
    - matrix.room_ids set to ["!room:matrix.org"]

    Returns:
        MagicMock: A mocked BibleBot instance with the above config.
    """
    mock_bot = MagicMock(spec=BibleBot)
    mock_bot.config = {
        "matrix": {
            "bot_user_id": "@biblebot:matrix.org",
            "room_ids": ["!room:matrix.org"],
        }
    }
    return mock_bot


@patch("biblebot.bot.get_bible_text", new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_bible_bot_message_handling(
    mock_get_bible_text, mock_room, mock_event, test_config
):
    """
    Verify that the bot processes a room message requesting a Bible verse and responds correctly.

    Sets up a real BibleBot with a mocked Matrix client and a mocked get_bible_text returning a verse. Ensures the bot:
    - only handles messages from supported rooms (room id present in the bot's room set),
    - ignores messages older than the bot's start_time (start_time set before the event timestamp here),
    - fetches the Bible text via get_bible_text, and
    - sends both a reaction and the verse message to the room (two room_send calls).
    """
    # Mock Bible API response
    mock_get_bible_text.return_value = ("For God so loved the world...", "John 3:16")

    # Create real BibleBot instance with mock client
    mock_client = MagicMock()
    mock_client.user_id = "@biblebot:matrix.org"
    mock_client.room_send = AsyncMock()

    bot = BibleBot(config=test_config, client=mock_client)
    bot.start_time = 1234567880000  # Before event timestamp
    # Populate room ID set for testing (normally done in initialize())
    bot._room_id_set = set(test_config["matrix"]["room_ids"])

    # Test verse request handling
    await bot.on_room_message(mock_room, mock_event)

    # Verify Bible text was fetched and both reaction and message were sent (order-agnostic)
    mock_get_bible_text.assert_called_once()
    assert mock_client.room_send.call_count == 2
    types = [c.args[1] for c in mock_client.room_send.call_args_list]
    assert "m.reaction" in types
    assert "m.room.message" in types


@patch("biblebot.bot.get_bible_text", new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_bible_bot_ignore_own_messages(
    mock_get_bible_text, mock_room, mock_event, test_config
):
    """Test that messages from the bot itself are ignored."""
    mock_event.sender = "@biblebot:matrix.org"

    # Create real BibleBot instance with mock client
    mock_client = MagicMock()
    mock_client.user_id = "@biblebot:matrix.org"
    mock_client.room_send = AsyncMock()

    bot = BibleBot(config=test_config, client=mock_client)
    bot.start_time = 1234567880000
    # Populate room ID set for testing (normally done in initialize())
    bot._room_id_set = set(test_config["matrix"]["room_ids"])

    await bot.on_room_message(mock_room, mock_event)

    # Verify no Bible text was fetched
    mock_get_bible_text.assert_not_called()


@patch("biblebot.bot.get_bible_text", new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_bible_bot_unsupported_room(
    mock_get_bible_text, mock_room, mock_event, test_config
):
    """Test that messages from unsupported rooms are ignored."""
    mock_room.room_id = "!unsupported:matrix.org"

    # Create real BibleBot instance with mock client
    mock_client = MagicMock()
    mock_client.user_id = "@biblebot:matrix.org"
    mock_client.room_send = AsyncMock()

    bot = BibleBot(config=test_config, client=mock_client)
    bot.start_time = 1234567880000
    # Populate room ID set for testing (normally done in initialize())
    bot._room_id_set = set(test_config["matrix"]["room_ids"])

    await bot.on_room_message(mock_room, mock_event)

    # Verify no Bible text was fetched
    mock_get_bible_text.assert_not_called()


@patch("biblebot.bot.get_bible_text", new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_bible_bot_api_error_handling(
    mock_get_bible_text, mock_room, mock_event, test_config
):
    """Test that API errors are handled gracefully."""
    # Mock API error by raising PassageNotFound exception
    from biblebot.bot import PassageNotFound

    mock_get_bible_text.side_effect = PassageNotFound("Test passage not found")

    # Create real BibleBot instance with mock client
    mock_client = MagicMock()
    mock_client.user_id = "@biblebot:matrix.org"
    mock_client.room_send = AsyncMock()

    bot = BibleBot(config=test_config, client=mock_client)
    bot.start_time = 1234567880000
    # Populate room ID set for testing (normally done in initialize())
    bot._room_id_set = set(test_config["matrix"]["room_ids"])

    await bot.on_room_message(mock_room, mock_event)

    # Verify error message was sent
    mock_client.room_send.assert_called_once()
    content = mock_client.room_send.call_args[0][2]
    assert (
        "error" in (content.get("formatted_body", "") + content.get("body", "")).lower()
    )


def test_load_credentials_success():
    """Test successful credentials loading."""
    import json

    with patch("biblebot.auth.credentials_path") as mock_path:
        mock_file = MagicMock()
        mock_file.exists.return_value = True
        mock_file.read_text.return_value = json.dumps(
            {
                "homeserver": "https://matrix.org",
                "user_id": "@test:matrix.org",
                "access_token": "test_token",
                "device_id": "TEST_DEVICE",
            }
        )
        mock_path.return_value = mock_file

        credentials = load_credentials()

        assert credentials is not None
        assert credentials.homeserver == "https://matrix.org"
        assert credentials.user_id == "@test:matrix.org"
        assert credentials.access_token == "test_token"  # noqa: S105
        assert credentials.device_id == "TEST_DEVICE"


@patch("biblebot.auth.credentials_path")
def test_load_credentials_file_not_exists(mock_credentials_path):
    """Test credentials loading when file doesn't exist."""
    mock_file = MagicMock()
    mock_file.exists.return_value = False
    mock_credentials_path.return_value = mock_file

    credentials = load_credentials()

    assert credentials is None


@patch("biblebot.auth.tempfile.NamedTemporaryFile")
@patch("biblebot.auth.os.replace")
@patch("biblebot.auth.os.chmod")
@patch("biblebot.auth.credentials_path")
def test_save_credentials(
    mock_credentials_path, mock_chmod, mock_replace, mock_temp_file, tmp_path
):
    """Test credentials saving with atomic write."""

    from biblebot.auth import Credentials

    # Mock credentials path to use tmp_path
    credentials_file = tmp_path / "credentials.json"
    mock_credentials_path.return_value = credentials_file

    # Mock temporary file with proper fileno and fsync
    mock_temp = MagicMock()
    temp_name = str(tmp_path / "temp_file")
    mock_temp.name = temp_name
    mock_temp.fileno.return_value = 3  # Return a valid file descriptor
    mock_temp_file.return_value = mock_temp

    # Mock os.fsync and os.stat to avoid filesystem issues
    with patch("biblebot.auth.os.fsync") as mock_fsync, patch(
        "biblebot.auth.os.stat"
    ) as mock_stat:

        # Mock os.stat to simulate same filesystem (so os.replace is used)
        mock_stat_result = MagicMock()
        mock_stat_result.st_dev = 12345  # Same device ID for both temp and dest
        mock_stat.return_value = mock_stat_result

        test_credentials = Credentials(
            homeserver="https://matrix.org",
            user_id="@bot:matrix.org",
            access_token="test_token",  # noqa: S106
            device_id="TEST_DEVICE",
        )

        save_credentials(test_credentials)

        mock_temp_file.assert_called_once()
        mock_fsync.assert_called_once()  # Don't check specific args
        # Check that chmod was called with the temp file and correct permissions
        mock_chmod.assert_any_call(temp_name, 0o600)
        # Should use os.replace since we mocked same filesystem
        mock_replace.assert_called_once_with(temp_name, credentials_file)


@patch("biblebot.bot.make_api_request", new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_bible_api_verse_fetch(mock_api_request):
    """Test Bible API verse fetching."""
    # Mock API response
    mock_api_request.return_value = {
        "text": "For God so loved the world...",
        "reference": "John 3:16",
    }

    # Test verse fetching using actual function
    from biblebot.bot import get_kjv_text

    text, reference = await get_kjv_text("John 3:16")

    assert "For God so loved the world" in text
    assert "John 3:16" in reference
    mock_api_request.assert_called_once()


@patch("biblebot.bot.make_api_request", new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_bible_api_error_handling(mock_api_request):
    """Test Bible API error handling."""
    # Mock API error response
    mock_api_request.return_value = None

    # Test error handling using actual function
    from biblebot.bot import PassageNotFound, get_kjv_text

    # Should raise PassageNotFound exception
    with pytest.raises(PassageNotFound) as exc_info:
        await get_kjv_text("Invalid 99:99")

    assert "Invalid 99:99" in str(exc_info.value)
    assert "not found in KJV" in str(exc_info.value)
    mock_api_request.assert_called_once()


def test_bible_verse_parsing():
    """Test Bible verse reference parsing using existing patterns."""
    # Test with existing REFERENCE_PATTERNS

    from biblebot.bot import REFERENCE_PATTERNS

    test_cases = [
        ("John 3:16", True),
        ("1 Cor 13:4-7", True),
        ("Genesis 1:1 kjv", True),
        ("Psalm 23:1 esv", True),
        ("invalid text", False),
        ("", False),
    ]

    for text, should_match in test_cases:
        matches = any(pattern.match(text) for pattern in REFERENCE_PATTERNS)
        assert matches == should_match, f"Pattern matching failed for: {text}"


def test_bible_book_normalization():
    """Test Bible book name validation and normalization."""
    from biblebot.bot import validate_and_normalize_book_name

    valid_test_cases = [
        ("gen", "Genesis"),
        ("GEN", "Genesis"),
        ("Genesis", "Genesis"),
        ("1 cor", "1 Corinthians"),
        ("1co", "1 Corinthians"),
        ("rev", "Revelation"),
        ("ps", "Psalms"),
    ]

    for input_name, expected in valid_test_cases:
        result = validate_and_normalize_book_name(input_name)
        assert result == expected, f"Book normalization failed for: {input_name}"

    # Test invalid book names return None
    invalid_test_cases = ["unknown", "invalidbook", "xyz"]
    for invalid_name in invalid_test_cases:
        result = validate_and_normalize_book_name(invalid_name)
        assert result is None, f"Expected None for invalid book: {invalid_name}"


@pytest.mark.asyncio
async def test_matrix_client_initialization(test_config):
    """Test Matrix client initialization."""
    mock_client = MagicMock()
    mock_client.sync = AsyncMock()
    mock_client.rooms = {}
    mock_client.user_id = "@biblebot:matrix.org"

    bot = BibleBot(config=test_config, client=mock_client)
    bot.start_time = 1234567880000

    # Test that bot can be initialized with client
    assert bot.client is not None
    assert bot.config == test_config


@pytest.mark.asyncio
async def test_matrix_room_joining(test_config):
    """Test Matrix room joining functionality."""
    mock_client = MagicMock()
    mock_client.rooms = {}
    mock_client.join = AsyncMock(return_value=MagicMock(room_id="!room:matrix.org"))

    bot = BibleBot(config=test_config, client=mock_client)

    await bot.join_matrix_room("!room:matrix.org")

    mock_client.join.assert_called_once_with("!room:matrix.org")
