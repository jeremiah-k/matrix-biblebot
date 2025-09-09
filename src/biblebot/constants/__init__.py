"""
Constants package for BibleBot.

This package follows the mmrelay pattern of organizing constants into
separate files by category. This __init__.py re-exports a subset of
the most commonly used constants for convenience, allowing for imports
like `from biblebot.constants import APP_NAME`.
"""

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

__all__ = []
__all__ += getattr(_api, "__all__", [])
__all__ += getattr(_app, "__all__", [])
__all__ += getattr(_bible, "__all__", [])
__all__ += getattr(_config, "__all__", [])
__all__ += getattr(_logging, "__all__", [])
__all__ += getattr(_matrix, "__all__", [])
__all__ += getattr(_messages, "__all__", [])
__all__ += getattr(_system, "__all__", [])
__all__ += getattr(_update, "__all__", [])

# Verify that there are no duplicate constants being exported.
if len(__all__) != len(set(__all__)):
    from collections import Counter

    counts = Counter(__all__)
    duplicates = [name for name, count in counts.items() if count > 1]
    raise NameError(f"Duplicate constants found in biblebot.constants: {duplicates}")

from .api import *  # noqa: F403, E402
from .app import *  # noqa: F403, E402
from .bible import *  # noqa: F403, E402
from .config import *  # noqa: F403, E402
from .logging import *  # noqa: F403, E402
from .matrix import *  # noqa: F403, E402
from .messages import *  # noqa: F403, E402
from .system import *  # noqa: F403, E402
from .update import *  # noqa: F403, E402
