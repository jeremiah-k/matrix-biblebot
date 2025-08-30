import logging
import os
import re
import time
from collections import OrderedDict
from time import monotonic

import aiohttp
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

from .auth import Credentials, get_store_dir, load_credentials

# Configure logging
logger = logging.getLogger("BibleBot")


# Constants and defaults
DEFAULT_TRANSLATION = "kjv"
ESV_API_URL = "https://api.esv.org/v3/passage/text/"
KJV_API_URL_TEMPLATE = "https://bible-api.com/{passage}?translation=kjv"
REFERENCE_PATTERNS = [r"^([\w\s]+?)(\d+[:]\d+[-]?\d*)\s*(kjv|esv)?$"]
SYNC_TIMEOUT_MS = 30000
REACTION_OK = "✅"
MESSAGE_SUFFIX = " 🕊️✝️"
E2EE_KEY_SHARING_DELAY_SECONDS = 3


# Load config
def load_config(config_file):
    """Load configuration from YAML file."""
    try:
        with open(config_file, "r") as f:
            config = yaml.safe_load(f) or {}
            # Basic validation
            required = ["matrix_homeserver", "matrix_user", "matrix_room_ids"]
            missing = [k for k in required if k not in config]
            if missing:
                logger.error(
                    f"Missing required config keys: {', '.join(missing)} in {config_file}"
                )
                return None
            if not isinstance(config.get("matrix_room_ids"), list):
                logger.error("'matrix_room_ids' must be a list in config")
                return None
            # Normalize homeserver URL (avoid trailing slash)
            if isinstance(config.get("matrix_homeserver"), str):
                config["matrix_homeserver"] = config["matrix_homeserver"].rstrip("/")
            logger.info(f"Loaded configuration from {config_file}")
            return config
    except Exception as e:
        logger.error(f"Error loading config from {config_file}: {e}")
        return None


# Load environment variables
def load_environment(config_path):
    """
    Load environment variables from .env file.
    First tries to load from the same directory as the config file,
    then falls back to the current directory.
    """
    # Try to load .env from the same directory as the config file
    config_dir = os.path.dirname(config_path)
    env_path = os.path.join(config_dir, ".env")

    if os.path.exists(env_path):
        load_dotenv(env_path)
        logger.info(f"Loaded environment variables from {env_path}")
    else:
        # Fall back to default .env in current directory if present
        cwd_env = os.path.join(os.getcwd(), ".env")
        if os.path.exists(cwd_env):
            load_dotenv(cwd_env)
            logger.info(f"Loaded environment variables from {cwd_env}")
        else:
            # Still call load_dotenv to pick up any env already set or parent dirs
            load_dotenv()
            logger.debug("No .env file found; relying on process environment")

    # Get access token and API keys
    matrix_access_token = os.getenv("MATRIX_ACCESS_TOKEN")
    if not matrix_access_token:
        logger.warning(
            "MATRIX_ACCESS_TOKEN not found in environment variables; bot cannot start"
        )

    # Dictionary to hold API keys for different translations
    api_keys = {
        "esv": os.getenv("ESV_API_KEY"),
        # Add more translations here
    }

    # Log which API keys were found (without showing the actual keys)
    for translation, key in api_keys.items():
        if key:
            logger.info(f"Found API key for {translation.upper()} translation")
        else:
            logger.debug(f"No API key found for {translation.upper()} translation")

    return matrix_access_token, api_keys


# Set nio logging to WARNING level to suppress verbose messages by default.
logging.getLogger("nio").setLevel(logging.WARNING)


# Handles headers & parameters for API requests
async def make_api_request(url, headers=None, params=None):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, params=params) as response:
                if response.status == 200:
                    return await response.json()
                logger.warning(f"HTTP {response.status} fetching {url}")
                return None
    except aiohttp.ClientError as e:
        logger.error(f"Network error fetching {url}: {e}")
        return None


# Get Bible text
_PASSAGE_CACHE_MAX = 128
_PASSAGE_CACHE_TTL_SECS = 12 * 60 * 60  # 12 hours
_passage_cache: "OrderedDict[tuple[str, str], tuple[float, tuple[str, str]]]" = (
    OrderedDict()
)


def _cache_get(passage: str, translation: str):
    key = (passage.lower(), translation.lower())
    now = monotonic()
    if key in _passage_cache:
        ts, value = _passage_cache.pop(key)
        # Evict if stale
        if now - ts <= _PASSAGE_CACHE_TTL_SECS:
            _passage_cache[key] = (ts, value)  # reinsert to mark recent
            return value
    return None


def _cache_set(passage: str, translation: str, value: tuple[str, str]):
    key = (passage.lower(), translation.lower())
    _passage_cache[key] = (monotonic(), value)
    # enforce LRU max size
    while len(_passage_cache) > _PASSAGE_CACHE_MAX:
        _passage_cache.popitem(last=False)


async def get_bible_text(passage, translation=DEFAULT_TRANSLATION, api_keys=None):
    # Check cache first
    cached = _cache_get(passage, translation)
    if cached is not None:
        return cached
    api_key = None
    if api_keys:
        api_key = api_keys.get(translation)

    _text, _reference = None, None
    if translation == "esv":
        result = await get_esv_text(passage, api_key)
    else:  # Assuming KJV as the default
        result = await get_kjv_text(passage)
    if result is not None:
        _cache_set(passage, translation, result)
    return result


async def get_esv_text(passage, api_key):
    if api_key is None:
        logger.warning("ESV API key not found")
        return None
    API_URL = ESV_API_URL
    params = {
        "q": passage,
        "include-headings": "false",
        "include-footnotes": "false",
        "include-verse-numbers": "false",
        "include-short-copyright": "false",
        "include-passage-references": "false",
    }
    headers = {"Authorization": f"Token {api_key}"}
    response = await make_api_request(API_URL, headers, params)
    passages = response["passages"] if response else None
    reference = response["canonical"] if response else None
    return passages[0].strip(), (
        reference if passages else ("Error: Passage not found", "")
    )


async def get_kjv_text(passage):
    API_URL = KJV_API_URL_TEMPLATE.format(passage=passage)
    response = await make_api_request(API_URL)
    passages = [response["text"]] if response else None
    reference = response["reference"] if response else None
    return (
        (passages[0].strip(), reference)
        if passages
        else ("Error: Passage not found", "")
    )


class BibleBot:
    def __init__(self, config):
        self.config = config
        self.client = AsyncClient(config["matrix_homeserver"], config["matrix_user"])
        self.api_keys = {}  # Will be set in main()

    async def resolve_aliases(self):
        """
        Allow room IDs or aliases in config; always resolve to room IDs for internal use.
        This method updates the config["matrix_room_ids"] list with resolved room IDs.
        """
        resolved_ids = []
        for entry in self.config["matrix_room_ids"]:
            if entry.startswith("#"):
                try:
                    resp = await self.client.room_resolve_alias(entry)
                    if hasattr(resp, "room_id"):
                        resolved_ids.append(resp.room_id)
                        logger.info(f"Resolved alias {entry} to room ID {resp.room_id}")
                except RoomResolveAliasError:
                    logger.warning(f"Could not resolve alias: {entry}")
            else:
                resolved_ids.append(entry)
        self.config["matrix_room_ids"] = list(set(resolved_ids))

    async def join_matrix_room(self, room_id_or_alias):
        """
        Join a Matrix room by its ID or alias.
        This method handles both room IDs and aliases, resolving aliases to IDs as needed.
        """
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
            if room_id not in self.client.rooms:
                response = await self.client.join(room_id)
                if response and hasattr(response, "room_id"):
                    logger.info(f"Joined room '{room_id_or_alias}' successfully")
                else:
                    logger.error(
                        f"Failed to join room '{room_id_or_alias}': {response.message if hasattr(response, 'message') else 'Unknown error'}"
                    )
            else:
                logger.debug(f"Bot is already in room '{room_id_or_alias}'")
        except Exception as e:
            logger.error(f"Error joining room '{room_id_or_alias}': {e}")

    async def ensure_joined_rooms(self):
        """
        On startup, join all rooms in config if not already joined.
        Uses the join_matrix_room method for each room.
        """
        for room_id in self.config["matrix_room_ids"]:
            await self.join_matrix_room(room_id)

    async def start(self):
        """Start the bot and begin processing events."""
        self.start_time = int(
            time.time() * 1000
        )  # Store bot start time in milliseconds
        logger.info("Initializing BibleBot...")
        await self.resolve_aliases()  # Support for aliases in config
        await self.ensure_joined_rooms()  # Ensure bot is in all configured rooms
        logger.info("Starting bot event processing loop...")
        await self.client.sync_forever(timeout=SYNC_TIMEOUT_MS)  # Sync every 30 seconds

    async def on_decryption_failure(self, room: MatrixRoom, event: MegolmEvent) -> None:
        """When decryption fails, request the keys and log."""
        logger.error(
            f"Failed to decrypt event '{getattr(event, 'event_id', '?')}' in room '{room.room_id}'. Requesting keys..."
        )
        try:
            event.room_id = room.room_id
            request = event.as_key_request(
                self.client.user_id, getattr(self.client, "device_id", None)
            )
            await self.client.to_device(request)
            logger.info("Requested keys for undecryptable event")
        except Exception as e:
            logger.warning(f"Key request failed: {e}")

    async def on_invite(self, room: MatrixRoom, event: InviteEvent):
        """Handle room invites for the bot."""
        if room.room_id in self.config["matrix_room_ids"]:
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
        await self.client.room_send(
            room_id,
            "m.reaction",
            content,
        )

    async def on_room_message(self, room: MatrixRoom, event: RoomMessageText):
        """
        Process incoming room messages and look for Bible verse references.
        Only processes messages in configured rooms, from other users, and after bot start time.
        """
        if (
            room.room_id in self.config["matrix_room_ids"]
            and event.sender != self.client.user_id
            and event.server_timestamp > self.start_time
        ):
            # Bible verse reference pattern(s)
            search_patterns = REFERENCE_PATTERNS

            passage = None
            translation = DEFAULT_TRANSLATION  # Default translation is KJV
            for pattern in search_patterns:
                match = re.match(pattern, event.body, re.IGNORECASE)
                if match:
                    book_name = match.group(1).strip()
                    verse_reference = match.group(2).strip()
                    passage = f"{book_name} {verse_reference}"
                    if match.group(
                        3
                    ):  # Check if the translation (esv or kjv) is specified
                        translation = match.group(3).lower()
                    else:
                        translation = "kjv"  # Default to kjv if not specified
                    logger.info(
                        f"Detected Bible reference: {passage} ({translation.upper()})"
                    )
                    break

            if passage:
                await self.handle_scripture_command(
                    room.room_id, passage, translation, event
                )

    async def handle_scripture_command(self, room_id, passage, translation, event):
        """
        Handle a detected Bible verse reference by fetching and posting the text.
        Sends a reaction to the original message and posts the verse text.
        """
        logger.info(f"Fetching scripture passage: {passage} ({translation.upper()})")
        text, reference = await get_bible_text(passage, translation, self.api_keys)

        if text is None or reference is None:
            logger.warning(f"Failed to retrieve passage: {passage}")
            await self.client.room_send(
                room_id,
                "m.room.message",
                {
                    "msgtype": "m.text",
                    "body": "Error: Failed to retrieve the specified passage.",
                },
            )
            return

        if text.startswith("Error:"):
            logger.warning(f"Invalid passage format: {passage}")
            await self.client.room_send(
                room_id,
                "m.room.message",
                {
                    "msgtype": "m.text",
                    "body": "Error: Invalid passage format. Use [Book Chapter:Verse-range (optional)]",
                },
            )
        else:
            # Formatting text to ensure one space between words
            text = " ".join(text.replace("\n", " ").split())

            # Send a checkmark reaction to the original message
            await self.send_reaction(room_id, event.event_id, REACTION_OK)

            # Format and send the scripture message
            message = f"{text} - {reference}{MESSAGE_SUFFIX}"
            logger.info(f"Sending scripture: {reference}")
            await self.client.room_send(
                room_id,
                "m.room.message",
                {"msgtype": "m.text", "body": message},
            )


# Run bot
async def main(config_path="config.yaml"):
    """
    Main entry point for the bot.
    Loads configuration, sets up the bot, and starts processing events.
    """
    # Load config and environment variables
    config = load_config(config_path)
    if not config:
        logger.error(f"Failed to load configuration from {config_path}")
        return

    matrix_access_token, api_keys = load_environment(config_path)
    creds = load_credentials()

    # Determine E2EE configuration from config
    matrix_section = (
        config.get("matrix", {}) if isinstance(config.get("matrix"), dict) else {}
    )
    e2ee_cfg = matrix_section.get("e2ee") or matrix_section.get("encryption") or {}
    e2ee_enabled = bool(e2ee_cfg.get("enabled", False))

    # Create AsyncClient with optional E2EE store
    client_config = AsyncClientConfig(
        store_sync_tokens=True, encryption_enabled=e2ee_enabled
    )

    logger.info("Creating BibleBot instance")
    bot = BibleBot(config)
    bot.client = AsyncClient(
        config["matrix_homeserver"],
        config["matrix_user"],
        store_path=str(get_store_dir()) if e2ee_enabled else None,
        config=client_config,
    )
    bot.api_keys = api_keys

    if creds:
        logger.info("Using saved credentials.json for Matrix session")
        bot.client.restore_login(
            user_id=creds.user_id,
            device_id=creds.device_id,
            access_token=creds.access_token,
        )
    else:
        if not matrix_access_token:
            logger.error("No credentials.json and no MATRIX_ACCESS_TOKEN found.")
            logger.error(
                "Run 'biblebot --auth-login' or set MATRIX_ACCESS_TOKEN in .env"
            )
            return
        bot.client.access_token = matrix_access_token
        try:
            bot.client.user_id = config.get("matrix_user", bot.client.user_id)
        except Exception:
            pass

    # If E2EE is enabled, ensure keys are uploaded
    if e2ee_enabled:
        try:
            if bot.client.should_upload_keys:
                logger.info("Uploading encryption keys...")
                await bot.client.keys_upload()
                logger.info("Encryption keys uploaded")
        except Exception as e:
            logger.warning(f"Failed to upload E2EE keys: {e}")

    # Register event handlers
    logger.debug("Registering event handlers")
    bot.client.add_event_callback(bot.on_invite, InviteEvent)
    bot.client.add_event_callback(bot.on_room_message, RoomMessageText)
    # Register decryption failure handler for encrypted rooms
    try:
        bot.client.add_event_callback(bot.on_decryption_failure, MegolmEvent)
    except Exception:
        pass

    # Start the bot
    await bot.start()


async def on_decryption_failure(room: MatrixRoom, event: MegolmEvent) -> None:
    pass  # replaced by BibleBot.on_decryption_failure bound method
