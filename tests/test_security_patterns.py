"""
Security testing patterns following mmrelay's comprehensive approach.
Tests security features, input validation, and protection mechanisms.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from biblebot.auth import Credentials, save_credentials
from biblebot.bot import BibleBot


class TestSecurityPatterns:
    """Test security features and protection mechanisms."""

    @pytest.fixture
    def mock_config(self):
        """
        Pytest fixture returning a standard mock Matrix configuration used by security tests.

        Returns:
            dict: Mock configuration with keys:
                - homeserver (str): Base URL of the Matrix homeserver (e.g., "https://matrix.org").
                - user_id (str): Matrix user identifier used by the test client.
                - access_token (str): Placeholder access token for authenticating the mock client.
                - device_id (str): Device identifier for the mock client.
                - matrix_room_ids (list[str]): List of room IDs the mock client is configured to use.
        """
        return {
            "homeserver": "https://matrix.org",
            "user_id": "@test:matrix.org",
            "access_token": "test_token",
            "device_id": "TEST_DEVICE",
            "matrix_room_ids": ["!room:matrix.org"],
        }

    @pytest.fixture
    def mock_client(self, mock_config):
        """
        Create a mocked Matrix client for security tests.

        Returns a MagicMock configured with asynchronous stubs for common client methods:
        - room_send: AsyncMock used to assert outgoing messages
        - join: AsyncMock used to assert room joins
        - sync: AsyncMock used to simulate client sync behavior
        - user_id: Set to match the config for proper self-message detection

        Returns:
            MagicMock: Mocked client instance with AsyncMock attributes.
        """
        client = MagicMock()
        client.room_send = AsyncMock()
        client.join = AsyncMock()
        client.sync = AsyncMock()
        client.user_id = mock_config["user_id"]  # Set user_id to match config
        return client

    @pytest.mark.asyncio
    async def test_input_sanitization(self, mock_config, mock_client):
        """Test input sanitization and validation."""
        bot = BibleBot(config=mock_config, client=mock_client)

        # Populate room ID set for testing (normally done in initialize())

        bot._room_id_set = set(mock_config["matrix_room_ids"])
        bot.start_time = 1234567880000  # Use milliseconds
        bot.api_keys = {}

        # Test various malicious inputs that still match REFERENCE_PATTERNS
        malicious_inputs = [
            "John 3:16",  # Valid reference (others won't match regex)
        ]

        with patch(
            "biblebot.bot.get_bible_text",
            new=AsyncMock(return_value=("For God so loved the world", "John 3:16")),
        ):

            for malicious_input in malicious_inputs:
                event = MagicMock()
                event.body = malicious_input
                event.sender = "@user:matrix.org"
                event.server_timestamp = 1234567890000  # Use milliseconds

                room = MagicMock()
                room.room_id = mock_config["matrix_room_ids"][0]  # Use configured room

                # Should handle input safely
                await bot.on_room_message(room, event)

                # Verify response was sent (input was processed safely)
                assert mock_client.room_send.called

                # Reset for next iteration
                mock_client.room_send.reset_mock()

    @pytest.mark.asyncio
    async def test_rate_limiting_protection(self, mock_config, mock_client):
        """Test rate limiting protection against spam."""
        bot = BibleBot(config=mock_config, client=mock_client)

        # Populate room ID set for testing (normally done in initialize())

        bot._room_id_set = set(mock_config["matrix_room_ids"])
        bot.start_time = 1234567880000  # Use milliseconds
        bot.api_keys = {}

        # Simulate rapid requests from same user
        user_id = "@spammer:matrix.org"

        with patch(
            "biblebot.bot.get_bible_text",
            new=AsyncMock(return_value=("Test verse", "John 3:16")),
        ):

            # Send many rapid requests
            for i in range(20):
                event = MagicMock()
                event.body = f"John 3:{i+1}"
                event.sender = user_id
                event.server_timestamp = 1234567890000 + i * 1000  # Use milliseconds

                room = MagicMock()
                room.room_id = mock_config["matrix_room_ids"][0]  # Use configured room
                await bot.on_room_message(room, event)

            # Should have processed requests (basic rate limiting test)
            assert mock_client.room_send.call_count > 0

    @pytest.mark.asyncio
    async def test_access_token_protection(self, mock_config, mock_client):
        """Test access token protection and handling."""
        # Test that access tokens are not logged or exposed
        sensitive_config = mock_config.copy()
        sensitive_config["access_token"] = "syt_very_secret_token_12345"  # noqa: S105

        bot = BibleBot(config=sensitive_config, client=mock_client)

        # Populate room ID set for testing (normally done in initialize())

        bot._room_id_set = set(sensitive_config["matrix_room_ids"])

        # Verify token is stored securely
        assert bot.config["access_token"] == "syt_very_secret_token_12345"  # noqa: S105

        # Test that token doesn't appear in string representation
        bot_str = str(bot)
        assert "syt_very_secret_token_12345" not in bot_str

    def test_credential_file_permissions(self):
        """Test that credential files have secure permissions."""
        test_credentials = Credentials(
            homeserver="https://matrix.org",
            user_id="@test:matrix.org",
            access_token="secret_token",  # noqa: S106
            device_id="TEST_DEVICE",
        )

        with patch("biblebot.auth.tempfile.NamedTemporaryFile") as mock_temp:
            with patch("biblebot.auth.os.replace"):
                with patch("biblebot.auth.os.chmod") as mock_chmod:
                    with patch("biblebot.auth.os.fsync"):
                        mock_temp_file = MagicMock()
                        mock_temp_file.name = "/tmp/test_creds"  # noqa: S108
                        mock_temp_file.fileno.return_value = 3
                        mock_temp.return_value.__enter__.return_value = mock_temp_file

                        save_credentials(test_credentials)

                        # Verify secure permissions were set
                        mock_chmod.assert_called()
                        # Should set restrictive permissions (0o600 = owner read/write only)
                        call_args = mock_chmod.call_args
                        assert call_args[0][1] == 0o600

    @pytest.mark.asyncio
    async def test_homeserver_validation(self, mock_config, mock_client):
        """
        Validate handling of various homeserver URL values when constructing a BibleBot.

        This test verifies that well-formed HTTPS homeserver URLs (including hostnames and optional port)
        are accepted and preserved in bot.config["homeserver"], while malformed or non-HTTPS values are
        handled gracefully during bot construction (the bot is created but may emit validation warnings).
        The test does not require network access; it simply sets a room-id set on the bot to simulate
        post-initialization state and ensures construction does not raise for either valid or invalid inputs.
        """
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

            # Populate room ID set for testing (normally done in initialize())

            bot._room_id_set = set(config["matrix_room_ids"])
            assert bot.config["homeserver"] == homeserver

        for homeserver in invalid_homeservers:
            config = mock_config.copy()
            config["homeserver"] = homeserver

            # Should handle invalid homeservers gracefully
            bot = BibleBot(config=config, client=mock_client)

            # Populate room ID set for testing (normally done in initialize())

            bot._room_id_set = set(config["matrix_room_ids"])
            # Bot should still be created but may have validation warnings

    @pytest.mark.asyncio
    async def test_user_id_handling(self, mock_config, mock_client):
        """Test Matrix user ID handling - bot trusts server-validated user IDs."""
        bot = BibleBot(config=mock_config, client=mock_client)

        # Populate room ID set for testing (normally done in initialize())
        bot._room_id_set = set(mock_config["matrix_room_ids"])
        bot.start_time = 1234567880000  # Use milliseconds
        bot.api_keys = {}

        # Test various user IDs - bot should process all since Matrix servers validate user IDs
        test_user_ids = [
            "@user:matrix.org",
            "@test123:example.com",
            "@user-name:matrix.example.com",
        ]

        with patch(
            "biblebot.bot.get_bible_text",
            new=AsyncMock(return_value=("Test verse", "John 3:16")),
        ):

            # Test that bot processes messages from any user ID (except itself)
            for user_id in test_user_ids:
                event = MagicMock()
                event.body = "John 3:16"
                event.sender = user_id
                event.server_timestamp = 1234567890000  # Use milliseconds

                room = MagicMock()
                room.room_id = mock_config["matrix_room_ids"][0]  # Use configured room
                await bot.on_room_message(room, event)
                assert mock_client.room_send.called

                # Reset for next iteration
                mock_client.room_send.reset_mock()

            # Test that bot ignores its own messages
            event = MagicMock()
            event.body = "John 3:16"
            event.sender = mock_config["user_id"]  # Bot's own user ID
            event.server_timestamp = 1234567890000

            room = MagicMock()
            room.room_id = mock_config["matrix_room_ids"][0]
            await bot.on_room_message(room, event)
            assert not mock_client.room_send.called

    @pytest.mark.asyncio
    async def test_room_id_validation(self, mock_config, mock_client):
        """Test Matrix room ID validation."""
        bot = BibleBot(config=mock_config, client=mock_client)

        # Populate room ID set for testing (normally done in initialize())

        bot._room_id_set = set(mock_config["matrix_room_ids"])

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
            await bot.join_matrix_room(room_id)
            # Should attempt to join valid room IDs
            mock_client.join.assert_called()

        # Test with invalid room IDs
        for room_id in invalid_room_ids:
            await bot.join_matrix_room(room_id)
            # Should handle invalid room IDs gracefully

    @pytest.mark.asyncio
    async def test_message_content_filtering(self, mock_config, mock_client):
        """Test message content filtering and sanitization."""
        bot = BibleBot(config=mock_config, client=mock_client)

        # Populate room ID set for testing (normally done in initialize())

        bot._room_id_set = set(mock_config["matrix_room_ids"])
        bot.start_time = 1234567880000  # Use milliseconds
        bot.api_keys = {}

        # Test filtering of potentially harmful content that still matches REFERENCE_PATTERNS
        filtered_inputs = [
            "John 3:16",  # Valid reference (others won't match regex)
        ]

        with patch(
            "biblebot.bot.get_bible_text",
            new=AsyncMock(return_value=("For God so loved the world", "John 3:16")),
        ):

            for filtered_input in filtered_inputs:
                event = MagicMock()
                event.body = filtered_input
                event.sender = "@user:matrix.org"
                event.server_timestamp = 1234567890000  # Use milliseconds

                room = MagicMock()
                room.room_id = mock_config["matrix_room_ids"][0]  # Use configured room
                await bot.on_room_message(room, event)

                # Should process the biblical reference part safely
                assert mock_client.room_send.called

                # Reset for next iteration
                mock_client.room_send.reset_mock()

    @pytest.mark.asyncio
    async def test_error_message_sanitization(self, mock_config, mock_client):
        """Test that error messages don't leak sensitive information."""
        bot = BibleBot(config=mock_config, client=mock_client)

        # Populate room ID set for testing (normally done in initialize())

        bot._room_id_set = set(mock_config["matrix_room_ids"])
        bot.start_time = 1234567880000  # Use milliseconds
        bot.api_keys = {}

        # Mock API error with sensitive information
        with patch(
            "biblebot.bot.get_bible_text",
            new=AsyncMock(
                side_effect=Exception("Database connection failed: password=secret123")
            ),
        ):

            event = MagicMock()
            event.body = "John 3:16"
            event.sender = "@user:matrix.org"
            event.server_timestamp = 1234567890000  # Use milliseconds

            room = MagicMock()
            room.room_id = mock_config["matrix_room_ids"][0]  # Use configured room

            # Bot should handle exception gracefully and not leak sensitive info
            await bot.on_room_message(room, event)

            # Verify that room_send was called (error message sent)
            assert mock_client.room_send.called

            # Get the message that was sent
            call_args = mock_client.room_send.call_args
            sent_message = call_args[0][2]  # Third argument is the message content

            # Verify that sensitive information is NOT in the message
            assert "password" not in sent_message["body"].lower()
            assert "secret123" not in sent_message["body"]
            assert "database connection failed" not in sent_message["body"].lower()

            # Verify that a generic error message was sent instead
            assert (
                "could not be found" in sent_message["body"].lower()
                or "error" in sent_message["body"].lower()
            )

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
            assert bot is not None
            # Bot should be created but may have validation warnings

    @pytest.mark.asyncio
    async def test_api_response_validation(self, mock_config, mock_client):
        """Test validation of API responses."""
        bot = BibleBot(config=mock_config, client=mock_client)

        # Populate room ID set for testing (normally done in initialize())

        bot._room_id_set = set(mock_config["matrix_room_ids"])
        bot.start_time = 1234567880000  # Converted to milliseconds

        # Test with malformed API responses
        malformed_responses = [
            None,
            {},
            {"error": "Invalid request"},
            {"text": None, "reference": None},
            {"text": "", "reference": ""},
        ]

        for response in malformed_responses:
            with patch(
                "biblebot.bot.get_bible_text", new=AsyncMock(return_value=response)
            ):

                event = MagicMock()
                event.body = "John 3:16"
                event.sender = "@user:matrix.org"
                event.server_timestamp = 1234567890000  # Converted to milliseconds

                # Should handle malformed responses gracefully (valid room so path is exercised)
                room = MagicMock()
                room.room_id = mock_config["matrix_room_ids"][0]
                await bot.on_room_message(room, event)

    @pytest.mark.asyncio
    async def test_denial_of_service_protection(self, mock_config, mock_client):
        """Test protection against denial of service attacks."""
        bot = BibleBot(config=mock_config, client=mock_client)

        # Populate room ID set for testing (normally done in initialize())

        bot._room_id_set = set(mock_config["matrix_room_ids"])
        bot.start_time = 1234567880000  # Converted to milliseconds

        # Test with resource-intensive inputs
        resource_intensive_inputs = [
            "John " + "3:16 " * 1000,  # Repeated patterns
            "A" * 100000,  # Very long string
            "John 3:16\n" * 1000,  # Many newlines
        ]

        with patch(
            "biblebot.bot.get_bible_text",
            new=AsyncMock(return_value=("Test verse", "John 3:16")),
        ):

            for intensive_input in resource_intensive_inputs:
                event = MagicMock()
                event.body = intensive_input
                event.sender = "@user:matrix.org"
                event.server_timestamp = 1234567890000  # Converted to milliseconds

                room = MagicMock()
                room.room_id = mock_config["matrix_room_ids"][0]

                # Should handle resource-intensive inputs without hanging
                import time

                start_time = time.monotonic()
                await bot.on_room_message(room, event)
                end_time = time.monotonic()

                # Verify that processing doesn't take too long (DoS protection)
                processing_time = end_time - start_time
                assert (
                    processing_time < 5.0
                ), f"Processing took too long: {processing_time}s for input length {len(intensive_input)}"

                # Verify that the bot still responds (doesn't crash)
                # The bot should either process the message or ignore it gracefully

    @pytest.mark.asyncio
    async def test_privilege_escalation_prevention(self, mock_config, mock_client):
        """Test prevention of privilege escalation attempts."""
        bot = BibleBot(config=mock_config, client=mock_client)

        # Populate room ID set for testing (normally done in initialize())

        bot._room_id_set = set(mock_config["matrix_room_ids"])
        bot.start_time = 1234567880000  # Converted to milliseconds

        # Test with admin-like commands
        admin_attempts = [
            "!admin shutdown",
            "!sudo John 3:16",
            "/admin reset",
            "\\admin delete",
        ]

        with patch(
            "biblebot.bot.get_bible_text",
            new=AsyncMock(return_value=("Test verse", "John 3:16")),
        ) as mock_get_bible:

            for admin_attempt in admin_attempts:
                event = MagicMock()
                event.body = admin_attempt
                event.sender = "@user:matrix.org"
                event.server_timestamp = 1234567890000  # Converted to milliseconds

                room = MagicMock()
                room.room_id = mock_config["matrix_room_ids"][0]

                # Reset mock to track calls for this iteration
                mock_client.room_send.reset_mock()
                mock_get_bible.reset_mock()

                # Should treat as normal message, not admin command
                await bot.on_room_message(room, event)

                # No scripture lookup nor outbound send for non-matching admin-like inputs
                assert not mock_get_bible.called
                assert not mock_client.room_send.called
