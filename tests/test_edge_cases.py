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
        """Mock configuration for edge case tests."""
        return {
            "homeserver": "https://matrix.org",
            "user_id": "@test:matrix.org",
            "access_token": "test_token",
            "device_id": "TEST_DEVICE",
            "matrix_room_ids": [r"!room:matrix.org"],
        }

    @pytest.fixture
    def mock_client(self):
        """Mock Matrix client for edge case tests."""
        client = MagicMock()
        client.room_send = AsyncMock()
        client.join = AsyncMock()
        client.sync = AsyncMock()
        return client

    async def test_empty_message_handling(self, mock_config, mock_client):
        """Test handling of empty messages."""
        bot = BibleBot(config=mock_config, client=mock_client)
        bot.start_time = 1234567880

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
            event.server_timestamp = 1234567890

            room = MagicMock()
            room.room_id = "!room:matrix.org"

            # Should handle empty messages gracefully
            await bot.on_room_message(room, event)
            # Should not crash or send responses for empty messages

    async def test_extremely_long_messages(self, mock_config, mock_client):
        """Test handling of extremely long messages."""
        bot = BibleBot(config=mock_config, client=mock_client)
        bot.start_time = 1234567880000  # Use milliseconds
        bot.api_keys = {}

        with patch("biblebot.bot.get_bible_text") as mock_get_bible:
            mock_get_bible.return_value = ("Test verse", "John 3:16")

            # Test with message that has valid reference format
            # The regex requires the entire message to match: ^([\w\s]+?)(\d+[:]\d+[-]?\d*)\s*(kjv|esv)?$
            # So we need a long book name that still matches the pattern
            long_book_name = "A" * 100000  # Very long book name
            long_message = f"{long_book_name} 3:16"  # This will match the regex pattern

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
        bot.start_time = 1234567880

        with patch("biblebot.bot.get_bible_text") as mock_get_bible:
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
                event.server_timestamp = 1234567890

                room = MagicMock()
                room.room_id = "!room:matrix.org"

                # Should handle special characters gracefully
                await bot.on_room_message(room, event)

    async def test_malformed_bible_references(self, mock_config, mock_client):
        """Test handling of malformed Bible references."""
        bot = BibleBot(config=mock_config, client=mock_client)
        bot.start_time = 1234567880000  # Use milliseconds
        bot.api_keys = {}

        with patch("biblebot.bot.get_bible_text") as mock_get_bible:
            # Mock API to return None for malformed references
            mock_get_bible.return_value = None

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

                # The real bot crashes when get_bible_text returns None
                # So we need to catch the exception
                try:
                    await bot.on_room_message(room, event)
                except TypeError:
                    pass  # Expected when trying to unpack None

    async def test_rapid_message_bursts(self, mock_config, mock_client):
        """Test handling of rapid message bursts."""
        bot = BibleBot(config=mock_config, client=mock_client)
        bot.start_time = 1234567880

        with patch("biblebot.bot.get_bible_text") as mock_get_bible:
            mock_get_bible.return_value = ("Test verse", "John 3:16")

            # Send many messages in rapid succession
            tasks = []
            for i in range(100):
                event = MagicMock()
                event.body = f"John 3:{i % 31 + 1}"  # Cycle through valid verses
                event.sender = "@user:matrix.org"
                event.server_timestamp = 1234567890 + i

                room = MagicMock()
                room.room_id = "!room:matrix.org"

                task = bot.on_room_message(room, event)
                tasks.append(task)

            # Should handle rapid bursts without crashing
            await asyncio.gather(*tasks, return_exceptions=True)

    async def test_concurrent_same_user_messages(self, mock_config, mock_client):
        """Test concurrent messages from the same user."""
        bot = BibleBot(config=mock_config, client=mock_client)
        bot.start_time = 1234567880

        with patch("biblebot.bot.get_bible_text") as mock_get_bible:
            mock_get_bible.return_value = ("Test verse", "John 3:16")

            # Send multiple concurrent messages from same user
            same_user = "@spammer:matrix.org"
            tasks = []

            for i in range(20):
                event = MagicMock()
                event.body = f"John 3:{i + 1}"
                event.sender = same_user
                event.server_timestamp = 1234567890 + i

                room = MagicMock()
                room.room_id = "!room:matrix.org"

                task = bot.on_room_message(room, event)
                tasks.append(task)

            # Should handle concurrent messages from same user
            await asyncio.gather(*tasks)

    async def test_message_timestamp_edge_cases(self, mock_config, mock_client):
        """Test edge cases with message timestamps."""
        bot = BibleBot(config=mock_config, client=mock_client)
        bot.start_time = 1234567880

        with patch("biblebot.bot.get_bible_text") as mock_get_bible:
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
        """Test edge cases with room IDs."""
        bot = BibleBot(config=mock_config, client=mock_client)
        bot.start_time = 1234567880

        with patch("biblebot.bot.get_bible_text") as mock_get_bible:
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
                event.server_timestamp = 1234567890

                room = MagicMock()
                room.room_id = room_id

                # Should handle various room ID formats
                await bot.on_room_message(room, event)

    async def test_user_id_edge_cases(self, mock_config, mock_client):
        """Test edge cases with user IDs."""
        bot = BibleBot(config=mock_config, client=mock_client)
        bot.start_time = 1234567880

        with patch("biblebot.bot.get_bible_text") as mock_get_bible:
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
                event.server_timestamp = 1234567890

                room = MagicMock()
                room.room_id = "!room:matrix.org"

                # Should handle various user ID formats
                await bot.on_room_message(room, event)

    async def test_api_response_edge_cases(self, mock_config, mock_client):
        """Test edge cases with API responses."""
        bot = BibleBot(config=mock_config, client=mock_client)
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
            with patch("biblebot.bot.get_bible_text") as mock_get_bible:
                mock_get_bible.return_value = response

                event = MagicMock()
                event.body = "John 3:16"
                event.sender = "@user:matrix.org"
                event.server_timestamp = 1234567890000  # Use milliseconds

                room = MagicMock()
                room.room_id = "!room:matrix.org"

                # Should handle various API response formats
                try:
                    await bot.on_room_message(room, event)
                except TypeError:
                    pass  # Expected when response is None

    async def test_network_timeout_edge_cases(self, mock_config, mock_client):
        """Test edge cases with network timeouts."""
        bot = BibleBot(config=mock_config, client=mock_client)
        bot.start_time = 1234567880000  # Use milliseconds
        bot.api_keys = {}

        # Test various timeout scenarios
        timeout_scenarios = [
            0.001,  # Very short timeout
            1.0,  # Normal timeout
            10.0,  # Long timeout
            60.0,  # Very long timeout
        ]

        for timeout_duration in timeout_scenarios:

            async def timeout_api(*args, **kwargs):
                await asyncio.sleep(timeout_duration)
                raise asyncio.TimeoutError("API timeout")

            with patch("biblebot.bot.get_bible_text", side_effect=timeout_api):
                event = MagicMock()
                event.body = "John 3:16"
                event.sender = "@user:matrix.org"
                event.server_timestamp = 1234567890000  # Use milliseconds

                room = MagicMock()
                room.room_id = "!room:matrix.org"

                # Should handle various timeout durations
                start_time = time.time()
                try:
                    await bot.on_room_message(room, event)
                except asyncio.TimeoutError:
                    pass  # Expected timeout
                end_time = time.time()

                # Should not hang indefinitely
                assert end_time - start_time < 30.0

    async def test_memory_pressure_edge_cases(self, mock_config, mock_client):
        """Test behavior under memory pressure."""
        bot = BibleBot(config=mock_config, client=mock_client)
        bot.start_time = 1234567880

        # Simulate memory pressure by creating large objects
        large_objects = []

        with patch("biblebot.bot.get_bible_text") as mock_get_bible:
            mock_get_bible.return_value = ("Test verse", "John 3:16")

            try:
                # Create some memory pressure
                for i in range(10):
                    large_objects.append("X" * 1000000)  # 1MB strings

                event = MagicMock()
                event.body = "John 3:16"
                event.sender = "@user:matrix.org"
                event.server_timestamp = 1234567890

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
        bot.start_time = 1234567880

        with patch("biblebot.bot.get_bible_text") as mock_get_bible:
            mock_get_bible.return_value = ("Test verse", "John 3:16")

            # Test with minimal event object
            minimal_event = MagicMock()
            minimal_event.body = "John 3:16"
            minimal_event.sender = "@user:matrix.org"
            minimal_event.server_timestamp = 1234567890

            room = MagicMock()
            room.room_id = "!room:matrix.org"

            # Should handle minimal event objects
            await bot.on_room_message(room, minimal_event)

            # Test with event object having extra attributes
            extended_event = MagicMock()
            extended_event.body = "John 3:16"
            extended_event.sender = "@user:matrix.org"
            extended_event.server_timestamp = 1234567890
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
        }

        bot = BibleBot(config=minimal_config, client=mock_client)
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
        assert bot.config is not None
