"""Tests for BibleBot.for_testing factory."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from biblebot.bot import BibleBot
from biblebot.protocols import BotClient



def test_for_testing_returns_biblebot_instance():
    """for_testing must return a BibleBot constructed with the supplied config."""
    config: dict = {"bot": {}, "matrix": {"room_ids": ["!room:example.org"]}}
    bot = BibleBot.for_testing(config)
    assert isinstance(bot, BibleBot)


def test_for_testing_attaches_protocol_compatible_mock_client():
    """The generated client satisfies BotClient, including its async surface."""
    bot = BibleBot.for_testing({"bot": {}})

    assert isinstance(bot.client, MagicMock)
    assert isinstance(bot.client, BotClient)
    assert bot.client.user_id is None
    assert bot.client.device_id is None
    assert bot.client.rooms == {}

    for name in (
        "room_resolve_alias",
        "join",
        "sync",
        "sync_forever",
        "request_room_key",
        "to_device",
        "room_send",
        "close",
    ):
        assert isinstance(getattr(bot.client, name), AsyncMock)

    assert not hasattr(bot.client, "definitely_not_a_method")


async def test_for_testing_generated_client_is_awaitable():
    """Generated protocol methods can be awaited by normal BibleBot code."""
    bot = BibleBot.for_testing({"bot": {}})

    await bot.client.room_send(
        "!room:example.org",
        "m.room.message",
        {"msgtype": "m.text", "body": "test"},
    )

    bot.client.room_send.assert_awaited_once()


def test_for_testing_accepts_optional_client_override():
    """Callers can override the auto-generated mock client.

    When the caller passes a client, the factory uses it verbatim — it does
    not re-spec it, so callers retain full control over the test double.
    """
    config: dict = {"bot": {}}
    explicit = MagicMock()
    explicit.user_id = "@override:example.org"
    bot = BibleBot.for_testing(config, client=explicit)
    assert bot.client is explicit


def test_for_testing_does_not_alias_top_level_config_keys():
    """The factory must not mutate the supplied config at the top level."""
    config: dict = {"bot": {}, "matrix": {"room_ids": ["!room:example.org"]}}
    snapshot = dict(config)
    BibleBot.for_testing(config)
    assert config == snapshot


def test_for_testing_does_not_alias_nested_config_values():
    """The factory must deep-copy config so later mutations don't leak in.

    This guards against a regression where the bot stores the caller's dict
    by reference; if a test mutates a nested value after construction, the bot
    must still see the snapshot it was built with.
    """
    config: dict = {
        "bot": {},
        "matrix": {"room_ids": ["!room:example.org"]},
    }
    bot = BibleBot.for_testing(config)

    # Mutate a nested value in the original config.
    config["matrix"]["room_ids"].append("!nested:example.org")
    config["bot"]["new_key"] = "should not leak"

    assert "!nested:example.org" not in bot.config["matrix"]["room_ids"]
    assert "new_key" not in bot.config["bot"]


def test_for_testing_returns_copy_that_can_be_mutated_safely():
    """Mutations to the returned bot's config must not affect the caller's dict.

    The factory returns a bot whose config is an independent copy; the caller
    can safely mutate either side without affecting the other.
    """
    config: dict = {"bot": {"setting": "original"}}
    bot = BibleBot.for_testing(config)

    # Mutating the bot's config must not change the caller's config.
    bot.config["bot"]["setting"] = "mutated"
    assert config["bot"]["setting"] == "original"
