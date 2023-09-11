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

# Get Bible text
def get_bible_text(passage, translation='kjv', api_key=None):
    if translation == 'esv':
        logging.info("Using ESV API")  # Debug log
        API_URL = 'https://api.esv.org/v3/passage/text/'
        params = {
            'q': passage,
            'include-headings': False,
            'include-footnotes': False,
            'include-verse-numbers': False,
            'include-short-copyright': False,
            'include-passage-references': False
        }
        headers = {'Authorization': f'Token {api_key}'}
        response = requests.get(API_URL, params=params, headers=headers)
        passages = response.json()['passages']
        reference = response.json()['canonical']
        return (passages[0].strip(), reference) if passages else ('Error: Passage not found', '')
    else:
        logging.info("Using Bible-API for KJV")  # Debug log
        api_url = f"https://bible-api.com/{passage}?translation={translation}"
        response = requests.get(api_url)
        if response.status_code == 200:
            data = response.json()
            return data['text'], data['reference']
        else:
            return None, None

class BibleBot:
    def __init__(self, config):
        self.config = config
        self.client = AsyncClient(config["matrix_homeserver"], config["matrix_user"])

    async def start(self):
        self.client.access_token = self.config["matrix_access_token"]
        self.start_time = int(time.time() * 1000)  # Store bot start time in milliseconds
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
            and event.server_timestamp > self.start_time
        ):
            search_patterns = [
                r"^!scripture\s+(\d?\s*?\w+)\s*([\d:]+[-]?\d*)\s*(esv|kjv)?",
                r"^(\d?\s*?\w+)\s*([\d:]+[-]?\d*)\s*(esv|kjv)?",
            ]



            passage = None
            translation = 'kjv'  # Default translation
            for pattern in search_patterns:
                match = re.match(pattern, event.body)
                if match:
                    book_name = match.group(1).strip()  # Extract book name (e.g., "John" or "1 John")
                    verse_reference = match.group(2).strip()  # Extract verse reference (e.g., "3:16")
                    passage = f"{book_name} {verse_reference}"
                    if match.group(3):  # Check if the translation (esv or kjv) is specified
                        translation = match.group(3).lower()
                    logging.info(f"Extracted passage: {passage}, Extracted translation: {translation}")
                    break

            if passage:
                await self.handle_scripture_command(room.room_id, passage, translation, event)




    async def handle_scripture_command(self, room_id, passage, translation, event): 
        logging.info(f"Handling scripture command with translation: {translation}")  
        text, reference = get_bible_text(passage, translation, self.config["api_bible_key"])
        
        # Check if text is None
        if not text:
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
            await self.send_reaction(room_id, event.event_id, "✅")
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
