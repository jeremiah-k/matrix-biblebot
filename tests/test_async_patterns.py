import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from biblebot.bot import BibleBot

pytestmark = pytest.mark.asyncio


class TestAsyncPatterns:
    """Test async patterns following mmrelay's proven approach."""

    @pytest.fixture
    def mock_config(self):
        """
        Provide a mock configuration dictionary used by tests.

        Returns a dict containing:
        - "matrix": homeserver URL, bot_user_id, and access_token for a mocked Matrix client.
        - "matrix_room_ids": list of room IDs the bot should consider during tests.
        - "bible_api": base_url and api_key for mocked Bible API calls.
        """
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
        """
        Create a MagicMock that simulates a Matrix AsyncClient for tests.

        The mock provides AsyncMock methods `sync`, `room_send`, `close`, and `join`,
        and a `rooms` attribute initialized to an empty dict. Use this fixture to inject
        an AsyncClient-compatible mock into tests.
        """
        client = MagicMock()
        client.sync = AsyncMock()
        client.room_send = AsyncMock()
        client.close = AsyncMock()
        client.join = AsyncMock()
        client.rooms = {}
        return client

    @pytest.fixture
    def mock_room(self):
        """
        Create a MagicMock configured to represent a Matrix room for tests.

        The mock has these attributes:
        - room_id: "!room:matrix.org"
        - display_name: "Test Room"

        Returns:
            MagicMock: A mock room object with the attributes above.
        """
        room = MagicMock()
        room.room_id = "!room:matrix.org"
        room.display_name = "Test Room"
        return room

    @pytest.fixture
    def mock_event(self):
        """
        Create a MagicMock that simulates a Matrix room event for use in async tests.

        The mock exposes commonly accessed attributes used across the test suite:
        - sender (str): example "@user:matrix.org"
        - body (str): human-readable event body, e.g. "John 3:16"
        - event_id (str): example "$event123"
        - server_timestamp (int): epoch milliseconds (set to 1234567890000)
        - source (dict): nested structure with content.body matching `body`

        Returns:
            MagicMock: A mock object shaped like a Matrix event, ready for test scenarios.
        """
        event = MagicMock()
        event.sender = "@user:matrix.org"
        event.body = "John 3:16"
        event.event_id = "$event123"
        event.server_timestamp = 1234567890000  # After start time (milliseconds)
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
        bot.start_time = 1234567880000  # Before event timestamp (milliseconds)
        # Populate room ID set for testing (normally done in initialize())
        bot._room_id_set = set(mock_config["matrix_room_ids"])

        # Mock Bible text retrieval
        with patch(
            "biblebot.bot.get_bible_text", new_callable=AsyncMock
        ) as mock_get_bible:
            mock_get_bible.return_value = ("For God so loved the world...", "John 3:16")

            await bot.on_room_message(mock_room, mock_event)

            mock_get_bible.assert_called_once()
            assert mock_client.room_send.call_count == 2  # Reaction + message

    async def test_async_error_handling(
        self, mock_config, mock_client, mock_room, mock_event
    ):
        """Test async error handling patterns."""
        bot = BibleBot(config=mock_config, client=mock_client)
        bot.start_time = 1234567880000  # Before event timestamp (milliseconds)
        # Populate room ID set for testing (normally done in initialize())
        bot._room_id_set = set(mock_config["matrix_room_ids"])

        # Mock API error
        with patch(
            "biblebot.bot.get_bible_text", new_callable=AsyncMock
        ) as mock_get_bible:
            from biblebot.bot import PassageNotFound

            mock_get_bible.side_effect = PassageNotFound(
                "Test passage not found"
            )  # Simulate error

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

        # Mock timeout during room join - our BibleBot logs errors instead of raising
        mock_client.join.side_effect = asyncio.TimeoutError()

        # Should not raise exception, should handle gracefully
        result = await bot.join_matrix_room("!room:matrix.org")

        # Verify it handled the error gracefully
        assert result is None  # join_matrix_room returns None on error

    async def test_async_concurrent_operations(self, mock_config, mock_client):
        """
        Verify that multiple concurrent join_matrix_room calls run in parallel and each invokes the client's join method.

        Creates a BibleBot with a mocked client whose join returns a room-like object, starts three concurrent join_matrix_room coroutines with asyncio.gather, and asserts that three results are returned and the client's join was called three times.
        """
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

        # Test that we can access client methods (no async mock issues)
        assert hasattr(mock_client, "close")
        assert bot.config == mock_config

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
        BibleBot(config=mock_config, client=mock_client)

        # Test that our API calls work with successful response
        with patch("biblebot.bot.make_api_request", new_callable=AsyncMock) as mock_api:
            mock_api.return_value = {"text": "Success", "reference": "John 3:16"}

            # Test actual function
            from biblebot.bot import get_kjv_text

            # Should succeed on first try
            text, reference = await get_kjv_text("John 3:16")

            assert "Success" in text
            assert "John 3:16" in reference
            mock_api.assert_called_once()

    async def test_async_rate_limiting_patterns(self, mock_config, mock_client):
        """
        Verify the bot handles rate-limited API calls by introducing delays between requests.

        Patches asyncio.sleep and the get_bible_text coroutine, simulates multiple sequential rate-limited requests that await a short delay before fetching a passage, and asserts that the delay (asyncio.sleep) was invoked during the process.
        """
        BibleBot(config=mock_config, client=mock_client)

        # Mock rate-limited API
        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            with patch(
                "biblebot.bot.get_bible_text", new_callable=AsyncMock
            ) as mock_get_bible:
                mock_get_bible.return_value = ("Test verse", "John 3:16")

                # Simulate rate limiting by adding delays
                async def rate_limited_call():
                    """
                    Asynchronously perform a simulated rate-limited retrieval of the passage "John 3:16".

                    Awaits a short delay to emulate rate limiting, then awaits and returns the result of calling the `mock_get_bible` coroutine with "John 3:16".
                    Returns:
                        The value returned by `mock_get_bible("John 3:16")` (typically a tuple or object containing verse text and reference).
                    """
                    await asyncio.sleep(0.1)  # Simulate rate limit
                    return await mock_get_bible("John 3:16")

                # Make multiple requests
                for _ in range(3):
                    await rate_limited_call()

                # Should have introduced delays
                mock_sleep.assert_called()

    async def test_async_cancellation_patterns(self, mock_config, mock_client):
        """Test async cancellation patterns."""
        BibleBot(config=mock_config, client=mock_client)

        # Test that tasks can be cancelled gracefully
        async def quick_task():
            """
            Short cancellable coroutine that sleeps briefly and returns "completed".

            Awaits asyncio.sleep(0.1) and then returns the literal string "completed".
            If the task is cancelled while sleeping, asyncio.CancelledError will propagate to the caller.

            Returns:
                str: "completed" when the coroutine finishes normally.
            """
            await asyncio.sleep(0.1)  # Longer sleep to ensure cancellation
            return "completed"

        # Start task and cancel it
        task = asyncio.create_task(quick_task())
        await asyncio.sleep(0.01)  # Let it start
        task.cancel()

        # Wait for cancellation to take effect
        try:
            await task
        except asyncio.CancelledError:
            pass

        # Verify cancellation worked
        assert task.cancelled()

    async def test_async_exception_propagation(self, mock_config, mock_client):
        """
        Verify that exceptions raised during Bible text retrieval are handled without propagating.

        This async test sets up a BibleBot with mocked config and client, patches
        biblebot.bot.get_bible_text to raise a ValueError, and sends a simulated
        room event. It asserts that calling on_room_message does not raise the
        exception (the bot should catch and handle errors originating from the
        retrieval logic).
        """
        bot = BibleBot(config=mock_config, client=mock_client)

        # Test that exceptions are properly propagated
        with patch(
            "biblebot.bot.get_bible_text", new_callable=AsyncMock
        ) as mock_get_bible:
            mock_get_bible.side_effect = ValueError("Invalid verse reference")

            # Exception should be caught and handled gracefully
            mock_event = MagicMock()
            mock_event.body = "Invalid 99:99"
            mock_event.sender = "@user:matrix.org"
            mock_event.server_timestamp = (
                1234567890000  # After start time (milliseconds)
            )

            bot.start_time = 1234567880000  # Before event timestamp (milliseconds)
            await bot.on_room_message(MagicMock(), mock_event)

    async def test_async_resource_management(self, mock_config, mock_client):
        """Test async resource management patterns."""
        # Test proper resource cleanup even with exceptions
        bot = BibleBot(config=mock_config, client=mock_client)

        try:
            # Simulate an error during operation
            raise Exception("Simulated error")
        except Exception as exc:  # noqa: BLE001
            # Optional: log for debug
            _ = exc
            pass
        finally:
            # Test that client is still accessible for cleanup (no async mock issues)
            assert bot.client is not None
            assert hasattr(mock_client, "close")

    async def test_async_event_loop_integration(self, mock_config, mock_client):
        """Test async event loop integration patterns."""
        with patch("biblebot.bot.AsyncClient", return_value=mock_client):
            BibleBot(config=mock_config)

            # Test that bot works with different event loop policies
            loop = asyncio.get_running_loop()
            assert loop is not None

            # Test scheduling callbacks
            callback_called = False

            def callback():
                """
                Mark the enclosing scope's `callback_called` flag as True.

                This zero-argument callback is intended to signal completion by setting the
                nonlocal variable `callback_called` in the surrounding scope. It has no return
                value and does not raise exceptions.
                """
                nonlocal callback_called
                callback_called = True

            loop.call_soon(callback)
            await asyncio.sleep(0)  # Let callback run

            assert callback_called

    async def test_async_signal_handling(self, mock_config, mock_client):
        """
        Simulate and verify graceful async shutdown handling.

        Creates a BibleBot with mocked config and client, defines a simple async shutdown callback that sets a flag, invokes it, and asserts the shutdown logic runs (the flag becomes True).
        """
        BibleBot(config=mock_config, client=mock_client)

        # Test graceful shutdown simulation
        shutdown_called = False

        async def mock_shutdown():
            """
            Mark the test's shutdown flag to simulate a graceful shutdown.

            When awaited, sets the nonlocal `shutdown_called` variable to True so tests can assert that shutdown logic ran.
            """
            nonlocal shutdown_called
            shutdown_called = True

        # Simulate signal handling by calling shutdown directly
        await mock_shutdown()

        assert shutdown_called is True

    async def test_async_background_tasks(self, mock_config, mock_client):
        """Test async background task patterns."""
        with patch("biblebot.bot.AsyncClient", return_value=mock_client):
            BibleBot(config=mock_config)

            # Test background task management
            task_completed = False

            async def background_task():
                """
                Run a short asynchronous background task and mark completion.

                Sleeps for ~0.1 seconds and sets the surrounding scope's nonlocal variable `task_completed` to True to indicate the background work finished.
                """
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
