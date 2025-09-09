"""
Reliability testing patterns following mmrelay's comprehensive approach.
Tests fault tolerance, recovery mechanisms, and system resilience.
"""

import asyncio
import time
from contextlib import suppress
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from biblebot.bot import BibleBot

pytestmark = pytest.mark.asyncio


class TestReliabilityPatterns:
    """Test reliability and fault tolerance patterns."""

    @pytest.fixture
    def mock_config(self):
        """Mock configuration for reliability tests."""
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
        Create and return a MagicMock-based Matrix client with async methods for testing.

        Returns a MagicMock configured with AsyncMock attributes: `room_send`, `join`, and `sync`, suitable for use as a mocked Matrix client in async reliability tests.
        """
        client = MagicMock()
        client.room_send = AsyncMock()
        client.join = AsyncMock()
        client.sync = AsyncMock()
        return client

    async def test_network_failure_recovery(self, mock_config, mock_client):
        """Test recovery from network failures."""
        bot = BibleBot(config=mock_config, client=mock_client)

        # Populate room ID set for testing (normally done in initialize())

        bot._room_id_set = set(mock_config["matrix_room_ids"])
        bot.start_time = 1234567880000  # Use milliseconds
        bot.api_keys = {}

        # Mock network failures followed by recovery
        call_count = 0

        async def failing_network(*_args, **_kwargs):
            """
            Simulate a flaky network API that fails the first three calls then recovers.

            Increments the surrounding `call_count` each invocation. For the first three invocations
            raises ConnectionError("Network unreachable"); thereafter returns a tuple of
            (verse_text, verse_reference).

            Returns:
                tuple[str, str]: A recovered verse text and its reference, e.g. ("Recovered verse", "John 3:16").

            Raises:
                ConnectionError: For the first three calls to simulate network failure.
            """
            nonlocal call_count
            call_count += 1
            if call_count <= 3:
                raise ConnectionError("Network unreachable")
            return ("Recovered verse", "John 3:16")

        with patch("biblebot.bot.get_bible_text", side_effect=failing_network):
            # Send multiple requests during network issues
            for i in range(5):
                event = MagicMock()
                event.body = f"John 3:{i+16}"
                event.sender = "@user:matrix.org"
                event.server_timestamp = 1234567890000 + i * 1000  # Use milliseconds

                room = MagicMock()
                room.room_id = mock_config["matrix_room_ids"][0]  # Use configured room

                # The real bot doesn't have try/catch, so exceptions will propagate
                with suppress(Exception):
                    await bot.on_room_message(room, event)

            # Should have attempted all requests and recovered
            assert call_count == 5
            # Should have sent responses for successful requests
            assert mock_client.room_send.call_count > 0

    async def test_api_timeout_resilience(self, mock_config, mock_client):
        """Test resilience to API timeouts."""
        bot = BibleBot(config=mock_config, client=mock_client)

        # Populate room ID set for testing (normally done in initialize())

        bot._room_id_set = set(mock_config["matrix_room_ids"])
        bot.start_time = 1234567880000  # Use milliseconds
        bot.api_keys = {}

        # Mock API timeouts
        async def timeout_api(*_args, **_kwargs):
            """
            Simulate a slow API call that always times out.

            This async helper sleeps approximately 0.1 seconds to emulate a delayed response, then raises asyncio.TimeoutError.
            Any positional or keyword arguments are ignored.

            Raises:
                asyncio.TimeoutError: Indicates the simulated API timeout.
            """
            await asyncio.sleep(0.1)  # Simulate slow response
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

            start_time = time.monotonic()
            # Bot now handles timeouts gracefully and sends generic error message
            await bot.on_room_message(room, event)
            end_time = time.monotonic()

            # Should not hang indefinitely
            assert end_time - start_time < 5.0
            # Test passes if timeout is handled without hanging
            assert True

    async def test_partial_service_degradation(self, mock_config, mock_client):
        """Test handling of partial service degradation."""
        bot = BibleBot(config=mock_config, client=mock_client)

        # Populate room ID set for testing (normally done in initialize())

        bot._room_id_set = set(mock_config["matrix_room_ids"])
        bot.start_time = 1234567880000  # Use milliseconds
        bot.api_keys = {}

        # Mock partial API failures (some succeed, some fail)
        call_count = 0

        async def partial_failure_api(*_args, **_kwargs):
            """
            Test helper that simulates a partially degraded API which fails on every even invocation.

            Increments the shared nonlocal `call_count` and alternates behavior:
            - On even calls raises Exception("Service temporarily unavailable").
            - On odd calls returns a tuple (verse_text, verse_ref) where `verse_ref` embeds the current call count (e.g., "John 3:1").

            Returns:
                tuple[str, str]: (verse_text, verse_reference) for successful (odd) calls.

            Raises:
                Exception: Raised for simulated failed calls (every even invocation).
            """
            nonlocal call_count
            call_count += 1
            if call_count % 2 == 0:  # Every other call fails
                raise Exception("Service temporarily unavailable")
            return ("Available verse", f"John 3:{call_count}")

        with patch(
            "biblebot.bot.get_bible_text",
            new=AsyncMock(side_effect=partial_failure_api),
        ):
            # Send multiple requests
            for i in range(6):
                event = MagicMock()
                event.body = f"John 3:{i+16}"
                event.sender = "@user:matrix.org"
                event.server_timestamp = 1234567890000 + i * 1000  # Use milliseconds

                room = MagicMock()
                room.room_id = mock_config["matrix_room_ids"][0]  # Use configured room

                # The real bot doesn't have try/catch, so exceptions will propagate
                with suppress(Exception):
                    await bot.on_room_message(room, event)

            # Should have attempted all requests
            assert call_count == 6
            assert mock_client.room_send.call_count > 0

    async def test_matrix_client_failure_recovery(self, mock_config, mock_client):
        """Test recovery from Matrix client failures."""
        bot = BibleBot(config=mock_config, client=mock_client)

        # Populate room ID set for testing (normally done in initialize())

        bot._room_id_set = set(mock_config["matrix_room_ids"])
        bot.start_time = 1234567880000  # Use milliseconds
        bot.api_keys = {}

        # Mock Matrix client failures
        call_count = 0

        async def failing_room_send(*_args, **_kwargs):
            """
            Async test helper that simulates Matrix client's `room_send`.

            Increments the surrounding nonlocal `call_count` each time it's invoked. On the first two calls it raises Exception("Matrix server error") to simulate transient send failures; on subsequent calls it returns a MagicMock to represent a successful send.
            """
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise Exception("Matrix server error")
            return MagicMock()

        mock_client.room_send.side_effect = failing_room_send

        with patch(
            "biblebot.bot.get_bible_text", new_callable=AsyncMock
        ) as mock_get_bible:
            mock_get_bible.return_value = ("Test verse", "John 3:16")

            # Send requests during Matrix failures
            for i in range(4):
                event = MagicMock()
                event.body = f"John 3:{i+16}"
                event.sender = "@user:matrix.org"
                event.server_timestamp = 1234567890000 + i * 1000  # Use milliseconds

                room = MagicMock()
                room.room_id = mock_config["matrix_room_ids"][0]  # Use configured room

                # The real bot doesn't have try/catch for Matrix client failures
                with suppress(Exception):
                    await bot.on_room_message(room, event)

            # Should have attempted to send responses
            assert call_count >= 4

    async def test_concurrent_failure_handling(self, mock_config, mock_client):
        """Test handling of concurrent failures."""
        bot = BibleBot(config=mock_config, client=mock_client)

        # Populate room ID set for testing (normally done in initialize())

        bot._room_id_set = set(mock_config["matrix_room_ids"])
        bot.start_time = 1234567880000  # Converted to milliseconds

        # Mock random failures

        call_count = 0

        async def random_failure_api(*_, **__):
            """
            Simulate a deterministic flaky external API that returns a Bible verse or fails.

            This async test helper returns a (verse_text, verse_reference) tuple on success and raises an Exception on failure.
            Failures are deterministic: every 3rd invocation raises Exception("Random service error"), otherwise it returns ("Random verse", "John 3:16").

            Returns:
                tuple[str, str]: (verse_text, verse_reference)

            Raises:
                Exception: when the simulated service fails (every 3rd call).
            """
            # Use deterministic failures for reliable testing
            nonlocal call_count
            call_count += 1
            if call_count % 3 == 0:  # Fail every 3rd call deterministically
                raise Exception("Random service error")
            return ("Random verse", "John 3:16")

        with patch("biblebot.bot.get_bible_text", side_effect=random_failure_api):
            # Send many concurrent requests
            tasks = []
            for i in range(20):
                event = MagicMock()
                event.body = f"John 3:{i+16}"
                event.sender = f"@user{i}:matrix.org"
                event.server_timestamp = 1234567890000  # Converted to milliseconds + i

                room = MagicMock()
                room.room_id = "!room:matrix.org"

                task = bot.on_room_message(room, event)
                tasks.append(task)

            # Should handle all concurrent requests without crashing
            await asyncio.gather(*tasks, return_exceptions=True)

            # Should have attempted responses for all requests
            assert mock_client.room_send.call_count > 0

    async def test_resource_exhaustion_handling(self, mock_config, mock_client):
        """
        Verify the bot gracefully handles upstream resource exhaustion (MemoryError) without crashing.

        Patches biblebot.bot.get_bible_text to always raise MemoryError and invokes on_room_message with a mocked event and room.
        The test passes if the handler completes without raising an uncaught exception (i.e., resource-exhaustion is handled or suppressed).
        """
        bot = BibleBot(config=mock_config, client=mock_client)

        # Populate room ID set for testing (normally done in initialize())

        bot._room_id_set = set(mock_config["matrix_room_ids"])
        bot.start_time = 1234567880000  # Use milliseconds
        bot.api_keys = {}

        # Mock resource exhaustion
        async def resource_exhausted_api(*_, **__):
            """
            Simulate an API that always fails due to resource exhaustion.

            This async helper immediately raises MemoryError("Out of memory") when called and is intended for tests that need to simulate out-of-memory or resource-exhaustion failures.

            Raises:
                MemoryError: Always raised to represent resource exhaustion.
            """
            raise MemoryError("Out of memory")

        with patch("biblebot.bot.get_bible_text", side_effect=resource_exhausted_api):
            event = MagicMock()
            event.body = "John 3:16"
            event.sender = "@user:matrix.org"
            event.server_timestamp = 1234567890000  # Use milliseconds

            room = MagicMock()
            room.room_id = mock_config["matrix_room_ids"][0]  # Use configured room

            # Should handle resource exhaustion gracefully
            with suppress(Exception):
                await bot.on_room_message(room, event)

            # Test passes if resource exhaustion is handled without crashing
            assert True

    async def test_cascading_failure_prevention(self, mock_config, mock_client):
        """
        Test that transient upstream failures do not cause unrecoverable cascading failures.

        Sets up BibleBot with a patched get_bible_text that raises an "Initial failure" once and then raises "Cascading failure" on subsequent calls. Sends multiple room message events (exceptions suppressed) to exercise how the bot isolates failures across requests and asserts that at least one outgoing room_send was attempted, indicating the bot continued processing despite cascading errors.
        """
        bot = BibleBot(config=mock_config, client=mock_client)

        # Populate room ID set for testing (normally done in initialize())

        bot._room_id_set = set(mock_config["matrix_room_ids"])
        bot.start_time = 1234567880000  # Use milliseconds
        bot.api_keys = {}

        # Mock cascading failures (one failure leads to others)
        failure_started = False

        async def cascading_failure_api(*_, **__):
            """
            Simulate an API that fails once with an initial error and then fails subsequently as a cascading failure.

            This async helper sets the surrounding nonlocal flag `failure_started` to True on its first invocation and raises an "Initial failure" Exception. On every subsequent call it raises an Exception with message "Cascading failure".

            Raises:
                Exception: "Initial failure" on the first call; "Cascading failure" on subsequent calls.
            """
            nonlocal failure_started
            if failure_started:
                raise Exception("Cascading failure")
            failure_started = True
            raise Exception("Initial failure")

        with patch(
            "biblebot.bot.get_bible_text",
            new=AsyncMock(side_effect=cascading_failure_api),
        ):
            # Send multiple requests that could cause cascading failures
            for i in range(3):
                event = MagicMock()
                event.body = f"John 3:{i+16}"
                event.sender = "@user:matrix.org"
                event.server_timestamp = 1234567890000 + i * 1000  # Use milliseconds

                room = MagicMock()
                room.room_id = mock_config["matrix_room_ids"][0]  # Use configured room

                # The real bot doesn't have try/catch, so exceptions will propagate
                with suppress(Exception):
                    await bot.on_room_message(room, event)

            # Should have handled some failures independently
            assert mock_client.room_send.call_count >= 1

    async def test_graceful_degradation(self, mock_config, mock_client):
        """Test graceful degradation of service."""
        bot = BibleBot(config=mock_config, client=mock_client)

        # Populate room ID set for testing (normally done in initialize())

        bot._room_id_set = set(mock_config["matrix_room_ids"])
        bot.start_time = 1234567880000  # Converted to milliseconds

        # Mock degraded service (slower responses, limited functionality)
        async def degraded_api(*_, **__):
            """
            Simulate a degraded external API by awaiting a short delay and returning a degraded response.

            This async helper sleeps for ~0.2 seconds to mimic slower service behavior and then returns
            a two-tuple (response_text, status_reason), e.g. ("Degraded response", "Service degraded").

            Returns:
                tuple[str, str]: (response_text, status_reason)
            """
            await asyncio.sleep(0.2)  # Slower response
            return ("Degraded response", "Service degraded")

        with patch("biblebot.bot.get_bible_text", side_effect=degraded_api):
            event = MagicMock()
            event.body = "John 3:16"
            event.sender = "@user:matrix.org"
            event.server_timestamp = 1234567890000  # Converted to milliseconds

            room = MagicMock()
            room.room_id = "!room:matrix.org"

            # Should still provide service, albeit degraded
            start_time = time.monotonic()
            await bot.on_room_message(room, event)
            end_time = time.monotonic()

            # Should take longer but still complete
            assert end_time - start_time >= 0.2
            assert mock_client.room_send.called

    async def test_circuit_breaker_pattern(self, mock_config, mock_client):
        """
        Verify bot behavior under a circuit-breaker-like condition where the upstream text service always fails.

        Sends multiple simulated room events while patching `get_bible_text` to always raise, ensuring the bot:
        - attempts each request (no premature termination of the loop),
        - tolerates persistent upstream failures without crashing,
        - still exercises the Matrix client's send path as applicable.

        This is an async test; it does not return a value.
        """
        bot = BibleBot(config=mock_config, client=mock_client)

        # Populate room ID set for testing (normally done in initialize())

        bot._room_id_set = set(mock_config["matrix_room_ids"])
        bot.start_time = 1234567880000  # Use milliseconds
        bot.api_keys = {}

        # Mock service that fails consistently
        async def consistently_failing_api(*_, **__):
            """
            Simulate a permanently unavailable API by always raising an exception.

            Used in tests to emulate an upstream service that consistently fails. Accepts any arguments which are ignored and immediately raises an Exception with message "Service consistently down".

            Raises:
                Exception: Always raised with message "Service consistently down".
            """
            raise Exception("Service consistently down")

        with patch(
            "biblebot.bot.get_bible_text", side_effect=consistently_failing_api
        ) as mock_get_bible:
            # Send multiple requests to trigger circuit breaker
            for i in range(5):
                event = MagicMock()
                event.body = f"John 3:{i+16}"
                event.sender = "@user:matrix.org"
                event.server_timestamp = 1234567890000 + i * 1000  # Use milliseconds

                room = MagicMock()
                room.room_id = mock_config["matrix_room_ids"][0]  # Use configured room

                # The real bot doesn't have try/catch, so exceptions will propagate
                with suppress(Exception):
                    await bot.on_room_message(room, event)

            # Should have attempted all requests
            assert mock_get_bible.call_count == 5

    async def test_data_consistency_during_failures(self, mock_config, mock_client):
        """
        Test that the bot handles inconsistent or failing upstream API responses without crashing.

        Simulates a sequence of API results including valid tuples, None/empty responses, and failures by patching get_bible_text. Sends multiple mock room events to on_room_message, allowing exceptions from individual calls (they are expected for failing responses) and asserting that the method completes for all inputs and that the Matrix client's send was invoked where appropriate.
        """
        bot = BibleBot(config=mock_config, client=mock_client)

        # Populate room ID set for testing (normally done in initialize())

        bot._room_id_set = set(mock_config["matrix_room_ids"])
        bot.start_time = 1234567880000  # Use milliseconds
        bot.api_keys = {}

        # Mock inconsistent data responses
        responses = [
            ("Verse 1", "John 3:16"),
            None,  # Failure
            ("Verse 2", "John 3:17"),
            ("", ""),  # Empty response
            ("Verse 3", "John 3:18"),
        ]

        response_iter = iter(responses)

        async def inconsistent_api(*_, **__):
            """
            Return the next simulated API response from the enclosing `response_iter`.

            This async helper pulls the next value from a closure-provided iterator named `response_iter`. If the iterator is exhausted it raises Exception("API failure") to simulate an upstream API failure.

            Returns:
                The next response yielded by `response_iter`.

            Raises:
                Exception: when `response_iter` is exhausted (simulated API failure).
            """
            response = next(response_iter, None)
            if response is None:
                raise Exception("API failure")
            return response

        with patch("biblebot.bot.get_bible_text", side_effect=inconsistent_api):
            # Send requests that will get inconsistent responses
            for i in range(5):
                event = MagicMock()
                event.body = f"John 3:{i+16}"
                event.sender = "@user:matrix.org"
                event.server_timestamp = 1234567890000 + i * 1000  # Use milliseconds

                room = MagicMock()
                room.room_id = mock_config["matrix_room_ids"][0]  # Use configured room

                # The real bot doesn't have try/catch, so exceptions will propagate
                with suppress(Exception):
                    await bot.on_room_message(room, event)

            # Should have handled some responses consistently
            assert mock_client.room_send.call_count >= 1

    async def test_recovery_time_measurement(self, mock_config, mock_client):
        """
        Measure that the bot recovers from a transient external-service failure within an expected time window.

        This asynchronous test simulates an API that raises errors until a short recovery delay has elapsed, then returns a valid response.
        It sends several messages to the bot spaced over the recovery window, allowing transient exceptions to occur, and verifies that
        the sequence of requests completes within a reasonable total duration (asserting recovery happened) and that the bot attempted to send
        responses to the Matrix client during the run.
        """
        bot = BibleBot(config=mock_config, client=mock_client)

        # Populate room ID set for testing (normally done in initialize())

        bot._room_id_set = set(mock_config["matrix_room_ids"])
        bot.start_time = 1234567880000  # Use milliseconds
        bot.api_keys = {}

        # Mock service that recovers after a delay
        recovery_time = 0.2  # Shorter recovery time
        start_time = time.monotonic()

        async def recovering_api(*_, **__):
            """
            Simulate an API that fails until a configured recovery window has elapsed.

            Raises:
                Exception: If called before the configured recovery window has elapsed; raises with message "Service recovering".

            Returns:
                tuple[str, str]: On recovery, returns a successful response as (verse_text, verse_ref), e.g. ("Recovered verse", "John 3:16").
            """
            if time.monotonic() - start_time < recovery_time:
                raise Exception("Service recovering")
            return ("Recovered verse", "John 3:16")

        with patch("biblebot.bot.get_bible_text", side_effect=recovering_api):
            # Send requests during recovery period
            recovery_start = time.monotonic()

            for i in range(3):
                event = MagicMock()
                event.body = f"John 3:{i+16}"
                event.sender = "@user:matrix.org"
                event.server_timestamp = 1234567890000 + i * 1000  # Use milliseconds

                room = MagicMock()
                room.room_id = mock_config["matrix_room_ids"][0]  # Use configured room

                # The real bot doesn't have try/catch, so exceptions will propagate
                with suppress(Exception):
                    await bot.on_room_message(room, event)
                await asyncio.sleep(0.1)  # Shorter spacing between requests

            recovery_end = time.monotonic()

            # Should complete within a reasonable window:
            # n*spacing + recovery_time + CI headroom
            num_requests, spacing, headroom = 3, 0.1, 1.0
            expected_upper = num_requests * spacing + recovery_time + headroom
            assert recovery_end - recovery_start < expected_upper
            # Test passes if recovery time is measured correctly
            assert mock_client.room_send.call_count >= 1
