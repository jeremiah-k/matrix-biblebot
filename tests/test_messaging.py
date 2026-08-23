"""Tests for pure message-retry policy and final-chunk body composition."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

import html as _html

from biblebot.constants.messages import MESSAGE_SUFFIX
from biblebot.messaging import (
    RetryPolicy,
    compose_final_chunk_bodies,
    compute_retry_delay_seconds,
    is_rate_limit_error,
    remaining_retry_budget,
    should_retry_rate_limit,
)


@dataclass
class _FakeRateLimitError(Exception):
    status: int = 429
    retry_after_ms: int = 1000


def test_is_rate_limit_error_matches_matrix_429():
    assert is_rate_limit_error(_FakeRateLimitError())
    assert not is_rate_limit_error(_FakeRateLimitError(status=500))


def test_remaining_retry_budget_clamps_to_max():
    assert remaining_retry_budget(0) == 0
    assert remaining_retry_budget(2) == 2
    assert remaining_retry_budget(99) == 3


def test_should_retry_rate_limit_requires_budget_and_status():
    assert should_retry_rate_limit(1, _FakeRateLimitError())
    assert not should_retry_rate_limit(0, _FakeRateLimitError())
    assert not should_retry_rate_limit(1, _FakeRateLimitError(status=500))


def test_compute_retry_delay_seconds_uses_fixed_rng():
    delay = compute_retry_delay_seconds(
        retries_left=2, exc=_FakeRateLimitError(retry_after_ms=1000), rng=lambda lo, hi: 1.0
    )

    assert delay == pytest.approx(2.0)


def test_compute_retry_delay_seconds_grows_with_attempts():
    rng = lambda lo, hi: 1.0  # noqa: E731
    first = compute_retry_delay_seconds(retries_left=2, exc=_FakeRateLimitError(), rng=rng)
    second = compute_retry_delay_seconds(retries_left=1, exc=_FakeRateLimitError(), rng=rng)

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
