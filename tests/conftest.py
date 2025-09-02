import asyncio
import contextlib
import gc
import os
import sys
import warnings
from concurrent.futures import Future
from pathlib import Path

import pytest

# Ensure src/ is importable without installation
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


def clear_env(keys):
    """
    Remove specified environment variables from os.environ and return their previous values.

    Parameters:
        keys (iterable): An iterable of environment variable names (strings) to remove.

    Returns:
        dict: A mapping of removed environment variable names to their previous values.
    """
    removed = {}
    for k in keys:
        if k in os.environ:
            removed[k] = os.environ.pop(k)
    return removed


@pytest.fixture(autouse=True)
def cleanup_asyncmock_objects(request):
    """
    Force garbage collection after tests that commonly create AsyncMock objects to prevent "never awaited" RuntimeWarning messages.

    This autouse pytest fixture yields to the test and, after the test completes, triggers a garbage collection sweep for tests whose filename matches known AsyncMock-using patterns (e.g., "test_cli", "test_bot", "test_auth", "test_integration"). During cleanup it temporarily suppresses RuntimeWarning about unawaited coroutines so spurious warnings are not raised.
    """
    yield

    # Only force garbage collection for tests that might create AsyncMock objects
    test_file = request.node.fspath.basename

    # List of test files/patterns that use AsyncMock
    asyncmock_patterns = [
        "test_cli",
        "test_bot",
        "test_auth",
        "test_integration",
    ]

    if any(pattern in test_file for pattern in asyncmock_patterns):
        # Suppress RuntimeWarning about unawaited coroutines during cleanup
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore", category=RuntimeWarning, message=".*never awaited.*"
            )
            gc.collect()


@pytest.fixture(autouse=True)
def mock_submit_coro(monkeypatch):
    """
    Replace any existing `_submit_coro` function with a synchronous runner that awaits AsyncMock coroutines and returns a concurrent.futures.Future with the result or exception.

    This pytest fixture patches `biblebot.bot._submit_coro` (if present) with an implementation that:
    - returns None for non-coroutines,
    - creates a temporary event loop, runs the coroutine to completion, and returns a Future containing the result or exception.

    Yields control to the test; `monkeypatch` will restore the original attribute after the test.
    """
    import inspect

    def mock_submit(coro, _loop=None):  # noqa: ARG001
        """
        Run a coroutine to completion on a temporary event loop and return a Future containing its outcome.

        If `coro` is not a coroutine object, returns None. Otherwise this function creates a new event loop,
        runs the coroutine to completion, and returns a concurrent.futures.Future that is already resolved
        with the coroutine's result or completed with the coroutine's raised exception. The temporary loop
        is closed before returning.
        """
        if not inspect.iscoroutine(coro):  # Not a coroutine
            return None

        # For AsyncMock coroutines, we need to actually await them to get the result
        # and prevent "never awaited" warnings, while also triggering any side effects
        temp_loop = asyncio.new_event_loop()
        try:
            result = temp_loop.run_until_complete(coro)
            future = Future()
            future.set_result(result)
            return future
        except Exception as e:
            future = Future()
            future.set_exception(e)
            return future
        finally:
            temp_loop.close()

    # Try to patch any _submit_coro functions that might exist
    try:
        import biblebot.bot as bot_module

        if hasattr(bot_module, "_submit_coro"):
            monkeypatch.setattr(bot_module, "_submit_coro", mock_submit)
    except (ImportError, AttributeError):
        pass

    yield


@pytest.fixture(autouse=True)
def comprehensive_cleanup():
    """
    Comprehensive resource cleanup fixture for tests that create async resources.

    This fixture ensures all system resources are properly cleaned up after tests,
    preventing resource warnings about unclosed sockets and event loops.
    Particularly important for Python 3.10+ compatibility in CI environments.
    """
    yield

    # Force cleanup of all async tasks and event loops
    try:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.get_event_loop_policy().get_event_loop()

        if loop and not loop.is_closed():
            # Cancel all pending tasks
            pending_tasks = [
                task for task in asyncio.all_tasks(loop) if not task.done()
            ]
            if pending_tasks:
                for task in pending_tasks:
                    task.cancel()
                # Use a new loop to gather cancelled tasks
                gather_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(gather_loop)
                gather_loop.run_until_complete(
                    asyncio.gather(*pending_tasks, return_exceptions=True)
                )
                gather_loop.close()

            # Shutdown any remaining executors
            if hasattr(loop, "_default_executor") and loop._default_executor:
                with contextlib.suppress(Exception):
                    executor = loop._default_executor
                    loop._default_executor = None
                    executor.shutdown(wait=True)

            # Close the original event loop if it's not the main one
            if loop is not asyncio.get_event_loop_policy().get_event_loop():
                with contextlib.suppress(Exception):
                    loop.close()

    except Exception:
        # Suppress any errors during cleanup to avoid affecting test results
        pass

    # Ensure the main event loop is reset
    asyncio.set_event_loop(None)

    # Force garbage collection to clean up any remaining resources
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore", category=ResourceWarning, message="unclosed.*"
        )
        warnings.filterwarnings(
            "ignore", category=RuntimeWarning, message=".*never awaited.*"
        )
        warnings.filterwarnings(
            "ignore", category=DeprecationWarning, message=".*no current event loop.*"
        )
        gc.collect()
