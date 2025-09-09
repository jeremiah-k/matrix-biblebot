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
        assert bot.split_message_length == 0

    @pytest.mark.parametrize(
        "bot_config, expected_value",
        [
            ({}, False),  # Default when 'bot' section is missing
            ({"bot": {}}, False),  # Default when 'bot' section is empty
            ({"bot": {"detect_references_anywhere": False}}, False),
            ({"bot": {"detect_references_anywhere": True}}, True),
            # String value handling
            ({"bot": {"detect_references_anywhere": "true"}}, True),
            ({"bot": {"detect_references_anywhere": "false"}}, False),
            ({"bot": {"detect_references_anywhere": "TRUE"}}, True),
            ({"bot": {"detect_references_anywhere": "FALSE"}}, False),
            ({"bot": {"detect_references_anywhere": "yes"}}, True),
            ({"bot": {"detect_references_anywhere": "no"}}, False),
            ({"bot": {"detect_references_anywhere": "1"}}, True),
            ({"bot": {"detect_references_anywhere": "0"}}, False),
            ({"bot": {"detect_references_anywhere": "on"}}, True),
            ({"bot": {"detect_references_anywhere": "off"}}, False),
            ({"bot": {"detect_references_anywhere": ""}}, False),
            ({"bot": {"detect_references_anywhere": "  "}}, False),
            ({"bot": {"detect_references_anywhere": None}}, False),
            ({"bot": {"detect_references_anywhere": "random"}}, False),
        ],
    )
    def test_detect_references_anywhere_setting(self, bot_config, expected_value):
        """Test detect_references_anywhere configuration setting with robust string handling."""
        config = {"matrix_room_ids": ["!test:example.org"], **bot_config}
        bot = BibleBot(config)
        assert bot.detect_references_anywhere is expected_value

    def test_bot_split_message_length_default(self):
        """Test bot with default split_message_length setting."""
        config = {"matrix_room_ids": ["!test:example.org"]}
        bot = BibleBot(config)

        assert bot.split_message_length == 0  # disabled by default

    def test_bot_split_message_length_custom(self):
        """Test bot with custom split_message_length setting."""
        config = {
            "matrix_room_ids": ["!test:example.org"],
            "bot": {"split_message_length": 200},
        }
        bot = BibleBot(config)

        assert bot.split_message_length == 200

    def test_bot_split_message_length_invalid(self):
        """Test bot with invalid split_message_length falls back to disabled."""
        config = {
            "matrix_room_ids": ["!test:example.org"],
            "bot": {"split_message_length": -50},  # invalid
        }

        with patch("biblebot.bot.logger") as mock_logger:
            bot = BibleBot(config)

            assert bot.split_message_length == 0  # should disable splitting
            mock_logger.warning.assert_called_once()

    def test_bot_split_message_length_type_validation(self):
        """Test bot with invalid split_message_length type falls back to disabled."""
        config = {
            "matrix_room_ids": ["!test:example.org"],
            "bot": {"split_message_length": "invalid"},  # string instead of int
        }

        with patch("biblebot.bot.logger") as mock_logger:
            bot = BibleBot(config)

            assert bot.split_message_length == 0  # should disable splitting
            mock_logger.warning.assert_called_once()

    def test_bot_split_message_length_capping(self):
        """Test bot caps split_message_length to max_message_length."""
        config = {
            "matrix_room_ids": ["!test:example.org"],
            "bot": {
                "split_message_length": 5000,  # larger than max_message_length
                "max_message_length": 2000,
            },
        }

        with patch("biblebot.bot.logger") as mock_logger:
            bot = BibleBot(config)

            assert bot.split_message_length == 2000  # should be capped
            mock_logger.info.assert_called_once()


class TestMessageSplitting:
    """Test message splitting functionality."""

    def test_split_text_into_chunks(self):
        """Test the _split_text_into_chunks method."""
        config = {"matrix_room_ids": ["!test:example.org"]}
        bot = BibleBot(config)

        # Test short text (no splitting needed)
        short_text = "Short text"
        chunks = bot._split_text_into_chunks(short_text, 50)
        assert chunks == ["Short text"]

        # Test text that needs splitting at word boundary
        long_text = "This is a long text that needs to be split into multiple chunks"
        chunks = bot._split_text_into_chunks(long_text, 20)
        assert len(chunks) > 1
        for chunk in chunks:
            assert len(chunk) <= 20
        # Verify all text is preserved (normalize whitespace for comparison)
        assert " ".join(chunks).split() == long_text.split()
        # No leading/trailing spaces in any chunk
        assert all(c == c.strip() for c in chunks)

        # Test text with very long word (edge case)
        text_with_long_word = "Short verylongwordthatexceedsthelimit more"
        chunks = bot._split_text_into_chunks(text_with_long_word, 10)
        assert len(chunks) > 1
        # Every produced chunk should obey the width constraint
        assert all(len(chunk) <= 10 for chunk in chunks)

    @pytest.mark.asyncio
    async def test_handle_scripture_command_with_message_splitting(self):
        """Test handle_scripture_command with message splitting enabled."""
        config = {
            "matrix_room_ids": ["!test:example.org"],
            "bot": {"split_message_length": 30},  # Short limit to force splitting
        }

        mock_client = AsyncMock()
        bot = BibleBot(config, mock_client)
        bot.api_keys = {}
        bot._room_id_set = {"!test:example.org"}

        mock_event = MagicMock()
        mock_event.event_id = "$event:matrix.org"

        long_text = "This is a very long Bible verse that should be split into multiple messages because it exceeds the split message length"
        with patch(
            "biblebot.bot.get_bible_text",
            new=AsyncMock(return_value=(long_text, "John 3:16")),
        ):
            await bot.handle_scripture_command(
                "!test:example.org", "John 3:16", "kjv", mock_event
            )

            # Should send reaction + multiple messages
            assert mock_client.room_send.call_count > 2

            # Get all message calls (skip the first reaction call)
            calls = mock_client.room_send.call_args_list
            message_calls = [call for call in calls if call[0][1] == "m.room.message"]

            # Should have multiple message parts
            assert len(message_calls) > 1

            # Check that only the last message has the reference and suffix
            from biblebot.constants.messages import MESSAGE_SUFFIX

            for i, call in enumerate(message_calls):
                content = call[0][2]
                if i == len(message_calls) - 1:  # Last message
                    assert "John 3:16" in content["body"]
                    assert MESSAGE_SUFFIX in content["body"]
                    # Last message must respect max_message_length
                    assert len(content["body"]) <= bot.max_message_length
                else:  # Earlier messages
                    assert "John 3:16" not in content["body"]
                    assert MESSAGE_SUFFIX not in content["body"]
                    # Non-final chunks must respect split_message_length
                    assert len(content["body"]) <= bot.split_message_length

    @pytest.mark.asyncio
    async def test_handle_scripture_command_splitting_disabled(self):
        """Test that splitting is disabled when split_message_length is 0."""
        config = {
            "matrix_room_ids": ["!test:example.org"],
            "bot": {
                "split_message_length": 0,  # Disabled
                "max_message_length": 50,  # Should use truncation instead
            },
        }

        mock_client = AsyncMock()
        bot = BibleBot(config, mock_client)
        bot.api_keys = {}
        bot._room_id_set = {"!test:example.org"}

        mock_event = MagicMock()
        mock_event.event_id = "$event:matrix.org"

        long_text = "This is a very long Bible verse that should be truncated not split"
        with patch(
            "biblebot.bot.get_bible_text",
            new=AsyncMock(return_value=(long_text, "John 3:16")),
        ):
            await bot.handle_scripture_command(
                "!test:example.org", "John 3:16", "kjv", mock_event
            )

            # Should send reaction + single truncated message
            assert mock_client.room_send.call_count == 2

            # Get the message call
            calls = mock_client.room_send.call_args_list
            message_call = calls[1]  # Second call should be the message
            content = message_call[0][2]

            # Should be truncated with "..."
            assert "..." in content["body"]
            assert len(content["body"]) <= 50
            assert "John 3:16" in content["body"]

    @pytest.mark.asyncio
    async def test_handle_scripture_command_splitting_respects_max_length(self):
        """Test that splitting respects max_message_length even when split_message_length is larger."""
        config = {
            "matrix_room_ids": ["!test:example.org"],
            "bot": {
                "split_message_length": 100,  # Larger than max_message_length
                "max_message_length": 50,  # Smaller limit
            },
        }

        mock_client = AsyncMock()
        bot = BibleBot(config, mock_client)
        bot.api_keys = {}
        bot._room_id_set = {"!test:example.org"}

        mock_event = MagicMock()
        mock_event.event_id = "$event:matrix.org"

        long_text = "This is a very long Bible verse that should be split but also respect the maximum message length limit"
        with patch(
            "biblebot.bot.get_bible_text",
            new=AsyncMock(return_value=(long_text, "John 3:16")),
        ):
            await bot.handle_scripture_command(
                "!test:example.org", "John 3:16", "kjv", mock_event
            )

            # Get all message calls
            calls = mock_client.room_send.call_args_list
            message_calls = [call for call in calls if call[0][1] == "m.room.message"]

            # Should have multiple message parts
            assert len(message_calls) > 1

            # All messages must respect max_message_length
            for call in message_calls:
                content = call[0][2]
                assert len(content["body"]) <= 50  # max_message_length

    @pytest.mark.asyncio
    async def test_handle_scripture_command_extremely_long_reference(self):
        """Test that extremely long references are trimmed to prevent suffix overflow."""
        config = {
            "matrix_room_ids": ["!test:example.org"],
            "bot": {
                "split_message_length": 30,
                "max_message_length": 50,  # Very small limit
            },
        }

        mock_client = AsyncMock()
        bot = BibleBot(config, mock_client)
        bot.api_keys = {}
        bot._room_id_set = {"!test:example.org"}

        mock_event = MagicMock()
        mock_event.event_id = "$event:matrix.org"

        # Very long reference that would exceed max_message_length if not trimmed
        long_reference = "This is an extremely long Bible reference that would definitely exceed the maximum message length limit if not properly trimmed"
        short_text = "Short verse text"

        with patch(
            "biblebot.bot.get_bible_text",
            new=AsyncMock(return_value=(short_text, long_reference)),
        ):
            await bot.handle_scripture_command(
                "!test:example.org", long_reference, "kjv", mock_event
            )

            # Get all message calls
            calls = mock_client.room_send.call_args_list
            message_calls = [call for call in calls if call[0][1] == "m.room.message"]

            # All messages must respect max_message_length
            for call in message_calls:
                content = call[0][2]
                assert len(content["body"]) <= 50  # max_message_length

            # At least one message should contain some form of reference (trimmed)
            assert any(
                "..." in call[0][2]["body"] or long_reference[:10] in call[0][2]["body"]
                for call in message_calls
            ), "Expected a trimmed or partial reference in at least one message"
            # Note: reference might be completely dropped if too long, so this is optional
            # The important thing is that no message exceeds the length limit

    @pytest.mark.asyncio
    async def test_handle_scripture_command_suffix_exceeds_max(self):
        """Reference + suffix longer than max_message_length should be trimmed or dropped."""
        config = {
            "matrix_room_ids": ["!test:example.org"],
            "bot": {
                "max_message_length": 20,
                "split_message_length": 0,
            },  # force single-message path
        }
        mock_client = AsyncMock()
        bot = BibleBot(config, mock_client)
        bot.api_keys = {}
        bot._room_id_set = {"!test:example.org"}
        mock_event = MagicMock()
        mock_event.event_id = "$event:matrix.org"

        long_text = "X" * 5  # short text
        with patch(
            "biblebot.bot.get_bible_text",
            new=AsyncMock(
                return_value=(long_text, "Very Long Reference That Won't Fit")
            ),
        ):
            await bot.handle_scripture_command(
                "!test:example.org", "John 3:16", "kjv", mock_event
            )

        # message is second call (after reaction)
        msg = next(
            (
                c
                for c in mock_client.room_send.call_args_list
                if c[0][1] == "m.room.message"
            ),
            None,
        )
        assert msg is not None, "No m.room.message call captured"
        body = msg[0][2]["body"]
        assert len(body) <= 20
        # Either a trimmed reference or suffix-only (implementation-dependent), but never overflow


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
        """
        Ensure that calling _cache_set with cache_enabled=False does not modify the global passage cache.

        This test clears the module-level _passage_cache, calls _cache_set with cache disabled, and asserts the cache remains empty.
        """
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

            # Check reaction event type (reactions use m.relates_to, not msgtype)
            reaction_content = reaction_call[0][2]
            assert "m.relates_to" in reaction_content

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

            # Check reaction event type (reactions use m.relates_to, not msgtype)
            reaction_content = reaction_call[0][2]
            assert "m.relates_to" in reaction_content

            # Check the message call (second call)
            content = message_call[0][2]

            assert "..." in content["body"]
            assert len(content["body"]) <= 50
            assert "John 3:16" in content["body"]  # Reference should still be included
