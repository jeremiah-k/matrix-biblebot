"""
Constants package for BibleBot.

This package follows the mmrelay pattern of organizing constants into
separate files by category. This __init__.py re-exports a subset of
the most commonly used constants for convenience, allowing for imports
like `from biblebot.constants import APP_NAME`.
"""

# Note: __all__ is intentionally omitted to avoid ruff F405 warnings with star imports
# All constants are re-exported via star imports from individual modules

# ruff: noqa: F403
from .api import *
from .app import *
from .bible import *
from .config import *
from .logging import *
from .matrix import *
from .messages import *
from .system import *
from .update import *
