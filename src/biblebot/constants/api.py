"""Constants for external APIs."""

__all__ = [
    "API_PARAM_FALSE",
    "API_PARAM_INCLUDE_FOOTNOTES",
    "API_PARAM_INCLUDE_HEADINGS",
    "API_PARAM_INCLUDE_PASSAGE_REFERENCES",
    "API_PARAM_INCLUDE_SHORT_COPYRIGHT",
    "API_PARAM_INCLUDE_VERSE_NUMBERS",
    "API_PARAM_Q",
    "API_REQUEST_TIMEOUT_SEC",
    "CACHE_MAX_SIZE",
    "CACHE_TTL_SECONDS",
    "DISCOVERY_ATTR_HOMESERVER_URL",
    "ESV_API_URL",
    "KJV_API_URL_TEMPLATE",
    "URL_PREFIX_HTTP",
    "URL_PREFIX_HTTPS",
]

# API URLs and endpoints
ESV_API_URL = "https://api.esv.org/v3/passage/text/"
KJV_API_URL_TEMPLATE = "https://bible-api.com/{passage}?translation=kjv"

# Timeouts and limits
API_REQUEST_TIMEOUT_SEC = 10

# API parameter names
API_PARAM_Q = "q"
API_PARAM_INCLUDE_HEADINGS = "include-headings"
API_PARAM_INCLUDE_FOOTNOTES = "include-footnotes"
API_PARAM_INCLUDE_VERSE_NUMBERS = "include-verse-numbers"
API_PARAM_INCLUDE_SHORT_COPYRIGHT = "include-short-copyright"
API_PARAM_INCLUDE_PASSAGE_REFERENCES = "include-passage-references"
API_PARAM_FALSE = "false"

# Discovery API attribute
DISCOVERY_ATTR_HOMESERVER_URL = "homeserver_url"

# URL prefixes
URL_PREFIX_HTTP = "http://"
URL_PREFIX_HTTPS = "https://"

# Cache settings
CACHE_MAX_SIZE = 100
CACHE_TTL_SECONDS = 3600  # 1 hour
