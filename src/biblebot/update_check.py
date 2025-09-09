"""Update check functionality for BibleBot."""

import asyncio
import logging
from typing import Optional, Tuple

import aiohttp
from packaging import version

from biblebot import __version__
from biblebot.constants.app import LOGGER_NAME
from biblebot.constants.update import (
    RELEASES_PAGE_URL,
    RELEASES_URL,
    UPDATE_CHECK_TIMEOUT,
    UPDATE_CHECK_USER_AGENT,
)

logger = logging.getLogger(LOGGER_NAME)


async def get_latest_release_version() -> Optional[str]:
    """
    Asynchronously fetch the latest GitHub release tag for BibleBot.

    Queries the configured RELEASES_URL (GitHub releases API) and returns the release's `tag_name`
    with a leading "v" stripped (e.g., "v1.2.3" -> "1.2.3"). Returns None if the tag is missing
    or the request/response cannot be obtained or parsed.
    """
    try:
        timeout = aiohttp.ClientTimeout(total=UPDATE_CHECK_TIMEOUT)
        headers = {
            "User-Agent": UPDATE_CHECK_USER_AGENT,
            "Accept": "application/vnd.github.v3+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

        async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
            async with session.get(RELEASES_URL) as response:
                response.raise_for_status()
                data = await response.json()
                if isinstance(data, list):
                    data = data[0] if data else {}
                tag = data.get("tag_name")
                if not tag:
                    logger.debug("Latest release from GitHub missing tag_name")
                    return None
                tag_name = str(tag).strip().lstrip("vV")
                logger.debug(f"Latest release from GitHub: {tag_name}")
                return tag_name

    except asyncio.TimeoutError:
        logger.debug("Update check timed out")
        return None
    except aiohttp.ClientResponseError as e:
        logger.debug(f"GitHub API error {e.status}: {e}")
        return None
    except aiohttp.ClientError as e:
        logger.debug(f"Network error during update check: {e}")
        return None
    except (ValueError, KeyError, TypeError) as e:
        logger.debug(f"Unexpected data while checking updates: {e}")
        return None


def compare_versions(current: str, latest: str) -> bool:
    """
    Return True if `latest` represents a newer version than `current`.

    Both inputs are parsed with `packaging.version.parse` (PEP 440–compatible). If either value cannot be parsed as a version, the function returns False.
    """
    try:
        current_ver = version.parse(str(current))
        latest_ver = version.parse(str(latest))
    except (TypeError, ValueError, version.InvalidVersion) as e:
        logger.debug(f"Error comparing versions '{current}' and '{latest}': {e}")
        return False
    else:
        return latest_ver > current_ver


async def check_for_updates() -> Tuple[bool, Optional[str]]:
    """
    Determine whether a newer BibleBot release is available.

    Fetches the latest release tag from the configured source and compares it to the running package version.

    Returns:
        Tuple[bool, Optional[str]]: A pair (update_available, latest_version) where `update_available` is True if a newer release exists, and `latest_version` is the latest release tag (without a leading "v") or None if the latest version could not be determined.
    """
    current_version = __version__
    logger.debug(f"Current version: {current_version}")

    latest_version = await get_latest_release_version()
    if latest_version is None:
        logger.debug("Could not determine latest version")
        return False, None

    update_available = compare_versions(current_version, latest_version)
    logger.debug(f"Update available: {update_available}")

    return update_available, latest_version


def print_startup_banner() -> None:
    """
    Log a startup banner containing the current BibleBot version.

    Intended to be called once at the very start of application startup.
    """
    logger.info(f"Starting BibleBot version {__version__}")


async def perform_startup_update_check() -> None:
    """
    Check for a newer release on startup and log a user-facing notification if one is available.

    This coroutine calls the update-check routine, and if a newer version is found logs an informational message with the latest version and releases page URL; otherwise it logs that the application is up to date. Intended to be awaited during application startup.
    """
    logger.debug("Performing startup update check...")

    update_available, latest_version = await check_for_updates()

    if update_available and latest_version:
        logger.info("🔄 A new version of BibleBot is available!")
        logger.info(f"   Latest version: {latest_version}")
        logger.info(f"   Visit: {RELEASES_PAGE_URL}")
    else:
        logger.debug("BibleBot is up to date")
