"""Tests for update check functionality."""

from unittest.mock import patch

import pytest

from biblebot.log_utils import configure_component_loggers
from biblebot.update_check import (
    check_for_updates,
    compare_versions,
    perform_startup_update_check,
    print_startup_banner,
)


class TestUpdateCheck:
    """Test cases for update check functionality."""

    @pytest.mark.parametrize(
        "current,latest,expected",
        [("1.0.0", "1.1.0", True), ("1.0.0", "2.0.0", True), ("1.0.0", "1.0.1", True)],
    )
    def test_compare_versions_update_available(self, current, latest, expected):
        """Test version comparison when update is available."""
        assert compare_versions(current, latest) is expected

    def test_compare_versions_no_update(self):
        """Test version comparison when no update is available."""
        assert compare_versions("1.1.0", "1.0.0") is False
        assert compare_versions("1.0.0", "1.0.0") is False
        assert compare_versions("2.0.0", "1.9.9") is False

    def test_compare_versions_invalid(self):
        """Test version comparison with invalid version strings."""
        assert compare_versions("invalid", "1.0.0") is False
        assert compare_versions("1.0.0", "invalid") is False

    @pytest.mark.asyncio
    async def test_check_for_updates_available(self):
        """Test check_for_updates when update is available."""

        async def mock_get_latest():
            """
            Coroutine that simulates fetching the latest release version for tests.

            Always returns the string "1.1.0".
            Returns:
                str: The mocked latest version ("1.1.0").
            """
            return "1.1.0"

        with patch(
            "biblebot.update_check.get_latest_release_version",
            side_effect=mock_get_latest,
        ):
            with patch("biblebot.update_check.__version__", "1.0.0"):
                update_available, latest_version = await check_for_updates()
                assert update_available is True
                assert latest_version == "1.1.0"

    @pytest.mark.asyncio
    async def test_check_for_updates_not_available(self):
        """Test check_for_updates when no update is available."""

        async def mock_get_latest():
            """
            Async test helper that simulates retrieving the latest release version.

            Returns:
                str: A semantic version string ("1.0.0") used by tests to represent the latest available release.
            """
            return "1.0.0"

        with patch(
            "biblebot.update_check.get_latest_release_version",
            side_effect=mock_get_latest,
        ):
            with patch("biblebot.update_check.__version__", "1.1.0"):
                update_available, latest_version = await check_for_updates()
                assert update_available is False
                assert latest_version == "1.0.0"

    @pytest.mark.asyncio
    async def test_check_for_updates_api_failure(self):
        """Test check_for_updates when API call fails."""

        async def mock_get_latest():
            """
            Async test stub that simulates failure to retrieve the latest release version.

            Returns:
                None: Indicates no version was obtained (e.g., API failure or no release found).
            """
            return None

        with patch(
            "biblebot.update_check.get_latest_release_version",
            side_effect=mock_get_latest,
        ):
            update_available, latest_version = await check_for_updates()
            assert update_available is False
            assert latest_version is None

    @pytest.mark.asyncio
    async def test_perform_startup_update_check_no_exception(self):
        """Test startup update check runs without exceptions."""

        async def mock_check_for_updates():
            """
            Async test helper that simulates an update check returning no update and a fixed latest version.

            Returns:
                tuple: (update_available, latest_version) where `update_available` is False and
                `latest_version` is the string "1.0.0".
            """
            return False, "1.0.0"

        with patch(
            "biblebot.update_check.check_for_updates",
            side_effect=mock_check_for_updates,
        ):
            # Should not raise any exceptions
            await perform_startup_update_check()

    def test_print_startup_banner(self):
        """Test startup banner prints version information."""
        # Use mock to verify the logger.info call - more reliable than caplog/capsys
        with patch("biblebot.update_check.logger.info") as mock_info:
            print_startup_banner()
            mock_info.assert_called_once()
            call_args = mock_info.call_args[0][0]
            assert "Starting BibleBot version" in call_args

    def test_configure_component_loggers(self):
        """Test component logger configuration."""
        # Test that the function runs without error
        configure_component_loggers()

        # The function should complete without raising exceptions
        # (Actual logger configuration depends on loaded config)
