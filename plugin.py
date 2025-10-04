"""
BibleBot as a meshtastic-matrix-relay Plugin.

This file provides the plugin interface for BibleBot to be used with
meshtastic-matrix-relay. It allows BibleBot to respond to Bible verse
requests from both Matrix and Meshtastic networks.

To use this plugin, the BibleBot package must be installed in the same
Python environment as mmrelay. The plugin can be configured in the mmrelay
config.yaml file.

Example community-plugins config:
community-plugins:
  biblebot:
    active: true
    repository: https://github.com/your-username/BibleBot.git
    branch: main
    config:
      api_keys:
        esv: "YOUR_ESV_API_KEY"
      default_translation: "kjv"
      detect_references_anywhere: true

This file is designed to be at the root of the BibleBot project repository
to be compatible with the mmrelay community plugin system.
"""

import asyncio
import logging
import os
import sys

import aiohttp

# Add the src directory to the Python path to allow for absolute imports
# when the plugin is loaded by mmrelay. This is necessary because mmrelay
# does not know about the src layout.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "src")))


try:
    from mmrelay.plugins.base_plugin import BasePlugin

    MMRELAY_AVAILABLE = True
except ImportError:
    MMRELAY_AVAILABLE = False

# Import the core biblebot logic
from biblebot.bot import (
    APIKeyMissing,
    PassageNotFound,
    get_bible_text,
    validate_and_normalize_book_name,
)
from biblebot.constants.bible import (
    DEFAULT_TRANSLATION,
    PARTIAL_REFERENCE_PATTERNS,
    REFERENCE_PATTERNS,
    TRANSLATION_ESV,
)
from biblebot.constants.messages import ERROR_PASSAGE_NOT_FOUND

if MMRELAY_AVAILABLE:

    class Plugin(BasePlugin):
        plugin_name = "biblebot"

        def __init__(self):
            super().__init__()
            self.logger = logging.getLogger(f"mmrelay.plugin.{self.plugin_name}")
            self.http_session = None
            self.api_keys = {}
            self.default_translation = DEFAULT_TRANSLATION
            self.detect_references_anywhere = False

        async def start(self):
            self.logger.info("Starting BibleBot plugin")
            self.api_keys = self.plugin_config.get("api_keys", {})
            if not self.api_keys.get(TRANSLATION_ESV):
                self.logger.warning("ESV API key not configured for biblebot plugin.")
            self.default_translation = self.plugin_config.get(
                "default_translation", DEFAULT_TRANSLATION
            )
            self.detect_references_anywhere = self.plugin_config.get(
                "detect_references_anywhere", False
            )
            self.http_session = aiohttp.ClientSession()

        async def stop(self):
            self.logger.info("Stopping BibleBot plugin")
            if self.http_session:
                await self.http_session.close()

        async def handle_meshtastic_message(
            self, packet, formatted_message, longname, meshnet_name
        ):
            if "decoded" in packet and "text" in packet["decoded"]:
                message = packet["decoded"]["text"].strip()
                passage, translation = self._find_passage(message)

                if passage:
                    self.logger.info(
                        f"Detected Bible reference from Meshtastic: {passage} ({translation})"
                    )

                    is_dm = self.is_direct_message(packet)
                    if not self.is_channel_enabled(
                        packet.get("channel", 0), is_direct_message=is_dm
                    ):
                        return False

                    await asyncio.sleep(self.get_response_delay())

                    try:
                        text, reference = await get_bible_text(
                            passage,
                            translation,
                            api_keys=self.api_keys,
                            default_translation=self.default_translation,
                            session=self.http_session,
                        )

                        response = f"{text} - {reference}" if reference else text

                        # Truncate if too long for mesh
                        max_len = 220
                        if len(response) > max_len:
                            response = response[: max_len - 3] + "..."

                        if is_dm:
                            self.send_message(
                                text=response, destination_id=packet.get("fromId")
                            )
                        else:
                            self.send_message(
                                text=response, channel=packet.get("channel", 0)
                            )

                        return True

                    except APIKeyMissing as e:
                        self.logger.warning(f"Error fetching passage: {e}")
                        error_msg = "ESV API key missing."
                        if is_dm:
                            self.send_message(
                                text=error_msg, destination_id=packet.get("fromId")
                            )
                        else:
                            self.send_message(
                                text=error_msg, channel=packet.get("channel", 0)
                            )
                        return True
                    except PassageNotFound:
                        self.logger.warning(f"Passage not found: {passage}")
                        if is_dm:
                            self.send_message(
                                text=ERROR_PASSAGE_NOT_FOUND,
                                destination_id=packet.get("fromId"),
                            )
                        else:
                            self.send_message(
                                text=ERROR_PASSAGE_NOT_FOUND,
                                channel=packet.get("channel", 0),
                            )
                        return True
                    except Exception:
                        self.logger.exception(
                            "Unexpected error handling meshtastic message"
                        )
                        return False

            return False

        async def handle_room_message(self, room, event, full_message):
            if event.sender == self.matrix_client.user_id:
                return False

            message = event.body.strip()
            passage, translation = self._find_passage(message)

            if passage:
                self.logger.info(
                    f"Detected Bible reference from Matrix: {passage} ({translation}) in room {room.room_id}"
                )

                try:
                    text, reference = await get_bible_text(
                        passage,
                        translation,
                        api_keys=self.api_keys,
                        default_translation=self.default_translation,
                        session=self.http_session,
                    )

                    response = f"{text} - {reference}" if reference else text
                    await self.send_matrix_message(room.room_id, response)
                    return True

                except APIKeyMissing:
                    await self.send_matrix_message(
                        room.room_id, "ESV translation requires an API key."
                    )
                    return True
                except PassageNotFound:
                    await self.send_matrix_message(
                        room.room_id, ERROR_PASSAGE_NOT_FOUND
                    )
                    return True
                except Exception:
                    self.logger.exception("Unexpected error handling matrix message")
                    await self.send_matrix_message(
                        room.room_id, "An error occurred while fetching the scripture."
                    )
                    return True

            return False

        def _find_passage(self, message):
            patterns = (
                PARTIAL_REFERENCE_PATTERNS
                if self.detect_references_anywhere
                else REFERENCE_PATTERNS
            )
            match_func = (
                "search" if self.detect_references_anywhere else "fullmatch"
            )

            for pattern in patterns:
                match = getattr(pattern, match_func)(message)
                if match:
                    raw_book_name = match.group("book").strip()
                    if not raw_book_name:
                        continue

                    book_name = validate_and_normalize_book_name(raw_book_name)
                    if not book_name:
                        continue

                    verse_reference = match.group("ref").strip()
                    passage = f"{book_name} {verse_reference}"

                    trans_group = match.groupdict().get("translation")
                    translation = (
                        trans_group.lower().strip()
                        if trans_group
                        else self.default_translation
                    )
                    return passage, translation

            return None, None