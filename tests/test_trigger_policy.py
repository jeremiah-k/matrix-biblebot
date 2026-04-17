"""Tests for the trigger policy system."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from biblebot.bot import BibleBot
from biblebot.triggers import (
    TriggerMode,
    TriggerSource,
    detect_trigger,
)


def _make_bot(
    default_translation="kjv",
    bot_mxid="@bot:example.org",
):
    cfg = {
        "matrix_room_ids": ["!test:example.org"],
        "bot": {
            "default_translation": default_translation,
        },
    }
    bot = BibleBot(cfg)
    bot.client = MagicMock()
    bot.client.user_id = bot_mxid
    bot.start_time = 0
    bot._room_id_set = {"!test:example.org"}
    return bot


def _make_event(body, sender="@user:example.org", formatted_body=None, timestamp=1000):
    event = MagicMock()
    event.body = body
    event.sender = sender
    event.server_timestamp = timestamp
    event.formatted_body = formatted_body
    event.event_id = "$event:example.org"
    return event


def _make_room(room_id="!test:example.org"):
    room = MagicMock()
    room.room_id = room_id
    room.encrypted = False
    return room


class TestDirectOnlyMode:
    def test_exact_chapter_verse(self):
        result = detect_trigger(
            "John 3:16", None, TriggerMode.DIRECT_ONLY, "!bible", "@bot:x", "kjv"
        )
        assert result is not None
        assert result.passage == "John 3:16"
        assert result.source == TriggerSource.DIRECT

    def test_exact_chapter_only(self):
        result = detect_trigger(
            "Psalm 23", None, TriggerMode.DIRECT_ONLY, "!bible", "@bot:x", "kjv"
        )
        assert result is not None
        assert result.passage == "Psalms 23"
        assert result.source == TriggerSource.DIRECT

    def test_embedded_reference_rejected(self):
        result = detect_trigger(
            "show me John 3:16 please",
            None,
            TriggerMode.DIRECT_ONLY,
            "!bible",
            "@bot:x",
            "kjv",
        )
        assert result is None

    def test_prefix_rejected(self):
        result = detect_trigger(
            "!bible John 3:16", None, TriggerMode.DIRECT_ONLY, "!bible", "@bot:x", "kjv"
        )
        assert result is None

    def test_mention_rejected(self):
        result = detect_trigger(
            "@bot:example.org John 3:16",
            None,
            TriggerMode.DIRECT_ONLY,
            "!bible",
            "@bot:example.org",
            "kjv",
        )
        assert result is None

    def test_empty_body(self):
        result = detect_trigger(
            "", None, TriggerMode.DIRECT_ONLY, "!bible", "@bot:x", "kjv"
        )
        assert result is None

    def test_whitespace_body(self):
        result = detect_trigger(
            "   ", None, TriggerMode.DIRECT_ONLY, "!bible", "@bot:x", "kjv"
        )
        assert result is None

    def test_translation_suffix(self):
        result = detect_trigger(
            "John 3:16 esv", None, TriggerMode.DIRECT_ONLY, "!bible", "@bot:x", "kjv"
        )
        assert result is not None
        assert result.translation == "esv"

    def test_verse_range(self):
        result = detect_trigger(
            "1 Cor 15:1-4", None, TriggerMode.DIRECT_ONLY, "!bible", "@bot:x", "kjv"
        )
        assert result is not None
        assert result.passage == "1 Corinthians 15:1-4"

    def test_abbreviation(self):
        result = detect_trigger(
            "jn 3:16", None, TriggerMode.DIRECT_ONLY, "!bible", "@bot:x", "kjv"
        )
        assert result is not None
        assert result.passage == "John 3:16"

    def test_bare_localpart_does_not_trigger(self):
        result = detect_trigger(
            "bot John 3:16", None, TriggerMode.DIRECT_ONLY, "!bible", "@bot:x", "kjv"
        )
        assert result is None

    def test_mention_with_formatted_body_rejected(self):
        fb = '<a href="https://matrix.to/#/@bot:x">@bot</a> Psalm 23'
        result = detect_trigger(
            "@bot Psalm 23", fb, TriggerMode.DIRECT_ONLY, "!bible", "@bot:x", "kjv"
        )
        assert result is None

    def test_devotional_text_rejected(self):
        result = detect_trigger(
            "The Lord is my shepherd, I shall not want. Psalm 23 is so comforting.",
            None,
            TriggerMode.DIRECT_ONLY,
            "!bible",
            "@bot:x",
            "kjv",
        )
        assert result is None

    def test_embedded_chapter_verse_rejected(self):
        result = detect_trigger(
            "Have you read John 3:16 today?",
            None,
            TriggerMode.DIRECT_ONLY,
            "!bible",
            "@bot:x",
            "kjv",
        )
        assert result is None

    def test_thessalonians_false_positive_rejected(self):
        result = detect_trigger(
            "1 Thessalonians 4 16 says something important",
            None,
            TriggerMode.DIRECT_ONLY,
            "!bible",
            "@bot:x",
            "kjv",
        )
        assert result is None


class TestBotIntegration:
    @pytest.mark.asyncio
    async def test_direct_only_exact_triggers(self):
        bot = _make_bot()
        with patch.object(bot, "handle_scripture_command", new_callable=AsyncMock) as m:
            await bot.on_room_message(_make_room(), _make_event("John 3:16"))
            m.assert_called_once()

    @pytest.mark.asyncio
    async def test_direct_only_psalm_23(self):
        bot = _make_bot()
        with patch.object(bot, "handle_scripture_command", new_callable=AsyncMock) as m:
            await bot.on_room_message(_make_room(), _make_event("Psalm 23"))
            m.assert_called_once()

    @pytest.mark.asyncio
    async def test_direct_only_embedded_ignored(self):
        bot = _make_bot()
        with patch.object(bot, "handle_scripture_command", new_callable=AsyncMock) as m:
            await bot.on_room_message(_make_room(), _make_event("show me John 3:16"))
            m.assert_not_called()

    @pytest.mark.asyncio
    async def test_prefix_ignored(self):
        bot = _make_bot()
        with patch.object(bot, "handle_scripture_command", new_callable=AsyncMock) as m:
            await bot.on_room_message(_make_room(), _make_event("!bible John 3:16"))
            m.assert_not_called()

    @pytest.mark.asyncio
    async def test_mention_ignored(self):
        bot = _make_bot()
        fb = '<a href="https://matrix.to/#/@bot:example.org">@bot</a> Psalm 23'
        with patch.object(bot, "handle_scripture_command", new_callable=AsyncMock) as m:
            await bot.on_room_message(
                _make_room(), _make_event("@bot Psalm 23", formatted_body=fb)
            )
            m.assert_not_called()

    @pytest.mark.asyncio
    async def test_devotional_text_rejected(self):
        bot = _make_bot()
        with patch.object(bot, "handle_scripture_command", new_callable=AsyncMock) as m:
            await bot.on_room_message(
                _make_room(), _make_event("Psalm 23 is my favorite chapter")
            )
            m.assert_not_called()

    @pytest.mark.asyncio
    async def test_anywhere_config_ignored(self):
        bot = _make_bot()
        with patch.object(bot, "handle_scripture_command", new_callable=AsyncMock) as m:
            await bot.on_room_message(
                _make_room(), _make_event("Check John 3:16 for context")
            )
            m.assert_not_called()

    def test_bot_default_trigger_mode_is_direct_only(self):
        cfg = {"matrix_room_ids": ["!test:example.org"]}
        bot = BibleBot(cfg)
        assert bot.trigger_mode == TriggerMode.DIRECT_ONLY

    def test_bot_detect_references_anywhere_always_false(self):
        cfg = {"matrix_room_ids": ["!test:example.org"]}
        bot = BibleBot(cfg)
        assert bot.trigger_mode == TriggerMode.DIRECT_ONLY
        assert bot.detect_references_anywhere is False
