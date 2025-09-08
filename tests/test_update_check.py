"""Tests for update check functionality."""

import logging
from unittest.mock import patch

import pytest

from biblebot.update_check import (
    check_for_updates,
    compare_versions,
    perform_startup_update_check,
    print_startup_banner,
    suppress_component_loggers,
)


class TestUpdateCheck:
    """Test cases for update check functionality."""

    def test_compare_versions_update_available(self):
        """Test version comparison when update is available."""
        assert compare_versions("1.0.0", "1.1.0") is True
        assert compare_versions("1.0.0", "2.0.0") is True
        assert compare_versions("1.0.0", "1.0.1") is True

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
            return False, "1.0.0"

        with patch(
            "biblebot.update_check.check_for_updates",
            side_effect=mock_check_for_updates,
        ):
            # Should not raise any exceptions
            await perform_startup_update_check()

    def test_print_startup_banner(self, caplog):
        """Test startup banner prints version information."""
        from biblebot.constants.app import LOGGER_NAME

        logger = logging.getLogger(LOGGER_NAME)
        logger.addHandler(caplog.handler)
        with caplog.at_level(logging.INFO):
            print_startup_banner()
            assert "Starting BibleBot version" in caplog.text

    def test_suppress_component_loggers(self):
        """Test component logger suppression."""
        import logging

        # Test that loggers get suppressed
        suppress_component_loggers()

        # Check that nio logger is suppressed
        nio_logger = logging.getLogger("nio")
        assert nio_logger.level == logging.CRITICAL + 1
