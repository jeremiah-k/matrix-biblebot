"""Pure helpers for Matrix room identifier handling."""

from __future__ import annotations

from typing import Final

from biblebot.constants.config import CONFIG_KEY_MATRIX, CONFIG_MATRIX_ROOM_IDS
from biblebot.constants.matrix import _PLACEHOLDER_ROOM_IDS

_PLACEHOLDER_PREFIX: Final[str] = "!your_room_id:"
_PLACEHOLDER_SUFFIX: Final[str] = ":your_homeserver_domain"


def is_alias(value: str) -> bool:
    """Return True if a room identifier begins with the Matrix alias marker."""
    return isinstance(value, str) and value.startswith("#")


def is_placeholder_room_id(value: str) -> bool:
    """Return True if the value is a documented placeholder/sample room id."""
    if not isinstance(value, str):
        return False
    if value in _PLACEHOLDER_ROOM_IDS:
        return True
    return value.startswith(_PLACEHOLDER_PREFIX) or value.endswith(_PLACEHOLDER_SUFFIX)


def read_room_ids(config: dict) -> list[str]:
    """Return the configured room list, supporting nested and legacy schemas."""
    if not isinstance(config, dict):
        return []
    nested = config.get(CONFIG_KEY_MATRIX)
    if isinstance(nested, dict):
        nested_ids = nested.get("room_ids")
        if isinstance(nested_ids, list):
            return [str(item) for item in nested_ids if isinstance(item, str)]
    legacy = config.get(CONFIG_MATRIX_ROOM_IDS)
    if isinstance(legacy, list):
        return [str(item) for item in legacy if isinstance(item, str)]
    return []


def merge_resolved_entries(original: list[str], resolved: list[str]) -> list[str]:
    """Return a deduplicated, first-occurrence-preserving merged list."""
    merged: list[str] = []
    seen: set[str] = set()
    for entry in [*original, *resolved]:
        if not isinstance(entry, str) or entry in seen:
            continue
        seen.add(entry)
        merged.append(entry)
    return merged
