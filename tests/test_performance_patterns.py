"""
Performance testing patterns following mmrelay's comprehensive approach.
Tests performance characteristics, memory usage, and scalability patterns.
"""

import asyncio
import gc
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from biblebot.bot import BibleBot


class TestPerformancePatterns:
    """Test performance characteristics and optimization patterns."""

    @pytest.fixture
    def mock_config(self):
        """Mock configuration for performance tests."""
        return {
            "homeserver": "https://matrix.org",
            "user_id": "@test:matrix.org",
            "access_token": "test_token",
            "device_id": "TEST_DEVICE",
            "matrix_room_ids": ["!room:matrix.org"],
        }

    @pytest.fixture
    def mock_client(self):
        """Mock Matrix client for performance tests."""
        client = MagicMock()
        client.room_send = AsyncMock()
        client.join = AsyncMock()
        client.sync = AsyncMock()
        return client

    async def test_message_processing_performance(self, mock_config, mock_client):
        """Test message processing performance under load."""
        bot = BibleBot(config=mock_config, client=mock_client)
        bot.start_time = int((time.time() - 100) * 1000)  # Use milliseconds
        bot.api_keys = {}

        # Mock Bible API response
        with patch("biblebot.bot.get_bible_text") as mock_get_bible:
            mock_get_bible.return_value = ("Test verse", "John 3:16")

            # Create multiple mock events
            events = []
            for i in range(100):
                event = MagicMock()
                event.body = f"John 3:{i+1}"
                event.sender = f"@user{i}:matrix.org"
                event.server_timestamp = int(time.time() * 1000)
                events.append(event)

            # Measure processing time
            start_time = time.perf_counter()

            # Process events concurrently with proper room configuration
            tasks = []
            for event in events[:10]:  # Test with 10 concurrent messages
                room = MagicMock()
                room.room_id = mock_config["matrix_room_ids"][0]  # Use configured room
                task = bot.on_room_message(room, event)
                tasks.append(task)

            await asyncio.gather(*tasks)

            end_time = time.perf_counter()
            processing_time = end_time - start_time

            # Performance assertions
            assert (
                processing_time < 5.0
            )  # Should process 10 messages in under 5 seconds
            assert (
                mock_client.room_send.call_count >= 10
            )  # At least one response per message

    async def test_memory_usage_patterns(self, mock_config, mock_client):
        """Test memory usage patterns and garbage collection."""
        # Get initial memory usage using resource module (skip if unavailable)
        resource = pytest.importorskip("resource")
        initial_memory = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss

        bot = BibleBot(config=mock_config, client=mock_client)
        bot.start_time = int(
            (time.time() - 100) * 1000
        )  # Set start_time for message filtering

        # Create and process many events to test memory management
        with patch("biblebot.bot.get_bible_text") as mock_get_bible:
            mock_get_bible.return_value = ("Test verse", "John 3:16")

            for i in range(50):
                event = MagicMock()
                event.body = f"John 3:{i+1}"
                event.sender = f"@user{i}:matrix.org"
                event.server_timestamp = int(time.time() * 1000)

                room = MagicMock()
                room.room_id = mock_config["matrix_room_ids"][0]
                await bot.on_room_message(room, event)

        # Force garbage collection
        gc.collect()

        # Check memory usage hasn't grown excessively
        final_memory = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        growth = final_memory - initial_memory
        # Linux: KB, macOS: bytes
        import sys

        if sys.platform == "darwin":
            assert growth < 50 * 1024 * 1024  # 50 MB
        else:
            assert growth < 50 * 1024  # 50 MB in KB

    async def test_concurrent_request_handling(self, mock_config, mock_client):
        """Test handling of concurrent API requests."""
        bot = BibleBot(config=mock_config, client=mock_client)
        bot.start_time = int((time.time() - 100) * 1000)  # Use milliseconds
        bot.api_keys = {}

        # Mock API with varying response times
        call_count = 0

        async def mock_api_call(*_args, **_kwargs):
            nonlocal call_count
            call_count += 1
            # Simulate varying API response times
            await asyncio.sleep(0.1 + (call_count % 3) * 0.05)
            return (f"Verse {call_count}", f"John 3:{call_count}")

        with patch("biblebot.bot.get_bible_text", side_effect=mock_api_call):
            # Create concurrent requests
            tasks = []
            for i in range(20):
                event = MagicMock()
                event.body = f"John 3:{i+1}"
                event.sender = f"@user{i}:matrix.org"
                event.server_timestamp = int(time.time() * 1000)

                room = MagicMock()
                room.room_id = mock_config["matrix_room_ids"][0]  # Use configured room
                task = bot.on_room_message(room, event)
                tasks.append(task)

            # Measure concurrent processing time
            start_time = time.perf_counter()
            await asyncio.gather(*tasks)
            end_time = time.perf_counter()

            processing_time = end_time - start_time

            # Should handle 20 concurrent requests efficiently
            assert processing_time < 10.0  # Should complete in under 10 seconds
            assert call_count == 20  # All requests should be processed

    async def test_rate_limiting_performance(self, mock_config, mock_client):
        """Test performance under rate limiting conditions."""
        bot = BibleBot(config=mock_config, client=mock_client)
        bot.start_time = int((time.time() - 100) * 1000)  # Use milliseconds
        bot.api_keys = {}

        # Mock rate-limited API
        request_times = []

        async def rate_limited_api(*_args, **_kwargs):
            request_times.append(time.perf_counter())
            # Simulate rate limiting delay
            await asyncio.sleep(0.1)
            return ("Rate limited verse", "John 3:16")

        with patch("biblebot.bot.get_bible_text", side_effect=rate_limited_api):
            # Send requests rapidly
            tasks = []
            for i in range(5):
                event = MagicMock()
                event.body = f"John 3:{i+1}"
                event.sender = f"@user{i}:matrix.org"
                event.server_timestamp = int(time.time() * 1000)

                room = MagicMock()
                room.room_id = mock_config["matrix_room_ids"][0]  # Use configured room
                task = bot.on_room_message(room, event)
                tasks.append(task)

            start = time.perf_counter()
            await asyncio.gather(*tasks)
            duration = time.perf_counter() - start

            # Verify requests were processed
            assert len(request_times) == 5
            # Sequential ≈ 0.5s (5 × 0.1); concurrent should be well under that.
            assert duration < 0.5

    async def test_large_message_handling(self, mock_config, mock_client):
        """Test handling of large message content."""
        bot = BibleBot(config=mock_config, client=mock_client)

        # Create event with large message content
        event = MagicMock()
        event.body = "John 1:1 " * 1000  # Very long message
        event.sender = "@user:matrix.org"
        event.server_timestamp = int(time.time() * 1000)

        with patch("biblebot.bot.get_bible_text") as mock_get_bible:
            mock_get_bible.return_value = ("In the beginning was the Word", "John 1:1")

            # Should handle large messages without issues
            start_time = time.perf_counter()
            await bot.on_room_message(MagicMock(), event)
            end_time = time.perf_counter()

            processing_time = end_time - start_time
            assert processing_time < 1.0  # Should process quickly even with large input

    async def test_error_recovery_performance(self, mock_config, mock_client):
        """Test performance during error conditions and recovery."""
        bot = BibleBot(config=mock_config, client=mock_client)

        # Mock API that fails then recovers
        call_count = 0

        async def failing_api(*_args, **_kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 3:
                raise RuntimeError("API Error")
            return ("Recovered verse", "John 3:16")

        with patch("biblebot.bot.get_bible_text", side_effect=failing_api):
            # Send multiple requests during failure and recovery
            tasks = []
            for i in range(6):
                event = MagicMock()
                event.body = f"John 3:{i+1}"
                event.sender = f"@user{i}:matrix.org"
                event.server_timestamp = int(time.time() * 1000)

                task = bot.on_room_message(MagicMock(), event)
                tasks.append(task)

            # Should handle errors gracefully without hanging
            start_time = time.perf_counter()
            await asyncio.gather(*tasks, return_exceptions=True)
            end_time = time.perf_counter()

            processing_time = end_time - start_time
            assert processing_time < 5.0  # Should complete quickly even with errors

    async def test_cleanup_performance(self, mock_config, mock_client):
        """Test cleanup and resource deallocation performance."""
        # Create multiple bot instances to test cleanup
        bots = []
        for _i in range(10):
            bot = BibleBot(config=mock_config, client=mock_client)
            bots.append(bot)

        # Simulate cleanup
        start_time = time.perf_counter()
        for bot in bots:
            # Simulate cleanup operations
            bot.client = None
            bot.config = None

        # Force garbage collection
        gc.collect()
        end_time = time.perf_counter()

        cleanup_time = end_time - start_time
        assert cleanup_time < 1.0  # Cleanup should be fast

    async def test_startup_performance(self, mock_config, mock_client):
        """Test bot startup and initialization performance."""
        # Measure bot initialization time
        start_time = time.perf_counter()

        bot = BibleBot(config=mock_config, client=mock_client)

        end_time = time.perf_counter()
        initialization_time = end_time - start_time

        # Initialization should be fast (relaxed for CI)
        assert initialization_time < 0.3  # Should initialize in under 300ms
        assert bot.client is not None
        assert bot.config is not None

    async def test_background_task_performance(self, mock_config, mock_client):
        """Test background task performance and resource usage."""
        bot = BibleBot(config=mock_config, client=mock_client)
        bot.start_time = int((time.time() - 100) * 1000)  # Use milliseconds
        bot.api_keys = {}

        # Create a background task
        task_completed = False

        async def background_task():
            nonlocal task_completed
            await asyncio.sleep(0.1)
            task_completed = True

        # Start background task
        task = asyncio.create_task(background_task())

        # Continue with other operations
        event = MagicMock()
        event.body = "John 3:16"
        event.sender = "@user:matrix.org"
        event.server_timestamp = int(time.time() * 1000)

        room = MagicMock()
        room.room_id = mock_config["matrix_room_ids"][0]  # Use configured room

        with patch("biblebot.bot.get_bible_text") as mock_get_bible:
            mock_get_bible.return_value = ("Test verse", "John 3:16")

            await bot.on_room_message(room, event)

        # Wait for background task
        await task

        assert task_completed is True
        assert mock_client.room_send.called
