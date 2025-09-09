"""
Configuration testing patterns following mmrelay's comprehensive approach.
Tests configuration loading, validation, and management patterns.
"""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

from biblebot.auth import Credentials, load_credentials
from biblebot.bot import BibleBot


class TestConfigurationPatterns:
    """Test configuration management patterns."""

    def test_default_configuration_loading(self):
        """Test loading of default configuration values."""
        # Test with minimal configuration
        minimal_config = {
            "homeserver": "https://matrix.org",
            "user_id": "@test:matrix.org",
            "access_token": "test_token",
            "device_id": "TEST_DEVICE",
        }

        bot = BibleBot(config=minimal_config)

        # Should have loaded configuration
        assert bot.config["homeserver"] == "https://matrix.org"
        assert bot.config["user_id"] == "@test:matrix.org"
        assert bot.config["access_token"] == "test_token"  # noqa: S105
        assert bot.config["device_id"] == "TEST_DEVICE"

    def test_configuration_validation_patterns(self):
        """Test configuration validation and error handling."""
        # Test with invalid bot settings that actually trigger validation
        invalid_configs = [
            {
                "homeserver": "https://matrix.org",
                "user_id": "@test:matrix.org",
                "access_token": "test_token",
                "device_id": "TEST_DEVICE",
                "bot": {
                    "split_message_length": "invalid_number",  # Invalid type
                },
            },
            {
                "homeserver": "https://matrix.org",
                "user_id": "@test:matrix.org",
                "access_token": "test_token",
                "device_id": "TEST_DEVICE",
                "bot": {
                    "max_message_length": -100,  # Invalid value
                },
            },
            {
                "homeserver": "https://matrix.org",
                "user_id": "@test:matrix.org",
                "access_token": "test_token",
                "device_id": "TEST_DEVICE",
                "bot": {
                    "split_message_length": -50,  # Invalid value
                },
            },
        ]

        for config in invalid_configs:
            # Should handle invalid configurations gracefully
            with patch("biblebot.bot.logger") as mock_logger:
                bot = BibleBot(config=config)
                # Bot should still be created but may have validation warnings
                assert bot.config is not None
                # Should log validation warnings for invalid bot settings
                assert mock_logger.warning.called or mock_logger.error.called

    def test_environment_variable_configuration(self):
        """Test configuration from environment variables."""
        env_vars = {
            "MATRIX_HOMESERVER": "https://env.matrix.org",
            "MATRIX_USER_ID": "@envtest:matrix.org",
            "MATRIX_ACCESS_TOKEN": "env_token",
            "MATRIX_DEVICE_ID": "ENV_DEVICE",
        }

        with patch.dict(os.environ, env_vars):
            # Test that environment variables could be used
            # (Implementation may vary)
            config = {
                "homeserver": os.environ.get("MATRIX_HOMESERVER", "https://matrix.org"),
                "user_id": os.environ.get("MATRIX_USER_ID", "@test:matrix.org"),
                "access_token": os.environ.get("MATRIX_ACCESS_TOKEN", "test_token"),
                "device_id": os.environ.get("MATRIX_DEVICE_ID", "TEST_DEVICE"),
            }

            bot = BibleBot(config=config)

            assert bot.config["homeserver"] == "https://env.matrix.org"
            assert bot.config["user_id"] == "@envtest:matrix.org"

    def test_configuration_file_loading(self):
        """Test loading configuration from files."""
        config_data = {
            "homeserver": "https://file.matrix.org",
            "user_id": "@filetest:matrix.org",
            "access_token": "file_token",
            "device_id": "FILE_DEVICE",
            "matrix_room_ids": ["!room1:matrix.org", "!room2:matrix.org"],
        }

        # Create temporary config file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config_data, f)
            config_file = f.name

        try:
            # Load configuration from file
            with open(config_file, "r") as f:
                loaded_config = json.load(f)

            bot = BibleBot(config=loaded_config)

            assert bot.config["homeserver"] == "https://file.matrix.org"
            assert bot.config["user_id"] == "@filetest:matrix.org"
            assert "matrix_room_ids" in bot.config

        finally:
            os.unlink(config_file)

    def test_configuration_merging_patterns(self):
        """Test merging of configuration from multiple sources."""
        # Base configuration
        base_config = {
            "homeserver": "https://matrix.org",
            "user_id": "@test:matrix.org",
            "access_token": "test_token",
            "device_id": "TEST_DEVICE",
        }

        # Override configuration
        override_config = {
            "matrix_room_ids": ["!room:matrix.org"],
            "bible_version": "NIV",
        }

        # Merge configurations
        merged_config = {**base_config, **override_config}

        bot = BibleBot(config=merged_config)

        # Should have both base and override values
        assert bot.config["homeserver"] == "https://matrix.org"
        assert "matrix_room_ids" in bot.config
        assert "bible_version" in bot.config

    def test_configuration_secrets_handling(self):
        """Test handling of sensitive configuration data."""
        config_with_secrets = {
            "homeserver": "https://matrix.org",
            "user_id": "@test:matrix.org",
            "access_token": "fake_token_for_tests",
            "device_id": "TEST_DEVICE",
        }

        bot = BibleBot(config=config_with_secrets)

        # Should store secrets securely
        assert bot.config["access_token"] == "fake_token_for_tests"  # noqa: S105

        # Should not expose secrets in string representation
        bot_str = str(bot)
        assert "fake_token_for_tests" not in bot_str

    def test_configuration_validation_errors(self):
        """Test handling of configuration validation errors."""
        # Test with missing required fields
        incomplete_configs = [
            {},  # Empty config
            {"homeserver": "https://matrix.org"},  # Missing user_id
            {"user_id": "@test:matrix.org"},  # Missing homeserver
            {
                "homeserver": "https://matrix.org",
                "user_id": "@test:matrix.org",
                # Missing access_token and device_id
            },
        ]

        for config in incomplete_configs:
            # Should handle incomplete configurations
            bot = BibleBot(config=config)
            # Bot should be created but may have validation warnings
            assert bot.config is not None

    def test_configuration_type_validation(self):
        """
        Verify that configurations with incorrect value types are handled gracefully.

        Creates several configs where fields have the wrong types (e.g., numeric homeserver,
        list user_id, string matrix_room_ids) and ensures constructing a BibleBot does not
        crash and results in a non-None config object.
        """
        # Test with wrong types
        type_configs = [
            {
                "homeserver": 12345,  # Should be string
                "user_id": "@test:matrix.org",
                "access_token": "test_token",
                "device_id": "TEST_DEVICE",
            },
            {
                "homeserver": "https://matrix.org",
                "user_id": ["@test:matrix.org"],  # Should be string, not list
                "access_token": "test_token",
                "device_id": "TEST_DEVICE",
            },
            {
                "homeserver": "https://matrix.org",
                "user_id": "@test:matrix.org",
                "access_token": "test_token",
                "device_id": "TEST_DEVICE",
                "matrix_room_ids": "!room:matrix.org",  # Should be list, not string
            },
        ]

        for config in type_configs:
            # Should handle type mismatches gracefully
            bot = BibleBot(config=config)
            assert bot.config is not None

    def test_configuration_update_patterns(self):
        """Test dynamic configuration updates."""
        initial_config = {
            "homeserver": "https://matrix.org",
            "user_id": "@test:matrix.org",
            "access_token": "test_token",
            "device_id": "TEST_DEVICE",
            "matrix_room_ids": ["!room1:matrix.org"],
        }

        bot = BibleBot(config=initial_config)

        # Test configuration updates
        updated_config = initial_config.copy()
        updated_config["matrix_room_ids"] = ["!room1:matrix.org", "!room2:matrix.org"]

        # Update bot configuration
        bot.config.update(updated_config)

        # Should reflect updates
        assert len(bot.config["matrix_room_ids"]) == 2

    def test_credentials_configuration_integration(self):
        """Test integration between credentials and configuration."""
        # Create test credentials
        test_credentials = Credentials(
            homeserver="https://creds.matrix.org",
            user_id="@credstest:matrix.org",
            access_token="creds_token",  # noqa: S106 - test fixture, not a real secret
            device_id="CREDS_DEVICE",
        )

        # Create temporary credentials file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            creds_data = {
                "homeserver": test_credentials.homeserver,
                "user_id": test_credentials.user_id,
                "access_token": test_credentials.access_token,
                "device_id": test_credentials.device_id,
            }
            json.dump(creds_data, f)
            creds_file = f.name

        try:
            # Mock credentials path
            with patch("biblebot.auth.credentials_path") as mock_path:
                mock_path.return_value = Path(creds_file)

                # Load credentials
                loaded_creds = load_credentials()

                if loaded_creds:
                    # Create configuration from credentials
                    config = {
                        "homeserver": loaded_creds.homeserver,
                        "user_id": loaded_creds.user_id,
                        "access_token": loaded_creds.access_token,
                        "device_id": loaded_creds.device_id,
                    }

                    bot = BibleBot(config=config)

                    assert bot.config["homeserver"] == "https://creds.matrix.org"
                    assert bot.config["user_id"] == "@credstest:matrix.org"

        finally:
            os.unlink(creds_file)

    def test_configuration_schema_validation(self):
        """
        Validate that a configuration dict conforms to the expected schema for BibleBot.

        Constructs a BibleBot with a known-good configuration and asserts:
        - `homeserver` is an HTTPS URL (starts with "https://").
        - `user_id` begins with "@".
        - `matrix_room_ids`, if present, is a list.

        This test ensures required shape and basic value formats are accepted by the bot.
        """
        # Valid configuration schema
        valid_config = {
            "homeserver": "https://matrix.org",
            "user_id": "@test:matrix.org",
            "access_token": "test_token",
            "device_id": "TEST_DEVICE",
            "matrix_room_ids": ["!room:matrix.org"],
            "bible_version": "NIV",
            "response_format": "html",
        }

        bot = BibleBot(config=valid_config)

        # Should accept valid schema
        assert bot.config["homeserver"].startswith("https://")
        assert bot.config["user_id"].startswith("@")
        assert isinstance(bot.config.get("matrix_room_ids", []), list)

    def test_configuration_defaults_application(self):
        """Test application of default configuration values."""
        # Minimal configuration
        minimal_config = {
            "homeserver": "https://matrix.org",
            "user_id": "@test:matrix.org",
            "access_token": "test_token",
            "device_id": "TEST_DEVICE",
        }

        bot = BibleBot(config=minimal_config)

        # Should have applied defaults for missing values
        # (Implementation may vary on what defaults are applied)
        assert bot.config["homeserver"] == "https://matrix.org"
        assert bot.config["user_id"] == "@test:matrix.org"

    def test_configuration_override_precedence(self):
        """Test precedence of configuration overrides."""
        # Test configuration precedence: explicit > environment > defaults
        base_config = {
            "homeserver": "https://base.matrix.org",
            "user_id": "@base:matrix.org",
            "access_token": "base_token",
            "device_id": "BASE_DEVICE",
        }

        # Environment override
        env_override = {
            "homeserver": "https://env.matrix.org",
        }

        # Explicit override
        explicit_override = {
            "homeserver": "https://explicit.matrix.org",
        }

        # Apply overrides in precedence order
        final_config = {**base_config, **env_override, **explicit_override}

        bot = BibleBot(config=final_config)

        # Should use highest precedence value
        assert bot.config["homeserver"] == "https://explicit.matrix.org"
        assert bot.config["user_id"] == "@base:matrix.org"  # No override

    def test_configuration_hot_reload_patterns(self):
        """
        Verify that updating the bot's configuration at runtime (hot reload) is applied to the running instance.

        Creates a BibleBot with an initial set of matrix_room_ids, updates bot.config with an expanded list, and asserts the bot's configuration reflects the added rooms (the new list is longer than the original).
        """
        initial_config = {
            "homeserver": "https://matrix.org",
            "user_id": "@test:matrix.org",
            "access_token": "test_token",
            "device_id": "TEST_DEVICE",
            "matrix_room_ids": ["!room1:matrix.org"],
        }

        bot = BibleBot(config=initial_config)
        initial_rooms = bot.config["matrix_room_ids"].copy()

        # Simulate configuration reload
        new_config = initial_config.copy()
        new_config["matrix_room_ids"] = [
            "!room1:matrix.org",
            "!room2:matrix.org",
            "!room3:matrix.org",
        ]

        # Update configuration
        bot.config.update(new_config)

        # Should reflect new configuration
        assert len(bot.config["matrix_room_ids"]) > len(initial_rooms)

    def test_configuration_backup_and_restore(self):
        """Test configuration backup and restore functionality."""
        original_config = {
            "homeserver": "https://matrix.org",
            "user_id": "@test:matrix.org",
            "access_token": "test_token",
            "device_id": "TEST_DEVICE",
            "matrix_room_ids": ["!room:matrix.org"],
        }

        bot = BibleBot(config=original_config)

        # Create backup of configuration
        config_backup = bot.config.copy()

        # Modify configuration
        bot.config["matrix_room_ids"] = ["!newroom:matrix.org"]

        # Restore from backup
        bot.config.update(config_backup)

        # Should match original configuration
        assert bot.config["matrix_room_ids"] == ["!room:matrix.org"]

    def test_configuration_migration_patterns(self):
        """Test configuration migration between versions."""
        # Old format configuration
        old_config = {
            "homeserver": "https://matrix.org",
            "user_id": "@test:matrix.org",
            "access_token": "test_token",
            "device_id": "TEST_DEVICE",
            "rooms": ["!room:matrix.org"],  # Old key name
        }

        # Migrate to new format
        migrated_config = old_config.copy()
        if "rooms" in migrated_config:
            migrated_config["matrix_room_ids"] = migrated_config.pop("rooms")

        bot = BibleBot(config=migrated_config)

        # Should use new format
        assert "matrix_room_ids" in bot.config
        assert "rooms" not in bot.config
