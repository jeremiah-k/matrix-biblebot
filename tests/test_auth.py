"""Tests for the auth module."""

import json
import os
from unittest.mock import AsyncMock, MagicMock, patch

import nio.exceptions
import pytest

from biblebot import auth


@pytest.fixture
def temp_config_dir(tmp_path):
    """
    Pytest fixture that creates a temporary configuration directory and patches auth paths to use it.

    Yields:
        pathlib.Path: Path to a temporary config directory (named "matrix-biblebot"). While yielded,
        auth.CONFIG_DIR, auth.CREDENTIALS_FILE, and auth.E2EE_STORE_DIR are patched to point inside
        this directory so tests run in isolation.
    """
    config_dir = tmp_path / "matrix-biblebot"
    config_dir.mkdir(parents=True, exist_ok=True)

    # Patch the CONFIG_DIR to use our temp directory
    with patch.object(auth, "CONFIG_DIR", config_dir):
        with patch.object(auth, "CREDENTIALS_FILE", config_dir / "credentials.json"):
            with patch.object(auth, "E2EE_STORE_DIR", config_dir / "e2ee-store"):
                yield config_dir


class TestCredentials:
    """Test the Credentials dataclass."""

    def test_credentials_to_dict(self):
        """Test converting credentials to dictionary."""
        creds = auth.Credentials(
            homeserver="https://matrix.org",
            user_id="@test:matrix.org",
            access_token="test_token",
            device_id="test_device",
        )

        expected = {
            "homeserver": "https://matrix.org",
            "user_id": "@test:matrix.org",
            "access_token": "test_token",
            "device_id": "test_device",
        }

        assert creds.to_dict() == expected

    def test_credentials_from_dict(self):
        """Test creating credentials from dictionary."""
        data = {
            "homeserver": "https://matrix.org",
            "user_id": "@test:matrix.org",
            "access_token": "test_token",
            "device_id": "test_device",
        }

        creds = auth.Credentials.from_dict(data)

        assert creds.homeserver == "https://matrix.org"
        assert creds.user_id == "@test:matrix.org"
        assert creds.access_token == "test_token"
        assert creds.device_id == "test_device"

    def test_credentials_from_dict_missing_fields(self):
        """Test creating credentials from incomplete dictionary."""
        data = {"homeserver": "https://matrix.org", "user_id": "@test:matrix.org"}

        creds = auth.Credentials.from_dict(data)

        assert creds.homeserver == "https://matrix.org"
        assert creds.user_id == "@test:matrix.org"
        assert creds.access_token == ""
        assert creds.device_id is None


class TestConfigDirectory:
    """Test config directory management."""

    def test_get_config_dir_creates_directory(self, temp_config_dir):
        """Test that get_config_dir creates the directory."""
        # Remove the directory first
        temp_config_dir.rmdir()
        assert not temp_config_dir.exists()

        result = auth.get_config_dir()

        assert result.exists()
        assert result.is_dir()

    def test_credentials_path(self, temp_config_dir):
        """Test credentials path generation."""
        path = auth.credentials_path()

        assert path.name == "credentials.json"
        assert path.parent == temp_config_dir


class TestCredentialsPersistence:
    """Test saving and loading credentials."""

    def test_save_and_load_credentials(self, temp_config_dir):
        """Test saving and loading credentials."""
        creds = auth.Credentials(
            homeserver="https://matrix.org",
            user_id="@test:matrix.org",
            access_token="test_token",
            device_id="test_device",
        )

        # Save credentials
        auth.save_credentials(creds)

        # Load credentials
        loaded_creds = auth.load_credentials()

        assert loaded_creds is not None
        assert loaded_creds.homeserver == creds.homeserver
        assert loaded_creds.user_id == creds.user_id
        assert loaded_creds.access_token == creds.access_token
        assert loaded_creds.device_id == creds.device_id

    def test_load_credentials_no_file(self, temp_config_dir):
        """Test loading credentials when file doesn't exist."""
        result = auth.load_credentials()
        assert result is None

    def test_load_credentials_invalid_json(self, temp_config_dir):
        """Test loading credentials with invalid JSON."""
        creds_file = temp_config_dir / "credentials.json"
        creds_file.write_text("invalid json content")

        result = auth.load_credentials()
        assert result is None

    def test_save_credentials_creates_secure_file(self, temp_config_dir):
        """Test that saved credentials file has secure permissions."""
        creds = auth.Credentials(
            homeserver="https://matrix.org",
            user_id="@test:matrix.org",
            access_token="test_token",
        )

        auth.save_credentials(creds)

        creds_file = temp_config_dir / "credentials.json"
        assert creds_file.exists()

        # Check file permissions (on Unix systems)
        if os.name != "nt":  # Not Windows
            stat_info = creds_file.stat()
            # Should be readable/writable by owner only (0o600)
            assert stat_info.st_mode & 0o777 == 0o600


class TestE2EEStatus:
    """Test E2EE status checking."""

    @patch("platform.system")
    def test_check_e2ee_status_windows(self, mock_system, temp_config_dir):
        """Test E2EE status on Windows (not supported)."""
        mock_system.return_value = "Windows"

        status = auth.check_e2ee_status()

        assert status["available"] is False
        assert status["platform_supported"] is False
        assert "Windows" in status["error"]

    @patch("platform.system")
    @patch("importlib.util.find_spec")
    def test_check_e2ee_status_missing_deps(
        self, mock_find_spec, mock_system, temp_config_dir
    ):
        """Test E2EE status with missing dependencies."""
        mock_system.return_value = "Linux"
        mock_find_spec.return_value = None  # Dependencies not found

        status = auth.check_e2ee_status()

        assert status["available"] is False
        assert status["dependencies_installed"] is False
        assert status["platform_supported"] is True
        assert "dependencies not installed" in status["error"]

    @patch("platform.system")
    @patch("importlib.util.find_spec")
    def test_check_e2ee_status_deps_available_no_creds(
        self, mock_find_spec, mock_system, temp_config_dir
    ):
        """Test E2EE status with dependencies but no credentials."""
        mock_system.return_value = "Linux"
        mock_find_spec.return_value = MagicMock()  # Dependencies found

        status = auth.check_e2ee_status()

        assert status["available"] is True  # Dependencies available
        assert status["ready"] is False  # But not ready (no creds)
        assert status["dependencies_installed"] is True
        assert status["platform_supported"] is True
        assert status["store_exists"] is False

    @patch("platform.system")
    @patch("importlib.util.find_spec")
    def test_check_e2ee_status_fully_available(
        self, mock_find_spec, mock_system, temp_config_dir
    ):
        """Test E2EE status when fully available."""
        mock_system.return_value = "Linux"
        mock_find_spec.return_value = MagicMock()  # Dependencies found

        # Create credentials
        creds = auth.Credentials(
            homeserver="https://matrix.org",
            user_id="@test:matrix.org",
            access_token="test_token",
        )
        auth.save_credentials(creds)

        # Create store directory
        auth.get_store_dir()

        status = auth.check_e2ee_status()

        assert status["available"] is True
        assert status["dependencies_installed"] is True
        assert status["platform_supported"] is True
        assert status["store_exists"] is True


class TestE2EEStoreManagement:
    """Test E2EE store directory management."""

    def test_get_store_dir_creates_directory(self, temp_config_dir):
        """Test that get_store_dir creates the store directory."""
        store_dir = auth.get_store_dir()

        assert store_dir.exists()
        assert store_dir.is_dir()
        assert store_dir.name == "e2ee-store"

    def test_get_store_dir_sets_permissions(self, temp_config_dir):
        """Test that store directory has secure permissions."""
        store_dir = auth.get_store_dir()

        # Check permissions on Unix systems
        if os.name != "nt":  # Not Windows
            stat_info = store_dir.stat()
            # Should be accessible by owner only (0o700)
            assert stat_info.st_mode & 0o777 == 0o700


class TestPrintE2EEStatus:
    """Test E2EE status printing."""

    @patch("builtins.print")
    @patch.object(auth, "check_e2ee_status")
    def test_print_e2ee_status_available(self, mock_check, mock_print, temp_config_dir):
        """Test printing E2EE status when available."""
        mock_check.return_value = {
            "available": True,
            "dependencies_installed": True,
            "store_exists": True,
            "platform_supported": True,
            "ready": True,
            "error": None,
        }

        auth.print_e2ee_status()

        # Check that print was called with expected content
        mock_print.assert_called()
        # Get all print call arguments safely
        print_calls = []
        for call in mock_print.call_args_list:
            if call[0]:  # If there are positional arguments
                print_calls.extend(str(arg) for arg in call[0])
        status_text = " ".join(print_calls)

        # Check for some indication of E2EE status being printed
        assert len(status_text) > 0  # At least something was printed

    @patch("builtins.print")
    @patch.object(auth, "check_e2ee_status")
    def test_print_e2ee_status_with_error(
        self, mock_check, mock_print, temp_config_dir
    ):
        """Test printing E2EE status with error."""
        mock_check.return_value = {
            "available": False,
            "dependencies_installed": False,
            "store_exists": False,
            "platform_supported": True,
            "ready": False,
            "error": "Dependencies not installed",
        }

        auth.print_e2ee_status()

        # Check that error message was printed
        mock_print.assert_called()
        # Get all print call arguments safely
        print_calls = []
        for call in mock_print.call_args_list:
            if call[0]:  # If there are positional arguments
                print_calls.extend(str(arg) for arg in call[0])
        status_text = " ".join(print_calls)

        # Check for some indication of error being printed
        assert len(status_text) > 0  # At least something was printed
        assert "pip install" in status_text


class TestDiscoverHomeserver:
    """Test homeserver discovery functionality."""

    @pytest.mark.asyncio
    async def test_discover_homeserver_success(self):
        """Test successful homeserver discovery."""
        from nio import DiscoveryInfoResponse

        mock_client = AsyncMock()
        mock_response = DiscoveryInfoResponse("https://discovered.matrix.org")
        mock_client.discovery_info.return_value = mock_response

        result = await auth.discover_homeserver(mock_client, "https://matrix.org")

        assert result == "https://discovered.matrix.org"
        mock_client.discovery_info.assert_called_once()

    @pytest.mark.asyncio
    async def test_discover_homeserver_timeout(self):
        """Test homeserver discovery with timeout."""
        import asyncio

        mock_client = AsyncMock()
        mock_client.discovery_info.side_effect = asyncio.TimeoutError()

        result = await auth.discover_homeserver(
            mock_client, "https://matrix.org", timeout=0.1
        )

        assert result == "https://matrix.org"  # Falls back to original

    @pytest.mark.asyncio
    async def test_discover_homeserver_error(self):
        """Test homeserver discovery with error."""
        mock_client = AsyncMock()
        mock_client.discovery_info.side_effect = nio.exceptions.RemoteProtocolError(
            "Discovery failed"
        )

        result = await auth.discover_homeserver(mock_client, "https://matrix.org")

        assert result == "https://matrix.org"  # Falls back to original


class TestInteractiveLogin:
    """Test interactive login functionality."""

    @pytest.mark.asyncio
    @patch("builtins.input")
    @patch("getpass.getpass")
    @patch.object(auth, "load_credentials")
    @patch.object(auth, "save_credentials")
    @patch.object(auth, "discover_homeserver", new_callable=AsyncMock)
    @patch.object(auth, "get_store_dir")
    async def test_interactive_login_success(
        self,
        mock_get_store,
        mock_discover,
        mock_save_creds,
        mock_load_creds,
        mock_getpass,
        mock_input,
        temp_config_dir,
    ):
        """Test successful interactive login."""
        # Setup mocks
        mock_load_creds.return_value = None  # No existing credentials
        mock_input.side_effect = ["https://matrix.org", "@test:matrix.org"]
        mock_getpass.return_value = "password"
        mock_discover.return_value = "https://matrix.org"
        mock_get_store.return_value = temp_config_dir / "store"

        # Mock the AsyncClient and login response
        with patch("biblebot.auth.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client

            # Create a proper nio.LoginResponse instance
            mock_response = nio.LoginResponse(
                user_id="@test:matrix.org",
                device_id="test_device",
                access_token="test_token",
            )
            mock_client.login.return_value = mock_response

            # Mock importlib for E2EE check
            with patch("importlib.util.find_spec") as mock_find_spec:
                mock_find_spec.return_value = None  # No E2EE deps

                result = await auth.interactive_login()

                assert result is True
                mock_save_creds.assert_called_once()
                # Ensure client close was called at least once
                assert mock_client.close.await_count >= 1

    @pytest.mark.asyncio
    @patch("builtins.input")
    @patch.object(auth, "load_credentials")
    async def test_interactive_login_existing_credentials_cancel(
        self, mock_load_creds, mock_input, temp_config_dir
    ):
        """Test interactive login with existing credentials - user cancels."""
        existing_creds = auth.Credentials(
            homeserver="https://matrix.org",
            user_id="@existing:matrix.org",
            access_token="existing_token",
        )
        mock_load_creds.return_value = existing_creds
        mock_input.return_value = "n"  # User chooses not to login again

        result = await auth.interactive_login()

        assert result is True  # Already logged in counts as success

    @pytest.mark.asyncio
    @patch("builtins.input")
    @patch("getpass.getpass")
    @patch.object(auth, "load_credentials")
    async def test_interactive_login_timeout(
        self, mock_load_creds, mock_getpass, mock_input, temp_config_dir
    ):
        """Test interactive login with timeout."""
        mock_load_creds.return_value = None
        mock_input.side_effect = ["https://matrix.org", "@test:matrix.org"]
        mock_getpass.return_value = "password"

        with patch("biblebot.auth.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client
            import asyncio

            mock_client.login.side_effect = asyncio.TimeoutError()

            with patch("importlib.util.find_spec") as mock_find_spec:
                mock_find_spec.return_value = None

                result = await auth.interactive_login()

                assert result is False
                # We now create two clients (temp for discovery + actual), so close is called twice
                assert mock_client.close.call_count == 2


class TestInteractiveLogout:
    """Test interactive logout functionality."""

    @pytest.mark.asyncio
    @patch.object(auth, "load_credentials")
    @patch("biblebot.auth.shutil.rmtree")
    async def test_interactive_logout_success(
        self, mock_rmtree, mock_load_creds, temp_config_dir
    ):
        """Test successful logout."""
        # Create credentials file
        creds = auth.Credentials(
            homeserver="https://matrix.org",
            user_id="@test:matrix.org",
            access_token="test_token",
            device_id="test_device",
        )
        mock_load_creds.return_value = creds

        # Create credentials file to be removed
        creds_file = temp_config_dir / "credentials.json"
        creds_file.write_text(json.dumps(creds.to_dict()))

        # Create store directory
        store_dir = temp_config_dir / "e2ee-store"
        store_dir.mkdir()

        with patch("biblebot.auth.AsyncClient") as mock_client_class:
            mock_client = MagicMock(spec_set=["restore_login", "logout", "close"])
            mock_client.restore_login = MagicMock()  # Sync method
            mock_client.logout = AsyncMock()  # Async method
            mock_client.close = AsyncMock()  # Async method
            mock_client_class.return_value = mock_client

            result = await auth.interactive_logout()

            assert result is True
            assert not creds_file.exists()
            mock_client.logout.assert_called_once()
            mock_client.close.assert_called_once()

    @pytest.mark.asyncio
    @patch.object(auth, "load_credentials")
    async def test_interactive_logout_no_credentials(
        self, mock_load_creds, temp_config_dir
    ):
        """Test logout with no existing credentials."""
        mock_load_creds.return_value = None

        result = await auth.interactive_logout()

        assert result is True  # Should still succeed

    @pytest.mark.asyncio
    @patch.object(auth, "load_credentials")
    async def test_interactive_logout_server_error(
        self, mock_load_creds, temp_config_dir
    ):
        """Test logout with server error."""
        creds = auth.Credentials(
            homeserver="https://matrix.org",
            user_id="@test:matrix.org",
            access_token="test_token",
        )
        mock_load_creds.return_value = creds

        with patch("biblebot.auth.AsyncClient") as mock_client_class:
            mock_client = MagicMock(spec_set=["restore_login", "logout", "close"])
            mock_client.restore_login = MagicMock()  # Sync method
            mock_client.logout = AsyncMock(
                side_effect=Exception("Server error")
            )  # Async method
            mock_client.close = AsyncMock()  # Async method
            mock_client_class.return_value = mock_client

            result = await auth.interactive_logout()

            assert result is True  # Should still succeed despite server error
            mock_client.close.assert_called_once()


class TestE2EEStatusFunctions:
    """Test E2EE status checking functions."""

    @patch("biblebot.auth.E2EE_STORE_DIR")
    @patch("platform.system")
    def test_check_e2ee_status_linux_available(self, mock_system, mock_store_dir):
        """Test E2EE status check on Linux with dependencies."""
        mock_system.return_value = "Linux"
        mock_store_dir.exists.return_value = True

        with patch("importlib.util.find_spec") as mock_find_spec:
            mock_find_spec.return_value = MagicMock()  # Dependencies available

            status = auth.check_e2ee_status()

            assert status["platform_supported"] is True
            assert status["dependencies_installed"] is True
            assert status["store_exists"] is True
            # Note: available may be False due to other conditions in the actual function

    @patch("biblebot.auth.E2EE_STORE_DIR")
    @patch("platform.system")
    def test_check_e2ee_status_windows_unavailable(self, mock_system, mock_store_dir):
        """Test E2EE status check on Windows (unsupported)."""
        mock_system.return_value = "Windows"
        mock_store_dir.exists.return_value = False

        status = auth.check_e2ee_status()

        assert status["platform_supported"] is False
        assert status["available"] is False

    @patch("biblebot.auth.E2EE_STORE_DIR")
    @patch("platform.system")
    def test_check_e2ee_status_missing_dependencies(self, mock_system, mock_store_dir):
        """Test E2EE status check with missing dependencies."""
        mock_system.return_value = "Linux"
        mock_store_dir.exists.return_value = False

        with patch("importlib.util.find_spec") as mock_find_spec:
            mock_find_spec.return_value = None  # Dependencies missing

            status = auth.check_e2ee_status()

            assert status["platform_supported"] is True
            assert status["dependencies_installed"] is False
            assert status["store_exists"] is False
            assert status["available"] is False


class TestDirectoryManagement:
    """Test directory management functions."""

    @patch("biblebot.auth.CONFIG_DIR")
    @patch("os.chmod")
    def test_get_config_dir_success(self, mock_chmod, mock_config_dir):
        """Test successful config directory creation."""
        mock_config_dir.mkdir = MagicMock()

        result = auth.get_config_dir()

        mock_config_dir.mkdir.assert_called_once_with(parents=True, exist_ok=True)
        mock_chmod.assert_called_once_with(mock_config_dir, 0o700)
        assert result == mock_config_dir

    @patch("biblebot.auth.CONFIG_DIR")
    @patch("os.chmod")
    def test_get_config_dir_chmod_failure(self, mock_chmod, mock_config_dir):
        """Test config directory creation with chmod failure."""
        mock_config_dir.mkdir = MagicMock()
        mock_chmod.side_effect = OSError("Permission denied")

        result = auth.get_config_dir()

        mock_config_dir.mkdir.assert_called_once_with(parents=True, exist_ok=True)
        assert result == mock_config_dir

    @patch("biblebot.auth.E2EE_STORE_DIR")
    @patch("os.chmod")
    def test_get_store_dir_success(self, mock_chmod, mock_store_dir):
        """Test successful E2EE store directory creation."""
        mock_store_dir.mkdir = MagicMock()

        result = auth.get_store_dir()

        mock_store_dir.mkdir.assert_called_once_with(parents=True, exist_ok=True)
        mock_chmod.assert_called_once_with(mock_store_dir, 0o700)
        assert result == mock_store_dir

    @patch("biblebot.auth.E2EE_STORE_DIR")
    @patch("os.chmod")
    def test_get_store_dir_chmod_failure(self, mock_chmod, mock_store_dir):
        """Test E2EE store directory creation with chmod failure."""
        mock_store_dir.mkdir = MagicMock()
        mock_chmod.side_effect = OSError("Permission denied")

        result = auth.get_store_dir()

        mock_store_dir.mkdir.assert_called_once_with(parents=True, exist_ok=True)
        assert result == mock_store_dir

    @patch("biblebot.auth.get_config_dir")
    @patch("biblebot.auth.CREDENTIALS_FILE")
    def test_credentials_path(self, mock_creds_file, mock_get_config_dir):
        """Test credentials path function."""
        result = auth.credentials_path()

        mock_get_config_dir.assert_called_once()
        assert result == mock_creds_file


class TestDiscoverHomeserverExceptions:
    """Test homeserver discovery exception handling."""

    @pytest.mark.asyncio
    async def test_discover_homeserver_exception(self):
        """Test homeserver discovery with exception."""
        mock_client = AsyncMock()
        mock_client.discovery_info.side_effect = nio.exceptions.RemoteTransportError(
            "Network error"
        )

        result = await auth.discover_homeserver(mock_client, "https://matrix.org")

        assert result == "https://matrix.org"  # Falls back to provided
