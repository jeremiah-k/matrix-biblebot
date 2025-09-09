"""Tests for the tools module."""

import os
import stat
import warnings
from pathlib import Path
from unittest.mock import patch

import pytest

from biblebot import tools


def _get_sample_config_path_no_warnings():
    """
    Return the sample configuration file path while suppressing DeprecationWarning.

    This test helper calls tools.get_sample_config_path() inside a warnings context that ignores DeprecationWarning so tests don't fail or emit noise when the underlying API is deprecated.

    Returns:
        str: Path to the sample configuration file (as returned by tools.get_sample_config_path()).
    """
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        return tools.get_sample_config_path()


class TestSampleFilePaths:
    """Test sample file path functions."""

    def test_get_sample_config_path(self):
        """Test getting sample config path."""
        path_str = _get_sample_config_path_no_warnings()
        path = Path(path_str)

        assert path.name == "sample_config.yaml"
        assert path.exists()
        assert path.is_file()

    def test_sample_config_content(self):
        """Test that sample config contains expected content."""
        path_str = _get_sample_config_path_no_warnings()
        path = Path(path_str)
        content = path.read_text()

        # Check for key configuration sections
        assert "room_ids" in content  # New nested structure
        assert "biblebot auth login" in content  # Should mention auth flow

        # Check for API keys section
        assert "api_keys" in content
        assert "esv" in content


class TestPackageStructure:
    """Test package structure and file locations."""

    def test_tools_module_location(self):
        """Test that tools module is in correct location."""
        tools_file = Path(tools.__file__)

        assert tools_file.name == "__init__.py"  # tools is a package
        assert "biblebot" in str(tools_file)
        assert "tools" in str(tools_file)

    def test_sample_files_in_package(self):
        """Test that sample files are included in package."""
        # Get the package directory
        package_dir = Path(tools.__file__).parent

        # Check for sample config file (no longer includes .env)
        sample_config = package_dir / "sample_config.yaml"

        assert sample_config.exists(), f"Sample config not found at {sample_config}"


class TestFilePermissions:
    """Test file permissions and security."""

    def test_sample_files_readable(self):
        """Test that sample files are readable."""
        config_path_str = _get_sample_config_path_no_warnings()
        config_path = Path(config_path_str)

        # Should be able to read the config file
        assert config_path.is_file()

        # Should be able to read content
        config_content = config_path.read_text()

        assert len(config_content) > 0

    @pytest.mark.skipif(
        os.name == "nt", reason="Unix permissions not applicable on Windows"
    )
    def test_sample_files_permissions(self):
        """Test that sample files have appropriate permissions."""
        config_path_str = _get_sample_config_path_no_warnings()
        config_path = Path(config_path_str)

        # Get file permissions
        config_stat = config_path.stat()

        # Should be readable by owner (minimum requirement)
        assert config_stat.st_mode & stat.S_IRUSR  # Owner read

        # Should not be world-writable (security concern)
        assert not (config_stat.st_mode & stat.S_IWOTH)  # No other write

        # Note: Group write permission is acceptable for package files
        # as it's common in development environments


class TestSampleConfigValidation:
    """Test that sample config is valid YAML and contains required fields."""

    def test_sample_config_valid_yaml(self):
        """Test that sample config is valid YAML."""
        import yaml

        config_path_str = _get_sample_config_path_no_warnings()

        try:
            with open(config_path_str, "r") as f:
                config = yaml.safe_load(f)

            assert isinstance(config, dict)

        except yaml.YAMLError as e:
            pytest.fail(f"Sample config is not valid YAML: {e}")

    def test_sample_config_required_fields(self):
        """Test that sample config contains all required fields."""
        import yaml

        config_path_str = _get_sample_config_path_no_warnings()

        with open(config_path_str, "r") as f:
            config = yaml.safe_load(f)

        # Check required fields (matrix_homeserver and matrix_user now handled by auth)
        # Check for new nested structure
        assert (
            "matrix" in config
        ), "Required 'matrix' section missing from sample config"
        assert (
            "room_ids" in config["matrix"]
        ), "Required 'matrix.room_ids' field missing from sample config"

        # Check that matrix.room_ids is a list
        assert isinstance(config["matrix"]["room_ids"], list)
        assert len(config["matrix"]["room_ids"]) > 0

    def test_sample_config_placeholder_values(self):
        """Test that sample config contains placeholder values."""
        import yaml

        config_path_str = _get_sample_config_path_no_warnings()

        with open(config_path_str, "r") as f:
            config = yaml.safe_load(f)

        # Should contain placeholder values that users need to replace
        room_ids = config.get("matrix", {}).get("room_ids", [])

        # Room IDs should be example values, not real ones
        assert len(room_ids) > 0, "Should have example room IDs"
        for room_id in room_ids:
            assert (
                "your" in room_id.lower()
                or "example" in room_id.lower()
                or room_id.startswith("!")
            ), f"Room ID '{room_id}' should be a placeholder value"


class TestErrorHandling:
    """Test error handling in tools module."""

    @patch("pathlib.Path.exists")
    def test_missing_sample_files_handling(self, mock_exists):
        """
        Verify that _get_sample_config_path_no_warnings() returns a path string containing "sample_config.yaml" even when the filesystem reports the sample file as missing.

        The test patches Path.exists (via the mock_exists fixture) to always return False and asserts the helper still returns a string path referencing the sample config file.
        """
        mock_exists.return_value = False

        # Should still return path even if file doesn't exist
        config_path_str = _get_sample_config_path_no_warnings()

        assert isinstance(config_path_str, str)
        assert "sample_config.yaml" in config_path_str


class TestIntegration:
    """Test integration with other modules."""

    def test_tools_importable_from_cli(self):
        """Test that tools module can be imported by CLI module."""
        try:
            from biblebot.cli import copy_sample_config_to

            # Should be able to import the function
            assert callable(copy_sample_config_to)

        except ImportError as e:
            pytest.fail(f"Could not import tools functions from CLI: {e}")

    def test_sample_files_usable_by_cli(self):
        """Test that sample config file can be used by CLI generate_config function."""
        import shutil
        import tempfile

        # Create temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Get sample config file path
            sample_config_str = _get_sample_config_path_no_warnings()
            sample_config = Path(sample_config_str)

            # Copy sample config file (simulating CLI generate_config)
            target_config = temp_path / "config.yaml"

            shutil.copy2(sample_config, target_config)

            # Verify file was copied successfully
            assert target_config.exists()

            # Verify content is preserved
            original_config = sample_config.read_text()
            copied_config = target_config.read_text()
            assert original_config == copied_config
