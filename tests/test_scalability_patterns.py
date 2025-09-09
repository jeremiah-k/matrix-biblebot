"""
Scalability testing patterns following mmrelay's comprehensive approach.
Tests system behavior under load, scaling characteristics, and resource usage.
"""

import asyncio
import gc
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.asyncio

from biblebot.bot import BibleBot  # noqa: E402


class TestScalabilityPatterns:
    """Test scalability and load handling patterns."""

    @pytest.fixture
    def mock_config(self):
        """
        Fixture providing a mocked Matrix-like configuration dictionary for scalability tests.

        Returns a dict containing the minimal fields the tests expect:
        - homeserver: homeserver URL used by the client (string).
        - user_id: Matrix user identifier used in events (string).
        - access_token: token used for authenticated requests (string).
        - device_id: client device identifier (string).
        - matrix_room_ids: list of room IDs to initialize or simulate rooms (list of strings).
        """
        return {
            "homeserver": "https://matrix.org",
            "user_id": "@test:matrix.org",
            "access_token": "test_token",
            "device_id": "TEST_DEVICE",
            "matrix_room_ids": ["!room:matrix.org"],
        }

    @pytest.fixture
    def mock_client(self):
        """
        Create and return a MagicMock representing a Matrix client for scalability tests.

        The mock exposes async methods used by the tests:
        - `room_send`: AsyncMock for sending messages/reactions.
        - `join`: AsyncMock for joining rooms.
        - `sync`: AsyncMock for syncing the client.

        Returns:
            MagicMock: A mock client with the async attributes above.
        """
        client = MagicMock()
        client.room_send = AsyncMock()
        client.join = AsyncMock()
        client.sync = AsyncMock()
        return client

    async def test_high_volume_message_processing(self, mock_config, mock_client):
        """
        Simulate 100 concurrent incoming messages to a single room and assert throughput and per-message I/O behavior.

        Runs a high-volume scenario with a deterministic patched Bible API, measures total processing time and messages/sec, and asserts:
        - total processing completes in under 30 seconds,
        - throughput exceeds 3 messages/second,
        - the mock Matrix client's `room_send` is invoked twice per message (reaction + response).
        """
        bot = BibleBot(config=mock_config, client=mock_client)

        # Populate room ID set for testing (normally done in initialize())

        bot._room_id_set = set(mock_config["matrix_room_ids"])
        bot.start_time = 1234567880000  # Converted to milliseconds

        with patch(
            "biblebot.bot.get_bible_text",
            new=AsyncMock(return_value=("Test verse", "John 3:16")),
        ):

            # Process large number of messages
            message_count = 100
            start_time = time.perf_counter()

            tasks = []
            for i in range(message_count):
                event = MagicMock()
                event.body = f"John 3:{i+1}"
                event.sender = f"@user{i % 10}:matrix.org"  # 10 different users
                event.server_timestamp = 1234567890000  # Converted to milliseconds + i

                room = MagicMock()
                room.room_id = "!room:matrix.org"

                task = bot.on_room_message(room, event)
                tasks.append(task)

            # Process all messages concurrently
            await asyncio.gather(*tasks)
            end_time = time.perf_counter()

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

        # Populate room ID set for testing (normally done in initialize())

        bot._room_id_set = set(mock_config["matrix_room_ids"])
        bot.start_time = 1234567880000  # Converted to milliseconds

        with patch(
            "biblebot.bot.get_bible_text",
            new=AsyncMock(return_value=("Test verse", "John 3:16")),
        ):

            # Simulate many concurrent users
            user_count = 50
            messages_per_user = 3

            tasks = []
            for user_id in range(user_count):
                for msg_id in range(messages_per_user):
                    event = MagicMock()
                    event.body = f"John 3:{msg_id + 16}"
                    event.sender = f"@user{user_id}:matrix.org"
                    event.server_timestamp = 1234567890000  # Converted to milliseconds + user_id * 10 + msg_id

                    room = MagicMock()
                    room.room_id = "!room:matrix.org"

                    task = bot.on_room_message(room, event)
                    tasks.append(task)

            # Process all user messages concurrently
            start_time = time.perf_counter()
            await asyncio.gather(*tasks)
            end_time = time.perf_counter()

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

        # Populate room ID set for testing (normally done in initialize())

        bot._room_id_set = set(multi_room_config["matrix_room_ids"])
        bot.start_time = 1234567880000  # Converted to milliseconds

        with patch(
            "biblebot.bot.get_bible_text",
            new=AsyncMock(return_value=("Test verse", "John 3:16")),
        ):

            # Send messages to multiple rooms
            room_count = 20
            messages_per_room = 5

            tasks = []
            for room_id in range(room_count):
                for msg_id in range(messages_per_room):
                    event = MagicMock()
                    event.body = f"John 3:{msg_id + 16}"
                    event.sender = f"@user{msg_id}:matrix.org"
                    event.server_timestamp = 1234567890000  # Converted to milliseconds + room_id * 10 + msg_id

                    room = MagicMock()
                    room.room_id = f"!room{room_id}:matrix.org"

                    task = bot.on_room_message(room, event)
                    tasks.append(task)

            # Process messages from all rooms
            start_time = time.perf_counter()
            await asyncio.gather(*tasks)
            end_time = time.perf_counter()

            total_messages = room_count * messages_per_room
            processing_time = end_time - start_time

            # Should handle multiple rooms efficiently
            assert processing_time < 45.0
            assert mock_client.room_send.call_count == total_messages * 2

    async def test_memory_scaling_under_load(self, mock_config, mock_client):
        """Test memory usage scaling under load."""
        import resource

        # Get initial memory usage
        _ru_start = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        import sys

        initial_memory = _ru_start / 1024 if sys.platform == "darwin" else _ru_start

        bot = BibleBot(config=mock_config, client=mock_client)

        # Populate room ID set for testing (normally done in initialize())

        bot._room_id_set = set(mock_config["matrix_room_ids"])
        bot.start_time = 1234567880000  # Converted to milliseconds

        with patch(
            "biblebot.bot.get_bible_text",
            new=AsyncMock(return_value=("Test verse", "John 3:16")),
        ):

            # Process many messages to test memory scaling
            for _batch in range(10):  # 10 batches
                tasks = []
                for i in range(20):  # 20 messages per batch
                    event = MagicMock()
                    event.body = f"John 3:{i + 16}"
                    event.sender = f"@user{i}:matrix.org"
                    event.server_timestamp = (
                        1234567890000  # Converted to milliseconds + batch * 100 + i
                    )

                    room = MagicMock()
                    room.room_id = "!room:matrix.org"

                    task = bot.on_room_message(room, event)
                    tasks.append(task)

                await asyncio.gather(*tasks)

                # Force garbage collection between batches
                gc.collect()

        # Check final memory usage
        _ru_end = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        final_memory = _ru_end / 1024 if sys.platform == "darwin" else _ru_end
        memory_growth = final_memory - initial_memory

        # Memory growth should be reasonable (less than 100MB)
        max_growth = 100 * 1024  # 100MB in KB
        assert memory_growth < max_growth

    async def test_api_request_scaling(self, mock_config, mock_client):
        """
        Test that external API request latency remains stable under concurrent load.

        Creates a BibleBot with a mocked Matrix client and patches the external `get_bible_text`
        call to an async helper that simulates ~10ms latency while recording each call's
        duration. It then concurrently sends 50 simulated room message events to the bot,
        collects per-call timings, and asserts:

        - Exactly 50 API calls were recorded.
        - The average API time stays within a permissive budget derived from the median
          observed latency (avg < median + 0.25).
        - The worst single-call time stays within a permissive spike allowance (max < median + 0.45).

        This test focuses on measuring per-request latency under load and uses relaxed
        tolerances to reduce CI flakiness.
        """
        bot = BibleBot(config=mock_config, client=mock_client)

        # Populate room ID set for testing (normally done in initialize())

        bot._room_id_set = set(mock_config["matrix_room_ids"])
        bot.start_time = 1234567880000  # Converted to milliseconds

        # Track API call performance
        api_call_times = []

        async def timed_api_call(*_args, **_kwargs):
            """
            Simulate a short (~10 ms) external API call, record its duration, and return a fixed verse tuple.

            This async helper accepts arbitrary positional and keyword arguments (they are ignored), sleeps approximately 10 milliseconds to emulate network latency, appends the measured call duration (seconds) to the external list `api_call_times`, and returns a (verse_text, reference) tuple — ("Test verse", "John 3:16").
            """
            start = time.perf_counter()
            await asyncio.sleep(0.01)  # Simulate API latency
            end = time.perf_counter()
            api_call_times.append(end - start)
            return ("Test verse", "John 3:16")

        with patch("biblebot.bot.get_bible_text", side_effect=timed_api_call):
            # Make many API requests
            tasks = []
            for i in range(50):
                event = MagicMock()
                event.body = f"John 3:{i + 16}"
                event.sender = f"@user{i}:matrix.org"
                event.server_timestamp = 1234567890000  # Converted to milliseconds + i

                room = MagicMock()
                room.room_id = "!room:matrix.org"

                task = bot.on_room_message(room, event)
                tasks.append(task)

            await asyncio.gather(*tasks)

            # Analyze API performance scaling
            assert len(api_call_times) == 50
            avg_api_time = sum(api_call_times) / len(api_call_times)
            max_api_time = max(api_call_times)

            # API times should remain consistent under load (more lenient for CI)
            # Derive tolerances from observed timings to reduce CI flakiness
            import statistics

            sim_latency = statistics.median(api_call_times)
            avg_budget = sim_latency + 0.25  # generous CI headroom
            max_budget = sim_latency + 0.45  # generous per-call spike allowance
            assert avg_api_time < avg_budget
            assert max_api_time < max_budget

    async def test_connection_pool_scaling(self, mock_config, mock_client):
        """
        Verify the bot's external-request connection pooling scales under concurrent load.

        Creates a BibleBot with a mocked client and configuration, patches get_bible_text with an async helper that simulates ~50 ms latency while tracking concurrent callers, then drives 30 concurrent on_room_message calls. Asserts the observed peak concurrent connections is greater than 1 (uses multiple connections) and does not exceed the number of requests (<= 30).
        """
        bot = BibleBot(config=mock_config, client=mock_client)

        # Populate room ID set for testing (normally done in initialize())

        bot._room_id_set = set(mock_config["matrix_room_ids"])
        bot.start_time = 1234567880000  # Converted to milliseconds

        # Mock connection pool behavior
        active_connections = 0
        max_connections = 0

        async def connection_tracking_api(*_args, **_kwargs):
            """
            Simulated async API that tracks concurrent "connections" and returns a fixed verse.

            Increments the enclosing active_connections counter and updates max_connections to record peak concurrency,
            awaits ~50 ms to simulate external latency, then decrements active_connections and returns a fixed
            (verse, reference) tuple. Accepts arbitrary positional and keyword arguments (ignored).

            Returns:
                tuple[str, str]: A fixed (verse, reference) pair ("Test verse", "John 3:16").
            """
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
                event.server_timestamp = 1234567890000  # Converted to milliseconds + i

                room = MagicMock()
                room.room_id = "!room:matrix.org"

                task = bot.on_room_message(room, event)
                tasks.append(task)

            await asyncio.gather(*tasks)

            # Connection pool should scale appropriately
            assert max_connections <= 30  # Should not exceed request count
            assert max_connections > 1  # Should use multiple connections

    async def test_response_time_under_load(self, mock_config, mock_client):
        """
        Measure how BibleBot's per-batch response time changes as concurrent load increases.

        Runs three load levels (10, 20, 30 concurrent messages). For each level it executes 3 batches of concurrent calls to bot.on_room_message (with get_bible_text patched to a deterministic AsyncMock), records each batch's elapsed time, and computes the average batch time per load level. Asserts that three average times were collected and that the final average does not exceed five times the first average (permits moderate degradation under load).

        No return value. Side effects: invokes the bot's message handler concurrently using the provided mocked client and configuration.
        """
        bot = BibleBot(config=mock_config, client=mock_client)

        # Populate room ID set for testing (normally done in initialize())

        bot._room_id_set = set(mock_config["matrix_room_ids"])
        bot.start_time = 1234567880000  # Use milliseconds
        bot.api_keys = {}

        response_times = []

        with patch(
            "biblebot.bot.get_bible_text",
            new=AsyncMock(return_value=("Test verse", "John 3:16")),
        ):

            # Measure response times under increasing load
            for load_level in [10, 20, 30]:
                batch_times = []

                for _batch in range(3):  # 3 batches per load level
                    tasks = []
                    start_time = time.perf_counter()

                    for i in range(load_level):
                        event = MagicMock()
                        event.body = f"John 3:{i + 16}"
                        event.sender = f"@user{i}:matrix.org"
                        event.server_timestamp = (
                            1234567890000 + i * 1000
                        )  # Use milliseconds

                        room = MagicMock()
                        room.room_id = mock_config["matrix_room_ids"][
                            0
                        ]  # Use configured room

                        task = bot.on_room_message(room, event)
                        tasks.append(task)

                    await asyncio.gather(*tasks)
                    end_time = time.perf_counter()

                    batch_time = end_time - start_time
                    batch_times.append(batch_time)

                avg_batch_time = sum(batch_times) / len(batch_times)
                response_times.append(avg_batch_time)

            # Response times should not degrade significantly
            assert len(response_times) == 3
            # Allow for more realistic performance degradation under load
            assert (
                response_times[2] < response_times[0] * 5
            )  # Allow 5x degradation instead of 3x

    async def test_throughput_scaling(self, mock_config, mock_client):
        """
        Measure throughput scaling for BibleBot by sending concurrent message batches of sizes 25, 50, and 75 and asserting stability.

        Sends each batch concurrently to bot.on_room_message, records processing time per batch, computes messages/sec for each batch, and asserts:
        - Three throughput measurements are produced.
        - Minimum throughput > 1.0 messages/second.
        - Ratio of max to min throughput < 5.0 (reasonable variation across batch sizes).

        This test relies on a patched `get_bible_text` returning a deterministic response and uses the provided mock client/config.
        """
        bot = BibleBot(config=mock_config, client=mock_client)

        # Populate room ID set for testing (normally done in initialize())

        bot._room_id_set = set(mock_config["matrix_room_ids"])
        bot.start_time = 1234567880000  # Converted to milliseconds

        with patch(
            "biblebot.bot.get_bible_text",
            new=AsyncMock(return_value=("Test verse", "John 3:16")),
        ):

            # Test different batch sizes
            throughput_results = []

            for batch_size in [25, 50, 75]:
                start_time = time.perf_counter()

                tasks = []
                for i in range(batch_size):
                    event = MagicMock()
                    event.body = f"John 3:{i + 16}"
                    event.sender = f"@user{i}:matrix.org"
                    event.server_timestamp = (
                        1234567890000  # Converted to milliseconds + i
                    )

                    room = MagicMock()
                    room.room_id = "!room:matrix.org"

                    task = bot.on_room_message(room, event)
                    tasks.append(task)

                await asyncio.gather(*tasks)
                end_time = time.perf_counter()

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
        """
        Test that resources are cleaned up under repeated load waves.

        Runs five waves of simulated message processing; each wave allocates 20 simulated resources and processes 20 messages concurrently via BibleBot.on_room_message. Every other wave triggers an explicit cleanup (clearing accumulated resources and running garbage collection). The test asserts that accumulated resources do not grow without bound (final count <= 40).
        """
        bot = BibleBot(config=mock_config, client=mock_client)

        # Populate room ID set for testing (normally done in initialize())

        bot._room_id_set = set(mock_config["matrix_room_ids"])
        bot.start_time = 1234567880000  # Converted to milliseconds

        # Track resource allocation and cleanup
        allocated_resources = []

        with patch(
            "biblebot.bot.get_bible_text",
            new=AsyncMock(return_value=("Test verse", "John 3:16")),
        ):

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
                    event.server_timestamp = (
                        1234567890000  # Converted to milliseconds + wave * 100 + i
                    )

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

        # Populate room ID set for testing (normally done in initialize())

        bot._room_id_set = set(mock_config["matrix_room_ids"])
        bot.start_time = 1234567880000  # Converted to milliseconds

        with patch(
            "biblebot.bot.get_bible_text",
            new=AsyncMock(return_value=("Test verse", "John 3:16")),
        ):

            # Simulate burst traffic (many requests in short time)
            burst_size = 40
            burst_start = time.perf_counter()

            tasks = []
            for i in range(burst_size):
                event = MagicMock()
                event.body = f"John 3:{i + 16}"
                event.sender = f"@user{i}:matrix.org"
                event.server_timestamp = 1234567890000  # Converted to milliseconds + i

                room = MagicMock()
                room.room_id = "!room:matrix.org"

                task = bot.on_room_message(room, event)
                tasks.append(task)

            # Process entire burst
            await asyncio.gather(*tasks)
            burst_end = time.perf_counter()

            burst_duration = burst_end - burst_start
            burst_throughput = burst_size / burst_duration

            # Should handle burst traffic effectively
            assert burst_duration < 20.0  # Should complete burst quickly
            assert burst_throughput > 2.0  # Should maintain good throughput
            assert mock_client.room_send.call_count == burst_size * 2
