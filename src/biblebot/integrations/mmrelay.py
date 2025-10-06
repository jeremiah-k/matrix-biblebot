"""Meshtastic Matrix Relay integration for BibleBot."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp

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

try:  # pragma: no cover - optional dependency
    from mmrelay.plugins.base_plugin import BasePlugin as _BasePlugin
except ImportError:  # pragma: no cover - used when not running inside mmrelay

    class _BasePlugin:  # type: ignore[too-many-ancestors]
        """Fallback base class that raises helpful guidance when misused."""

        def __init__(
            self, *args: Any, **kwargs: Any
        ) -> None:  # noqa: D401 - simple guard
            raise RuntimeError(
                "mmrelay.plugins.base_plugin is not available. "
                "Install meshtastic-matrix-relay and run BibleBot via its plugin system "
                "to use the mmrelay integration."
            )

    BasePlugin = _BasePlugin
else:  # pragma: no cover - exercised within mmrelay runtime
    BasePlugin = _BasePlugin

__all__ = ["Plugin"]


class Plugin(BasePlugin):
    """Community plugin entry point wiring BibleBot into mmrelay."""

    plugin_name = "biblebot"

    def __init__(self) -> None:  # pragma: no cover - thin wrapper
        super().__init__()
        self.logger = logging.getLogger(f"mmrelay.plugin.{self.plugin_name}")
        self.http_session: aiohttp.ClientSession | None = None
        self.api_keys: dict[str, str] = {}
        self.default_translation = DEFAULT_TRANSLATION
        self.detect_references_anywhere = False

    async def start(self) -> None:
        """Initialise plugin state and HTTP client."""

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

    async def stop(self) -> None:
        """Release HTTP resources on shutdown."""

        self.logger.info("Stopping BibleBot plugin")
        if self.http_session:
            await self.http_session.close()
            self.http_session = None

    async def handle_meshtastic_message(
        self,
        packet: dict[str, Any],
        formatted_message: str,
        longname: str,
        meshnet_name: str,
    ) -> bool:
        """Detect references in Meshtastic messages and respond."""

        if "decoded" not in packet or "text" not in packet["decoded"]:
            return False

        message = packet["decoded"]["text"].strip()
        passage, translation = self._find_passage(message)
        if not passage:
            return False

        self.logger.info(
            "Detected Bible reference from Meshtastic: %s (%s)",
            passage,
            translation,
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
        except APIKeyMissing as exc:
            self.logger.warning("Error fetching passage: %s", exc)
            self._send_mesh_message("ESV API key missing.", packet, is_dm)
            return True
        except PassageNotFound:
            self.logger.warning("Passage not found: %s", passage)
            self._send_mesh_message(ERROR_PASSAGE_NOT_FOUND, packet, is_dm)
            return True
        except Exception:  # noqa: BLE001 - log unexpected runtime issues
            self.logger.exception("Unexpected error handling Meshtastic message")
            return False

        response = f"{text} - {reference}" if reference else text
        max_len = 220
        if len(response) > max_len:
            response = response[: max_len - 3] + "..."

        self._send_mesh_message(response, packet, is_dm)
        return True

    async def handle_room_message(self, room, event, full_message: str) -> bool:  # type: ignore[override]
        """Detect references in Matrix rooms bridged by mmrelay."""

        if event.sender == self.matrix_client.user_id:
            return False

        message = event.body.strip()
        passage, translation = self._find_passage(message)
        if not passage:
            return False

        self.logger.info(
            "Detected Bible reference from Matrix: %s (%s) in room %s",
            passage,
            translation,
            room.room_id,
        )

        try:
            text, reference = await get_bible_text(
                passage,
                translation,
                api_keys=self.api_keys,
                default_translation=self.default_translation,
                session=self.http_session,
            )
        except APIKeyMissing:
            await self.send_matrix_message(
                room.room_id, "ESV translation requires an API key."
            )
            return True
        except PassageNotFound:
            await self.send_matrix_message(room.room_id, ERROR_PASSAGE_NOT_FOUND)
            return True
        except Exception:  # noqa: BLE001
            self.logger.exception("Unexpected error handling Matrix message")
            await self.send_matrix_message(
                room.room_id, "An error occurred while fetching the scripture."
            )
            return True

        response = f"{text} - {reference}" if reference else text
        await self.send_matrix_message(room.room_id, response)
        return True

    def _find_passage(self, message: str) -> tuple[str | None, str | None]:
        """Return (passage, translation) when a reference is detected."""

        patterns = (
            PARTIAL_REFERENCE_PATTERNS
            if self.detect_references_anywhere
            else REFERENCE_PATTERNS
        )
        match_func = "search" if self.detect_references_anywhere else "fullmatch"

        for pattern in patterns:
            match = getattr(pattern, match_func)(message)
            if not match:
                continue

            raw_book_name = match.group("book").strip()
            if not raw_book_name:
                continue

            book_name = validate_and_normalize_book_name(raw_book_name)
            if not book_name:
                continue

            verse_reference = match.group("ref").strip()
            passage = f"{book_name} {verse_reference}" if verse_reference else book_name

            trans_group = match.groupdict().get("translation")
            translation = (
                trans_group.lower().strip() if trans_group else self.default_translation
            )
            return passage, translation

        return None, None

    def _send_mesh_message(
        self, text: str, packet: dict[str, Any], is_dm: bool
    ) -> None:
        """Send a message via mmrelay channel or direct message."""

        if is_dm:
            self.send_message(text=text, destination_id=packet.get("fromId"))
        else:
            self.send_message(text=text, channel=packet.get("channel", 0))
