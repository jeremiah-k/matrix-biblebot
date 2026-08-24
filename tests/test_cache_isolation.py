"""Regression coverage for passage-cache isolation between tests."""

from biblebot import passages


def test_1_populates_process_global_passage_cache():
    passages._passage_cache[("John 3:16", "kjv")] = (0.0, ("cached", "John 3:16"))

    assert passages._passage_cache


def test_2_passage_cache_starts_empty():
    assert not passages._passage_cache
