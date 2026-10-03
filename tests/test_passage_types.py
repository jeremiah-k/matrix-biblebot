"""Tests pinning the public type contract for passage lookup functions."""

from __future__ import annotations

import asyncio
from typing import get_type_hints

import pytest

from biblebot.bot import (
    APIKeyMissing,
    PassageNotFound,
    get_bible_text,
    get_esv_text,
    get_kjv_text,
)


def _has_return_annotation(func) -> bool:
    try:
        hints = get_type_hints(func)
    except Exception:
        return False
    return "return" in hints


def test_get_bible_text_has_return_annotation():
    assert _has_return_annotation(
        get_bible_text
    ), "get_bible_text must declare a return annotation"


def test_get_esv_text_has_return_annotation():
    assert _has_return_annotation(
        get_esv_text
    ), "get_esv_text must declare a return annotation"


def test_get_kjv_text_has_return_annotation():
    assert _has_return_annotation(
        get_kjv_text
    ), "get_kjv_text must declare a return annotation"


def test_get_bible_text_return_annotation_allows_none_reference():
    """The canonical reference returned by the upstream API may be None.

    Callers like ``BibleBot.handle_scripture_command`` pass it to
    ``trim_reference_for_suffix`` which expects ``str | None``.
    """
    hints = get_type_hints(get_bible_text)
    return_hint = str(hints["return"])
    assert (
        "None" in return_hint
    ), f"get_bible_text return annotation must allow a None reference; got {return_hint!r}"


def test_get_esv_text_return_annotation_allows_none_reference():
    hints = get_type_hints(get_esv_text)
    assert "None" in str(
        hints["return"]
    ), f"get_esv_text return annotation must allow a None reference; got {hints['return']!r}"


def test_get_kjv_text_return_annotation_allows_none_reference():
    hints = get_type_hints(get_kjv_text)
    assert "None" in str(
        hints["return"]
    ), f"get_kjv_text return annotation must allow a None reference; got {hints['return']!r}"


def test_passage_exceptions_are_distinct_and_inherit_exception():
    assert issubclass(PassageNotFound, Exception)
    assert issubclass(APIKeyMissing, Exception)
    assert PassageNotFound is not APIKeyMissing


def test_get_esv_text_missing_api_key_raises_documented_exception():
    """A missing API key must raise APIKeyMissing with the passage in the message."""

    async def _check():
        await get_esv_text("John 3:16", api_key=None)

    with pytest.raises(APIKeyMissing) as exc_info:
        asyncio.run(_check())
    assert "John 3:16" in str(exc_info.value)
    assert "ESV API key" in str(exc_info.value)


def test_get_bible_text_unsupported_translation_raises_documented_exception():
    """An unsupported translation must raise PassageNotFound with an explanatory message."""

    async def _check() -> tuple[str, str]:
        return await get_bible_text(
            "John 3:16",
            translation="niv",
            api_keys=None,
            cache_enabled=False,
            default_translation="kjv",
            session=None,
        )

    with pytest.raises(PassageNotFound) as exc_info:
        asyncio.run(_check())
    assert "Unsupported translation" in str(exc_info.value)


@pytest.mark.parametrize(
    "response", [None, [], 17, "text", {"text": []}, {"text": 17}, {"text": "  "}]
)
async def test_kjv_malformed_payload_raises_lookup_error(monkeypatch, response):
    from unittest.mock import AsyncMock

    from biblebot import passages

    monkeypatch.setattr(passages, "make_api_request", AsyncMock(return_value=response))
    with pytest.raises(PassageNotFound):
        await get_kjv_text("John 3:16")


@pytest.mark.parametrize(
    "response",
    [
        None,
        [],
        {"passages": "text"},
        {"passages": [17]},
        {"passages": [None]},
        {"passages": ["  "]},
    ],
)
async def test_esv_malformed_payload_raises_lookup_error(monkeypatch, response):
    from unittest.mock import AsyncMock

    from biblebot import passages

    monkeypatch.setattr(passages, "make_api_request", AsyncMock(return_value=response))
    with pytest.raises(PassageNotFound):
        await get_esv_text("John 3:16", "key")


@pytest.mark.parametrize("key", [None, "", "   "])
async def test_esv_empty_key_never_requests_network(monkeypatch, key):
    from unittest.mock import AsyncMock

    from biblebot import passages

    request = AsyncMock()
    monkeypatch.setattr(passages, "make_api_request", request)
    with pytest.raises(APIKeyMissing):
        await get_esv_text("John 3:16", key)
    request.assert_not_awaited()


async def test_invalid_optional_reference_is_normalized_before_caching(monkeypatch):
    from unittest.mock import AsyncMock

    from biblebot import passages

    request = AsyncMock(return_value={"text": " verse ", "reference": ["invalid"]})
    monkeypatch.setattr(passages, "make_api_request", request)
    assert await get_bible_text("John 3:16", "kjv") == ("verse", None)
    assert await get_bible_text("John 3:16", "kjv") == ("verse", None)
    request.assert_awaited_once()


def test_replacing_cache_entry_refreshes_lru_order(monkeypatch):
    from biblebot import passages

    monkeypatch.setattr(passages, "_PASSAGE_CACHE_MAX", 2)
    passages._cache_set("John 1:1", "kjv", ("first", None))
    passages._cache_set("John 1:2", "kjv", ("second", None))
    passages._cache_set("John 1:1", "kjv", ("refreshed", None))
    passages._cache_set("John 1:3", "kjv", ("third", None))
    assert passages._cache_get("John 1:1", "kjv") == ("refreshed", None)
    assert passages._cache_get("John 1:2", "kjv") is None
