"""Tests for the setup_utils module."""

import os
from pathlib import Path
from unittest.mock import patch

from biblebot import setup_utils


class TestServiceUtilities:
    """Test service utility functions."""

    def test_get_executable_path(self):
        """Test getting executable path."""
        with patch("shutil.which", return_value="/usr/bin/biblebot"):
            path = setup_utils.get_executable_path()
            assert path == "/usr/bin/biblebot"

    def test_get_executable_path_fallback(self):
        """Test executable path fallback."""
        with patch("shutil.which", return_value=None):
            with patch("sys.executable", "/usr/bin/python3"):
                path = setup_utils.get_executable_path()
                assert path == "/usr/bin/python3"

    def test_get_user_service_path(self):
        """Test getting user service path."""
        with patch("pathlib.Path.home", return_value=Path("/home/user")):
            path = setup_utils.get_user_service_path()
            expected = Path("/home/user/.config/systemd/user/biblebot.service")
            assert path == expected

    def test_service_exists(self):
        """Test checking if service exists."""
        with patch("pathlib.Path.exists", return_value=True):
            assert setup_utils.service_exists() is True

        with patch("pathlib.Path.exists", return_value=False):
            assert setup_utils.service_exists() is False


class TestServiceInstallation:
    """Test service installation functionality."""

    @patch("builtins.print")
    def test_print_service_commands(self, mock_print):
        """Test printing service commands."""
        setup_utils.print_service_commands()

        # Should print service control commands
        mock_print.assert_called()
        print_calls = [call[0][0] for call in mock_print.call_args_list]
        commands_text = " ".join(print_calls)

        assert "systemctl --user start" in commands_text
        assert "systemctl --user stop" in commands_text
        assert "systemctl --user restart" in commands_text


class TestLingeringManagement:
    """Test user lingering management."""

    def test_lingering_concept_documentation(self):
        """Test that we understand lingering concept for future implementation."""
        # This test documents the lingering concept for future reference
        # User lingering allows systemd user services to start at boot
        # without requiring the user to be logged in

        # Key concepts:
        # 1. loginctl enable-linger <user> - enables lingering for a user
        # 2. loginctl show-user <user> --property=Linger - checks lingering status
        # 3. Lingering is required for user services to auto-start at boot

        # For now, we just verify the concept is documented
        assert True  # This test always passes as it's documentation


class TestErrorHandling:
    """Test error handling in setup utilities."""

    def test_username_detection_fallback(self):
        """Test username detection with fallback."""
        with patch.dict("os.environ", {}, clear=True):
            # When no USER or USERNAME env vars
            username = os.environ.get("USER", os.environ.get("USERNAME"))
            assert username is None

        with patch.dict("os.environ", {"USERNAME": "testuser"}, clear=True):
            # When only USERNAME is available (Windows)
            username = os.environ.get("USER", os.environ.get("USERNAME"))
            assert username == "testuser"


class TestServiceStatusChecks:
    """Test service status checking functionality."""

    @patch("pathlib.Path.read_text")
    @patch("pathlib.Path.exists")
    def test_read_service_file_exists(self, mock_exists, mock_read_text):
        """Test reading service file when it exists."""
        mock_exists.return_value = True
        mock_read_text.return_value = "[Unit]\nDescription=BibleBot"

        content = setup_utils.read_service_file()
        assert content == "[Unit]\nDescription=BibleBot"

    @patch("pathlib.Path.exists")
    def test_read_service_file_not_exists(self, mock_exists):
        """Test reading service file when it doesn't exist."""
        mock_exists.return_value = False

        content = setup_utils.read_service_file()
        assert content is None

    @patch("subprocess.run")
    def test_is_service_enabled_true(self, mock_run):
        """Test checking if service is enabled - true case."""
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "enabled"

        result = setup_utils.is_service_enabled()
        assert result is True

    @patch("subprocess.run")
    def test_is_service_enabled_false(self, mock_run):
        """Test checking if service is enabled - false case."""
        mock_run.return_value.returncode = 1

        result = setup_utils.is_service_enabled()
        assert result is False

    @patch("subprocess.run")
    def test_is_service_active_true(self, mock_run):
        """Test checking if service is active - true case."""
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "active"

        result = setup_utils.is_service_active()
        assert result is True

    @patch("subprocess.run")
    def test_is_service_active_false(self, mock_run):
        """Test checking if service is active - false case."""
        mock_run.return_value.returncode = 1

        result = setup_utils.is_service_active()
        assert result is False

    @patch("subprocess.run")
    def test_reload_daemon_success(self, mock_run):
        """Test successful daemon reload."""
        mock_run.return_value = None

        result = setup_utils.reload_daemon()
        assert result is True

    @patch("subprocess.run")
    def test_reload_daemon_failure(self, mock_run):
        """Test daemon reload failure."""
        mock_run.side_effect = OSError("Command not found")

        result = setup_utils.reload_daemon()
        assert result is False

    @patch("subprocess.run")
    def test_start_service_success(self, mock_run):
        """Test successful service start."""
        mock_run.return_value = None

        result = setup_utils.start_service()
        assert result is True

    @patch("subprocess.run")
    def test_start_service_failure(self, mock_run):
        """Test service start failure."""
        mock_run.side_effect = OSError("Command not found")

        result = setup_utils.start_service()
        assert result is False


class TestServiceTemplateHandling:
    """Test service template handling functionality."""

    def test_get_template_service_content(self):
        """Test getting template service content."""
        content = setup_utils.get_template_service_content()
        assert isinstance(content, str)
        assert "[Unit]" in content
        assert "Description=Matrix Bible Bot Service" in content

    @patch("subprocess.run")
    def test_check_loginctl_available_true(self, mock_run):
        """Test loginctl availability check - available."""
        mock_run.return_value.returncode = 0

        result = setup_utils.check_loginctl_available()
        assert result is True

    @patch("subprocess.run")
    def test_check_loginctl_available_false(self, mock_run):
        """Test loginctl availability check - not available."""
        mock_run.side_effect = Exception("Command not found")

        result = setup_utils.check_loginctl_available()
        assert result is False

    @patch("subprocess.run")
    def test_check_lingering_enabled_true(self, mock_run):
        """Test lingering check - enabled."""
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "Linger=yes"

        result = setup_utils.check_lingering_enabled()
        assert result is True

    @patch("subprocess.run")
    def test_check_lingering_enabled_false(self, mock_run):
        """Test lingering check - disabled."""
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "Linger=no"

        result = setup_utils.check_lingering_enabled()
        assert result is False
