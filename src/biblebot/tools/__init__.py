"""Tools and resources for BibleBot."""

import importlib.resources
import pathlib
import shutil
import warnings
from contextlib import contextmanager

from biblebot.constants import SAMPLE_CONFIG_FILENAME


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

    .. deprecated::
        This function may return ephemeral paths under zipped installs.
        Use copy_sample_config_to() or open_sample_config() instead.
    """
    warnings.warn(
        "get_sample_config_path() may return ephemeral paths under zipped installs. "
        "Use copy_sample_config_to() or open_sample_config() instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    res = importlib.resources.files(__package__) / SAMPLE_CONFIG_FILENAME
    # Caller should prefer copy_sample_config_to(); this path may be ephemeral.
    with importlib.resources.as_file(res) as p:
        return str(p)


def copy_sample_config_to(dst_path: str) -> str:
    """
    Copy the bundled sample configuration to dst_path and return the actual file path.
    Always yields a stable file even under zipped installs.
    """
    res = importlib.resources.files(__package__) / SAMPLE_CONFIG_FILENAME
    dst = pathlib.Path(dst_path)
    # If dst is an existing dir or a path without a suffix, treat as directory
    if dst.exists() and dst.is_dir():
        dst = dst / SAMPLE_CONFIG_FILENAME
    elif dst.suffix == "":
        dst = dst / SAMPLE_CONFIG_FILENAME
    with importlib.resources.as_file(res) as p:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, dst)
    return str(dst)


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
    Copy the packaged service template to dst_path and return the actual file path.
    """
    filename = "biblebot.service"
    res = importlib.resources.files(__package__) / filename
    dst = pathlib.Path(dst_path)
    if dst.exists() and dst.is_dir():
        dst = dst / filename
    elif dst.suffix == "":
        dst = dst / filename
    with importlib.resources.as_file(res) as p:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, dst)
    return str(dst)
