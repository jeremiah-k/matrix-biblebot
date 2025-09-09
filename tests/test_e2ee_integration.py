from unittest.mock import AsyncMock, MagicMock, patch

import pytest

try:
    from nio import LoginResponse as NioLoginResponse  # type: ignore[attr-defined]
except (ImportError, AttributeError):
    from nio.responses import LoginResponse as NioLoginResponse  # fallback

from biblebot.auth import (
    check_e2ee_status,
    get_store_dir,
)
from tests.test_constants import TEST_HOMESERVER, TEST_USER_ID


@pytest.fixture
def mock_credentials():
    """
    Pytest fixture that returns a Credentials object populated with deterministic test values for E2EE tests.

    Returns:
        biblebot.auth.Credentials: Credentials with TEST_HOMESERVER, TEST_USER_ID, access_token "test_token", and device_id "TEST_DEVICE".
    """
    from biblebot.auth import Credentials

    return Credentials(
        homeserver=TEST_HOMESERVER,
        user_id=TEST_USER_ID,
        access_token="test_token",  # noqa: S106 - test fixture token
        device_id="TEST_DEVICE",
    )


class TestE2EEStatus:
    """Test E2EE status checking functionality."""

    @patch("platform.system", return_value="Linux")
    def test_check_e2ee_status_linux_supported(self, _mock_system):
        """Test E2EE status on supported Linux platform."""
        status = check_e2ee_status()

        assert status["platform_supported"] is True

    @patch("platform.system", return_value="Windows")
    def test_check_e2ee_status_windows_unsupported(self, _mock_system):
        """Test E2EE status on unsupported Windows platform."""
        status = check_e2ee_status()

        assert status["platform_supported"] is False
        assert "Windows" in status["error"]

    @patch("platform.system", return_value="Linux")
    def test_check_e2ee_status_missing_deps(self, _mock_system):
        """Test E2EE status when dependencies are missing."""
        with patch("importlib.util.find_spec", return_value=None):
            status = check_e2ee_status()

            assert status["dependencies_installed"] is False
            assert "E2EE dependencies not installed" in status["error"]

    @patch("platform.system", return_value="Linux")
    def test_check_e2ee_status_deps_available_no_creds(self, _mock_system):
        """Test E2EE status when deps available but no credentials."""
        with patch("importlib.util.find_spec") as mock_find_spec:
            mock_find_spec.return_value = MagicMock()  # Mock olm module found

            with patch("biblebot.auth.load_credentials", return_value=None):
                status = check_e2ee_status()

                assert status["dependencies_installed"] is True
                assert status["available"] is True  # Dependencies available
                assert status["ready"] is False  # But not ready (no creds)

    @patch("platform.system", return_value="Linux")
    def test_check_e2ee_status_fully_available(self, _mock_system, mock_credentials):
        """Test E2EE status when fully available."""
        with patch("importlib.util.find_spec") as mock_find_spec:
            mock_find_spec.return_value = MagicMock()  # Mock olm module found

            with patch("biblebot.auth.load_credentials", return_value=mock_credentials):
                with patch("biblebot.auth.E2EE_STORE_DIR") as mock_store:
                    mock_store.exists.return_value = True
                    status = check_e2ee_status()

                    assert status["dependencies_installed"] is True
                    assert status["store_exists"] is True
                    assert status["available"] is True


class TestE2EEStoreManagement:
    """Test E2EE store directory management."""

    @patch("pathlib.Path.mkdir")
    def test_get_store_dir_creates_directory(self, mock_mkdir):
        """Test that E2EE store directory is created when it doesn't exist."""
        store_dir = get_store_dir()

        assert store_dir is not None
        assert "store" in str(store_dir)  # Convert PosixPath to string
        mock_mkdir.assert_called_with(parents=True, exist_ok=True)

    @patch("biblebot.auth.os.chmod")
    @patch("biblebot.auth.E2EE_STORE_DIR")
    def test_get_store_dir_sets_permissions(self, mock_store_dir, mock_chmod):
        """Test that E2EE store directory permissions are set correctly on Unix."""
        mock_store_dir.mkdir = MagicMock()
        store_dir = get_store_dir()

        assert store_dir is not None
        mock_chmod.assert_called_once_with(mock_store_dir, 0o700)


class TestPrintE2EEStatus:
    """Test E2EE status printing functionality."""

    def test_print_e2ee_status_available(self, capsys):
        """Test printing E2EE status when available."""
        from biblebot.auth import print_e2ee_status

        # Mock check_e2ee_status to return available status
        with patch("biblebot.auth.check_e2ee_status") as mock_check:
            mock_check.return_value = {
                "platform_supported": True,
                "dependencies_installed": True,
                "store_exists": True,
                "available": True,
                "ready": True,
                "error": None,
            }

            print_e2ee_status()  # No parameters needed

            captured = capsys.readouterr()
            assert "E2EE" in captured.out
            assert "Available: ✓" in captured.out
            assert "Ready: ✓" in captured.out

    def test_print_e2ee_status_with_error(self, capsys):
        """Test printing E2EE status with error information."""
        from biblebot.auth import print_e2ee_status

        # Mock check_e2ee_status to return error status
        with patch("biblebot.auth.check_e2ee_status") as mock_check:
            mock_check.return_value = {
                "platform_supported": False,
                "dependencies_installed": False,
                "store_exists": False,
                "available": False,
                "ready": False,
                "error": "E2EE not supported on Windows",
            }

            print_e2ee_status()  # No parameters needed

            captured = capsys.readouterr()
            assert "E2EE" in captured.out
            assert "Available: ✗" in captured.out
            assert "Ready: ✗" in captured.out
            assert "Windows" in captured.out


class TestDiscoverHomeserver:
    """Test homeserver discovery functionality."""

    @pytest.mark.asyncio
    async def test_discover_homeserver_success(self):
        """Test successful homeserver discovery."""

        from biblebot.auth import discover_homeserver

        # Mock AsyncClient and discovery response
        mock_client = MagicMock()
        mock_discovery_response = MagicMock()
        mock_discovery_response.homeserver_url = TEST_HOMESERVER
        mock_client.discovery_info = AsyncMock(return_value=mock_discovery_response)

        result = await discover_homeserver(mock_client, TEST_HOMESERVER)

        assert result == TEST_HOMESERVER
        mock_client.discovery_info.assert_called_once()

    @pytest.mark.asyncio
    async def test_discover_homeserver_timeout(self):
        """Test homeserver discovery with timeout."""
        import asyncio

        from biblebot.auth import discover_homeserver

        # Mock AsyncClient with timeout
        mock_client = MagicMock()
        mock_client.discovery_info = AsyncMock(side_effect=asyncio.TimeoutError())

        result = await discover_homeserver(mock_client, "matrix.org")

        # Should return the original homeserver on timeout
        assert result == "matrix.org"

    @pytest.mark.asyncio
    async def test_discover_homeserver_error(self):
        """Test homeserver discovery with error."""
        from nio import DiscoveryInfoError

        from biblebot.auth import discover_homeserver

        # Mock AsyncClient with discovery error
        mock_client = MagicMock()

        async def _discovery_error(*_args, **_kwargs):
            """
            Async helper that simulates a homeserver discovery failure by always raising DiscoveryInfoError.

            Used in tests to mock AsyncClient.discovery_info behavior when discovery should fail.

            Raises:
                DiscoveryInfoError: Always raised with message "Error".
            """
            raise DiscoveryInfoError("Error")

        mock_client.discovery_info = _discovery_error

        result = await discover_homeserver(mock_client, "invalid.server")

        # Should return the original homeserver on error
        assert result == "invalid.server"


class TestInteractiveLogin:
    """Test interactive login functionality."""

    @patch("biblebot.auth.getpass.getpass")
    @patch("biblebot.auth.input")
    @patch("biblebot.auth.AsyncClient")
    @pytest.mark.asyncio
    async def test_interactive_login_success(
        self, mock_client, mock_input, mock_getpass
    ):
        """Test successful interactive login."""
        from biblebot.auth import interactive_login

        # Mock user inputs
        mock_input.side_effect = [
            TEST_HOMESERVER,  # homeserver
            TEST_USER_ID,  # username
        ]
        mock_getpass.return_value = "password123"

        # Mock client login
        mock_client_instance = MagicMock()
        # Create a proper nio.LoginResponse instance
        mock_response = NioLoginResponse(
            user_id="@biblebot:matrix.org",
            device_id="TEST_DEVICE",
            access_token="test_token",  # noqa: S106 - test value
        )
        mock_client_instance.login = AsyncMock(return_value=mock_response)
        mock_client_instance.close = AsyncMock()
        mock_client.return_value = mock_client_instance

        # Mock no existing credentials to avoid the early return
        with patch("biblebot.auth.load_credentials", return_value=None):
            with patch("biblebot.auth.save_credentials") as mock_save:
                with patch(
                    "biblebot.auth.discover_homeserver",
                    return_value=TEST_HOMESERVER,
                ):
                    result = await interactive_login()

                    assert result is True
                    mock_save.assert_called_once()

    @patch("biblebot.auth.load_credentials")
    @patch("biblebot.auth.input")
    @pytest.mark.asyncio
    async def test_interactive_login_existing_credentials_cancel(
        self, mock_input, mock_load, mock_credentials
    ):
        """Test interactive login when credentials exist and user cancels."""
        from biblebot.auth import interactive_login

        mock_load.return_value = mock_credentials
        mock_input.return_value = "n"  # User chooses not to overwrite

        result = await interactive_login()

        # According to the implementation, this returns True (user is already logged in)
        assert result is True

    @patch("biblebot.auth.getpass.getpass")
    @patch("biblebot.auth.input")
    @patch("biblebot.auth.AsyncClient")
    @patch("biblebot.auth.asyncio.wait_for")
    @pytest.mark.asyncio
    async def test_interactive_login_timeout(
        self, mock_wait_for, mock_client, mock_input, mock_getpass
    ):
        """Test interactive login with timeout."""
        import asyncio

        from biblebot.auth import interactive_login

        mock_input.side_effect = [
            TEST_HOMESERVER,
            TEST_USER_ID,
        ]
        mock_getpass.return_value = "password123"

        # Mock client instance with proper async close
        mock_client_instance = MagicMock()
        mock_client_instance.close = AsyncMock()
        mock_client.return_value = mock_client_instance

        # Mock timeout during login - but our implementation returns True for existing creds
        mock_wait_for.side_effect = asyncio.TimeoutError()

        # Mock no existing credentials
        with patch("biblebot.auth.load_credentials", return_value=None):
            result = await interactive_login()

            assert result is False


class TestInteractiveLogout:
    """Test interactive logout functionality."""

    @patch("biblebot.auth.getpass.getpass")
    @patch("biblebot.auth.AsyncClient")
    @pytest.mark.asyncio
    async def test_interactive_logout_success(
        self, mock_client, mock_getpass, mock_credentials
    ):
        """Test successful interactive logout."""
        from biblebot.auth import interactive_logout

        mock_getpass.return_value = "password123"

        # Mock client logout
        mock_client_instance = MagicMock()
        mock_client_instance.login = AsyncMock(return_value=MagicMock())
        mock_client_instance.logout = AsyncMock(return_value=MagicMock())
        mock_client_instance.close = AsyncMock()
        mock_client.return_value = mock_client_instance

        with patch("biblebot.auth.load_credentials", return_value=mock_credentials):
            result = await interactive_logout()

            assert result is True
            # Verify logout was attempted
            mock_client_instance.logout.assert_called_once()

    @patch("biblebot.auth.load_credentials")
    @pytest.mark.asyncio
    async def test_interactive_logout_no_credentials(self, mock_load):
        """Test interactive logout when no credentials exist."""
        from biblebot.auth import interactive_logout

        mock_load.return_value = None

        result = await interactive_logout()

        assert result is True  # Should succeed (nothing to logout)

    @patch("biblebot.auth.getpass.getpass")
    @patch("biblebot.auth.AsyncClient")
    @pytest.mark.asyncio
    async def test_interactive_logout_server_error(
        self, mock_client, mock_getpass, mock_credentials
    ):
        """Test interactive logout with server error."""
        from biblebot.auth import interactive_logout

        mock_getpass.return_value = "password123"

        # Mock client with logout error
        mock_client_instance = MagicMock()
        mock_client_instance.login = AsyncMock(return_value=MagicMock())
        mock_client_instance.logout = AsyncMock(side_effect=Exception("Server error"))
        mock_client_instance.close = AsyncMock()
        mock_client.return_value = mock_client_instance

        with patch("biblebot.auth.load_credentials", return_value=mock_credentials):
            result = await interactive_logout()

            # Should still succeed due to local cleanup
            assert result is True
            # Verify logout was attempted despite server error
            mock_client_instance.logout.assert_called_once()
