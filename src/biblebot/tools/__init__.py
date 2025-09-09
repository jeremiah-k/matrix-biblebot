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
    Context manager that yields a real filesystem Path to the bundled sample configuration file.

    Yields:
        pathlib.Path: A Path pointing to the packaged sample config file. The returned path is guaranteed
        to refer to an actual file on the host filesystem only for the duration of the context; do not
        use it after exiting the context. Prefer this context manager over retrieving a raw path string
        from the package (which may be ephemeral under certain installation formats).
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
    Copy the bundled sample configuration file to the given destination and return the path to the copied file.

    If dst_path points to an existing directory or has no suffix, the sample filename is appended. The destination directory is created if necessary. Returns a filesystem path to the copied file (stable on zipped installs because the resource is copied out).
    Parameters:
        dst_path (str): Destination file path or directory where the sample config should be placed.
    Returns:
        str: Filesystem path to the copied sample configuration file.
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
    Yield a temporary filesystem Path to the packaged `biblebot.service` template.

    Yields:
        pathlib.Path: A Path pointing to the bundled `biblebot.service` file that is guaranteed
        to exist and be usable only for the lifetime of the context manager. The path may
        be ephemeral (e.g., a temporary file) and should not be relied on after exiting the
        context.
    """
    res = importlib.resources.files(__package__) / "biblebot.service"
    with importlib.resources.as_file(res) as p:
        yield pathlib.Path(p)


def get_service_template_path():
    """
    Return the filesystem path to the packaged service template file as a string.

    .. deprecated::
        Under zipped installs this may be ephemeral. Prefer copy_service_template_to()
        or open_service_template().
    """
    warnings.warn(
        "get_service_template_path() may return ephemeral paths under zipped installs. "
        "Use copy_service_template_to() or open_service_template() instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    res = importlib.resources.files(__package__) / "biblebot.service"
    with importlib.resources.as_file(res) as p:
        return str(p)


def copy_service_template_to(dst_path: str) -> str:
    """
    Copy the packaged service template ("biblebot.service") to a filesystem destination and return the final file path as a string.

    If dst_path names an existing directory, or if it has no suffix, the function will place the service template inside that directory using the filename "biblebot.service". Parent directories are created as needed. The returned string is the path to the copied file on the local filesystem.
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
