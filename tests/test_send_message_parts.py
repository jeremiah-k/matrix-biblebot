"""Direct coverage for the message-retry paths in BibleBot._send_message_parts."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from biblebot.bot import BibleBot
from tests.conftest import MockMatrixRequestError


@pytest.mark.asyncio
async def test_send_message_parts_retries_then_succeeds(monkeypatch):
    bot = BibleBot(config={"matrix_room_ids": []}, client=MagicMock())
    bot.client.room_send = AsyncMock(
        side_effect=[
            MockMatrixRequestError("rate limited", status_code=429, errcode="M_LIMIT_EXCEEDED"),
            MockMatrixRequestError("rate limited", status_code=429, errcode="M_LIMIT_EXCEEDED"),
            MagicMock(),
        ]
    )

    async def _no_sleep(_value):
        return None

    monkeypatch.setattr("biblebot.bot.asyncio.sleep", _no_sleep)

    await bot._send_message_parts("!room:example.org", ["Verse text"], "John 3:16")

    assert bot.client.room_send.await_count == 3


@pytest.mark.asyncio
async def test_send_message_parts_skips_retries_for_non_rate_limit(monkeypatch):
    bot = BibleBot(config={"matrix_room_ids": []}, client=MagicMock())

    bad = MockMatrixRequestError("server", status_code=500, errcode=None)
    bot.client.room_send = AsyncMock(side_effect=bad)

    sleeps: list[float] = []

    async def _record_sleep(value: float) -> None:
        sleeps.append(value)

    monkeypatch.setattr("biblebot.bot.asyncio.sleep", _record_sleep)

    with pytest.raises(MockMatrixRequestError):
        await bot._send_message_parts("!room:example.org", ["Verse text"], None)

    assert sleeps == []
