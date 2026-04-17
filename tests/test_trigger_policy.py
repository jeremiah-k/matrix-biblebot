"""Tests for the trigger policy system."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from biblebot.bot import BibleBot
from biblebot.constants.bible import DEFAULT_TRANSLATION
from biblebot.triggers import (
    TriggerMatch,
    TriggerMode,
    TriggerSource,
    _extract_mention_body,
    _try_direct_match,
    _try_embedded_match,
    _try_prefix_match,
    detect_trigger,
)


def _make_bot(
    trigger_mode=TriggerMode.DIRECT_ONLY,
    command_prefix="!bible",
    default_translation="kjv",
    bot_mxid="@bot:example.org",
):
    mode_value = (
        trigger_mode.value if isinstance(trigger_mode, TriggerMode) else trigger_mode
    )
    cfg = {
        "matrix_room_ids": ["!test:example.org"],
        "bot": {
            "trigger_mode": mode_value,
            "command_prefix": command_prefix,
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


class TestSmartMode:
    def test_exact_reference_triggers(self):
        result = detect_trigger(
            "John 3:16", None, TriggerMode.SMART, "!bible", "@bot:x", "kjv"
        )
        assert result is not None
        assert result.passage == "John 3:16"
        assert result.source == TriggerSource.DIRECT

    def test_exact_chapter_only_triggers(self):
        result = detect_trigger(
            "Psalm 23", None, TriggerMode.SMART, "!bible", "@bot:x", "kjv"
        )
        assert result is not None
        assert result.passage == "Psalms 23"
        assert result.source == TriggerSource.DIRECT

    def test_mention_with_reference_via_formatted_body(self):
        fb = '<a href="https://matrix.to/#/@bot:x">@bot</a> Psalm 23'
        result = detect_trigger(
            "@bot Psalm 23", fb, TriggerMode.SMART, "!bible", "@bot:x", "kjv"
        )
        assert result is not None
        assert result.passage == "Psalms 23"
        assert result.source == TriggerSource.MENTION

    def test_mention_with_reference_via_plain_mxid(self):
        body = "@bot:example.org John 3:16"
        result = detect_trigger(
            body, None, TriggerMode.SMART, "!bible", "@bot:example.org", "kjv"
        )
        assert result is not None
        assert "John 3:16" in result.passage
        assert result.source == TriggerSource.MENTION

    def test_prefix_with_reference(self):
        result = detect_trigger(
            "!bible Psalm 23", None, TriggerMode.SMART, "!bible", "@bot:x", "kjv"
        )
        assert result is not None
        assert result.passage == "Psalms 23"
        assert result.source == TriggerSource.PREFIX

    def test_prefix_with_translation(self):
        result = detect_trigger(
            "!bible John 3:16 esv", None, TriggerMode.SMART, "!bible", "@bot:x", "kjv"
        )
        assert result is not None
        assert result.passage == "John 3:16"
        assert result.translation == "esv"
        assert result.source == TriggerSource.PREFIX

    def test_ambient_embedded_rejected(self):
        result = detect_trigger(
            "Have you read John 3:16 today?",
            None,
            TriggerMode.SMART,
            "!bible",
            "@bot:x",
            "kjv",
        )
        assert result is None

    def test_devotional_text_rejected(self):
        result = detect_trigger(
            "The Lord is my shepherd, I shall not want. Psalm 23 is so comforting.",
            None,
            TriggerMode.SMART,
            "!bible",
            "@bot:x",
            "kjv",
        )
        assert result is None

    def test_mention_no_remainder(self):
        body = "@bot:example.org"
        result = detect_trigger(
            body, None, TriggerMode.SMART, "!bible", "@bot:example.org", "kjv"
        )
        assert result is None

    def test_mention_short_sigil_without_formatted_body(self):
        body = "@bot Psalm 23"
        result = detect_trigger(
            body, None, TriggerMode.SMART, "!bible", "@bot:example.org", "kjv"
        )
        assert result is not None
        assert result.passage == "Psalms 23"
        assert result.source == TriggerSource.MENTION

    def test_bare_localpart_does_not_trigger(self):
        body = "bot John 3:16"
        result = detect_trigger(
            body, None, TriggerMode.SMART, "!bible", "@bot:example.org", "kjv"
        )
        assert result is None

    def test_mention_invalid_reference(self):
        body = "@bot:example.org what's up?"
        result = detect_trigger(
            body, None, TriggerMode.SMART, "!bible", "@bot:example.org", "kjv"
        )
        assert result is None


class TestAnywhereMode:
    def test_embedded_chapter_verse_triggers(self):
        result = detect_trigger(
            "Have you read John 3:16 today?",
            None,
            TriggerMode.ANYWHERE,
            "!bible",
            "@bot:x",
            "kjv",
        )
        assert result is not None
        assert "John 3:16" in result.passage
        assert result.source == TriggerSource.ANYWHERE

    def test_embedded_chapter_only_rejected(self):
        result = detect_trigger(
            "1 Thessalonians 4 16 For the Lord himself will descend...",
            None,
            TriggerMode.ANYWHERE,
            "!bible",
            "@bot:x",
            "kjv",
        )
        assert result is None

    def test_standalone_chapter_only_works(self):
        result = detect_trigger(
            "Psalm 23", None, TriggerMode.ANYWHERE, "!bible", "@bot:x", "kjv"
        )
        assert result is not None
        assert result.passage == "Psalms 23"
        assert result.source == TriggerSource.DIRECT

    def test_standalone_chapter_verse_works(self):
        result = detect_trigger(
            "John 3:16", None, TriggerMode.ANYWHERE, "!bible", "@bot:x", "kjv"
        )
        assert result is not None
        assert result.source == TriggerSource.DIRECT

    def test_false_positive_thessalonians(self):
        result = detect_trigger(
            "1 Thessalonians 4 16 says something important",
            None,
            TriggerMode.ANYWHERE,
            "!bible",
            "@bot:x",
            "kjv",
        )
        assert result is None

    def test_embedded_with_translation(self):
        result = detect_trigger(
            "Check out John 3:16 esv everyone",
            None,
            TriggerMode.ANYWHERE,
            "!bible",
            "@bot:x",
            "kjv",
        )
        assert result is not None
        assert result.translation == "esv"

    def test_devotional_with_chapter_verse(self):
        result = detect_trigger(
            "I love Psalm 23:1, it speaks to my heart",
            None,
            TriggerMode.ANYWHERE,
            "!bible",
            "@bot:x",
            "kjv",
        )
        assert result is not None
        assert "Psalms 23:1" in result.passage

    def test_prefix_command_triggers(self):
        result = detect_trigger(
            "!bible John 3:16",
            None,
            TriggerMode.ANYWHERE,
            "!bible",
            "@bot:x",
            "kjv",
        )
        assert result is not None
        assert result.passage == "John 3:16"
        assert result.source == TriggerSource.PREFIX

    def test_mention_triggers(self):
        result = detect_trigger(
            "@bot Psalm 23",
            None,
            TriggerMode.ANYWHERE,
            "!bible",
            "@bot:example.org",
            "kjv",
        )
        assert result is not None
        assert result.passage == "Psalms 23"
        assert result.source == TriggerSource.MENTION

    def test_embedded_chapter_only_in_ambient_text_rejected(self):
        result = detect_trigger(
            "I really like Psalm 23 it is a great chapter",
            None,
            TriggerMode.ANYWHERE,
            "!bible",
            "@bot:x",
            "kjv",
        )
        assert result is None

    def test_bare_localpart_does_not_trigger_as_mention(self):
        result = detect_trigger(
            "bot John 3:16",
            None,
            TriggerMode.ANYWHERE,
            "!bible",
            "@bot:example.org",
            "kjv",
        )
        assert result is not None
        assert result.source == TriggerSource.ANYWHERE
        assert result.passage == "John 3:16"


class TestPrefixCustomization:
    def test_custom_prefix(self):
        result = detect_trigger(
            "!verse John 3:16", None, TriggerMode.SMART, "!verse", "@bot:x", "kjv"
        )
        assert result is not None
        assert result.source == TriggerSource.PREFIX

    def test_wrong_prefix_no_match(self):
        result = detect_trigger(
            "!wrong John 3:16", None, TriggerMode.SMART, "!bible", "@bot:x", "kjv"
        )
        assert result is None

    def test_empty_prefix_disables(self):
        result = detect_trigger(
            "!bible John 3:16", None, TriggerMode.SMART, "", "@bot:x", "kjv"
        )
        assert result is None

    def test_none_prefix_disables(self):
        result = detect_trigger(
            "!bible John 3:16", None, TriggerMode.SMART, None, "@bot:x", "kjv"
        )
        assert result is None

    def test_prefix_with_space(self):
        result = detect_trigger(
            "!bible  John 3:16", None, TriggerMode.SMART, "!bible", "@bot:x", "kjv"
        )
        assert result is not None


class TestLegacyMigration:
    def test_detect_anywhere_true_maps_to_anywhere(self):
        cfg = {
            "matrix_room_ids": ["!test:example.org"],
            "bot": {"detect_references_anywhere": True},
        }
        with patch("biblebot.bot.logger") as mock_logger:
            bot = BibleBot(cfg)
            assert bot.trigger_mode == TriggerMode.ANYWHERE
            assert bot.detect_references_anywhere is True
            mock_logger.warning.assert_called_once()
            assert "deprecated" in mock_logger.warning.call_args[0][0].lower()

    def test_detect_anywhere_false_maps_to_direct_only(self):
        cfg = {
            "matrix_room_ids": ["!test:example.org"],
            "bot": {"detect_references_anywhere": False},
        }
        with patch("biblebot.bot.logger") as mock_logger:
            bot = BibleBot(cfg)
            assert bot.trigger_mode == TriggerMode.DIRECT_ONLY
            assert bot.detect_references_anywhere is False

    def test_trigger_mode_takes_precedence_over_legacy(self):
        cfg = {
            "matrix_room_ids": ["!test:example.org"],
            "bot": {
                "detect_references_anywhere": True,
                "trigger_mode": "smart",
            },
        }
        bot = BibleBot(cfg)
        assert bot.trigger_mode == TriggerMode.SMART


class TestBotIntegration:
    @pytest.mark.asyncio
    async def test_direct_only_exact_triggers(self):
        bot = _make_bot(TriggerMode.DIRECT_ONLY)
        with patch.object(bot, "handle_scripture_command", new_callable=AsyncMock) as m:
            await bot.on_room_message(_make_room(), _make_event("John 3:16"))
            m.assert_called_once()

    @pytest.mark.asyncio
    async def test_direct_only_psalm_23(self):
        bot = _make_bot(TriggerMode.DIRECT_ONLY)
        with patch.object(bot, "handle_scripture_command", new_callable=AsyncMock) as m:
            await bot.on_room_message(_make_room(), _make_event("Psalm 23"))
            m.assert_called_once()

    @pytest.mark.asyncio
    async def test_direct_only_embedded_ignored(self):
        bot = _make_bot(TriggerMode.DIRECT_ONLY)
        with patch.object(bot, "handle_scripture_command", new_callable=AsyncMock) as m:
            await bot.on_room_message(_make_room(), _make_event("show me John 3:16"))
            m.assert_not_called()

    @pytest.mark.asyncio
    async def test_smart_mention_via_formatted_body(self):
        bot = _make_bot(TriggerMode.SMART)
        fb = '<a href="https://matrix.to/#/@bot:example.org">@bot</a> Psalm 23'
        with patch.object(bot, "handle_scripture_command", new_callable=AsyncMock) as m:
            await bot.on_room_message(
                _make_room(), _make_event("@bot Psalm 23", formatted_body=fb)
            )
            m.assert_called_once()
            assert "Psalms 23" in m.call_args[0][1]

    @pytest.mark.asyncio
    async def test_smart_prefix_triggers(self):
        bot = _make_bot(TriggerMode.SMART)
        with patch.object(bot, "handle_scripture_command", new_callable=AsyncMock) as m:
            await bot.on_room_message(_make_room(), _make_event("!bible John 3:16"))
            m.assert_called_once()

    @pytest.mark.asyncio
    async def test_smart_ambient_rejected(self):
        bot = _make_bot(TriggerMode.SMART)
        with patch.object(bot, "handle_scripture_command", new_callable=AsyncMock) as m:
            await bot.on_room_message(
                _make_room(), _make_event("The Lord is my shepherd. Psalm 23 is great.")
            )
            m.assert_not_called()

    @pytest.mark.asyncio
    async def test_anywhere_embedded_verse_triggers(self):
        bot = _make_bot(TriggerMode.ANYWHERE)
        with patch.object(bot, "handle_scripture_command", new_callable=AsyncMock) as m:
            await bot.on_room_message(
                _make_room(), _make_event("Check John 3:16 for context")
            )
            m.assert_called_once()

    @pytest.mark.asyncio
    async def test_anywhere_embedded_chapter_only_rejected(self):
        bot = _make_bot(TriggerMode.ANYWHERE)
        with patch.object(bot, "handle_scripture_command", new_callable=AsyncMock) as m:
            await bot.on_room_message(
                _make_room(), _make_event("1 Thessalonians 4 16 says the Lord descends")
            )
            m.assert_not_called()

    @pytest.mark.asyncio
    async def test_anywhere_prefix_triggers(self):
        bot = _make_bot(TriggerMode.ANYWHERE)
        with patch.object(bot, "handle_scripture_command", new_callable=AsyncMock) as m:
            await bot.on_room_message(_make_room(), _make_event("!bible John 3:16"))
            m.assert_called_once()

    @pytest.mark.asyncio
    async def test_anywhere_mention_triggers(self):
        bot = _make_bot(TriggerMode.ANYWHERE)
        fb = '<a href="https://matrix.to/#/@bot:example.org">@bot</a> Psalm 23'
        with patch.object(bot, "handle_scripture_command", new_callable=AsyncMock) as m:
            await bot.on_room_message(
                _make_room(), _make_event("@bot Psalm 23", formatted_body=fb)
            )
            m.assert_called_once()
            assert "Psalms 23" in m.call_args[0][1]

    @pytest.mark.asyncio
    async def test_anywhere_embedded_chapter_only_ambient_rejected(self):
        bot = _make_bot(TriggerMode.ANYWHERE)
        with patch.object(bot, "handle_scripture_command", new_callable=AsyncMock) as m:
            await bot.on_room_message(
                _make_room(),
                _make_event("I really like Psalm 23 it is a great chapter"),
            )
            m.assert_not_called()

    @pytest.mark.asyncio
    async def test_devotional_text_rejected_in_smart(self):
        bot = _make_bot(TriggerMode.SMART)
        with patch.object(bot, "handle_scripture_command", new_callable=AsyncMock) as m:
            await bot.on_room_message(
                _make_room(), _make_event("Psalm 23 is my favorite chapter")
            )
            m.assert_not_called()

    @pytest.mark.asyncio
    async def test_bot_default_trigger_mode_is_direct_only(self):
        cfg = {"matrix_room_ids": ["!test:example.org"]}
        bot = BibleBot(cfg)
        assert bot.trigger_mode == TriggerMode.DIRECT_ONLY

    @pytest.mark.asyncio
    async def test_bot_default_command_prefix(self):
        cfg = {"matrix_room_ids": ["!test:example.org"]}
        bot = BibleBot(cfg)
        assert bot.command_prefix == "!bible"

    @pytest.mark.asyncio
    async def test_bot_null_command_prefix(self):
        cfg = {
            "matrix_room_ids": ["!test:example.org"],
            "bot": {"command_prefix": None},
        }
        bot = BibleBot(cfg)
        assert bot.command_prefix is None

    @pytest.mark.asyncio
    async def test_bot_empty_command_prefix(self):
        cfg = {
            "matrix_room_ids": ["!test:example.org"],
            "bot": {"command_prefix": ""},
        }
        bot = BibleBot(cfg)
        assert bot.command_prefix is None

    @pytest.mark.asyncio
    async def test_bot_numeric_command_prefix_coerced(self):
        cfg = {
            "matrix_room_ids": ["!test:example.org"],
            "bot": {"command_prefix": 123},
        }
        with patch("biblebot.bot.logger") as mock_logger:
            bot = BibleBot(cfg)
            assert bot.command_prefix == "123"
            mock_logger.warning.assert_called_once()
            assert "command_prefix" in mock_logger.warning.call_args[0][0].lower()
