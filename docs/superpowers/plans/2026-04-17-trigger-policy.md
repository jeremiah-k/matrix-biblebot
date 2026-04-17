# Trigger Policy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the loose boolean trigger system with a structured trigger-policy model (direct_only / smart / anywhere) that eliminates false positives from ambient chat while preserving convenient reference detection.

**Architecture:** New `triggers.py` module with pure-function API (`detect_trigger()`), enums (`TriggerMode`, `TriggerSource`), and a `TriggerMatch` dataclass. `bot.py` delegates all trigger detection to this module. Embedded matching loses chapter-only support. Legacy `detect_references_anywhere` maps to new modes with a deprecation warning.

**Tech Stack:** Python 3.10+, dataclasses, enum, re, existing bible.py regex infrastructure.

---

## File Structure

| Action | File                               | Responsibility                                                                                                                                                                |
| ------ | ---------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Create | `src/biblebot/triggers.py`         | TriggerMode enum, TriggerSource enum, TriggerMatch dataclass, detect_trigger(), \_try_direct_match(), \_try_embedded_match(), \_try_prefix_match(), \_extract_mention_body()  |
| Create | `tests/test_trigger_policy.py`     | All trigger policy tests                                                                                                                                                      |
| Modify | `src/biblebot/constants/bible.py`  | Add EMBEDDED_REFERENCE_PATTERNS (chapter:verse only), DEFAULT_COMMAND_PREFIX, trigger mode string constants                                                                   |
| Modify | `src/biblebot/constants/config.py` | Add CONFIG_TRIGGER_MODE, CONFIG_COMMAND_PREFIX                                                                                                                                |
| Modify | `src/biblebot/bot.py`              | Import triggers module; update **init** to read trigger_mode/command_prefix with legacy migration; replace inline trigger logic in on_room_message with detect_trigger() call |
| Modify | `sample_config.yaml`               | Add trigger_mode and command_prefix options                                                                                                                                   |
| Modify | `README.md`                        | Update trigger detection docs                                                                                                                                                 |
| Modify | `docs/CONFIGURATION.md`            | Replace detect_references_anywhere section with trigger policy docs                                                                                                           |

---

## Task 1: Update constants

**Files:**

- Modify: `src/biblebot/constants/bible.py`
- Modify: `src/biblebot/constants/config.py`

### constants/bible.py changes

Add to `__all__`:

- `"DEFAULT_COMMAND_PREFIX"`
- `"EMBEDDED_REFERENCE_PATTERNS"`
- `"TRIGGER_MODE_ANYWHERE"`
- `"TRIGGER_MODE_DIRECT_ONLY"`
- `"TRIGGER_MODE_SMART"`
- `"VALID_TRIGGER_MODES"`

Add these constants:

```python
DEFAULT_COMMAND_PREFIX = "!bible"

TRIGGER_MODE_DIRECT_ONLY = "direct_only"
TRIGGER_MODE_SMART = "smart"
TRIGGER_MODE_ANYWHERE = "anywhere"

VALID_TRIGGER_MODES = (TRIGGER_MODE_DIRECT_ONLY, TRIGGER_MODE_SMART, TRIGGER_MODE_ANYWHERE)

EMBEDDED_REFERENCE_PATTERNS = [
    re.compile(
        rf"\b(?P<book>{_PARTIAL_BOOK_PATTERN_STR})\s+(?P<ref>\d+:\d+(?:\s*[-\u2011-\u2015]\s*\d+)?)\s*(?P<translation>{_TX})?\b",
        re.IGNORECASE,
    ),
]
```

Note: EMBEDDED_REFERENCE_PATTERNS has ONLY the chapter:verse variant. NO chapter-only pattern. This is the key tightening.

### constants/config.py changes

Add to `__all__`:

- `"CONFIG_COMMAND_PREFIX"`
- `"CONFIG_TRIGGER_MODE"`

Add these constants:

```python
CONFIG_TRIGGER_MODE = "trigger_mode"
CONFIG_COMMAND_PREFIX = "command_prefix"
```

- [ ] **Step 1:** Edit `src/biblebot/constants/bible.py` to add the new constants and EMBEDDED_REFERENCE_PATTERNS.
- [ ] **Step 2:** Edit `src/biblebot/constants/config.py` to add CONFIG_TRIGGER_MODE and CONFIG_COMMAND_PREFIX.
- [ ] **Step 3:** Run `python -c "from biblebot.constants import VALID_TRIGGER_MODES, EMBEDDED_REFERENCE_PATTERNS, CONFIG_TRIGGER_MODE, CONFIG_COMMAND_PREFIX; print('OK')"` from the project root with `PYTHONPATH=src` to verify imports work.

---

## Task 2: Create triggers module

**Files:**

- Create: `src/biblebot/triggers.py`

This module exports: `TriggerMode`, `TriggerSource`, `TriggerMatch`, `detect_trigger`.

```python
"""Trigger policy module for BibleBot.

Encapsulates all scripture reference detection logic. The main entry point is
detect_trigger(), which takes message content and bot configuration and returns
a TriggerMatch when a valid reference is found, or None otherwise.
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum

from biblebot.constants.bible import (
    DEFAULT_COMMAND_PREFIX,
    DEFAULT_TRANSLATION,
    EMBEDDED_REFERENCE_PATTERNS,
    REFERENCE_PATTERNS,
    TRIGGER_MODE_ANYWHERE,
    TRIGGER_MODE_DIRECT_ONLY,
    TRIGGER_MODE_SMART,
)
from biblebot.validation import validate_and_normalize_book_name


class TriggerMode(str, Enum):
    DIRECT_ONLY = TRIGGER_MODE_DIRECT_ONLY
    SMART = TRIGGER_MODE_SMART
    ANYWHERE = TRIGGER_MODE_ANYWHERE


class TriggerSource(str, Enum):
    DIRECT = "direct"
    MENTION = "mention"
    PREFIX = "prefix"
    ANYWHERE = "anywhere"


@dataclass(frozen=True)
class TriggerMatch:
    passage: str
    translation: str
    source: TriggerSource


_MENTION_LINK_RE = re.compile(
    r'<a\s+href="https?://matrix\.to/#/(?P<mxid>@[^"]+)"[^>]*>.*?</a>'
)

_MENTION_BOUNDARY_RE = re.compile(r"^[\s\W]|$")


def _match_reference(
    text: str,
    patterns: Sequence[re.Pattern],
    method: str,
    default_translation: str,
) -> tuple[str, str] | None:
    for pattern in patterns:
        match = getattr(pattern, method)(text)
        if not match:
            continue
        raw_book = match.group("book").strip()
        if not raw_book:
            continue
        book_name = validate_and_normalize_book_name(raw_book)
        if not book_name:
            continue
        verse_ref = match.group("ref").strip()
        passage = f"{book_name} {verse_ref}"
        trans_group = match.groupdict().get("translation")
        translation = trans_group.lower() if trans_group else default_translation
        return passage, translation
    return None


def _try_direct_match(
    body: str, default_translation: str
) -> tuple[str, str] | None:
    return _match_reference(body, REFERENCE_PATTERNS, "fullmatch", default_translation)


def _try_embedded_match(
    body: str, default_translation: str
) -> tuple[str, str] | None:
    return _match_reference(
        body, EMBEDDED_REFERENCE_PATTERNS, "search", default_translation
    )


def _try_prefix_match(
    body: str, prefix: str, default_translation: str
) -> tuple[str, str] | None:
    if not prefix:
        return None
    if not body.startswith(prefix):
        return None
    remainder = body[len(prefix):].strip()
    if not remainder:
        return None
    return _try_direct_match(remainder, default_translation)


def _extract_mention_body(
    body: str, formatted_body: str | None, bot_mxid: str | None
) -> str | None:
    if not bot_mxid:
        return None

    if formatted_body:
        for m in _MENTION_LINK_RE.finditer(formatted_body):
            if m.group("mxid") == bot_mxid:
                link_text = m.group(0)
                plain = re.sub(r"<[^>]+>", "", link_text).strip()
                if plain and plain in body:
                    idx = body.index(plain)
                    remainder = (body[:idx] + body[idx + len(plain) :]).strip()
                    if remainder:
                        return remainder
                return None

    localpart = bot_mxid.lstrip("@").split(":")[0]
    candidates = [bot_mxid, f"@{localpart}"]

    for candidate in candidates:
        if not body.startswith(candidate):
            continue
        after = body[len(candidate) :]
        if not after:
            return None
        if not _MENTION_BOUNDARY_RE.match(after):
            continue
        remainder = after.strip()
        if remainder:
            return remainder
        return None

    return None


def detect_trigger(
    body: str,
    formatted_body: str | None,
    trigger_mode: TriggerMode,
    command_prefix: str | None,
    bot_mxid: str | None,
    default_translation: str,
) -> TriggerMatch | None:
    if not body or not body.strip():
        return None

    if trigger_mode == TriggerMode.DIRECT_ONLY:
        result = _try_direct_match(body, default_translation)
        if result:
            return TriggerMatch(passage=result[0], translation=result[1], source=TriggerSource.DIRECT)
        return None

    if trigger_mode == TriggerMode.SMART:
        result = _try_direct_match(body, default_translation)
        if result:
            return TriggerMatch(passage=result[0], translation=result[1], source=TriggerSource.DIRECT)

        if command_prefix:
            result = _try_prefix_match(body, command_prefix, default_translation)
            if result:
                return TriggerMatch(passage=result[0], translation=result[1], source=TriggerSource.PREFIX)

        mention_body = _extract_mention_body(body, formatted_body, bot_mxid)
        if mention_body:
            result = _try_direct_match(mention_body, default_translation)
            if result:
                return TriggerMatch(passage=result[0], translation=result[1], source=TriggerSource.MENTION)

        return None

    if trigger_mode == TriggerMode.ANYWHERE:
        result = _try_direct_match(body, default_translation)
        if result:
            return TriggerMatch(passage=result[0], translation=result[1], source=TriggerSource.DIRECT)

        if command_prefix:
            result = _try_prefix_match(body, command_prefix, default_translation)
            if result:
                return TriggerMatch(passage=result[0], translation=result[1], source=TriggerSource.PREFIX)

        mention_body = _extract_mention_body(body, formatted_body, bot_mxid)
        if mention_body:
            result = _try_direct_match(mention_body, default_translation)
            if result:
                return TriggerMatch(passage=result[0], translation=result[1], source=TriggerSource.MENTION)

        result = _try_embedded_match(body, default_translation)
        if result:
            return TriggerMatch(passage=result[0], translation=result[1], source=TriggerSource.ANYWHERE)

        return None

    return None
```

- [ ] **Step 1:** Create `src/biblebot/triggers.py` with the complete module content above.
- [ ] **Step 2:** Run `python -c "from biblebot.triggers import detect_trigger, TriggerMode, TriggerMatch, TriggerSource; print('OK')"` from project root with `PYTHONPATH=src`.

---

## Task 3: Integrate triggers into bot.py

**Files:**

- Modify: `src/biblebot/bot.py`

### Changes in imports section (around line 66-86)

Add import:

```python
from biblebot.triggers import TriggerMode, TriggerSource, detect_trigger
```

Add import of new config constants:

```python
from biblebot.constants.config import (
    CONFIG_COMMAND_PREFIX,
    CONFIG_TRIGGER_MODE,
    # ... keep existing imports ...
)
```

Add import of new bible constants:

```python
from biblebot.constants.bible import (
    DEFAULT_COMMAND_PREFIX,
    # ... keep existing imports ...
)
```

### Changes in BibleBot.**init** (around line 615-622)

Replace the current detect_references_anywhere block with trigger mode logic:

```python
        raw_detect_anywhere = bot_settings.get(CONFIG_DETECT_REFERENCES_ANYWHERE, None)
        raw_trigger_mode = bot_settings.get(CONFIG_TRIGGER_MODE, None)

        if raw_trigger_mode is not None:
            mode_str = str(raw_trigger_mode).lower().strip()
            if mode_str in (TRIGGER_MODE_DIRECT_ONLY, TRIGGER_MODE_SMART, TRIGGER_MODE_ANYWHERE):
                self.trigger_mode = TriggerMode(mode_str)
            else:
                logger.warning(
                    f"Invalid trigger_mode '{raw_trigger_mode}', falling back to '{TRIGGER_MODE_DIRECT_ONLY}'"
                )
                self.trigger_mode = TriggerMode.DIRECT_ONLY
        elif raw_detect_anywhere is not None:
            anywhere = str(raw_detect_anywhere).lower().strip() in {
                "true", "yes", "1", "on",
            }
            self.trigger_mode = TriggerMode.ANYWHERE if anywhere else TriggerMode.DIRECT_ONLY
            logger.warning(
                "detect_references_anywhere is deprecated; use trigger_mode instead. "
                f"Mapped {raw_detect_anywhere!r} to trigger_mode={self.trigger_mode.value}"
            )
        else:
            self.trigger_mode = TriggerMode.DIRECT_ONLY

        self.detect_references_anywhere = self.trigger_mode == TriggerMode.ANYWHERE

        raw_prefix = bot_settings.get(CONFIG_COMMAND_PREFIX, DEFAULT_COMMAND_PREFIX)
        self.command_prefix = raw_prefix if raw_prefix else None
```

### Changes in on_room_message (lines 988-1064)

Replace the entire pattern-selection and matching block with:

```python
    async def on_room_message(self, room: MatrixRoom, event: RoomMessageText):
        logger.debug(
            f"Received RoomMessageText in room {room.room_id} from {event.sender}: "
            f"encrypted={room.encrypted}, decrypted={getattr(event, 'decrypted', False)}"
        )

        if (
            room.room_id in self._room_id_set
            and event.sender != self.client.user_id
            and event.server_timestamp > self.start_time
        ):
            formatted_body = getattr(event, "formatted_body", None)
            match = detect_trigger(
                body=event.body,
                formatted_body=formatted_body,
                trigger_mode=self.trigger_mode,
                command_prefix=self.command_prefix,
                bot_mxid=self.client.user_id,
                default_translation=self.default_translation,
            )

            if match:
                logger.info(
                    f"Detected Bible reference ({match.source.value}): {match.passage} "
                    f"({match.translation}) in room {room.room_id}"
                )
                await self.handle_scripture_command(
                    room.room_id, match.passage, match.translation, event
                )
```

Also need to add the `TRIGGER_MODE_DIRECT_ONLY, TRIGGER_MODE_SMART, TRIGGER_MODE_ANYWHERE` imports from `biblebot.constants.bible` in the existing bible imports block.

And remove the now-unused `PARTIAL_REFERENCE_PATTERNS` import since it's no longer used directly in bot.py.

- [ ] **Step 1:** Update imports in `src/biblebot/bot.py`.
- [ ] **Step 2:** Replace the detect_references_anywhere block in `__init__` with trigger_mode logic.
- [ ] **Step 3:** Replace `on_room_message` method body with detect_trigger() delegation.
- [ ] **Step 4:** Run `python -c "from biblebot.bot import BibleBot; print('OK')"` with `PYTHONPATH=src`.

---

## Task 4: Create comprehensive tests

**Files:**

- Create: `tests/test_trigger_policy.py`

Test file should cover all required scenarios. Use MagicMock for events/rooms, patch `handle_scripture_command` with AsyncMock.

```python
"""Tests for the trigger policy system."""

import warnings
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from biblebot.bot import BibleBot
from biblebot.constants.bible import DEFAULT_TRANSLATION
from biblebot.triggers import (
    TriggerMatch,
    TriggerMode,
    TriggerSource,
    detect_trigger,
    _extract_mention_body,
    _try_direct_match,
    _try_embedded_match,
    _try_prefix_match,
)


def _make_bot(trigger_mode=TriggerMode.DIRECT_ONLY, command_prefix="!bible",
              default_translation="kjv", bot_mxid="@bot:example.org"):
    cfg = {
        "matrix_room_ids": ["!test:example.org"],
        "bot": {
            "trigger_mode": trigger_mode if isinstance(trigger_mode, str) else trigger_mode.value,
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


# ===== Unit tests for detect_trigger =====

class TestDirectOnly:
    def test_exact_chapter_verse(self):
        result = detect_trigger("John 3:16", None, TriggerMode.DIRECT_ONLY, "!bible", "@bot:x", "kjv")
        assert result is not None
        assert result.passage == "John 3:16"
        assert result.source == TriggerSource.DIRECT

    def test_exact_chapter_only(self):
        result = detect_trigger("Psalm 23", None, TriggerMode.DIRECT_ONLY, "!bible", "@bot:x", "kjv")
        assert result is not None
        assert result.passage == "Psalms 23"
        assert result.source == TriggerSource.DIRECT

    def test_embedded_reference_rejected(self):
        result = detect_trigger("show me John 3:16 please", None, TriggerMode.DIRECT_ONLY, "!bible", "@bot:x", "kjv")
        assert result is None

    def test_prefix_rejected(self):
        result = detect_trigger("!bible John 3:16", None, TriggerMode.DIRECT_ONLY, "!bible", "@bot:x", "kjv")
        assert result is None

    def test_mention_rejected(self):
        result = detect_trigger("@bot:example.org John 3:16", None, TriggerMode.DIRECT_ONLY, "!bible", "@bot:example.org", "kjv")
        assert result is None

    def test_empty_body(self):
        result = detect_trigger("", None, TriggerMode.DIRECT_ONLY, "!bible", "@bot:x", "kjv")
        assert result is None

    def test_translation_suffix(self):
        result = detect_trigger("John 3:16 esv", None, TriggerMode.DIRECT_ONLY, "!bible", "@bot:x", "kjv")
        assert result is not None
        assert result.translation == "esv"


class TestSmartMode:
    def test_exact_reference_triggers(self):
        result = detect_trigger("John 3:16", None, TriggerMode.SMART, "!bible", "@bot:x", "kjv")
        assert result is not None
        assert result.passage == "John 3:16"
        assert result.source == TriggerSource.DIRECT

    def test_mention_with_reference_via_formatted_body(self):
        fb = '<a href="https://matrix.to/#/@bot:x">@bot</a> Psalm 23'
        result = detect_trigger("@bot Psalm 23", fb, TriggerMode.SMART, "!bible", "@bot:x", "kjv")
        assert result is not None
        assert result.passage == "Psalms 23"
        assert result.source == TriggerSource.MENTION

    def test_mention_with_reference_via_plain_mxid(self):
        body = "@bot:example.org John 3:16"
        result = detect_trigger(body, None, TriggerMode.SMART, "!bible", "@bot:example.org", "kjv")
        assert result is not None
        assert "John 3:16" in result.passage
        assert result.source == TriggerSource.MENTION

    def test_prefix_with_reference(self):
        result = detect_trigger("!bible Psalm 23", None, TriggerMode.SMART, "!bible", "@bot:x", "kjv")
        assert result is not None
        assert result.passage == "Psalms 23"
        assert result.source == TriggerSource.PREFIX

    def test_prefix_with_translation(self):
        result = detect_trigger("!bible John 3:16 esv", None, TriggerMode.SMART, "!bible", "@bot:x", "kjv")
        assert result is not None
        assert result.passage == "John 3:16"
        assert result.translation == "esv"
        assert result.source == TriggerSource.PREFIX

    def test_ambient_embedded_rejected(self):
        result = detect_trigger("Have you read John 3:16 today?", None, TriggerMode.SMART, "!bible", "@bot:x", "kjv")
        assert result is None

    def test_devotional_text_rejected(self):
        result = detect_trigger(
            "The Lord is my shepherd, I shall not want. Psalm 23 is so comforting.",
            None, TriggerMode.SMART, "!bible", "@bot:x", "kjv"
        )
        assert result is None

    def test_prefix_disabled_when_null(self):
        result = detect_trigger("!bible Psalm 23", None, TriggerMode.SMART, None, "@bot:x", "kjv")
        assert result is None


class TestAnywhereMode:
    def test_embedded_chapter_verse_triggers(self):
        result = detect_trigger(
            "Have you read John 3:16 today?",
            None, TriggerMode.ANYWHERE, "!bible", "@bot:x", "kjv"
        )
        assert result is not None
        assert "John 3:16" in result.passage
        assert result.source == TriggerSource.ANYWHERE

    def test_embedded_chapter_only_rejected(self):
        result = detect_trigger(
            "1 Thessalonians 4 16 For the Lord himself will descend...",
            None, TriggerMode.ANYWHERE, "!bible", "@bot:x", "kjv"
        )
        assert result is None

    def test_standalone_chapter_only_works(self):
        result = detect_trigger("Psalm 23", None, TriggerMode.ANYWHERE, "!bible", "@bot:x", "kjv")
        assert result is not None
        assert result.passage == "Psalms 23"
        assert result.source == TriggerSource.DIRECT

    def test_standalone_chapter_verse_works(self):
        result = detect_trigger("John 3:16", None, TriggerMode.ANYWHERE, "!bible", "@bot:x", "kjv")
        assert result is not None
        assert result.source == TriggerSource.DIRECT

    def test_false_positive_thessalonians(self):
        result = detect_trigger(
            "1 Thessalonians 4 16 says something important",
            None, TriggerMode.ANYWHERE, "!bible", "@bot:x", "kjv"
        )
        assert result is None

    def test_embedded_with_translation(self):
        result = detect_trigger(
            "Check out John 3:16 esv everyone",
            None, TriggerMode.ANYWHERE, "!bible", "@bot:x", "kjv"
        )
        assert result is not None
        assert result.translation == "esv"


class TestPrefixCustomization:
    def test_custom_prefix(self):
        result = detect_trigger("!verse John 3:16", None, TriggerMode.SMART, "!verse", "@bot:x", "kjv")
        assert result is not None
        assert result.source == TriggerSource.PREFIX

    def test_wrong_prefix_no_match(self):
        result = detect_trigger("!wrong John 3:16", None, TriggerMode.SMART, "!bible", "@bot:x", "kjv")
        assert result is None

    def test_empty_prefix_disables(self):
        result = detect_trigger("!bible John 3:16", None, TriggerMode.SMART, "", "@bot:x", "kjv")
        assert result is None

    def test_none_prefix_disables(self):
        result = detect_trigger("!bible John 3:16", None, TriggerMode.SMART, None, "@bot:x", "kjv")
        assert result is None


class TestLegacyMigration:
    def test_detect_anywhere_true_maps_to_anywhere(self):
        cfg = {
            "matrix_room_ids": ["!test:example.org"],
            "bot": {"detect_references_anywhere": True},
        }
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            bot = BibleBot(cfg)
            assert bot.trigger_mode == TriggerMode.ANYWHERE
            assert bot.detect_references_anywhere is True
            assert any("deprecated" in str(warning.message).lower() for warning in w)

    def test_detect_anywhere_false_maps_to_direct_only(self):
        cfg = {
            "matrix_room_ids": ["!test:example.org"],
            "bot": {"detect_references_anywhere": False},
        }
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
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
    """Integration tests using BibleBot.on_room_message."""

    @pytest.mark.asyncio
    async def test_direct_only_exact_triggers(self):
        bot = _make_bot(TriggerMode.DIRECT_ONLY)
        with patch.object(bot, "handle_scripture_command", new_callable=AsyncMock) as m:
            await bot.on_room_message(_make_room(), _make_event("John 3:16"))
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
            await bot.on_room_message(_make_room(), _make_event("@bot Psalm 23", formatted_body=fb))
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
            await bot.on_room_message(_make_room(), _make_event("The Lord is my shepherd. Psalm 23 is great."))
            m.assert_not_called()

    @pytest.mark.asyncio
    async def test_anywhere_embedded_verse_triggers(self):
        bot = _make_bot(TriggerMode.ANYWHERE)
        with patch.object(bot, "handle_scripture_command", new_callable=AsyncMock) as m:
            await bot.on_room_message(_make_room(), _make_event("Check John 3:16 ESV for context"))
            m.assert_called_once()

    @pytest.mark.asyncio
    async def test_anywhere_embedded_chapter_only_rejected(self):
        bot = _make_bot(TriggerMode.ANYWHERE)
        with patch.object(bot, "handle_scripture_command", new_callable=AsyncMock) as m:
            await bot.on_room_message(_make_room(), _make_event("1 Thessalonians 4 16 says the Lord descends"))
            m.assert_not_called()

    @pytest.mark.asyncio
    async def test_devotional_text_rejected_in_smart(self):
        bot = _make_bot(TriggerMode.SMART)
        with patch.object(bot, "handle_scripture_command", new_callable=AsyncMock) as m:
            await bot.on_room_message(_make_room(), _make_event("Psalm 23 is my favorite chapter"))
            m.assert_not_called()
```

- [ ] **Step 1:** Create `tests/test_trigger_policy.py` with all test classes above.
- [ ] **Step 2:** Run `python -m pytest tests/test_trigger_policy.py -v` and verify all tests pass.

---

## Task 5: Update documentation

**Files:**

- Modify: `sample_config.yaml`
- Modify: `README.md`
- Modify: `docs/CONFIGURATION.md`

### sample_config.yaml changes

Replace the `detect_references_anywhere` section in the bot config comments with:

```yaml
#   # How the bot detects scripture references (default: direct_only)
#   # - direct_only: Only respond when the whole message is a reference ("John 3:16")
#   # - smart: Also respond to mentions (@Bot John 3:16) and prefix commands (!bible John 3:16)
#   # - anywhere: Detect references embedded in any message (useful for bridges)
#   trigger_mode: direct_only
#
#   # Command prefix for scripture lookups (default: "!bible")
#   # Set to null or empty string to disable prefix commands.
#   # Only used when trigger_mode is "smart".
#   command_prefix: "!bible"
#
#   # DEPRECATED: Use trigger_mode instead.
#   # detect_references_anywhere: false
```

### README.md changes

In the "Supported Reference Formats" section, add a note about trigger modes:

After the existing table, add a brief paragraph:

````markdown
### Trigger Modes

The bot supports three trigger modes that control how aggressively it responds:

| Mode                    | Behavior                                                                             |
| ----------------------- | ------------------------------------------------------------------------------------ |
| `direct_only` (default) | Only responds when the entire message is a scripture reference                       |
| `smart`                 | Also responds to mentions (`@Bot Psalm 23`) and prefix commands (`!bible John 3:16`) |
| `anywhere`              | Detects references embedded in any message (useful with Matrix bridges)              |

Configure in `config.yaml`:

```yaml
bot:
  trigger_mode: smart
  command_prefix: "!bible"
```
````

`````markdown
### docs/CONFIGURATION.md changes

Replace the "### Reference Detection" section (lines 195-208) with:

````markdown
### Reference Detection (Trigger Mode)

Control how the bot detects Bible references:

```yaml
bot:
  trigger_mode: direct_only # Options: direct_only, smart, anywhere
  command_prefix: "!bible" # Prefix for commands (only in smart mode)
```
````

#### Trigger Modes

| Mode          | Whole-message reference | Mention (`@Bot`) | Prefix (`!bible`) |     Embedded in text     |
| ------------- | :---------------------: | :--------------: | :---------------: | :----------------------: |
| `direct_only` |           Yes           |        No        |        No         |            No            |
| `smart`       |           Yes           |       Yes        |        Yes        |            No            |
| `anywhere`    |           Yes           |       Yes        |        Yes        | Yes (chapter:verse only) |

**`direct_only`** (default): The bot only responds when the entire message is a scripture reference. For example, sending "John 3:16" triggers a response, but "show me John 3:16" does not.

**`smart`**: In addition to whole-message references, the bot responds when:

- Mentioned: `@BotName Psalm 23`
- Prefixed: `!bible John 3:16`

It does **not** scan ambient messages for embedded references, making it safe for active chat rooms.

**`anywhere`**: The bot detects references embedded in any message. Embedded matching requires a chapter:verse reference (e.g., "John 3:16") and will not match chapter-only references (e.g., "Psalm 23" embedded in text). This prevents false positives like "1 Thessalonians 4 16 ..." being matched as chapter 4.

#### Command Prefix

Configure the prefix for scripture commands (default: `!bible`):

```yaml
bot:
  command_prefix: "!bible" # or "!verse", null to disable
```

- Only used when `trigger_mode` is `smart`
- Set to `null` or empty string to disable prefix commands
- Treated as a literal string, not a regex

#### Migration from detect_references_anywhere

The `detect_references_anywhere` option is deprecated. The bot will automatically map:

| Old value | New trigger_mode |
| --------- | ---------------- |
| `false`   | `direct_only`    |
| `true`    | `anywhere`       |

A deprecation warning is logged when `detect_references_anywhere` is used. Update your config to use `trigger_mode` instead.
`````

- [ ] **Step 1:** Update `sample_config.yaml` with new trigger_mode and command_prefix options.
- [ ] **Step 2:** Update `README.md` with trigger modes section.
- [ ] **Step 3:** Update `docs/CONFIGURATION.md` with comprehensive trigger policy docs.

---

## Task 6: Run existing tests to verify no regressions

- [ ] **Step 1:** Run `python -m pytest tests/ -v --tb=short` and verify existing tests still pass.
- [ ] **Step 2:** If any tests fail, fix them (most likely: tests that directly set `detect_references_anywhere` on config now need to go through the legacy migration path, or tests that import `PARTIAL_REFERENCE_PATTERNS` from bot.py).

---

## Self-Review Checklist

1. **Spec coverage:** All 10 design requirements mapped to tasks.
   - Req 1 (replace boolean): Task 2 + Task 3
   - Req 2 (minimal config): Task 1 + Task 5
   - Req 3 (trigger modes): Task 2
   - Req 4 (mode semantics): Task 2
   - Req 5 (prefix): Task 2
   - Req 6 (mention): Task 2
   - Req 7 (no chapter-only embedded): Task 1 (EMBEDDED_REFERENCE_PATTERNS)
   - Req 8 (preserve direct refs): Task 2
   - Req 9 (backward compat): Task 3
   - Req 10 (clean decomposition): Task 2

2. **Placeholder scan:** No TBD/TODO/fill-in-details found.

3. **Type consistency:** TriggerMode enum values match string constants. TriggerMatch fields consistent across all usage. detect_trigger signature matches bot.py call site.
