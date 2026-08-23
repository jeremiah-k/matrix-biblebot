"""Pure helpers for Matrix message-retry policy and final-chunk body composition."""

from __future__ import annotations

import html
import random
from dataclasses import dataclass
from typing import Final

from biblebot.constants.matrix import DEFAULT_RETRY_AFTER_MS, MAX_RATE_LIMIT_RETRIES
from biblebot.constants.messages import MESSAGE_SUFFIX


_RATE_LIMIT_STATUS: Final[int] = 429


def is_rate_limit_error(exc: BaseException) -> bool:
    """Return True when an exception represents a retriable Matrix rate-limit."""
    return getattr(exc, "status", None) == _RATE_LIMIT_STATUS


def remaining_retry_budget(retries_left: int) -> int:
    """Clamp a retry-remaining counter to the configured maximum."""
    return max(0, min(retries_left, MAX_RATE_LIMIT_RETRIES))


def should_retry_rate_limit(retries_left: int, exc: BaseException) -> bool:
    """Return True if a rate-limit error should trigger another retry attempt."""
    if retries_left <= 0:
        return False
    return is_rate_limit_error(exc)


def compute_retry_delay_seconds(
    retries_left: int, exc: BaseException, *, rng=random.uniform
) -> float:
    """Compute exponential backoff with bounded jitter for one retry attempt."""
    retry_ms = int(getattr(exc, "retry_after_ms", DEFAULT_RETRY_AFTER_MS))
    attempt_index = MAX_RATE_LIMIT_RETRIES - retries_left
    base_delay = retry_ms / 1000.0 * (2**attempt_index)
    return base_delay * rng(0.8, 1.2)


def compose_final_chunk_bodies(
    formatted_text: str,
    html_text: str,
    *,
    reference: str | None,
) -> tuple[str, str]:
    """Compose the plain and HTML bodies for the final message chunk."""
    if reference:
        plain = f"{formatted_text} - {reference}{MESSAGE_SUFFIX}"
        rendered = (
            f"{html_text} - {html.escape(reference)}{html.escape(MESSAGE_SUFFIX)}"
        )
    else:
        plain = f"{formatted_text}{MESSAGE_SUFFIX}"
        rendered = f"{html_text}{html.escape(MESSAGE_SUFFIX)}"
    return plain, rendered


@dataclass(frozen=True)
class RetryPolicy:
    """Immutable description of the message-retry policy used by send paths."""

    max_attempts: int = MAX_RATE_LIMIT_RETRIES
    default_retry_after_ms: int = DEFAULT_RETRY_AFTER_MS
    jitter_low: float = 0.8
    jitter_high: float = 1.2
