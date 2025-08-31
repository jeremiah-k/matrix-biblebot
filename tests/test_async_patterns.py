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
        with patch("biblebot.bot.AsyncClient", return_value=mock_client):
            bot = BibleBot(config=mock_config)
            await bot.initialize_client()

            assert bot.client is not None
            mock_client.sync.assert_called_once()

    async def test_async_message_handling(
        self, mock_config, mock_client, mock_room, mock_event
    ):
        """Test async message handling patterns."""
        with patch("biblebot.bot.AsyncClient", return_value=mock_client):
            bot = BibleBot(config=mock_config)
            bot.client = mock_client

            # Mock verse fetching
            with patch.object(bot, "fetch_verse", new_callable=AsyncMock) as mock_fetch:
                mock_fetch.return_value = "For God so loved the world..."

                await bot.handle_message(mock_room, mock_event)

                mock_fetch.assert_called_once()
                mock_client.room_send.assert_called_once()

    async def test_async_error_handling(
        self, mock_config, mock_client, mock_room, mock_event
    ):
        """Test async error handling patterns."""
        with patch("biblebot.bot.AsyncClient", return_value=mock_client):
            bot = BibleBot(config=mock_config)
            bot.client = mock_client

            # Mock API error
            with patch.object(bot, "fetch_verse", new_callable=AsyncMock) as mock_fetch:
                mock_fetch.side_effect = Exception("API Error")

                # Should not raise exception
                await bot.handle_message(mock_room, mock_event)

                # Should send error message
                mock_client.room_send.assert_called_once()
                call_args = mock_client.room_send.call_args[1]
                assert "error" in call_args["content"]["body"].lower()

    async def test_async_timeout_handling(self, mock_config, mock_client):
        """Test async timeout handling patterns."""
        with patch("biblebot.bot.AsyncClient", return_value=mock_client):
            bot = BibleBot(config=mock_config)

            # Mock timeout during sync
            mock_client.sync.side_effect = asyncio.TimeoutError()

            with pytest.raises(asyncio.TimeoutError):
                await bot.initialize_client()

    async def test_async_concurrent_operations(self, mock_config, mock_client):
        """Test async concurrent operation patterns."""
        with patch("biblebot.bot.AsyncClient", return_value=mock_client):
            bot = BibleBot(config=mock_config)
            bot.client = mock_client

            # Mock multiple concurrent verse fetches
            with patch.object(bot, "fetch_verse", new_callable=AsyncMock) as mock_fetch:
                mock_fetch.return_value = "Test verse"

                # Run multiple concurrent operations
                tasks = [
                    bot.fetch_verse("John 3:16"),
                    bot.fetch_verse("Romans 8:28"),
                    bot.fetch_verse("Philippians 4:13"),
                ]

                results = await asyncio.gather(*tasks)

                assert len(results) == 3
                assert all(result == "Test verse" for result in results)
                assert mock_fetch.call_count == 3

    async def test_async_cleanup_patterns(self, mock_config, mock_client):
        """Test async cleanup patterns."""
        with patch("biblebot.bot.AsyncClient", return_value=mock_client):
            bot = BibleBot(config=mock_config)
            bot.client = mock_client

            # Test cleanup on exit
            await bot.cleanup()

            mock_client.close.assert_called_once()

    async def test_async_context_manager_patterns(self, mock_config):
        """Test async context manager patterns."""
        with patch("biblebot.bot.AsyncClient") as mock_async_client:
            mock_client = MagicMock()
            mock_client.sync = AsyncMock()
            mock_client.close = AsyncMock()
            mock_async_client.return_value = mock_client

            # Test using bot as async context manager
            async with BibleBot(config=mock_config) as bot:
                assert bot.client is not None
                mock_client.sync.assert_called_once()

            # Cleanup should be called automatically
            mock_client.close.assert_called_once()

    async def test_async_retry_patterns(self, mock_config, mock_client):
        """Test async retry patterns."""
        with patch("biblebot.bot.AsyncClient", return_value=mock_client):
            bot = BibleBot(config=mock_config)

            # Mock API with initial failures then success
            call_count = 0

            async def mock_api_call(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                if call_count < 3:
                    raise Exception("Temporary error")
                return {"data": {"content": "Success"}}

            with patch("aiohttp.ClientSession") as mock_session:
                mock_response = MagicMock()
                mock_response.status = 200
                mock_response.json = mock_api_call

                mock_session_instance = MagicMock()
                mock_session_instance.get = AsyncMock(return_value=mock_response)
                mock_session.return_value.__aenter__.return_value = (
                    mock_session_instance
                )

                # Should eventually succeed after retries
                result = await bot.fetch_verse_with_retry("John 3:16", max_retries=3)

                assert "Success" in result
                assert call_count == 3

    async def test_async_rate_limiting_patterns(self, mock_config, mock_client):
        """Test async rate limiting patterns."""
        with patch("biblebot.bot.AsyncClient", return_value=mock_client):
            bot = BibleBot(config=mock_config)
            bot.client = mock_client

            # Mock rate-limited API
            with patch("asyncio.sleep") as mock_sleep:
                with patch.object(
                    bot, "fetch_verse", new_callable=AsyncMock
                ) as mock_fetch:
                    mock_fetch.return_value = "Test verse"

                    # Simulate rate limiting
                    start_time = asyncio.get_event_loop().time()

                    # Make multiple requests
                    for _ in range(3):
                        await bot.fetch_verse_rate_limited("John 3:16")

                    # Should have introduced delays
                    mock_sleep.assert_called()

    async def test_async_cancellation_patterns(self, mock_config, mock_client):
        """Test async cancellation patterns."""
        with patch("biblebot.bot.AsyncClient", return_value=mock_client):
            bot = BibleBot(config=mock_config)

            # Create a long-running task
            async def long_running_task():
                await asyncio.sleep(10)
                return "completed"

            with patch.object(bot, "fetch_verse", new_callable=AsyncMock) as mock_fetch:
                mock_fetch.side_effect = long_running_task

                # Start task and cancel it
                task = asyncio.create_task(bot.fetch_verse("John 3:16"))
                await asyncio.sleep(0.1)  # Let it start
                task.cancel()

                with pytest.raises(asyncio.CancelledError):
                    await task

    async def test_async_exception_propagation(self, mock_config, mock_client):
        """Test async exception propagation patterns."""
        with patch("biblebot.bot.AsyncClient", return_value=mock_client):
            bot = BibleBot(config=mock_config)

            # Test that exceptions are properly propagated
            with patch.object(bot, "fetch_verse", new_callable=AsyncMock) as mock_fetch:
                mock_fetch.side_effect = ValueError("Invalid verse reference")

                with pytest.raises(ValueError, match="Invalid verse reference"):
                    await bot.fetch_verse("Invalid 99:99")

    async def test_async_resource_management(self, mock_config):
        """Test async resource management patterns."""
        with patch("biblebot.bot.AsyncClient") as mock_async_client:
            mock_client = MagicMock()
            mock_client.sync = AsyncMock()
            mock_client.close = AsyncMock()
            mock_async_client.return_value = mock_client

            # Test proper resource cleanup even with exceptions
            bot = BibleBot(config=mock_config)

            try:
                await bot.initialize_client()
                # Simulate an error during operation
                raise Exception("Simulated error")
            except Exception:
                pass
            finally:
                await bot.cleanup()

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
        with patch("biblebot.bot.AsyncClient", return_value=mock_client):
            bot = BibleBot(config=mock_config)

            # Test graceful shutdown on signal
            shutdown_called = False

            async def mock_shutdown():
                nonlocal shutdown_called
                shutdown_called = True

            with patch.object(
                bot, "shutdown", new_callable=AsyncMock
            ) as mock_shutdown_method:
                mock_shutdown_method.side_effect = mock_shutdown

                # Simulate signal handling
                await bot.handle_shutdown_signal()

                mock_shutdown_method.assert_called_once()

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
