"""
Integration testing patterns following mmrelay's comprehensive approach.
Tests end-to-end workflows, system integration, and real-world scenarios.
"""

import asyncio
import json
import os
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from biblebot.auth import load_credentials
from biblebot.bot import BibleBot


class TestIntegrationPatterns:
    """Test end-to-end integration scenarios."""

    @pytest.fixture
    def mock_config(self):
        """Mock configuration for integration tests."""
        return {
            "homeserver": "https://matrix.org",
            "user_id": "@biblebot:matrix.org",
            "access_token": "test_token",
            "device_id": "TEST_DEVICE",
            "matrix_room_ids": ["!room1:matrix.org", "!room2:matrix.org"],
        }

    @pytest.fixture
    def mock_client(self):
        """Mock Matrix client for integration tests."""
        client = MagicMock()
        client.room_send = AsyncMock()
        client.join = AsyncMock()
        client.sync = AsyncMock()
        client.close = AsyncMock()
        return client

    async def test_full_message_workflow(self, mock_config, mock_client):
        """Test complete message processing workflow."""
        bot = BibleBot(config=mock_config, client=mock_client)
        bot.start_time = 1234567880000  # Set in milliseconds like the real bot
        bot.api_keys = {}  # Set API keys

        # Mock complete API chain
        with patch("biblebot.bot.get_bible_text") as mock_get_bible:
            mock_get_bible.return_value = (
                "For God so loved the world that he gave his one and only Son, "
                "that whoever believes in him shall not perish but have eternal life.",
                "John 3:16 (NIV)",
            )

            # Create realistic event with proper format
            event = MagicMock()
            event.body = "John 3:16"  # Use exact format that matches REFERENCE_PATTERNS
            event.sender = "@user:matrix.org"
            event.server_timestamp = 1234567890000  # Use milliseconds
            event.event_id = "$event123:matrix.org"

            room = MagicMock()
            room.room_id = "!room1:matrix.org"  # This room is in mock_config

            # Process complete workflow
            await bot.on_room_message(room, event)

            # Verify complete workflow
            assert mock_client.room_send.call_count == 2  # Reaction + message

            # Check reaction was sent
            reaction_call = mock_client.room_send.call_args_list[0]
            assert reaction_call[0][0] == "!room1:matrix.org"
            assert "m.reaction" in reaction_call[0][1]

            # Check verse message was sent
            message_call = mock_client.room_send.call_args_list[1]
            assert message_call[0][0] == "!room1:matrix.org"
            assert "m.room.message" in message_call[0][1]
            message_content = message_call[0][2]
            assert "John 3:16" in message_content["body"]
            assert "For God so loved the world" in message_content["body"]

    async def test_multi_room_integration(self, mock_config, mock_client):
        """Test bot operation across multiple rooms."""
        bot = BibleBot(config=mock_config, client=mock_client)
        bot.start_time = 1234567880000  # Set in milliseconds
        bot.api_keys = {}

        with patch("biblebot.bot.get_bible_text") as mock_get_bible:
            mock_get_bible.return_value = ("Test verse", "John 3:16")

            # Send messages from different rooms (only use configured rooms)
            rooms = [
                "!room1:matrix.org",
                "!room2:matrix.org",
            ]  # These are in mock_config

            for i, room_id in enumerate(rooms):
                event = MagicMock()
                event.body = f"John 3:{i+16}"
                event.sender = f"@user{i}:matrix.org"
                event.server_timestamp = 1234567890000 + i * 1000  # Use milliseconds

                room = MagicMock()
                room.room_id = room_id

                await bot.on_room_message(room, event)

            # Should respond in all configured rooms
            assert (
                mock_client.room_send.call_count == len(rooms) * 2
            )  # Reaction + message per room

            # Verify responses went to correct rooms
            sent_rooms = [call[0][0] for call in mock_client.room_send.call_args_list]
            for room_id in rooms:
                assert sent_rooms.count(room_id) == 2  # Reaction + message

    async def test_concurrent_user_integration(self, mock_config, mock_client):
        """Test handling multiple concurrent users."""
        bot = BibleBot(config=mock_config, client=mock_client)
        bot.start_time = 1234567880

        with patch("biblebot.bot.get_bible_text") as mock_get_bible:
            mock_get_bible.return_value = ("Test verse", "John 3:16")

            # Create events from multiple users simultaneously
            users = [f"@user{i}:matrix.org" for i in range(10)]
            tasks = []

            for i, user in enumerate(users):
                event = MagicMock()
                event.body = f"John 3:{i+16}"
                event.sender = user
                event.server_timestamp = 1234567890 + i

                room = MagicMock()
                room.room_id = "!room1:matrix.org"

                task = bot.on_room_message(room, event)
                tasks.append(task)

            # Process all concurrently
            await asyncio.gather(*tasks)

            # Should handle all users
            assert (
                mock_client.room_send.call_count == len(users) * 2
            )  # Reaction + message per user

    async def test_error_recovery_integration(self, mock_config, mock_client):
        """Test error recovery in integrated workflow."""
        bot = BibleBot(config=mock_config, client=mock_client)
        bot.start_time = 1234567880000  # Set in milliseconds
        bot.api_keys = {}

        # Mock API that fails then recovers
        call_count = 0

        async def failing_api(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise Exception("API temporarily unavailable")
            return ("Recovered verse", "John 3:16")

        with patch("biblebot.bot.get_bible_text", side_effect=failing_api):
            # Send multiple requests during failure period
            for i in range(5):
                event = MagicMock()
                event.body = f"John 3:{i+16}"
                event.sender = f"@user{i}:matrix.org"
                event.server_timestamp = 1234567890000 + i * 1000  # Use milliseconds

                room = MagicMock()
                room.room_id = "!room1:matrix.org"

                # The real bot doesn't have try/catch, so exceptions will propagate
                try:
                    await bot.on_room_message(room, event)
                except Exception:
                    pass  # Expected for first 2 calls

            # Should have attempted all requests
            assert call_count == 5

    async def test_authentication_integration(self, mock_config, mock_client):
        """Test authentication workflow integration."""
        # Test credential loading and bot initialization
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json") as f:
            credentials_data = {
                "homeserver": "https://matrix.org",
                "user_id": "@biblebot:matrix.org",
                "access_token": "integration_test_token",
                "device_id": "INTEGRATION_DEVICE",
            }
            json.dump(credentials_data, f)
            credentials_file = f.name

        try:
            with patch("biblebot.auth.credentials_path") as mock_path:
                from pathlib import Path

                mock_path.return_value = Path(credentials_file)

                # Load credentials
                credentials = load_credentials()
                assert credentials is not None
                assert credentials.access_token == "integration_test_token"

                # Use credentials with bot
                config = {
                    "homeserver": credentials.homeserver,
                    "user_id": credentials.user_id,
                    "access_token": credentials.access_token,
                    "device_id": credentials.device_id,
                    "rooms": ["!room:matrix.org"],
                }

                bot = BibleBot(config=config, client=mock_client)
                assert bot.config["access_token"] == "integration_test_token"

        finally:
            os.unlink(credentials_file)

    async def test_room_joining_integration(self, mock_config, mock_client):
        """Test room joining workflow integration."""
        bot = BibleBot(config=mock_config, client=mock_client)

        # Mock successful room join
        mock_client.join.return_value = MagicMock(room_id="!newroom:matrix.org")

        # Test joining multiple rooms
        rooms_to_join = [
            "!newroom1:matrix.org",
            "!newroom2:matrix.org",
            "!newroom3:matrix.org",
        ]

        for room_id in rooms_to_join:
            await bot.join_matrix_room(room_id)
            # join_matrix_room returns None on success in our implementation

        # Should have attempted to join all rooms
        assert mock_client.join.call_count == len(rooms_to_join)

    async def test_message_formatting_integration(self, mock_config, mock_client):
        """Test message formatting in integrated workflow."""
        bot = BibleBot(config=mock_config, client=mock_client)
        bot.start_time = 1234567880

        with patch("biblebot.bot.get_bible_text") as mock_get_bible:
            mock_get_bible.return_value = (
                "In the beginning was the Word, and the Word was with God, and the Word was God.",
                "John 1:1 (NIV)",
            )

            event = MagicMock()
            event.body = "John 1:1"
            event.sender = "@user:matrix.org"
            event.server_timestamp = 1234567890

            room = MagicMock()
            room.room_id = "!room1:matrix.org"

            await bot.on_room_message(room, event)

            # Check message formatting
            message_call = [
                call
                for call in mock_client.room_send.call_args_list
                if call[0][1] == "m.room.message"
            ][0]
            content = message_call[0][2]

            # Should have both plain and formatted content
            assert "body" in content
            assert "formatted_body" in content
            assert content["format"] == "org.matrix.custom.html"

            # Content should include verse and reference
            assert "In the beginning was the Word" in content["body"]
            assert "John 1:1" in content["body"]

    async def test_api_integration_chain(self, mock_config, mock_client):
        """Test complete API integration chain."""
        bot = BibleBot(config=mock_config, client=mock_client)
        bot.start_time = 1234567880

        # Mock the entire API chain
        with patch("biblebot.bot.make_api_request") as mock_api:
            mock_api.return_value = {
                "text": "For God so loved the world that he gave his one and only Son",
                "reference": "John 3:16",
                "version": "NIV",
            }

            event = MagicMock()
            event.body = "Show me John 3:16"
            event.sender = "@user:matrix.org"
            event.server_timestamp = 1234567890

            room = MagicMock()
            room.room_id = "!room1:matrix.org"

            await bot.on_room_message(room, event)

            # Verify API was called
            mock_api.assert_called_once()

            # Verify response was sent
            assert mock_client.room_send.call_count == 2  # Reaction + message

    async def test_configuration_integration(self, mock_config, mock_client):
        """Test configuration handling integration."""
        # Test with various configuration scenarios
        configs = [
            # Minimal config
            {
                "homeserver": "https://matrix.org",
                "user_id": "@test:matrix.org",
                "access_token": "token",
                "device_id": "device",
            },
            # Full config
            {
                "homeserver": "https://matrix.org",
                "user_id": "@test:matrix.org",
                "access_token": "token",
                "device_id": "device",
                "rooms": ["!room1:matrix.org", "!room2:matrix.org"],
                "bible_version": "NIV",
                "response_format": "html",
            },
        ]

        for config in configs:
            bot = BibleBot(config=config, client=mock_client)

            # Should handle all configuration variants
            assert bot.config["homeserver"] == config["homeserver"]
            assert bot.config["user_id"] == config["user_id"]

    async def test_lifecycle_integration(self, mock_config, mock_client):
        """Test complete bot lifecycle integration."""
        # Test initialization
        bot = BibleBot(config=mock_config, client=mock_client)
        assert bot.client is not None
        assert bot.config is not None

        # Test operation
        bot.start_time = 1234567880

        with patch("biblebot.bot.get_bible_text") as mock_get_bible:
            mock_get_bible.return_value = ("Test verse", "John 3:16")

            event = MagicMock()
            event.body = "John 3:16"
            event.sender = "@user:matrix.org"
            event.server_timestamp = 1234567890

            room = MagicMock()
            room.room_id = "!room1:matrix.org"

            await bot.on_room_message(room, event)

        # Test cleanup (simulated)
        bot.client = None
        bot.config = None

        # Should complete lifecycle without errors
        assert True  # If we get here, lifecycle completed successfully

    async def test_stress_integration(self, mock_config, mock_client):
        """Test system under stress conditions."""
        bot = BibleBot(config=mock_config, client=mock_client)
        bot.start_time = 1234567880000  # Use milliseconds
        bot.api_keys = {}

        with patch("biblebot.bot.get_bible_text") as mock_get_bible:
            mock_get_bible.return_value = ("Test verse", "John 3:16")

            # Create many concurrent requests
            tasks = []
            for i in range(50):
                event = MagicMock()
                event.body = f"John 3:{i+1}"
                event.sender = f"@user{i % 10}:matrix.org"  # 10 different users
                event.server_timestamp = 1234567890000 + i * 1000  # Use milliseconds

                room = MagicMock()
                # Use configured room IDs only
                room.room_id = mock_config["matrix_room_ids"][
                    i % len(mock_config["matrix_room_ids"])
                ]

                task = bot.on_room_message(room, event)
                tasks.append(task)

            # Process all concurrently
            await asyncio.gather(*tasks)

            # Should handle stress load
            assert mock_client.room_send.call_count == 100  # 50 reactions + 50 messages

    async def test_real_world_scenarios(self, mock_config, mock_client):
        """Test realistic real-world usage scenarios."""
        bot = BibleBot(config=mock_config, client=mock_client)
        bot.start_time = 1234567880000  # Use milliseconds
        bot.api_keys = {}

        # Scenario 1: Bible study group
        with patch("biblebot.bot.get_bible_text") as mock_get_bible:
            mock_get_bible.side_effect = [
                ("In the beginning was the Word", "John 1:1"),
                ("For God so loved the world", "John 3:16"),
                ("I can do all things through Christ", "Philippians 4:13"),
            ]

            # Use exact format that matches REFERENCE_PATTERNS regex
            study_requests = [
                "John 1:1",
                "John 3:16",
                "Philippians 4:13",
            ]

            room = MagicMock()
            room.room_id = mock_config["matrix_room_ids"][0]  # Use configured room

            for i, request in enumerate(study_requests):
                event = MagicMock()
                event.body = request
                event.sender = f"@student{i}:matrix.org"
                event.server_timestamp = 1234567890000 + i * 60000  # Use milliseconds

                await bot.on_room_message(room, event)

            # Should respond to all study requests
            assert mock_client.room_send.call_count == 6  # 3 reactions + 3 messages

        # Scenario 2: Quick reference lookup
        mock_client.room_send.reset_mock()

        with patch("biblebot.bot.get_bible_text") as mock_get_bible:
            mock_get_bible.return_value = (
                "Love is patient, love is kind",
                "1 Corinthians 13:4",
            )

            event = MagicMock()
            event.body = "1 Corinthians 13:4"
            event.sender = "@quicklookup:matrix.org"
            event.server_timestamp = 1234567890000  # Use milliseconds

            await bot.on_room_message(room, event)

            # Should provide quick response
            assert mock_client.room_send.call_count == 2  # Reaction + message
