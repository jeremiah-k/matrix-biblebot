import yaml
import re
from nio import AsyncClient, RoomMessageText, MatrixRoom, InviteEvent
import asyncio
import requests
import time
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


# Load config
def load_config(config_file):
    with open(config_file, "r") as f:
        return yaml.safe_load(f)


# Get ESV text
def get_esv_text(passage, api_key):
    API_URL = 'https://api.esv.org/v3/passage/text/'

    params = {
        'q': passage,
        'include-headings': False,
        'include-footnotes': False,
        'include-verse-numbers': False,
        'include-short-copyright': False,
        'include-passage-references': False
    }

    headers = {
        'Authorization': 'Token %s' % api_key
    }

    response = requests.get(API_URL, params=params, headers=headers)

    passages = response.json()['passages']
    reference = response.json()['canonical']

    return (passages[0].strip(), reference) if passages else ('Error: Passage not found', '')


class BibleBot:
    def __init__(self, config):
        self.config = config
        self.client = AsyncClient(config["matrix_homeserver"], config["matrix_user"])

    async def start(self):
        self.client.access_token = self.config["matrix_access_token"]
        self.start_time = int(time.time() * 1000)  # Store bot start time in milliseconds
        logging.info("Starting bot...")
        await self.client.sync_forever(timeout=30000)  # Sync every 30 seconds

    async def on_invite(self, room: MatrixInvitedRoom, event: InviteEvent):
        room_id = room.room_id
        if room_id in self.config["matrix_room_ids"]:
            logging.info(f"Joined room: {room_id}")
            await self.client.join(room_id)
        else:
            logging.warning(f"Unexpected room invite: {room_id}")
    
    async def send_reaction(self, room_id, event_id, emoji):
        content = {
            "m.relates_to": {
                "rel_type": "m.annotation",
                "event_id": event_id,
                "key": emoji
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
            and event.server_timestamp > self.start_time  # Check if the event occurred after the bot started
        ):
            search_patterns = [
                r"^!scripture\s+([\w\s]+[\d]+[:]\d+[-]?\d*)$",
                r"^([\w\s]+[\d]+[:]\d+[-]?\d*)$",
            ]

            passage = None
            for pattern in search_patterns:
                match = re.match(pattern, event.body)
                if match:
                    passage = match.group(1)
                    break

            if passage:
                await self.handle_scripture_command(room.room_id, passage, event)


    async def handle_scripture_command(self, room_id, passage, event):
        text, reference = get_esv_text(passage, self.config["api_bible_key"])
        if text.startswith('Error:'):
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
            logging.info(f"Scripture search: {passage}")

            # Send the green checkbox (✅) as a reaction to the requester's message
            await self.send_reaction(room_id, event.event_id, "✅")

            # Add the string of emojis (🕊️✝️ 📔) at the end of the reference
            message = f"{text} - {reference} 🕊️✝️"
            await self.client.room_send(
                room_id,
                "m.room.message",
                {"msgtype": "m.text", "body": message},
            )


# Run bot
async def main():
    config = load_config("config.yaml")
    bot = BibleBot(config)

    bot.client.add_event_callback(bot.on_invite, InviteEvent)
    bot.client.add_event_callback(bot.on_room_message, RoomMessageText)

    await bot.start()

if __name__ == "__main__":
    asyncio.run(main())
