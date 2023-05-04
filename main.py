import asyncio
from nio import AsyncClient, MatrixRoom, RoomMessageText
from datetime import datetime
import requests
import json
import yaml
import logging
import re

bot_start_time = datetime.now()

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Load configuration from config.yaml
with open("config.yaml", "r") as config_file:
    config = yaml.safe_load(config_file)

API_BIBLE_KEY = config['api_bible_key']
MATRIX_HOMESERVER = config['matrix_homeserver']
MATRIX_USER = config['matrix_user']
MATRIX_ACCESS_TOKEN = config['matrix_access_token']
MATRIX_ROOM_ID = config['matrix_room_id']
DEFAULT_TRANSLATION = config['default_translation']

async def fetch_scripture(translation, book, chapter, verse_start, verse_end=None):
    headers = {'api-key': API_BIBLE_KEY}
    if verse_end:
        verse_range = f'{verse_start}-{verse_end}'
    else:
        verse_range = verse_start
    response = requests.get(f'https://api.scripture.api.bible/v1/bibles/{translation}/passages/{book}.{chapter}.{verse_range}', headers=headers)

    if response.status_code == 200:
        data = json.loads(response.text)
        return data['content']
    else:
        return None

async def main():
    client = AsyncClient(MATRIX_HOMESERVER, MATRIX_USER)
    client.access_token = MATRIX_ACCESS_TOKEN

    async def on_text(room, event):
        if isinstance(event, RoomMessageText):
            # Check if the event timestamp is greater than the bot's start time
            event_time = datetime.fromtimestamp(event.server_timestamp / 1000)
            if event_time > bot_start_time:
                logging.info(f"Received message: {event.body}")
                if event.body.startswith('!bible set-default'):
                    _, _, new_translation = event.body.split()
                    config['default_translation'] = new_translation
                    with open("config.yaml", "w") as config_file:
                        yaml.safe_dump(config, config_file)
                    await client.room_send(
                        room_id=room.room_id,
                        message_type='m.room.message',
                        content={
                            'msgtype': 'm.text',
                            'body': f'Default translation set to: {new_translation}'
                        }
                    )
                elif event.body.startswith('!scripture'):
                    _, reference = event.body.split(maxsplit=1)
                    translation = config['default_translation']
                    # Parse the reference and call fetch_scripture with the correct parameters
                    match = re.match(r"(\d?\s?[A-Za-z]{1,}\s?[A-Za-z]{0,})\s*(\d+):(\d+)-?(\d+)?", reference)
                    if match:
                        book, chapter, verse_start, verse_end = match.groups()
                        logging.info(f'Parsed reference: {book} {chapter}:{verse_start}-{verse_end if verse_end else ""}')
                        logging.info(f'Translation: {translation}')
                        scripture = await fetch_scripture(translation, book, chapter, verse_start, verse_end)
                        if scripture:
                            await client.room_send(
                                room_id=room.room_id,
                                message_type='m.room.message',
                                content={
                                    'msgtype': 'm.text',
                                    'body': scripture
                                }
                            )
                        else:
                            await client.room_send(
                                room_id=room.room_id,
                                message_type='m.room.message',
                                content={
                                    'msgtype': 'm.text',
                                    'body': 'Error fetching scripture. Please check the provided reference and translation.'
                                }
                            )
                    else:
                        await client.room_send(
                            room_id=room.room_id,
                            message_type='m.room.message',
                            content={
                                'msgtype': 'm.text',
                                'body': 'Invalid reference format. Please use the format: !scripture Book Chapter:Verse-EndVerse'
                            }
                        )
                else:
                    logging.info("Unknown command")

    client.add_event_callback(on_text, RoomMessageText)  # Fix the indentation here

    try:
        logging.info("Starting sync...")
        await client.sync_forever(timeout=30000)
    finally:
        logging.info("Closing client...")
        await client.close()

if __name__ == '__main__':
    asyncio.run(main())