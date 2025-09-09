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
    Fetch the latest release version from GitHub.

    Returns:
        Optional[str]: The latest release version tag, or None if unable to fetch.
    """
    try:
        timeout = aiohttp.ClientTimeout(total=UPDATE_CHECK_TIMEOUT)
        headers = {
            "User-Agent": UPDATE_CHECK_USER_AGENT,
            "Accept": "application/vnd.github.v3+json",
        }

        async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
            async with session.get(RELEASES_URL) as response:
                response.raise_for_status()
                data = await response.json()
                tag = data.get("tag_name")
                if not tag:
                    logger.debug("Latest release from GitHub missing tag_name")
                    return None
                tag_name = str(tag).lstrip("v")
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
    Compare two version strings to determine if an update is available.

    Args:
        current (str): Current version string
        latest (str): Latest available version string

    Returns:
        bool: True if latest version is newer than current version
    """
    try:
        current_ver = version.parse(current)
        latest_ver = version.parse(latest)
    except (TypeError, ValueError, version.InvalidVersion) as e:
        logger.debug(f"Error comparing versions '{current}' and '{latest}': {e}")
        return False
    else:
        return latest_ver > current_ver


async def check_for_updates() -> Tuple[bool, Optional[str]]:
    """
    Check if a newer version of BibleBot is available.

    Returns:
        Tuple[bool, Optional[str]]: (update_available, latest_version)
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
    Print the startup banner with version information.

    This should be called once at the very beginning of startup.
    """
    logger.info(f"Starting BibleBot version {__version__}")


async def perform_startup_update_check() -> None:
    """
    Perform an update check on startup and log the result.

    This function is designed to be called during bot startup.
    Only shows update notification if current version is older than latest release.
    """
    logger.debug("Performing startup update check...")

    update_available, latest_version = await check_for_updates()

    if update_available and latest_version:
        logger.info("🔄 A new version of BibleBot is available!")
        logger.info(f"   Latest version: {latest_version}")
        logger.info(f"   Visit: {RELEASES_PAGE_URL}")
    else:
        logger.debug("BibleBot is up to date")
