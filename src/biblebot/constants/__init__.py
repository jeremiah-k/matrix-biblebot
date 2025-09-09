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
from . import logging as _const_logging
from . import matrix as _matrix
from . import messages as _messages
from . import system as _system
from . import update as _update


class DuplicateConstantError(NameError):
    """Raised when duplicate constants are found during import."""

    def __init__(self, duplicates):
        """
        Exception raised when two or more constants share the same name across submodules.

        Duplicates provided are converted to a tuple and stored on the instance as `self.duplicates`; the exception message includes that tuple.

        Parameters:
            duplicates (Iterable[str]): Iterable of duplicate constant names.
        """
        self.duplicates = tuple(duplicates)
        super().__init__(
            f"Duplicate constants found in biblebot.constants: {self.duplicates}"
        )


_modules = (
    _api,
    _app,
    _bible,
    _config,
    _const_logging,
    _matrix,
    _messages,
    _system,
    _update,
)
_missing_all = [
    getattr(m, "__name__", str(m)) for m in _modules if not hasattr(m, "__all__")
]
if _missing_all:
    raise ImportError(
        f"Each constants submodule must define __all__; missing: {_missing_all}"
    )
_exported = [name for m in _modules for name in getattr(m, "__all__", [])]
__all__ = ("DuplicateConstantError", *_exported)

# Verify that there are no duplicate constants being exported.
if len(__all__) != len(set(__all__)):
    counts = Counter(__all__)
    duplicates = [name for name, count in counts.items() if count > 1]
    raise DuplicateConstantError(sorted(duplicates))

# Import all constants from submodules (after validation)
from .api import *  # noqa: F403, E402
from .app import *  # noqa: F403, E402
from .bible import *  # noqa: F403, E402
from .config import *  # noqa: F403, E402
from .logging import *  # noqa: F403, E402
from .matrix import *  # noqa: F403, E402
from .messages import *  # noqa: F403, E402
from .system import *  # noqa: F403, E402
from .update import *  # noqa: F403, E402
