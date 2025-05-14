import logging
import os
import re
import time

import aiohttp
import yaml
from dotenv import load_dotenv
from nio import AsyncClient, InviteEvent, MatrixRoom, RoomMessageText


# Load config
def load_config(config_file):
    with open(config_file, "r") as f:
        return yaml.safe_load(f)


# Load environment variables
def load_environment(config_path):
    # Try to load .env from the same directory as the config file
    config_dir = os.path.dirname(config_path)
    env_path = os.path.join(config_dir, ".env")

    if os.path.exists(env_path):
        load_dotenv(env_path)
        logging.info(f"Loaded environment variables from {env_path}")
    else:
        # Fall back to default .env in current directory
        load_dotenv()
        logging.info("Loaded environment variables from current directory")

    # Get access token and API keys
    matrix_access_token = os.getenv("MATRIX_ACCESS_TOKEN")
    if not matrix_access_token:
        logging.warning("MATRIX_ACCESS_TOKEN not found in environment variables")

    # Dictionary to hold API keys for different translations
    api_keys = {
        "esv": os.getenv("ESV_API_KEY"),
        # Add more translations here
    }

    return matrix_access_token, api_keys


logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
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

    async def start(self):
        self.start_time = int(
            time.time() * 1000
        )  # Store bot start time in milliseconds
        logging.info("Starting bot...")
        await self.client.sync_forever(timeout=30000)  # Sync every 30 seconds

    async def on_invite(self, room: MatrixRoom, event: InviteEvent):
        if room.room_id in self.config["matrix_room_ids"]:
            logging.info(f"Joined room: {room.room_id}")
            await self.client.join(room.room_id)
        else:
            logging.warning(f"Unexpected room invite: {room.room_id}")

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
        if (
            room.room_id in self.config["matrix_room_ids"]
            and event.sender != self.client.user_id
            and event.server_timestamp > self.start_time
        ):
            # Finally the right regex I think!!
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
                    logging.info(
                        f"Extracted passage: {passage}, Extracted translation: {translation}"
                    )
                    break

            if passage:
                await self.handle_scripture_command(
                    room.room_id, passage, translation, event
                )

    async def handle_scripture_command(self, room_id, passage, translation, event):
        logging.info(f"Handling scripture command with translation: {translation}")
        text, reference = await get_bible_text(passage, translation, self.api_keys)
        if text is None or reference is None:
            logging.warning(f"Failed to retrieve passage: {passage}")
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
            logging.warning(f"Invalid passage format: {passage}")
            await self.client.room_send(
                room_id,
                "m.room.message",
                {
                    "msgtype": "m.text",
                    "body": "Error: Invalid passage format. Use [Book Chapter:Verse-range (optional)]",
                },
            )
        else:
            # Formatting KJV text to ensure one space between words
            text = " ".join(text.replace("\n", " ").split())

            logging.info(f"Scripture search: {passage}")
            await self.send_reaction(room_id, event.event_id, "✅")
            message = f"{text} - {reference} 🕊️✝️"
            await self.client.room_send(
                room_id,
                "m.room.message",
                {"msgtype": "m.text", "body": message},
            )


# Run bot
async def main(config_path="config.yaml"):
    # Load config and environment variables
    config = load_config(config_path)
    matrix_access_token, api_keys = load_environment(config_path)

    if not matrix_access_token:
        logging.error("MATRIX_ACCESS_TOKEN not found in environment variables")
        logging.error("Please set MATRIX_ACCESS_TOKEN in your .env file")
        return

    # Create bot instance
    bot = BibleBot(config)
    bot.client.access_token = matrix_access_token
    bot.api_keys = api_keys

    # Register event handlers
    bot.client.add_event_callback(bot.on_invite, InviteEvent)
    bot.client.add_event_callback(bot.on_room_message, RoomMessageText)

    # Start the bot
    await bot.start()
