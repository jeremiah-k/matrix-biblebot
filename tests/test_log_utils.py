"""Tests for log_utils module."""

import logging
from pathlib import Path
from unittest.mock import patch

from biblebot import log_utils


class TestLogConfiguration:
    """Test log configuration functionality."""

    def test_configure_logging_default(self):
        """Test configure_logging with default config."""
        log_utils.configure_logging()

        # Check that config is set to None by default
        assert log_utils.config is None

    def test_configure_logging_with_config(self):
        """Test configure_logging with config dict."""
        test_config = {"logging": {"debug": {"matrix_nio": True}}}
        log_utils.configure_logging(test_config)

        # Check that config is stored
        assert log_utils.config == test_config

    def test_configure_component_debug_logging(self):
        """Test component debug logging configuration."""
        # This function should not raise errors
        log_utils.configure_component_debug_logging()

        # Call twice to ensure idempotence and no exceptions
        log_utils.configure_component_debug_logging()


class TestLogDirectory:
    """Test log directory functionality."""

    def test_get_log_dir(self):
        """Test getting log directory."""
        log_dir = log_utils.get_log_dir()
        assert isinstance(log_dir, Path)
        assert str(log_dir).endswith("logs")

    @patch("biblebot.auth.get_config_dir")
    def test_get_log_dir_with_mock(self, mock_get_config_dir):
        """Test get_log_dir with mocked config dir."""
        mock_get_config_dir.return_value = Path("/test/config")

        log_dir = log_utils.get_log_dir()
        assert str(log_dir) == "/test/config/logs"


class TestLoggerCreation:
    """Test logger creation functionality."""

    def test_get_logger_with_name(self):
        """Test getting logger with specific name."""
        logger = log_utils.get_logger("test_logger")
        assert logger.name == "test_logger"
        assert isinstance(logger, logging.Logger)

    def test_get_logger_has_handlers(self):
        """Test that created logger has handlers."""
        logger = log_utils.get_logger("test_with_handlers")
        # Should have at least a console handler
        assert len(logger.handlers) > 0


class TestLoggerErrorHandling:
    """Test error handling in logging utilities."""

    def test_configure_logging_with_none(self):
        """Test configure_logging with None config."""
        # Should not raise exception
        log_utils.configure_logging(None)
        assert log_utils.config is None

    @patch("logging.getLogger", side_effect=Exception("Logger error"))
    def test_get_logger_error_handling(self, _mock_get_logger):
        """Test get_logger propagates exceptions from logging.getLogger."""
        import pytest

        with pytest.raises(Exception, match="Logger error"):
            log_utils.get_logger("test")


class TestLogUtilsIntegration:
    """Test integration scenarios for log utilities."""

    def test_logging_integration_workflow(self):
        """Test complete logging setup workflow."""
        # Configure logging
        test_config = {"logging": {"debug": {"matrix_nio": False}}}
        log_utils.configure_logging(test_config)

        # Get a logger
        logger = log_utils.get_logger("integration_test")

        # Verify logger works
        assert logger.name == "integration_test"
        assert isinstance(logger, logging.Logger)

    def test_multiple_logger_creation(self):
        """Test creating multiple loggers."""
        logger1 = log_utils.get_logger("test1")
        logger2 = log_utils.get_logger("test2")

        assert logger1.name == "test1"
        assert logger2.name == "test2"
        assert logger1 is not logger2
