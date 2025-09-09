import asyncio
import contextlib
import gc
import os
import sys
import warnings
from concurrent.futures import Future
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Ensure src/ is importable without installation
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

# Mock all E2EE dependencies before any imports can occur
# This prevents ImportError and allows tests to run without real E2EE setup


# Create proper Exception classes for nio.exceptions
class MockRemoteProtocolError(Exception):
    pass


class MockRemoteTransportError(Exception):
    pass


class MockLocalProtocolError(Exception):
    pass


class MockDiscoveryInfoError(Exception):
    pass


class MockLoginError(Exception):
    def __init__(self, message="", status_code=None, errcode=None):
        """
        Initialize the MockLoginError.
        
        Parameters:
            message (str): Human-readable error message (defaults to empty string).
            status_code (Optional[int]): HTTP-like status code associated with the error, if any.
            errcode (Optional[str]): Matrix/MX-style error code or internal error identifier, if any.
        
        Sets:
            self.message, self.status_code, self.errcode
        """
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.errcode = errcode

    def __repr__(self):
        """
        Return an unambiguous developer-friendly string representation of the MockLoginError.
        
        The resulting string includes the `message`, `status_code`, and `errcode`
        attributes in a form suitable for debugging, e.g.
        `MockLoginError(message='...', status_code=400, errcode='M_FORBIDDEN')`.
        
        Returns:
            str: The formatted representation.
        """
        return f"MockLoginError(message={self.message!r}, status_code={self.status_code!r}, errcode={self.errcode!r})"


class MockRoomResolveAliasError(Exception):
    def __init__(self, message=""):
        """
        Initialize the MockRoomResolveAliasError.
        
        Parameters:
            message (str): Optional human-readable error message describing the alias resolution failure.
        """
        super().__init__(message)
        self.message = message

    def __repr__(self):
        """
        Return a concise, developer-friendly string representation of the error.
        
        The representation includes the error's message attribute in the form
        `MockRoomResolveAliasError(message=<message>)` and is intended for debugging.
        """
        return f"MockRoomResolveAliasError(message={self.message!r})"


class MockDiscoveryInfoResponse:
    def __init__(self, homeserver_url=None):
        """
        Initialize a MockDiscoveryInfoResponse.
        
        Parameters:
            homeserver_url (str | None): The homeserver base URL to simulate in tests (e.g. "https://matrix.example"). If None, no URL is set.
        """
        self.homeserver_url = homeserver_url


class MockLoginResponse:
    def __init__(self, user_id=None, device_id=None, access_token=None):
        """
        Initialize a MockLoginResponse container with optional authentication fields.
        
        Parameters:
            user_id (str, optional): Matrix user identifier (e.g. '@alice:example.org').
            device_id (str, optional): Device identifier for the logged-in session.
            access_token (str, optional): Access token issued for the session.
        """
        self.user_id = user_id
        self.device_id = device_id
        self.access_token = access_token


# Create nio mock with proper exception classes
nio_mock = MagicMock()
nio_exceptions_mock = MagicMock()
nio_exceptions_mock.RemoteProtocolError = MockRemoteProtocolError
nio_exceptions_mock.RemoteTransportError = MockRemoteTransportError
nio_exceptions_mock.LocalProtocolError = MockLocalProtocolError
nio_exceptions_mock.DiscoveryInfoError = MockDiscoveryInfoError
nio_exceptions_mock.LoginError = MockLoginError
nio_exceptions_mock.RoomResolveAliasError = MockRoomResolveAliasError

sys.modules["nio"] = nio_mock
sys.modules["nio.events"] = MagicMock()
sys.modules["nio.events.room_events"] = MagicMock()
sys.modules["nio.events.misc"] = MagicMock()
sys.modules["nio.store"] = MagicMock()
sys.modules["nio.store.database"] = MagicMock()
sys.modules["nio.crypto"] = MagicMock()
sys.modules["nio.exceptions"] = nio_exceptions_mock

# Mock olm (E2EE crypto library)
olm_mock = MagicMock()
olm_mock.__spec__ = MagicMock()  # Required for importlib.util.find_spec
sys.modules["olm"] = olm_mock
sys.modules["olm.account"] = MagicMock()
sys.modules["olm.session"] = MagicMock()
sys.modules["olm.inbound_group_session"] = MagicMock()
sys.modules["olm.outbound_group_session"] = MagicMock()

# Mock other E2EE related dependencies
sys.modules["peewee"] = MagicMock()
sys.modules["atomicwrites"] = MagicMock()
sys.modules["cachetools"] = MagicMock()

# Set up nio mock attributes
nio_mock.AsyncClient = MagicMock()
nio_mock.AsyncClientConfig = MagicMock()
nio_mock.SqliteStore = MagicMock()
nio_mock.exceptions = nio_exceptions_mock
nio_mock.DiscoveryInfoResponse = MockDiscoveryInfoResponse
nio_mock.DiscoveryInfoError = MockDiscoveryInfoError
nio_mock.LoginError = MockLoginError
nio_mock.RoomResolveAliasError = MockRoomResolveAliasError
nio_mock.LoginResponse = MockLoginResponse

# Set up proper __spec__ for nio module to support importlib.util.find_spec
nio_mock.__spec__ = MagicMock()
nio_mock.__spec__.name = "nio"
nio_mock.__spec__.origin = "mocked"


def clear_env(keys):
    """
    Remove the given environment variables from os.environ and return their previous values.
    
    If a variable from `keys` is not present in the environment it is ignored.
    
    Parameters:
        keys (iterable[str]): Names of environment variables to remove.
    
    Returns:
        dict: Mapping of each removed variable name to its previous value.
    """
    removed = {}
    for k in keys:
        if k in os.environ:
            removed[k] = os.environ.pop(k)
    return removed


@pytest.fixture(autouse=True)
def event_loop_safety():
    """
    Create and provide a dedicated asyncio event loop for tests, ensuring proper cleanup.

    This fixture creates a fresh event loop, assigns it for use during tests,
    yields the loop, then cancels any remaining tasks, waits for them to finish,
    closes the loop, and clears the global event loop reference on teardown.
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    yield loop

    # Teardown: Clean up the loop
    try:
        tasks = asyncio.all_tasks(loop=loop)
        for task in tasks:
            task.cancel()
        if tasks:
            loop.run_until_complete(asyncio.gather(*tasks, return_exceptions=True))
    finally:
        loop.close()
        asyncio.set_event_loop(None)


@pytest.fixture(autouse=True)
def cleanup_asyncmock_objects(request):
    """
    Force garbage collection after tests that commonly create AsyncMock objects to prevent "never awaited" RuntimeWarning messages.

    This autouse pytest fixture yields to the test and, after the test completes, triggers a garbage collection sweep for tests whose filename matches known AsyncMock-using patterns (e.g., "test_cli", "test_bot", "test_auth", "test_integration"). During cleanup it temporarily suppresses RuntimeWarning about unawaited coroutines so spurious warnings are not raised.
    """
    yield

    # Only force garbage collection for tests that might create AsyncMock objects
    test_file = request.node.path.name

    # List of test files/patterns that use AsyncMock
    asyncmock_patterns = [
        "test_cli",
        "test_bot",
        "test_auth",
        "test_integration",
        "run_bot",
        "main_run_bot",
        "main",
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
    Pytest fixture that patches biblebot.bot._submit_coro (if present) with a synchronous runner for coroutine objects.
    
    The replacement runner returns None for non-coroutine inputs. For coroutine inputs it creates a temporary event loop, runs the coroutine to completion (so AsyncMock coroutines are actually awaited), closes the loop, and returns a concurrent.futures.Future that is already resolved with the coroutine's result or completed with the raised exception. Yields control to the test; monkeypatch restores the original attribute on teardown.
    """
    import inspect

    def mock_submit(coro):
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
            outcome_ok, payload = True, result
        except Exception as e:
            outcome_ok, payload = False, e
        finally:
            temp_loop.close()
        future = Future()
        (future.set_result if outcome_ok else future.set_exception)(payload)
        return future

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
    Perform comprehensive asynchronous resource cleanup after a test.
    
    This autouse teardown fixture cancels pending asyncio tasks, attempts to shut down
    and close non-main event loops and their executors, resets the global event loop
    reference, and forces garbage collection while suppressing common warnings about
    unclosed resources or never-awaited coroutines. Broad exception handling is used
    to avoid test interruptions during cleanup.
    """
    yield

    # Force cleanup of all async tasks and event loops
    try:  # noqa: S110 - intentional try-except-pass for test cleanup
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
                # Only drive the loop if it is not currently running
                if not loop.is_running():
                    with contextlib.suppress(Exception):
                        loop.run_until_complete(
                            asyncio.gather(*pending_tasks, return_exceptions=True)
                        )

            # Shutdown any remaining executors
            with contextlib.suppress(Exception):
                if hasattr(loop, "shutdown_default_executor"):
                    # Python 3.9+ public API
                    if not loop.is_running():
                        loop.run_until_complete(loop.shutdown_default_executor())
                elif hasattr(loop, "_default_executor") and loop._default_executor:
                    # Fallback for older Python versions
                    executor = loop._default_executor
                    loop._default_executor = None
                    executor.shutdown(wait=True)

            # Close the original event loop if it's not the main one
            if loop is not asyncio.get_event_loop_policy().get_event_loop():
                with contextlib.suppress(Exception):
                    loop.close()

    except (  # noqa: S110 - intentional try-except-pass for test cleanup
        Exception
    ):  # noqa: BLE001 - test cleanup needs broad exception handling
        # Suppress cleanup errors to avoid affecting test results
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
