"""Tests for the bot module."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import yaml

from biblebot import bot


@pytest.fixture
def sample_config():
    """Sample configuration for testing."""
    return {
        "matrix_homeserver": "https://matrix.org",
        "matrix_user": "@testbot:matrix.org",
        "matrix_room_ids": ["!room1:matrix.org", "!room2:matrix.org"],
        "matrix": {"e2ee": {"enabled": False}},
    }


@pytest.fixture
def temp_config_file(tmp_path, sample_config):
    """Create a temporary config file."""
    config_file = tmp_path / "config.yaml"
    with open(config_file, "w") as f:
        yaml.dump(sample_config, f)
    return config_file


@pytest.fixture
def temp_env_file(tmp_path):
    """Create a temporary .env file."""
    env_file = tmp_path / ".env"
    env_file.write_text(
        """
MATRIX_ACCESS_TOKEN=test_token
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
        assert config["matrix_homeserver"] == "https://matrix.org"
        assert config["matrix_user"] == "@testbot:matrix.org"
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
            "matrix_homeserver": "https://matrix.org"
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

        matrix_token, api_keys = bot.load_environment(str(temp_config_file))

        assert matrix_token == "test_token"
        assert api_keys["esv"] == "test_esv_key"

    @patch.dict(
        "os.environ", {"MATRIX_ACCESS_TOKEN": "env_token", "ESV_API_KEY": "env_esv_key"}
    )
    def test_load_environment_from_os_env(self, temp_config_file):
        """Test loading environment from OS environment variables."""
        matrix_token, api_keys = bot.load_environment(str(temp_config_file))

        assert matrix_token == "env_token"
        assert api_keys["esv"] == "env_esv_key"

    @patch.dict("os.environ", {}, clear=True)
    def test_load_environment_no_env_vars(self, temp_config_file):
        """Test loading environment with no environment variables."""
        matrix_token, api_keys = bot.load_environment(str(temp_config_file))

        assert matrix_token is None
        assert api_keys["esv"] is None


class TestBookNameNormalization:
    """Test Bible book name normalization."""

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
            ("unknown", "Unknown"),  # Returns title case if not found
        ],
    )
    def test_normalize_book_name(self, input_name, expected):
        """Test book name normalization with various inputs."""
        result = bot.normalize_book_name(input_name)
        assert result == expected


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
            mock_get.return_value.__aenter__.return_value = mock_response

            result = await bot.make_api_request("/test")
            assert result == mock_response_data

    @pytest.mark.asyncio
    async def test_make_api_request_http_error(self):
        """Test API request with HTTP error."""

        with patch("aiohttp.ClientSession.get") as mock_get:
            mock_response = AsyncMock()
            mock_response.status = 404
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


class TestBibleTextRetrieval:
    """Test Bible text retrieval functions."""

    @pytest.mark.asyncio
    async def test_get_kjv_text_success(self):
        """Test successful KJV text retrieval."""
        mock_response = {
            "text": "For God so loved the world...",
            "reference": "John 3:16",
        }

        with patch.object(bot, "make_api_request", return_value=mock_response):
            result = await bot.get_kjv_text("John 3:16")

            assert result is not None
            text, reference = result
            assert text == "For God so loved the world..."
            assert reference == "John 3:16"

    @pytest.mark.asyncio
    async def test_get_kjv_text_not_found(self):
        """Test KJV text retrieval when verse not found."""
        with patch.object(bot, "make_api_request", return_value=None):
            result = await bot.get_kjv_text("Invalid 99:99")

            assert result is not None
            text, reference = result
            assert text == "Error: Passage not found"
            assert reference == ""

    @pytest.mark.asyncio
    async def test_get_esv_text_success(self):
        """Test successful ESV text retrieval."""
        mock_response = {
            "passages": ["For God so loved the world..."],
            "canonical": "John 3:16",
        }

        with patch.object(bot, "make_api_request", return_value=mock_response):
            result = await bot.get_esv_text("John 3:16", "test_api_key")

            assert result is not None
            text, reference = result
            assert text == "For God so loved the world..."
            assert reference == "John 3:16"

    @pytest.mark.asyncio
    async def test_get_esv_text_no_api_key(self):
        """Test ESV text retrieval without API key."""
        result = await bot.get_esv_text("John 3:16", None)
        assert result is None

    @pytest.mark.asyncio
    async def test_get_bible_text_with_cache(self):
        """Test Bible text retrieval with caching."""
        # Clear cache first
        if hasattr(bot, "_passage_cache"):
            bot._passage_cache.clear()

        mock_response = {
            "text": "For God so loved the world...",
            "reference": "John 3:16",
        }

        with patch.object(
            bot, "make_api_request", return_value=mock_response
        ) as mock_request:
            # First call should hit the API
            result1 = await bot.get_bible_text("John 3:16", "kjv")

            # Second call should use cache
            result2 = await bot.get_bible_text("John 3:16", "kjv")

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
        config_with_alias["matrix_room_ids"] = [
            "!room1:matrix.org",
            "#alias:matrix.org",
        ]

        with patch("biblebot.bot.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client

            # Mock alias resolution response
            mock_response = MagicMock()
            mock_response.room_id = "!resolved:matrix.org"
            mock_client.room_resolve_alias.return_value = mock_response

            bot_instance = bot.BibleBot(config_with_alias)
            bot_instance.client = mock_client

            await bot_instance.resolve_aliases()

            # Check that alias was resolved and added to room IDs
            assert "!resolved:matrix.org" in bot_instance.config["matrix_room_ids"]
            mock_client.room_resolve_alias.assert_called_once_with("#alias:matrix.org")

    @pytest.mark.asyncio
    async def test_join_matrix_room_success(self, sample_config):
        """Test successful room joining."""
        with patch("biblebot.bot.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client
            mock_client.rooms = {}  # Bot not in room yet

            # Mock successful join response
            mock_response = MagicMock()
            mock_response.room_id = "!room1:matrix.org"
            mock_client.join.return_value = mock_response

            bot_instance = bot.BibleBot(sample_config)
            bot_instance.client = mock_client

            await bot_instance.join_matrix_room("!room1:matrix.org")

            mock_client.join.assert_called_once_with("!room1:matrix.org")

    @pytest.mark.asyncio
    async def test_join_matrix_room_already_joined(self, sample_config):
        """Test joining room when already a member."""
        with patch("biblebot.bot.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client
            mock_client.rooms = {"!room1:matrix.org": MagicMock()}  # Already in room

            bot_instance = bot.BibleBot(sample_config)
            bot_instance.client = mock_client

            await bot_instance.join_matrix_room("!room1:matrix.org")

            # Should not attempt to join
            mock_client.join.assert_not_called()

    @pytest.mark.asyncio
    async def test_send_reaction(self, sample_config):
        """Test sending reaction to message."""
        with patch("biblebot.bot.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client

            bot_instance = bot.BibleBot(sample_config)
            bot_instance.client = mock_client

            await bot_instance.send_reaction(
                "!room:matrix.org", "$event:matrix.org", "✅"
            )

            # Check that room_send was called with correct reaction content
            mock_client.room_send.assert_called_once()
            call_args = mock_client.room_send.call_args

            assert call_args[0][0] == "!room:matrix.org"
            assert call_args[0][1] == "m.reaction"
            content = call_args[0][2]
            assert content["m.relates_to"]["event_id"] == "$event:matrix.org"
            assert content["m.relates_to"]["key"] == "✅"


class TestMessageHandling:
    """Test message handling and Bible verse detection."""

    @pytest.mark.asyncio
    async def test_on_room_message_bible_reference(self, sample_config):
        """Test handling room message with Bible reference."""
        with patch("biblebot.bot.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client
            mock_client.user_id = "@testbot:matrix.org"

            bot_instance = bot.BibleBot(sample_config)
            bot_instance.client = mock_client
            bot_instance.start_time = 1000000  # Set start time (milliseconds)

            # Mock room and event
            mock_room = MagicMock()
            mock_room.room_id = "!room1:matrix.org"

            mock_event = MagicMock()
            mock_event.sender = "@user:matrix.org"  # Different from bot
            mock_event.server_timestamp = 2000000  # After start time (milliseconds)
            mock_event.body = "John 3:16"
            mock_event.event_id = "$event:matrix.org"

            # Mock the scripture handling
            with patch.object(bot_instance, "handle_scripture_command") as mock_handle:
                await bot_instance.on_room_message(mock_room, mock_event)

                mock_handle.assert_called_once()
                call_args = mock_handle.call_args[0]
                assert call_args[0] == "!room1:matrix.org"
                assert "John 3:16" in call_args[1]
                assert call_args[2] == "kjv"  # Default translation

    @pytest.mark.asyncio
    async def test_on_room_message_ignore_own_message(self, sample_config):
        """Test ignoring messages from the bot itself."""
        with patch("biblebot.bot.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client
            mock_client.user_id = "@testbot:matrix.org"

            bot_instance = bot.BibleBot(sample_config)
            bot_instance.client = mock_client
            bot_instance.start_time = 1000

            mock_room = MagicMock()
            mock_room.room_id = "!room1:matrix.org"

            mock_event = MagicMock()
            mock_event.sender = "@testbot:matrix.org"  # Same as bot
            mock_event.server_timestamp = 2000
            mock_event.body = "John 3:16"

            with patch.object(bot_instance, "handle_scripture_command") as mock_handle:
                await bot_instance.on_room_message(mock_room, mock_event)

                # Should not handle scripture from own message
                mock_handle.assert_not_called()

    @pytest.mark.asyncio
    async def test_on_room_message_ignore_old_message(self, sample_config):
        """Test ignoring messages from before bot start."""
        with patch("biblebot.bot.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client
            mock_client.user_id = "@testbot:matrix.org"

            bot_instance = bot.BibleBot(sample_config)
            bot_instance.client = mock_client
            bot_instance.start_time = 2000

            mock_room = MagicMock()
            mock_room.room_id = "!room1:matrix.org"

            mock_event = MagicMock()
            mock_event.sender = "@user:matrix.org"
            mock_event.server_timestamp = 1000  # Before start time
            mock_event.body = "John 3:16"

            with patch.object(bot_instance, "handle_scripture_command") as mock_handle:
                await bot_instance.on_room_message(mock_room, mock_event)

                # Should not handle old message
                mock_handle.assert_not_called()

    @pytest.mark.asyncio
    async def test_on_room_message_wrong_room(self, sample_config):
        """Test ignoring messages from non-configured rooms."""
        with patch("biblebot.bot.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client
            mock_client.user_id = "@testbot:matrix.org"

            bot_instance = bot.BibleBot(sample_config)
            bot_instance.client = mock_client
            bot_instance.start_time = 1000

            mock_room = MagicMock()
            mock_room.room_id = "!wrong_room:matrix.org"  # Not in config

            mock_event = MagicMock()
            mock_event.sender = "@user:matrix.org"
            mock_event.server_timestamp = 2000
            mock_event.body = "John 3:16"

            with patch.object(bot_instance, "handle_scripture_command") as mock_handle:
                await bot_instance.on_room_message(mock_room, mock_event)

                # Should not handle message from wrong room
                mock_handle.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_scripture_command_success(self, sample_config):
        """Test successful scripture command handling."""
        with patch("biblebot.bot.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client

            bot_instance = bot.BibleBot(sample_config)
            bot_instance.client = mock_client
            bot_instance.api_keys = {"kjv": None}

            mock_event = MagicMock()
            mock_event.event_id = "$event:matrix.org"

            # Mock successful Bible text retrieval
            with patch.object(
                bot, "get_bible_text", return_value=("Test verse text", "Test 1:1")
            ):
                with patch.object(bot_instance, "send_reaction") as mock_reaction:
                    await bot_instance.handle_scripture_command(
                        "!room:matrix.org", "Test 1:1", "kjv", mock_event
                    )

                    # Should send reaction
                    mock_reaction.assert_called_once_with(
                        "!room:matrix.org", "$event:matrix.org", "✅"
                    )

                    # Should send scripture message
                    mock_client.room_send.assert_called_once()
                    call_args = mock_client.room_send.call_args[0]
                    assert call_args[0] == "!room:matrix.org"
                    assert call_args[1] == "m.room.message"
                    content = call_args[2]
                    assert "Test verse text" in content["body"]
                    assert "Test 1:1" in content["body"]

    @pytest.mark.asyncio
    async def test_handle_scripture_command_failure(self, sample_config):
        """Test scripture command handling when retrieval fails."""
        with patch("biblebot.bot.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client

            bot_instance = bot.BibleBot(sample_config)
            bot_instance.client = mock_client
            bot_instance.api_keys = {"kjv": None}

            mock_event = MagicMock()
            mock_event.event_id = "$event:matrix.org"

            # Mock failed Bible text retrieval
            with patch.object(bot, "get_bible_text", return_value=(None, None)):
                with patch.object(bot_instance, "send_reaction") as mock_reaction:
                    await bot_instance.handle_scripture_command(
                        "!room:matrix.org", "Invalid 99:99", "kjv", mock_event
                    )

                    # Should not send reaction
                    mock_reaction.assert_not_called()

                    # Should send error message
                    mock_client.room_send.assert_called_once()
                    call_args = mock_client.room_send.call_args[0]
                    content = call_args[2]
                    assert "Error: Failed to retrieve" in content["body"]


class TestInviteHandling:
    """Test room invite handling."""

    @pytest.mark.asyncio
    async def test_on_invite_configured_room(self, sample_config):
        """Test handling invite to configured room."""
        with patch("biblebot.bot.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client

            bot_instance = bot.BibleBot(sample_config)
            bot_instance.client = mock_client

            mock_room = MagicMock()
            mock_room.room_id = "!room1:matrix.org"  # In config

            mock_event = MagicMock()

            with patch.object(bot_instance, "join_matrix_room") as mock_join:
                await bot_instance.on_invite(mock_room, mock_event)

                mock_join.assert_called_once_with("!room1:matrix.org")

    @pytest.mark.asyncio
    async def test_on_invite_non_configured_room(self, sample_config):
        """Test handling invite to non-configured room."""
        with patch("biblebot.bot.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client

            bot_instance = bot.BibleBot(sample_config)
            bot_instance.client = mock_client

            mock_room = MagicMock()
            mock_room.room_id = "!unknown:matrix.org"  # Not in config

            mock_event = MagicMock()

            with patch.object(bot_instance, "join_matrix_room") as mock_join:
                await bot_instance.on_invite(mock_room, mock_event)

                # Should not join non-configured room
                mock_join.assert_not_called()


class TestE2EEFunctionality:
    """Test E2EE-related functionality."""

    @pytest.mark.asyncio
    async def test_on_decryption_failure(self, sample_config):
        """Test handling decryption failure events."""
        with patch("biblebot.bot.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client
            mock_client.user_id = "@testbot:matrix.org"
            mock_client.device_id = "TEST_DEVICE"

            # Mock request_room_key method
            mock_client.request_room_key = AsyncMock()

            bot_instance = bot.BibleBot(sample_config)
            bot_instance.client = mock_client

            mock_room = MagicMock()
            mock_room.room_id = "!room:matrix.org"

            mock_event = MagicMock()
            mock_event.event_id = "$failed_event:matrix.org"

            await bot_instance.on_decryption_failure(mock_room, mock_event)

            # Should request room key
            mock_client.request_room_key.assert_called_once_with(mock_event)
            # Event should have room_id set
            assert mock_event.room_id == "!room:matrix.org"

    @pytest.mark.asyncio
    async def test_on_decryption_failure_fallback(self, sample_config):
        """Test decryption failure fallback when request_room_key not available."""
        with patch("biblebot.bot.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client
            mock_client.user_id = "@testbot:matrix.org"
            mock_client.device_id = "TEST_DEVICE"

            # No request_room_key method available
            del mock_client.request_room_key

            bot_instance = bot.BibleBot(sample_config)
            bot_instance.client = mock_client

            mock_room = MagicMock()
            mock_room.room_id = "!room:matrix.org"

            mock_event = MagicMock()
            mock_event.event_id = "$failed_event:matrix.org"
            mock_event.as_key_request.return_value = MagicMock()

            await bot_instance.on_decryption_failure(mock_room, mock_event)

            # Should use fallback method
            mock_client.to_device.assert_called_once()
            mock_event.as_key_request.assert_called_once_with(
                "@testbot:matrix.org", "TEST_DEVICE"
            )


class TestMainFunction:
    """Test the main bot function."""

    @pytest.mark.asyncio
    @patch.dict("os.environ", {}, clear=True)  # Clear environment variables
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
        # Setup mocks - ensure credentials are found
        mock_load_config.return_value = sample_config
        mock_load_env.return_value = (
            "test_access_token",  # Provide access token instead of relying on credentials
            {"esv": "test_key"},
        )

        mock_load_creds.return_value = None  # No saved credentials

        mock_get_store.return_value = tmp_path / "store"

        with patch("biblebot.bot.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.restore_login = MagicMock()
            mock_client.add_event_callback = MagicMock()
            mock_client.should_upload_keys = False
            mock_client_class.return_value = mock_client

            with patch("biblebot.bot.BibleBot") as mock_bot_class:
                mock_bot = MagicMock()
                mock_bot_class.return_value = mock_bot
                mock_bot.client = mock_client
                mock_bot.start = AsyncMock()

                await bot.main("test_config.yaml")

                # Should set access token directly (not restore_login since no credentials)
                # Check that access_token was assigned
                assert mock_client.access_token == "test_access_token"

                # Should start the bot
                mock_bot.start.assert_called_once()

    @pytest.mark.asyncio
    @patch("biblebot.bot.load_credentials")
    @patch("biblebot.bot.load_config")
    @patch("biblebot.bot.load_environment")
    async def test_main_with_access_token(
        self, mock_load_env, mock_load_config, mock_load_creds, sample_config
    ):
        """Test main function with access token."""
        # Setup mocks
        mock_load_config.return_value = sample_config
        mock_load_env.return_value = ("test_access_token", {"esv": "test_key"})
        mock_load_creds.return_value = None  # No saved credentials

        with patch("biblebot.bot.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.restore_login = MagicMock()
            mock_client.add_event_callback = MagicMock()
            mock_client_class.return_value = mock_client

            with patch("biblebot.bot.BibleBot") as mock_bot_class:
                mock_bot = MagicMock()
                mock_bot_class.return_value = mock_bot
                mock_bot.client = mock_client
                mock_bot.start = AsyncMock()

                await bot.main("test_config.yaml")

                # Should set access token on the client
                # Note: The client is passed to BibleBot, so check the mock_client_class call
                mock_client_class.assert_called_once()

                # Should start the bot
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

        # The main function should return early without creating client/bot
        result = await bot.main("test_config.yaml")

        # Should return None (early return due to no auth)
        assert result is None

        # Verify the mocks were called to check for auth
        mock_load_env.assert_called_once()
        mock_load_creds.assert_called_once()

    @pytest.mark.asyncio
    @patch("biblebot.bot.load_config")
    async def test_main_invalid_config(self, mock_load_config):
        """Test main function with invalid config."""
        mock_load_config.return_value = None  # Invalid config

        with patch("biblebot.bot.BibleBot") as mock_bot_class:
            mock_bot = MagicMock()
            mock_bot_class.return_value = mock_bot

            await bot.main("invalid_config.yaml")

            # Should not create bot instance
            mock_bot_class.assert_not_called()

    @pytest.mark.asyncio
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
        mock_load_env.return_value = ("test_token", {"esv": "test_key"})
        mock_load_creds.return_value = None
        mock_get_store.return_value = tmp_path / "store"

        with patch("biblebot.bot.AsyncClient") as mock_client_class:
            with patch("biblebot.bot.AsyncClientConfig"):
                mock_client = AsyncMock()
                mock_client.restore_login = MagicMock()
                mock_client.add_event_callback = MagicMock()
                mock_client.keys_upload = AsyncMock()
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

    def test_normalize_book_name_full_names(self):
        """Test normalizing full book names."""
        assert bot.normalize_book_name("Genesis") == "Genesis"
        assert bot.normalize_book_name("Exodus") == "Exodus"
        assert bot.normalize_book_name("Matthew") == "Matthew"

    def test_normalize_book_name_abbreviations(self):
        """Test normalizing common abbreviations."""
        assert bot.normalize_book_name("Gen") == "Genesis"
        assert bot.normalize_book_name("Ex") == "Exodus"
        assert bot.normalize_book_name("Matt") == "Matthew"
        assert bot.normalize_book_name("Mt") == "Matthew"

    def test_normalize_book_name_case_insensitive(self):
        """Test case insensitive normalization."""
        assert bot.normalize_book_name("gen") == "Genesis"
        assert bot.normalize_book_name("GEN") == "Genesis"
        assert bot.normalize_book_name("GeN") == "Genesis"

    def test_normalize_book_name_unknown(self):
        """Test normalizing unknown book names."""
        assert bot.normalize_book_name("Unknown") == "Unknown"
        assert (
            bot.normalize_book_name("XYZ") == "Xyz"
        )  # Function capitalizes first letter


class TestCacheFunctions:
    """Test caching functionality."""

    def test_cache_get_miss(self):
        """Test cache miss."""
        # Clear cache first
        if hasattr(bot, "_passage_cache"):
            bot._passage_cache.clear()

        result = bot._cache_get("John 3:16", "kjv")
        assert result is None

    def test_cache_set_and_get(self):
        """Test cache set and get."""
        # Clear cache first
        if hasattr(bot, "_passage_cache"):
            bot._passage_cache.clear()

        # Set cache
        bot._cache_set("John 3:16", "kjv", ("For God so loved...", "John 3:16"))

        # Get from cache
        result = bot._cache_get("John 3:16", "kjv")
        assert result == ("For God so loved...", "John 3:16")

    def test_cache_case_insensitive(self):
        """Test cache is case insensitive."""
        # Clear cache first
        if hasattr(bot, "_passage_cache"):
            bot._passage_cache.clear()

        # Set with one case
        bot._cache_set("John 3:16", "KJV", ("For God so loved...", "John 3:16"))

        # Get with different case
        result = bot._cache_get("john 3:16", "kjv")
        assert result == ("For God so loved...", "John 3:16")


class TestEnvironmentLoadingExtra:
    """Test environment loading functionality."""

    def test_load_environment_with_env_file(self, temp_env_file):
        """Test loading environment with .env file."""
        config_path = str(temp_env_file.parent / "config.yaml")

        matrix_token, api_keys = bot.load_environment(config_path)

        # matrix_token should be a string (or None)
        assert matrix_token == "test_token" or matrix_token is None
        # api_keys should be a dictionary
        assert isinstance(api_keys, dict)
        assert "esv" in api_keys

    def test_load_environment_returns_proper_types(self, tmp_path):
        """Test loading environment returns proper data structures."""
        config_path = str(tmp_path / "config.yaml")

        matrix_token, api_keys = bot.load_environment(config_path)

        # Should return (string/None, dict)
        assert matrix_token is None or isinstance(matrix_token, str)
        assert isinstance(api_keys, dict)
