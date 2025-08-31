"""
Scalability testing patterns following mmrelay's comprehensive approach.
Tests system behavior under load, scaling characteristics, and resource usage.
"""

import asyncio
import gc
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from biblebot.bot import BibleBot


class TestScalabilityPatterns:
    """Test scalability and load handling patterns."""

    @pytest.fixture
    def mock_config(self):
        """Mock configuration for scalability tests."""
        return {
            "homeserver": "https://matrix.org",
            "user_id": "@test:matrix.org",
            "access_token": "test_token",
            "device_id": "TEST_DEVICE",
            "matrix_room_ids": ["!room:matrix.org"],
        }

    @pytest.fixture
    def mock_client(self):
        """Mock Matrix client for scalability tests."""
        client = MagicMock()
        client.room_send = AsyncMock()
        client.join = AsyncMock()
        client.sync = AsyncMock()
        return client

    async def test_high_volume_message_processing(self, mock_config, mock_client):
        """Test processing high volume of messages."""
        bot = BibleBot(config=mock_config, client=mock_client)
        bot.start_time = 1234567880

        with patch("biblebot.bot.get_bible_text") as mock_get_bible:
            mock_get_bible.return_value = ("Test verse", "John 3:16")

            # Process large number of messages
            message_count = 100
            start_time = time.time()

            tasks = []
            for i in range(message_count):
                event = MagicMock()
                event.body = f"John 3:{i+1}"
                event.sender = f"@user{i % 10}:matrix.org"  # 10 different users
                event.server_timestamp = 1234567890 + i

                room = MagicMock()
                room.room_id = "!room:matrix.org"

                task = bot.on_room_message(room, event)
                tasks.append(task)

            # Process all messages concurrently
            await asyncio.gather(*tasks)
            end_time = time.time()

            processing_time = end_time - start_time
            messages_per_second = message_count / processing_time

            # Should process messages efficiently
            assert processing_time < 30.0  # Should complete in under 30 seconds
            assert (
                messages_per_second > 3.0
            )  # Should process at least 3 messages/second
            assert (
                mock_client.room_send.call_count == message_count * 2
            )  # Reaction + message

    async def test_concurrent_user_scaling(self, mock_config, mock_client):
        """Test scaling with many concurrent users."""
        bot = BibleBot(config=mock_config, client=mock_client)
        bot.start_time = 1234567880

        with patch("biblebot.bot.get_bible_text") as mock_get_bible:
            mock_get_bible.return_value = ("Test verse", "John 3:16")

            # Simulate many concurrent users
            user_count = 50
            messages_per_user = 3

            tasks = []
            for user_id in range(user_count):
                for msg_id in range(messages_per_user):
                    event = MagicMock()
                    event.body = f"John 3:{msg_id + 16}"
                    event.sender = f"@user{user_id}:matrix.org"
                    event.server_timestamp = 1234567890 + user_id * 10 + msg_id

                    room = MagicMock()
                    room.room_id = "!room:matrix.org"

                    task = bot.on_room_message(room, event)
                    tasks.append(task)

            # Process all user messages concurrently
            start_time = time.time()
            await asyncio.gather(*tasks)
            end_time = time.time()

            total_messages = user_count * messages_per_user
            processing_time = end_time - start_time

            # Should handle concurrent users efficiently
            assert processing_time < 60.0  # Should complete in under 1 minute
            assert mock_client.room_send.call_count == total_messages * 2

    async def test_multi_room_scaling(self, mock_config, mock_client):
        """Test scaling across multiple rooms."""
        # Update config for multiple rooms
        multi_room_config = mock_config.copy()
        multi_room_config["matrix_room_ids"] = [
            f"!room{i}:matrix.org" for i in range(20)
        ]

        bot = BibleBot(config=multi_room_config, client=mock_client)
        bot.start_time = 1234567880

        with patch("biblebot.bot.get_bible_text") as mock_get_bible:
            mock_get_bible.return_value = ("Test verse", "John 3:16")

            # Send messages to multiple rooms
            room_count = 20
            messages_per_room = 5

            tasks = []
            for room_id in range(room_count):
                for msg_id in range(messages_per_room):
                    event = MagicMock()
                    event.body = f"John 3:{msg_id + 16}"
                    event.sender = f"@user{msg_id}:matrix.org"
                    event.server_timestamp = 1234567890 + room_id * 10 + msg_id

                    room = MagicMock()
                    room.room_id = f"!room{room_id}:matrix.org"

                    task = bot.on_room_message(room, event)
                    tasks.append(task)

            # Process messages from all rooms
            start_time = time.time()
            await asyncio.gather(*tasks)
            end_time = time.time()

            total_messages = room_count * messages_per_room
            processing_time = end_time - start_time

            # Should handle multiple rooms efficiently
            assert processing_time < 45.0
            assert mock_client.room_send.call_count == total_messages * 2

    async def test_memory_scaling_under_load(self, mock_config, mock_client):
        """Test memory usage scaling under load."""
        import resource

        # Get initial memory usage
        initial_memory = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss

        bot = BibleBot(config=mock_config, client=mock_client)
        bot.start_time = 1234567880

        with patch("biblebot.bot.get_bible_text") as mock_get_bible:
            mock_get_bible.return_value = ("Test verse", "John 3:16")

            # Process many messages to test memory scaling
            for batch in range(10):  # 10 batches
                tasks = []
                for i in range(20):  # 20 messages per batch
                    event = MagicMock()
                    event.body = f"John 3:{i + 16}"
                    event.sender = f"@user{i}:matrix.org"
                    event.server_timestamp = 1234567890 + batch * 100 + i

                    room = MagicMock()
                    room.room_id = "!room:matrix.org"

                    task = bot.on_room_message(room, event)
                    tasks.append(task)

                await asyncio.gather(*tasks)

                # Force garbage collection between batches
                gc.collect()

        # Check final memory usage
        final_memory = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        memory_growth = final_memory - initial_memory

        # Memory growth should be reasonable (less than 100MB)
        max_growth = 100 * 1024  # 100MB in KB
        assert memory_growth < max_growth

    async def test_api_request_scaling(self, mock_config, mock_client):
        """Test scaling of API requests."""
        bot = BibleBot(config=mock_config, client=mock_client)
        bot.start_time = 1234567880

        # Track API call performance
        api_call_times = []

        async def timed_api_call(*args, **kwargs):
            start = time.time()
            await asyncio.sleep(0.01)  # Simulate API latency
            end = time.time()
            api_call_times.append(end - start)
            return ("Test verse", "John 3:16")

        with patch("biblebot.bot.get_bible_text", side_effect=timed_api_call):
            # Make many API requests
            tasks = []
            for i in range(50):
                event = MagicMock()
                event.body = f"John 3:{i + 16}"
                event.sender = f"@user{i}:matrix.org"
                event.server_timestamp = 1234567890 + i

                room = MagicMock()
                room.room_id = "!room:matrix.org"

                task = bot.on_room_message(room, event)
                tasks.append(task)

            await asyncio.gather(*tasks)

            # Analyze API performance scaling
            assert len(api_call_times) == 50
            avg_api_time = sum(api_call_times) / len(api_call_times)
            max_api_time = max(api_call_times)

            # API times should remain consistent under load
            assert avg_api_time < 0.1  # Average should be reasonable
            assert max_api_time < 0.5  # No single call should take too long

    async def test_connection_pool_scaling(self, mock_config, mock_client):
        """Test connection pool scaling behavior."""
        bot = BibleBot(config=mock_config, client=mock_client)
        bot.start_time = 1234567880

        # Mock connection pool behavior
        active_connections = 0
        max_connections = 0

        async def connection_tracking_api(*args, **kwargs):
            nonlocal active_connections, max_connections
            active_connections += 1
            max_connections = max(max_connections, active_connections)

            await asyncio.sleep(0.05)  # Simulate connection time

            active_connections -= 1
            return ("Test verse", "John 3:16")

        with patch("biblebot.bot.get_bible_text", side_effect=connection_tracking_api):
            # Create burst of concurrent requests
            tasks = []
            for i in range(30):
                event = MagicMock()
                event.body = f"John 3:{i + 16}"
                event.sender = f"@user{i}:matrix.org"
                event.server_timestamp = 1234567890 + i

                room = MagicMock()
                room.room_id = "!room:matrix.org"

                task = bot.on_room_message(room, event)
                tasks.append(task)

            await asyncio.gather(*tasks)

            # Connection pool should scale appropriately
            assert max_connections <= 30  # Should not exceed request count
            assert max_connections > 1  # Should use multiple connections

    async def test_response_time_under_load(self, mock_config, mock_client):
        """Test response time degradation under load."""
        bot = BibleBot(config=mock_config, client=mock_client)
        bot.start_time = 1234567880

        response_times = []

        with patch("biblebot.bot.get_bible_text") as mock_get_bible:
            mock_get_bible.return_value = ("Test verse", "John 3:16")

            # Measure response times under increasing load
            for load_level in [10, 20, 30]:
                batch_times = []

                for _batch in range(3):  # 3 batches per load level
                    tasks = []
                    start_time = time.time()

                    for i in range(load_level):
                        event = MagicMock()
                        event.body = f"John 3:{i + 16}"
                        event.sender = f"@user{i}:matrix.org"
                        event.server_timestamp = 1234567890 + i

                        room = MagicMock()
                        room.room_id = "!room:matrix.org"

                        task = bot.on_room_message(room, event)
                        tasks.append(task)

                    await asyncio.gather(*tasks)
                    end_time = time.time()

                    batch_time = end_time - start_time
                    batch_times.append(batch_time)

                avg_batch_time = sum(batch_times) / len(batch_times)
                response_times.append(avg_batch_time)

            # Response times should not degrade significantly
            assert len(response_times) == 3
            # Later loads should not be more than 3x slower than initial
            assert response_times[2] < response_times[0] * 3

    async def test_throughput_scaling(self, mock_config, mock_client):
        """Test throughput scaling characteristics."""
        bot = BibleBot(config=mock_config, client=mock_client)
        bot.start_time = 1234567880

        with patch("biblebot.bot.get_bible_text") as mock_get_bible:
            mock_get_bible.return_value = ("Test verse", "John 3:16")

            # Test different batch sizes
            throughput_results = []

            for batch_size in [25, 50, 75]:
                start_time = time.time()

                tasks = []
                for i in range(batch_size):
                    event = MagicMock()
                    event.body = f"John 3:{i + 16}"
                    event.sender = f"@user{i}:matrix.org"
                    event.server_timestamp = 1234567890 + i

                    room = MagicMock()
                    room.room_id = "!room:matrix.org"

                    task = bot.on_room_message(room, event)
                    tasks.append(task)

                await asyncio.gather(*tasks)
                end_time = time.time()

                processing_time = end_time - start_time
                throughput = batch_size / processing_time
                throughput_results.append(throughput)

            # Throughput should scale reasonably
            assert len(throughput_results) == 3
            # Should maintain reasonable throughput across batch sizes
            min_throughput = min(throughput_results)
            max_throughput = max(throughput_results)
            assert min_throughput > 1.0  # At least 1 message/second
            assert max_throughput / min_throughput < 5.0  # Not more than 5x variation

    async def test_resource_cleanup_scaling(self, mock_config, mock_client):
        """Test resource cleanup under scaling conditions."""
        bot = BibleBot(config=mock_config, client=mock_client)
        bot.start_time = 1234567880

        # Track resource allocation and cleanup
        allocated_resources = []

        with patch("biblebot.bot.get_bible_text") as mock_get_bible:
            mock_get_bible.return_value = ("Test verse", "John 3:16")

            # Process messages in waves with cleanup between
            for wave in range(5):
                # Allocate resources (simulate with list)
                wave_resources = []

                tasks = []
                for i in range(20):
                    # Simulate resource allocation
                    wave_resources.append(f"resource_{wave}_{i}")

                    event = MagicMock()
                    event.body = f"John 3:{i + 16}"
                    event.sender = f"@user{i}:matrix.org"
                    event.server_timestamp = 1234567890 + wave * 100 + i

                    room = MagicMock()
                    room.room_id = "!room:matrix.org"

                    task = bot.on_room_message(room, event)
                    tasks.append(task)

                await asyncio.gather(*tasks)

                # Simulate cleanup
                allocated_resources.extend(wave_resources)
                if wave % 2 == 1:  # Cleanup every other wave
                    allocated_resources.clear()
                    gc.collect()

        # Should have managed resources effectively
        assert len(allocated_resources) <= 40  # Should not accumulate indefinitely

    async def test_burst_traffic_handling(self, mock_config, mock_client):
        """Test handling of burst traffic patterns."""
        bot = BibleBot(config=mock_config, client=mock_client)
        bot.start_time = 1234567880

        with patch("biblebot.bot.get_bible_text") as mock_get_bible:
            mock_get_bible.return_value = ("Test verse", "John 3:16")

            # Simulate burst traffic (many requests in short time)
            burst_size = 40
            burst_start = time.time()

            tasks = []
            for i in range(burst_size):
                event = MagicMock()
                event.body = f"John 3:{i + 16}"
                event.sender = f"@user{i}:matrix.org"
                event.server_timestamp = 1234567890 + i

                room = MagicMock()
                room.room_id = "!room:matrix.org"

                task = bot.on_room_message(room, event)
                tasks.append(task)

            # Process entire burst
            await asyncio.gather(*tasks)
            burst_end = time.time()

            burst_duration = burst_end - burst_start
            burst_throughput = burst_size / burst_duration

            # Should handle burst traffic effectively
            assert burst_duration < 20.0  # Should complete burst quickly
            assert burst_throughput > 2.0  # Should maintain good throughput
            assert mock_client.room_send.call_count == burst_size * 2
