"""Tools and resources for BibleBot."""

import importlib.resources
import pathlib


def get_sample_config_path():
    """Get the path to the sample config file."""
    try:
        # For Python 3.9+
        return str(importlib.resources.files("biblebot.tools") / "sample_config.yaml")
    except AttributeError:
        # Fallback for older Python versions
        return str(pathlib.Path(__file__).parent / "sample_config.yaml")


def get_sample_env_path():
    """Get the path to the sample .env file."""
    try:
        # For Python 3.9+
        return str(importlib.resources.files("biblebot.tools") / "sample.env")
    except AttributeError:
        # Fallback for older Python versions
        return str(pathlib.Path(__file__).parent / "sample.env")


def get_service_template_path():
    """Get the path to the service template file."""
    try:
        # For Python 3.9+
        return str(importlib.resources.files("biblebot.tools") / "biblebot.service")
    except AttributeError:
        # Fallback for older Python versions
        return str(pathlib.Path(__file__).parent / "biblebot.service")
