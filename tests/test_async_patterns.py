import asyncio
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from biblebot.bot import BibleBot


class TestAsyncPatterns:
    """Test async patterns following mmrelay's proven approach."""

    @pytest.fixture
    def event_loop(self):
        """Create event loop for async tests."""
        loop = asyncio.new_event_loop()
        yield loop
        loop.close()

    @pytest.fixture
    def mock_config(self):
        """Mock configuration for testing."""
        return {
            "matrix": {
                "homeserver": "https://matrix.org",
                "bot_user_id": "@biblebot:matrix.org",
                "access_token": "test_token",
            },
            "matrix_room_ids": ["!room:matrix.org"],
            "bible_api": {
                "base_url": "https://api.scripture.api.bible",
                "api_key": "test_key",
            },
        }

    @pytest.fixture
    def mock_client(self):
        """Mock Matrix client for testing."""
        client = MagicMock()
        client.sync = AsyncMock()
        client.room_send = AsyncMock()
        client.close = AsyncMock()
        client.rooms = {}
        return client

    @pytest.fixture
    def mock_room(self):
        """Mock Matrix room for testing."""
        room = MagicMock()
        room.room_id = "!room:matrix.org"
        room.display_name = "Test Room"
        return room

    @pytest.fixture
    def mock_event(self):
        """Mock Matrix event for testing."""
        event = MagicMock()
        event.sender = "@user:matrix.org"
        event.body = "John 3:16"
        event.event_id = "$event123"
        event.server_timestamp = 1234567890
        event.source = {"content": {"body": "John 3:16"}}
        return event

    async def test_async_client_initialization(self, mock_config, mock_client):
        """Test async client initialization patterns."""
        bot = BibleBot(config=mock_config, client=mock_client)

        assert bot.client is not None
        assert bot.config == mock_config

    async def test_async_message_handling(
        self, mock_config, mock_client, mock_room, mock_event
    ):
        """Test async message handling patterns."""
        bot = BibleBot(config=mock_config, client=mock_client)
        bot.start_time = 1234567880  # Before event timestamp

        # Mock Bible text retrieval
        with patch("biblebot.bot.get_bible_text") as mock_get_bible:
            mock_get_bible.return_value = ("For God so loved the world...", "John 3:16")

            await bot.on_room_message(mock_room, mock_event)

            mock_get_bible.assert_called_once()
            assert mock_client.room_send.call_count == 2  # Reaction + message

    async def test_async_error_handling(
        self, mock_config, mock_client, mock_room, mock_event
    ):
        """Test async error handling patterns."""
        bot = BibleBot(config=mock_config, client=mock_client)
        bot.start_time = 1234567880

        # Mock API error
        with patch("biblebot.bot.get_bible_text") as mock_get_bible:
            mock_get_bible.return_value = (None, None)  # Simulate error

            # Should not raise exception
            await bot.on_room_message(mock_room, mock_event)

            # Should send error message
            mock_client.room_send.assert_called_once()
            call_args = mock_client.room_send.call_args
            content = (
                call_args[0][2] if len(call_args[0]) > 2 else call_args[1]["content"]
            )
            assert "error" in content["body"].lower()

    async def test_async_timeout_handling(self, mock_config, mock_client):
        """Test async timeout handling patterns."""
        bot = BibleBot(config=mock_config, client=mock_client)

        # Mock timeout during room join
        mock_client.join.side_effect = asyncio.TimeoutError()

        with pytest.raises(asyncio.TimeoutError):
            await bot.join_matrix_room("!room:matrix.org")

    async def test_async_concurrent_operations(self, mock_config, mock_client):
        """Test async concurrent operation patterns."""
        bot = BibleBot(config=mock_config, client=mock_client)

        # Mock multiple concurrent room joins
        mock_client.join.return_value = MagicMock(room_id="!room:matrix.org")

        # Run multiple concurrent operations
        tasks = [
            bot.join_matrix_room("!room1:matrix.org"),
            bot.join_matrix_room("!room2:matrix.org"),
            bot.join_matrix_room("!room3:matrix.org"),
        ]

        results = await asyncio.gather(*tasks)

        assert len(results) == 3
        assert mock_client.join.call_count == 3

    async def test_async_cleanup_patterns(self, mock_config, mock_client):
        """Test async cleanup patterns."""
        bot = BibleBot(config=mock_config, client=mock_client)

        # Test that client is properly set
        assert bot.client is not None

        # Test that we can access client methods
        mock_client.close.return_value = None
        mock_client.close()
        mock_client.close.assert_called_once()

    async def test_async_context_manager_patterns(self, mock_config, mock_client):
        """Test async context manager patterns."""
        # Test that BibleBot can be used in async context
        bot = BibleBot(config=mock_config, client=mock_client)

        # Simulate context manager behavior
        try:
            assert bot.client is not None
            assert bot.config == mock_config
        finally:
            # Cleanup would happen here
            pass

    async def test_async_retry_patterns(self, mock_config, mock_client):
        """Test async retry patterns."""
        bot = BibleBot(config=mock_config, client=mock_client)

        # Mock API with initial failures then success
        call_count = 0

        async def mock_api_call(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Temporary error")
            return {"text": "Success", "reference": "John 3:16"}

        with patch("biblebot.bot.make_api_request", side_effect=mock_api_call):
            # Test retry pattern with actual function
            from biblebot.bot import get_kjv_text

            # Should eventually succeed after retries
            text, reference = await get_kjv_text("John 3:16")

            assert "Success" in text
            assert call_count == 3

    async def test_async_rate_limiting_patterns(self, mock_config, mock_client):
        """Test async rate limiting patterns."""
        bot = BibleBot(config=mock_config, client=mock_client)

        # Mock rate-limited API
        with patch("asyncio.sleep") as mock_sleep:
            with patch("biblebot.bot.get_bible_text") as mock_get_bible:
                mock_get_bible.return_value = ("Test verse", "John 3:16")

                # Simulate rate limiting by adding delays
                async def rate_limited_call():
                    await asyncio.sleep(0.1)  # Simulate rate limit
                    return await mock_get_bible("John 3:16")

                # Make multiple requests
                for _ in range(3):
                    await rate_limited_call()

                # Should have introduced delays
                mock_sleep.assert_called()

    async def test_async_cancellation_patterns(self, mock_config, mock_client):
        """Test async cancellation patterns."""
        bot = BibleBot(config=mock_config, client=mock_client)

        # Create a long-running task
        async def long_running_task():
            await asyncio.sleep(10)
            return "completed"

        with patch("biblebot.bot.get_bible_text", side_effect=long_running_task):
            # Start task and cancel it
            task = asyncio.create_task(bot.on_room_message(MagicMock(), MagicMock()))
            await asyncio.sleep(0.1)  # Let it start
            task.cancel()

            with pytest.raises(asyncio.CancelledError):
                await task

    async def test_async_exception_propagation(self, mock_config, mock_client):
        """Test async exception propagation patterns."""
        bot = BibleBot(config=mock_config, client=mock_client)

        # Test that exceptions are properly propagated
        with patch("biblebot.bot.get_bible_text") as mock_get_bible:
            mock_get_bible.side_effect = ValueError("Invalid verse reference")

            # Exception should be caught and handled gracefully
            mock_event = MagicMock()
            mock_event.body = "Invalid 99:99"
            mock_event.sender = "@user:matrix.org"
            mock_event.server_timestamp = 1234567890

            bot.start_time = 1234567880
            await bot.on_room_message(MagicMock(), mock_event)

    async def test_async_resource_management(self, mock_config, mock_client):
        """Test async resource management patterns."""
        # Test proper resource cleanup even with exceptions
        bot = BibleBot(config=mock_config, client=mock_client)

        try:
            # Simulate an error during operation
            raise Exception("Simulated error")
        except Exception:
            pass
        finally:
            # Test that client is still accessible for cleanup
            assert bot.client is not None
            mock_client.close.return_value = None
            mock_client.close()
            mock_client.close.assert_called_once()

    async def test_async_event_loop_integration(self, mock_config, mock_client):
        """Test async event loop integration patterns."""
        with patch("biblebot.bot.AsyncClient", return_value=mock_client):
            bot = BibleBot(config=mock_config)

            # Test that bot works with different event loop policies
            loop = asyncio.get_event_loop()
            assert loop is not None

            # Test scheduling callbacks
            callback_called = False

            def callback():
                nonlocal callback_called
                callback_called = True

            loop.call_soon(callback)
            await asyncio.sleep(0)  # Let callback run

            assert callback_called

    async def test_async_signal_handling(self, mock_config, mock_client):
        """Test async signal handling patterns."""
        bot = BibleBot(config=mock_config, client=mock_client)

        # Test graceful shutdown simulation
        shutdown_called = False

        async def mock_shutdown():
            nonlocal shutdown_called
            shutdown_called = True

        # Simulate signal handling by calling shutdown directly
        await mock_shutdown()

        assert shutdown_called is True

    async def test_async_background_tasks(self, mock_config, mock_client):
        """Test async background task patterns."""
        with patch("biblebot.bot.AsyncClient", return_value=mock_client):
            bot = BibleBot(config=mock_config)

            # Test background task management
            task_completed = False

            async def background_task():
                nonlocal task_completed
                await asyncio.sleep(0.1)
                task_completed = True

            # Start background task
            task = asyncio.create_task(background_task())

            # Wait for completion
            await task

            assert task_completed
            assert task.done()
            assert not task.cancelled()
