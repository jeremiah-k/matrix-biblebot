import logging
import os
import re
import time

import aiohttp
import yaml
from dotenv import load_dotenv
from nio import (
    AsyncClient,
    InviteEvent,
    MatrixRoom,
    RoomMessageText,
    RoomResolveAliasError,
)

# Configure logging
logger = logging.getLogger("BibleBot")


# Load config
def load_config(config_file):
    """Load configuration from YAML file."""
    try:
        with open(config_file, "r") as f:
            config = yaml.safe_load(f)
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
        # Fall back to default .env in current directory
        load_dotenv()
        logger.info("Loaded environment variables from current directory")

    # Get access token and API keys
    matrix_access_token = os.getenv("MATRIX_ACCESS_TOKEN")
    if not matrix_access_token:
        logger.warning("MATRIX_ACCESS_TOKEN not found in environment variables")

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


# Set up default logging configuration
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)


# Handles headers & parameters for API requests
async def make_api_request(url, headers=None, params=None):
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers, params=params) as response:
            if response.status == 200:
                return await response.json()
            return None


# Get Bible text
async def get_bible_text(passage, translation="kjv", api_keys=None):
    api_key = None
    if api_keys:
        api_key = api_keys.get(translation)

    text, reference = None, None
    if translation == "esv":
        return await get_esv_text(passage, api_key)
    else:  # Assuming KJV as the default
        return await get_kjv_text(passage)
    return text, reference


async def get_esv_text(passage, api_key):
    if api_key is None:
        logging.warning("ESV API key not found")
        return None
    API_URL = "https://api.esv.org/v3/passage/text/"
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
    API_URL = f"https://bible-api.com/{passage}?translation=kjv"
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
        await self.client.sync_forever(timeout=30000)  # Sync every 30 seconds

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
            # Bible verse reference pattern
            search_patterns = [
                r"^([\w\s]+?)(\d+[:]\d+[-]?\d*)\s*(kjv|esv)?$",
            ]

            passage = None
            translation = "kjv"  # Default translation is KJV
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
            await self.send_reaction(room_id, event.event_id, "✅")

            # Format and send the scripture message
            message = f"{text} - {reference} 🕊️✝️"
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

    if not matrix_access_token:
        logger.error("MATRIX_ACCESS_TOKEN not found in environment variables")
        logger.error("Please set MATRIX_ACCESS_TOKEN in your .env file")
        return

    # Create bot instance
    logger.info("Creating BibleBot instance")
    bot = BibleBot(config)
    bot.client.access_token = matrix_access_token
    bot.api_keys = api_keys

    # Register event handlers
    logger.debug("Registering event handlers")
    bot.client.add_event_callback(bot.on_invite, InviteEvent)
    bot.client.add_event_callback(bot.on_room_message, RoomMessageText)

    # Start the bot
    await bot.start()
