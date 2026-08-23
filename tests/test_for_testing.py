"""Tests for BibleBot.for_testing factory."""

from __future__ import annotations

from unittest.mock import MagicMock

from biblebot.bot import BibleBot


def test_for_testing_returns_biblebot_instance():
    """for_testing must return a BibleBot constructed with the supplied config."""
    config: dict = {"bot": {}, "matrix": {"room_ids": ["!room:example.org"]}}
    bot = BibleBot.for_testing(config)
    assert isinstance(bot, BibleBot)


def test_for_testing_attaches_a_mock_client():
    """for_testing must wire a client that satisfies the BotClient surface.

    Note: ``isinstance(MagicMock(), BotClient)`` is False because Python's
    runtime Protocol check inspects class attributes, not instance state.
    The factory uses a plain MagicMock for that reason; tests that need a
    fully-spec'd BotClient should construct it themselves.
    """
    bot = BibleBot.for_testing({"bot": {}})
    assert bot.client is not None
    assert isinstance(bot.client, MagicMock)
    # Spot-check that the surfaced BotClient methods are all reachable.
    for name in ("room_send", "sync", "sync_forever", "close", "user_id"):
        assert hasattr(bot.client, name), f"client must expose {name}"


def test_for_testing_accepts_optional_client_override():
    """Callers can override the auto-generated mock client."""
    config: dict = {"bot": {}}
    explicit = MagicMock()
    explicit.user_id = "@override:example.org"
    bot = BibleBot.for_testing(config, client=explicit)
    assert bot.client is explicit


def test_for_testing_preserves_config():
    """The factory must not mutate or alias the supplied config."""
    config: dict = {"bot": {}, "matrix": {"room_ids": ["!room:example.org"]}}
    snapshot = dict(config)
    BibleBot.for_testing(config)
    assert config == snapshot
