import pytest

from biblebot import bot as botmod
from biblebot.cli import run_async


def test_reference_patterns_basic():
    """
    Verify that the configured reference patterns match common Bible reference strings.

    Uses botmod.REFERENCE_PATTERNS when available, otherwise falls back to a default regex list.
    For each example reference (e.g., "John 3:16", "1 Cor 15:1-4", "Genesis 1:1 kjv"), the test attempts
    matching with every pattern. Patterns may be compiled regex objects or plain pattern strings;
    both forms are supported. The test asserts that at least one pattern matches each example.
    """
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
        # Handle both compiled patterns and string patterns
        matches = []
        for p in pats:
            if hasattr(p, "match"):  # Compiled pattern
                matches.append(p.match(s))
            else:  # String pattern
                matches.append(re.match(p, s, re.IGNORECASE))
        assert any(matches)


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
        ("1jn", "1 John"),  # Edge case: compact John abbreviation
        ("2jn", "2 John"),  # Edge case: compact 2 John abbreviation
        ("3jn", "3 John"),  # Edge case: compact 3 John abbreviation
        ("1 john", "1 John"),  # Edge case: spaced variant
    ],
)
def test_validate_and_normalize_book_name_valid(abbreviation, full_name):
    """
    Assert that a valid book abbreviation normalizes to the expected full book name.

    The test passes the given abbreviation (which may include extra whitespace, punctuation, numeric prefixes like "1", and varying case) to validate_and_normalize_book_name and verifies the returned canonical book name equals full_name.
    """
    assert botmod.validate_and_normalize_book_name(abbreviation) == full_name


@pytest.mark.parametrize(
    "invalid_book",
    [
        "invalidbook",
        "xyz",
        "notabook",
        "",
        "   ",
    ],
)
def test_validate_and_normalize_book_name_invalid(invalid_book):
    """
    Assert that invalid book names return None.

    The test passes invalid book names to validate_and_normalize_book_name and verifies that None is returned.
    """
    assert botmod.validate_and_normalize_book_name(invalid_book) is None


def test_passage_cache(monkeypatch):
    # Clear cache before test to prevent cross-test contamination
    """
    Verify that get_bible_text caches API responses and avoids redundant external requests.

    This test clears any existing passage cache, monkeypatches botmod.make_api_request with an async
    fake that increments a counter and returns a deterministic payload for "John 3:16", then calls
    botmod.get_bible_text twice for the same passage. It asserts the external request was made only
    once and that both calls returned identical text and reference. The passage cache is cleared on
    setup and teardown to avoid cross-test contamination.
    """
    if hasattr(botmod, "_passage_cache"):
        botmod._passage_cache.clear()

    calls = {"n": 0}

    async def fake_req(_url, *_args, **_kwargs):
        """
        Test helper that simulates an async HTTP request to a Bible API.

        Increments the outer `calls["n"]` counter and returns a fixed payload mimicking a kjv
        response: a dict with "text" and "reference" keys (e.g., John 3:16). Intended for use
        in tests that need a predictable async API response and to verify caching or call counts.

        Parameters:
            url (str): Requested URL (ignored).
            headers (dict|None): Request headers (ignored).
            params (dict|None): Query parameters (ignored).
            session: HTTP session (ignored).
            timeout: Request timeout (ignored).

        Returns:
            dict: Fixed response payload with keys "text" and "reference".
        """
        calls["n"] += 1
        # Simulate bible-api.com kjv response
        return {"text": "For God so loved the world...", "reference": "John 3:16"}

    monkeypatch.setattr(botmod, "make_api_request", fake_req)

    try:
        # First call populates cache
        text1, ref1 = run_async(
            botmod.get_bible_text("John 3:16", translation="kjv", api_keys=None)
        )
        # Second call should be served from cache, no new request
        text2, ref2 = run_async(
            botmod.get_bible_text("John 3:16", translation="kjv", api_keys=None)
        )

        assert calls["n"] == 1
        assert text1 == text2 and ref1 == ref2
    finally:
        # Clear cache after test
        if hasattr(botmod, "_passage_cache"):
            botmod._passage_cache.clear()
