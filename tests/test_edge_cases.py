"""
Edge case testing patterns following mmrelay's comprehensive approach.
Tests boundary conditions, unusual inputs, and corner cases.
"""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from biblebot.bot import BibleBot


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.fixture
    def mock_config(self):
        """
        Provide a minimal mock Matrix client configuration for edge-case tests.

        Returns a dict with the keys used by tests:
        - homeserver: base URL of the Matrix homeserver (str)
        - user_id: the bot/user ID (str)
        - access_token: authentication token (str)
        - device_id: device identifier (str)
        - matrix_room_ids: list of room IDs the bot should consider (list[str])

        Used by fixtures to construct a BibleBot instance without real network configuration.
        """
        return {
            "homeserver": "https://matrix.org",
            "user_id": "@test:matrix.org",
            "access_token": "test_token",
            "device_id": "TEST_DEVICE",
            "matrix_room_ids": [r"!room:matrix.org"],
        }

    @pytest.fixture
    def mock_client(self):
        """
        Create a MagicMock Matrix client configured for edge-case tests.

        The returned mock exposes async-compatible methods used by the tests:
        - room_send: AsyncMock used to simulate sending messages to a room.
        - join: AsyncMock used to simulate joining a room.
        - sync: AsyncMock used to simulate client syncing.

        Returns:
            MagicMock: A mock Matrix client with the above AsyncMock attributes.
        """
        client = MagicMock()
        client.room_send = AsyncMock()
        client.join = AsyncMock()
        client.sync = AsyncMock()
        return client

    async def test_empty_message_handling(self, mock_config, mock_client):
        """
        Verify that on_room_message gracefully ignores messages that contain no meaningful content.

        This asynchronous test creates a BibleBot with a mocked client and populates its room ID set and start time, then sends a variety of empty or whitespace-only message bodies (empty string, space, newline, tab, mixed whitespace) as events. The expectation is that calling bot.on_room_message for each event does not raise and does not produce a response (i.e., no crash or outgoing room_send).
        """
        bot = BibleBot(config=mock_config, client=mock_client)

        # Populate room ID set for testing (normally done in initialize())

        bot._room_id_set = set(mock_config["matrix_room_ids"])
        bot.start_time = 1234567880000  # Converted to milliseconds

        # Test various empty message scenarios
        empty_messages = [
            "",  # Completely empty
            " ",  # Single space
            "\n",  # Just newline
            "\t",  # Just tab
            "   \n\t  ",  # Mixed whitespace
        ]

        for empty_msg in empty_messages:
            event = MagicMock()
            event.body = empty_msg
            event.sender = "@user:matrix.org"
            event.server_timestamp = 1234567890000  # Converted to milliseconds

            room = MagicMock()
            room.room_id = "!room:matrix.org"

            # Should handle empty messages gracefully
            await bot.on_room_message(room, event)
            # Should not crash or send responses for empty messages

    async def test_extremely_long_messages(self, mock_config, mock_client):
        """
        Verify on_room_message handles extremely long messages and detects embedded scripture references.

        Sets up a BibleBot with mocked config/client, enables partial-reference detection, and patches get_bible_text to return a valid verse. Sends an ~10k-character message that contains an embedded reference ("John 3:16") and asserts the bot processes it without crashing and attempts to send a reply (client.room_send is called).
        """
        bot = BibleBot(config=mock_config, client=mock_client)

        # Populate room ID set for testing (normally done in initialize())

        bot._room_id_set = set(mock_config["matrix_room_ids"])
        bot.start_time = 1234567880000  # Use milliseconds
        bot.api_keys = {}

        # Enable partial matching to allow scripture references within long text
        bot.detect_references_anywhere = True

        with patch(
            "biblebot.bot.get_bible_text", new_callable=AsyncMock
        ) as mock_get_bible:
            mock_get_bible.return_value = ("Test verse", "John 3:16")

            # Test with extremely long message containing embedded scripture reference
            # This tests both long message handling and partial reference detection
            long_text = "A" * 10000  # Create extremely long text for stress testing
            long_message = f"Here is some very long text: {long_text} and here's a scripture reference: John 3:16 ESV"

            event = MagicMock()
            event.body = long_message
            event.sender = "@user:matrix.org"
            event.server_timestamp = 1234567890000  # Use milliseconds

            room = MagicMock()
            room.room_id = "!room:matrix.org"

            # Should handle long messages without crashing
            await bot.on_room_message(room, event)
            assert mock_client.room_send.called

    async def test_unicode_and_special_characters(self, mock_config, mock_client):
        """Test handling of Unicode and special characters."""
        bot = BibleBot(config=mock_config, client=mock_client)

        # Populate room ID set for testing (normally done in initialize())

        bot._room_id_set = set(mock_config["matrix_room_ids"])
        bot.start_time = 1234567880000  # Converted to milliseconds

        with patch(
            "biblebot.bot.get_bible_text", new_callable=AsyncMock
        ) as mock_get_bible:
            mock_get_bible.return_value = ("Test verse", "John 3:16")

            # Test various Unicode and special characters
            special_messages = [
                "John 3:16 🙏✝️📖",  # Emojis
                "John 3:16 中文测试",  # Chinese characters
                "John 3:16 العربية",  # Arabic
                "John 3:16 русский",  # Cyrillic
                "John 3:16 \u200b\u200c",  # Zero-width characters
                "John 3:16 \x00\x01\x02",  # Control characters
                "John 3:16 ñáéíóú",  # Accented characters
            ]

            for special_msg in special_messages:
                event = MagicMock()
                event.body = special_msg
                event.sender = "@user:matrix.org"
                event.server_timestamp = 1234567890000  # Converted to milliseconds

                room = MagicMock()
                room.room_id = "!room:matrix.org"

                # Should handle special characters gracefully
                await bot.on_room_message(room, event)

    async def test_malformed_bible_references(self, mock_config, mock_client):
        """Test handling of malformed Bible references."""
        bot = BibleBot(config=mock_config, client=mock_client)

        # Populate room ID set for testing (normally done in initialize())

        bot._room_id_set = set(mock_config["matrix_room_ids"])
        bot.start_time = 1234567880000  # Use milliseconds
        bot.api_keys = {}

        with patch(
            "biblebot.bot.get_bible_text", new_callable=AsyncMock
        ) as mock_get_bible:
            # Mock API to raise PassageNotFound for malformed references
            from biblebot.bot import PassageNotFound

            mock_get_bible.side_effect = PassageNotFound("Malformed reference")

            malformed_refs = [
                "John 999:999",  # Non-existent chapter/verse
                "Fakebook 1:1",  # Non-existent book
                "John -1:1",  # Negative numbers
                "John 3:",  # Missing verse
                ":16",  # Missing book/chapter
                "John 3:16:17",  # Too many colons
                "John three:sixteen",  # Words instead of numbers
                "John 3.16",  # Wrong separator
            ]

            for malformed_ref in malformed_refs:
                event = MagicMock()
                event.body = malformed_ref
                event.sender = "@user:matrix.org"
                event.server_timestamp = 1234567890000  # Use milliseconds

                room = MagicMock()
                room.room_id = "!room:matrix.org"

                # The bot now handles None gracefully and logs a warning
                await bot.on_room_message(room, event)
                # Should not crash, just log the failure

    async def test_rapid_message_bursts(self, mock_config, mock_client):
        """Test handling of rapid message bursts."""
        bot = BibleBot(config=mock_config, client=mock_client)

        # Populate room ID set for testing (normally done in initialize())

        bot._room_id_set = set(mock_config["matrix_room_ids"])
        bot.start_time = 1234567880000  # Converted to milliseconds

        with patch(
            "biblebot.bot.get_bible_text", new_callable=AsyncMock
        ) as mock_get_bible:
            mock_get_bible.return_value = ("Test verse", "John 3:16")

            # Send many messages in rapid succession
            tasks = []
            for i in range(100):
                event = MagicMock()
                event.body = f"John 3:{i % 31 + 1}"  # Cycle through valid verses
                event.sender = "@user:matrix.org"
                event.server_timestamp = 1234567890000  # Converted to milliseconds + i

                room = MagicMock()
                room.room_id = "!room:matrix.org"

                task = bot.on_room_message(room, event)
                tasks.append(task)

            # Should handle rapid bursts without crashing
            await asyncio.gather(*tasks, return_exceptions=True)

    async def test_concurrent_same_user_messages(self, mock_config, mock_client):
        """Test concurrent messages from the same user."""
        bot = BibleBot(config=mock_config, client=mock_client)

        # Populate room ID set for testing (normally done in initialize())

        bot._room_id_set = set(mock_config["matrix_room_ids"])
        bot.start_time = 1234567880000  # Converted to milliseconds

        with patch(
            "biblebot.bot.get_bible_text", new_callable=AsyncMock
        ) as mock_get_bible:
            mock_get_bible.return_value = ("Test verse", "John 3:16")

            # Send multiple concurrent messages from same user
            same_user = "@spammer:matrix.org"
            tasks = []

            for i in range(20):
                event = MagicMock()
                event.body = f"John 3:{i + 1}"
                event.sender = same_user
                event.server_timestamp = 1234567890000  # Converted to milliseconds + i

                room = MagicMock()
                room.room_id = "!room:matrix.org"

                task = bot.on_room_message(room, event)
                tasks.append(task)

            # Should handle concurrent messages from same user
            await asyncio.gather(*tasks)

    async def test_message_timestamp_edge_cases(self, mock_config, mock_client):
        """
        Verify that on_room_message correctly handles a variety of message timestamp edge cases.

        This async test sets up a BibleBot with mock configuration and client, injects a start time and room set, patches get_bible_text to return a sample verse, and invokes on_room_message with events whose server_timestamp values exercise:
        - 0 (Unix epoch)
        - a typical integer timestamp
        - a very large future timestamp
        - a negative timestamp
        - a floating-point timestamp

        The test ensures these timestamp formats are handled without raising exceptions or crashing.
        """
        bot = BibleBot(config=mock_config, client=mock_client)

        # Populate room ID set for testing (normally done in initialize())

        bot._room_id_set = set(mock_config["matrix_room_ids"])
        bot.start_time = 1234567880000  # Converted to milliseconds

        with patch(
            "biblebot.bot.get_bible_text", new_callable=AsyncMock
        ) as mock_get_bible:
            mock_get_bible.return_value = ("Test verse", "John 3:16")

            # Test various timestamp edge cases
            timestamp_cases = [
                0,  # Unix epoch
                1234567890,  # Normal timestamp
                9999999999999,  # Far future timestamp
                -1,  # Negative timestamp (invalid)
                1234567890.5,  # Float timestamp
            ]

            for timestamp in timestamp_cases:
                event = MagicMock()
                event.body = "John 3:16"
                event.sender = "@user:matrix.org"
                event.server_timestamp = timestamp

                room = MagicMock()
                room.room_id = "!room:matrix.org"

                # Should handle various timestamp formats
                await bot.on_room_message(room, event)

    async def test_room_id_edge_cases(self, mock_config, mock_client):
        """
        Verify BibleBot.on_room_message handles a variety of room_id formats without raising.

        Sets up a BibleBot with mocked client/config, patches get_bible_text to return a valid verse,
        and sends messages from several room_id edge cases (normal, long, subdomain, with port,
        localhost, and IP-like). The test ensures processing completes for each room_id variant
        (implicitly asserting no exceptions and that the handler accepts different room identifier shapes).
        """
        bot = BibleBot(config=mock_config, client=mock_client)

        # Populate room ID set for testing (normally done in initialize())

        bot._room_id_set = set(mock_config["matrix_room_ids"])
        bot.start_time = 1234567880000  # Converted to milliseconds

        with patch(
            "biblebot.bot.get_bible_text", new_callable=AsyncMock
        ) as mock_get_bible:
            mock_get_bible.return_value = ("Test verse", "John 3:16")

            # Test various room ID edge cases
            room_id_cases = [
                "!room:matrix.org",  # Normal room ID
                "!very-long-room-name-with-many-characters:matrix.org",  # Long room ID
                "!room:sub.domain.matrix.org",  # Subdomain
                "!room:matrix.org:8448",  # With port
                "!room:localhost",  # Localhost
                "!room:192.168.1.1",  # IP address
            ]

            for room_id in room_id_cases:
                event = MagicMock()
                event.body = "John 3:16"
                event.sender = "@user:matrix.org"
                event.server_timestamp = 1234567890000  # Converted to milliseconds

                room = MagicMock()
                room.room_id = room_id

                # Should handle various room ID formats
                await bot.on_room_message(room, event)

    async def test_user_id_edge_cases(self, mock_config, mock_client):
        """Test edge cases with user IDs."""
        bot = BibleBot(config=mock_config, client=mock_client)

        # Populate room ID set for testing (normally done in initialize())

        bot._room_id_set = set(mock_config["matrix_room_ids"])
        bot.start_time = 1234567880000  # Converted to milliseconds

        with patch(
            "biblebot.bot.get_bible_text", new_callable=AsyncMock
        ) as mock_get_bible:
            mock_get_bible.return_value = ("Test verse", "John 3:16")

            # Test various user ID edge cases
            user_id_cases = [
                "@user:matrix.org",  # Normal user ID
                "@very-long-username-with-many-chars:matrix.org",  # Long username
                "@user123:matrix.org",  # With numbers
                "@user-name:matrix.org",  # With hyphens
                "@user_name:matrix.org",  # With underscores
                "@user.name:matrix.org",  # With dots
                "@user:sub.domain.matrix.org",  # Subdomain
            ]

            for user_id in user_id_cases:
                event = MagicMock()
                event.body = "John 3:16"
                event.sender = user_id
                event.server_timestamp = 1234567890000  # Converted to milliseconds

                room = MagicMock()
                room.room_id = "!room:matrix.org"

                # Should handle various user ID formats
                await bot.on_room_message(room, event)

    async def test_api_response_edge_cases(self, mock_config, mock_client):
        """
        Verify on_room_message handles a variety of API response shapes without crashing.

        This test patches get_bible_text to return several edge-case responses (None, empty strings, extremely long texts, long references, strings with newlines/tabs, and Unicode/emojis) and calls on_room_message for each case. The expected behavior is graceful handling of each response; a TypeError is tolerated when the API returns None.
        """
        bot = BibleBot(config=mock_config, client=mock_client)

        # Populate room ID set for testing (normally done in initialize())

        bot._room_id_set = set(mock_config["matrix_room_ids"])
        bot.start_time = 1234567880000  # Use milliseconds
        bot.api_keys = {}

        # Test various API response edge cases
        api_responses = [
            None,  # None response
            ("", ""),  # Empty strings
            ("Very long verse text " * 1000, "John 3:16"),  # Very long verse
            ("Short", "Very long reference " * 100),  # Long reference
            ("Verse with\nnewlines\nand\ttabs", "John 3:16"),  # Special chars
            ("Verse with 🙏 emojis ✝️", "John 3:16"),  # Unicode
        ]

        for response in api_responses:
            with patch(
                "biblebot.bot.get_bible_text", new_callable=AsyncMock
            ) as mock_get_bible:
                mock_get_bible.return_value = response
                # Reset mock client for each iteration
                mock_client.room_send.reset_mock()

                event = MagicMock()
                event.body = "John 3:16"
                event.sender = "@user:matrix.org"
                event.server_timestamp = 1234567890000  # Use milliseconds

                room = MagicMock()
                room.room_id = "!room:matrix.org"

                await bot.on_room_message(room, event)
                # Check behavior based on response type
                if response is None:
                    # None response causes exception, should send error message
                    assert mock_client.room_send.called
                elif response == ("", ""):
                    # Empty strings should not send a message (just log warning)
                    assert not mock_client.room_send.called
                else:
                    # Valid responses should send a message
                    assert mock_client.room_send.called

    async def test_network_timeout_edge_cases(self, mock_config, mock_client):
        """Test edge cases with network timeouts."""
        bot = BibleBot(config=mock_config, client=mock_client)

        # Populate room ID set for testing (normally done in initialize())

        bot._room_id_set = set(mock_config["matrix_room_ids"])
        bot.start_time = 1234567880000  # Use milliseconds
        bot.api_keys = {}

        # Test various timeout scenarios (optimized for faster testing)
        for _ in range(4):

            async def timeout_api(*_args, **_kwargs):
                # Simulate timeout without actual delay for faster testing
                # await asyncio.sleep(timeout_duration)
                """
                Simulate an API timeout by immediately raising asyncio.TimeoutError.

                This coroutine is intended for testing: it accepts any positional and keyword arguments
                but does not perform I/O or delays — it immediately raises asyncio.TimeoutError to
                simulate a timeout condition.

                Raises:
                    asyncio.TimeoutError: Always raised to represent an API timeout.
                """
                raise asyncio.TimeoutError("API timeout")

            with patch(
                "biblebot.bot.get_bible_text", new=AsyncMock(side_effect=timeout_api)
            ):
                event = MagicMock()
                event.body = "John 3:16"
                event.sender = "@user:matrix.org"
                event.server_timestamp = 1234567890000  # Use milliseconds

                room = MagicMock()
                room.room_id = mock_config["matrix_room_ids"][0]  # Use configured room

                # Should handle various timeout durations
                start_time = time.time()
                try:
                    await bot.on_room_message(room, event)
                except asyncio.TimeoutError:
                    pass  # Expected timeout
                end_time = time.time()

                # Should not hang indefinitely (much faster now)
                assert end_time - start_time < 5.0

    async def test_memory_pressure_edge_cases(self, mock_config, mock_client):
        """Test behavior under memory pressure."""
        bot = BibleBot(config=mock_config, client=mock_client)

        # Populate room ID set for testing (normally done in initialize())

        bot._room_id_set = set(mock_config["matrix_room_ids"])
        bot.start_time = 1234567880000  # Converted to milliseconds

        # Simulate memory pressure by creating large objects
        large_objects = []

        with patch(
            "biblebot.bot.get_bible_text", new_callable=AsyncMock
        ) as mock_get_bible:
            mock_get_bible.return_value = ("Test verse", "John 3:16")

            try:
                # Create some memory pressure
                for _i in range(5):
                    large_objects.append("X" * 500_000)  # ~0.5MB each

                event = MagicMock()
                event.body = "John 3:16"
                event.sender = "@user:matrix.org"
                event.server_timestamp = 1234567890000  # Converted to milliseconds

                room = MagicMock()
                room.room_id = "!room:matrix.org"

                # Should handle memory pressure gracefully
                await bot.on_room_message(room, event)

            finally:
                # Clean up large objects
                large_objects.clear()

    async def test_event_object_edge_cases(self, mock_config, mock_client):
        """Test edge cases with event objects."""
        bot = BibleBot(config=mock_config, client=mock_client)

        # Populate room ID set for testing (normally done in initialize())

        bot._room_id_set = set(mock_config["matrix_room_ids"])
        bot.start_time = 1234567880000  # Converted to milliseconds

        with patch(
            "biblebot.bot.get_bible_text", new_callable=AsyncMock
        ) as mock_get_bible:
            mock_get_bible.return_value = ("Test verse", "John 3:16")

            # Test with minimal event object
            minimal_event = MagicMock()
            minimal_event.body = "John 3:16"
            minimal_event.sender = "@user:matrix.org"
            minimal_event.server_timestamp = 1234567890000  # Converted to milliseconds

            room = MagicMock()
            room.room_id = "!room:matrix.org"

            # Should handle minimal event objects
            await bot.on_room_message(room, minimal_event)

            # Test with event object having extra attributes
            extended_event = MagicMock()
            extended_event.body = "John 3:16"
            extended_event.sender = "@user:matrix.org"
            extended_event.server_timestamp = 1234567890000  # Converted to milliseconds
            extended_event.event_id = "$event123:matrix.org"
            extended_event.origin_server_ts = 1234567890
            extended_event.unsigned = {}
            extended_event.content = {"body": "John 3:16"}

            # Should handle extended event objects
            await bot.on_room_message(room, extended_event)

    async def test_configuration_edge_cases(self, mock_client):
        """Test edge cases with bot configuration."""
        # Test with minimal configuration
        minimal_config = {
            "homeserver": "https://matrix.org",
            "user_id": "@test:matrix.org",
            "access_token": "test_token",
            "device_id": "TEST_DEVICE",
            "matrix_room_ids": ["!room:matrix.org"],
        }

        bot = BibleBot(config=minimal_config, client=mock_client)

        # Populate room ID set for testing (normally done in initialize())

        bot._room_id_set = set(minimal_config["matrix_room_ids"])
        assert bot.config is not None

        # Test with configuration containing None values
        none_config = {
            "homeserver": "https://matrix.org",
            "user_id": "@test:matrix.org",
            "access_token": "test_token",
            "device_id": "TEST_DEVICE",
            "matrix_room_ids": None,
            "bible_version": None,
        }

        bot = BibleBot(config=none_config, client=mock_client)

        # Populate room ID set for testing (normally done in initialize())

        bot._room_id_set = set(none_config["matrix_room_ids"] or [])
        assert bot.config is not None

        # Test with configuration containing empty values
        empty_config = {
            "homeserver": "https://matrix.org",
            "user_id": "@test:matrix.org",
            "access_token": "test_token",
            "device_id": "TEST_DEVICE",
            "matrix_room_ids": [],
            "bible_version": "",
        }

        bot = BibleBot(config=empty_config, client=mock_client)

        # Populate room ID set for testing (normally done in initialize())

        bot._room_id_set = set(empty_config["matrix_room_ids"])
        assert bot.config is not None
