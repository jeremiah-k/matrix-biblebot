"""Resource ownership throughout startup, including cancellation."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from biblebot import bot
from biblebot.auth import Credentials


@pytest.mark.parametrize(
    "failure", [asyncio.CancelledError(), RuntimeError("restore failed")]
)
async def test_client_closes_when_startup_is_interrupted(monkeypatch, failure):
    client = MagicMock()
    client.close = AsyncMock()
    client.restore_login.side_effect = (
        failure if isinstance(failure, RuntimeError) else None
    )
    bot_double = MagicMock()
    bot_double.http_session = None
    bot_double.close = AsyncMock()
    bot_double.start = AsyncMock()
    monkeypatch.setattr(bot, "AsyncClient", lambda *a, **k: client)
    monkeypatch.setattr(bot, "BibleBot", lambda *a, **k: bot_double)
    monkeypatch.setattr(
        bot,
        "load_credentials",
        lambda: Credentials("https://server", "@bot:server", "token", "DEVICE"),
    )
    monkeypatch.setattr(bot, "load_environment", lambda *a: (None, {}))
    monkeypatch.setattr(
        bot,
        "perform_startup_update_check",
        AsyncMock(
            side_effect=failure if isinstance(failure, asyncio.CancelledError) else None
        ),
    )

    with pytest.raises(type(failure)):
        await bot.main(config={"matrix_room_ids": ["!room:server"]})
    bot_double.start.assert_not_awaited()
    bot_double.close.assert_awaited_once()
    client.close.assert_awaited_once()
