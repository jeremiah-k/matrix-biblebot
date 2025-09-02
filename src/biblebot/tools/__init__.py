"""Tools and resources for BibleBot."""

import importlib.resources
import pathlib

from ..constants import SAMPLE_CONFIG_FILENAME


def get_sample_config_path():
    """
    Return a filesystem path for the bundled sample config.
    WARNING: Under zipped installs this may be ephemeral. Prefer copy_sample_config_to().
    """
    try:
        res = importlib.resources.files("biblebot.tools") / SAMPLE_CONFIG_FILENAME
        # Caller should prefer copy_sample_config_to(); this path may be ephemeral.
        with importlib.resources.as_file(res) as p:
            return str(p)
    except AttributeError:
        return str(pathlib.Path(__file__).parent / SAMPLE_CONFIG_FILENAME)


def copy_sample_config_to(dst_path: str) -> str:
    """
    Copy the bundled sample configuration to dst_path and return dst_path.
    Always yields a stable file even under zipped installs.
    """
    import shutil

    try:
        res = importlib.resources.files("biblebot.tools") / SAMPLE_CONFIG_FILENAME
        with importlib.resources.as_file(res) as p:
            shutil.copy2(p, dst_path)
        return dst_path
    except AttributeError:
        src = pathlib.Path(__file__).parent / SAMPLE_CONFIG_FILENAME
        shutil.copy2(src, dst_path)
        return dst_path


def get_service_template_path():
    """
    Return the filesystem path to the packaged service template file as a string.
    WARNING: Under zipped installs this may be ephemeral. Prefer copy_service_template_to().
    """
    try:
        res = importlib.resources.files("biblebot.tools") / "biblebot.service"
        with importlib.resources.as_file(res) as p:
            return str(p)
    except AttributeError:
        return str(pathlib.Path(__file__).parent / "biblebot.service")


def copy_service_template_to(dst_path: str) -> str:
    """
    Copy the packaged service template to dst_path and return dst_path.
    """
    import shutil

    try:
        res = importlib.resources.files("biblebot.tools") / "biblebot.service"
        with importlib.resources.as_file(res) as p:
            shutil.copy2(p, dst_path)
        return dst_path
    except AttributeError:
        src = pathlib.Path(__file__).parent / "biblebot.service"
        shutil.copy2(src, dst_path)
        return dst_path
