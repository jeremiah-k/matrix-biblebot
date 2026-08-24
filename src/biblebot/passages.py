"""
Passage retrieval for BibleBot: API access, caching, and translation dispatch.

This module owns everything between a scripture reference and its text:
- make_api_request: shared aiohttp GET helper returning decoded JSON or None
- an LRU/TTL in-memory passage cache
- get_esv_text / get_kjv_text: per-translation API backends
- get_bible_text: cache-aware dispatch to the right backend

The bot module re-exports these names; production code and tests should
import from here.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections import OrderedDict
from time import monotonic
from typing import Any, Mapping
from urllib.parse import quote

import aiohttp

from biblebot.constants.api import (
    API_PARAM_FALSE,
    API_PARAM_INCLUDE_FOOTNOTES,
    API_PARAM_INCLUDE_HEADINGS,
    API_PARAM_INCLUDE_PASSAGE_REFERENCES,
    API_PARAM_INCLUDE_SHORT_COPYRIGHT,
    API_PARAM_INCLUDE_VERSE_NUMBERS,
    API_PARAM_Q,
    API_REQUEST_TIMEOUT_SEC,
    CACHE_MAX_SIZE,
    CACHE_TTL_SECONDS,
    ESV_API_URL,
    KJV_API_URL_TEMPLATE,
)
from biblebot.constants.app import BIBLEBOT_HTTP_USER_AGENT, LOGGER_NAME
from biblebot.constants.bible import (
    DEFAULT_TRANSLATION,
    TRANSLATION_ESV,
    TRANSLATION_KJV,
)

logger = logging.getLogger(LOGGER_NAME)


# Custom exceptions for Bible text retrieval
class PassageNotFound(Exception):
    """Raised when a Bible passage cannot be found or retrieved."""


class APIKeyMissing(Exception):
    """Raised when a required API key is missing."""


# Patchable cache constants for backward compatibility and testing
# These can be patched in tests to control cache behavior
_PASSAGE_CACHE_MAX = CACHE_MAX_SIZE
_PASSAGE_CACHE_TTL_SECS = CACHE_TTL_SECONDS

_passage_cache: "OrderedDict[tuple[str, str], tuple[float, tuple[str, str | None]]]" = (
    OrderedDict()
)


async def make_api_request(
    url: str,
    headers: Mapping[str, str] | None = None,
    params: Mapping[str, Any] | None = None,
    session: aiohttp.ClientSession | None = None,
    timeout: aiohttp.ClientTimeout | float | int = API_REQUEST_TIMEOUT_SEC,
) -> Any:
    """
    Perform an HTTP GET for `url` and return the decoded JSON object on success, or None on failure.

    This function issues a GET request using the provided aiohttp ClientSession if `session` is given, otherwise it creates a temporary session for the call. `headers` and `params` are forwarded to the request; a minimal User-Agent and Accept: application/json header are merged with any caller headers. `timeout` may be an aiohttp.ClientTimeout or a numeric total timeout (seconds).

    Returns:
        The decoded JSON value (usually dict or list) when the response status is 200 and the body is valid JSON; otherwise returns None (for non-200 responses, invalid JSON, or network/timeout errors).

    Side effects:
        Logs warnings for non-200 responses and unexpected Content-Type; logs an exception when JSON decoding fails.
    """

    # Normalize timeout to ClientTimeout
    req_timeout = (
        timeout
        if isinstance(timeout, aiohttp.ClientTimeout)
        else aiohttp.ClientTimeout(total=timeout)
    )

    async def _request(sess):
        """
        Perform an HTTP GET using the provided aiohttp session and return parsed JSON on success.

        Performs a GET to the outer-scope `url` using `sess`, merging a minimal default User-Agent/Accept with outer-scope `headers`, and applying outer-scope `params` and `req_timeout`. If the response status is 200 and the body is valid JSON, returns the decoded JSON (typically a dict or list). Returns None for non-200 responses or when the body cannot be parsed as JSON.

        Side effects: logs warnings for non-200 responses and unexpected Content-Type, and logs an exception when JSON decoding fails.
        """
        # Merge a minimal default UA with caller-provided headers
        _base_headers = {
            "User-Agent": BIBLEBOT_HTTP_USER_AGENT,
            "Accept": "application/json",
        }
        _headers = {**_base_headers, **(headers or {})}
        async with sess.get(
            url, headers=_headers, params=params, timeout=req_timeout
        ) as response:
            if response.status == 200:
                try:
                    content_type = response.headers.get("Content-Type", "")
                    if content_type and "application/json" not in content_type:
                        logger.warning(
                            f"Unexpected content-type '{content_type}' from {url}"
                        )
                    return await response.json()
                except (aiohttp.ContentTypeError, json.JSONDecodeError):
                    logger.exception(f"Invalid JSON from {url}")
                    return None
            try:
                snippet = (await response.text())[:200]
            except (aiohttp.ClientError, UnicodeDecodeError):
                snippet = "<unavailable>"
            logger.warning(
                f"HTTP {response.status} fetching {url} - body[:200]={snippet!r}"
            )
            return None

    try:
        if session:
            return await _request(session)
        else:
            async with aiohttp.ClientSession(timeout=req_timeout) as new_session:
                return await _request(new_session)
    except (aiohttp.ClientError, asyncio.TimeoutError):
        logger.warning(f"Network error fetching {url}", exc_info=False)
        return None


def _cache_get(passage: str, translation: str, cache_enabled: bool = True):
    """
    Return a cached passage text for a given passage and translation if present and not expired.

    Looks up an LRU-style in-memory cache keyed by (passage, translation) after normalizing both to lowercase.
    If cache_enabled is False this function always returns None. If a cached entry exists and its timestamp
    is within the TTL (_PASSAGE_CACHE_TTL_SECS), the entry is reinserted to mark it as recently used and its
    value is returned. Expired or missing entries return None.

    Parameters:
        passage (str): Bible passage identifier (e.g., "John 3:16"); matching is case-insensitive.
        translation (str): Translation code/name (case-insensitive).
        cache_enabled (bool): When False, bypasses the cache and returns None.

    Returns:
        The cached passage text (any type stored) if present and fresh; otherwise None.
    """
    if not cache_enabled:
        return None

    key = (passage.lower(), translation.lower())
    now = monotonic()
    if key in _passage_cache:
        ts, value = _passage_cache.pop(key)
        # Evict if stale
        if now - ts <= _PASSAGE_CACHE_TTL_SECS:
            _passage_cache[key] = (ts, value)  # reinsert to mark recent
            return value
    return None


def _cache_set(
    passage: str,
    translation: str,
    value: tuple[str, str | None],
    cache_enabled: bool = True,
):
    """
    Store a fetched passage in the module-level in-memory LRU TTL cache.

    This inserts an entry keyed by the lowercased (passage, translation) pair and stores a tuple
    (monotonic_timestamp, payload). The payload is typically (verse_text, canonical_reference).
    If cache_enabled is False the function is a no-op. When the cache exceeds _PASSAGE_CACHE_MAX
    the oldest entries are evicted to enforce LRU behavior.
    """
    if not cache_enabled:
        return

    key = (passage.lower(), translation.lower())
    _passage_cache[key] = (monotonic(), value)
    # enforce LRU max size
    while len(_passage_cache) > _PASSAGE_CACHE_MAX:
        _passage_cache.popitem(last=False)


async def get_bible_text(
    passage: str,
    translation: str | None = None,
    api_keys: Mapping[str, str] | None = None,
    cache_enabled: bool = True,
    default_translation: str = DEFAULT_TRANSLATION,
    session: Any | None = None,
) -> tuple[str, str | None]:
    # Use provided translation or fall back to configurable default
    """
    Retrieve a Bible passage and its canonical reference, optionally using a specified translation and an in-memory LRU/TTL cache.

    If `translation` is None the function uses `default_translation`. When `cache_enabled` is True, a cached (passage, translation) result is returned if present. Translation identifiers are compared case-insensitively. The function dispatches to the appropriate backend (ESV or KJV), may consult `api_keys` for backends that require a key, and stores successful results in the cache before returning.

    Parameters:
        passage (str): Passage or range to fetch (e.g., "John 3:16").
        translation (str | None): Translation identifier (case-insensitive). If None, `default_translation` is used.
        api_keys (Mapping[str, str] | None): Optional mapping from translation identifier to API key; used by backends that require a key (ESV).
        cache_enabled (bool): If True, consult and update the module's in-memory passage cache.
        default_translation (str): Translation to use when `translation` is None.
        session: Optional aiohttp-like session to reuse for HTTP requests.

    Returns:
        tuple(str, str): (passage_text, canonical_reference)

    Raises:
        PassageNotFound: If the passage cannot be retrieved or the requested translation is unsupported.
        APIKeyMissing: If a backend that requires an API key (e.g., ESV) is selected but no API key is provided.
    """
    if translation is None:
        translation = default_translation
    trans_norm = translation.lower()

    # Check cache first
    cached = _cache_get(passage, trans_norm, cache_enabled)
    if cached is not None:
        return cached

    api_key = None
    if api_keys:
        api_key = api_keys.get(trans_norm)

    if trans_norm == TRANSLATION_ESV:
        result = await get_esv_text(passage, api_key, session=session)
    elif trans_norm == TRANSLATION_KJV:
        result = await get_kjv_text(passage, session=session)
    else:
        raise PassageNotFound(f"Unsupported translation: '{translation}'")
    _cache_set(passage, trans_norm, result, cache_enabled)
    return result


async def get_esv_text(
    passage: str,
    api_key: str | None,
    session: Any | None = None,
) -> tuple[str, str | None]:
    """
    Fetch a passage from the ESV API and return its text and canonical reference.

    Fetches the specified passage using the provided ESV API key and returns a tuple of
    (stripped passage text, canonical reference). The canonical reference may be None
    if the API omits it.

    Parameters:
        passage (str): Passage query (e.g., "John 3:16").
        api_key (str | None): ESV API key; required for the request.

    Returns:
        tuple[str, str | None]: (passage_text, canonical_reference)

    Raises:
        APIKeyMissing: If api_key is None.
        PassageNotFound: If the API response is invalid or the passage could not be found.
    """
    if api_key is None:
        raise APIKeyMissing(f"ESV API key is required for passage '{passage}'")

    API_URL = ESV_API_URL
    params = {
        API_PARAM_Q: passage,
        API_PARAM_INCLUDE_HEADINGS: API_PARAM_FALSE,
        API_PARAM_INCLUDE_FOOTNOTES: API_PARAM_FALSE,
        API_PARAM_INCLUDE_VERSE_NUMBERS: API_PARAM_FALSE,
        API_PARAM_INCLUDE_SHORT_COPYRIGHT: API_PARAM_FALSE,
        API_PARAM_INCLUDE_PASSAGE_REFERENCES: API_PARAM_FALSE,
    }
    headers = {"Authorization": f"Token {api_key}"}
    response = await make_api_request(API_URL, headers, params, session=session)

    if not isinstance(response, dict):
        raise PassageNotFound(f"Invalid API response for passage '{passage}'")

    passages = response.get("passages")
    reference = response.get("canonical")

    if not passages or not passages[0].strip():
        raise PassageNotFound(f"Passage '{passage}' not found in ESV")

    return (passages[0].strip(), reference)


async def get_kjv_text(
    passage: str,
    session: Any | None = None,
) -> tuple[str, str | None]:
    # Preserve ':' in chapter:verse while encoding spaces and punctuation
    """
    Fetch the King James Version (KJV) text for a given Bible passage.

    Parameters:
        passage (str): Passage reference (e.g., "John 3:16" or "Genesis 1:1-3"). Colons in the passage are preserved for URL encoding.

    Returns:
        tuple[str, str | None]: (text, reference) where `text` is the trimmed passage text and `reference` is the canonical reference returned by the API (may be None).

    Raises:
        PassageNotFound: If the API returns no result or returns an empty text for the requested passage.
    """
    encoded = quote(passage, safe=":")
    # Use the original KJV API URL template directly rather than any discovered endpoint
    # because the KJV API has a specific URL structure that doesn't follow standard discovery patterns
    API_URL = KJV_API_URL_TEMPLATE.format(passage=encoded)
    response = await make_api_request(API_URL, session=session)

    if not response or not response.get("text"):
        raise PassageNotFound(f"Passage '{passage}' not found in KJV")

    text = response.get("text").strip()
    reference = response.get("reference")

    if not text:
        raise PassageNotFound(f"Empty text returned for passage '{passage}' in KJV")

    return (text, reference)
