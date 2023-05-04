import asyncio
import re
import yaml
from nio import AsyncClient, RoomMessageText
import aiohttp

async def scripture_request(reference, api_key):
    url = f"https://api.scripture.api.bible/v1/bibles/de4e12af7f28f599-01/passages/{reference}"
    params = {
        "content-type": "html",
        "include-notes": "false",
        "include-titles": "true",
        "include-chapter-numbers": "false",
        "include-verse-numbers": "true",
        "include-verse-spans": "true",
        "use-org-id": "false",
    }
    headers = {
        "accept": "application/json",
        "api-key": api_key,
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params, headers=headers) as response:
            data = await response.json()
            return data["data"]["content"]

async def message_handler(room, event):
    if isinstance(event, RoomMessageText):
        if event.body.startswith("!scripture"):
            try:
                reference = event.body.split(" ", 1)[1]
                scripture_content = await scripture_request(reference, config["api_key"])
                await client.room_send(
                    room.room_id,
                    "m.room.message",
                    {
                        "msgtype": "m.text",
                        "body": scripture_content,
                    },
                )
            except Exception as e:
                print(f"Error: {e}")

async def main():
    global client
    client = AsyncClient(config["homeserver"], config["username"])
    await client.login(config["password"])
    client.add_event_callback(message_handler, RoomMessageText)

    await asyncio.sleep(30000)  # Run the bot for 30,000 seconds (about 8 hours)
    await client.close()

if __name__ == "__main__":
    with open("config.yaml", "r") as f:
        config = yaml.safe_load(f)
    asyncio.run(main())