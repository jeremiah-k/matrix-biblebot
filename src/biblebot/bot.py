"""
Matrix BibleBot - Core bot implementation.

This module contains the main BibleBot class and supporting functions for:
- Bible verse fetching from multiple APIs (bible-api.com, ESV API)
- Matrix message handling and room management
- Reference parsing and validation
- Message formatting and splitting
- Rate limiting and error handling
- Configuration management and environment loading

The bot supports both KJV (default) and ESV translations, with extensible
architecture for additional Bible APIs. It handles both encrypted and
unencrypted Matrix rooms, with proper E2EE support when available.
"""

import asyncio
import copy
import html
import logging
import os
import time
from typing import Any, Mapping
from unittest.mock import MagicMock

import aiohttp
from dotenv import load_dotenv
from nio import (
    AsyncClient,
    AsyncClientConfig,
    InviteEvent,
    LocalProtocolError,
    MatrixRoom,
    MegolmEvent,
    RemoteProtocolError,
    RemoteTransportError,
    RoomMessageText,
    RoomResolveAliasError,
)

from biblebot.auth import get_store_dir, load_credentials
from biblebot.config import load_config_file
from biblebot.constants.api import (
    API_REQUEST_TIMEOUT_SEC,
)
from biblebot.constants.app import LOGGER_NAME
from biblebot.constants.bible import (
    DEFAULT_TRANSLATION,
    TRANSLATION_ESV,
)
from biblebot.constants.config import (
    CONFIG_KEY_MATRIX,
    CONFIG_MATRIX_E2EE,
    CONFIG_MATRIX_ROOM_IDS,
    CONFIG_PRESERVE_POETRY_FORMATTING,
    DEFAULT_CONFIG_FILENAME,
    DEFAULT_ENV_FILENAME,
    ENV_ESV_API_KEY,
    ENV_MATRIX_ACCESS_TOKEN,
)
from biblebot.constants.logging import LOGGER_NIO
from biblebot.constants.matrix import (
    MAX_RATE_LIMIT_RETRIES,
    MIN_PRACTICAL_CHUNK_SIZE,
    SYNC_TIMEOUT_MS,
)
from biblebot.constants.messages import (
    ERROR_AUTH_INSTRUCTIONS,
    ERROR_NO_CREDENTIALS_AND_TOKEN,
    ERROR_PASSAGE_NOT_FOUND,
    ERROR_SEND_OTHER,
    FALLBACK_MESSAGE_TOO_LONG,
    INFO_API_KEY_FOUND,
    INFO_LOADING_ENV,
    INFO_NO_API_KEY,
    INFO_NO_ENV_FILE,
    INFO_RESOLVED_ALIAS,
    MESSAGE_SUFFIX,
    REACTION_OK,
    TRUNCATION_INDICATOR,
    WARN_COULD_NOT_RESOLVE_ALIAS,
    WARN_MATRIX_ACCESS_TOKEN_NOT_SET,
)
from biblebot.formatting import (
    format_text_for_display,
    split_text_into_chunks,
    trim_reference_for_suffix,
)
from biblebot.log_utils import configure_component_loggers, configure_logging
from biblebot.messaging import (
    classify_send_failure,
    compose_final_chunk_bodies,
    is_error_response,
    is_rate_limit_response,
    response_retry_delay_seconds,
    send_failure_notice,
)
from biblebot.passages import (  # noqa: F401 - re-export for import compatibility
    APIKeyMissing,
    PassageNotFound,
    get_bible_text,
    get_esv_text,
    get_kjv_text,
    make_api_request,
)
from biblebot.protocols import BotClient
from biblebot.rooms import (
    is_alias,
    is_placeholder_room_id,
    merge_resolved_entries,
    read_room_ids,
)
from biblebot.triggers import detect_trigger
from biblebot.update_check import (
    perform_startup_update_check,
    print_startup_banner,
)

# Configure logging
logger = logging.getLogger(LOGGER_NAME)


class MessageSendError(Exception):
    """Raised when a Matrix message send fails at the transport level.

    nio reports Matrix-level (HTTP) failures by returning an
    ``ErrorResponse`` rather than raising; transport-level failures such as
    dropped connections surface as exceptions and are wrapped in this type.
    """


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
    result = load_config_file(config_file)
    if not result.ok:
        for diagnostic in result.diagnostics:
            logger.error(diagnostic.message)
        return None

    if result.converted_legacy:
        logger.info("Converting legacy flat config structure to nested structure")
    if log_loading:
        logger.info(f"Loaded configuration from {config_file}")
    return result.config


# Load environment variables
def load_environment(
    config: Mapping[str, Any] | None,
    config_path: str | os.PathLike[str],
) -> tuple[str | None, dict[str, str | None]]:
    """
    Load Matrix access token and translation API keys from configuration and environment.

    Checks the provided config dict for an "api_keys" mapping and reads legacy .env files (first looking beside config_path, then the current working directory). Environment variables take precedence over config values. Emits deprecation warnings when a legacy .env file is loaded or legacy environment-based access tokens are used.

    Parameters:
        config (dict): Parsed configuration (typically from YAML). If present, the function will read config["api_keys"]["esv"] when available.
        config_path (str): Filesystem path to the active config file; its directory is searched for a legacy .env file.

    Returns:
        tuple: (matrix_access_token, api_keys)
            - matrix_access_token (str | None): value of the MATRIX_ACCESS_TOKEN environment variable if set, otherwise None.
            - api_keys (dict): mapping of translation identifiers to API keys. Always contains the `TRANSLATION_ESV` key (value may be None).
    """
    # Initialize with expected keys set to None
    api_keys: dict[str, str | None] = {TRANSLATION_ESV: None}

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


class BibleBot:
    def __init__(
        self,
        config: Any,
        client: BotClient,
    ) -> None:
        """
        Initialize the BibleBot with configuration and a Matrix client.

        Read bot-specific settings from config["bot"], apply defaults, and coerce/validate numeric and boolean options to safe runtime values.

        Recognized settings (all under config["bot"]):
        - default_translation (str): translation to use when none is specified. Default: DEFAULT_TRANSLATION.
        - cache_enabled (bool): enable in-memory passage caching. Default: True.
        - max_message_length (int): maximum length of outgoing messages. Non-positive values are reset to 2000. Default: 2000.
        - split_message_length (int): threshold for splitting long messages into multiple parts. Non-integer or negative values disable splitting (0). Values larger than max_message_length are capped to max_message_length. Default: 0 (disabled).
        - preserve_poetry_formatting (bool): preserve original line breaks for poetry-style passages. Default: False.

        Parameters:
            config (dict): Loaded configuration mapping used to populate bot settings.
            client (BotClient): Required Matrix client implementation. In production this is ``nio.AsyncClient``; tests may inject a compatible test double directly. The client must satisfy the ``biblebot.protocols.BotClient`` structural type.

        Notes:
        - The initializer enforces type coercion and caps to prevent generating oversized message chunks.
        """
        self.config = config
        self.client: BotClient = client  # Injected client (AsyncClient or test double)
        self.api_keys: Any = {}  # Will be set in main()
        self._room_id_set: set[str] = set()
        self.http_session: aiohttp.ClientSession | None = (
            None  # set in start(), closed in close()
        )

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

        The string includes the list of keys present in the bot's `config` (empty list if `config` is not a dict). The client is always present after construction so it is not advertised in the repr.

        Returns:
            str: A representation like "BibleBot(config_keys=['a','b'])".
        """
        keys = list(self.config.keys()) if isinstance(self.config, dict) else []
        return f"BibleBot(config_keys={keys})"

    @classmethod
    def for_testing(
        cls,
        config: Any,
        *,
        client: BotClient | None = None,
    ) -> "BibleBot":
        """Construct a BibleBot with an auto-generated MagicMock client.

        Convenience factory for tests that exercise bot behavior other than the
        Matrix client contract (configuration parsing, formatting, dispatch,
        ``__repr__``, etc.). When ``client`` is None a ``MagicMock`` that
        satisfies ``biblebot.protocols.BotClient`` is created automatically.
        The factory deep-copies ``config`` so mutations to the original dict
        after construction do not leak into the bot.

        Tests that depend on specific client behavior (e.g. message dispatch
        tests) should construct the bot directly with an explicit client.

        Parameters:
            config (Any): The configuration mapping passed to ``__init__``.
                Deep-copied so the factory does not retain a reference.
            client (BotClient | None): Optional explicit client override. When
                omitted, a spec'd MagicMock is created for the test.

        Returns:
            BibleBot: An instance with the client attribute populated. The bot's
            ``config`` attribute is an independent copy of the input.
        """
        if client is None:
            mock_client = MagicMock(spec=BotClient)
            mock_client.user_id = None
            mock_client.device_id = None
            mock_client.rooms = {}
            test_client: BotClient = mock_client
        else:
            test_client = client
        return cls(copy.deepcopy(config), test_client)

    async def resolve_aliases(self):
        """
        Resolve Matrix room aliases configured for the bot and replace them with canonical room IDs.

        For each entry in the configured room list (supports both legacy top-level and nested
        `matrix.room_ids` schemas), entries beginning with "#" are resolved via the Matrix
        client's alias resolution. Resolved room IDs replace aliases; non-alias entries are
        kept. The final list preserves the original order, removes duplicates (first-occurrence
        wins), and is written back into self.config using the same schema that was present.

        Side effects:
        - Updates self.config in place with the resolved, deduplicated room IDs.
        - Logs info for successful resolutions and warnings for aliases that could not be resolved.
        """
        resolved_ids = []
        room_ids = read_room_ids(self.config)
        for entry in room_ids:
            if is_alias(entry):
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
        # This deduplicates room IDs and replaces aliases with their resolved room IDs
        # to avoid duplicate joins and ensure we're working with canonical room IDs
        unique_ids = merge_resolved_entries(room_ids, resolved_ids)
        if (
            CONFIG_KEY_MATRIX in self.config
            and "room_ids" in self.config[CONFIG_KEY_MATRIX]
        ):
            self.config[CONFIG_KEY_MATRIX]["room_ids"] = unique_ids
        else:
            self.config[CONFIG_MATRIX_ROOM_IDS] = unique_ids

    async def join_matrix_room(self, room_id_or_alias):
        """
        Join a Matrix room given a room ID or alias.

        Resolves a room alias (strings starting with '#') to a canonical room ID and attempts to join the room if the bot is not already a member. Placeholder/sample room IDs are ignored. Failures are logged and the method will not raise; it always returns None.

        Parameters:
            room_id_or_alias (str): A Matrix room identifier — either a room ID (e.g. "!abc:example.org") or an alias (e.g. "#room:example.org").
        """
        # Skip placeholder room IDs from sample config to prevent attempting to join
        # non-existent rooms that are just examples in the configuration template
        # This occurs when users haven't updated their config.yaml from the sample
        if (
            room_id_or_alias.startswith("!your_room_id:")
            or room_id_or_alias.endswith(":your_homeserver_domain")
            or is_placeholder_room_id(room_id_or_alias)
        ):
            logger.debug(f"Skipping placeholder room ID: {room_id_or_alias}")
            return

        try:
            if is_alias(room_id_or_alias):
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
            LocalProtocolError,
            RemoteProtocolError,
            RemoteTransportError,
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
        Start the bot: perform startup tasks and enter the continuous Matrix sync loop.

        Sets self.start_time (epoch ms), ensures an aiohttp session exists, resolves configured room aliases,
        builds the internal room ID set, and attempts to join all configured rooms. Performs an initial full-state
        sync (with a guarded recovery attempt for a known one_time_key_counts validation condition) and then
        hands control to the client's long-running sync_forever loop to process events.

        Side effects:
        - Updates self.start_time.
        - May create and store an aiohttp.ClientSession in self.http_session.
        - May join Matrix rooms and send network requests via the Matrix client.

        Exceptions:
        - asyncio.CancelledError is re-raised to preserve cancellation semantics.
        - aiohttp.ClientError (or subclasses) raised while creating the HTTP session may propagate.

        Returns:
        - None; this coroutine only returns when the client's sync loop ends or is cancelled.
        """
        # Store bot start time in epoch milliseconds to compare with event.server_timestamp
        self.start_time = int(time.time() * 1000)
        logger.info("Initializing BibleBot...")

        # Initialize HTTP session for connection pooling and API requests
        # This is created here (rather than in __init__) because aiohttp sessions
        # must be created within an async context and after the event loop is running
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
        except asyncio.CancelledError:
            raise
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
                except asyncio.CancelledError:
                    raise
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
        Handle Megolm decryption failures by requesting the missing session keys.

        When an encrypted event cannot be decrypted, attempt to recover by requesting the room key from the sender. The method sets event.room_id to the room's id if necessary, then prefers the client's high-level request_room_key API and falls back to sending a manual to-device key request when the high-level call is not usable. All errors are logged and not raised to callers; the method returns None.
        """
        # Check if E2EE is enabled in config
        e2ee_config = self.config.get("matrix", {}).get("e2ee", {})
        e2ee_enabled = e2ee_config.get("enabled", False)

        if not e2ee_enabled:
            # E2EE is disabled in config but we received an encrypted message
            # This happens when the bot is in an encrypted room but the user hasn't enabled E2EE support
            # The bot cannot decrypt the message without E2EE enabled and proper key management
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
            # This occurs when the nio library receives encrypted events but cannot
            # decrypt them due to missing keys - the room_id field may be missing
            # Note: This mutates the event object to ensure proper key request functionality
            event.room_id = room.room_id

            # Try the high-level API first
            try:
                await self.client.request_room_key(event)
                logger.info(
                    f"Requested keys via client.request_room_key for event {getattr(event, 'event_id', '?')}"
                )
            except LocalProtocolError:
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
        Handle an incoming room invite: join the room if its ID is configured, otherwise log a warning.

        This callback checks the invited room's ID against the bot's configured room set and calls join_matrix_room when the room is recognized.

        Parameters:
            _event (InviteEvent): The invite event object (unused by this handler).
        """
        if room.room_id in self._room_id_set:
            logger.info(f"Received invite for configured room: {room.room_id}")
            await self.join_matrix_room(room.room_id)
        else:
            logger.warning(f"Received invite for non-configured room: {room.room_id}")

    async def send_reaction(self, room_id, event_id, emoji):
        """
        Send an m.reaction (emoji annotation) to a Matrix event in a room.

        This asynchronously sends an "m.reaction" relation referencing event_id with the given emoji.
        Network- or Matrix-related failures are caught and logged; the method does not raise on such errors.

        Parameters:
            room_id (str): Matrix room ID or alias where the reaction will be sent.
            event_id (str): The Matrix event ID being reacted to.
            emoji (str): The emoji (reaction key) to send.
        """
        content = {
            "m.relates_to": {
                "rel_type": "m.annotation",
                "event_id": event_id,
                "key": emoji,
            }
        }
        try:
            response = await self.client.room_send(
                room_id,
                "m.reaction",
                content,
                ignore_unverified_devices=True,
            )
            if is_error_response(response):
                logger.warning(f"Failed to send reaction: {response}")
        except aiohttp.ClientError as e:
            logger.warning(f"Failed to send reaction: {e}", exc_info=True)
        except Exception:
            logger.exception("Unexpected error sending reaction")

    async def _handle_failed_send(self, room_id: str, send_error: object) -> None:
        """Report a failed Matrix send without attempting an impossible notice."""
        kind = classify_send_failure(send_error)
        if kind == "forbidden":
            logger.error(
                f"Not posting delivery-failure notice to forbidden room {room_id}"
            )
            return
        await self._send_error_message(room_id, send_failure_notice(kind))

    async def _send_error_message(self, room_id: str, message: str):
        """
        Send an error message to a Matrix room as an HTML-formatted `m.text` event.

        The provided plain-text `message` will be HTML-escaped and sent in the event's
        `formatted_body`. Failures are caught and logged; this method does not raise.

        Parameters:
            room_id (str): Matrix room ID to send the message to.
            message (str): Plain-text error message to deliver.
        """
        content = {
            "msgtype": "m.text",
            "body": message,
            "format": "org.matrix.custom.html",
            "formatted_body": html.escape(message),
        }
        try:
            response = await self.client.room_send(
                room_id,
                "m.room.message",
                content,
                ignore_unverified_devices=True,
            )
            # The notice itself can be rejected (e.g. M_FORBIDDEN in the very
            # room that rejected the passage). Never claim delivery that did
            # not happen; the error is already logged by callers.
            if is_error_response(response):
                logger.error(f"Error notice to {room_id} was not delivered: {response}")
        except Exception:
            logger.exception(f"Failed to send error message to room {room_id}")

    async def on_room_message(self, room: MatrixRoom, event: RoomMessageText):
        """
        Handle incoming room message events, detect Bible verse references, and trigger scripture processing.

        Only processes messages that:
        - originate in configured rooms,
        - are not sent by the bot itself, and
        - were sent after the bot's recorded start time.

        The bot responds only when a message is a scripture reference.
        Delegates to detect_trigger() from the triggers module for strict
        whole-message scripture reference matching.

        Parameters are typed (MatrixRoom, RoomMessageText) and represent the source room and the received event.
        This handles both unencrypted messages and successfully decrypted messages from encrypted rooms.
        """
        logger.debug(
            f"Received RoomMessageText in room {room.room_id} from {event.sender}: "
            f"encrypted={room.encrypted}, decrypted={getattr(event, 'decrypted', False)}"
        )

        if (
            room.room_id in self._room_id_set
            and event.sender != self.client.user_id
            and event.server_timestamp > self.start_time
        ):
            match = detect_trigger(
                body=event.body,
                default_translation=self.default_translation,
            )

            if match:
                logger.info(
                    "Detected Bible reference (%s): %s (%s) in room %s",
                    match.source.value,
                    match.passage,
                    match.translation,
                    room.room_id,
                )
                await self.handle_scripture_command(
                    room.room_id, match.passage, match.translation, event
                )

    def _format_text_for_display(self, text: str) -> tuple[str, str]:
        """Format text according to this bot's poetry-preservation setting."""
        return format_text_for_display(
            text, preserve_poetry=self.preserve_poetry_formatting
        )

    def _split_text_into_chunks(self, text, max_length):
        """Split passage text according to the configured maximum length."""
        return split_text_into_chunks(text, max_length=max_length)

    def _trim_reference_for_suffix(self, reference, reserve_fallback_space=False):
        """Trim a reference to this bot's configured message-length budget."""
        return trim_reference_for_suffix(
            reference,
            max_message_length=self.max_message_length,
            reserve_fallback_space=reserve_fallback_space,
        )

    async def _send_message_parts(self, room_id, text_parts, reference):
        """
        Send multiple message parts to a Matrix room, appending the provided Bible reference and MESSAGE_SUFFIX only to the final part.

        Each text part is formatted for plain and HTML display via _format_text_for_display. If a reference is given, the last part is suffixed with " - {reference}{MESSAGE_SUFFIX}"; otherwise the last part ends with MESSAGE_SUFFIX. Sends messages using the bot's Matrix client. Because nio's room_send returns ErrorResponse objects rather than raising, each response is inspected: transient 429 (rate-limited) responses are retried with exponential backoff and jitter up to MAX_RATE_LIMIT_RETRIES; any other ErrorResponse or transport failure stops the send.

        Parameters:
            room_id (str): Target Matrix room ID.
            text_parts (list[str]): Ordered message fragments to send.
            reference (str | None): Bible reference to append to the final message, or None to omit.

        Returns:
            The first non-retriable nio ErrorResponse encountered, or None when every part was sent.

        Raises:
            MessageSendError: If the underlying transport fails (aiohttp.ClientError) or the client raises a nio protocol/transport error (e.g. LocalProtocolError when not logged in).
        """
        for i, text_part in enumerate(text_parts):
            # Format the text part
            formatted_text, html_text = self._format_text_for_display(text_part)

            # Only add reference and suffix to the last message
            if i == len(text_parts) - 1:
                plain_body, formatted_body = compose_final_chunk_bodies(
                    formatted_text, html_text, reference=reference
                )
            else:
                plain_body = formatted_text
                formatted_body = html_text

            content = {
                "msgtype": "m.text",
                "body": plain_body,
                "format": "org.matrix.custom.html",
                "formatted_body": formatted_body,
            }

            # Send with enhanced rate limit handling: inspect the returned
            # response (nio returns ErrorResponse instead of raising) and
            # retry only transient 429 rate-limit responses.
            retries_left = MAX_RATE_LIMIT_RETRIES
            attempt = 0
            while True:
                try:
                    response = await self.client.room_send(
                        room_id,
                        "m.room.message",
                        content,
                        ignore_unverified_devices=True,
                    )
                except (
                    aiohttp.ClientError,
                    LocalProtocolError,
                    RemoteProtocolError,
                    RemoteTransportError,
                ) as e:
                    raise MessageSendError(
                        f"Transport error sending message to {room_id}: {e}"
                    ) from e
                if response is None or not is_error_response(response):
                    break  # Success
                if retries_left > 0 and is_rate_limit_response(response):
                    delay = response_retry_delay_seconds(response, attempt=attempt)
                    logger.warning(
                        f"Rate limited; backing off for {delay:.1f}s "
                        f"(attempt {attempt + 1}/{MAX_RATE_LIMIT_RETRIES})"
                    )
                    await asyncio.sleep(delay)
                    retries_left -= 1
                    attempt += 1
                    continue
                return response

    async def handle_scripture_command(self, room_id, passage, translation, event):
        """
        Fetch a Bible passage and post it to a Matrix room, handling splitting, truncation, reactions, and user-facing errors.

        Retrieves `passage` (using `translation` or the bot's configured default), reacts to the triggering `event` with a confirmation emoji, and posts the passage text to `room_id`. If the passage text exceeds configured limits the method will attempt to split it into multiple messages when splitting is enabled and practical; otherwise it truncates the text and appends a reference suffix or falls back to a short placeholder. Network errors, missing API key (ESV), and "passage not found" conditions are reported to the room as user-facing messages; exceptions are handled internally and not propagated.

        Parameters:
            room_id (str): Matrix room ID where the response will be posted.
            passage (str): Canonical passage string (e.g., "John 3:16").
            translation (str|None): Translation code to request; when None the bot's configured default is used.
            event: The original Matrix event that triggered the command (used to send a reaction).
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

            # Defer formatting to _send_message_parts; keep only a trim here
            text = text.strip()

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
                    send_error = await self._send_message_parts(
                        room_id, text_chunks, trimmed_reference
                    )

                    if send_error is not None:
                        logger.error(
                            f"Failed to send split scripture to {room_id}: {send_error}"
                        )
                        await self._handle_failed_send(room_id, send_error)
                        return

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

            send_error = await self._send_message_parts(
                room_id, [message_text], trimmed_reference
            )

            if send_error is not None:
                logger.error(f"Failed to send scripture to {room_id}: {send_error}")
                await self._handle_failed_send(room_id, send_error)
                return

            if trimmed_reference:
                logger.info(f"Sent scripture: {trimmed_reference}")
            else:
                logger.info("Sent scripture response")

        except APIKeyMissing as e:
            logger.warning(f"Failed to retrieve passage: {passage} ({e})")
            # Send helpful message about missing API key
            api_key_error = f"ESV translation requires an API key. Please configure one in your config.yaml or use KJV instead. (Try: {passage} kjv)"
            await self._send_error_message(room_id, api_key_error)
        except MessageSendError as e:
            # The passage was fetched but delivery failed at the transport
            # level; report it as a delivery failure, not a lookup failure.
            logger.error(f"Transport failure delivering passage to {room_id}: {e}")
            await self._send_error_message(room_id, ERROR_SEND_OTHER)
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
async def main(config_path=DEFAULT_CONFIG_FILENAME, config=None):
    """
    Start and run the BibleBot: load configuration and environment, create and configure the Matrix client and BibleBot instance, register event handlers, perform startup checks, and run the bot's main sync loop until shutdown.

    If `config` is None, the YAML configuration at `config_path` is loaded and validated. If `config` is provided, it is used as-is; `config_path` is still consulted for environment- and key-resolution. The routine establishes authentication (modern credentials flow when available, otherwise a legacy access-token/homeserver/user flow), configures optional end-to-end encryption (E2EE) and key upload, wires API keys into the bot, registers Matrix event callbacks, runs a non-fatal startup update check, and starts the bot. On termination it attempts orderly cleanup of bot resources and the Matrix client.

    Parameters:
        config_path (str): Path used to load configuration when `config` is not provided and for environment/key resolution when `config` is provided.
        config (dict | None): Preloaded configuration dictionary; when present, configuration is not read from disk.

    Raises:
        RuntimeError: When configuration, credentials, or required legacy homeserver/user information are missing or invalid.
        asyncio.CancelledError: Re-raised if startup tasks are cancelled to preserve cancellation semantics.
    """
    # Print startup banner
    print_startup_banner()

    # Load config and environment variables (only if not already provided)
    if config is None:
        config = load_config(config_path)
        if not config:
            logger.error(f"Failed to load configuration from {config_path}")
            raise RuntimeError(f"Failed to load configuration from {config_path}")

    matrix_access_token, api_keys = load_environment(config, config_path)
    # Now config's ready — publish it to log_utils and wire up component loggers
    configure_logging(config)
    configure_component_loggers()
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

    # Perform update check on startup
    try:
        await perform_startup_update_check()
    except asyncio.CancelledError:
        raise
    except Exception:  # noqa: BLE001 - intentional guard to keep startup resilient
        logger.debug("Startup update check failed", exc_info=True)

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
            LocalProtocolError,
            RemoteProtocolError,
            RemoteTransportError,
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
            # Successfully decrypted messages are converted to RoomMessageText by nio.
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
