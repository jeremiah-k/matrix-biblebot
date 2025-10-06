"""Community plugin shim for running BibleBot inside mmrelay."""

from __future__ import annotations

import pathlib
import sys
from importlib import import_module


def _import_plugin() -> type:
    """Import the packaged plugin, falling back to local src when necessary."""

    try:
        return import_module("biblebot.integrations.mmrelay").Plugin
    except ModuleNotFoundError:  # pragma: no cover - exercised inside mmrelay
        repo_root = pathlib.Path(__file__).resolve().parent
        src_dir = repo_root / "src"
        if src_dir.exists():
            sys.path.insert(0, str(src_dir))
        return import_module("biblebot.integrations.mmrelay").Plugin


Plugin = _import_plugin()

__all__ = ["Plugin"]
