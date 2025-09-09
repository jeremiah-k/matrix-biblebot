"""
Constants package for BibleBot.

This package follows the mmrelay pattern of organizing constants into
separate files by category. This __init__.py re-exports the public constants
(union of submodule __all__) for convenience, allowing for imports
like `from biblebot.constants import APP_NAME`.
"""

from collections import Counter

# Build explicit export list from submodules, then re-export for convenience.
from . import api as _api
from . import app as _app
from . import bible as _bible
from . import config as _config
from . import logging as _logging
from . import matrix as _matrix
from . import messages as _messages
from . import system as _system
from . import update as _update

# Import all constants from submodules
from .api import *  # noqa: F403
from .app import *  # noqa: F403
from .bible import *  # noqa: F403
from .config import *  # noqa: F403
from .logging import *  # noqa: F403
from .matrix import *  # noqa: F403
from .messages import *  # noqa: F403
from .system import *  # noqa: F403
from .update import *  # noqa: F403


class DuplicateConstantError(NameError):
    """Raised when duplicate constants are found during import."""

    def __init__(self, duplicates):
        """
        Initialize the DuplicateConstantError with the given duplicate names.

        Parameters:
            duplicates (Iterable[str]): Names of constants that were found more than once; stored as a tuple on the instance.

        The exception message will include the tuple of duplicate names.
        """
        self.duplicates = tuple(duplicates)
        super().__init__(
            f"Duplicate constants found in biblebot.constants: {self.duplicates}"
        )


_modules = (_api, _app, _bible, _config, _logging, _matrix, _messages, _system, _update)
__all__ = tuple(name for m in _modules for name in getattr(m, "__all__", []))

# Verify that there are no duplicate constants being exported.
if len(__all__) != len(set(__all__)):
    counts = Counter(__all__)
    duplicates = [name for name, count in counts.items() if count > 1]
    raise DuplicateConstantError(sorted(duplicates))
