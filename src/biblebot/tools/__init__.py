"""Tools and resources for BibleBot."""

import importlib.resources
import pathlib
import shutil
from contextlib import contextmanager

from ..constants import SAMPLE_CONFIG_FILENAME


@contextmanager
def open_sample_config():
    """
    Yield a real filesystem Path to the bundled sample config for the duration
    of the context. Prefer this over get_sample_config_path().
    """
    res = importlib.resources.files(__package__) / SAMPLE_CONFIG_FILENAME
    with importlib.resources.as_file(res) as p:
        yield pathlib.Path(p)


def get_sample_config_path():
    """
    Return a filesystem path for the bundled sample config.
    WARNING: Under zipped installs this may be ephemeral. Prefer copy_sample_config_to().
    """
    res = importlib.resources.files(__package__) / SAMPLE_CONFIG_FILENAME
    # Caller should prefer copy_sample_config_to(); this path may be ephemeral.
    with importlib.resources.as_file(res) as p:
        return str(p)


def copy_sample_config_to(dst_path: str) -> str:
    """
    Copy the bundled sample configuration to dst_path and return dst_path.
    Always yields a stable file even under zipped installs.
    """
    res = importlib.resources.files(__package__) / SAMPLE_CONFIG_FILENAME
    with importlib.resources.as_file(res) as p:
        shutil.copy2(p, dst_path)
    return dst_path


@contextmanager
def open_service_template():
    """
    Yield a real filesystem Path to the packaged service template for the
    duration of the context.
    """
    res = importlib.resources.files(__package__) / "biblebot.service"
    with importlib.resources.as_file(res) as p:
        yield pathlib.Path(p)


def get_service_template_path():
    """
    Return the filesystem path to the packaged service template file as a string.
    WARNING: Under zipped installs this may be ephemeral. Prefer copy_service_template_to().
    """
    res = importlib.resources.files(__package__) / "biblebot.service"
    with importlib.resources.as_file(res) as p:
        return str(p)


def copy_service_template_to(dst_path: str) -> str:
    """
    Copy the packaged service template to dst_path and return dst_path.
    """
    res = importlib.resources.files(__package__) / "biblebot.service"
    with importlib.resources.as_file(res) as p:
        shutil.copy2(p, dst_path)
    return dst_path
