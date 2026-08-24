import gc
import os
import sys
import warnings
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Ensure src/ is importable without installation
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


@pytest.fixture(autouse=True)
def isolate_passage_cache():
    """Prevent process-global passage cache entries from leaking between tests."""
    from biblebot import bot

    bot._passage_cache.clear()
    yield
    bot._passage_cache.clear()


# Mock all E2EE dependencies before any imports can occur
# This prevents ImportError and allows tests to run without real E2EE setup

# Preserve the real nio.responses module so code under test can still do
# ``from nio.responses import ErrorResponse`` after the ``nio`` package is
# replaced by the mock below. A pre-seeded sys.modules entry short-circuits
# the submodule import, which would otherwise fail against a MagicMock parent.
try:
    import nio.responses as _real_nio_responses

    sys.modules.setdefault("nio.responses", _real_nio_responses)
except ImportError:  # pragma: no cover - environment without a real nio
    pass


# Create proper Exception classes for the mocked top-level nio API
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
sys.modules["nio"] = nio_mock
sys.modules["nio.events"] = MagicMock()
sys.modules["nio.events.room_events"] = MagicMock()
sys.modules["nio.events.misc"] = MagicMock()
sys.modules["nio.store"] = MagicMock()
sys.modules["nio.store.database"] = MagicMock()
sys.modules["nio.crypto"] = MagicMock()
nio_cross_signing_mock = MagicMock()
nio_cross_signing_mock.cross_signing_sidecar_path.side_effect = (
    lambda store_path, user_id: Path(store_path) / f"{user_id}_cross_signing.json"
)
sys.modules["nio.crypto.cross_signing"] = nio_cross_signing_mock

# Mock vodozemac (E2EE crypto provider)
vodozemac_mock = MagicMock()
vodozemac_mock.__spec__ = MagicMock()  # Required for importlib.util.find_spec
sys.modules["vodozemac"] = vodozemac_mock

# Mock other E2EE related dependencies
sys.modules["peewee"] = MagicMock()
sys.modules["atomicwrites"] = MagicMock()
sys.modules["cachetools"] = MagicMock()

# Set up nio mock attributes
nio_mock.AsyncClient = MagicMock()
nio_mock.AsyncClientConfig = MagicMock()
nio_mock.SqliteStore = MagicMock()
nio_mock.DiscoveryInfoResponse = MockDiscoveryInfoResponse
nio_mock.DiscoveryInfoError = MockDiscoveryInfoError
nio_mock.LoginError = MockLoginError
nio_mock.RoomResolveAliasError = MockRoomResolveAliasError
nio_mock.LoginResponse = MockLoginResponse
nio_mock.LocalProtocolError = MockLocalProtocolError
nio_mock.RemoteProtocolError = MockRemoteProtocolError
nio_mock.RemoteTransportError = MockRemoteTransportError

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
