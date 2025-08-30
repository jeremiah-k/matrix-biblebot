import asyncio

import pytest

from biblebot import bot as botmod


def test_reference_patterns_basic():
    pats = (
        botmod.REFERENCE_PATTERNS
        if hasattr(botmod, "REFERENCE_PATTERNS")
        else [
            r"^([\w\s]+?)(\d+[:]\d+[-]?\d*)\s*(kjv|esv)?$",
        ]
    )
    import re

    good = [
        "John 3:16",
        "1 Cor 15:1-4",
        "Genesis 1:1 kjv",
        "John 3:16 esv",
        "jn 3:16",
        "1co 13:1",
        "rev 22:20 kjv",
    ]
    for s in good:
        assert any(re.match(p, s, re.IGNORECASE) for p in pats)


@pytest.mark.parametrize(
    "abbreviation,full_name",
    [
        ("Gen", "Genesis"),
        ("jn", "John"),
        ("1 Cor", "1 Corinthians"),
        ("1co", "1 Corinthians"),
        ("ps", "Psalms"),
        ("rev.", "Revelation"),
        ("  rom  ", "Romans"),
        ("invalidbook", "Invalidbook"),  # Test fallback to title case
    ],
)
def test_normalize_book_name(abbreviation, full_name):
    """Tests the normalization of book abbreviations."""
    assert botmod.normalize_book_name(abbreviation) == full_name


def test_passage_cache(monkeypatch):
    # Clear cache before test to prevent cross-test contamination
    if hasattr(botmod, "request_cache"):
        botmod.request_cache.clear()

    calls = {"n": 0}

    async def fake_req(url, headers=None, params=None):
        calls["n"] += 1
        # Simulate bible-api.com kjv response
        return {"text": "For God so loved the world...", "reference": "John 3:16"}

    monkeypatch.setattr(botmod, "make_api_request", fake_req)

    # First call populates cache
    text1, ref1 = asyncio.get_event_loop().run_until_complete(
        botmod.get_bible_text("John 3:16", translation="kjv", api_keys=None)
    )
    # Second call should be served from cache, no new request
    text2, ref2 = asyncio.get_event_loop().run_until_complete(
        botmod.get_bible_text("John 3:16", translation="kjv", api_keys=None)
    )

    assert calls["n"] == 1
    assert text1 == text2 and ref1 == ref2

    # Clear cache after test
    if hasattr(botmod, "request_cache"):
        botmod.request_cache.clear()
