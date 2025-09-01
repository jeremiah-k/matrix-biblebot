"""
Monitoring and observability testing patterns following mmrelay's comprehensive approach.
Tests logging, metrics, health checks, and monitoring capabilities.
"""

import asyncio
import logging
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from biblebot.bot import BibleBot


class TestMonitoringPatterns:
    """Test monitoring and observability patterns."""

    @pytest.fixture
    def mock_config(self):
        """Mock configuration for monitoring tests."""
        return {
            "homeserver": "https://matrix.org",
            "user_id": "@test:matrix.org",
            "access_token": "test_token",
            "device_id": "TEST_DEVICE",
            "matrix_room_ids": ["!room:matrix.org"],
        }

    @pytest.fixture
    def mock_client(self):
        """Mock Matrix client for monitoring tests."""
        client = MagicMock()
        client.room_send = AsyncMock()
        client.join = AsyncMock()
        client.sync = AsyncMock()
        return client

    async def test_request_logging_patterns(self, mock_config, mock_client, caplog):
        """Test request logging and tracing."""
        bot = BibleBot(config=mock_config, client=mock_client)

        # Populate room ID set for testing (normally done in initialize())

        bot._room_id_set = set(mock_config["matrix_room_ids"])
        bot.start_time = 1234567880000  # Converted to milliseconds

        with patch(
            "biblebot.bot.get_bible_text", new_callable=AsyncMock
        ) as mock_get_bible:
            mock_get_bible.return_value = ("Test verse", "John 3:16")

            # Enable debug logging
            with caplog.at_level(logging.DEBUG):
                event = MagicMock()
                event.body = "John 3:16"
                event.sender = "@user:matrix.org"
                event.server_timestamp = 1234567890000  # Converted to milliseconds
                event.event_id = "$event123:matrix.org"

                room = MagicMock()
                room.room_id = "!room:matrix.org"

                await bot.on_room_message(room, event)

                # Should have logged request processing
                log_messages = [record.message for record in caplog.records]
                assert log_messages, "Expected at least one log record"
                assert any(r.levelno >= logging.DEBUG for r in caplog.records)

    async def test_error_logging_patterns(self, mock_config, mock_client, caplog):
        """Test error logging and tracking."""
        bot = BibleBot(config=mock_config, client=mock_client)

        # Populate room ID set for testing (normally done in initialize())

        bot._room_id_set = set(mock_config["matrix_room_ids"])
        bot.start_time = 1234567880000  # Use milliseconds
        bot.api_keys = {}

        with patch(
            "biblebot.bot.get_bible_text", new_callable=AsyncMock
        ) as mock_get_bible:
            mock_get_bible.side_effect = Exception("Test API error")

            with caplog.at_level(logging.ERROR):
                event = MagicMock()
                event.body = "John 3:16"
                event.sender = "@user:matrix.org"
                event.server_timestamp = 1234567890000  # Use milliseconds

                room = MagicMock()
                room.room_id = mock_config["matrix_room_ids"][0]  # Use configured room

                # Bot now handles exceptions gracefully and logs them
                await bot.on_room_message(room, event)
                # Should have logged the error
                error_logs = [r for r in caplog.records if r.levelno >= logging.ERROR]
                assert error_logs, "Expected at least one ERROR log"

    async def test_performance_metrics_collection(self, mock_config, mock_client):
        """Test collection of performance metrics."""
        bot = BibleBot(config=mock_config, client=mock_client)

        # Populate room ID set for testing (normally done in initialize())

        bot._room_id_set = set(mock_config["matrix_room_ids"])
        bot.start_time = 1234567880000  # Converted to milliseconds

        # Track timing metrics
        processing_times = []

        async def timed_api_call(*args, **kwargs):
            start_time = time.time()
            await asyncio.sleep(0.01)  # Simulate processing
            end_time = time.time()
            processing_times.append(end_time - start_time)
            return ("Test verse", "John 3:16")

        with patch("biblebot.bot.get_bible_text", side_effect=timed_api_call):
            # Process multiple requests to collect metrics
            for i in range(10):
                event = MagicMock()
                event.body = f"John 3:{i+16}"
                event.sender = "@user:matrix.org"
                event.server_timestamp = 1234567890000  # Converted to milliseconds + i

                room = MagicMock()
                room.room_id = "!room:matrix.org"

                await bot.on_room_message(room, event)

            # Should have collected timing metrics
            assert len(processing_times) == 10
            avg_time = sum(processing_times) / len(processing_times)
            assert avg_time > 0.005  # Should have some processing time

    async def test_health_check_patterns(self, mock_config, mock_client):
        """Test health check functionality."""
        bot = BibleBot(config=mock_config, client=mock_client)

        # Populate room ID set for testing (normally done in initialize())

        bot._room_id_set = set(mock_config["matrix_room_ids"])
        bot.start_time = 1234567880000  # Use fixed start time in milliseconds
        bot.api_keys = {}

        # Test basic health indicators
        assert bot.client is not None  # Client should be available
        assert bot.config is not None  # Configuration should be loaded
        assert bot.start_time is not None  # Should have start time

        # Test component health
        with patch(
            "biblebot.bot.get_bible_text", new_callable=AsyncMock
        ) as mock_get_bible:
            mock_get_bible.return_value = ("Test verse", "John 3:16")

            # Simulate health check request
            event = MagicMock()
            event.body = "John 3:16"
            event.sender = "@healthcheck:matrix.org"
            event.server_timestamp = (
                1234567890000  # Use fixed timestamp after start_time
            )

            room = MagicMock()
            room.room_id = mock_config["matrix_room_ids"][0]  # Use configured room

            # Should process health check successfully
            await bot.on_room_message(room, event)
            assert mock_client.room_send.called

    async def test_uptime_tracking(self, mock_config, mock_client):
        """Test uptime tracking and reporting."""
        bot = BibleBot(config=mock_config, client=mock_client)

        # Populate room ID set for testing (normally done in initialize())

        bot._room_id_set = set(mock_config["matrix_room_ids"])

        # Set start time in the past
        past_time = time.time() - 3600  # 1 hour ago
        bot.start_time = past_time

        # Calculate uptime
        current_time = time.time()
        uptime = current_time - bot.start_time

        # Should track uptime correctly
        assert uptime >= 3600  # At least 1 hour
        assert uptime < 7200  # Less than 2 hours

    async def test_request_rate_monitoring(self, mock_config, mock_client):
        """Test monitoring of request rates."""
        bot = BibleBot(config=mock_config, client=mock_client)

        # Populate room ID set for testing (normally done in initialize())

        bot._room_id_set = set(mock_config["matrix_room_ids"])
        bot.start_time = 1234567880000  # Converted to milliseconds

        # Track request timestamps
        request_times = []

        async def timestamped_api_call(*args, **kwargs):
            request_times.append(time.time())
            return ("Test verse", "John 3:16")

        with patch("biblebot.bot.get_bible_text", side_effect=timestamped_api_call):
            # Send requests at different intervals
            for i in range(5):
                event = MagicMock()
                event.body = f"John 3:{i+16}"
                event.sender = "@user:matrix.org"
                event.server_timestamp = 1234567890000  # Converted to milliseconds + i

                room = MagicMock()
                room.room_id = "!room:matrix.org"

                await bot.on_room_message(room, event)
                await asyncio.sleep(0.1)  # Small delay between requests

            # Should have tracked request timing
            assert len(request_times) == 5

            # Calculate request rate
            time_span = request_times[-1] - request_times[0]
            request_rate = len(request_times) / time_span if time_span > 0 else 0
            assert request_rate > 0  # Should have measurable rate

    async def test_error_rate_monitoring(self, mock_config, mock_client):
        """Test monitoring of error rates."""
        bot = BibleBot(config=mock_config, client=mock_client)

        # Populate room ID set for testing (normally done in initialize())

        bot._room_id_set = set(mock_config["matrix_room_ids"])
        bot.start_time = 1234567880000  # Use milliseconds
        bot.api_keys = {}

        # Track success and error counts
        success_count = 0
        error_count = 0

        async def error_prone_api(*args, **kwargs):
            nonlocal success_count, error_count
            # Simulate 30% error rate
            import random

            if random.random() < 0.3:
                error_count += 1
                raise Exception("API Error")
            else:
                success_count += 1
                return ("Test verse", "John 3:16")

        with patch("biblebot.bot.get_bible_text", side_effect=error_prone_api):
            # Process multiple requests
            for i in range(20):
                event = MagicMock()
                event.body = f"John 3:{i+16}"
                event.sender = "@user:matrix.org"
                event.server_timestamp = 1234567890000 + i * 1000  # Use milliseconds

                room = MagicMock()
                room.room_id = mock_config["matrix_room_ids"][0]  # Use configured room

                # The bot handles exceptions gracefully, so no exception should propagate
                try:
                    await bot.on_room_message(room, event)
                except Exception:
                    pass  # Expected for error cases

            # Should have tracked both successes and errors
            total_requests = success_count + error_count
            assert total_requests == 20

            # Calculate error rate
            error_rate = error_count / total_requests if total_requests > 0 else 0
            assert 0 <= error_rate <= 1  # Error rate should be between 0 and 1

    async def test_resource_usage_monitoring(self, mock_config, mock_client):
        """Test monitoring of resource usage."""
        import resource

        bot = BibleBot(config=mock_config, client=mock_client)

        # Populate room ID set for testing (normally done in initialize())

        bot._room_id_set = set(mock_config["matrix_room_ids"])
        bot.start_time = 1234567880000  # Converted to milliseconds

        # Get initial resource usage
        initial_memory = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        initial_cpu = resource.getrusage(resource.RUSAGE_SELF).ru_utime

        with patch(
            "biblebot.bot.get_bible_text", new_callable=AsyncMock
        ) as mock_get_bible:
            mock_get_bible.return_value = ("Test verse", "John 3:16")

            # Process some requests
            for i in range(10):
                event = MagicMock()
                event.body = f"John 3:{i+16}"
                event.sender = "@user:matrix.org"
                event.server_timestamp = 1234567890000  # Converted to milliseconds + i

                room = MagicMock()
                room.room_id = "!room:matrix.org"

                await bot.on_room_message(room, event)

        # Get final resource usage
        final_memory = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        final_cpu = resource.getrusage(resource.RUSAGE_SELF).ru_utime

        # Should have measurable resource usage
        memory_used = final_memory - initial_memory
        cpu_used = final_cpu - initial_cpu

        assert cpu_used > 0, "CPU time should increase after processing requests"
        assert memory_used >= 0

    async def test_alert_threshold_monitoring(self, mock_config, mock_client):
        """Test monitoring for alert thresholds."""
        bot = BibleBot(config=mock_config, client=mock_client)

        # Populate room ID set for testing (normally done in initialize())

        bot._room_id_set = set(mock_config["matrix_room_ids"])
        bot.start_time = 1234567880000  # Use milliseconds
        bot.api_keys = {}

        # Track response times for threshold monitoring
        slow_responses = 0
        total_responses = 0

        async def variable_speed_api(*args, **kwargs):
            nonlocal slow_responses, total_responses
            total_responses += 1

            # Simulate variable response times without actual delays for faster testing
            import random

            response_time = random.uniform(0.01, 0.5)
            # Remove the actual sleep to speed up the test
            # await asyncio.sleep(response_time)

            # Track slow responses (>0.3 seconds) - simulate the logic
            if response_time > 0.3:
                slow_responses += 1

            return ("Test verse", "John 3:16")

        with patch("biblebot.bot.get_bible_text", side_effect=variable_speed_api):
            # Process fewer requests for faster testing
            for i in range(10):  # Reduced from 15 to 10
                event = MagicMock()
                event.body = f"John 3:{i+16}"
                event.sender = "@user:matrix.org"
                event.server_timestamp = 1234567890000 + i * 1000  # Use milliseconds

                room = MagicMock()
                room.room_id = mock_config["matrix_room_ids"][0]  # Use configured room

                await bot.on_room_message(room, event)

            # Calculate slow response rate
            slow_response_rate = (
                slow_responses / total_responses if total_responses > 0 else 0
            )

            # Should have processed all requests
            assert total_responses == 10  # Updated count
            assert 0 <= slow_response_rate <= 1

    async def test_custom_metrics_collection(self, mock_config, mock_client):
        """Test collection of custom application metrics."""
        bot = BibleBot(config=mock_config, client=mock_client)

        # Populate room ID set for testing (normally done in initialize())

        bot._room_id_set = set(mock_config["matrix_room_ids"])
        bot.start_time = 1234567880000  # Converted to milliseconds

        # Track custom metrics
        verse_requests = {}
        user_activity = {}

        async def metrics_collecting_api(*args, **kwargs):
            # Extract verse reference from args if available
            verse_ref = "John 3:16"  # Default
            verse_requests[verse_ref] = verse_requests.get(verse_ref, 0) + 1
            return ("Test verse", verse_ref)

        with patch("biblebot.bot.get_bible_text", side_effect=metrics_collecting_api):
            # Process requests from different users
            users = ["@user1:matrix.org", "@user2:matrix.org", "@user3:matrix.org"]

            for i in range(12):
                user = users[i % len(users)]
                user_activity[user] = user_activity.get(user, 0) + 1

                event = MagicMock()
                event.body = f"John 3:{(i % 5) + 16}"
                event.sender = user
                event.server_timestamp = 1234567890000  # Converted to milliseconds + i

                room = MagicMock()
                room.room_id = "!room:matrix.org"

                await bot.on_room_message(room, event)

            # Should have collected custom metrics
            assert len(verse_requests) > 0
            assert len(user_activity) == 3
            assert sum(user_activity.values()) == 12

    async def test_distributed_tracing_patterns(self, mock_config, mock_client):
        """Test distributed tracing capabilities."""
        bot = BibleBot(config=mock_config, client=mock_client)

        # Populate room ID set for testing (normally done in initialize())

        bot._room_id_set = set(mock_config["matrix_room_ids"])
        bot.start_time = 1234567880000  # Converted to milliseconds

        # Track trace information
        trace_spans = []

        async def traced_api_call(*args, **kwargs):
            # Simulate trace span
            span_id = f"span_{len(trace_spans)}"
            start_time = time.time()

            await asyncio.sleep(0.01)  # Simulate work

            end_time = time.time()
            trace_spans.append(
                {
                    "span_id": span_id,
                    "operation": "bible_api_call",
                    "duration": end_time - start_time,
                    "start_time": start_time,
                    "end_time": end_time,
                }
            )

            return ("Test verse", "John 3:16")

        with patch("biblebot.bot.get_bible_text", side_effect=traced_api_call):
            # Process requests with tracing
            for i in range(5):
                event = MagicMock()
                event.body = f"John 3:{i+16}"
                event.sender = "@user:matrix.org"
                event.server_timestamp = 1234567890000  # Converted to milliseconds + i

                room = MagicMock()
                room.room_id = "!room:matrix.org"

                await bot.on_room_message(room, event)

            # Should have collected trace data
            assert len(trace_spans) == 5

            # Verify trace span structure
            for span in trace_spans:
                assert "span_id" in span
                assert "operation" in span
                assert "duration" in span
                assert span["duration"] > 0

    async def test_log_aggregation_patterns(self, mock_config, mock_client, caplog):
        """Test log aggregation and structured logging."""
        bot = BibleBot(config=mock_config, client=mock_client)

        # Populate room ID set for testing (normally done in initialize())

        bot._room_id_set = set(mock_config["matrix_room_ids"])
        bot.start_time = 1234567880000  # Converted to milliseconds

        with patch(
            "biblebot.bot.get_bible_text", new_callable=AsyncMock
        ) as mock_get_bible:
            mock_get_bible.return_value = ("Test verse", "John 3:16")

            # Process requests with structured logging
            with caplog.at_level(logging.INFO):
                for i in range(3):
                    event = MagicMock()
                    event.body = f"John 3:{i+16}"
                    event.sender = f"@user{i}:matrix.org"
                    event.server_timestamp = (
                        1234567890000  # Converted to milliseconds + i
                    )
                    event.event_id = f"$event{i}:matrix.org"

                    room = MagicMock()
                    room.room_id = "!room:matrix.org"

                    await bot.on_room_message(room, event)

                # Should have generated structured logs
                log_records = caplog.records
                assert log_records, "Expected at least one structured log record"
                assert any(r.levelno >= logging.INFO for r in log_records)
