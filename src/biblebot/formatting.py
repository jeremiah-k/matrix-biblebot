"""Pure helpers for rendering and sizing outbound Bible passage messages."""

from __future__ import annotations

import html
import re
import textwrap

from biblebot.constants.messages import (
    FALLBACK_MESSAGE_TOO_LONG,
    MESSAGE_SUFFIX,
    REFERENCE_SEPARATOR_LEN,
    TRUNCATION_INDICATOR,
)


def format_text_for_display(text: str, *, preserve_poetry: bool) -> tuple[str, str]:
    """Return normalized plain text and an HTML-safe representation."""
    if preserve_poetry:
        plain = re.sub(r"[ \t]+", " ", text)
        plain = re.sub(r"\n\s*\n", "\n\n", plain).strip()
        return plain, html.escape(plain).replace("\n", "<br />")

    plain = " ".join(text.replace("\n", " ").split())
    return plain, html.escape(plain)


def split_text_into_chunks(text: str, *, max_length: int) -> list[str]:
    """Split text at word boundaries when possible within a maximum length."""
    return textwrap.wrap(
        text,
        width=max_length,
        break_long_words=True,
        replace_whitespace=False,
        break_on_hyphens=True,
    )


def trim_reference_for_suffix(
    reference: str | None,
    *,
    max_message_length: int,
    reserve_fallback_space: bool = False,
) -> str | None:
    """Return a reference shortened to fit beside the standard message suffix."""
    if not reference:
        return None
    reserved_text_length = (
        len(FALLBACK_MESSAGE_TOO_LONG) if reserve_fallback_space else 1
    )
    budget = (
        max_message_length
        - len(MESSAGE_SUFFIX)
        - REFERENCE_SEPARATOR_LEN
        - reserved_text_length
    )
    if budget <= 0:
        return None
    if len(reference) <= budget:
        return reference
    if budget < len(TRUNCATION_INDICATOR):
        return None
    keep = budget - len(TRUNCATION_INDICATOR)
    return reference[:keep] + TRUNCATION_INDICATOR if keep > 0 else None
