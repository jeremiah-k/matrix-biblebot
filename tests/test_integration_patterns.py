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

pytestmark = pytest.mark.asyncio

from biblebot.auth import load_credentials  # noqa: E402
from biblebot.bot import BibleBot  # noqa: E402


class TestIntegrationPatterns:
    """Test end-to-end integration scenarios."""

    @pytest.fixture
    def mock_config(self):
        """
        Return a mock configuration dict used by integration tests.

        The dict contains the minimal fields the tests expect:
        - homeserver (str): Matrix homeserver URL.
        - user_id (str): Bot's Matrix user ID.
        - access_token (str): Token used to authenticate the mock client.
        - device_id (str): Device identifier for the bot.
        - matrix_room_ids (list[str]): List of room IDs the bot is configured to operate in.

        Returns:
            dict: Mock configuration mapping the keys above to test values.
        """
        return {
            "homeserver": "https://matrix.org",
            "user_id": "@biblebot:matrix.org",
            "access_token": "test_token",
            "device_id": "TEST_DEVICE",
            "matrix_room_ids": ["!room1:matrix.org", "!room2:matrix.org"],
        }

    @pytest.fixture
    def mock_client(self):
        """
        Create a MagicMock that simulates a Matrix client for integration tests.

        The returned mock exposes commonly used async methods as AsyncMock instances:
        - room_send: simulate sending messages to a room
        - join: simulate joining a room
        - sync: simulate the client's sync loop
        - close: simulate cleanup/close

        Returns:
            MagicMock: A mock client whose async methods can be awaited and inspected by tests.
        """
        client = MagicMock()
        client.room_send = AsyncMock()
        client.join = AsyncMock()
        client.sync = AsyncMock()
        client.close = AsyncMock()
        return client

    async def test_full_message_workflow(self, mock_config, mock_client):
        """Test complete message processing workflow."""
        bot = BibleBot(config=mock_config, client=mock_client)

        # Populate room ID set for testing (normally done in initialize())

        bot._room_id_set = set(mock_config["matrix_room_ids"])
        bot.start_time = 1234567880000  # Set in milliseconds like the real bot
        bot.api_keys = {}  # Set API keys

        # Mock complete API chain
        with patch(
            "biblebot.bot.get_bible_text", new_callable=AsyncMock
        ) as mock_get_bible:
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

            # Verify complete workflow (order-agnostic)
            assert mock_client.room_send.call_count == 2  # Reaction + message
            types = [c.args[1] for c in mock_client.room_send.call_args_list]
            assert "m.reaction" in types
            assert "m.room.message" in types
            msg_call = next(
                c
                for c in mock_client.room_send.call_args_list
                if c.args[1] == "m.room.message"
            )
            assert msg_call.args[0] == "!room1:matrix.org"
            message_content = msg_call.args[2]
            assert "John 3:16" in message_content["body"]
            assert "For God so loved the world" in message_content["body"]

    async def test_multi_room_integration(self, mock_config, mock_client):
        """Test bot operation across multiple rooms."""
        bot = BibleBot(config=mock_config, client=mock_client)

        # Populate room ID set for testing (normally done in initialize())

        bot._room_id_set = set(mock_config["matrix_room_ids"])
        bot.start_time = 1234567880000  # Set in milliseconds
        bot.api_keys = {}

        with patch(
            "biblebot.bot.get_bible_text", new_callable=AsyncMock
        ) as mock_get_bible:
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

        # Populate room ID set for testing (normally done in initialize())

        bot._room_id_set = set(mock_config["matrix_room_ids"])
        bot.start_time = 1234567880000  # Converted to milliseconds

        with patch(
            "biblebot.bot.get_bible_text", new_callable=AsyncMock
        ) as mock_get_bible:
            mock_get_bible.return_value = ("Test verse", "John 3:16")

            # Create events from multiple users simultaneously
            users = [f"@user{i}:matrix.org" for i in range(10)]
            tasks = []

            for i, user in enumerate(users):
                event = MagicMock()
                event.body = f"John 3:{i+16}"
                event.sender = user
                event.server_timestamp = 1234567890000  # Converted to milliseconds + i

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

        # Populate room ID set for testing (normally done in initialize())

        bot._room_id_set = set(mock_config["matrix_room_ids"])
        bot.start_time = 1234567880000  # Set in milliseconds
        bot.api_keys = {}

        # Mock API that fails then recovers
        call_count = 0

        async def failing_api(*args, **kwargs):
            """
            Test helper that simulates a transient API: fails on the first two calls, then returns a recovered verse.

            Raises:
                Exception: "API temporarily unavailable" for the first two invocations.

            Returns:
                tuple[str, str]: (verse_text, reference) once recovery occurs.

            Notes:
                - Increments an external `call_count` nonlocal each invocation.
                - Accepts arbitrary positional and keyword arguments (ignored).
            """
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise Exception("API temporarily unavailable")
            return ("Recovered verse", "John 3:16")

        with patch(
            "biblebot.bot.get_bible_text", new_callable=AsyncMock
        ) as mock_get_bible:
            mock_get_bible.side_effect = failing_api
            # Send multiple requests during failure period
            for i in range(5):
                event = MagicMock()
                event.body = f"John 3:{i+16}"
                event.sender = f"@user{i}:matrix.org"
                event.server_timestamp = 1234567890000 + i * 1000  # Use milliseconds

                room = MagicMock()
                room.room_id = "!room1:matrix.org"

                # All calls should complete (bot handles errors internally)
                await bot.on_room_message(room, event)

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
                assert (
                    credentials.access_token == "integration_test_token"  # noqa: S105
                )

                # Use credentials with bot
                config = {
                    "homeserver": credentials.homeserver,
                    "user_id": credentials.user_id,
                    "access_token": credentials.access_token,
                    "device_id": credentials.device_id,
                    "matrix_room_ids": ["!room:matrix.org"],
                }

                bot = BibleBot(config=config, client=mock_client)

                # Populate room ID set for testing (normally done in initialize())

                bot._room_id_set = set(config["matrix_room_ids"])
                assert (
                    bot.config["access_token"] == "integration_test_token"  # noqa: S105
                )

        finally:
            os.unlink(credentials_file)

    async def test_room_joining_integration(self, mock_config, mock_client):
        """Test room joining workflow integration."""
        bot = BibleBot(config=mock_config, client=mock_client)

        # Populate room ID set for testing (normally done in initialize())

        bot._room_id_set = set(mock_config["matrix_room_ids"])

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
        """
        Verify that when a verse is requested the bot sends a formatted Matrix message containing both plain-text and HTML-formatted content.

        This integration-style test:
        - Mocks biblebot.bot.get_bible_text to return verse text and reference.
        - Seeds the bot's configured room set and simulates an incoming room message event.
        - Asserts the bot calls the Matrix client's room_send with message content that includes both "body" and "formatted_body", uses the "org.matrix.custom.html" format, and contains the verse text and its reference in the plain body.
        """
        bot = BibleBot(config=mock_config, client=mock_client)

        # Populate room ID set for testing (normally done in initialize())

        bot._room_id_set = set(mock_config["matrix_room_ids"])
        bot.start_time = 1234567880000  # Converted to milliseconds

        with patch(
            "biblebot.bot.get_bible_text", new_callable=AsyncMock
        ) as mock_get_bible:
            mock_get_bible.return_value = (
                "In the beginning was the Word, and the Word was with God, and the Word was God.",
                "John 1:1 (NIV)",
            )

            event = MagicMock()
            event.body = "John 1:1"
            event.sender = "@user:matrix.org"
            event.server_timestamp = 1234567890000  # Converted to milliseconds

            room = MagicMock()
            room.room_id = "!room1:matrix.org"

            await bot.on_room_message(room, event)

            # Check message formatting
            message_call = next(
                c
                for c in mock_client.room_send.call_args_list
                if c.args[1] == "m.room.message"
            )
            content = message_call.args[2]

            # Should have both plain and formatted content
            assert "body" in content
            assert "formatted_body" in content
            assert content["format"] == "org.matrix.custom.html"

            # Content should include verse and reference
            assert "In the beginning was the Word" in content["body"]
            assert "John 1:1" in content["body"]

    async def test_api_integration_chain(self, mock_config, mock_client):
        """
        Verify the full API integration chain: when the external Bible API returns a verse, the bot calls the API and sends a reaction and a formatted message to the room.

        The test:
        - Creates a BibleBot with mocked config and client and populates its room set and start time.
        - Patches `make_api_request` to return a sample verse payload (text, reference, version).
        - Constructs a mock Matrix event and room and invokes `await bot.on_room_message(room, event)`.
        - Asserts the API was invoked once and the Matrix client sent two messages (a reaction and the verse message).
        """
        bot = BibleBot(config=mock_config, client=mock_client)

        # Populate room ID set for testing (normally done in initialize())

        bot._room_id_set = set(mock_config["matrix_room_ids"])
        bot.start_time = 1234567880000  # Converted to milliseconds

        # Mock the entire API chain
        with patch("biblebot.bot.make_api_request", new_callable=AsyncMock) as mock_api:
            mock_api.return_value = {
                "text": "For God so loved the world that he gave his one and only Son",
                "reference": "John 3:16",
                "version": "NIV",
            }

            event = MagicMock()
            event.body = "John 3:16"  # Exact reference to match default behavior
            event.sender = "@user:matrix.org"
            event.server_timestamp = 1234567890000  # Converted to milliseconds

            room = MagicMock()
            room.room_id = "!room1:matrix.org"

            await bot.on_room_message(room, event)

            # Verify API was called
            mock_api.assert_called_once()

            # Verify response was sent
            assert mock_client.room_send.call_count == 2  # Reaction + message

    async def test_api_integration_chain_partial_mode(self, mock_config, mock_client):
        """Test API integration with detect_references_anywhere enabled."""
        config = {**mock_config, "bot": {"detect_references_anywhere": True}}
        bot = BibleBot(config=config, client=mock_client)

        # Populate room ID set for testing
        bot._room_id_set = set(config["matrix_room_ids"])
        bot.start_time = 1234567880000
        bot.api_keys = {}

        # Mock the Bible text retrieval function
        with patch(
            "biblebot.bot.get_bible_text", new_callable=AsyncMock
        ) as mock_get_bible:
            mock_get_bible.return_value = (
                "For God so loved the world that he gave his one and only Son",
                "John 3:16",
            )

            event = MagicMock()
            event.body = (
                "Show me John 3:16 please"  # Natural sentence with embedded reference
            )
            event.sender = "@user:matrix.org"
            event.server_timestamp = 1234567890000

            room = MagicMock()
            room.room_id = "!room1:matrix.org"

            await bot.on_room_message(room, event)

            # Verify Bible text was fetched with correct parameters
            mock_get_bible.assert_called_once()
            call_args = mock_get_bible.call_args
            assert "John 3:16" in call_args[0][0]  # passage argument

            # Verify response was sent
            assert mock_client.room_send.call_count == 2  # Reaction + message
            # First call should be the reaction, second the verse message
            reaction_call = mock_client.room_send.call_args_list[0]
            assert reaction_call.args[1] == "m.reaction"
            msg = mock_client.room_send.call_args_list[1]
            assert msg.args[1] == "m.room.message"
            assert "John 3:16" in msg.args[2]["body"]

    async def test_api_integration_chain_partial_mode_disabled(
        self, mock_config, mock_client
    ):
        """Test that partial references are ignored when detect_references_anywhere is disabled (default)."""
        # Use default config (detect_references_anywhere defaults to False)
        bot = BibleBot(config=mock_config, client=mock_client)

        # Populate room ID set for testing
        bot._room_id_set = set(mock_config["matrix_room_ids"])
        bot.start_time = 1234567880000
        bot.api_keys = {}

        # Mock the Bible text retrieval function
        with patch(
            "biblebot.bot.get_bible_text", new_callable=AsyncMock
        ) as mock_get_bible:
            mock_get_bible.return_value = (
                "For God so loved the world that he gave his one and only Son",
                "John 3:16",
            )

            event = MagicMock()
            event.body = (
                "Show me John 3:16 please"  # Natural sentence with embedded reference
            )
            event.sender = "@user:matrix.org"
            event.server_timestamp = 1234567890000

            room = MagicMock()
            room.room_id = "!room1:matrix.org"

            await bot.on_room_message(room, event)

            # Verify Bible text was NOT fetched (partial references ignored in default mode)
            mock_get_bible.assert_not_called()
            # Verify no response was sent
            assert mock_client.room_send.call_count == 0
            assert not any(
                c.args[1] == "m.reaction" for c in mock_client.room_send.call_args_list
            )

    async def test_configuration_integration(self, mock_config, mock_client):
        """
        Validate that BibleBot accepts and preserves essential configuration variants.

        Creates Bot instances for both a minimal and a fuller configuration, seeds the bot's internal room set as tests normally expect, and asserts that critical fields (homeserver and user_id) from each input config are retained on the bot instance.
        """
        # Test with various configuration scenarios
        configs = [
            # Minimal config
            {
                "homeserver": "https://matrix.org",
                "user_id": "@test:matrix.org",
                "access_token": "token",
                "device_id": "device",
                "matrix_room_ids": ["!room:matrix.org"],
            },
            # Full config
            {
                "homeserver": "https://matrix.org",
                "user_id": "@test:matrix.org",
                "access_token": "token",
                "device_id": "device",
                "matrix_room_ids": ["!room1:matrix.org", "!room2:matrix.org"],
                "bible_version": "NIV",
                "response_format": "html",
            },
        ]

        for config in configs:
            bot = BibleBot(config=config, client=mock_client)

            # Populate room ID set for testing (normally done in initialize())

            bot._room_id_set = set(config["matrix_room_ids"])

            # Should handle all configuration variants
            assert bot.config["homeserver"] == config["homeserver"]
            assert bot.config["user_id"] == config["user_id"]

    async def test_lifecycle_integration(self, mock_config, mock_client):
        """Test complete bot lifecycle integration."""
        # Test initialization
        bot = BibleBot(config=mock_config, client=mock_client)

        # Populate room ID set for testing (normally done in initialize())

        bot._room_id_set = set(mock_config["matrix_room_ids"])
        assert bot.client is not None
        assert bot.config is not None

        # Test operation
        bot.start_time = 1234567880000  # Converted to milliseconds

        with patch(
            "biblebot.bot.get_bible_text", new_callable=AsyncMock
        ) as mock_get_bible:
            mock_get_bible.return_value = ("Test verse", "John 3:16")

            event = MagicMock()
            event.body = "John 3:16"
            event.sender = "@user:matrix.org"
            event.server_timestamp = 1234567890000  # Converted to milliseconds

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

        # Populate room ID set for testing (normally done in initialize())

        bot._room_id_set = set(mock_config["matrix_room_ids"])
        bot.start_time = 1234567880000  # Use milliseconds
        bot.api_keys = {}

        with patch(
            "biblebot.bot.get_bible_text", new_callable=AsyncMock
        ) as mock_get_bible:
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

        # Populate room ID set for testing (normally done in initialize())

        bot._room_id_set = set(mock_config["matrix_room_ids"])
        bot.start_time = 1234567880000  # Use milliseconds
        bot.api_keys = {}

        # Scenario 1: Bible study group
        with patch(
            "biblebot.bot.get_bible_text", new_callable=AsyncMock
        ) as mock_get_bible:
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

        with patch(
            "biblebot.bot.get_bible_text", new_callable=AsyncMock
        ) as mock_get_bible:
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
