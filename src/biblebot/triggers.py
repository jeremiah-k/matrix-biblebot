"""Trigger policy module for BibleBot.

Encapsulates all scripture reference detection logic. The main entry point is
detect_trigger(), which takes message content and bot configuration and returns
a TriggerMatch when a valid reference is found, or None otherwise.
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum

from biblebot.constants.bible import (
    EMBEDDED_REFERENCE_PATTERNS,
    REFERENCE_PATTERNS,
    TRIGGER_MODE_ANYWHERE,
    TRIGGER_MODE_DIRECT_ONLY,
    TRIGGER_MODE_SMART,
)
from biblebot.validation import validate_and_normalize_book_name


class TriggerMode(str, Enum):
    DIRECT_ONLY = TRIGGER_MODE_DIRECT_ONLY
    SMART = TRIGGER_MODE_SMART
    ANYWHERE = TRIGGER_MODE_ANYWHERE


class TriggerSource(str, Enum):
    DIRECT = "direct"
    MENTION = "mention"
    PREFIX = "prefix"
    ANYWHERE = "anywhere"


@dataclass(frozen=True)
class TriggerMatch:
    passage: str
    translation: str
    source: TriggerSource


_MENTION_LINK_RE = re.compile(
    r'<a\s+href="https?://matrix\.to/#/(?P<mxid>@[^"]+)"[^>]*>.*?</a>'
)

_MENTION_BOUNDARY_RE = re.compile(r"^[\s\W]|$")


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


def _try_embedded_match(body: str, default_translation: str) -> tuple[str, str] | None:
    return _match_reference(
        body, EMBEDDED_REFERENCE_PATTERNS, "search", default_translation
    )


def _try_prefix_match(
    body: str, prefix: str, default_translation: str
) -> tuple[str, str] | None:
    if not prefix:
        return None
    if not body.startswith(prefix):
        return None
    remainder = body[len(prefix) :].strip()
    if not remainder:
        return None
    return _try_direct_match(remainder, default_translation)


def _extract_mention_body(
    body: str, formatted_body: str | None, bot_mxid: str | None
) -> str | None:
    if not bot_mxid:
        return None

    if formatted_body:
        for m in _MENTION_LINK_RE.finditer(formatted_body):
            if m.group("mxid") == bot_mxid:
                link_text = m.group(0)
                plain = re.sub(r"<[^>]+>", "", link_text).strip()
                if plain and plain in body:
                    idx = body.index(plain)
                    remainder = (body[:idx] + body[idx + len(plain) :]).strip()
                    if remainder:
                        return remainder
                return None

    localpart = bot_mxid.lstrip("@").split(":")[0]
    candidates = [bot_mxid, f"@{localpart}"]

    for candidate in candidates:
        if not body.startswith(candidate):
            continue
        after = body[len(candidate) :]
        if not after:
            return None
        if not _MENTION_BOUNDARY_RE.match(after):
            continue
        remainder = after.strip()
        if remainder:
            return remainder
        return None

    return None


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

    if trigger_mode == TriggerMode.DIRECT_ONLY:
        result = _try_direct_match(body, default_translation)
        if result:
            return TriggerMatch(
                passage=result[0], translation=result[1], source=TriggerSource.DIRECT
            )
        return None

    if trigger_mode == TriggerMode.SMART:
        result = _try_direct_match(body, default_translation)
        if result:
            return TriggerMatch(
                passage=result[0], translation=result[1], source=TriggerSource.DIRECT
            )

        if command_prefix:
            result = _try_prefix_match(body, command_prefix, default_translation)
            if result:
                return TriggerMatch(
                    passage=result[0],
                    translation=result[1],
                    source=TriggerSource.PREFIX,
                )

        mention_body = _extract_mention_body(body, formatted_body, bot_mxid)
        if mention_body:
            result = _try_direct_match(mention_body, default_translation)
            if result:
                return TriggerMatch(
                    passage=result[0],
                    translation=result[1],
                    source=TriggerSource.MENTION,
                )

        return None

    if trigger_mode == TriggerMode.ANYWHERE:
        result = _try_direct_match(body, default_translation)
        if result:
            return TriggerMatch(
                passage=result[0], translation=result[1], source=TriggerSource.DIRECT
            )

        if command_prefix:
            result = _try_prefix_match(body, command_prefix, default_translation)
            if result:
                return TriggerMatch(
                    passage=result[0],
                    translation=result[1],
                    source=TriggerSource.PREFIX,
                )

        mention_body = _extract_mention_body(body, formatted_body, bot_mxid)
        if mention_body:
            result = _try_direct_match(mention_body, default_translation)
            if result:
                return TriggerMatch(
                    passage=result[0],
                    translation=result[1],
                    source=TriggerSource.MENTION,
                )

        result = _try_embedded_match(body, default_translation)
        if result:
            return TriggerMatch(
                passage=result[0], translation=result[1], source=TriggerSource.ANYWHERE
            )

        return None

    return None
