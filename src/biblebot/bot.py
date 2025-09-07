import asyncio
import html
import json
import logging
import os
import random
import textwrap
import time
from collections import OrderedDict
from time import monotonic
from typing import Optional
from urllib.parse import quote

import aiohttp
import nio.exceptions
import yaml
from dotenv import load_dotenv
from nio import (
    AsyncClient,
    AsyncClientConfig,
    InviteEvent,
    MatrixRoom,
    MegolmEvent,
    RoomMessageText,
    RoomResolveAliasError,
)

from .auth import get_store_dir, load_credentials
from .bible_constants import BOOK_ABBREVIATIONS
from .constants import (
    API_PARAM_FALSE,
    API_PARAM_INCLUDE_FOOTNOTES,
    API_PARAM_INCLUDE_HEADINGS,
    API_PARAM_INCLUDE_PASSAGE_REFERENCES,
    API_PARAM_INCLUDE_SHORT_COPYRIGHT,
    API_PARAM_INCLUDE_VERSE_NUMBERS,
    API_PARAM_Q,
    API_REQUEST_TIMEOUT_SEC,
    APP_NAME,
    CACHE_MAX_SIZE,
    CACHE_TTL_SECONDS,
    CHAR_DOT,
    CONFIG_DETECT_REFERENCES_ANYWHERE,
    CONFIG_KEY_MATRIX,
    CONFIG_MATRIX_E2EE,
    CONFIG_MATRIX_HOMESERVER,
    CONFIG_MATRIX_ROOM_IDS,
    CONFIG_MATRIX_USER,
    CONFIG_PRESERVE_POETRY_FORMATTING,
    DEFAULT_CONFIG_FILENAME_MAIN,
    DEFAULT_ENV_FILENAME,
    DEFAULT_TRANSLATION,
    ENV_ESV_API_KEY,
    ENV_MATRIX_ACCESS_TOKEN,
    ERROR_AUTH_INSTRUCTIONS,
    ERROR_NO_CREDENTIALS_AND_TOKEN,
    ERROR_PASSAGE_NOT_FOUND,
    ESV_API_URL,
    FILE_ENCODING_UTF8,
    INFO_API_KEY_FOUND,
    INFO_LOADING_ENV,
    INFO_NO_API_KEY,
    INFO_NO_ENV_FILE,
    INFO_RESOLVED_ALIAS,
    KJV_API_URL_TEMPLATE,
    LOGGER_NAME,
    LOGGER_NIO,
    MESSAGE_SUFFIX,
    PARTIAL_REFERENCE_PATTERNS,
    REACTION_OK,
    REFERENCE_PATTERNS,
    SYNC_TIMEOUT_MS,
    TRANSLATION_ESV,
    TRANSLATION_KJV,
    WARN_COULD_NOT_RESOLVE_ALIAS,
    WARN_MATRIX_ACCESS_TOKEN_NOT_SET,
)

# Configure logging
logger = logging.getLogger(LOGGER_NAME)

# Constants
FALLBACK_MESSAGE_TOO_LONG = "[Message too long]"
MIN_PRACTICAL_CHUNK_SIZE = 8  # Minimum reasonable chunk size for splitting
MAX_RATE_LIMIT_RETRIES = 3  # Maximum number of rate limit retries
DEFAULT_RETRY_AFTER_MS = 1000  # Default retry delay in milliseconds


# Create a comprehensive lookup table for all valid book names and abbreviations
_ALL_NAMES_TO_CANONICAL = BOOK_ABBREVIATIONS.copy()
# Add lowercased full book names to the lookup table
for book_name in set(
    BOOK_ABBREVIATIONS.values()
):  # Use set to avoid redundant iterations
    _ALL_NAMES_TO_CANONICAL[book_name.lower()] = book_name
TRUNCATION_INDICATOR = "..."  # Indicator for truncated text
REFERENCE_SEPARATOR_LEN = 3  # Length of " - " separator


# Custom exceptions for Bible text retrieval
class PassageNotFound(Exception):
    """Raised when a Bible passage cannot be found or retrieved."""

    pass


class APIKeyMissing(Exception):
    """Raised when a required API key is missing."""

    pass


# Patchable cache constants for backward compatibility and testing
# These can be patched in tests to control cache behavior
_PASSAGE_CACHE_MAX = CACHE_MAX_SIZE
_PASSAGE_CACHE_TTL_SECS = CACHE_TTL_SECONDS


def _clean_book_name(book_str: str) -> str:
    """Clean and normalize book name string for consistent matching."""
    return " ".join(book_str.lower().replace(CHAR_DOT, "").strip().split())


def validate_and_normalize_book_name(book_str: str) -> Optional[str]:
    """
    Validate and normalize a Bible book name in one operation.

    Returns the canonical full name if the book is valid, None if invalid.
    This function combines validation and normalization for optimal performance
    in contexts where both operations are needed.
    """
    clean_str = _clean_book_name(book_str)
    return _ALL_NAMES_TO_CANONICAL.get(clean_str)


# Load config
def load_config(config_file, log_loading=True):
    """
    Load and validate the bot configuration from a YAML file.

    This reads YAML from config_file, supports a legacy flat format by migrating
    matrix_* keys into a nested `matrix` section, and ensures a list of room IDs
    is present. On success returns the parsed configuration with a top-level
    `CONFIG_MATRIX_ROOM_IDS` key populated for backward compatibility.

    Parameters:
        config_file (str): Path to the YAML configuration file.
        log_loading (bool): Whether to log the "Loaded configuration" message.
                           Set to False to suppress duplicate logging.

    Returns:
        dict | None: Parsed configuration dictionary on success; None if the file
        cannot be read, contains invalid YAML, or fails validation (missing or
        non-list room IDs).
    """
    try:
        with open(config_file, "r", encoding=FILE_ENCODING_UTF8) as f:
            config = yaml.safe_load(f) or {}

            # Handle both old flat structure and new nested structure
            # Convert old flat structure to new nested structure for backward compatibility
            if "matrix_room_ids" in config and "matrix" not in config:
                logger.info(
                    "Converting legacy flat config structure to nested structure"
                )
                matrix_config = {}

                # Copy matrix-related keys under matrix section (keep originals for compatibility)
                if CONFIG_MATRIX_HOMESERVER in config:
                    matrix_config["homeserver"] = config[CONFIG_MATRIX_HOMESERVER]
                if CONFIG_MATRIX_USER in config:
                    matrix_config["user"] = config[CONFIG_MATRIX_USER]
                if CONFIG_MATRIX_ROOM_IDS in config:
                    matrix_config["room_ids"] = config[CONFIG_MATRIX_ROOM_IDS]

                config["matrix"] = matrix_config

            # Basic validation - check for room_ids in either location
            room_ids = None
            if CONFIG_KEY_MATRIX in config and isinstance(
                config[CONFIG_KEY_MATRIX], dict
            ):
                room_ids = config[CONFIG_KEY_MATRIX].get("room_ids")
            if not room_ids and CONFIG_MATRIX_ROOM_IDS in config:
                room_ids = config[CONFIG_MATRIX_ROOM_IDS]

            if not room_ids:
                logger.error(
                    f"Missing required configuration: room_ids in {config_file}"
                )
                return None
            if not isinstance(room_ids, list):
                logger.error("'room_ids' must be a list in config")
                return None

            # Ensure matrix_room_ids is available at top level for backward compatibility
            config[CONFIG_MATRIX_ROOM_IDS] = room_ids

            if log_loading:
                logger.info(f"Loaded configuration from {config_file}")
            return config
    except (OSError, yaml.YAMLError):
        logger.exception(f"Error loading config from {config_file}")
        return None


# Load environment variables
def load_environment(config: dict, config_path: str):
    """
    Load API keys and the Matrix access token from the provided configuration and the environment.

    Checks the supplied config dict for an "api_keys" section and reads a legacy .env file next to the given config_path (falling back to a .env in the current working directory or the process environment). Environment variables take precedence over values in the config file. Emits deprecation warnings when legacy .env or MATRIX_ACCESS_TOKEN are used.

    Parameters:
        config (dict): Parsed configuration dictionary (typically loaded from YAML). If it contains an "api_keys" mapping, any "esv" entry will be read.
        config_path (str): Filesystem path to the active config file; its directory is used to locate a legacy .env file.

    Returns:
        tuple: (matrix_access_token, api_keys) where
            - matrix_access_token (str | None): value of the ENV_MATRIX_ACCESS_TOKEN environment variable if set, otherwise None.
            - api_keys (dict): mapping of translation keys to API keys (contains at least the TRANSLATION_ESV key, which may be None).
    """
    # Initialize with expected keys set to None
    api_keys = {TRANSLATION_ESV: None}

    # Get API keys from config file first (new method)
    if config and "api_keys" in config:
        config_api_keys = config["api_keys"] or {}
        if config_api_keys.get("esv"):
            api_keys[TRANSLATION_ESV] = config_api_keys["esv"]
            logger.info(INFO_API_KEY_FOUND.format(TRANSLATION_ESV.upper()))

    # Try to load .env from a list of possible locations (legacy support)
    env_paths_to_check = [
        os.path.join(os.path.dirname(config_path), DEFAULT_ENV_FILENAME),
        os.path.join(os.getcwd(), DEFAULT_ENV_FILENAME),
    ]

    env_loaded = False
    for env_path in env_paths_to_check:
        if os.path.exists(env_path):
            load_dotenv(env_path)
            logger.warning(
                "⚠️  .env file detected - this is deprecated. Consider moving API keys to config.yaml"
            )
            logger.debug(f"{INFO_LOADING_ENV} {env_path}")
            env_loaded = True
            break  # Stop after finding the first .env file

    if not env_loaded:
        logger.debug(INFO_NO_ENV_FILE)

    # Get access token from environment (legacy support with deprecation warning)
    matrix_access_token = os.getenv(ENV_MATRIX_ACCESS_TOKEN)
    if matrix_access_token:
        # Don't warn here; main() decides legacy vs modern auth.
        logger.debug("MATRIX_ACCESS_TOKEN environment variable detected")
    else:
        # Don't warn here; main() decides legacy vs modern auth.
        logger.debug(WARN_MATRIX_ACCESS_TOKEN_NOT_SET)

    # Override API keys from environment if present (environment takes precedence)
    esv_key = os.getenv(ENV_ESV_API_KEY)
    if esv_key:
        api_keys[TRANSLATION_ESV] = esv_key
        logger.info(INFO_API_KEY_FOUND.format(TRANSLATION_ESV.upper()))
    elif not api_keys.get(TRANSLATION_ESV):
        logger.debug(INFO_NO_API_KEY.format(TRANSLATION_ESV.upper()))

    return matrix_access_token, api_keys


# Set nio logging to WARNING level to suppress verbose messages by default.
logging.getLogger(LOGGER_NIO).setLevel(logging.WARNING)


# Handles headers & parameters for API requests
async def make_api_request(
    url, headers=None, params=None, session=None, timeout=API_REQUEST_TIMEOUT_SEC
):
    """
    Perform an HTTP GET to the given URL and return the parsed JSON response, or None on failure.

    The function accepts optional request headers and query parameters. If a ClientSession is provided it will be reused; otherwise a temporary session is created for the request. The timeout argument may be either an aiohttp.ClientTimeout instance or a numeric total timeout in seconds.

    Returns:
        The decoded JSON object on HTTP 200 with valid JSON, or None if the response is non-200, the body is not valid JSON, or a network/timeout error occurs.
    """

    # Normalize timeout to ClientTimeout
    req_timeout = (
        timeout
        if isinstance(timeout, aiohttp.ClientTimeout)
        else aiohttp.ClientTimeout(total=timeout)
    )

    async def _request(sess):
        """
        Perform an HTTP GET on the outer-scope URL and return the parsed JSON response.

        Returns the decoded JSON object (typically a dict or list) on HTTP 200 with valid JSON, or None on non-200 responses or if the response body cannot be parsed as JSON. Side effects: logs warnings on non-200 status and logs exceptions when JSON decoding fails.
        """
        # Merge a minimal default UA with caller-provided headers
        _base_headers = {"User-Agent": APP_NAME, "Accept": "application/json"}
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
        logger.exception(f"Network error fetching {url}")
        return None


# Get Bible text
_passage_cache: "OrderedDict[tuple[str, str], tuple[float, tuple[str, str]]]" = (
    OrderedDict()
)


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
    passage: str, translation: str, value: tuple[str, str], cache_enabled: bool = True
):
    """
    Store a fetched passage in the in-memory LRU TTL cache.

    If caching is disabled this is a no-op. The cache key is the lowercased (passage, translation) pair;
    the stored value is a tuple of (timestamp, value). When the cache exceeds the module-level
    _max size, the oldest entries are evicted (LRU behavior).

    Parameters:
        passage (str): Bible passage string (e.g., "John 3:16").
        translation (str): Translation identifier (e.g., "ESV", "KJV"); used in the cache key.
        value (tuple[str, str]): The cached payload, typically (verse_text, canonical_reference).
        cache_enabled (bool): If False, the function returns without modifying the cache.
    """
    if not cache_enabled:
        return

    key = (passage.lower(), translation.lower())
    _passage_cache[key] = (monotonic(), value)
    # enforce LRU max size
    while len(_passage_cache) > _PASSAGE_CACHE_MAX:
        _passage_cache.popitem(last=False)


async def get_bible_text(
    passage,
    translation=None,
    api_keys=None,
    cache_enabled=True,
    default_translation=DEFAULT_TRANSLATION,
    session=None,
):
    # Use provided translation or fall back to configurable default
    """
    Retrieve a Bible passage text (with its canonical reference), using optional translation selection and an LRU TTL cache.

    If `translation` is not provided the function uses `default_translation`. When caching is enabled and a cached entry exists for the (passage, translation) pair that cached value is returned. The function dispatches to the appropriate backend for the requested translation (ESV uses an API key from `api_keys`, KJV uses the public KJV endpoint), stores successful results in the cache, and returns the fetched passage result.

    Parameters:
        passage (str): Bible passage identifier or range (e.g., "John 3:16").
        translation (str | None): Translation identifier (e.g., value of TRANSLATION_ESV). If None, `default_translation` is used.
        api_keys (Mapping[str, str] | None): Optional mapping of translation identifiers to API keys; used when a translation backend requires a key (ESV).
        cache_enabled (bool): If True, consult and update the internal passage cache (LRU with TTL); set False to bypass caching.
        default_translation (str): Translation to use when `translation` is None.

    Returns:
        The fetched passage result (contains the passage text and its canonical reference).

    Raises:
        PassageNotFound: If the passage cannot be retrieved or is not present in the backend response.
        APIKeyMissing: If a backend requiring an API key (e.g., ESV) is requested but no key is available.
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


async def get_esv_text(passage, api_key, session=None):
    """
    Fetch the specified passage text from the ESV API and return the passage text with its canonical reference.

    Parameters:
        passage (str): Passage query (e.g., "John 3:16").
        api_key (str | None): ESV API key; required.

    Returns:
        tuple[str, str | None]: (passage_text, canonical_reference). passage_text is stripped of surrounding whitespace; canonical_reference may be None if the API did not provide one.

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


async def get_kjv_text(passage, session=None):
    # Preserve ':' in chapter:verse while encoding spaces and punctuation
    """
    Fetch the King James Version (KJV) text for a given Bible passage.

    Parameters:
        passage (str): Passage reference (e.g., "John 3:16" or "Genesis 1:1-3"). Colons in the passage are preserved during URL encoding.

    Returns:
        tuple[str, str | None]: A pair (text, reference) where `text` is the passage text (trimmed) and `reference` is the canonical reference returned by the API (may be None).

    Raises:
        PassageNotFound: If the API returns no result or an empty text for the requested passage.
    """
    encoded = quote(passage, safe=":")
    API_URL = KJV_API_URL_TEMPLATE.format(passage=encoded)
    response = await make_api_request(API_URL, session=session)

    if not response or not response.get("text"):
        raise PassageNotFound(f"Passage '{passage}' not found in KJV")

    text = response.get("text").strip()
    reference = response.get("reference")

    if not text:
        raise PassageNotFound(f"Empty text returned for passage '{passage}' in KJV")

    return (text, reference)


class BibleBot:
    def __init__(self, config, client=None):
        """
        Initialize the BibleBot instance.

        Parameters:
            config (dict): Configuration mapping (expected keys: "bot" with optional "default_translation",
                "cache_enabled", "max_message_length", "split_message_length", and "detect_references_anywhere";
                the final chunk includes the reference/suffix and must also respect max_message_length;
                also contains matrix room IDs elsewhere in the config).
            client: Optional injected AsyncClient used for Matrix interactions (omitted from detailed param docs as a common service).

        Behavior:
            - Stores the provided config and optional client.
            - Initializes an empty api_keys dict (populated later by main) and an empty set of joined room IDs.
            - Reads bot settings from config["bot"]:
                - default_translation: translation to use when none is specified (defaults to DEFAULT_TRANSLATION).
                - cache_enabled: whether passage caching is enabled (defaults to True).
                - max_message_length: maximum allowed length for outgoing messages (defaults to 2000).
                - split_message_length: length at which to split long messages into multiple messages (defaults to 0, disabled).
                - detect_references_anywhere: whether to detect scripture references anywhere in messages (defaults to False).
            - Validates max_message_length and resets it to 2000 if a non-positive value is supplied.
            - Validates split_message_length, coerces to int, resets to 0 if negative, and caps to max_message_length.
        """
        self.config = config
        self.client = client  # Injected AsyncClient instance
        self.api_keys = {}  # Will be set in main()
        self._room_id_set: set[str] = set()
        self.http_session = None  # set in start(), closed in close()

        # Bot configuration settings with defaults
        bot_settings = config.get("bot", {}) if isinstance(config, dict) else {}
        self.default_translation = bot_settings.get(
            "default_translation", DEFAULT_TRANSLATION
        )
        self.cache_enabled = bot_settings.get("cache_enabled", True)
        self.max_message_length = bot_settings.get("max_message_length", 2000)
        self.preserve_poetry_formatting = bot_settings.get(
            CONFIG_PRESERVE_POETRY_FORMATTING, False
        )
        # Type-validate and coerce detect_references_anywhere
        raw_detect_anywhere = bot_settings.get(CONFIG_DETECT_REFERENCES_ANYWHERE, False)
        self.detect_references_anywhere = str(raw_detect_anywhere).lower().strip() in {
            "true",
            "yes",
            "1",
            "on",
        }
        # Type-validate and coerce split_message_length
        raw_split_len = bot_settings.get("split_message_length", 0)
        try:
            self.split_message_length = int(raw_split_len)
        except (TypeError, ValueError):
            logger.warning(
                f"Invalid split_message_length type: {raw_split_len!r}, disabling message splitting"
            )
            self.split_message_length = 0

        # Validate settings
        if self.max_message_length <= 0:
            logger.warning(
                f"Invalid max_message_length: {self.max_message_length}, using default 2000"
            )
            self.max_message_length = 2000

        if self.split_message_length < 0:
            logger.warning(
                f"Invalid split_message_length: {self.split_message_length}, disabling message splitting"
            )
            self.split_message_length = 0

        # Cap to max_message_length to avoid generating oversize chunks
        if (
            self.split_message_length
            and self.split_message_length > self.max_message_length
        ):
            logger.info(
                f"split_message_length {self.split_message_length} exceeds max_message_length "
                f"{self.max_message_length}; capping to max."
            )
            self.split_message_length = self.max_message_length

    def __repr__(self):
        """
        Return a concise, developer-oriented representation of the BibleBot.

        The string includes the list of keys present in the bot's `config` (empty list if `config` is not a dict) and a boolean `client_set` indicating whether an AsyncClient was provided.

        Returns:
            str: A representation like "BibleBot(config_keys=['a','b'], client_set=True)".
        """
        keys = list(self.config.keys()) if isinstance(self.config, dict) else []
        return f"BibleBot(config_keys={keys}, client_set={self.client is not None})"

    async def resolve_aliases(self):
        """
        Resolve any Matrix room aliases in the configured room list and replace them with canonical room IDs.

        Iterates over room IDs from config; for entries starting with '#', attempts to resolve the alias via self.client.room_resolve_alias and replaces the alias with the resolved room_id. Non-alias entries are preserved. Duplicates are removed while preserving order. The method updates the room IDs in place and logs warnings for aliases that cannot be resolved.
        """
        resolved_ids = []
        # Support both old and new config schema
        room_ids = self.config.get("matrix", {}).get("room_ids") or self.config.get(
            CONFIG_MATRIX_ROOM_IDS, []
        )
        for entry in room_ids:
            if entry.startswith("#"):
                try:
                    resp = await self.client.room_resolve_alias(entry)
                    if hasattr(resp, "room_id"):
                        resolved_ids.append(resp.room_id)
                        logger.info(INFO_RESOLVED_ALIAS.format(entry, resp.room_id))
                    else:
                        logger.warning(f"{WARN_COULD_NOT_RESOLVE_ALIAS}: {entry}")
                except RoomResolveAliasError:
                    logger.warning(
                        f"{WARN_COULD_NOT_RESOLVE_ALIAS} (exception): {entry}"
                    )
            else:
                resolved_ids.append(entry)
        # Update configuration with resolved IDs (support both schemas)
        unique_ids = list(dict.fromkeys(resolved_ids))
        if (
            CONFIG_KEY_MATRIX in self.config
            and "room_ids" in self.config[CONFIG_KEY_MATRIX]
        ):
            self.config[CONFIG_KEY_MATRIX]["room_ids"] = unique_ids
        else:
            self.config[CONFIG_MATRIX_ROOM_IDS] = unique_ids

    async def join_matrix_room(self, room_id_or_alias):
        """
        Join a Matrix room by ID or alias.

        If room_id_or_alias starts with '#', the alias is resolved to a room ID via the client's room_resolve_alias; otherwise the value is treated as a room ID. If the bot is not already in the room, this method attempts to join it. Successes and failures are logged; exceptions are caught and logged — the method does not raise.
        Parameters:
            room_id_or_alias (str): A Matrix room ID (e.g. "!abc:example.org") or alias (e.g. "#room:example.org").
        """
        # Skip placeholder room IDs from sample config
        if (
            "your_room_id" in room_id_or_alias
            or "your_homeserver_domain" in room_id_or_alias
            or "example.org" in room_id_or_alias
        ):
            logger.debug(f"Skipping placeholder room ID: {room_id_or_alias}")
            return

        try:
            if room_id_or_alias.startswith("#"):
                # If it's a room alias, resolve it to a room ID
                response = await self.client.room_resolve_alias(room_id_or_alias)
                if not hasattr(response, "room_id"):
                    logger.error(
                        f"Failed to resolve room alias '{room_id_or_alias}': {response.message if hasattr(response, 'message') else 'Unknown error'}"
                    )
                    return
                room_id = response.room_id
            else:
                room_id = room_id_or_alias

            # Attempt to join the room if not already joined
            rooms = getattr(self.client, "rooms", {})
            if room_id not in rooms:
                response = await self.client.join(room_id)
                if response and hasattr(response, "room_id"):
                    logger.info(f"Joined room '{room_id_or_alias}' successfully")
                else:
                    logger.error(
                        f"Failed to join room '{room_id_or_alias}': {response.message if hasattr(response, 'message') else 'Unknown error'}"
                    )
            else:
                logger.debug(f"Bot is already in room '{room_id_or_alias}'")
        except (
            nio.exceptions.LocalProtocolError,
            nio.exceptions.RemoteProtocolError,
            nio.exceptions.RemoteTransportError,
            aiohttp.ClientError,
            RoomResolveAliasError,
            asyncio.TimeoutError,
        ):
            logger.exception(f"Error joining room '{room_id_or_alias}'")

    async def ensure_joined_rooms(self):
        """
        On startup, join all rooms in config if not already joined.
        Uses the join_matrix_room method for each room.
        """
        for room_id in self.config[CONFIG_MATRIX_ROOM_IDS]:
            await self.join_matrix_room(room_id)

    async def start(self):
        """
        Start the bot and begin processing Matrix events.

        Performs startup tasks and then enters the continuous event sync loop:
        - Records the bot start time (milliseconds) in self.start_time.
        - Resolves any room aliases in configuration and builds the internal room ID set.
        - Ensures the bot is joined to all configured rooms.
        - Performs an initial full-state sync; any exception during this step is logged and startup proceeds.
        - Enters the long-running `sync_forever` loop to process events.

        This method is asynchronous and does not return; it only returns when the client's sync loop ends or raises.
        """
        # Store bot start time in epoch milliseconds to compare with event.server_timestamp
        self.start_time = int(time.time() * 1000)
        logger.info("Initializing BibleBot...")

        # Initialize HTTP session for connection pooling
        if self.http_session is None:
            try:
                self.http_session = aiohttp.ClientSession(
                    timeout=aiohttp.ClientTimeout(total=API_REQUEST_TIMEOUT_SEC)
                )
            except aiohttp.ClientError:
                logger.exception("Failed to create HTTP session")
                raise
        await self.resolve_aliases()  # Support for aliases in config
        self._room_id_set = set(self.config[CONFIG_MATRIX_ROOM_IDS])
        await self.ensure_joined_rooms()  # Ensure bot is in all configured rooms

        logger.info("Performing initial sync...")
        try:
            await self.client.sync(timeout=SYNC_TIMEOUT_MS, full_state=True)
            logger.info("Initial sync complete.")
        except Exception as e:
            # Check if this is the one_time_key_counts validation error
            error_msg = str(e)
            if "one_time_key_counts" in error_msg and "required property" in error_msg:
                logger.warning(
                    "⚠️  Matrix server did not provide device_one_time_keys_count in sync response. "
                    "This is normal for some servers when no one-time keys exist. "
                    "Continuing without E2EE validation."
                )
                # Try sync again with a timeout to see if it recovers
                try:
                    await asyncio.sleep(1)  # Brief pause
                    await self.client.sync(timeout=SYNC_TIMEOUT_MS, full_state=False)
                    logger.info("Recovery sync complete.")
                except Exception as recovery_error:
                    logger.warning(f"Recovery sync also failed: {recovery_error}")
                    logger.info("Continuing with bot startup despite sync issues...")
            else:
                logger.exception("Error during initial sync")
                # We'll log and continue, as sync_forever might recover.

        logger.info("Starting bot event processing loop...")
        await self.client.sync_forever(timeout=SYNC_TIMEOUT_MS)  # Sync every 30 seconds

    async def close(self):
        """
        Clean up resources used by the bot.

        Closes the HTTP session if it exists to prevent resource leaks.
        """
        if self.http_session:
            await self.http_session.close()
            self.http_session = None

    async def on_decryption_failure(self, room: MatrixRoom, event: MegolmEvent) -> None:
        """
        Handle a Megolm event that failed to decrypt by requesting the missing session keys.

        If the event cannot be decrypted, this will request the needed room key from the sender. As a side effect the event's `room_id` may be set/updated to the provided room's id. The method prefers the client's `request_room_key` API and falls back to creating and sending a to-device key request when necessary. Exceptions are logged and not propagated.
        """
        # Check if E2EE is enabled in config
        e2ee_config = self.config.get("matrix", {}).get("e2ee", {})
        e2ee_enabled = e2ee_config.get("enabled", False)

        if not e2ee_enabled:
            logger.warning(
                f"⚠️  Received encrypted message in room '{room.room_id}' but E2EE is disabled in config! "
                f"Enable E2EE in your config.yaml under matrix.e2ee.enabled to decrypt messages. "
                f"Event ID: {getattr(event, 'event_id', '?')}"
            )
            return

        logger.warning(
            f"Failed to decrypt event '{getattr(event, 'event_id', '?')}' in room '{room.room_id}'. "
            f"This is usually temporary and resolves on its own. "
            f"If this persists, the bot's session may be corrupt."
        )
        try:
            # Set room_id on the event object for key request methods
            # This is necessary because MegolmEvent objects that failed to decrypt
            # may not have room_id set, but event.as_key_request() requires it
            # Note: This mutates the event object to ensure proper key request functionality
            event.room_id = room.room_id

            # Try the high-level API first
            try:
                await self.client.request_room_key(event)
                logger.info(
                    f"Requested keys via client.request_room_key for event {getattr(event, 'event_id', '?')}"
                )
            except nio.exceptions.LocalProtocolError:
                # Duplicate/pending request — fall back to manual to-device path
                request = event.as_key_request(
                    self.client.user_id, getattr(self.client, "device_id", None)
                )
                await self.client.to_device(request)
                logger.info(
                    f"Requested keys via to_device for event {getattr(event, 'event_id', '?')}"
                )
        except Exception:
            logger.exception(
                f"Failed to request keys for event {getattr(event, 'event_id', '?')}"
            )

    async def on_invite(self, room: MatrixRoom, _event: InviteEvent):
        """
        Handle an incoming room invite: join the room when it is listed in the bot's configured rooms; otherwise log a warning.

        Parameters:
            room (MatrixRoom): The room the bot was invited to.
            event (InviteEvent): The invite event (unused by this handler).
        """
        if room.room_id in self._room_id_set:
            logger.info(f"Received invite for configured room: {room.room_id}")
            await self.join_matrix_room(room.room_id)
        else:
            logger.warning(f"Received invite for non-configured room: {room.room_id}")

    async def send_reaction(self, room_id, event_id, emoji):
        content = {
            "m.relates_to": {
                "rel_type": "m.annotation",
                "event_id": event_id,
                "key": emoji,
            }
        }
        try:
            await self.client.room_send(
                room_id,
                "m.reaction",
                content,
                ignore_unverified_devices=True,
            )
        except (nio.exceptions.MatrixRequestError, aiohttp.ClientError) as e:
            logger.warning(f"Failed to send reaction: {e}", exc_info=True)
        except Exception:
            logger.exception("Unexpected error sending reaction")

    async def _send_error_message(self, room_id: str, message: str):
        """Send a formatted error message to a room."""
        content = {
            "msgtype": "m.text",
            "body": message,
            "format": "org.matrix.custom.html",
            "formatted_body": html.escape(message),
        }
        try:
            await self.client.room_send(
                room_id,
                "m.room.message",
                content,
                ignore_unverified_devices=True,
            )
        except Exception:
            logger.exception(f"Failed to send error message to room {room_id}")

    async def on_room_message(self, room: MatrixRoom, event: RoomMessageText):
        """
        Handle incoming room message events, detect Bible verse references, and trigger scripture processing.

        Only processes messages that:
        - originate in configured rooms,
        - are not sent by the bot itself, and
        - were sent after the bot's recorded start time.

        Scans the message text with REFERENCE_PATTERNS (exact match) or PARTIAL_REFERENCE_PATTERNS
        (anywhere in message) based on detect_references_anywhere setting. When a match is found it:
        - validates and normalizes the book name with validate_and_normalize_book_name(),
        - constructs a passage string "<Book> <Reference>",
        - determines the requested translation (falls back to DEFAULT_TRANSLATION),
        - logs the detected reference, and
        - invokes handle_scripture_command(room_id, passage, translation, event) to produce a reply.

        Parameters are typed (MatrixRoom, RoomMessageText) and represent the source room and the received event.
        This handles both unencrypted messages and successfully decrypted messages from encrypted rooms.
        """
        # Log message reception for debugging encrypted room issues
        logger.debug(
            f"Received RoomMessageText in room {room.room_id} from {event.sender}: "
            f"encrypted={room.encrypted}, decrypted={getattr(event, 'decrypted', False)}"
        )

        if (
            room.room_id in self._room_id_set
            and event.sender != self.client.user_id
            and event.server_timestamp > self.start_time
        ):
            # Choose patterns and matcher function based on configuration
            use_search = self.detect_references_anywhere
            search_patterns = (
                PARTIAL_REFERENCE_PATTERNS if use_search else REFERENCE_PATTERNS
            )

            passage = None
            translation = self.default_translation  # Default translation
            for pattern in search_patterns:
                match = (
                    pattern.search(event.body)
                    if use_search
                    else pattern.fullmatch(event.body)
                )
                if match:
                    raw_book_name = match.group(1).strip()

                    # Validate and normalize the book name in one optimized step
                    book_name = validate_and_normalize_book_name(raw_book_name)
                    if not book_name:
                        continue  # Skip if not a valid Bible book

                    verse_reference = match.group(2).strip()
                    passage = f"{book_name} {verse_reference}"

                    # Get optional translation group - all patterns have exactly 3 groups
                    trans_group = match.group(3)
                    translation = (
                        trans_group.lower() if trans_group else self.default_translation
                    )
                    logger.info(
                        f"Detected Bible reference: {passage} ({translation}) in room {room.room_id}"
                    )
                    break

            if passage:
                await self.handle_scripture_command(
                    room.room_id, passage, translation, event
                )

    def _format_text_for_display(self, text: str) -> tuple[str, str]:
        """
        Format a passage for plain-text and HTML-safe display according to the bot's poetry-preservation setting.

        When preserve_poetry_formatting is True, this preserves paragraph/newline structure (collapsing multiple blank lines to a single blank line), normalizes internal spaces, strips leading/trailing whitespace, and converts newlines to HTML <br /> tags for the HTML output. When False, all whitespace (including newlines) is collapsed to single spaces. Both returned strings are HTML-escaped where appropriate.

        Returns:
            tuple[str, str]: (plain_text, html_text) — the normalized plain-text string and an HTML-safe representation suitable for sending as formatted message content.
        """
        if self.preserve_poetry_formatting:
            # Poetry mode: preserve newlines, clean excess whitespace
            import re

            formatted_text = re.sub(
                r"[ \t]+", " ", text
            )  # Multiple spaces/tabs -> single space
            formatted_text = re.sub(
                r"\n\s*\n", "\n\n", formatted_text
            )  # Multiple newlines -> double newline
            formatted_text = (
                formatted_text.strip()
            )  # Remove leading/trailing whitespace
            html_text = html.escape(formatted_text).replace("\n", "<br />")
        else:
            # Default mode: collapse all whitespace (original behavior)
            formatted_text = " ".join(text.replace("\n", " ").split())
            html_text = html.escape(formatted_text)

        return formatted_text, html_text

    def _split_text_into_chunks(self, text, max_length):
        """
        Split text into chunks of specified maximum length, preferring word boundaries.

        Parameters:
            text (str): The text to split
            max_length (int): Maximum length for each chunk

        Returns:
            list[str]: List of text chunks
        """
        return textwrap.wrap(
            text,
            width=max_length,
            break_long_words=True,
            replace_whitespace=False,
            break_on_hyphens=True,
        )

    def _trim_reference_for_suffix(self, reference, reserve_fallback_space=False):
        """
        Ensure a Bible reference fits when appended with the message suffix by trimming or dropping it.

        If the full reference would cause the final message (text + " - " + reference + MESSAGE_SUFFIX) to exceed the bot's max_message_length, this returns a truncated reference that fits (using "..." when space allows) or None if the reference must be omitted.

        Parameters:
            reference (str | None): The canonical Bible reference to trim; None or empty returns None.
            reserve_fallback_space (bool): When True, reserve space for the worst-case fallback message
                (FALLBACK_MESSAGE_TOO_LONG) instead of assuming at least one character of text. Use this
                when preparing a single-message response that may need to replace the passage text with a
                fallback placeholder.

        Returns:
            str | None: A reference string guaranteed to fit with the suffix and reserved text, or None
            when no acceptable reference can be included.
        """
        if not reference:
            return None

        # Calculate budget for reference (reserve space for " - ", MESSAGE_SUFFIX, and text)
        if reserve_fallback_space:
            # Reserve space for fallback text in single-message path. This is conservative,
            # reserving space for the worst-case scenario where the message text itself is
            # so long it must be replaced by FALLBACK_MESSAGE_TOO_LONG. This guarantees
            # the final combined message (text + reference + suffix) will not exceed max_message_length.
            reserved_text_len = len(FALLBACK_MESSAGE_TOO_LONG)
        else:
            # Reserve space for at least 1 character of text in splitting path
            reserved_text_len = 1

        budget = (
            self.max_message_length
            - len(MESSAGE_SUFFIX)
            - REFERENCE_SEPARATOR_LEN
            - reserved_text_len
        )
        if budget <= 0:
            # Not enough space even for minimal reference, drop it entirely
            return None

        # Check if full reference fits within budget
        if len(reference) <= budget:
            return reference

        # Truncate reference with truncation indicator if needed
        if budget >= len(TRUNCATION_INDICATOR):  # Need space for truncation indicator
            keep = max(0, budget - len(TRUNCATION_INDICATOR))
            return reference[:keep] + TRUNCATION_INDICATOR if keep > 0 else None
        else:
            return None

    async def _send_message_parts(self, room_id, text_parts, reference):
        """
        Send a sequence of message parts to a room, appending the reference and message suffix only to the final part.

        Each part is formatted for both plain text and HTML (using _format_text_for_display). The last part will include " - {reference}{MESSAGE_SUFFIX}" when a reference is provided; otherwise it will include MESSAGE_SUFFIX alone. Messages are sent via the Matrix client with guarded handling for 429 (rate-limited) responses: on 429 the method will perform exponential backoff with jitter and retry up to three times before propagating the error.

        Parameters:
            room_id (str): Matrix room ID to send the messages to.
            text_parts (list[str]): Ordered list of message body parts to send.
            reference (str | None): Bible reference to append to the final message, or None to omit.

        Raises:
            nio.exceptions.MatrixRequestError: If a send fails for reasons other than handled rate limiting.
            Exception: Propagates other unexpected exceptions from the Matrix client.
        """
        for i, text_part in enumerate(text_parts):
            # Format the text part
            formatted_text, html_text = self._format_text_for_display(text_part)

            # Only add reference and suffix to the last message
            if i == len(text_parts) - 1:
                if reference:
                    plain_body = f"{formatted_text} - {reference}{MESSAGE_SUFFIX}"
                    formatted_body = f"{html_text} - {html.escape(reference)}{html.escape(MESSAGE_SUFFIX)}"
                else:
                    plain_body = f"{formatted_text}{MESSAGE_SUFFIX}"
                    formatted_body = f"{html_text}{html.escape(MESSAGE_SUFFIX)}"
            else:
                plain_body = formatted_text
                formatted_body = html_text

            content = {
                "msgtype": "m.text",
                "body": plain_body,
                "format": "org.matrix.custom.html",
                "formatted_body": formatted_body,
            }

            # Send with enhanced rate limit handling
            retries = MAX_RATE_LIMIT_RETRIES
            while True:
                try:
                    await self.client.room_send(
                        room_id,
                        "m.room.message",
                        content,
                        ignore_unverified_devices=True,
                    )
                    break  # Success
                except nio.exceptions.MatrixRequestError as e:
                    # Enhanced handling for rate limiting with bounded retries
                    if retries > 0 and getattr(e, "status", None) == 429:
                        retry_ms = int(
                            getattr(e, "retry_after_ms", DEFAULT_RETRY_AFTER_MS)
                        )
                        base_delay = (
                            retry_ms
                            / 1000.0
                            * (2 ** (MAX_RATE_LIMIT_RETRIES - retries))
                        )  # Exponential backoff
                        # Add ±20% jitter to avoid thundering herd
                        delay = base_delay * random.uniform(
                            0.8, 1.2
                        )  # nosec B311 - not cryptographic
                        logger.warning(
                            f"Rate limited; backing off for {delay:.1f}s (attempt {MAX_RATE_LIMIT_RETRIES + 1 - retries}/{MAX_RATE_LIMIT_RETRIES})"
                        )
                        await asyncio.sleep(delay)
                        retries -= 1
                    else:
                        raise

    async def handle_scripture_command(self, room_id, passage, translation, event):
        """
        Handle a detected Bible reference: fetch the passage and post a formatted response to the given room.

        Fetches the requested passage (using the provided or default translation and cache), formats it for plain and HTML display, reacts to the triggering event with a checkmark, and sends the passage text plus its canonical reference to the room. If the passage exceeds configured length limits the bot will either:
        - split the text into multiple parts (when split_message_length is enabled) and append the reference only to the final part, or
        - truncate the text and append an ellipsis and reference, or
        - fall back to a short placeholder when truncation cannot produce a valid message.

        On failures the function posts a user-facing error message for missing API keys, not-found passages, or network errors. Unexpected exceptions are logged and result in the same generic error message being posted.

        Parameters:
            room_id (str): Matrix room ID where the response should be posted.
            passage (str): Detected Bible passage reference (e.g., "John 3:16").
            translation (str | None): Translation code to use; if None the bot's default_translation is used.
            event: The original Matrix event that triggered the command (used to send a reaction).

        Returns:
            None
        """
        # Use configured default translation if none specified
        if translation is None:
            translation = self.default_translation

        logger.info(f"Fetching scripture passage: {passage} ({translation.upper()})")

        try:
            text, reference = await get_bible_text(
                passage,
                translation,
                self.api_keys,
                cache_enabled=self.cache_enabled,
                default_translation=self.default_translation,
                session=self.http_session,
            )

            # Format text based on configuration
            text, _ = self._format_text_for_display(text)

            # Check if text is empty after cleaning
            if not text:
                logger.warning(f"Retrieved empty passage text for: {passage}")
                return

            # Send a checkmark reaction to the original message
            await self.send_reaction(room_id, event.event_id, REACTION_OK)

            # Check if message splitting is enabled and needed
            if (
                self.split_message_length
                and self.split_message_length > 0
                and len(text) > self.split_message_length
            ):
                # Trim reference if needed for splitting context
                trimmed_reference = self._trim_reference_for_suffix(
                    reference, reserve_fallback_space=False
                )
                plain_suffix = (
                    f" - {trimmed_reference}{MESSAGE_SUFFIX}"
                    if trimmed_reference
                    else MESSAGE_SUFFIX
                )
                reserved_last = len(plain_suffix)
                chunk_limit = min(self.split_message_length, self.max_message_length)
                last_chunk_limit = max(
                    1,
                    min(
                        self.split_message_length,
                        self.max_message_length - reserved_last,
                    ),
                )

                # If splitting is practical, do it and return
                if last_chunk_limit >= MIN_PRACTICAL_CHUNK_SIZE:
                    text_chunks = self._split_text_into_chunks(text, chunk_limit)
                    if text_chunks and len(text_chunks[-1]) > last_chunk_limit:
                        tail = text_chunks.pop()
                        text_chunks.extend(
                            self._split_text_into_chunks(tail, last_chunk_limit)
                        )

                    logger.info(f"Splitting message into {len(text_chunks)} parts")
                    await self._send_message_parts(
                        room_id, text_chunks, trimmed_reference
                    )

                    if trimmed_reference:
                        logger.info(f"Sent split scripture: {trimmed_reference}")
                    else:
                        logger.info("Sent split scripture response")
                    return  # We are done, exit the function

                logger.info(
                    "Suffix too large for effective splitting; using single-message path"
                )

            # Single-message logic (truncation)
            # This path is taken if splitting is disabled, not needed, or impractical.
            trimmed_reference = self._trim_reference_for_suffix(
                reference, reserve_fallback_space=True
            )
            plain_suffix = (
                f" - {trimmed_reference}{MESSAGE_SUFFIX}"
                if trimmed_reference
                else MESSAGE_SUFFIX
            )
            message_text = text

            if len(f"{text}{plain_suffix}") > self.max_message_length:
                suffix_len = len(plain_suffix) + len(TRUNCATION_INDICATOR)
                max_text_len = self.max_message_length - suffix_len
                if max_text_len > 0:
                    message_text = text[:max_text_len] + TRUNCATION_INDICATOR
                    logger.debug(
                        f"Truncated message from {len(text)} to {len(message_text)} characters"
                    )
                else:
                    message_text = FALLBACK_MESSAGE_TOO_LONG

            await self._send_message_parts(room_id, [message_text], trimmed_reference)

            if trimmed_reference:
                logger.info(f"Sent scripture: {trimmed_reference}")
            else:
                logger.info("Sent scripture response")

        except APIKeyMissing as e:
            logger.warning(f"Failed to retrieve passage: {passage} ({e})")
            # Send helpful message about missing API key
            api_key_error = f"ESV translation requires an API key. Please configure one in your config.yaml or use KJV instead. (Try: {passage} kjv)"
            await self._send_error_message(room_id, api_key_error)
        except PassageNotFound as e:
            logger.warning(f"Failed to retrieve passage: {passage} ({e})")
            await self._send_error_message(room_id, ERROR_PASSAGE_NOT_FOUND)
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            # Network or timeout errors - could be retried
            logger.warning(f"Network error during passage lookup for {passage}: {e}")
            await self._send_error_message(room_id, ERROR_PASSAGE_NOT_FOUND)
        except Exception:
            # Log full traceback but send generic message to user
            logger.exception(
                f"Unexpected exception during passage lookup for {passage} "
                f"(translation={translation}, cache_enabled={self.cache_enabled})"
            )
            await self._send_error_message(room_id, ERROR_PASSAGE_NOT_FOUND)


# Run bot
async def main(config_path=DEFAULT_CONFIG_FILENAME_MAIN, config=None):
    """
    Main entry point for the bot.
    Loads configuration, sets up the bot, and starts processing events.

    Parameters:
        config_path (str): Path to the configuration file.
        config (dict, optional): Pre-loaded configuration. If provided, config_path is only used for environment loading.
    """
    # Load config and environment variables (only if not already provided)
    if config is None:
        config = load_config(config_path)
        if not config:
            logger.error(f"Failed to load configuration from {config_path}")
            raise RuntimeError(f"Failed to load configuration from {config_path}")

    matrix_access_token, api_keys = load_environment(config, config_path)
    creds = load_credentials()

    # Determine E2EE configuration from config
    matrix_section = (
        config.get(CONFIG_KEY_MATRIX, {})
        if isinstance(config.get(CONFIG_KEY_MATRIX), dict)
        else {}
    )
    e2ee_cfg = (
        matrix_section.get(CONFIG_MATRIX_E2EE) or matrix_section.get("encryption") or {}
    )
    e2ee_enabled = bool(e2ee_cfg.get("enabled", False))

    # Create AsyncClient with optional E2EE store
    client_config = AsyncClientConfig(
        store_sync_tokens=True, encryption_enabled=e2ee_enabled
    )

    logger.info("Creating AsyncClient")
    if creds:
        # Modern auth flow - use credentials
        client = AsyncClient(
            creds.homeserver,
            creds.user_id,
            store_path=str(get_store_dir()) if e2ee_enabled else None,
            config=client_config,
        )
    else:
        # Legacy fallback - requires homeserver and user in config
        if not matrix_access_token:
            logger.error(
                "No credentials found. Please run 'biblebot auth login' first."
            )
            logger.error(
                "Legacy MATRIX_ACCESS_TOKEN is deprecated and does not support E2EE."
            )
            raise RuntimeError(
                "No credentials found. Please run 'biblebot auth login' first."
            )

        # For legacy mode, we need homeserver and user from environment or config
        homeserver = (
            os.getenv("MATRIX_HOMESERVER")
            or config.get("matrix_homeserver")
            or config.get("matrix", {}).get("homeserver")
        )
        user_id = (
            os.getenv("MATRIX_USER_ID")
            or config.get("matrix_user")
            or config.get("matrix", {}).get("user")
        )

        if not homeserver or not user_id:
            logger.error(
                "Legacy mode requires MATRIX_HOMESERVER and MATRIX_USER_ID set as environment variables or in config.yaml"
            )
            logger.error(
                "Please run 'biblebot auth login' for the modern authentication flow"
            )
            raise RuntimeError(
                "Legacy mode requires MATRIX_HOMESERVER and MATRIX_USER_ID"
            )

        client = AsyncClient(
            homeserver,
            user_id,
            store_path=str(get_store_dir()) if e2ee_enabled else None,
            config=client_config,
        )

    logger.info("Creating BibleBot instance")
    bot = BibleBot(config, client)
    bot.api_keys = api_keys

    if creds:
        logger.info("Using saved credentials.json for Matrix session")
        if matrix_access_token:
            logger.debug(
                "Found credentials.json, ignoring legacy MATRIX_ACCESS_TOKEN environment variable."
            )
        client.restore_login(
            user_id=creds.user_id,
            device_id=creds.device_id,
            access_token=creds.access_token,
        )
    else:
        if matrix_access_token:
            logger.warning(
                "⚠️  Using MATRIX_ACCESS_TOKEN environment variable. This is deprecated and does NOT support E2EE."
            )
            logger.warning(
                "⚠️  Consider using 'biblebot auth login' for secure session-based authentication with E2EE support."
            )
            client.access_token = matrix_access_token
        else:
            logger.error(ERROR_NO_CREDENTIALS_AND_TOKEN)
            logger.error(ERROR_AUTH_INSTRUCTIONS)
            raise RuntimeError("No credentials or access token found")

    # If E2EE is enabled, ensure keys are uploaded
    if e2ee_enabled:
        try:
            if client.should_upload_keys:
                logger.info("Uploading encryption keys...")
                await client.keys_upload()
                logger.info("Encryption keys uploaded")
        except (
            nio.exceptions.LocalProtocolError,
            nio.exceptions.RemoteProtocolError,
            nio.exceptions.RemoteTransportError,
            aiohttp.ClientError,
        ):
            logger.exception("Failed to upload E2EE keys")

    # Register event handlers
    logger.debug("Registering event handlers")
    client.add_event_callback(bot.on_invite, InviteEvent)
    client.add_event_callback(bot.on_room_message, RoomMessageText)

    # Register encrypted message handlers for E2EE rooms
    if e2ee_enabled:
        try:
            # Handle decryption failures for encrypted messages
            # Note: Successfully decrypted messages are automatically converted to RoomMessageText by matrix-nio
            client.add_event_callback(bot.on_decryption_failure, MegolmEvent)
        except AttributeError:
            logger.debug(
                "E2EE callback registration not supported by this nio version",
                exc_info=True,
            )

    # Start the bot
    try:
        await bot.start()
    finally:
        try:
            # Only call close if it's a real BibleBot instance (not a mock)
            if bot and hasattr(bot, "close") and hasattr(bot, "http_session"):
                await bot.close()
        except (AttributeError, TypeError) as e:
            # Handle mock objects or missing attributes gracefully
            logger.debug(f"Cleanup skipped for mock/test object: {e}")
        except Exception:
            logger.debug("Unexpected cleanup error during bot shutdown", exc_info=True)
        finally:
            if client:
                try:
                    await client.close()
                except Exception:
                    logger.debug(
                        "Ignoring client.close() error during shutdown", exc_info=True
                    )


async def main_with_config(config_path: str, config: dict):
    """
    Main entry point for the bot with pre-loaded configuration.
    This avoids duplicate config loading when called from CLI.
    """
    return await main(config_path, config)
