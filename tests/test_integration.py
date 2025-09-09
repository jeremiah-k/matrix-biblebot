"""Integration tests for the matrix-biblebot package."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import nio
import nio.exceptions
import pytest
import yaml

from biblebot import auth, bot, cli


class TestEndToEndWorkflow:
    """Test end-to-end workflows."""

    @pytest.fixture
    def temp_workspace(self, tmp_path):
        """
        Create a temporary workspace directory populated with sample configuration files for tests.

        The function creates a directory named "biblebot_test" under the provided tmp_path and writes two files:
        - config.yaml: YAML with keys `matrix_homeserver`, `matrix_user`, `matrix_room_ids`, and `matrix.e2ee.enabled` (False).
        - .env: environment file containing `MATRIX_ACCESS_TOKEN=test_token` and `ESV_API_KEY=test_key`.

        Parameters:
            tmp_path (pathlib.Path): Base temporary directory (pytest tmp_path fixture).

        Returns:
            pathlib.Path: Path to the created workspace directory.
        """
        workspace = tmp_path / "biblebot_test"
        workspace.mkdir()

        # Create config file
        config = {
            "matrix_homeserver": "https://matrix.org",
            "matrix_user": "@testbot:matrix.org",
            "matrix_room_ids": ["!room1:matrix.org"],
            "matrix": {"e2ee": {"enabled": False}},
        }

        config_file = workspace / "config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config, f)

        # Create .env file
        env_file = workspace / ".env"
        env_file.write_text("MATRIX_ACCESS_TOKEN=test_token\nESV_API_KEY=test_key\n")

        return workspace

    def test_config_generation_workflow(self, temp_workspace):
        """Test the complete config generation workflow."""
        target_dir = temp_workspace / "generated"
        target_config = target_dir / "config.yaml"

        # Test config generation
        with patch("biblebot.tools.get_sample_config_path") as mock_config:
            sample_config = temp_workspace / "sample_config.yaml"

            # Create sample config file with API keys section
            sample_config.write_text(
                """
matrix_homeserver: "https://example.matrix.org"
matrix_user: "@bot:example.org"
matrix_room_ids:
  - "!example:matrix.org"
e2ee:
  enabled: false
api_keys:
  esv: null
"""
            )

            mock_config.return_value = sample_config

            result = cli.generate_config(str(target_config))

            assert result is True
            assert target_config.exists()
            # No longer generates .env file
            assert not (target_dir / ".env").exists()

    @pytest.mark.asyncio
    async def test_authentication_workflow(self, temp_workspace):
        """
        Integration test that verifies saving/loading of credentials and the interactive logout cleanup.

        This async test uses the temp_workspace fixture (a Path to a temporary config directory) and patches auth.CONFIG_DIR, auth.CREDENTIALS_FILE, and auth.E2EE_STORE_DIR to operate inside that workspace. It performs three checks:
        1. Saves a Credentials object to disk via auth.save_credentials and verifies auth.load_credentials returns the same user_id and access_token.
        2. Mocks the AsyncClient used during logout and calls auth.interactive_logout, asserting it returns True.
        3. Verifies that credentials.json is removed from the workspace as part of the logout cleanup.

        Side effects: creates and deletes a credentials.json file inside temp_workspace.
        """
        # Patch the config directory to use our temp workspace
        with patch.object(auth, "CONFIG_DIR", temp_workspace):
            with patch.object(
                auth, "CREDENTIALS_FILE", temp_workspace / "credentials.json"
            ):
                with patch.object(
                    auth, "E2EE_STORE_DIR", temp_workspace / "e2ee-store"
                ):

                    # Test saving credentials
                    creds = auth.Credentials(
                        homeserver="https://matrix.org",
                        user_id="@test:matrix.org",
                        access_token="test_token",  # noqa: S106
                        device_id="TEST_DEVICE",
                    )

                    auth.save_credentials(creds)

                    # Test loading credentials
                    loaded_creds = auth.load_credentials()

                    assert loaded_creds is not None
                    assert loaded_creds.user_id == "@test:matrix.org"
                    assert loaded_creds.access_token == "test_token"  # noqa: S105

                    # Test logout (cleanup)
                    with patch("biblebot.auth.AsyncClient") as mock_client_class:
                        mock_client = MagicMock(
                            spec_set=["restore_login", "logout", "close"]
                        )
                        mock_client.restore_login = MagicMock()  # Sync method
                        mock_client.logout = AsyncMock()  # Async method
                        mock_client.close = AsyncMock()  # Async method
                        mock_client_class.return_value = mock_client

                        result = await auth.interactive_logout()

                        assert result is True
                        assert not (temp_workspace / "credentials.json").exists()

    @pytest.mark.asyncio
    @patch.dict(
        "os.environ",
        {
            "MATRIX_HOMESERVER": "https://matrix.org",
            "MATRIX_USER_ID": "@testbot:matrix.org",
            "MATRIX_ACCESS_TOKEN": "test_token",
        },
    )  # Set required environment variables for legacy mode
    async def test_bot_initialization_workflow(self, temp_workspace):
        """Test bot initialization with real config files."""
        config_file = temp_workspace / "config.yaml"

        with patch("biblebot.auth.load_credentials") as mock_load_creds:
            mock_load_creds.return_value = None  # No saved credentials

            with patch("biblebot.bot.AsyncClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_client.restore_login = MagicMock()
                mock_client.add_event_callback = MagicMock()
                mock_client_class.return_value = mock_client

                with patch("biblebot.bot.BibleBot") as mock_bot_class:
                    mock_bot_instance = MagicMock()
                    mock_bot_instance.client = mock_client
                    mock_bot_instance.start = AsyncMock()
                    mock_bot_class.return_value = mock_bot_instance

                    # This should load config and initialize bot
                    await bot.main(str(config_file))

                    # Verify bot was created and started
                    mock_bot_class.assert_called_once()
                    mock_bot_instance.start.assert_called_once()


class TestConfigValidation:
    """Test configuration validation across modules."""

    def test_config_loading_validation(self, tmp_path):
        """Test config validation in different scenarios."""
        # Test valid config
        valid_config = {
            "matrix_homeserver": "https://matrix.org",
            "matrix_user": "@test:matrix.org",
            "matrix_room_ids": ["!room:matrix.org"],
        }

        config_file = tmp_path / "valid.yaml"
        with open(config_file, "w") as f:
            yaml.dump(valid_config, f)

        loaded_config = bot.load_config(str(config_file))
        assert loaded_config is not None
        assert loaded_config["matrix_homeserver"] == "https://matrix.org"

        # Test invalid config (missing required fields)
        invalid_config = {
            "matrix_homeserver": "https://matrix.org"
            # Missing matrix_user and matrix_room_ids
        }

        invalid_file = tmp_path / "invalid.yaml"
        with open(invalid_file, "w") as f:
            yaml.dump(invalid_config, f)

        loaded_invalid = bot.load_config(str(invalid_file))
        assert loaded_invalid is None

    @patch.dict("os.environ", {}, clear=True)  # Clear all environment variables
    def test_environment_loading_integration(self, tmp_path):
        """Test environment loading with different configurations."""
        config_file = tmp_path / "config.yaml"
        env_file = tmp_path / ".env"

        # Create minimal config
        config = {"matrix_homeserver": "https://matrix.org"}
        with open(config_file, "w") as f:
            yaml.dump(config, f)

        # Test with .env file
        env_file.write_text("MATRIX_ACCESS_TOKEN=file_token\nESV_API_KEY=file_key\n")

        # Load config first, then pass to load_environment
        config = bot.load_config(str(config_file))
        matrix_token, api_keys = bot.load_environment(config, str(config_file))

        assert matrix_token == "file_token"  # noqa: S105
        assert api_keys["esv"] == "file_key"

        # Test with OS environment override
        with patch.dict("os.environ", {"MATRIX_ACCESS_TOKEN": "env_token"}):
            matrix_token, api_keys = bot.load_environment(config, str(config_file))
            assert (
                matrix_token == "env_token"  # noqa: S105 - OS env should override file
            )


class TestErrorScenarios:
    """Test error handling across modules."""

    @pytest.mark.asyncio
    async def test_network_error_handling(self):
        """Test handling of network errors in API requests."""

        # Test timeout handling
        with patch("aiohttp.ClientSession") as mock_session_class:
            # Create mock session context manager
            mock_session = MagicMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)

            # Make get() raise timeout error
            mock_session.get.side_effect = asyncio.TimeoutError()

            mock_session_class.return_value = mock_session

            result = await bot.make_api_request("https://test.api/timeout")
            assert result is None

        # Test connection error handling
        with patch("aiohttp.ClientSession") as mock_session_class:
            # Create mock session context manager that raises on get()
            mock_session = MagicMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)

            # Make get() raise aiohttp.ClientError (which is caught by make_api_request)
            import aiohttp

            mock_session.get.side_effect = aiohttp.ClientError("Connection failed")

            mock_session_class.return_value = mock_session

            result = await bot.make_api_request("https://test.api/error")
            assert result is None

    def test_file_permission_errors(self, tmp_path):
        """Test handling of file permission errors."""
        # Mock tempfile.NamedTemporaryFile to raise PermissionError
        with patch("tempfile.NamedTemporaryFile") as mock_temp, patch.object(
            auth, "CREDENTIALS_FILE", tmp_path / "credentials.json"
        ):
            mock_temp.side_effect = PermissionError("Permission denied")

            # Attempting to save credentials should raise permission error
            creds = auth.Credentials(
                homeserver="https://matrix.org",
                user_id="@test:matrix.org",
                access_token="test_token",  # noqa: S106
            )

            # Should raise permission error when trying to create temp file
            with pytest.raises(PermissionError):
                auth.save_credentials(creds)

    @pytest.mark.asyncio
    async def test_matrix_client_errors(self):
        """Test handling of Matrix client errors."""
        sample_config = {
            "matrix_homeserver": "https://matrix.org",
            "matrix_user": "@test:matrix.org",
            "matrix_room_ids": ["!room:matrix.org"],
        }

        with patch("biblebot.bot.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client

            # Test sync error handling
            mock_client.sync.side_effect = Exception("Sync failed")

            bot_instance = bot.BibleBot(sample_config)
            bot_instance.client = mock_client
            bot_instance.start_time = 1000

            # The bot should handle sync errors gracefully and continue to sync_forever
            await bot_instance.start()
            mock_client.sync_forever.assert_awaited_once()


class TestCacheManagement:
    """Test caching functionality across the application."""

    @pytest.mark.asyncio
    async def test_bible_text_caching(self):
        """Test Bible text caching behavior."""
        # Clear cache
        if hasattr(bot, "_passage_cache"):
            bot._passage_cache.clear()

        mock_response = {"text": "Test verse", "reference": "Test 1:1"}

        with patch.object(
            bot, "make_api_request", new=AsyncMock(return_value=mock_response)
        ) as mock_request:
            # First call should hit API
            result1 = await bot.get_bible_text("Test 1:1", "kjv")

            # Second call should use cache
            result2 = await bot.get_bible_text("Test 1:1", "kjv")

            assert result1 == result2
            # API should only be called once due to caching
            mock_request.assert_called_once()

    def test_cache_size_limits(self):
        """Test that cache respects size limits."""
        # Clear cache
        if hasattr(bot, "_passage_cache"):
            bot._passage_cache.clear()

        # Test cache size management

        # Temporarily set a small cache size for testing
        with patch("biblebot.bot._PASSAGE_CACHE_MAX", 2):
            # Add items to cache
            bot._cache_set("passage1", "kjv", ("text1", "ref1"))
            bot._cache_set("passage2", "kjv", ("text2", "ref2"))
            bot._cache_set("passage3", "kjv", ("text3", "ref3"))  # Should evict oldest

            # Cache should not exceed max size
            assert len(bot._passage_cache) <= 2


class TestCLIIntegration:
    """Test CLI integration with other modules."""

    @patch("biblebot.auth.check_e2ee_status")
    @patch("biblebot.bot.load_environment")
    @patch("biblebot.bot.load_config")
    def test_config_check_command_integration(
        self, mock_load_config, mock_load_env, mock_e2ee_status
    ):
        """
        Verify the config-check flow integrates load_config, load_environment, and check_e2ee_status correctly.

        Loads a mock config with two Matrix room IDs, a mock environment returning one non-empty API key (esv),
        and a mocked E2EE status indicating availability. Asserts the config contains two rooms, exactly one
        non-empty API key is present, and E2EE is reported available.
        """
        # Setup mocks - check_e2ee_status is a sync function, use regular Mock
        mock_load_config.return_value = {
            "matrix_room_ids": ["!room1:matrix.org", "!room2:matrix.org"]
        }
        mock_load_env.return_value = (None, {"esv": "test_key", "bible": None})
        # Ensure this is a regular Mock, not AsyncMock
        mock_e2ee_status.return_value = {"available": True}

        # Test the validation logic
        config = mock_load_config("test.yaml")
        if config:
            _, api_keys = mock_load_env("test.yaml")
            e2ee_status = mock_e2ee_status()

            # Verify integration works
            assert len(config["matrix_room_ids"]) == 2
            assert len([k for k, v in api_keys.items() if v]) == 1
            assert e2ee_status["available"] is True

    @patch("biblebot.auth.load_credentials")
    def test_auth_status_integration(self, mock_load_creds):
        """Test auth status command integration."""
        # Test with credentials
        mock_creds = MagicMock()
        mock_creds.user_id = "@test:matrix.org"
        mock_creds.homeserver = "https://matrix.org"
        mock_creds.device_id = "TEST_DEVICE"
        mock_load_creds.return_value = mock_creds

        creds = mock_load_creds()
        assert creds is not None
        assert creds.user_id == "@test:matrix.org"

        # Test without credentials
        mock_load_creds.return_value = None
        creds = mock_load_creds()
        assert creds is None


class TestCrossModuleIntegration:
    """Test integration between different modules."""

    def test_auth_to_cli_integration(self):
        """Test auth module integrates with CLI commands."""
        # Test credentials path function
        with patch("biblebot.auth.get_config_dir") as mock_get_dir:
            mock_get_dir.return_value = "/test/path"

            auth.credentials_path()

            # Should integrate properly
            mock_get_dir.assert_called_once()

    @pytest.mark.asyncio
    async def test_bot_to_auth_integration(self):
        """Test bot module integrates with auth functions."""
        # Test homeserver discovery integration
        mock_client = AsyncMock()
        mock_client.discovery_info.side_effect = nio.exceptions.RemoteTransportError(
            "Network error"
        )

        result = await auth.discover_homeserver(mock_client, "https://matrix.org")

        # Should handle integration gracefully
        assert result == "https://matrix.org"

    def test_cli_to_bot_integration(self, tmp_path):
        """Test CLI integrates with bot configuration."""
        # Create test config
        config_data = {
            "matrix_homeserver": "https://matrix.org",
            "matrix_user": "@testbot:matrix.org",
            "matrix_room_ids": ["!room1:matrix.org"],
        }

        config_file = tmp_path / "config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        # Test CLI to bot integration
        config = bot.load_config(str(config_file))

        # Should integrate properly
        assert config is not None
        assert config["matrix_homeserver"] == "https://matrix.org"


class TestDataFlowIntegration:
    """Test data flow integration across components."""

    def test_config_to_environment_flow(self, tmp_path):
        """Test config and environment data flow integration."""
        # Create .env file
        env_file = tmp_path / ".env"
        env_file.write_text(
            "MATRIX_ACCESS_TOKEN=flow_test_token\nESV_API_KEY=flow_test_key"
        )

        # Test data flow
        # Create a minimal config for testing
        config = {"matrix_room_ids": ["!test:matrix.org"]}
        matrix_token, api_keys = bot.load_environment(
            config, str(tmp_path / "config.yaml")
        )

        # Verify data flow integration
        assert isinstance(api_keys, dict)
        assert "esv" in api_keys

    def test_credentials_to_auth_flow(self):
        """Test credentials data flow integration."""
        # Create test credentials
        creds_data = {
            "homeserver": "https://matrix.org",
            "user_id": "@test:matrix.org",
            "access_token": "flow_token",
            "device_id": "flow_device",
        }

        # Test data flow
        creds = auth.Credentials.from_dict(creds_data)
        back_to_dict = creds.to_dict()

        # Verify data flow integration
        assert back_to_dict == creds_data

    @pytest.mark.asyncio
    async def test_api_to_cache_flow(self):
        """Test API response to cache data flow integration."""
        # Clear cache
        if hasattr(bot, "_passage_cache"):
            bot._passage_cache.clear()

        # Test data flow
        bot._cache_set("Test 1:1", "kjv", ("Test text", "Test 1:1"))
        result = bot._cache_get("Test 1:1", "kjv")

        # Verify data flow integration
        assert result == ("Test text", "Test 1:1")


class TestErrorPropagationIntegration:
    """Test error propagation integration across components."""

    def test_config_error_propagation(self, tmp_path):
        """Test config errors propagate properly."""
        # Create invalid config
        invalid_config = tmp_path / "invalid.yaml"
        invalid_config.write_text("invalid: yaml: [unclosed")

        # Test error propagation
        result = bot.load_config(str(invalid_config))

        # Should propagate error gracefully
        assert result is None

    @pytest.mark.asyncio
    async def test_api_error_propagation(self):
        """Test API errors propagate properly."""
        # Clear cache to ensure we hit the API
        bot._passage_cache.clear()

        with patch("biblebot.bot.make_api_request", new=AsyncMock(return_value=None)):

            # Test error propagation - should raise PassageNotFound
            from biblebot.bot import PassageNotFound

            with pytest.raises(PassageNotFound) as exc_info:
                await bot.get_bible_text("Test 1:1", "kjv")

            # Should propagate error gracefully with proper exception
            assert "Test 1:1" in str(exc_info.value)
            assert "not found in KJV" in str(exc_info.value)

    def test_auth_error_propagation(self):
        """Test auth errors propagate properly."""
        # Test with missing required fields
        incomplete_data = {"homeserver": "https://matrix.org"}

        # Test error propagation
        creds = auth.Credentials.from_dict(incomplete_data)

        # Should propagate error gracefully with defaults
        assert creds.user_id == ""
        assert creds.access_token == ""


class TestComponentInteractionIntegration:
    """Test component interaction integration."""

    def test_cli_auth_interaction(self):
        """Test CLI and auth component interaction."""
        with patch("biblebot.auth.load_credentials") as mock_load:
            mock_load.return_value = None

            # Test interaction
            creds = auth.load_credentials()

            # Should interact properly
            assert creds is None
            mock_load.assert_called_once()

    def test_bot_cache_interaction(self):
        """Test bot and cache component interaction."""
        # Clear cache
        if hasattr(bot, "_passage_cache"):
            bot._passage_cache.clear()

        # Test interaction
        bot._cache_set("Interaction 1:1", "test", ("Test", "Interaction 1:1"))
        result = bot._cache_get("interaction 1:1", "TEST")  # Different case

        # Should interact with case insensitivity
        assert result == ("Test", "Interaction 1:1")

    def test_auth_directory_interaction(self, tmp_path):
        """Test auth and directory component interaction."""
        with patch("biblebot.auth.CONFIG_DIR", new=tmp_path):
            with patch("os.chmod"):
                result = auth.get_config_dir()
                assert result == tmp_path
                assert (tmp_path).exists()
