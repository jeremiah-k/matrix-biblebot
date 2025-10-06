"""Community plugin shim for running BibleBot inside mmrelay."""

from __future__ import annotations

import pathlib
import sys
from importlib import import_module
from typing import Type


def _maybe_clear_foreign_biblebot(src_dir: pathlib.Path) -> None:
    """Ensure previously imported third-party biblebot modules do not shadow ours."""

    existing = sys.modules.get("biblebot")
    if not existing:
        return

    module_file = getattr(existing, "__file__", "")
    try:
        module_path = pathlib.Path(module_file).resolve()
    except (OSError, RuntimeError, ValueError):
        module_path = None

    if module_path and src_dir in module_path.parents:
        return

    for name in list(sys.modules):
        if name == "biblebot" or name.startswith("biblebot."):
            sys.modules.pop(name, None)


def _import_plugin() -> Type:
    """Import the packaged plugin, falling back to local src when necessary."""

    try:
        module = import_module("biblebot.integrations.mmrelay")
        return module.Plugin
    except ModuleNotFoundError:  # pragma: no cover - exercised inside mmrelay
        repo_root = pathlib.Path(__file__).resolve().parent
        src_dir = repo_root / "src"
        if src_dir.exists():
            sys.path.insert(0, str(src_dir))
        _maybe_clear_foreign_biblebot(src_dir)
        module = import_module("biblebot.integrations.mmrelay")
        return module.Plugin


Plugin = _import_plugin()

__all__ = ["Plugin"]
