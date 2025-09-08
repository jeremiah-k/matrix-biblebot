"""Constants for application update checks."""

from biblebot import __version__

# GitHub API configuration
GITHUB_API_BASE = "https://api.github.com"
REPO_OWNER = "jeremiah-k"
REPO_NAME = "matrix-biblebot"
RELEASES_URL = f"{GITHUB_API_BASE}/repos/{REPO_OWNER}/{REPO_NAME}/releases/latest"

# Update check configuration
UPDATE_CHECK_TIMEOUT = 10  # seconds
UPDATE_CHECK_USER_AGENT = f"BibleBot/{__version__}"
