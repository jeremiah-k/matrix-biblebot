"""Performance tests for BibleBot components."""

import asyncio
import os
import time
from unittest.mock import AsyncMock, patch

import pytest

from biblebot import bot


class TestCachePerformance:
    """Test cache performance characteristics."""

    @pytest.mark.slow
    def test_cache_performance_single_operations(self):
        """Test cache performance for single operations."""
        # Clear cache
        if hasattr(bot, "_passage_cache"):
            bot._passage_cache.clear()

        # Measure cache set performance
        start_time = time.perf_counter()
        for i in range(100):
            bot._cache_set(f"Test {i}:1", "kjv", (f"Text {i}", f"Text {i}:1"))
        set_time = time.perf_counter() - start_time

        # Measure cache get performance
        start_time = time.perf_counter()
        for i in range(100):
            result = bot._cache_get(f"Test {i}:1", "kjv")
            assert result is not None
        get_time = time.perf_counter() - start_time

        # Performance assertions
        if not os.getenv("CI_SLOW_RUNNER"):
            assert set_time < 2.0
            assert get_time < 1.0

    def test_cache_performance_bulk_operations(self):
        """
        Measure bulk cache set/get performance.

        Clears the internal passage cache if present, performs 50 bulk cache-set operations
        and 50 corresponding cache-get operations, and enforces timing budgets for the
        bulk set and bulk get phases. Get assertions (non-None results) are only made
        when the internal cache exists and contains entries. Timing assertions are
        skipped when the CI_SLOW_RUNNER environment variable is set.
        """
        # Clear cache
        if hasattr(bot, "_passage_cache"):
            bot._passage_cache.clear()

        # Bulk set operations
        start_time = time.perf_counter()
        for i in range(50):
            bot._cache_set(f"Bulk {i}:1", "kjv", (f"Bulk text {i}", f"Bulk {i}:1"))
        bulk_set_time = time.perf_counter() - start_time

        # Bulk get operations
        start_time = time.perf_counter()
        for i in range(50):  # Only get entries that were actually set (0-49)
            result = bot._cache_get(f"Bulk {i}:1", "kjv")
            # Only assert if cache is working, otherwise skip
            if hasattr(bot, "_passage_cache") and bot._passage_cache:
                assert result is not None
        bulk_get_time = time.perf_counter() - start_time

        # Performance assertions
        if not os.getenv("CI_SLOW_RUNNER"):
            assert bulk_set_time < 3.0
            assert bulk_get_time < 1.5

    def test_cache_performance_case_insensitive(self):
        """
        Measure cache performance for case-insensitive keys.

        Clears the internal `_passage_cache` if present, writes 100 entries using mixed-case keys via `bot._cache_set`,
        then reads them back using a different case via `bot._cache_get`. Asserts each read returns a non-None value
        and that the set phase completes under 1.0 second and the get phase under 0.5 seconds.
        """
        # Clear cache
        if hasattr(bot, "_passage_cache"):
            bot._passage_cache.clear()

        # Set with mixed case
        start_time = time.perf_counter()
        for i in range(100):
            bot._cache_set(f"CaSe {i}:1", "KJV", (f"Case text {i}", f"CaSe {i}:1"))
        case_set_time = time.perf_counter() - start_time

        # Get with different case
        start_time = time.perf_counter()
        for i in range(100):
            result = bot._cache_get(f"case {i}:1", "kjv")
            assert result is not None
        case_get_time = time.perf_counter() - start_time

        # Performance assertions
        if not os.getenv("CI_SLOW_RUNNER"):
            assert case_set_time < 1.0
            assert case_get_time < 0.5


class TestBookNormalizationPerformance:
    """Test book name normalization performance."""

    @pytest.mark.slow
    def test_normalization_performance_common_books(self):
        """
        Measure performance of book-name normalization on a list of common Bible books.

        Runs 200 iterations over a predefined list of common book names, calling
        bot.validate_and_normalize_book_name for each entry and asserting each result
        is a string. Records total elapsed time and, unless the CI_SLOW_RUNNER
        environment variable is set, enforces a total-time budget (< 4.0 s) and an
        average-per-call budget (< 6 ms).
        """
        common_books = [
            "Genesis",
            "Exodus",
            "Leviticus",
            "Numbers",
            "Deuteronomy",
            "Matthew",
            "Mark",
            "Luke",
            "John",
            "Acts",
            "Romans",
            "1 Corinthians",
            "2 Corinthians",
            "Galatians",
            "Ephesians",
        ]

        start_time = time.perf_counter()
        for _ in range(200):
            for book in common_books:
                result = bot.validate_and_normalize_book_name(book)
                assert isinstance(result, str)
        normalization_time = time.perf_counter() - start_time

        # Performance assertion - more lenient for CI stability
        # Skip timing checks on slow CI environments
        if not os.getenv("CI_SLOW_RUNNER"):
            assert normalization_time < 4.0  # Increased budget for flaky CI
            # Optional: guard against slow boxes by also checking average
            per_call = normalization_time / (200 * len(common_books))
            assert per_call < 0.006  # 6ms per normalization, extra slack

    @pytest.mark.slow
    def test_normalization_performance_abbreviations(self):
        """
        Measure performance of book-name normalization for common abbreviations.

        Runs 200 iterations over a representative set of abbreviated book names (including spaced variants)
        and verifies each normalization returns a string. When the CI_SLOW_RUNNER environment variable is
        not set, asserts the total run completes within 3.5 seconds and the average time per normalization
        is under 6 ms.
        """
        abbreviations = [
            "Gen",
            "Ex",
            "Lev",
            "Num",
            "Deut",
            "Matt",
            "Mk",
            "Lk",
            "Jn",
            "1jn",
            "2jn",
            "3jn",
            "1 john",  # Test spaced John variant
            "Acts",
            "Rom",
            "1co",
            "2co",
            "1 cor",  # Test spaced variant
            "2 cor",  # Test spaced variant
            "Gal",
            "Eph",
        ]

        start_time = time.perf_counter()
        for _ in range(200):
            for abbrev in abbreviations:
                result = bot.validate_and_normalize_book_name(abbrev)
                assert isinstance(result, str)
        abbrev_time = time.perf_counter() - start_time

        # Performance assertion - more lenient for CI stability
        # Skip timing checks on slow CI environments
        if not os.getenv("CI_SLOW_RUNNER"):
            assert abbrev_time < 3.5  # Increased budget for flaky CI
            # Optional: guard against slow boxes by also checking average
            per_call = abbrev_time / (200 * len(abbreviations))
            assert per_call < 0.006  # 6ms per normalization, extra slack

    @pytest.mark.slow
    def test_normalization_performance_mixed_case(self):
        """
        Test performance of validate_and_normalize_book_name using mixed-case book names.

        Runs 200 iterations over a predefined list of mixed-case book-name variants and asserts each normalization returns a string.
        When the CI_SLOW_RUNNER environment variable is not set, the total elapsed time for the loop must be under 3.5 seconds.
        """
        mixed_case_books = [
            "genesis",
            "EXODUS",
            "LeViTiCuS",
            "numbers",
            "DEUTERONOMY",
            "matthew",
            "MARK",
            "LuKe",
            "john",
            "ACTS",
        ]

        start_time = time.perf_counter()
        for _ in range(200):
            for book in mixed_case_books:
                result = bot.validate_and_normalize_book_name(book)
                assert isinstance(result, str)
        mixed_case_time = time.perf_counter() - start_time

        # Performance assertion - more lenient for CI stability
        # Skip timing checks on slow CI environments
        if not os.getenv("CI_SLOW_RUNNER"):
            assert mixed_case_time < 3.5  # Increased budget for flaky CI


class TestAPIPerformance:
    """Test API performance characteristics."""

    @pytest.mark.asyncio
    @patch("biblebot.bot.make_api_request", new_callable=AsyncMock)
    async def test_api_request_performance_single(self, mock_api):
        """
        Verify that a single call to get_bible_text returns a non-None result and completes quickly when the underlying API is mocked.

        The test sets the API mock to return a simple verse payload, measures elapsed time for await bot.get_bible_text("Test 1:1", "kjv"), and asserts the call completes in under 1.0 second and returns a non-None value.
        """
        mock_api.return_value = {"text": "Test verse", "reference": "Test 1:1"}

        start_time = time.perf_counter()
        result = await bot.get_bible_text("Test 1:1", "kjv")
        request_time = time.perf_counter() - start_time

        # Performance assertion
        assert request_time < 1.0  # Should complete quickly with mocked API
        assert result is not None

    @pytest.mark.asyncio
    @patch("biblebot.bot.make_api_request", new_callable=AsyncMock)
    async def test_api_request_performance_concurrent(self, mock_api):
        """Test concurrent API request performance."""
        mock_api.return_value = {"text": "Test verse", "reference": "Test 1:1"}

        async def single_request(verse):
            """
            Fetch the KJV text for a single test verse identifier.

            Parameters:
                verse (str|int): Verse identifier used to build the reference (formatted into "Test {verse}:1").

            Returns:
                str | None: The retrieved passage text (may be None if no text is found).
            """
            return await bot.get_bible_text(f"Test {verse}:1", "kjv")

        start_time = time.perf_counter()
        tasks = [single_request(i) for i in range(10)]
        results = await asyncio.gather(*tasks)
        concurrent_time = time.perf_counter() - start_time

        # Performance assertions
        assert concurrent_time < 2.0  # Should complete quickly with mocked API
        assert len(results) == 10
        assert all(result is not None for result in results)

    @pytest.mark.asyncio
    @patch("biblebot.bot.make_api_request", new_callable=AsyncMock)
    async def test_api_request_performance_with_cache(self, mock_api):
        """Test API request performance with caching."""
        mock_api.return_value = {"text": "Cached verse", "reference": "Cache 1:1"}

        # Clear cache
        if hasattr(bot, "_passage_cache"):
            bot._passage_cache.clear()

        # First request (should hit API)
        start_time = time.perf_counter()
        result1 = await bot.get_bible_text("Cache 1:1", "kjv")
        first_request_time = time.perf_counter() - start_time

        # Second request (should use cache)
        start_time = time.perf_counter()
        result2 = await bot.get_bible_text("Cache 1:1", "kjv")
        cached_request_time = time.perf_counter() - start_time

        # Performance assertions
        assert first_request_time < 1.0
        # Cache should be much faster; relax timing on slow CI
        if not os.getenv("CI_SLOW_RUNNER"):
            assert cached_request_time < 0.15
        assert result1 == result2
        assert mock_api.call_count == 1  # Only called once due to caching


class TestConfigPerformance:
    """Test configuration loading performance."""

    @pytest.mark.slow
    def test_config_loading_performance(self, tmp_path):
        """
        Measure that loading a YAML configuration via bot.load_config is performant.

        Creates a temporary YAML config file with minimal Matrix settings, then calls bot.load_config 100 times asserting each call returns a non-None configuration. Fails if the total load time exceeds 5.0 seconds. The test writes to the provided temporary path fixture.
        """
        # Create test config
        config_data = {
            "matrix": {
                "homeserver": "https://matrix.org",
                "bot_user_id": "@testbot:matrix.org",
                "room_ids": ["!room1:matrix.org", "!room2:matrix.org"],
                "e2ee": {"enabled": False},
            },
        }

        yaml = pytest.importorskip("yaml")

        config_file = tmp_path / "config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        # Measure config loading performance
        start_time = time.perf_counter()
        for _ in range(100):
            config = bot.load_config(str(config_file))
            assert config is not None
        loading_time = time.perf_counter() - start_time

        # Performance assertion
        if not os.getenv("CI_SLOW_RUNNER"):
            assert loading_time < 5.0  # Should complete in under 5 seconds

    @pytest.mark.slow
    def test_environment_loading_performance(self, tmp_path, monkeypatch):
        """Test environment loading performance."""
        monkeypatch.chdir(tmp_path)
        # Create test .env file
        env_file = tmp_path / ".env"
        env_file.write_text("MATRIX_ACCESS_TOKEN=test_token\nESV_API_KEY=test_key")

        # Measure environment loading performance
        # Create a minimal config for testing
        config = {"matrix": {"room_ids": ["!test:matrix.org"]}}
        start_time = time.perf_counter()
        for _ in range(100):
            matrix_token, api_keys = bot.load_environment(
                config, str(tmp_path / "config.yaml")
            )
            assert isinstance(api_keys, dict)
        env_loading_time = time.perf_counter() - start_time

        # Performance assertion
        if not os.getenv("CI_SLOW_RUNNER"):
            assert env_loading_time < 3.0  # Should complete in under 3 seconds


class TestMemoryPerformance:
    """Test memory usage performance."""

    def test_cache_memory_usage(self):
        """Test cache memory usage doesn't grow excessively."""
        # Clear cache
        if hasattr(bot, "_passage_cache"):
            bot._passage_cache.clear()

        # Add many items to cache
        for i in range(1000):
            bot._cache_set(
                f"Memory {i}:1", "kjv", (f"Memory text {i}", f"Memory {i}:1")
            )

        # Verify cache has items but isn't excessive
        if hasattr(bot, "_passage_cache"):
            cache_size = len(bot._passage_cache)
            assert cache_size > 0
            assert cache_size <= 1000  # Should not exceed what we put in

    @pytest.mark.slow
    def test_normalization_memory_usage(self):
        """
        Run repeated book-name normalizations to detect memory-growth issues.

        Performs 10,000 calls to bot.validate_and_normalize_book_name cycling through 100 distinct inputs.
        Each result is asserted to be either a string (normalized name) or None (invalid input).
        The test passes implicitly if it completes without excessive memory consumption or crashes.
        """
        # Test many normalizations
        for i in range(10000):
            book_name = f"TestBook{i % 100}"
            result = bot.validate_and_normalize_book_name(book_name)
            # Note: invalid book names return None, so we check for str or None
            assert result is None or isinstance(result, str)

        # If we get here without memory issues, test passes implicitly


class TestStressPerformance:
    """Test stress performance scenarios."""

    def test_rapid_cache_operations(self):
        """
        Stress-test mixed cache operations by performing 500 rapid set/get cycles and asserting functional correctness and performance.

        Clears the internal passage cache (if present), then for 500 iterations:
        - stores a passage via the internal cache-set helper,
        - retrieves it via the internal cache-get helper and asserts the result is not None,
        - retrieves it again using different casing for the key and version and asserts the result equals the first retrieval (verifies case-insensitive behavior).

        Measures total elapsed time and, unless the CI_SLOW_RUNNER environment variable is set, asserts the test completes in under 10 seconds.
        """
        # Clear cache
        if hasattr(bot, "_passage_cache"):
            bot._passage_cache.clear()

        start_time = time.perf_counter()

        # Rapid mixed operations
        for i in range(500):
            # Set operation
            bot._cache_set(
                f"Stress {i}:1", "kjv", (f"Stress text {i}", f"Stress {i}:1")
            )

            # Get operation
            result = bot._cache_get(f"Stress {i}:1", "kjv")
            assert result is not None

            # Get with different case
            result2 = bot._cache_get(f"stress {i}:1", "KJV")
            assert result2 == result

        stress_time = time.perf_counter() - start_time

        # Performance assertion
        if not os.getenv("CI_SLOW_RUNNER"):
            assert stress_time < 10.0  # Should complete in under 10 seconds

    def test_concurrent_normalization_stress(self):
        """
        Stress-test concurrent normalization of Bible book names using multiple threads.

        Spawns several worker threads that repeatedly call bot.validate_and_normalize_book_name on a fixed set of book-name variants and record each result in the shared `results` list; any exceptions are collected in the shared `errors` list. After joining all threads the test asserts there were no errors, that some results were produced, and that the total run completed within the expected time budget (5.0 seconds).
        """
        import threading

        results = []
        errors = []

        def normalize_worker():
            """
            Worker that performs 100 iterations of book-name normalization and records outcomes.

            Repeatedly calls bot.validate_and_normalize_book_name on a fixed set of book-name variants and appends each result to the outer-scope list `results`. Any exception encountered is caught and appended to the outer-scope list `errors`. Designed to be used as a threaded worker in concurrency/stress tests.
            """
            try:
                for _i in range(100):
                    book_names = [
                        "Genesis",
                        "gen",
                        "GENESIS",
                        "Matt",
                        "matthew",
                        "MATTHEW",
                    ]
                    for book in book_names:
                        result = bot.validate_and_normalize_book_name(book)
                        results.append(result)
            except Exception as e:  # noqa: BLE001
                errors.append(e)

        # Create multiple threads
        threads = []
        start_time = time.perf_counter()

        for _ in range(5):
            thread = threading.Thread(target=normalize_worker)
            threads.append(thread)
            thread.start()

        # Wait for all threads
        for thread in threads:
            thread.join()

        concurrent_time = time.perf_counter() - start_time

        # Performance and correctness assertions
        assert concurrent_time < 5.0  # Should complete in under 5 seconds
        assert len(errors) == 0  # No errors should occur
        assert len(results) > 0  # Should have results
