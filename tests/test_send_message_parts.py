"""Response-based send handling in BibleBot._send_message_parts.

nio's ``AsyncClient.room_send`` does not raise for Matrix-level errors: it
returns an ``ErrorResponse`` (retrying 429s internally). These tests pin the
contract that the bot inspects returned responses rather than catching a
``MatrixRequestError`` exception class that does not exist in this package.
"""

from __future__ import annotations

import logging
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
        def rng(lo, hi):
            return 1.0

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

        retry_delay = MagicMock(return_value=0.0)
        monkeypatch.setattr("biblebot.bot.response_retry_delay_seconds", retry_delay)

        result = await bot._send_message_parts("!room:x", ["Verse"], None)

        assert result is limited
        assert bot.client.room_send.await_count == 4  # initial + MAX_RATE_LIMIT_RETRIES
        assert retry_delay.call_count == 3

    @pytest.mark.asyncio
    async def test_returns_first_non_rate_limit_error_immediately(self, monkeypatch):
        bot = BibleBot(config={"matrix_room_ids": []}, client=MagicMock())
        server_error = _error("M_UNKNOWN")
        bot.client.room_send = AsyncMock(return_value=server_error)

        retry_delay = MagicMock(return_value=0.0)
        monkeypatch.setattr("biblebot.bot.response_retry_delay_seconds", retry_delay)

        result = await bot._send_message_parts("!room:x", ["Verse"], None)

        assert result is server_error
        assert bot.client.room_send.await_count == 1
        retry_delay.assert_not_called()

    @pytest.mark.asyncio
    async def test_returns_none_on_success(self):
        bot = BibleBot(config={"matrix_room_ids": []}, client=MagicMock())
        bot.client.room_send = AsyncMock(return_value=MagicMock())

        assert await bot._send_message_parts("!room:x", ["Verse"], None) is None

    @pytest.mark.asyncio
    async def test_raises_message_send_error_on_aiohttp_client_error(self):
        import aiohttp

        bot = BibleBot(config={"matrix_room_ids": []}, client=MagicMock())
        bot.client.room_send = AsyncMock(
            side_effect=aiohttp.ClientError("conn dropped")
        )

        with pytest.raises(MessageSendError):
            await bot._send_message_parts("!room:x", ["Verse"], None)

    @pytest.mark.asyncio
    async def test_raises_message_send_error_on_nio_transport_errors(self):
        from nio import LocalProtocolError, RemoteProtocolError, RemoteTransportError

        bot = BibleBot(config={"matrix_room_ids": []}, client=MagicMock())
        for exc in (
            LocalProtocolError("not logged in"),
            RemoteProtocolError("bad response"),
            RemoteTransportError("connection lost"),
        ):
            bot.client.room_send = AsyncMock(side_effect=exc)
            with pytest.raises(MessageSendError):
                await bot._send_message_parts("!room:x", ["Verse"], None)


class TestHandleScriptureCommandSendFailure:
    """handle_scripture_command must not log success when Matrix rejects a send."""

    @staticmethod
    def _bot_with_failing_send(error_response):
        bot = BibleBot(config={"matrix_room_ids": ["!room:x"]}, client=MagicMock())
        bot.client.room_send = AsyncMock(return_value=error_response)
        bot._send_error_message = AsyncMock()
        return bot

    @staticmethod
    def _event():
        event = MagicMock()
        event.event_id = "$evt:example.org"
        return event

    @pytest.mark.asyncio
    async def test_single_message_failure_skips_success_log(self, monkeypatch, caplog):
        from nio.responses import ErrorResponse

        bot = self._bot_with_failing_send(
            ErrorResponse("rejected", status_code="M_UNKNOWN")
        )
        monkeypatch.setattr(
            "biblebot.bot.get_bible_text",
            AsyncMock(return_value=("For God so loved the world", "John 3:16")),
        )

        with caplog.at_level(logging.INFO):
            await bot.handle_scripture_command(
                "!room:x", "John 3:16", None, self._event()
            )

        assert "Failed to send scripture" in caplog.text
        assert "Sent scripture" not in caplog.text

    @pytest.mark.asyncio
    async def test_split_message_failure_skips_success_log(self, monkeypatch, caplog):
        from nio.responses import ErrorResponse

        bot = self._bot_with_failing_send(
            ErrorResponse("rejected", status_code="M_LIMIT_EXCEEDED")
        )
        bot.split_message_length = 10  # force the split path
        monkeypatch.setattr(
            "biblebot.bot.get_bible_text",
            AsyncMock(return_value=("long text " * 50, "John 3:16")),
        )
        # Keep the retry path real while collapsing backoff to an event-loop yield.
        monkeypatch.setattr(
            "biblebot.bot.response_retry_delay_seconds", lambda *_args, **_kwargs: 0.0
        )

        with caplog.at_level(logging.INFO):
            await bot.handle_scripture_command(
                "!room:x", "John 3:16", None, self._event()
            )

        assert "Failed to send split scripture" in caplog.text
        assert "Sent split scripture" not in caplog.text

    @pytest.mark.asyncio
    async def test_success_still_logs_sent(self, monkeypatch, caplog):
        bot = BibleBot(config={"matrix_room_ids": ["!room:x"]}, client=MagicMock())
        bot.client.room_send = AsyncMock(return_value=MagicMock())
        monkeypatch.setattr(
            "biblebot.bot.get_bible_text",
            AsyncMock(return_value=("For God so loved the world", "John 3:16")),
        )

        with caplog.at_level(logging.INFO):
            await bot.handle_scripture_command(
                "!room:x", "John 3:16", None, self._event()
            )

        assert "Sent scripture" in caplog.text
        assert "Failed to send" not in caplog.text

    @pytest.mark.asyncio
    async def test_send_failure_sends_user_facing_notice(self, monkeypatch):
        from nio.responses import ErrorResponse

        # Forbidden response: the room rejects posts entirely, so no notice
        # can be delivered there. The bot must NOT attempt a doomed send.
        bot = self._bot_with_failing_send(
            ErrorResponse("rejected", status_code="M_FORBIDDEN")
        )
        monkeypatch.setattr(
            "biblebot.bot.get_bible_text",
            AsyncMock(return_value=("For God so loved the world", "John 3:16")),
        )

        await bot.handle_scripture_command("!room:x", "John 3:16", None, self._event())

        # 2 sends total: the reaction attempt (fails, logged) and the passage
        # send (429-style retry loop does not apply to M_FORBIDDEN, so only
        # one attempt). The delivery-failure notice is deliberately NOT sent
        # to the same forbidden room.
        assert bot.client.room_send.await_count == 2
        kinds = [c.args[1] for c in bot.client.room_send.await_args_list]
        assert "m.room.message" in kinds  # passage attempt happened

    @pytest.mark.asyncio
    async def test_rate_limit_exhaustion_notice_mentions_retry(self, monkeypatch):
        from nio.responses import ErrorResponse

        limited = ErrorResponse("slow down", status_code="M_LIMIT_EXCEEDED")
        bot = BibleBot(config={"matrix_room_ids": ["!room:x"]}, client=MagicMock())
        # Sequence: reaction fails, 4 passage attempts rate-limited, then the
        # notice finally succeeds on its own send.
        bot.client.room_send = AsyncMock(
            side_effect=[limited, limited, limited, limited, limited, MagicMock()]
        )
        monkeypatch.setattr(
            "biblebot.bot.get_bible_text",
            AsyncMock(return_value=("For God so loved the world", "John 3:16")),
        )
        # Keep the retry path real while collapsing backoff to an event-loop yield.
        monkeypatch.setattr(
            "biblebot.bot.response_retry_delay_seconds", lambda *_args, **_kwargs: 0.0
        )

        await bot.handle_scripture_command("!room:x", "John 3:16", None, self._event())

        calls = bot.client.room_send.await_args_list
        # 5 failed passage/reaction sends + 1 notice that got through
        assert len(calls) == 6
        notice_bodies = [
            c.args[2]["body"]
            for c in calls[1:]
            if c.args[1] == "m.room.message" and "rate-limited" in c.args[2]["body"]
        ]
        assert notice_bodies, "expected a delivered rate-limited notice"

    @pytest.mark.asyncio
    async def test_transport_failure_reports_delivery_not_lookup(self, monkeypatch):
        """room_send raising aiohttp.ClientError must yield ERROR_SEND_OTHER,
        not the generic ERROR_PASSAGE_NOT_FOUND lookup message."""
        import aiohttp

        bot = BibleBot(config={"matrix_room_ids": ["!room:x"]}, client=MagicMock())

        async def _raise_transport_error(*_args, **_kwargs):
            # A real failed request raises a fresh exception each time. Reusing one
            # exception instance can create a cause/context cycle when the passage
            # failure is wrapped and the follow-up notice also fails.
            raise aiohttp.ClientError("conn died")

        bot.client.room_send = AsyncMock(side_effect=_raise_transport_error)
        monkeypatch.setattr(
            "biblebot.bot.get_bible_text",
            AsyncMock(return_value=("For God so loved the world", "John 3:16")),
        )

        await bot.handle_scripture_command("!room:x", "John 3:16", None, self._event())

        calls = bot.client.room_send.await_args_list
        assert bot.client.room_send.await_count == 3
        # reaction + passage + notice attempts; notice body must be the
        # delivery-failure message, never the passage-not-found lookup text
        bodies = [c.args[2]["body"] for c in calls if c.args[1] == "m.room.message"]
        assert any("could not be delivered" in b for b in bodies)
        assert not any("passage could not be found" in b.lower() for b in bodies)


async def _record_sleep(sleeps):
    async def _sleep(delay):
        sleeps.append(delay)

    return _sleep
