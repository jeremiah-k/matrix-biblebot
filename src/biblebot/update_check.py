"""Update check functionality for BibleBot."""

import asyncio
import logging
from typing import Optional, Tuple

import aiohttp
from packaging import version

from . import __version__
from .constants import LOGGER_NAME

logger = logging.getLogger(LOGGER_NAME)

# GitHub API configuration
GITHUB_API_BASE = "https://api.github.com"
REPO_OWNER = "jeremiah-k"
REPO_NAME = "matrix-biblebot"
RELEASES_URL = f"{GITHUB_API_BASE}/repos/{REPO_OWNER}/{REPO_NAME}/releases/latest"

# Update check configuration
UPDATE_CHECK_TIMEOUT = 10  # seconds
UPDATE_CHECK_USER_AGENT = f"BibleBot/{__version__}"


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
                if response.status == 200:
                    data = await response.json()
                    tag_name = data.get("tag_name", "").lstrip("v")
                    logger.debug(f"Latest release from GitHub: {tag_name}")
                    return tag_name
                else:
                    logger.debug(f"GitHub API returned status {response.status}")
                    return None

    except asyncio.TimeoutError:
        logger.debug("Update check timed out")
        return None
    except aiohttp.ClientError as e:
        logger.debug(f"Network error during update check: {e}")
        return None
    except Exception as e:
        logger.debug(f"Unexpected error during update check: {e}")
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
        return latest_ver > current_ver
    except Exception as e:
        logger.debug(f"Error comparing versions '{current}' and '{latest}': {e}")
        return False


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


async def perform_startup_update_check() -> None:
    """
    Perform an update check on startup and log the result.

    This function is designed to be called during bot startup.
    It performs the check asynchronously and logs appropriate messages.
    """
    logger.debug("Performing startup update check...")

    try:
        update_available, latest_version = await check_for_updates()

        if update_available and latest_version:
            logger.info("🔄 A new version of BibleBot is available!")
            logger.info(f"   Current version: {__version__}")
            logger.info(f"   Latest version:  {latest_version}")
            logger.info(
                f"   Visit: https://github.com/{REPO_OWNER}/{REPO_NAME}/releases"
            )
        else:
            logger.debug("BibleBot is up to date")

    except Exception as e:
        logger.debug(f"Update check failed: {e}")
