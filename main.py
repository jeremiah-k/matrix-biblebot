import sys
import yaml
import re
from nio import AsyncClient, RoomMessageText, MatrixRoom, InviteEvent, RoomMemberEvent
import asyncio
import requests
import time

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

    return passages[0].strip() if passages else 'Error: Passage not found'

class BibleBot:
    def __init__(self, config):
        self.config = config
        self.client = AsyncClient(config["matrix_homeserver"], config["matrix_user"])

    async def start(self):
        self.client.access_token = self.config["matrix_access_token"]
        self.start_time = int(time.time() * 1000)  # Store bot start time in milliseconds
        await self.client.sync_forever(timeout=30000)  # Sync every 30 seconds

    async def on_invite(self, room_id: str, state: MatrixRoom):
        if room_id == self.config["matrix_room_id"]:
            await self.client.join(room_id)

    async def on_room_message(self, room: MatrixRoom, event: RoomMessageText):
        if (
            room.room_id == self.config["matrix_room_id"]
            and event.body.startswith("!scripture")
            and event.sender != self.client.user_id
            and event.server_timestamp > self.start_time  # Check if the event occurred after the bot started
        ):
            await self.handle_scripture_command(room.room_id, event.body)

    async def handle_scripture_command(self, room_id, command_text):
        search_pattern = r"!scripture\s+([\w\s]+[\d]+[:]\d+[-]?\d*)"
        match = re.match(search_pattern, command_text)

        if match:
            passage = match.group(1)
            text = get_esv_text(passage, self.config["api_bible_key"])
            await self.client.room_send(
                room_id,
                "m.room.message",
                {"msgtype": "m.text", "body": text},
            )
        else:
            await self.client.room_send(
                room_id,
                "m.room.message",
                {
                    "msgtype": "m.text",
                    "body": "Error: Invalid command format. Use !scripture [Book Chapter:Verse]",
                },
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