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
        res = importlib.resources.files("biblebot.tools") / SAMPLE_CONFIG_FILENAME
        import shutil
        import tempfile

        with importlib.resources.as_file(res) as p:
            # Copy to a permanent temporary file since as_file() may delete the original
            temp_fd, temp_path = tempfile.mkstemp(suffix=f"_{SAMPLE_CONFIG_FILENAME}")
            try:
                with open(temp_fd, "wb") as temp_file:
                    with open(p, "rb") as source_file:
                        shutil.copyfileobj(source_file, temp_file)
                return temp_path
            except:
                import os

                os.unlink(temp_path)
                raise
    except AttributeError:
        return str(pathlib.Path(__file__).parent / SAMPLE_CONFIG_FILENAME)


def get_service_template_path():
    """
    Return the filesystem path to the packaged service template file as a string.
    Attempts to resolve the resource using importlib.resources.files (Python 3.9+). If that API is unavailable, falls back to locating "biblebot.service" relative to this module's file.
    """
    try:
        res = importlib.resources.files("biblebot.tools") / "biblebot.service"
        import shutil
        import tempfile

        with importlib.resources.as_file(res) as p:
            # Copy to a permanent temporary file since as_file() may delete the original
            temp_fd, temp_path = tempfile.mkstemp(suffix="_biblebot.service")
            try:
                with open(temp_fd, "wb") as temp_file:
                    with open(p, "rb") as source_file:
                        shutil.copyfileobj(source_file, temp_file)
                return temp_path
            except:
                import os

                os.unlink(temp_path)
                raise
    except AttributeError:
        return str(pathlib.Path(__file__).parent / "biblebot.service")
