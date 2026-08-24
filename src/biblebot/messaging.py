"""Pure helpers for Matrix message-send error handling and final-chunk bodies."""

from __future__ import annotations

import html
import random
from typing import Final

from biblebot.constants.matrix import DEFAULT_RETRY_AFTER_MS
from biblebot.constants.messages import MESSAGE_SUFFIX

_RATE_LIMIT_STATUS: Final[int] = 429
_RATE_LIMIT_ERRCODE: Final[str] = "M_LIMIT_EXCEEDED"


def _has_message_attr(obj: object) -> bool:
    """Return True when *obj* looks like an nio Response (has ``message``)."""
    return hasattr(obj, "message")


def is_error_response(response: object) -> bool:
    """Return True when a client return value is an nio ``ErrorResponse``.

    ``nio.AsyncClient`` methods return ``ErrorResponse`` objects instead of
    raising for Matrix-level failures, so callers must inspect return values
    rather than catch exceptions.
    """
    from nio.responses import ErrorResponse  # deferred: keeps import cost local

    return isinstance(response, ErrorResponse)


def is_rate_limit_response(response: object) -> bool:
    """Return True when an ErrorResponse is a retriable rate-limit (429).

    Mirrors nio's own detection in ``AsyncClient._send``: the limit may be
    signalled by an integer 429 status or the ``M_LIMIT_EXCEEDED`` error
    code, on either the ``status_code`` or ``errcode`` attribute depending
    on how the response was constructed.
    """
    if response is None or not _has_message_attr(response):
        return False
    markers = (
        getattr(response, "status_code", None),
        getattr(response, "errcode", None),
    )
    return _RATE_LIMIT_STATUS in markers or _RATE_LIMIT_ERRCODE in markers


def response_retry_delay_seconds(
    response: object,
    *,
    attempt: int,
    rng=random.uniform,
) -> float:
    """Compute bounded-jitter backoff for one retry of a rate-limited send.

    Uses the server-provided ``retry_after_ms`` hint when present, falling
    back to the configured default; grows exponentially with ``attempt``.
    """
    retry_ms = getattr(response, "retry_after_ms", None)
    if not retry_ms:
        retry_ms = DEFAULT_RETRY_AFTER_MS
    base_delay = int(retry_ms) / 1000.0 * (2**attempt)
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


def classify_send_failure(response: object) -> str:
    """Return a short operator-friendly reason for a failed Matrix send.

    Maps the nio ``ErrorResponse`` errcode to one of ``"rate_limited"``,
    ``"forbidden"``, or ``"other"``. Unknown errcodes fall back to
    ``"other"`` so callers never have to handle an unmapped kind.
    """
    errcode = getattr(response, "errcode", None) or getattr(
        response, "status_code", None
    )
    if is_rate_limit_response(response):
        return "rate_limited"
    if errcode in ("M_FORBIDDEN", 403):
        return "forbidden"
    return "other"
