"""Tests for error message handling edge cases."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from biblebot.bot import BibleBot


@pytest.fixture
def mock_config():
    """
    Return a minimal sample configuration dict used by tests.

    The returned dict contains keys expected by the code under test:
    - "matrix": configuration for Matrix client:
        - "homeserver": base URL of the homeserver.
        - "room_ids": list with a single test room id.
        - "e2ee": dict with "enabled" boolean controlling end-to-end encryption.
    - "bible_api": API settings:
        - "default_translation": default Bible translation identifier (e.g., "kjv").
    """
    return {
        "matrix": {
            "homeserver": "https://matrix.org",
            "room_ids": ["!test:matrix.org"],
            "e2ee": {"enabled": False},
        },
        "bible_api": {"default_translation": "kjv"},
    }


class TestErrorMessageHandling:
    """Test error message handling edge cases."""

    @pytest.mark.asyncio
    async def test_send_error_message_failure(self, mock_config):
        """Test _send_error_message when Matrix client fails."""
        # Create a mock client that raises an exception
        mock_client = AsyncMock()
        mock_client.room_send.side_effect = Exception("Matrix API error")

        bot = BibleBot(config=mock_config, client=mock_client)

        # This should not raise an exception, just log it
        await bot._send_error_message("!room:matrix.org", "Test error message")

        # Verify the client was called
        mock_client.room_send.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_error_message_success(self, mock_config):
        """Test _send_error_message successful case."""
        mock_client = AsyncMock()
        mock_client.room_send.return_value = None

        bot = BibleBot(config=mock_config, client=mock_client)

        await bot._send_error_message("!room:matrix.org", "Test error message")

        # Verify the message was formatted correctly
        mock_client.room_send.assert_called_once()
        call_args = mock_client.room_send.call_args

        assert call_args[0][0] == "!room:matrix.org"  # room_id
        assert call_args[0][1] == "m.room.message"  # message type

        content = call_args[0][2]
        assert content["msgtype"] == "m.text"
        assert content["body"] == "Test error message"
        assert "formatted_body" in content

    @pytest.mark.asyncio
    async def test_error_message_html_escaping(self, mock_config):
        """Test that error messages properly escape HTML."""
        mock_client = AsyncMock()
        mock_client.room_send.return_value = None

        bot = BibleBot(config=mock_config, client=mock_client)

        # Message with HTML characters that should be escaped
        message_with_html = "Error: <script>alert('xss')</script> & other chars"

        await bot._send_error_message("!room:matrix.org", message_with_html)

        call_args = mock_client.room_send.call_args
        content = call_args[0][2]

        # Body should be unescaped
        assert content["body"] == message_with_html

        # Formatted body should be HTML escaped
        formatted_body = content["formatted_body"]
        assert "&lt;script&gt;" in formatted_body
        assert "&amp;" in formatted_body
        assert (
            "alert(&#x27;xss&#x27;)" in formatted_body
            or "alert(&apos;xss&apos;)" in formatted_body
        )  # Script content should be escaped

    @pytest.mark.asyncio
    async def test_decryption_failure_e2ee_disabled(self, mock_config):
        """Test decryption failure handling when E2EE is disabled."""
        mock_client = AsyncMock()
        bot = BibleBot(config=mock_config, client=mock_client)

        # Mock event
        mock_event = MagicMock()
        mock_event.event_id = "test_event_id"

        # Mock room
        mock_room = MagicMock()
        mock_room.room_id = "!room:matrix.org"

        # Test with E2EE disabled (default in mock_config)
        with patch("biblebot.bot.logger") as mock_logger:
            await bot.on_decryption_failure(mock_room, mock_event)

            # Should log warning about E2EE being disabled
            mock_logger.warning.assert_called_once()
            warning_msg = mock_logger.warning.call_args[0][0]
            assert "E2EE is disabled in config" in warning_msg
            assert "test_event_id" in warning_msg

    @pytest.mark.asyncio
    async def test_decryption_failure_e2ee_enabled(self, mock_config):
        """Test decryption failure handling when E2EE is enabled."""
        # Enable E2EE in config
        e2ee_config = mock_config.copy()
        e2ee_config["matrix"]["e2ee"]["enabled"] = True

        mock_client = AsyncMock()
        bot = BibleBot(config=e2ee_config, client=mock_client)

        # Mock event
        mock_event = MagicMock()
        mock_event.event_id = "test_event_id"

        # Mock room
        mock_room = MagicMock()
        mock_room.room_id = "!room:matrix.org"

        # Test with E2EE enabled
        with patch("biblebot.bot.logger") as mock_logger:
            await bot.on_decryption_failure(mock_room, mock_event)

            # Should log warning about decryption failure
            mock_logger.warning.assert_called_once()
            warning_msg = mock_logger.warning.call_args[0][0]
            assert "Failed to decrypt event" in warning_msg
            assert "test_event_id" in warning_msg
            assert "usually temporary" in warning_msg
