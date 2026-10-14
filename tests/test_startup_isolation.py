"""Lifecycle tests must not contact the external release service."""

from unittest.mock import AsyncMock, MagicMock, Mock

import pytest

from biblebot import bot, update_check
from biblebot.auth import Credentials


async def test_lifecycle_startup_does_not_open_a_release_http_session(monkeypatch):
    client = MagicMock()
    client.close = AsyncMock()
    client.restore_login.side_effect = RuntimeError("stop after update check")
    instance = MagicMock()
    instance.http_session = None
    instance.close = AsyncMock()
    monkeypatch.setattr(bot, "AsyncClient", lambda *a, **k: client)
    monkeypatch.setattr(bot, "BibleBot", lambda *a, **k: instance)
    monkeypatch.setattr(bot, "load_environment", lambda *a: (None, {}))
    monkeypatch.setattr(
        bot,
        "load_credentials",
        lambda: Credentials("https://server", "@bot:server", "token", "DEVICE"),
    )
    http_session = Mock(side_effect=AssertionError("external HTTP reached"))
    monkeypatch.setattr(update_check.aiohttp, "ClientSession", http_session)

    with pytest.raises(RuntimeError, match="stop after update check"):
        await bot.main(config={"matrix_room_ids": ["!room:server"]})

    http_session.assert_not_called()
