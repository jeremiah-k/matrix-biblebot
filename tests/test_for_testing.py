"""Tests for BibleBot.for_testing factory."""

from __future__ import annotations

from unittest.mock import MagicMock

from biblebot.bot import BibleBot


# The full set of client surface methods/attributes BibleBot accesses.
# Used for spec'ing the auto-generated test client so ``hasattr`` checks are
# meaningful (a plain MagicMock auto-creates any attribute on access).
_TEST_CLIENT_SPEC = (
    "room_resolve_alias",
    "join",
    "sync",
    "sync_forever",
    "request_room_key",
    "to_device",
    "room_send",
    "close",
    "user_id",
)


def test_for_testing_returns_biblebot_instance():
    """for_testing must return a BibleBot constructed with the supplied config."""
    config: dict = {"bot": {}, "matrix": {"room_ids": ["!room:example.org"]}}
    bot = BibleBot.for_testing(config)
    assert isinstance(bot, BibleBot)


def test_for_testing_attaches_specd_mock_client():
    """for_testing must wire a spec'd mock client that exposes every method
    BibleBot uses on its client.

    Using ``MagicMock(spec=...)`` (rather than a plain MagicMock) makes
    ``hasattr`` checks meaningful: a plain MagicMock auto-creates any
    attribute on access and would pass a getattr-based test even when the
    real client has no such method.
    """
    bot = BibleBot.for_testing({"bot": {}})

    # The client is a MagicMock.
    assert isinstance(bot.client, MagicMock)

    # Every method BibleBot uses on its client must be reachable AND callable.
    for name in _TEST_CLIENT_SPEC:
        assert hasattr(bot.client, name), f"client must expose {name}"
        assert callable(getattr(bot.client, name)), f"{name} must be callable"

    # An attribute that is NOT part of the contract must not be auto-created
    # (this proves the spec is actually applied).
    assert not hasattr(bot.client, "definitely_not_a_method")


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
