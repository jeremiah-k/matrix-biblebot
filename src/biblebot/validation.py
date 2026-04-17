"""Bible book name validation and normalization."""

from collections.abc import Mapping
from types import MappingProxyType

from biblebot.constants.app import CHAR_DOT
from biblebot.constants.bible import BOOK_ABBREVIATIONS

_ALL_NAMES_TO_CANONICAL: Mapping[str, str] = MappingProxyType(
    {
        **BOOK_ABBREVIATIONS,
        **{name.lower(): name for name in set(BOOK_ABBREVIATIONS.values())},
    }
)


def _clean_book_name(book_str: str) -> str:
    """Normalize a Bible book name string for canonical lookup.

    Lowercases the input, removes dot characters (CHAR_DOT), trims
    leading/trailing whitespace, and collapses consecutive internal
    whitespace into single spaces.

    Returns:
        The cleaned, space-separated, lower-case book name.
    """
    if not book_str or not book_str.strip():
        return ""
    return " ".join(book_str.lower().replace(CHAR_DOT, "").strip().split())


def validate_and_normalize_book_name(book_str: str) -> str | None:
    """Return the canonical full Bible book name for a user-supplied book
    string, or None if it is not recognized.

    Accepts common variants (abbreviations, punctuation, mixed case, and
    extra whitespace) and normalizes them before lookup.
    """
    if not book_str or not book_str.strip():
        return None
    clean_str = _clean_book_name(book_str)
    return _ALL_NAMES_TO_CANONICAL.get(clean_str)
