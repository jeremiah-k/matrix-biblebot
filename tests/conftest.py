import asyncio
import contextlib
import gc
import os
import sys
import threading
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
    removed = {}
    for k in keys:
        if k in os.environ:
            removed[k] = os.environ.pop(k)
    return removed


@pytest.fixture(autouse=True)
def cleanup_asyncmock_objects(request):
    """
    Force garbage collection after tests that commonly create AsyncMock objects to avoid "never awaited" RuntimeWarning messages.

    This fixture is based on the mmrelay testing patterns and helps prevent AsyncMock warnings.
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
    Mock any _submit_coro functions to properly await AsyncMock coroutines.

    Based on mmrelay patterns to ensure AsyncMock coroutines are properly awaited.
    """
    import inspect

    def mock_submit(coro, loop=None):
        """
        Synchronously runs a coroutine in a temporary event loop and returns a Future with its result or exception.
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
def comprehensive_cleanup(request):
    """
    Comprehensive resource cleanup fixture for tests that create async resources.

    Based on mmrelay patterns to ensure all system resources are properly cleaned up.
    """
    yield

    # Only perform async cleanup for tests that might need it
    test_file = request.node.fspath.basename
    test_name = request.node.name

    # List of test files/patterns that use async resources
    async_patterns = ["test_bot", "test_integration", "async", "main_function"]

    needs_async_cleanup = any(
        pattern in test_file.lower() or pattern in test_name.lower()
        for pattern in async_patterns
    )

    if needs_async_cleanup:
        # Force cleanup of all async tasks and event loops
        try:
            try:
                loop = asyncio.get_running_loop()
                if loop and not loop.is_closed():
                    # Cancel all pending tasks
                    pending_tasks = [
                        task for task in asyncio.all_tasks(loop) if not task.done()
                    ]
                    for task in pending_tasks:
                        task.cancel()

                    # Wait for cancelled tasks to complete
                    if pending_tasks:
                        with contextlib.suppress(Exception):
                            loop.run_until_complete(
                                asyncio.gather(*pending_tasks, return_exceptions=True)
                            )
            except RuntimeError:
                pass  # No running event loop

        except Exception:
            pass  # Ignore any cleanup errors

    # Force garbage collection to clean up any remaining resources
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore", category=RuntimeWarning, message=".*never awaited.*"
        )
        warnings.filterwarnings(
            "ignore", category=DeprecationWarning, message=".*no current event loop.*"
        )
        gc.collect()
