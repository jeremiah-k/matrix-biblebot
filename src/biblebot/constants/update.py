"""Constants for application update checks."""

from importlib.metadata import PackageNotFoundError, version

__all__ = [
    "GITHUB_API_BASE",
    "REPO_OWNER",
    "REPO_NAME",
    "RELEASES_URL",
    "RELEASES_PAGE_URL",
    "UPDATE_CHECK_TIMEOUT",
    "UPDATE_CHECK_USER_AGENT",
]

# GitHub API configuration
GITHUB_API_BASE = "https://api.github.com"
REPO_OWNER = "jeremiah-k"
REPO_NAME = "matrix-biblebot"
RELEASES_URL = f"{GITHUB_API_BASE}/repos/{REPO_OWNER}/{REPO_NAME}/releases/latest"
RELEASES_PAGE_URL = f"https://github.com/{REPO_OWNER}/{REPO_NAME}/releases"

# Update check configuration
UPDATE_CHECK_TIMEOUT = 10  # seconds
try:
    _VER = version("matrix-biblebot")
except PackageNotFoundError:
    _VER = "dev"
UPDATE_CHECK_USER_AGENT = f"BibleBot/{_VER}"
