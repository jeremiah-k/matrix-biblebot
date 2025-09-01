"""Tools and resources for BibleBot."""

import importlib.resources
import pathlib

from ..constants import SAMPLE_CONFIG_FILENAME


def get_sample_config_path():
    """
    Return the filesystem path to the bundled sample configuration file as a string.
    Uses importlib.resources.files (Python 3.9+) to locate the resource; on older Python versions falls back to the package file location next to this module. The returned path points to the resource named by SAMPLE_CONFIG_FILENAME.
    """
    try:
        # For Python 3.9+
        return str(importlib.resources.files("biblebot.tools") / SAMPLE_CONFIG_FILENAME)
    except AttributeError:
        # Fallback for older Python versions
        return str(pathlib.Path(__file__).parent / SAMPLE_CONFIG_FILENAME)


def get_service_template_path():
    """
    Return the filesystem path to the packaged service template file as a string.
    Attempts to resolve the resource using importlib.resources.files (Python 3.9+). If that API is unavailable, falls back to locating "biblebot.service" relative to this module's file.
    """
    try:
        # For Python 3.9+
        return str(importlib.resources.files("biblebot.tools") / "biblebot.service")
    except AttributeError:
        # Fallback for older Python versions
        return str(pathlib.Path(__file__).parent / "biblebot.service")
