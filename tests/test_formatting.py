"""Tests for pure message formatting and length-budget helpers."""

from biblebot.constants.messages import (
    FALLBACK_MESSAGE_TOO_LONG,
    MESSAGE_SUFFIX,
    REFERENCE_SEPARATOR_LEN,
)
from biblebot.formatting import (
    format_text_for_display,
    split_text_into_chunks,
    trim_reference_for_suffix,
)


def test_format_text_for_display_preserves_poetry_structure():
    plain, formatted = format_text_for_display(
        "  Blessed   is\tthe one\n\n\n<who walks>  ", preserve_poetry=True
    )

    assert plain == "Blessed is the one\n\n<who walks>"
    assert formatted == "Blessed is the one<br /><br />&lt;who walks&gt;"


def test_format_text_for_display_collapses_default_whitespace():
    plain, formatted = format_text_for_display(
        " Blessed\n\t is   <true> ", preserve_poetry=False
    )

    assert plain == "Blessed is <true>"
    assert formatted == "Blessed is &lt;true&gt;"


def test_split_text_into_chunks_prefers_word_boundaries():
    assert split_text_into_chunks("alpha beta gamma", max_length=10) == [
        "alpha beta",
        "gamma",
    ]


def test_trim_reference_for_suffix_uses_available_budget():
    max_length = len(MESSAGE_SUFFIX) + REFERENCE_SEPARATOR_LEN + 1 + 5

    assert (
        trim_reference_for_suffix("abcdefgh", max_message_length=max_length) == "ab..."
    )


def test_trim_reference_for_suffix_handles_boundary_budgets():
    separator_and_suffix = len(MESSAGE_SUFFIX) + REFERENCE_SEPARATOR_LEN

    assert trim_reference_for_suffix(None, max_message_length=100) is None
    assert trim_reference_for_suffix("John 3:16", max_message_length=100) == "John 3:16"
    assert (
        trim_reference_for_suffix("John", max_message_length=separator_and_suffix)
        is None
    )
    assert (
        trim_reference_for_suffix(
            "John",
            max_message_length=separator_and_suffix + 1 + 3,
        )
        is None
    )
    assert (
        trim_reference_for_suffix(
            "John 3:16",
            max_message_length=separator_and_suffix + len(FALLBACK_MESSAGE_TOO_LONG),
            reserve_fallback_space=True,
        )
        is None
    )
