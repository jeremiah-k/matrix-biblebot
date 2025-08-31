import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from biblebot.auth import (
    check_e2ee_status,
    get_store_dir,
    load_credentials,
    save_credentials,
)


@pytest.fixture
def mock_credentials():
    """Mock credentials fixture for E2EE testing."""
    from biblebot.auth import Credentials

    return Credentials(
        homeserver="https://matrix.org",
        user_id="@biblebot:matrix.org",
        access_token="test_token",
        device_id="TEST_DEVICE",
    )


@pytest.fixture
def e2ee_config():
    """E2EE configuration fixture."""
    return {
        "matrix": {
            "homeserver": "https://matrix.org",
            "bot_user_id": "@biblebot:matrix.org",
            "e2ee": {
                "enabled": True,
                "store_path": "/test/store",
            },
        },
        "matrix_room_ids": ["!room:matrix.org"],
    }


class TestE2EEStatus:
    """Test E2EE status checking functionality."""

    @patch("biblebot.auth.sys.platform", "linux")
    def test_check_e2ee_status_linux_supported(self):
        """Test E2EE status on supported Linux platform."""
        status = check_e2ee_status()

        assert status["platform_supported"] is True
        assert "linux" in status["platform"].lower()

    @patch("biblebot.auth.sys.platform", "win32")
    def test_check_e2ee_status_windows_unsupported(self):
        """Test E2EE status on unsupported Windows platform."""
        status = check_e2ee_status()

        assert status["platform_supported"] is False
        assert "windows" in status["platform"].lower()

    @patch("biblebot.auth.sys.platform", "linux")
    def test_check_e2ee_status_missing_deps(self):
        """Test E2EE status when dependencies are missing."""
        with patch(
            "builtins.__import__", side_effect=ImportError("No module named 'olm'")
        ):
            status = check_e2ee_status()

            assert status["dependencies_available"] is False
            assert "olm" in status["error_message"]

    @patch("biblebot.auth.sys.platform", "linux")
    def test_check_e2ee_status_deps_available_no_creds(self):
        """Test E2EE status when deps available but no credentials."""
        with patch("builtins.__import__") as mock_import:
            mock_import.return_value = MagicMock()  # Mock olm module

            with patch("biblebot.auth.load_credentials", return_value=None):
                status = check_e2ee_status()

                assert status["dependencies_available"] is True
                assert status["credentials_available"] is False

    @patch("biblebot.auth.sys.platform", "linux")
    def test_check_e2ee_status_fully_available(self, mock_credentials):
        """Test E2EE status when fully available."""
        with patch("builtins.__import__") as mock_import:
            mock_import.return_value = MagicMock()  # Mock olm module

            with patch("biblebot.auth.load_credentials", return_value=mock_credentials):
                status = check_e2ee_status()

                assert status["dependencies_available"] is True
                assert status["credentials_available"] is True
                assert status["overall_status"] == "ready"


class TestE2EEStoreManagement:
    """Test E2EE store directory management."""

    @patch("biblebot.auth.os.makedirs")
    @patch("biblebot.auth.os.path.exists", return_value=False)
    def test_get_store_dir_creates_directory(self, mock_exists, mock_makedirs):
        """Test that E2EE store directory is created when it doesn't exist."""
        store_dir = get_store_dir()

        assert store_dir is not None
        assert "store" in store_dir
        mock_makedirs.assert_called_once()

    @patch("biblebot.auth.os.chmod")
    @patch("biblebot.auth.os.makedirs")
    @patch("biblebot.auth.os.path.exists", return_value=False)
    @patch("biblebot.auth.sys.platform", "linux")
    def test_get_store_dir_sets_permissions(
        self, mock_exists, mock_makedirs, mock_chmod
    ):
        """Test that E2EE store directory permissions are set correctly on Unix."""
        store_dir = get_store_dir()

        assert store_dir is not None
        mock_chmod.assert_called_once()
        # Verify secure permissions (0o700 = owner read/write/execute only)
        call_args = mock_chmod.call_args
        assert call_args[0][1] == 0o700


class TestPrintE2EEStatus:
    """Test E2EE status printing functionality."""

    def test_print_e2ee_status_available(self, capsys):
        """Test printing E2EE status when available."""
        from biblebot.auth import print_e2ee_status

        status = {
            "platform_supported": True,
            "dependencies_available": True,
            "credentials_available": True,
            "overall_status": "ready",
            "platform": "Linux",
        }

        print_e2ee_status(status)

        captured = capsys.readouterr()
        assert "E2EE Status" in captured.out
        assert "ready" in captured.out.lower()

    def test_print_e2ee_status_with_error(self, capsys):
        """Test printing E2EE status with error information."""
        from biblebot.auth import print_e2ee_status

        status = {
            "platform_supported": False,
            "dependencies_available": False,
            "credentials_available": False,
            "overall_status": "unavailable",
            "platform": "Windows",
            "error_message": "E2EE not supported on Windows",
        }

        print_e2ee_status(status)

        captured = capsys.readouterr()
        assert "E2EE Status" in captured.out
        assert "Windows" in captured.out
        assert "not supported" in captured.out


class TestDiscoverHomeserver:
    """Test homeserver discovery functionality."""

    @patch("biblebot.auth.aiohttp.ClientSession")
    async def test_discover_homeserver_success(self, mock_session):
        """Test successful homeserver discovery."""
        from biblebot.auth import discover_homeserver

        # Mock successful discovery response
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={"m.homeserver": {"base_url": "https://matrix.org"}}
        )

        mock_session_instance = MagicMock()
        mock_session_instance.get = AsyncMock(return_value=mock_response)
        mock_session.return_value.__aenter__.return_value = mock_session_instance

        result = await discover_homeserver("matrix.org")

        assert result == "https://matrix.org"
        mock_session_instance.get.assert_called_once()

    @patch("biblebot.auth.aiohttp.ClientSession")
    async def test_discover_homeserver_timeout(self, mock_session):
        """Test homeserver discovery with timeout."""
        import asyncio

        from biblebot.auth import discover_homeserver

        mock_session_instance = MagicMock()
        mock_session_instance.get = AsyncMock(side_effect=asyncio.TimeoutError())
        mock_session.return_value.__aenter__.return_value = mock_session_instance

        result = await discover_homeserver("matrix.org")

        assert result is None

    @patch("biblebot.auth.aiohttp.ClientSession")
    async def test_discover_homeserver_error(self, mock_session):
        """Test homeserver discovery with HTTP error."""
        from biblebot.auth import discover_homeserver

        mock_response = MagicMock()
        mock_response.status = 404

        mock_session_instance = MagicMock()
        mock_session_instance.get = AsyncMock(return_value=mock_response)
        mock_session.return_value.__aenter__.return_value = mock_session_instance

        result = await discover_homeserver("invalid.server")

        assert result is None


class TestInteractiveLogin:
    """Test interactive login functionality."""

    @patch("biblebot.auth.getpass.getpass")
    @patch("biblebot.auth.input")
    @patch("biblebot.auth.AsyncClient")
    async def test_interactive_login_success(
        self, mock_client, mock_input, mock_getpass
    ):
        """Test successful interactive login."""
        from biblebot.auth import interactive_login

        # Mock user inputs
        mock_input.side_effect = [
            "https://matrix.org",  # homeserver
            "@biblebot:matrix.org",  # username
        ]
        mock_getpass.return_value = "password123"

        # Mock client login
        mock_client_instance = MagicMock()
        mock_client_instance.login = AsyncMock(
            return_value=MagicMock(access_token="test_token", device_id="TEST_DEVICE")
        )
        mock_client_instance.close = AsyncMock()
        mock_client.return_value = mock_client_instance

        with patch("biblebot.auth.save_credentials") as mock_save:
            result = await interactive_login()

            assert result is True
            mock_save.assert_called_once()

    @patch("biblebot.auth.load_credentials")
    @patch("biblebot.auth.input")
    async def test_interactive_login_existing_credentials_cancel(
        self, mock_input, mock_load, mock_credentials
    ):
        """Test interactive login when credentials exist and user cancels."""
        from biblebot.auth import interactive_login

        mock_load.return_value = mock_credentials
        mock_input.return_value = "n"  # User chooses not to overwrite

        result = await interactive_login()

        assert result is False

    @patch("biblebot.auth.getpass.getpass")
    @patch("biblebot.auth.input")
    @patch("biblebot.auth.AsyncClient")
    @patch("biblebot.auth.asyncio.wait_for")
    async def test_interactive_login_timeout(
        self, mock_wait_for, mock_client, mock_input, mock_getpass
    ):
        """Test interactive login with timeout."""
        import asyncio

        from biblebot.auth import interactive_login

        mock_input.side_effect = [
            "https://matrix.org",
            "@biblebot:matrix.org",
        ]
        mock_getpass.return_value = "password123"

        # Mock timeout during login
        mock_wait_for.side_effect = asyncio.TimeoutError()

        result = await interactive_login()

        assert result is False


class TestInteractiveLogout:
    """Test interactive logout functionality."""

    @patch("biblebot.auth.getpass.getpass")
    @patch("biblebot.auth.AsyncClient")
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
            with patch("biblebot.auth.cleanup_session_data") as mock_cleanup:
                result = await interactive_logout()

                assert result is True
                mock_cleanup.assert_called_once()

    @patch("biblebot.auth.load_credentials")
    async def test_interactive_logout_no_credentials(self, mock_load):
        """Test interactive logout when no credentials exist."""
        from biblebot.auth import interactive_logout

        mock_load.return_value = None

        result = await interactive_logout()

        assert result is True  # Should succeed (nothing to logout)

    @patch("biblebot.auth.getpass.getpass")
    @patch("biblebot.auth.AsyncClient")
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
            with patch(
                "biblebot.auth.cleanup_session_data", return_value=True
            ) as mock_cleanup:
                result = await interactive_logout()

                # Should still succeed due to local cleanup
                assert result is True
                mock_cleanup.assert_called_once()
