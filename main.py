import asyncio
from nio import AsyncClient, MatrixRoom, RoomMessageText
from datetime import datetime
from urllib.parse import quote
import requests
import json
import yaml
import logging
import re
import httpx
from unidecode import unidecode

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
TRANSLATIONS = config['translations']

def get_translation_id(search_query):
    search_query = unidecode(search_query.lower())
    for abbr, bible_id in TRANSLATIONS.items():
        if search_query in unidecode(abbr.lower()) or search_query in unidecode(TRANSLATIONS[abbr].lower()):
            return bible_id
    return None

async def fetch_scripture(translation_abbr, book, chapter, verse_start, verse_end=None):
    headers = {'api-key': API_BIBLE_KEY}
    if verse_end:
        verse_range = f'{verse_start}-{verse_end}'
    else:
        verse_range = verse_start
    # Create the passageId
    book_no_space = book.replace(' ', '')
    passage_id = f'{book_no_space}.{chapter}.{verse_range}'.replace(" ", "")

    # Get the Bible ID using the translation abbreviation
    translation_id = TRANSLATIONS[translation_abbr]
    params = (
        'content-type=html'
        '&include-notes=false'
        '&include-titles=true'
        '&include-chapter-numbers=false'
        '&include-verse-numbers=true'
        '&include-verse-spans=false'
        '&use-org-id=false'
    )
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f'https://api.scripture.api.bible/v1/bibles/{translation_id}/passages/{passage_id}?{params}',
            headers=headers
        )

        if response.status_code == 200:
            data = response.json()
            return data['content']
        else:
            logging.error(f"Error fetching scripture: {response.status_code} {response.text}")
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
                    parts = event.body.split(maxsplit=1)
                    if len(parts) == 2:
                        _, reference = parts
                        translation = config['default_translation']

                        # Check if the user provided a translation
                        if '|' in reference:
                            reference, provided_translation = reference.rsplit('|', 1)
                            provided_translation = provided_translation.strip()
                            translation_id = get_translation_id(provided_translation)
                            if translation_id:
                                translation = provided_translation
                            else:
                                await client.room_send(
                                    room_id=room.room_id,
                                    message_type='m.room.message',
                                    content={
                                        'msgtype': 'm.text',
                                        'body': f"Translation '{provided_translation}' not found. Using the default translation."
                                    }
                                )
                        # Parse the reference and call fetch_scripture with the correct parameters
                        match = re.match(r"(\d?\s?[A-Za-z]{1,}\s?[A-Za-z]{0,})\s*(\d+):(\d+)-?(\d+)?", reference)
                        if match:
                            book, chapter, verse_start, verse_end = match.groups()
                            book = book.strip()
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
                                    'body': 'Invalid reference format. Please use the format: !scripture Book Chapter:Verse-EndVerse | Translation'
                                }
                            )
                    else:
                        await client.room_send(
                            room_id=room.room_id,
                            message_type='m.room.message',
                            content={
                                'msgtype': 'm.text',
                                'body': 'Invalid command format. Please use the format: !scripture Book Chapter:Verse-EndVerse | Translation'
                            }
                        )

    client.add_event_callback(on_text, RoomMessageText)  # Fix the indentation here

    try:
        logging.info("Starting sync...")
        await client.sync_forever(timeout=30000)
    finally:
        logging.info("Closing client...")
        await client.close()

if __name__ == '__main__':
    asyncio.run(main())