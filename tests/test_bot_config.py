"""Tests for bot configuration settings."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from biblebot.bot import BibleBot, _cache_get, _cache_set, get_bible_text, load_config


class TestBotConfiguration:
    """Test bot configuration loading and settings."""

    def test_bot_default_settings(self):
        """Test bot with default settings when no bot config provided."""
        config = {"matrix_room_ids": ["!test:example.org"]}
        bot = BibleBot(config)

        assert bot.default_translation == "kjv"
        assert bot.cache_enabled is True
        assert bot.max_message_length == 2000

    def test_bot_custom_settings(self):
        """Test bot with custom settings."""
        config = {
            "matrix_room_ids": ["!test:example.org"],
            "bot": {
                "default_translation": "esv",
                "cache_enabled": False,
                "max_message_length": 1500,
            },
        }
        bot = BibleBot(config)

        assert bot.default_translation == "esv"
        assert bot.cache_enabled is False
        assert bot.max_message_length == 1500

    def test_bot_partial_settings(self):
        """Test bot with partial custom settings."""
        config = {
            "matrix_room_ids": ["!test:example.org"],
            "bot": {
                "default_translation": "esv"
                # cache_enabled and max_message_length should use defaults
            },
        }
        bot = BibleBot(config)

        assert bot.default_translation == "esv"
        assert bot.cache_enabled is True  # default
        assert bot.max_message_length == 2000  # default

    def test_bot_invalid_max_message_length(self):
        """Test bot with invalid max_message_length falls back to default."""
        config = {
            "matrix_room_ids": ["!test:example.org"],
            "bot": {"max_message_length": -100},  # invalid
        }

        with patch("biblebot.bot.logger") as mock_logger:
            bot = BibleBot(config)

            assert bot.max_message_length == 2000  # should use default
            mock_logger.warning.assert_called_once()

    def test_bot_non_dict_config(self):
        """Test bot handles non-dict config gracefully."""
        config = None
        bot = BibleBot(config)

        assert bot.default_translation == "kjv"
        assert bot.cache_enabled is True
        assert bot.max_message_length == 2000


class TestCacheConfiguration:
    """Test cache behavior with configuration."""

    def test_cache_enabled(self):
        """Test cache works when enabled."""
        # Set a value in cache
        _cache_set(
            "John 3:16", "kjv", ("For God so loved...", "John 3:16"), cache_enabled=True
        )

        # Should retrieve from cache
        result = _cache_get("John 3:16", "kjv", cache_enabled=True)
        assert result is not None
        assert result[0] == "For God so loved..."

    def test_cache_disabled_get(self):
        """Test cache get returns None when disabled."""
        # Set a value in cache first
        _cache_set(
            "John 3:16", "kjv", ("For God so loved...", "John 3:16"), cache_enabled=True
        )

        # Should not retrieve from cache when disabled
        result = _cache_get("John 3:16", "kjv", cache_enabled=False)
        assert result is None

    def test_cache_disabled_set(self):
        """Test cache set does nothing when disabled."""
        # Clear any existing cache
        from biblebot.bot import _passage_cache

        _passage_cache.clear()

        # Try to set with cache disabled
        _cache_set(
            "John 3:16",
            "kjv",
            ("For God so loved...", "John 3:16"),
            cache_enabled=False,
        )

        # Cache should still be empty
        assert len(_passage_cache) == 0


class TestGetBibleTextConfiguration:
    """Test get_bible_text with configuration options."""

    @pytest.mark.asyncio
    async def test_get_bible_text_custom_default_translation(self):
        """Test get_bible_text uses custom default translation."""
        with patch(
            "biblebot.bot.get_kjv_text",
            new=AsyncMock(return_value=("KJV text", "John 3:16")),
        ) as mock_kjv:
            with patch(
                "biblebot.bot.get_esv_text",
                new=AsyncMock(return_value=("ESV text", "John 3:16")),
            ) as mock_esv:
                # Test with custom default translation
                result = await get_bible_text(
                    "John 3:16",
                    translation=None,  # Should use default
                    default_translation="esv",
                )

                assert result[0] == "ESV text"
                mock_esv.assert_called_once()
                mock_kjv.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_bible_text_cache_disabled(self):
        """Test get_bible_text with cache disabled."""
        with patch(
            "biblebot.bot.get_kjv_text",
            new=AsyncMock(return_value=("KJV text", "John 3:16")),
        ) as mock_kjv:
            with patch("biblebot.bot._cache_get", return_value=None) as mock_cache_get:
                with patch("biblebot.bot._cache_set") as mock_cache_set:
                    result = await get_bible_text(
                        "John 3:16", "kjv", cache_enabled=False
                    )

                    assert result[0] == "KJV text"
                    mock_kjv.assert_called_once()
                    mock_cache_get.assert_called_once_with("John 3:16", "kjv", False)
                    mock_cache_set.assert_called_once_with(
                        "John 3:16", "kjv", ("KJV text", "John 3:16"), False
                    )


class TestConfigurationLoading:
    """Test configuration file loading with new structure."""

    def test_load_config_new_structure(self, tmp_path):
        """Test loading config with new nested structure."""
        config_file = tmp_path / "config.yaml"
        config_content = """
matrix:
  room_ids:
    - "!test:example.org"
  e2ee:
    enabled: true

bot:
  default_translation: "esv"
  cache_enabled: false
  max_message_length: 1500
"""
        config_file.write_text(config_content)

        config = load_config(str(config_file))

        assert config is not None
        assert config["matrix_room_ids"] == [
            "!test:example.org"
        ]  # backward compatibility
        assert config["matrix"]["room_ids"] == ["!test:example.org"]
        assert config["matrix"]["e2ee"]["enabled"] is True
        assert config["bot"]["default_translation"] == "esv"
        assert config["bot"]["cache_enabled"] is False
        assert config["bot"]["max_message_length"] == 1500

    def test_load_config_legacy_structure(self, tmp_path):
        """Test loading config with legacy flat structure."""
        config_file = tmp_path / "config.yaml"
        config_content = """
matrix_homeserver: https://matrix.org
matrix_user: "@bot:matrix.org"
matrix_room_ids:
  - "!test:example.org"

bot:
  default_translation: "esv"
"""
        config_file.write_text(config_content)

        config = load_config(str(config_file))

        assert config is not None
        # Should convert to nested structure
        assert config["matrix"]["homeserver"] == "https://matrix.org"
        assert config["matrix"]["user"] == "@bot:matrix.org"
        assert config["matrix"]["room_ids"] == ["!test:example.org"]
        # Should maintain backward compatibility
        assert config["matrix_room_ids"] == ["!test:example.org"]
        assert config["bot"]["default_translation"] == "esv"

    def test_load_config_missing_room_ids(self, tmp_path):
        """Test loading config with missing room_ids."""
        config_file = tmp_path / "config.yaml"
        config_content = """
bot:
  default_translation: "esv"
"""
        config_file.write_text(config_content)

        config = load_config(str(config_file))

        assert config is None  # Should fail validation

    def test_load_config_invalid_room_ids(self, tmp_path):
        """Test loading config with invalid room_ids type."""
        config_file = tmp_path / "config.yaml"
        config_content = """
matrix_room_ids: "not_a_list"
"""
        config_file.write_text(config_content)

        config = load_config(str(config_file))

        assert config is None  # Should fail validation


class TestMessageTruncation:
    """Test message truncation functionality."""

    @pytest.mark.asyncio
    async def test_handle_scripture_command_no_truncation(self):
        """Test handle_scripture_command with short message (no truncation needed)."""
        config = {
            "matrix_room_ids": ["!test:example.org"],
            "bot": {"max_message_length": 1000},
        }

        mock_client = AsyncMock()
        bot = BibleBot(config, mock_client)
        bot.api_keys = {}
        bot._room_id_set = {"!test:example.org"}

        mock_event = MagicMock()
        mock_event.event_id = "$event:matrix.org"

        short_text = "For God so loved the world"
        with patch(
            "biblebot.bot.get_bible_text",
            new=AsyncMock(return_value=(short_text, "John 3:16")),
        ):
            await bot.handle_scripture_command(
                "!test:example.org", "John 3:16", "kjv", mock_event
            )

            # Should send both reaction and message
            assert mock_client.room_send.call_count == 2

            # Assert the first send is a reaction and the second is a message
            calls = mock_client.room_send.call_args_list
            reaction_call = calls[0]
            message_call = calls[1]

            # Check reaction event type
            reaction_content = reaction_call[0][2]
            assert reaction_content.get("msgtype") == "m.reaction"

            # Check the message call (second call)
            content = message_call[0][2]

            assert short_text in content["body"]
            assert "..." not in content["body"]

    @pytest.mark.asyncio
    async def test_handle_scripture_command_with_truncation(self):
        """Test handle_scripture_command with long message (truncation needed)."""
        config = {
            "matrix_room_ids": ["!test:example.org"],
            "bot": {"max_message_length": 50},  # Very short limit
        }

        mock_client = AsyncMock()
        bot = BibleBot(config, mock_client)
        bot.api_keys = {}
        bot._room_id_set = {"!test:example.org"}

        mock_event = MagicMock()
        mock_event.event_id = "$event:matrix.org"

        long_text = "This is a very long Bible verse that should definitely be truncated because it exceeds the maximum message length"
        with patch(
            "biblebot.bot.get_bible_text",
            new=AsyncMock(return_value=(long_text, "John 3:16")),
        ):
            await bot.handle_scripture_command(
                "!test:example.org", "John 3:16", "kjv", mock_event
            )

            # Should send both reaction and message
            assert mock_client.room_send.call_count == 2

            # Assert the first send is a reaction and the second is a message
            calls = mock_client.room_send.call_args_list
            reaction_call = calls[0]
            message_call = calls[1]

            # Check reaction event type
            reaction_content = reaction_call[0][2]
            assert reaction_content.get("msgtype") == "m.reaction"

            # Check the message call (second call)
            content = message_call[0][2]

            assert "..." in content["body"]
            assert len(content["body"]) <= 50
            assert "John 3:16" in content["body"]  # Reference should still be included
