"""Authentication helpers for BibleBot.

Provides interactive login to obtain and persist Matrix credentials in
`~/.config/matrix-biblebot/credentials.json` and helpers to load them.
Prefers restoring sessions from saved credentials; falls back to legacy
token-based auth via environment variables for backward compatibility.
"""

from __future__ import annotations

import asyncio
import getpass
import importlib.util
import json
import logging
import os
import platform
import shutil
import ssl
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import aiohttp
import nio.exceptions
from nio import (
    AsyncClient,
    AsyncClientConfig,
    DiscoveryInfoError,
    DiscoveryInfoResponse,
)

from biblebot.constants.api import (
    DISCOVERY_ATTR_HOMESERVER_URL,
    URL_PREFIX_HTTP,
    URL_PREFIX_HTTPS,
)
from biblebot.constants.app import (
    FILE_ENCODING_UTF8,
    LOGGER_NAME,
    PLATFORM_WINDOWS,
)
from biblebot.constants.config import (
    CONFIG_DIR,
    CONFIG_DIR_PERMISSIONS,
    CRED_KEY_ACCESS_TOKEN,
    CRED_KEY_DEVICE_ID,
    CRED_KEY_HOMESERVER,
    CRED_KEY_USER_ID,
    CREDENTIALS_FILE,
    CREDENTIALS_FILE_PERMISSIONS,
    E2EE_KEY_AVAILABLE,
    E2EE_KEY_DEPENDENCIES_INSTALLED,
    E2EE_KEY_ERROR,
    E2EE_KEY_PLATFORM_SUPPORTED,
    E2EE_KEY_READY,
    E2EE_KEY_STORE_EXISTS,
    E2EE_STORE_DIR,
)
from biblebot.constants.matrix import LOGIN_TIMEOUT_SEC, MATRIX_DEVICE_NAME
from biblebot.constants.messages import (
    ERROR_E2EE_DEPS_MISSING,
    ERROR_E2EE_NOT_SUPPORTED,
    MSG_E2EE_DEPS_NOT_FOUND,
    MSG_SERVER_DISCOVERY_FAILED,
    PROMPT_HOMESERVER,
    PROMPT_LOGIN_AGAIN,
    PROMPT_PASSWORD,
    PROMPT_USERNAME,
    RESPONSE_YES_PREFIX,
)

# Try to import certifi for better SSL handling
try:
    import certifi
except ImportError:
    certifi = None

# Note: We do not suppress matrix-nio warnings. Instead, we handle errors properly
# by checking response types explicitly and providing appropriate error handling.
# This follows the pattern used by other successful matrix-nio implementations.

logger = logging.getLogger(LOGGER_NAME)


def _create_ssl_context():
    """
    Create an SSLContext for Matrix client connections, preferring certifi's CA bundle when available.

    Returns:
        ssl.SSLContext | None: An SSLContext configured with certifi's CA file if certifi is present,
        otherwise the system default SSLContext. Returns None only if context creation fails.
    """
    if certifi:
        try:
            return ssl.create_default_context(cafile=certifi.where())
        except (ssl.SSLError, OSError):
            logger.warning(
                "Failed to create certifi-backed SSL context, falling back to system default",
                exc_info=True,
            )
    try:
        return ssl.create_default_context()
    except (ssl.SSLError, OSError):
        logger.exception("Failed to create system default SSL context")
        return None


@dataclass
class Credentials:
    homeserver: str
    user_id: str
    access_token: str
    device_id: Optional[str] = None

    def to_dict(self) -> dict:
        """
        Return a JSON-serializable dict representation of the credentials.

        The returned dictionary uses the module's credential key constants as keys and maps
        them to the corresponding fields (homeserver, user_id, access_token, device_id).
        This structure is intended for persisting credentials to disk.
        """
        return {
            CRED_KEY_HOMESERVER: self.homeserver,
            CRED_KEY_USER_ID: self.user_id,
            CRED_KEY_ACCESS_TOKEN: self.access_token,
            CRED_KEY_DEVICE_ID: self.device_id,
        }

    @staticmethod
    def from_dict(d: dict) -> "Credentials":
        """
        Create a Credentials instance from a dictionary.

        The input dictionary is expected to contain the credential keys:
        - CRED_KEY_HOMESERVER -> homeserver URL (defaults to "")
        - CRED_KEY_USER_ID -> Matrix user ID (defaults to "")
        - CRED_KEY_ACCESS_TOKEN -> access token (defaults to "")
        - CRED_KEY_DEVICE_ID -> device ID (optional, may be None)

        Parameters:
            d (dict): Mapping containing credential values (typically parsed from JSON).

        Returns:
            Credentials: A new Credentials populated from the provided dictionary; missing string fields default to an empty string and device_id may be None.
        """
        return Credentials(
            homeserver=d.get(CRED_KEY_HOMESERVER, ""),
            user_id=d.get(CRED_KEY_USER_ID, ""),
            access_token=d.get(CRED_KEY_ACCESS_TOKEN, ""),
            device_id=d.get(CRED_KEY_DEVICE_ID),
        )


def get_config_dir() -> Path:
    """
    Ensure the application's configuration directory exists and return its Path.

    Creates CONFIG_DIR (including parents) if missing and attempts to set its POSIX
    permissions to CONFIG_DIR_PERMISSIONS. If setting permissions fails the function
    logs a debug message but still returns the directory path.

    Returns:
        Path: The path to the configuration directory (CONFIG_DIR).
    """
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(CONFIG_DIR, CONFIG_DIR_PERMISSIONS)
    except OSError:
        logger.debug(
            f"Could not set config dir perms to {oct(CONFIG_DIR_PERMISSIONS)}",
            exc_info=True,
        )
    return CONFIG_DIR


def credentials_path() -> Path:
    """
    Return the path to the credentials file, ensuring the configuration directory exists.

    The function ensures the application's configuration directory is created (and its
    permissions attempted to be set) before returning the resolved Path to the
    credentials JSON file used to persist Matrix credentials.

    Returns:
        pathlib.Path: Path to the credentials file (e.g. ~/.config/matrix-biblebot/credentials.json).
    """
    get_config_dir()
    return CREDENTIALS_FILE


def save_credentials(creds: Credentials) -> None:
    """
    Persist a Credentials object to the configured credentials file atomically.

    The credentials are serialized to JSON and written to a temporary file in the same
    directory before being atomically moved into place. File permissions are set to
    the configured credentials-file mode. On failure the temporary file is removed
    when possible; errors are logged but not raised.

    Parameters:
        creds (Credentials): Credentials to serialize and save.
    """
    path = credentials_path()

    data = json.dumps(creds.to_dict(), indent=2)
    tmp = None
    tmp_name = None
    try:
        # Create a temporary file in the same directory to ensure `os.replace` is atomic.
        tmp = tempfile.NamedTemporaryFile(
            "w", dir=str(path.parent), delete=False, encoding=FILE_ENCODING_UTF8
        )
        tmp.write(data)
        tmp.flush()
        os.fsync(tmp.fileno())
        tmp_name = tmp.name
    finally:
        if tmp:
            tmp.close()

    if not tmp_name:
        logger.error(
            "Failed to create temporary file for credentials. "
            "Possible causes: insufficient disk space, permission issues, "
            f"or directory {path.parent} is not writable."
        )
        return

    try:
        os.chmod(tmp_name, CREDENTIALS_FILE_PERMISSIONS)
        # Verify both files are on the same filesystem before using os.replace
        tmp_stat = os.stat(tmp_name)
        try:
            dest_stat = os.stat(path.parent)
            same_filesystem = tmp_stat.st_dev == dest_stat.st_dev
        except OSError:
            # Parent directory might not exist or be accessible, assume same filesystem
            same_filesystem = True

        if same_filesystem:
            os.replace(tmp_name, path)
        else:
            # Cross-filesystem move - use copy and delete
            logger.debug("Cross-filesystem move detected, using copy+delete fallback")
            import shutil

            shutil.copy2(tmp_name, path)
            os.unlink(tmp_name)

        logger.info(f"Saved credentials to {path}")
    except OSError:
        logger.exception(
            f"Failed to save credentials to {path}. "
            "Possible causes: insufficient permissions, disk full, "
            "filesystem issues, or cross-filesystem move attempted."
        )
        # On failure, clean up the temporary file.
        try:
            os.unlink(tmp_name)
        except OSError as cleanup_error:
            logger.debug(f"Failed to clean up temp file: {cleanup_error}")


def load_credentials() -> Optional[Credentials]:
    """
    Load persisted Matrix credentials from the configured credentials file.

    Reads and parses the credentials JSON at the configured credentials path and returns a Credentials instance.
    If the credentials file does not exist, cannot be read, or contains invalid JSON, returns None (errors are logged).
    """
    path = credentials_path()
    if not path.exists():
        return None
    try:
        text = path.read_text(encoding=FILE_ENCODING_UTF8)
        data = json.loads(text)
        return Credentials.from_dict(data)
    except (OSError, json.JSONDecodeError):
        logger.exception(f"Failed to read credentials from {path}")
        return None


def get_store_dir() -> Path:
    """
    Ensure the E2EE store directory exists and return its path.

    Creates the configured E2EE store directory (including parents) if missing and attempts to restrict
    its permissions to 0o700. Failure to change permissions is ignored (a debug message is logged).
    Returns the Path to the E2EE store directory.

    Returns:
        Path: Path to the E2EE store directory (guaranteed to exist after this call).
    """
    E2EE_STORE_DIR.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(E2EE_STORE_DIR, 0o700)
    except OSError:
        logger.debug("Could not set E2EE store perms to 0o700", exc_info=True)
    return E2EE_STORE_DIR


def check_e2ee_status() -> dict:
    """
    Return the E2EE readiness and availability status.

    Performs platform and dependency checks, inspects whether the local E2EE store directory exists (without creating it), and checks for saved Matrix credentials to determine whether encrypted sessions can be used.

    Returns:
        dict: A mapping keyed by E2EE status constants with the following entries:
            - E2EE_KEY_AVAILABLE (bool): True if the current platform is supported and required Python dependencies are installed.
            - E2EE_KEY_DEPENDENCIES_INSTALLED (bool): True if required libraries (e.g., olm and nio) are importable.
            - E2EE_KEY_STORE_EXISTS (bool): True if the configured E2EE store directory already exists on disk.
            - E2EE_KEY_PLATFORM_SUPPORTED (bool): False if the platform is unsupported (Windows).
            - E2EE_KEY_ERROR (Optional[str]): Human-readable error message when a check fails; otherwise None.
            - E2EE_KEY_READY (bool): True when E2EE is available, persisted credentials exist, and the store directory exists (ready for encrypted sessions).

    Notes:
        - This function does not create the E2EE store directory; it only checks for its existence.
        - It may call load_credentials() to determine whether credentials are present.
    """
    status = {
        E2EE_KEY_AVAILABLE: False,
        E2EE_KEY_DEPENDENCIES_INSTALLED: False,
        E2EE_KEY_STORE_EXISTS: False,
        E2EE_KEY_PLATFORM_SUPPORTED: True,
        E2EE_KEY_ERROR: None,
        E2EE_KEY_READY: False,
    }

    # Check platform support
    if platform.system() == PLATFORM_WINDOWS:
        status[E2EE_KEY_PLATFORM_SUPPORTED] = False
        status[E2EE_KEY_ERROR] = ERROR_E2EE_NOT_SUPPORTED
        return status

    # Check dependencies
    try:
        olm_spec = importlib.util.find_spec("olm")
        nio_spec = importlib.util.find_spec("nio")
        if olm_spec is not None and nio_spec is not None:
            status[E2EE_KEY_DEPENDENCIES_INSTALLED] = True
        else:
            raise ImportError(MSG_E2EE_DEPS_NOT_FOUND)
    except ImportError as e:
        status[E2EE_KEY_ERROR] = f"{ERROR_E2EE_DEPS_MISSING}: {e}"
        return status

    # Check store directory without creating it
    store_dir = E2EE_STORE_DIR
    status[E2EE_KEY_STORE_EXISTS] = store_dir.exists()

    creds = load_credentials()
    # E2EE "available" means dependencies are installed and platform is supported
    status[E2EE_KEY_AVAILABLE] = bool(
        status[E2EE_KEY_DEPENDENCIES_INSTALLED] and status[E2EE_KEY_PLATFORM_SUPPORTED]
    )
    # E2EE "ready" means available AND credentials exist AND store exists
    status[E2EE_KEY_READY] = bool(
        status[E2EE_KEY_AVAILABLE] and creds and status[E2EE_KEY_STORE_EXISTS]
    )

    return status


def print_e2ee_status():
    """
    Print a human-readable report about the module's End-to-End Encryption (E2EE) readiness to stdout.

    The report includes:
    - whether the current platform is supported,
    - whether required dependencies are installed,
    - whether a local E2EE store directory exists,
    - an overall enabled/disabled indicator,
    - any detected error message.

    If E2EE is supported but not available, the function also prints short instructions to enable E2EE and re-run login. This function obtains its information by calling check_e2ee_status() and has the side effect of writing the formatted status to standard output.
    """
    status = check_e2ee_status()

    print("\n🔐 Encryption (E2EE) Status:")
    print(f"  Platform Support: {'✓' if status[E2EE_KEY_PLATFORM_SUPPORTED] else '✗'}")
    print(f"  Dependencies: {'✓' if status[E2EE_KEY_DEPENDENCIES_INSTALLED] else '✗'}")
    print(f"  Store Directory: {'✓' if status[E2EE_KEY_STORE_EXISTS] else '✗'}")
    print(f"  Available: {'✓' if status[E2EE_KEY_AVAILABLE] else '✗'}")
    print(f"  Ready: {'✓' if status[E2EE_KEY_READY] else '✗'}")

    if status[E2EE_KEY_ERROR]:
        print(f"  Error: {status[E2EE_KEY_ERROR]}")

    if not status[E2EE_KEY_AVAILABLE] and status[E2EE_KEY_PLATFORM_SUPPORTED]:
        print("\n  To enable encryption:")
        print('    pip install ".[e2e]"  # preferred')
        print("    # or: pip install -r requirements-e2e.txt")
        print("    biblebot auth login  # Re-login to enable encryption")

    print()


async def discover_homeserver(
    client: AsyncClient, homeserver: str, timeout: float = 10.0
) -> str:
    """
    Discover the server's canonical homeserver URL via Matrix discovery, falling back to the provided homeserver on timeout or error.

    This awaits client.discovery_info() for up to `timeout` seconds; if the discovery response contains a usable homeserver URL that differs from the input, that URL is returned. On timeout, network/protocol errors, or unexpected responses the original `homeserver` is returned unchanged.

    Parameters:
        homeserver (str): Fallback homeserver URL to return when discovery does not yield a usable URL.
        timeout (float): Maximum seconds to wait for the discovery request (default 10.0).

    Returns:
        str: The discovered homeserver URL, or the provided `homeserver` if discovery fails or is inconclusive.
    """
    try:
        logger.debug(f"Attempting server discovery for {homeserver}")
        info = await asyncio.wait_for(client.discovery_info(), timeout=timeout)
        if isinstance(info, DiscoveryInfoResponse):
            discovered_url = getattr(info, DISCOVERY_ATTR_HOMESERVER_URL, None)
            if discovered_url:
                logger.debug(f"Server discovery successful: {discovered_url}")
                return discovered_url
            else:
                logger.debug("Server discovery response missing homeserver URL")
        elif isinstance(info, DiscoveryInfoError):
            logger.debug(
                f"DiscoveryInfoError: {info.message if hasattr(info, 'message') else 'Unknown error'}"
            )
        else:
            logger.debug(f"Unexpected discovery response type: {type(info)}")
    except asyncio.TimeoutError:
        # Discovery timeout: fall back to the original homeserver URL because it's likely
        # the correct server and discovery is just slow or unavailable
        logger.debug("Server discovery timed out; using provided homeserver URL")
    except (
        nio.exceptions.RemoteProtocolError,
        nio.exceptions.RemoteTransportError,
        aiohttp.ClientError,
    ) as e:
        # Network/protocol errors: fall back to original homeserver as it's the most reliable option
        # when discovery infrastructure is having issues
        logger.debug(
            f"{MSG_SERVER_DISCOVERY_FAILED}: {type(e).__name__}: {e}",
        )
    except Exception:
        logger.exception("Unexpected error during server discovery")

    logger.debug(f"Using original homeserver URL: {homeserver}")
    return homeserver


def _get_user_input(
    prompt: str, provided_value: Optional[str], field_name: str
) -> Optional[str]:
    """
    Prompt for a value unless one is already provided; return None on cancellation or empty input.

    If `provided_value` is non-empty, it is returned immediately. Otherwise the user is prompted with
    `prompt`; an EOFError or KeyboardInterrupt is treated as cancellation and returns None. If the
    entered value is empty after stripping, returns None and logs an error using `field_name` for context.

    Parameters:
        prompt (str): Prompt shown to the user when requesting input.
        provided_value (Optional[str]): Pre-supplied value to use instead of prompting.
        field_name (str): Name used in error messages when input is empty.

    Returns:
        Optional[str]: The provided or entered value, or None if cancelled or empty.
    """
    if provided_value:
        return provided_value

    try:
        value = input(prompt).strip()
    except (EOFError, KeyboardInterrupt):
        logger.info("\nLogin cancelled.")
        return None

    if not value:
        # Ensure field_name is valid before using it in error message
        safe_field_name = field_name if field_name and field_name.strip() else "Field"
        logger.error(f"{safe_field_name} cannot be empty.")
        return None

    return value


async def interactive_login(
    homeserver: Optional[str] = None,
    username: Optional[str] = None,
    password: Optional[str] = None,
) -> bool:
    """
    Perform an interactive Matrix login, persist credentials, and return whether a usable session exists.

    Prompts for any missing homeserver, username, or password. Performs server discovery to normalize the homeserver URL, enables end-to-end encryption and a local store when available, and saves a Credentials record (homeserver, user_id, access_token, device_id) on successful login. Returns False on user cancellation, timeouts, or login errors. If saved credentials already exist and the user declines to re-login, the function returns True (treats the existing session as a retained success).

    Parameters:
        homeserver (Optional[str]): Optional homeserver URL or host; if omitted the user is prompted. A scheme (http/https) will be prepended if missing.
        username (Optional[str]): Optional Matrix localpart (e.g., "alice") or full MXID (e.g., "@alice:example.org"); if omitted the user is prompted. A bare localpart will be converted to an MXID using the original server domain.
        password (Optional[str]): Optional password; if omitted the user is prompted with hidden input.

    Returns:
        bool: True if login completed successfully or an existing session was kept; False on cancellation, timeout, network or login errors.
    """
    existing_creds = load_credentials()
    if existing_creds:
        logger.info(f"You are already logged in as {existing_creds.user_id}")
        try:
            resp = input(PROMPT_LOGIN_AGAIN).lower()
            if not resp.startswith(RESPONSE_YES_PREFIX):
                logger.info("Login cancelled.")
                return True  # User is already logged in, so this is a "success"
        except (EOFError, KeyboardInterrupt):
            logger.info("\nLogin cancelled.")
            return False

    hs = _get_user_input(PROMPT_HOMESERVER, homeserver, "Homeserver")
    if hs is None:
        return False
    if not (hs.startswith(URL_PREFIX_HTTP) or hs.startswith(URL_PREFIX_HTTPS)):
        hs = URL_PREFIX_HTTPS + hs

    user_input = _get_user_input(PROMPT_USERNAME, username, "Username")
    if user_input is None:
        return False

    # Handle username input - support both full MXIDs and bare localparts
    localpart: Optional[str] = None
    if user_input.startswith("@"):
        # Full MXID provided (e.g., @user:server.com)
        user = user_input
        localpart = None
    else:
        # Bare localpart provided (e.g., "myusername")
        localpart = user_input
        # We'll construct the full MXID after server discovery
        user = None

    if password is not None:
        pwd = password
    else:
        try:
            pwd = getpass.getpass(PROMPT_PASSWORD)
        except (EOFError, KeyboardInterrupt):
            logger.info("\nLogin cancelled.")
            return False

    # E2EE-aware client config
    status = check_e2ee_status()
    e2ee_available = bool(status.get(E2EE_KEY_AVAILABLE))
    logger.debug(
        "E2EE dependencies %s; encryption %s",
        "found" if status.get(E2EE_KEY_DEPENDENCIES_INSTALLED) else "missing",
        "available" if e2ee_available else "unavailable",
    )

    # Create SSL context using certifi's certificates with system default fallback
    ssl_context = _create_ssl_context()
    if ssl_context is None:
        logger.warning(
            "Failed to create certifi/system SSL context; proceeding with AsyncClient defaults"
        )

    # First, we need to do server discovery to get the canonical homeserver URL
    # Create a temporary client for discovery
    temp_client_kwargs = {}
    if ssl_context:
        temp_client_kwargs["ssl"] = ssl_context

    temp_client = AsyncClient(hs, "@temp:temp.com", **temp_client_kwargs)

    # Attempt server discovery to normalize homeserver URL
    original_hs = hs
    discovered_hs = await discover_homeserver(temp_client, hs)
    await temp_client.close()

    logger.info(f"Server discovery: {original_hs} -> {discovered_hs}")

    # Now construct the proper MXID if we have a localpart
    # IMPORTANT: Use the ORIGINAL server domain for MXID, not the discovered API endpoint
    if localpart is not None:
        original_server_name = urlparse(original_hs).netloc
        user = f"@{localpart}:{original_server_name}"
        logger.info(
            f"Constructed MXID: {user} from localpart: {localpart} and original server: {original_server_name}"
        )
        logger.info(f"Discovered homeserver URL: {discovered_hs}")
        logger.info(f"Original server domain: {original_server_name}")

    # Use the discovered homeserver URL for API calls
    hs = discovered_hs

    if not user:
        logger.error("Failed to determine user ID for login")
        return False

    # Check for existing credentials to reuse device_id
    existing_device_id = None
    try:
        if existing_creds and existing_creds.user_id == user:
            existing_device_id = existing_creds.device_id
            if existing_device_id:
                logger.info(f"Reusing existing device_id: {existing_device_id}")
    except Exception as e:
        logger.debug(f"Could not check existing credentials: {e}")

    # Create the actual client with the proper homeserver and user ID
    client_kwargs = {}
    if e2ee_available:
        client_kwargs["store_path"] = str(get_store_dir())
    if ssl_context:
        client_kwargs["ssl"] = ssl_context
    if existing_device_id:
        client_kwargs["device_id"] = existing_device_id

    client = AsyncClient(
        hs,
        user,
        config=AsyncClientConfig(
            store_sync_tokens=True, encryption_enabled=e2ee_available
        ),
        **client_kwargs,
    )

    # Set device_id on client if we have an existing one
    if existing_device_id:
        client.device_id = existing_device_id

    logger.info(f"Logging in to {hs} as {user}")
    try:
        # Perform login without warning suppression - handle errors properly instead
        resp = await asyncio.wait_for(
            client.login(password=pwd, device_name=MATRIX_DEVICE_NAME),
            timeout=LOGIN_TIMEOUT_SEC,
        )

        # Check response type explicitly - following mmrelay pattern
        if hasattr(resp, "access_token"):
            # Login successful - check for access_token attribute like mmrelay does
            creds = Credentials(
                homeserver=hs,
                user_id=resp.user_id,
                access_token=resp.access_token,
                device_id=resp.device_id,
            )
            save_credentials(creds)
            logger.info("Login successful! Credentials saved.")
            return True
        else:
            # Login failed - handle error response properly
            logger.error(f"Login failed: {resp}")

            # Extract error details if available
            if hasattr(resp, "message"):
                logger.error(f"Error message: {resp.message}")
                error_message = resp.message.lower()

                # Provide user-friendly error messages based on the error
                errcode = getattr(resp, "errcode", None) or getattr(resp, "code", None)
                if (
                    errcode == "M_LIMIT_EXCEEDED"
                    or "limit" in error_message
                    or "too many" in error_message
                ):
                    logger.error(
                        "❌ Too many login attempts. Please wait a few minutes and try again."
                    )
                    if getattr(resp, "retry_after_ms", None) is not None:
                        wait_time = (
                            resp.retry_after_ms / 1000 / 60
                        )  # Convert to minutes
                        logger.error(
                            f"   Server requests waiting {wait_time:.1f} minutes before retry."
                        )
                elif errcode == "M_FORBIDDEN" or "forbidden" in error_message:
                    logger.error(
                        "❌ Invalid username or password. Please check your credentials and try again."
                    )
                elif "not found" in error_message or "unknown" in error_message:
                    logger.error(
                        "❌ User not found. Please check your username and homeserver."
                    )
                else:
                    logger.error(f"❌ Login failed: {resp.message}")

            if hasattr(resp, "status_code"):
                logger.error(f"Status code: {resp.status_code}")

            return False
    except asyncio.TimeoutError:
        logger.exception(f"Login timed out after {LOGIN_TIMEOUT_SEC} seconds")
        return False
    except Exception:
        # Handle other exceptions during login (following mmrelay pattern)
        logger.exception("Login exception")
        return False
    finally:
        try:
            await client.close()
        except Exception:
            logger.debug("Failed to close client after login", exc_info=True)


async def interactive_logout() -> bool:
    """Attempt to log out and remove local credentials and E2EE store.

    Returns True on successful cleanup, regardless of remote logout outcome.
    """
    creds = load_credentials()
    # Best-effort server logout if we have creds
    if creds:
        client = AsyncClient(creds.homeserver, creds.user_id)
        try:
            client.restore_login(
                user_id=creds.user_id,
                device_id=creds.device_id,
                access_token=creds.access_token,
            )
            await client.logout()
            logger.info("Logged out from Matrix server")
        except Exception:
            logger.warning("Remote logout failed or skipped", exc_info=True)
        finally:
            try:
                await client.close()
            except Exception:
                logger.debug("Failed to close client during logout", exc_info=True)

    # Remove credentials.json
    try:
        p = credentials_path()
        if p.exists():
            p.unlink()
            logger.info(f"Removed {p}")
    except OSError:
        logger.warning("Failed to remove credentials.json", exc_info=True)

    # Remove E2EE store dir
    store = E2EE_STORE_DIR
    if store.exists():
        try:
            shutil.rmtree(store)
            logger.info(f"Cleared E2EE store at {store}")
        except OSError:
            logger.exception(f"Failed to remove E2EE store at {store}")

    return True
