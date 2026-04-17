"""Trigger policy module for BibleBot.

Encapsulates scripture reference detection logic. The bot responds only when
the entire message is a valid scripture reference (direct-only mode).
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum

from biblebot.constants.bible import (
    REFERENCE_PATTERNS,
    TRIGGER_MODE_DIRECT_ONLY,
)
from biblebot.validation import validate_and_normalize_book_name


class TriggerMode(str, Enum):
    DIRECT_ONLY = TRIGGER_MODE_DIRECT_ONLY


class TriggerSource(str, Enum):
    DIRECT = "direct"


@dataclass(frozen=True)
class TriggerMatch:
    passage: str
    translation: str
    source: TriggerSource


def _match_reference(
    text: str,
    patterns: Sequence[re.Pattern],
    method: str,
    default_translation: str,
) -> tuple[str, str] | None:
    for pattern in patterns:
        match = getattr(pattern, method)(text)
        if not match:
            continue
        raw_book = match.group("book").strip()
        if not raw_book:
            continue
        book_name = validate_and_normalize_book_name(raw_book)
        if not book_name:
            continue
        verse_ref = match.group("ref").strip()
        passage = f"{book_name} {verse_ref}"
        trans_group = match.groupdict().get("translation")
        translation = trans_group.lower() if trans_group else default_translation
        return passage, translation
    return None


def _try_direct_match(body: str, default_translation: str) -> tuple[str, str] | None:
    return _match_reference(body, REFERENCE_PATTERNS, "fullmatch", default_translation)


def detect_trigger(
    body: str,
    formatted_body: str | None,
    trigger_mode: TriggerMode,
    command_prefix: str | None,
    bot_mxid: str | None,
    default_translation: str,
) -> TriggerMatch | None:
    if not body or not body.strip():
        return None

    result = _try_direct_match(body, default_translation)
    if result:
        return TriggerMatch(
            passage=result[0], translation=result[1], source=TriggerSource.DIRECT
        )
    return None
