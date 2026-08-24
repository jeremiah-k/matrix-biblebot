"""Response-based send handling in BibleBot._send_message_parts.

nio's ``AsyncClient.room_send`` does not raise for Matrix-level errors: it
returns an ``ErrorResponse`` (retrying 429s internally). These tests pin the
contract that the bot inspects returned responses rather than catching a
``MatrixRequestError`` exception class that does not exist in this package.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from biblebot.bot import BibleBot, MessageSendError
from biblebot.messaging import (
    is_error_response,
    is_rate_limit_response,
    response_retry_delay_seconds,
)


def _error(status_code=None, message="boom", retry_after_ms=None):
    from nio.responses import ErrorResponse

    return ErrorResponse(
        message=message, status_code=status_code, retry_after_ms=retry_after_ms
    )


class TestMessagingHelpers:
    def test_is_error_response_detects_nio_error_response(self):
        from nio.responses import ErrorResponse

        assert is_error_response(ErrorResponse("limit exceeded", "M_LIMIT_EXCEEDED"))
        assert not is_error_response(MagicMock(spec=[]))

    def test_is_rate_limit_response_matches_errcode_and_status(self):
        assert is_rate_limit_response(_error("M_LIMIT_EXCEEDED"))
        assert is_rate_limit_response(_error(429))
        assert not is_rate_limit_response(_error("M_UNKNOWN"))
        assert not is_rate_limit_response(None)

    def test_retry_delay_prefers_server_hint_with_jitter(self):
        delay = response_retry_delay_seconds(
            _error(retry_after_ms=2000), attempt=0, rng=lambda lo, hi: 1.0
        )
        assert delay == pytest.approx(2.0)

    def test_retry_delay_falls_back_and_grows_with_attempts(self):
        rng = lambda lo, hi: 1.0
        first = response_retry_delay_seconds(_error(), attempt=0, rng=rng)
        second = response_retry_delay_seconds(_error(), attempt=2, rng=rng)
        assert first > 0
        assert second > first


class TestSendMessageParts:
    @pytest.mark.asyncio
    async def test_returns_error_response_after_retries_exhausted(self, monkeypatch):
        bot = BibleBot(config={"matrix_room_ids": []}, client=MagicMock())
        limited = _error("M_LIMIT_EXCEEDED", retry_after_ms=1000)
        bot.client.room_send = AsyncMock(return_value=limited)

        sleeps: list[float] = []

        async def _record_sleep(delay):
            sleeps.append(delay)

        monkeypatch.setattr("biblebot.bot.asyncio.sleep", _record_sleep)

        result = await bot._send_message_parts("!room:x", ["Verse"], None)

        assert result is limited
        assert bot.client.room_send.await_count == 4  # initial + MAX_RATE_LIMIT_RETRIES
        assert len(sleeps) == 3

    @pytest.mark.asyncio
    async def test_returns_first_non_rate_limit_error_immediately(self, monkeypatch):
        bot = BibleBot(config={"matrix_room_ids": []}, client=MagicMock())
        server_error = _error("M_UNKNOWN")
        bot.client.room_send = AsyncMock(return_value=server_error)

        sleeps: list[float] = []

        async def _record_sleep(delay):
            sleeps.append(delay)

        monkeypatch.setattr("biblebot.bot.asyncio.sleep", _record_sleep)

        result = await bot._send_message_parts("!room:x", ["Verse"], None)

        assert result is server_error
        assert bot.client.room_send.await_count == 1
        assert sleeps == []

    @pytest.mark.asyncio
    async def test_returns_none_on_success(self):
        bot = BibleBot(config={"matrix_room_ids": []}, client=MagicMock())
        bot.client.room_send = AsyncMock(return_value=MagicMock())

        assert await bot._send_message_parts("!room:x", ["Verse"], None) is None

    @pytest.mark.asyncio
    async def test_raises_message_send_error_on_aiohttp_client_error(self):
        import aiohttp

        bot = BibleBot(config={"matrix_room_ids": []}, client=MagicMock())
        bot.client.room_send = AsyncMock(side_effect=aiohttp.ClientError("conn dropped"))

        with pytest.raises(MessageSendError):
            await bot._send_message_parts("!room:x", ["Verse"], None)


async def _record_sleep(sleeps):
    async def _sleep(delay):
        sleeps.append(delay)

    return _sleep
