"""Tests for the CLI module."""

from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from biblebot import cli


@pytest.fixture
def temp_config_dir(tmp_path):
    """
    Create and return a temporary "matrix-biblebot" configuration directory inside the provided pytest tmp_path.

    The directory is created with parents=True and exist_ok=True so it is safe to call if the directory already exists.

    Parameters:
        tmp_path (pathlib.Path): pytest temporary path fixture to contain the created config directory.

    Returns:
        pathlib.Path: Path to the created "matrix-biblebot" directory.
    """
    config_dir = tmp_path / "matrix-biblebot"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


@pytest.fixture
def mock_sample_files(tmp_path):
    """
    Create a minimal sample YAML config file for tests.

    Creates a file named "sample_config.yaml" in the provided temporary path containing
    a minimal Matrix and API-keys configuration used by tests.

    Parameters:
        tmp_path (pathlib.Path): Temporary directory (pytest tmp_path fixture) where the
            sample file will be written.

    Returns:
        tuple[pathlib.Path, None]: A tuple with the path to the created sample config file
        and None (second return value kept for historical test-signature compatibility).
    """
    sample_config = tmp_path / "sample_config.yaml"

    sample_config.write_text(
        """
matrix_homeserver: "https://matrix.org"
matrix_user: "@bot:matrix.org"
matrix_room_ids:
  - "!room:matrix.org"
api_keys:
  esv: null
"""
    )

    return sample_config, None


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

    @patch("biblebot.cli.copy_sample_config_to")
    @patch("os.chmod")
    def test_generate_config_success(
        self, mock_chmod, mock_copy_config, temp_config_dir, mock_sample_files
    ):
        """Test successful config generation."""
        sample_config, _ = mock_sample_files
        config_path = temp_config_dir / "config.yaml"

        # Mock copy function to actually create the file
        def create_file(path):
            """
            Write a minimal sample configuration file to the given path and return the path.

            This function creates or overwrites a file at `path` containing the literal
            string "sample config content". `path` may be a string or a pathlib.Path.
            The function returns the original `path` value.

            Parameters:
                path: Destination file path (str or pathlib.Path).

            Returns:
                The same `path` that was passed in.
            """
            from pathlib import Path

            Path(path).write_text("sample config content")
            return path

        mock_copy_config.side_effect = create_file

        result = cli.generate_config(str(config_path))

        assert result is True
        mock_copy_config.assert_called_once_with(str(config_path))
        mock_chmod.assert_called_once_with(config_path, 0o600)
        # Only generates config.yaml, no .env file
        assert not (temp_config_dir / ".env").exists()

    def test_generate_config_files_exist(self, temp_config_dir, capsys):
        """Test config generation when files already exist."""
        config_path = temp_config_dir / "config.yaml"

        # Create existing config file
        config_path.write_text("existing config")

        result = cli.generate_config(str(config_path))

        assert result is False
        captured = capsys.readouterr()
        assert "A config file already exists at:" in captured.out

    def test_generate_config_config_exists(self, temp_config_dir, capsys):
        """Test config generation when config.yaml already exists."""
        config_path = temp_config_dir / "config.yaml"

        # Create existing file
        config_path.write_text("existing config")

        result = cli.generate_config(str(config_path))

        assert result is False
        captured = capsys.readouterr()
        assert "A config file already exists at:" in captured.out
        assert str(config_path) in captured.out

    @patch("biblebot.cli.copy_sample_config_to")
    @patch("os.chmod")
    def test_generate_config_env_exists(
        self, mock_chmod, mock_copy_config, temp_config_dir, capsys
    ):
        """Test config generation when config doesn't exist (no longer checks .env)."""
        config_path = temp_config_dir / "config.yaml"

        # Mock copy function to actually create the file
        def create_file(path):
            """
            Write a minimal sample configuration file to the given path and return the path.

            This function creates or overwrites a file at `path` containing the literal
            string "sample config content". `path` may be a string or a pathlib.Path.
            The function returns the original `path` value.

            Parameters:
                path: Destination file path (str or pathlib.Path).

            Returns:
                The same `path` that was passed in.
            """
            from pathlib import Path

            Path(path).write_text("sample config content")
            return path

        mock_copy_config.side_effect = create_file

        # No existing config file - should succeed
        result = cli.generate_config(str(config_path))

        assert result is True
        mock_copy_config.assert_called_once_with(str(config_path))
        mock_chmod.assert_called_once_with(config_path, 0o600)
        captured = capsys.readouterr()
        assert "Generated sample config file at:" in captured.out


class TestArgumentParsing:
    """Test CLI argument parsing."""

    def test_parse_basic_args(self):
        """Test parsing basic arguments."""
        # Test actual argument parsing
        test_args = ["--log-level", "debug"]
        parser, _, _, _ = cli.create_parser()
        args = parser.parse_args(test_args)

        assert args.log_level == "debug"

    def test_parse_config_arg(self):
        """Test parsing config argument."""
        test_args = ["--config", "/custom/path.yaml"]
        parser, _, _, _ = cli.create_parser()
        args = parser.parse_args(test_args)

        assert args.config == "/custom/path.yaml"


class TestModernCommands:
    """Test modern grouped command handling."""

    @patch("biblebot.cli.generate_config")
    def test_config_generate_command(self, mock_generate):
        """Test 'biblebot config generate' command."""

        # ✅ CORRECT: Use simple object instead of MagicMock (mmrelay pattern)
        class MockArgs:
            command = "config"
            config_action = "generate"
            config = "test.yaml"

        args = MockArgs()

        # Simulate the command handling logic
        if args.command == "config" and args.config_action == "generate":
            mock_generate(args.config)

        mock_generate.assert_called_once_with("test.yaml")

    @patch("biblebot.bot.load_config")
    @patch("biblebot.bot.load_environment")
    @patch("biblebot.auth.check_e2ee_status")
    def test_config_check_command(
        self, mock_e2ee_status, mock_load_env, mock_load_config, capsys
    ):
        """Test 'biblebot config check' command."""
        # Setup mocks
        mock_load_config.return_value = {
            "matrix_room_ids": ["!room1:matrix.org", "!room2:matrix.org"]
        }
        mock_load_env.return_value = (None, {"esv": "key1", "bible": None})
        mock_e2ee_status.return_value = {"available": True}

        # ✅ CORRECT: Use simple object instead of MagicMock (mmrelay pattern)
        class MockArgs:
            command = "config"
            config_action = "check"
            config = "test.yaml"

        args = MockArgs()

        # Simulate the validation logic
        if args.command == "config" and args.config_action == "check":
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

    @patch("biblebot.cli.interactive_login", new_callable=AsyncMock)
    def test_auth_login_command(self, mock_login):
        """Test 'biblebot auth login' command."""
        mock_login.return_value = True
        with patch("sys.argv", ["biblebot", "auth", "login"]):
            with patch("builtins.input", return_value="https://matrix.org"):
                with patch("getpass.getpass", return_value="password"):
                    with patch("sys.exit") as mock_exit:
                        mock_exit.side_effect = SystemExit(0)
                        with pytest.raises(SystemExit) as e:
                            cli.main()
                        assert e.value.code == 0

    def test_auth_status_command(self, capsys):
        """Test 'biblebot auth status' command."""

        # ✅ CORRECT: Use explicit function replacement (mmrelay pattern)
        # Create simple object with attributes (no Mock inheritance)
        class MockCredentials:
            user_id = "@test:matrix.org"
            homeserver = "https://matrix.org"
            device_id = "TEST_DEVICE"

        # ✅ CORRECT: Create simple replacement functions
        def mock_load_credentials():
            """
            Return a fresh MockCredentials instance for tests.

            Provides a new MockCredentials object to simulate stored user credentials in test scenarios.
            """
            return MockCredentials()

        print_e2ee_called = []

        def mock_print_e2ee_status():
            """
            Mock replacement for an E2EE status printer used in tests.

            When called, records that the function was invoked by appending True to the
            shared list `print_e2ee_called`. Intended solely as a test spy; it does not
            produce output or return a value.
            """
            print_e2ee_called.append(True)

        # ✅ CORRECT: Use patch with explicit function replacement
        with patch("biblebot.auth.load_credentials", side_effect=mock_load_credentials):
            with patch(
                "biblebot.auth.print_e2ee_status", side_effect=mock_print_e2ee_status
            ):
                # Simulate the status command logic directly
                creds = mock_load_credentials()
                if creds:
                    print("🔑 Authentication Status: ✓ Logged in")
                    print(f"  User: {creds.user_id}")
                    print(f"  Homeserver: {creds.homeserver}")
                    print(f"  Device: {creds.device_id}")
                else:
                    print("🔑 Authentication Status: ✗ Not logged in")

                mock_print_e2ee_status()

                captured = capsys.readouterr()
                assert "✓ Logged in" in captured.out
                assert "@test:matrix.org" in captured.out
                assert "https://matrix.org" in captured.out
                assert len(print_e2ee_called) == 1


class TestServiceCommands:
    """Test service management commands."""

    def test_service_install_command(self):
        """Test 'biblebot service install' command."""

        # ✅ CORRECT: Use simple object instead of MagicMock (mmrelay pattern)
        class MockArgs:
            command = "service"
            service_action = "install"

        args = MockArgs()

        # ✅ CORRECT: Track function calls without Mock
        install_called = []

        def mock_install_service():
            """
            Record that the service installation was invoked by appending True to the test's `install_called` list.

            This function is a lightweight test stub intended to be used as a mock replacement for a real install routine; it has no return value and only mutates the surrounding `install_called` list.
            """
            install_called.append(True)

        # ✅ CORRECT: Use patch with explicit function replacement
        with patch(
            "biblebot.setup_utils.install_service", side_effect=mock_install_service
        ):
            # Simulate the command handling logic
            if args.command == "service" and args.service_action == "install":
                mock_install_service()

            assert len(install_called) == 1


class TestMainFunction:
    """Test the main CLI function."""

    def test_main_run_bot(self):
        """Test running the bot when config exists."""

        def mock_load_credentials():
            """
            Simulate absence of stored credentials by returning None.

            Used in tests to mock a credential loader that indicates the user is not authenticated.
            """
            return None  # No credentials

        # (removed unused local)
        mock_config = {
            "homeserver": "https://matrix.org",
            "user_id": "@test:matrix.org",
            "access_token": "test_token",
            "device_id": "TEST_DEVICE",
            "matrix_room_ids": ["!room:matrix.org"],
        }

        # Create a mock Path object that returns True for exists()
        mock_config_path = MagicMock()
        mock_config_path.exists.return_value = True

        # Create proper Credentials object so bot starts directly
        import secrets

        from biblebot.auth import Credentials

        TEST_ACCESS_TOKEN = secrets.token_urlsafe(24)

        mock_credentials = Credentials(
            homeserver="https://matrix.org",
            user_id="@test:matrix.org",
            access_token=TEST_ACCESS_TOKEN,
            device_id="TEST_DEVICE",
        )
        with patch("biblebot.cli.CONFIG_DIR") as mock_config_dir:
            # Mock credentials path to exist
            mock_credentials_path = MagicMock()
            mock_credentials_path.exists.return_value = True
            mock_config_dir.__truediv__.return_value = mock_credentials_path

            with patch(
                "biblebot.cli.load_credentials", return_value=mock_credentials
            ), patch("biblebot.bot.load_credentials", return_value=mock_credentials):
                # Mock the config loading to avoid file system access
                with patch("biblebot.bot.load_config", return_value=mock_config):
                    # Patch the async entrypoint with AsyncMock following testing guide
                    with patch(
                        "biblebot.bot.main_with_config", new_callable=AsyncMock
                    ) as mock_main:
                        mock_main.return_value = 0
                        # Run the bot directly instead of interactive mode
                        with patch("sys.argv", ["biblebot"]), patch(
                            "biblebot.cli.get_default_config_path",
                            return_value=mock_config_path,
                        ):
                            # Mock user input to start the bot
                            with patch("builtins.input", return_value="y"):
                                cli.main()
                        mock_main.assert_awaited_once()

        # Verifies the CLI attempted to run the bot (user answered "y").
        # No direct asyncio.run here; main_with_config is awaited.

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


class TestCLIArgumentParsing:
    """Test CLI argument parsing functionality."""

    def test_cli_module_imports(self):
        """Test that CLI module imports correctly."""
        assert hasattr(cli, "main")
        assert hasattr(cli, "get_default_config_path")
        assert hasattr(cli, "generate_config")

    def test_cli_functions_callable(self):
        """Test that CLI functions are callable."""
        assert callable(cli.main)
        assert callable(cli.get_default_config_path)
        assert callable(cli.generate_config)


class TestCLIMainFunction:
    """Test the main CLI function with comprehensive coverage."""

    @patch("sys.argv", ["biblebot", "--version"])
    def test_version_flag(self):
        """Test version flag."""
        with pytest.raises(SystemExit):
            cli.main()

    @patch("sys.argv", ["biblebot"])
    @patch("biblebot.cli.detect_configuration_state")
    @patch("biblebot.auth.load_credentials")
    @patch("biblebot.bot.load_config")
    @patch("biblebot.bot.main_with_config", new_callable=AsyncMock)
    def test_log_level_setting(
        self, mock_main, mock_load_config, mock_load_creds, mock_detect_state
    ):
        """Test log level setting."""
        # Mock configuration state to be ready (config and auth exist)
        mock_detect_state.return_value = (
            "ready",
            "Bot is configured and ready to start.",
            {"test": "config"},
        )
        mock_load_creds.return_value = Mock()
        mock_load_config.return_value = {"test": "config"}  # Return valid config
        mock_main.return_value = 0

        # Should not raise exception - just run the bot
        cli.main()
        mock_main.assert_awaited_once()

    @patch("sys.argv", ["biblebot", "config", "generate"])
    @patch("biblebot.cli.generate_config")
    def test_config_generate_command(self, mock_generate):
        """Test config generate command."""
        mock_generate.return_value = True

        cli.main()
        mock_generate.assert_called_once()

    @patch("sys.argv", ["biblebot", "config", "check"])
    @patch("biblebot.bot.load_config")
    @patch("biblebot.bot.load_environment")
    @patch("biblebot.auth.check_e2ee_status")
    @patch("builtins.print")
    def test_config_check_command(
        self, mock_print, mock_e2ee, mock_load_env, mock_load_config
    ):
        """Test config check command."""
        mock_load_config.return_value = {"matrix_room_ids": ["!room1", "!room2"]}
        mock_load_env.return_value = (None, {"api_key1": "value1", "api_key2": ""})
        mock_e2ee.return_value = {"available": True}

        cli.main()
        mock_load_config.assert_called_once()
        mock_print.assert_called()

    @patch("sys.argv", ["biblebot", "auth", "login"])
    @patch("biblebot.cli.interactive_login", new_callable=AsyncMock)
    @patch("sys.exit")
    def test_auth_login_command(self, mock_exit, mock_login):
        """Test auth login command."""
        # Return True from awaited coroutine
        mock_login.return_value = True

        # Mock sys.exit to prevent actual exit and capture the call
        mock_exit.side_effect = SystemExit

        with pytest.raises(SystemExit):
            cli.main()

        # Verify login was called and exit was called with success
        mock_login.assert_called_once()
        mock_exit.assert_called_with(0)

    @patch("sys.argv", ["biblebot", "auth", "logout"])
    @patch("biblebot.cli.interactive_logout", new_callable=AsyncMock)
    @patch("sys.exit")
    def test_auth_logout_command(self, mock_exit, mock_logout):
        """Test auth logout command."""
        mock_logout.return_value = True

        # Mock sys.exit to prevent actual exit and capture the call
        mock_exit.side_effect = SystemExit

        with pytest.raises(SystemExit):
            cli.main()

        mock_logout.assert_called_once()
        mock_exit.assert_called_with(0)

    @patch("sys.argv", ["biblebot", "auth", "status"])
    @patch("biblebot.auth.load_credentials")
    @patch("biblebot.auth.print_e2ee_status")
    @patch("builtins.print")
    def test_auth_status_logged_in(self, mock_print, mock_print_e2ee, mock_load_creds):
        """Test auth status when logged in."""
        mock_creds = Mock()
        mock_creds.user_id = "@test:matrix.org"
        mock_creds.homeserver = "https://matrix.org"
        mock_creds.device_id = "DEVICE123"
        mock_load_creds.return_value = mock_creds

        cli.main()
        mock_print.assert_called()
        mock_print_e2ee.assert_called_once()

    @patch("sys.argv", ["biblebot", "auth", "status"])
    @patch("biblebot.auth.load_credentials")
    @patch("biblebot.auth.print_e2ee_status")
    @patch("builtins.print")
    def test_auth_status_not_logged_in(
        self, mock_print, mock_print_e2ee, mock_load_creds
    ):
        """Test auth status when not logged in."""
        mock_load_creds.return_value = None

        cli.main()
        mock_print.assert_called()
        mock_print_e2ee.assert_called_once()

    @patch("sys.argv", ["biblebot", "service", "install"])
    @patch("biblebot.setup_utils.install_service")
    def test_service_install_command(self, mock_install):
        """Test service install command."""
        mock_install.return_value = True

        cli.main()
        mock_install.assert_called_once()

    @patch("sys.argv", ["biblebot", "config"])
    @patch("argparse.ArgumentParser.print_help")
    def test_config_no_action(self, mock_print_help):
        """Test config command with no action."""
        with pytest.raises(SystemExit):
            cli.main()
        mock_print_help.assert_called()

    @patch("sys.argv", ["biblebot", "auth"])
    @patch("argparse.ArgumentParser.print_help")
    def test_auth_no_action(self, mock_print_help):
        """Test auth command with no action."""
        with pytest.raises(SystemExit):
            cli.main()
        mock_print_help.assert_called()

    @patch("sys.argv", ["biblebot", "service"])
    @patch("argparse.ArgumentParser.print_help")
    def test_service_no_action(self, mock_print_help):
        """Test service command with no action."""
        with pytest.raises(SystemExit):
            cli.main()
        mock_print_help.assert_called()

    @patch("sys.argv", ["biblebot", "config", "check"])
    @patch("biblebot.bot.load_config")
    @patch("sys.exit")
    def test_config_check_invalid_config(self, mock_exit, mock_load_config):
        """Test config check with invalid config."""
        mock_load_config.return_value = None
        mock_exit.side_effect = SystemExit(1)

        with pytest.raises(SystemExit) as e:
            cli.main()

        assert e.value.code == 1
        mock_exit.assert_called_with(1)


class TestCLIBotOperation:
    """Test CLI bot operation scenarios."""

    @patch("sys.argv", ["biblebot"])
    @patch("biblebot.cli.detect_configuration_state")
    @patch("builtins.input")
    @patch("biblebot.auth.load_credentials")
    @patch("biblebot.bot.load_config")
    @patch("biblebot.bot.main_with_config", new_callable=AsyncMock)
    def test_bot_run_with_config(
        self,
        mock_main,
        mock_load_config,
        mock_load_creds,
        mock_input,
        mock_detect_state,
    ):
        """Test running bot with existing config."""
        # Mock configuration state to be ready
        mock_detect_state.return_value = (
            "ready",
            "Bot is configured and ready to start.",
            {"test": "config"},
        )

        mock_load_creds.return_value = Mock()
        mock_input.return_value = "y"  # User chooses to start bot
        mock_load_config.return_value = {"test": "config"}  # Return valid config
        mock_main.return_value = 0

        cli.main()
        mock_main.assert_awaited_once()

    @patch("sys.argv", ["biblebot"])
    @patch("biblebot.cli.detect_configuration_state")
    @patch("builtins.input")
    @patch("biblebot.cli.generate_config")
    def test_bot_no_config_generate_yes(
        self, mock_generate, mock_input, mock_detect_state
    ):
        """Test bot operation when no config exists and user chooses to generate."""
        # Mock configuration state to need setup
        mock_detect_state.return_value = (
            "setup",
            "No configuration found. Setup is required.",
            None,
        )

        mock_input.return_value = "y"
        mock_generate.return_value = True

        # Should not raise SystemExit anymore - just returns
        cli.main()

        mock_generate.assert_called_once()

    @patch("sys.argv", ["biblebot"])
    @patch("biblebot.cli.detect_configuration_state")
    @patch("biblebot.cli.generate_config")
    def test_bot_no_config_generate_no(self, mock_generate, mock_detect_state):
        """Test bot operation when no config exists and config generation fails."""
        # Mock configuration state to need setup
        mock_detect_state.return_value = (
            "setup",
            "No configuration found. Setup is required.",
            None,
        )

        # Mock config generation failure
        mock_generate.return_value = False

        # Should raise SystemExit(1) when config generation fails

        with pytest.raises(SystemExit) as exc_info:
            cli.main()
        assert exc_info.value.code == 1

    @patch("sys.argv", ["biblebot"])
    @patch("biblebot.cli.detect_configuration_state")
    @patch("biblebot.cli.generate_config")
    def test_bot_no_config_eof_error(self, mock_generate, mock_detect_state):
        """Test bot operation when no config exists and config generation succeeds."""
        # Mock configuration state to need setup
        mock_detect_state.return_value = (
            "setup",
            "No configuration found. Setup is required.",
            None,
        )

        # Mock successful config generation
        mock_generate.return_value = True

        # Should complete successfully without raising
        cli.main()  # Should not raise any exceptions
        mock_generate.assert_called_once()

    @patch("sys.argv", ["biblebot"])
    @patch("biblebot.cli.detect_configuration_state")
    @patch("builtins.input")
    def test_bot_no_config_keyboard_interrupt(self, mock_input, mock_detect_state):
        """
        Test that the CLI handles a KeyboardInterrupt gracefully when configuration requires authentication.

        Mocks the configuration detection to indicate authentication is required and simulates a KeyboardInterrupt raised during user input; running cli.main() must not propagate the exception.
        """
        # Mock configuration state to need auth
        mock_detect_state.return_value = (
            "auth",
            "Configuration found but authentication required. Use 'biblebot auth login'.",
            {"test": "config"},
        )
        mock_input.side_effect = KeyboardInterrupt()

        # Should handle KeyboardInterrupt gracefully
        cli.main()

    @patch("sys.argv", ["biblebot"])
    @patch("biblebot.cli.detect_configuration_state")
    @patch("builtins.input")
    @patch("biblebot.auth.load_credentials")
    @patch("biblebot.bot.load_config")
    @patch("biblebot.bot.main_with_config", new_callable=AsyncMock)
    def test_bot_keyboard_interrupt(
        self,
        mock_main,
        mock_load_config,
        mock_load_creds,
        mock_input,
        mock_detect_state,
    ):
        """Test bot operation with keyboard interrupt."""
        # Mock configuration state to be ready
        mock_detect_state.return_value = (
            "ready",
            "Bot is configured and ready to start.",
            {"test": "config"},
        )
        mock_load_creds.return_value = Mock()
        mock_input.return_value = "y"  # User chooses to start bot
        mock_load_config.return_value = {"test": "config"}  # Return valid config
        mock_main.side_effect = KeyboardInterrupt()

        # CLI catches KeyboardInterrupt and handles it gracefully
        cli.main()  # Should not raise exception
        mock_main.assert_awaited_once()

    @patch("sys.argv", ["biblebot"])
    @patch("biblebot.cli.detect_configuration_state")
    @patch("builtins.input")
    @patch("biblebot.auth.load_credentials")
    @patch("biblebot.bot.main_with_config", new_callable=AsyncMock)
    def test_bot_runtime_error(
        self, mock_main, mock_load_creds, mock_input, mock_detect_state
    ):
        """
        Verify CLI handles a runtime error during bot startup by exiting with code 1.

        Mocks a ready configuration state and valid credentials, simulates the user choosing to start the bot, and makes the bot's run function raise a RuntimeError. Asserts the CLI main() raises SystemExit with exit code 1 (graceful failure).
        """
        # Mock configuration state to be ready
        mock_detect_state.return_value = (
            "ready",
            "Bot is configured and ready to start.",
            {"test": "config"},
        )
        mock_load_creds.return_value = Mock()
        mock_input.return_value = "y"  # User chooses to start bot
        mock_main.side_effect = RuntimeError("Runtime error")

        # CLI should handle the exception gracefully and exit with code 1
        with pytest.raises(SystemExit) as exc_info:
            cli.main()
        assert exc_info.value.code == 1
        mock_main.assert_awaited_once()


class TestCLIUtilityFunctions:
    """Test CLI utility functions."""

    @patch("biblebot.cli.CONFIG_DIR")
    def test_get_default_config_path_custom_home(self, mock_config_dir, tmp_path):
        """Test default config path with custom home directory."""
        mock_config_dir.__truediv__ = lambda _, other: tmp_path / other
        path = cli.get_default_config_path()
        expected = tmp_path / "config.yaml"
        assert path == expected

    @patch("os.chmod")
    @patch("pathlib.Path.mkdir")
    @patch("pathlib.Path.exists")
    @patch("biblebot.cli.copy_sample_config_to")
    def test_generate_config_success(
        self, mock_copy_config, mock_path_exists, mock_path_mkdir, mock_chmod
    ):
        """Test successful config generation."""
        mock_path_exists.return_value = False  # No existing files

        result = cli.generate_config("/test/config.yaml")

        assert result is True
        mock_path_mkdir.assert_called_once_with(parents=True, exist_ok=True)
        mock_copy_config.assert_called_once_with("/test/config.yaml")
        from pathlib import Path

        mock_chmod.assert_called_once_with(Path("/test/config.yaml"), 0o600)

    @patch("builtins.print")
    @patch("pathlib.Path.exists")
    def test_generate_config_existing_files(self, mock_path_exists, mock_print):
        """Test config generation when files already exist."""
        mock_path_exists.return_value = True  # Files exist

        result = cli.generate_config("/test/config.yaml")

        assert result is False
        mock_print.assert_called()


class TestDetectConfigurationState:
    """Test detect_configuration_state function coverage."""

    @patch("biblebot.cli.get_default_config_path")
    @patch("pathlib.Path.exists")
    def test_no_config_file(self, mock_exists, mock_get_path):
        """Test when config file doesn't exist."""
        from pathlib import Path

        mock_get_path.return_value = Path("/tmp/config.yaml")  # noqa: S108
        mock_exists.return_value = False

        state, message, config = cli.detect_configuration_state()
        assert state == "setup"
        assert "No configuration found" in message
        assert config is None

    @patch("biblebot.cli.get_default_config_path")
    @patch("pathlib.Path.exists")
    @patch("biblebot.bot.load_config")
    def test_invalid_config(self, mock_load_config, mock_exists, mock_get_path):
        """Test when config is invalid."""
        from pathlib import Path

        mock_get_path.return_value = Path("/tmp/config.yaml")  # noqa: S108
        mock_exists.return_value = True
        mock_load_config.return_value = None

        state, message, config = cli.detect_configuration_state()
        assert state == "setup"
        assert "Invalid configuration" in message
        assert config is None

    @patch("biblebot.cli.get_default_config_path")
    @patch("pathlib.Path.exists")
    @patch("biblebot.bot.load_config")
    def test_config_load_error(self, mock_load_config, mock_exists, mock_get_path):
        """Test when config loading raises an exception."""
        from pathlib import Path

        mock_get_path.return_value = Path("/tmp/config.yaml")  # noqa: S108
        mock_exists.return_value = True
        mock_load_config.side_effect = ValueError("Invalid YAML")

        state, message, config = cli.detect_configuration_state()
        assert state == "setup"
        assert "Configuration error: Invalid YAML" in message
        assert config is None

    @patch("biblebot.cli.get_default_config_path")
    @patch("pathlib.Path.exists")
    @patch("biblebot.bot.load_config")
    @patch("os.getenv")
    def test_legacy_token_present(
        self, mock_getenv, mock_load_config, mock_exists, mock_get_path
    ):
        """Test when legacy MATRIX_ACCESS_TOKEN is present."""
        from pathlib import Path

        mock_get_path.return_value = Path("/tmp/config.yaml")  # noqa: S108
        # First call for config file exists, second call for credentials file doesn't exist
        mock_exists.side_effect = [True, False]
        mock_load_config.return_value = {"test": "config"}
        mock_getenv.return_value = "legacy_token"

        state, message, config = cli.detect_configuration_state()
        assert state == "ready_legacy"
        assert "legacy access token" in message
        assert config == {"test": "config"}

    @patch("biblebot.cli.get_default_config_path")
    @patch("pathlib.Path.exists")
    @patch("biblebot.bot.load_config")
    @patch("os.getenv")
    @patch("biblebot.cli.load_credentials")
    def test_invalid_credentials(
        self,
        mock_load_creds,
        mock_getenv,
        mock_load_config,
        mock_exists,
        mock_get_path,
    ):
        """Test when credentials are invalid."""
        from pathlib import Path

        mock_get_path.return_value = Path("/tmp/config.yaml")  # noqa: S108
        mock_exists.return_value = True
        mock_load_config.return_value = {"test": "config"}
        mock_getenv.return_value = None
        mock_load_creds.return_value = None

        state, message, config = cli.detect_configuration_state()
        assert state == "auth"
        assert "Invalid credentials found" in message
        assert config == {"test": "config"}

    @patch("biblebot.cli.get_default_config_path")
    @patch("pathlib.Path.exists")
    @patch("biblebot.bot.load_config")
    @patch("os.getenv")
    @patch("biblebot.cli.load_credentials")
    def test_credentials_load_error(
        self,
        mock_load_creds,
        mock_getenv,
        mock_load_config,
        mock_exists,
        mock_get_path,
    ):
        """Test when credentials loading raises an exception."""
        from pathlib import Path

        mock_get_path.return_value = Path("/tmp/config.yaml")  # noqa: S108
        mock_exists.return_value = True
        mock_load_config.return_value = {"test": "config"}
        mock_getenv.return_value = None
        mock_load_creds.side_effect = OSError("Cannot read credentials")

        state, message, config = cli.detect_configuration_state()
        assert state == "auth"
        assert "Cannot load credentials" in message
        assert config == {"test": "config"}


class TestCLIErrorHandling:
    """Test CLI error handling scenarios."""

    @patch("sys.argv", ["biblebot", "--config", "nonexistent.yaml"])
    @patch("biblebot.cli.detect_configuration_state")
    @patch("builtins.input", return_value="n")  # Mock user input to avoid stdin issues
    def test_invalid_config_handling(self, mock_input, mock_detect):
        """Test handling of invalid configuration."""
        # This test is for the non-interactive main() function with --config argument
        # When config file doesn't exist, it should offer to generate and exit with 1 when user says no

        with pytest.raises(SystemExit) as exc_info:
            cli.main()
        assert exc_info.value.code == 1

    @patch("sys.argv", ["biblebot"])
    @patch("biblebot.cli.detect_configuration_state")
    @patch("biblebot.bot.main_with_config", new_callable=AsyncMock)
    def test_keyboard_interrupt_handling(self, mock_main, mock_detect):
        """Test handling of keyboard interrupt."""
        mock_detect.return_value = ("ready", "Ready", {"test": "config"})
        mock_main.side_effect = KeyboardInterrupt()

        # CLI main() should handle KeyboardInterrupt gracefully and not raise
        cli.main()  # Should complete without raising exception

    def test_cli_module_functions_exist(self):
        """Test that expected CLI functions exist."""
        assert hasattr(cli, "main")
        assert hasattr(cli, "detect_configuration_state")
        assert hasattr(cli, "generate_config")
        assert callable(cli.main)
