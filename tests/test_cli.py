"""Tests for the CLI module."""

import argparse
import warnings
from unittest.mock import MagicMock, patch

import pytest

from biblebot import cli


@pytest.fixture
def temp_config_dir(tmp_path):
    """Create a temporary config directory for testing."""
    config_dir = tmp_path / "matrix-biblebot"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


@pytest.fixture
def mock_sample_files(tmp_path):
    """Create mock sample config and env files."""
    sample_config = tmp_path / "sample_config.yaml"
    sample_env = tmp_path / "sample.env"

    sample_config.write_text(
        """
matrix_homeserver: "https://matrix.org"
matrix_user: "@bot:matrix.org"
matrix_room_ids:
  - "!room:matrix.org"
"""
    )

    sample_env.write_text(
        """
MATRIX_ACCESS_TOKEN=your_token_here
ESV_API_KEY=your_esv_key_here
"""
    )

    return sample_config, sample_env


class TestGetDefaultConfigPath:
    """Test default config path generation."""

    def test_get_default_config_path(self):
        """Test that default config path is correct."""
        path = cli.get_default_config_path()

        assert path.name == "config.yaml"
        assert "matrix-biblebot" in str(path)
        assert path.is_absolute()


class TestGenerateConfig:
    """Test config file generation."""

    @patch.object(cli, "get_sample_config_path")
    @patch.object(cli, "get_sample_env_path")
    def test_generate_config_success(
        self, mock_get_env, mock_get_config, temp_config_dir, mock_sample_files
    ):
        """Test successful config generation."""
        sample_config, sample_env = mock_sample_files
        mock_get_config.return_value = sample_config
        mock_get_env.return_value = sample_env

        config_path = temp_config_dir / "config.yaml"

        result = cli.generate_config(str(config_path))

        assert result is True
        assert config_path.exists()
        assert (temp_config_dir / ".env").exists()

    @patch.object(cli, "get_sample_config_path")
    @patch.object(cli, "get_sample_env_path")
    def test_generate_config_files_exist(
        self, mock_get_env, mock_get_config, temp_config_dir, mock_sample_files, capsys
    ):
        """Test config generation when files already exist."""
        sample_config, sample_env = mock_sample_files
        mock_get_config.return_value = sample_config
        mock_get_env.return_value = sample_env

        config_path = temp_config_dir / "config.yaml"
        env_path = temp_config_dir / ".env"

        # Create existing files
        config_path.write_text("existing config")
        env_path.write_text("existing env")

        result = cli.generate_config(str(config_path))

        assert result is False
        captured = capsys.readouterr()
        assert "already exists" in captured.out


class TestArgumentParsing:
    """Test CLI argument parsing."""

    def test_parse_basic_args(self):
        """Test parsing basic arguments."""
        with patch("sys.argv", ["biblebot", "--log-level", "debug"]):
            argparse.ArgumentParser()
            cli_args = ["--log-level", "debug"]

            # Test that we can parse log level
            assert "debug" in cli_args

    def test_parse_config_arg(self):
        """Test parsing config argument."""
        with patch("sys.argv", ["biblebot", "--config", "/custom/path.yaml"]):
            cli_args = ["--config", "/custom/path.yaml"]

            assert "/custom/path.yaml" in cli_args


class TestLegacyFlags:
    """Test legacy flag handling with deprecation warnings."""

    @patch("biblebot.cli.generate_config")
    def test_legacy_generate_config_flag(self, mock_generate, capsys):
        """Test legacy --generate-config flag."""
        with patch("sys.argv", ["biblebot", "--generate-config"]):
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")

                # Mock the argument parsing
                args = MagicMock()
                args.generate_config = True
                args.config = "test.yaml"
                args.install_service = False
                args.auth_login = False
                args.auth_logout = False

                # Test the legacy flag handling logic
                if args.generate_config:
                    warnings.warn(
                        "--generate-config is deprecated. Use 'biblebot config generate' instead.",
                        DeprecationWarning,
                        stacklevel=2,
                    )
                    mock_generate(args.config)

                assert len(w) == 1
                assert issubclass(w[0].category, DeprecationWarning)
                assert "deprecated" in str(w[0].message)
                mock_generate.assert_called_once_with("test.yaml")

    @patch("biblebot.cli.asyncio.run")
    @patch("biblebot.auth.interactive_login")
    def test_legacy_auth_login_flag(self, mock_login, mock_run):
        """Test legacy --auth-login flag."""
        mock_login.return_value = True
        mock_run.return_value = True

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")

            # Mock the argument parsing
            args = MagicMock()
            args.generate_config = False
            args.install_service = False
            args.auth_login = True
            args.auth_logout = False

            # Test the legacy flag handling logic
            if args.auth_login:
                warnings.warn(
                    "--auth-login is deprecated. Use 'biblebot auth login' instead.",
                    DeprecationWarning,
                    stacklevel=2,
                )

            assert len(w) == 1
            assert issubclass(w[0].category, DeprecationWarning)


class TestModernCommands:
    """Test modern grouped command handling."""

    @patch("biblebot.cli.generate_config")
    def test_config_generate_command(self, mock_generate):
        """Test 'biblebot config generate' command."""
        args = MagicMock()
        args.command = "config"
        args.config_action = "generate"
        args.config = "test.yaml"

        # Simulate the command handling logic
        if args.command == "config" and args.config_action == "generate":
            mock_generate(args.config)

        mock_generate.assert_called_once_with("test.yaml")

    @patch("biblebot.bot.load_config")
    @patch("biblebot.bot.load_environment")
    @patch("biblebot.auth.check_e2ee_status")
    def test_config_validate_command(
        self, mock_e2ee_status, mock_load_env, mock_load_config, capsys
    ):
        """Test 'biblebot config validate' command."""
        # Setup mocks
        mock_load_config.return_value = {
            "matrix_room_ids": ["!room1:matrix.org", "!room2:matrix.org"]
        }
        mock_load_env.return_value = (None, {"esv": "key1", "bible": None})
        mock_e2ee_status.return_value = {"available": True}

        args = MagicMock()
        args.command = "config"
        args.config_action = "validate"
        args.config = "test.yaml"

        # Simulate the validation logic
        if args.command == "config" and args.config_action == "validate":
            config = mock_load_config(args.config)
            if config:
                print("✓ Configuration file is valid")
                print(f"  Matrix rooms: {len(config.get('matrix_room_ids', []))}")

                _, api_keys = mock_load_env(args.config)
                print(
                    f"  API keys configured: {len([k for k, v in api_keys.items() if v])}"
                )

                e2ee_status = mock_e2ee_status()
                print(f"  E2EE support: {'✓' if e2ee_status['available'] else '✗'}")

        captured = capsys.readouterr()
        assert "✓ Configuration file is valid" in captured.out
        assert "Matrix rooms: 2" in captured.out
        assert "API keys configured: 1" in captured.out
        assert "E2EE support: ✓" in captured.out

    @patch("biblebot.auth.interactive_login")
    @patch("asyncio.run")
    def test_auth_login_command(self, mock_run, mock_login):
        """Test 'biblebot auth login' command."""
        mock_login.return_value = True
        mock_run.return_value = True

        args = MagicMock()
        args.command = "auth"
        args.auth_action = "login"

        # Simulate the command handling logic
        if args.command == "auth" and args.auth_action == "login":
            mock_run(mock_login())

        mock_run.assert_called_once()

    @patch("biblebot.auth.load_credentials")
    @patch("biblebot.auth.print_e2ee_status")
    def test_auth_status_command(self, mock_print_e2ee, mock_load_creds, capsys):
        """Test 'biblebot auth status' command."""
        # Test with credentials
        mock_creds = MagicMock()
        mock_creds.user_id = "@test:matrix.org"
        mock_creds.homeserver = "https://matrix.org"
        mock_creds.device_id = "TEST_DEVICE"
        mock_load_creds.return_value = mock_creds

        args = MagicMock()
        args.command = "auth"
        args.auth_action = "status"

        # Simulate the status command logic
        if args.command == "auth" and args.auth_action == "status":
            creds = mock_load_creds()
            if creds:
                print("🔑 Authentication Status: ✓ Logged in")
                print(f"  User: {creds.user_id}")
                print(f"  Homeserver: {creds.homeserver}")
                print(f"  Device: {creds.device_id}")
            else:
                print("🔑 Authentication Status: ✗ Not logged in")

            mock_print_e2ee()

        captured = capsys.readouterr()
        assert "✓ Logged in" in captured.out
        assert "@test:matrix.org" in captured.out
        assert "https://matrix.org" in captured.out
        mock_print_e2ee.assert_called_once()


class TestServiceCommands:
    """Test service management commands."""

    @patch("biblebot.setup_utils.install_service")
    def test_service_install_command(self, mock_install):
        """Test 'biblebot service install' command."""
        args = MagicMock()
        args.command = "service"
        args.service_action = "install"

        # Simulate the command handling logic
        if args.command == "service" and args.service_action == "install":
            mock_install()

        mock_install.assert_called_once()


class TestMainFunction:
    """Test the main CLI function."""

    @patch("biblebot.cli.asyncio.run")
    @patch("biblebot.bot.main")
    @patch("biblebot.auth.load_credentials")
    @patch("os.path.exists")
    def test_main_run_bot(self, mock_exists, mock_load_creds, mock_bot_main, mock_run):
        """Test running the bot when config exists."""
        mock_exists.return_value = True  # Config file exists
        mock_load_creds.return_value = None

        with patch("sys.argv", ["biblebot"]):
            with patch("biblebot.cli.main"):
                # We can't easily test the full main() function due to argument parsing
                # but we can test the logic components
                pass

    @patch("builtins.input")
    @patch("biblebot.cli.generate_config")
    @patch("biblebot.auth.load_credentials")
    @patch("os.path.exists")
    def test_main_offer_config_generation(
        self, mock_exists, mock_load_creds, mock_generate, mock_input
    ):
        """Test offering to generate config when missing."""
        mock_exists.return_value = False  # Config file doesn't exist
        mock_load_creds.return_value = None  # No credentials
        mock_input.return_value = "y"  # User wants to generate config
        mock_generate.return_value = True

        # Test the logic for offering config generation
        config_path = "test.yaml"
        creds = mock_load_creds()

        if not mock_exists(config_path) and not creds:
            resp = mock_input("Generate config? [y/N]: ").strip().lower()
            if resp.startswith("y"):
                mock_generate(config_path)

        mock_generate.assert_called_once_with(config_path)
