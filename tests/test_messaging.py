"""Tests for pure message-retry policy and final-chunk body composition."""

from __future__ import annotations

import html as _html
from unittest.mock import MagicMock

import pytest

from biblebot.constants.messages import MESSAGE_SUFFIX
from biblebot.messaging import (
    RetryPolicy,
    compose_final_chunk_bodies,
    is_error_response,
    is_rate_limit_response,
    remaining_retry_budget,
    response_retry_delay_seconds,
)


def _fake_error_response(status_code=None, retry_after_ms=None):
    from nio.responses import ErrorResponse

    return ErrorResponse(
        message="boom", status_code=status_code, retry_after_ms=retry_after_ms
    )


def test_is_error_response_detects_nio_error_response():
    from nio.responses import ErrorResponse

    assert is_error_response(ErrorResponse("limit exceeded", "M_LIMIT_EXCEEDED"))
    assert not is_error_response(MagicMock(spec=[]))
    assert not is_error_response(None)


def test_is_rate_limit_response_matches_errcode_and_status():
    assert is_rate_limit_response(_fake_error_response("M_LIMIT_EXCEEDED"))
    assert is_rate_limit_response(_fake_error_response(429))
    assert not is_rate_limit_response(_fake_error_response("M_UNKNOWN"))
    assert not is_rate_limit_response(None)


def test_is_rate_limit_response_checks_errcode_field_separately():
    """A M_LIMIT_EXCEEDED errcode is retriable even with a non-429 status."""
    resp = _fake_error_response(status_code=503)
    resp.errcode = "M_LIMIT_EXCEEDED"
    assert is_rate_limit_response(resp)


def test_remaining_retry_budget_clamps_to_max():
    assert remaining_retry_budget(0) == 0
    assert remaining_retry_budget(2) == 2
    assert remaining_retry_budget(99) == 3


def test_response_retry_delay_uses_server_hint_with_jitter():
    delay = response_retry_delay_seconds(
        _fake_error_response(retry_after_ms=2000), attempt=0, rng=lambda lo, hi: 1.0
    )
    assert delay == pytest.approx(2.0)


def test_response_retry_delay_falls_back_and_grows_with_attempts():
    rng = lambda lo, hi: 1.0
    first = response_retry_delay_seconds(_fake_error_response(), attempt=0, rng=rng)
    second = response_retry_delay_seconds(_fake_error_response(), attempt=2, rng=rng)
    assert first > 0
    assert second > first


def test_compose_final_chunk_bodies_with_reference():
    plain, rendered = compose_final_chunk_bodies(
        "For God so loved the world",
        "For God so loved the world",
        reference="John 3:16",
    )

    assert plain == f"For God so loved the world - John 3:16{MESSAGE_SUFFIX}"
    assert rendered == (
        f"For God so loved the world - John 3:16{_html.escape(MESSAGE_SUFFIX)}"
    )


def test_compose_final_chunk_bodies_without_reference():
    plain, rendered = compose_final_chunk_bodies(
        "For God so loved the world",
        "For God so loved the world",
        reference=None,
    )

    assert plain == f"For God so loved the world{MESSAGE_SUFFIX}"
    assert rendered == f"For God so loved the world{_html.escape(MESSAGE_SUFFIX)}"



def test_retry_policy_defaults_match_constants():
    policy = RetryPolicy()
    assert policy.max_attempts == 3
    assert policy.default_retry_after_ms == 1000
    assert policy.jitter_low == 0.8
    assert policy.jitter_high == 1.2
