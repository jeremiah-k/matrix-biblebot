"""Authentication helpers for BibleBot.

Provides interactive login to obtain and persist Matrix credentials in
`~/.config/matrix-biblebot/credentials.json` and helpers to load them.
Prefers restoring sessions from saved credentials; falls back to legacy
token-based auth via environment variables for backward compatibility.
"""

from __future__ import annotations

import asyncio
import getpass
import json
import logging
import os
import shutil
import ssl
import tempfile
import warnings
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

from .constants import (
    CONFIG_DIR,
    CONFIG_DIR_PERMISSIONS,
    CRED_KEY_ACCESS_TOKEN,
    CRED_KEY_DEVICE_ID,
    CRED_KEY_HOMESERVER,
    CRED_KEY_USER_ID,
    CREDENTIALS_FILE,
    CREDENTIALS_FILE_PERMISSIONS,
    DISCOVERY_ATTR_HOMESERVER_URL,
    E2EE_KEY_AVAILABLE,
    E2EE_KEY_DEPENDENCIES_INSTALLED,
    E2EE_KEY_ERROR,
    E2EE_KEY_PLATFORM_SUPPORTED,
    E2EE_KEY_READY,
    E2EE_KEY_STORE_EXISTS,
    E2EE_STORE_DIR,
    ERROR_E2EE_DEPS_MISSING,
    ERROR_E2EE_NOT_SUPPORTED,
    FILE_ENCODING_UTF8,
    LOGGER_NAME,
    LOGIN_TIMEOUT_SEC,
    MATRIX_DEVICE_NAME,
    MSG_E2EE_DEPS_NOT_FOUND,
    MSG_SERVER_DISCOVERY_FAILED,
    PLATFORM_WINDOWS,
    PROMPT_HOMESERVER,
    PROMPT_LOGIN_AGAIN,
    PROMPT_PASSWORD,
    PROMPT_USERNAME,
    RESPONSE_YES_PREFIX,
    URL_PREFIX_HTTP,
    URL_PREFIX_HTTPS,
)

# Try to import certifi for better SSL handling
try:
    import certifi
except ImportError:
    certifi = None

# Suppress the specific nio validation warning that occurs when servers return error responses
# that don't match the success schema (this is a library issue, not our code)
warnings.filterwarnings(
    "ignore", message=".*user_id.*required property.*", category=UserWarning
)

logger = logging.getLogger(LOGGER_NAME)


def _create_ssl_context():
    """
    Create an SSLContext for Matrix client connections, preferring certifi's CA bundle when available.

    Returns:
        ssl.SSLContext | None: An SSLContext configured with certifi's CA file if certifi is present,
        otherwise the system default SSLContext. Returns None only if context creation fails.
    """
    try:
        if certifi:
            return ssl.create_default_context(cafile=certifi.where())
        else:
            return ssl.create_default_context()
    except Exception as e:
        logger.warning(
            f"Failed to create certifi-backed SSL context, falling back to system default: {e}"
        )
        try:
            return ssl.create_default_context()
        except Exception as fallback_e:
            logger.error(f"Failed to create system default SSL context: {fallback_e}")
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
        logger.error("Failed to create temporary file for credentials.")
        return

    try:
        os.chmod(tmp_name, CREDENTIALS_FILE_PERMISSIONS)
        os.replace(tmp_name, path)
        logger.info(f"Saved credentials to {path}")
    except OSError:
        logger.exception(f"Failed to save credentials to {path}")
        # On failure, clean up the temporary file.
        try:
            os.unlink(tmp_name)
        except OSError as e:
            logger.debug(f"Failed to clean up temp file: {e}")


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
    Return a dictionary describing whether End-to-End Encryption (E2EE) is available and ready.

    Performs platform and dependency checks, inspects whether the local E2EE store directory exists, and checks for saved Matrix credentials.

    Returns:
        dict: Status mapping with these keys:
            - E2EE_KEY_AVAILABLE (bool): True if platform is supported and required Python dependencies are present.
            - E2EE_KEY_DEPENDENCIES_INSTALLED (bool): True if required libraries (e.g., olm and nio) are importable.
            - E2EE_KEY_STORE_EXISTS (bool): True if the configured E2EE store directory exists on disk.
            - E2EE_KEY_PLATFORM_SUPPORTED (bool): False on unsupported platforms (Windows).
            - E2EE_KEY_ERROR (Optional[str]): Human-readable error message when a check failed, otherwise None.
            - E2EE_KEY_READY (bool): True when credentials are present and the E2EE store exists (ready for encrypted sessions).
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
    import platform

    if platform.system() == PLATFORM_WINDOWS:
        status[E2EE_KEY_PLATFORM_SUPPORTED] = False
        status[E2EE_KEY_ERROR] = ERROR_E2EE_NOT_SUPPORTED
        return status

    # Check dependencies
    try:
        import importlib.util

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
    # Consider E2EE "available" when deps are present AND creds exist AND a store exists
    status[E2EE_KEY_AVAILABLE] = bool(
        status[E2EE_KEY_DEPENDENCIES_INSTALLED] and status[E2EE_KEY_PLATFORM_SUPPORTED]
    )
    status[E2EE_KEY_READY] = bool(creds and status[E2EE_KEY_STORE_EXISTS])

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
    Attempt to discover the server's canonical homeserver URL via the Matrix discovery API and fall back to the provided homeserver on error or timeout.

    If discovery succeeds and returns a homeserver URL, that URL is returned. Any discovery errors, unexpected exceptions, or a timeout cause the function to return the original `homeserver` argument.

    Parameters:
        client (AsyncClient): Matrix client to use for discovery.
        homeserver (str): Fallback homeserver URL to use if discovery fails or times out.
        timeout (float): Maximum seconds to wait for the discovery request (default 10.0).

    Returns:
        str: The discovered homeserver URL, or the provided `homeserver` if discovery did not yield a URL.
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
        logger.debug("Server discovery timed out; using provided homeserver URL")
    except (
        nio.exceptions.RemoteProtocolError,
        nio.exceptions.RemoteTransportError,
        aiohttp.ClientError,
    ) as e:
        logger.debug(
            f"{MSG_SERVER_DISCOVERY_FAILED}: {type(e).__name__}: {e}",
        )
    except Exception as e:
        logger.debug(
            f"Unexpected error during server discovery: {type(e).__name__}: {e}"
        )

    logger.debug(f"Using original homeserver URL: {homeserver}")
    return homeserver


async def interactive_login(
    homeserver: Optional[str] = None,
    username: Optional[str] = None,
    password: Optional[str] = None,
) -> bool:
    """
    Perform an interactive Matrix login, persist credentials to the configured credentials file, and return whether login succeeded.

    Prompts for any missing homeserver, username, or password values; if saved credentials exist the user is asked whether to create a new device session. The function will attempt server discovery to normalize the homeserver URL, enable end-to-end encryption if dependencies and platform support are available (creating an E2EE store when enabled), and save a Credentials record (homeserver, user_id, access_token, device_id) on successful login. On user cancellation, timeouts, or login errors the function returns False. If the user declines to re-login when credentials already exist, the function returns True (treating the existing session as a successful state).

    Parameters:
        homeserver (Optional[str]): Optional homeserver URL or host to use; if omitted, the user is prompted. A scheme (http/https) will be added if missing.
        username (Optional[str]): Optional Matrix localpart or full user ID; if omitted the user is prompted. A bare localpart will be transformed into a full user ID using the homeserver host.
        password (Optional[str]): Optional password; if omitted the user is prompted (input is hidden).

    Returns:
        bool: True if login completed or an existing session was kept; False on cancellation, timeout, or any login error.
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

    hs = homeserver or input(PROMPT_HOMESERVER).strip()
    if not (hs.startswith(URL_PREFIX_HTTP) or hs.startswith(URL_PREFIX_HTTPS)):
        hs = URL_PREFIX_HTTPS + hs

    user_input = username or input(PROMPT_USERNAME).strip()

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

    pwd = password or getpass.getpass(PROMPT_PASSWORD)

    # E2EE-aware client config
    status = check_e2ee_status()
    e2ee_available = bool(status.get(E2EE_KEY_AVAILABLE))
    logger.debug(
        "E2EE dependencies %s; encryption %s",
        "found" if status.get(E2EE_KEY_DEPENDENCIES_INSTALLED) else "missing",
        "enabled" if e2ee_available else "disabled",
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
    hs = await discover_homeserver(temp_client, hs)
    await temp_client.close()

    # Now construct the proper MXID if we have a localpart
    if localpart is not None:
        server_name = urlparse(hs).netloc
        user = f"@{localpart}:{server_name}"
        logger.debug(
            f"Constructed MXID: {user} from localpart: {localpart} and server: {server_name}"
        )

    if not user:
        logger.error("Failed to determine user ID for login")
        return False

    # Create the actual client with the proper homeserver and user ID
    client_kwargs = {}
    if e2ee_available:
        client_kwargs["store_path"] = str(get_store_dir())
    if ssl_context:
        client_kwargs["ssl"] = ssl_context

    client = AsyncClient(
        hs,
        user,
        config=AsyncClientConfig(
            store_sync_tokens=True, encryption_enabled=e2ee_available
        ),
        **client_kwargs,
    )

    logger.info(f"Logging in to {hs} as {user}")
    try:
        resp = await asyncio.wait_for(
            client.login(password=pwd, device_name=MATRIX_DEVICE_NAME),
            timeout=LOGIN_TIMEOUT_SEC,
        )

        # Check if login was successful - nio returns LoginResponse on success, LoginError on failure
        if isinstance(resp, nio.LoginResponse):
            # LoginResponse has user_id, device_id, and access_token fields
            creds = Credentials(
                homeserver=hs,
                user_id=resp.user_id,
                access_token=resp.access_token,
                device_id=resp.device_id,
            )
            save_credentials(creds)
            logger.info("Login successful! Credentials saved.")
            await client.close()
            return True
        elif isinstance(resp, nio.LoginError):
            logger.error(f"Login failed: {resp.message}")

            # Provide user-friendly error messages based on the error
            error_message = resp.message.lower()
            if resp.status_code == "M_FORBIDDEN" or "forbidden" in error_message:
                logger.error(
                    "❌ Invalid username or password. Please check your credentials and try again."
                )
            elif "not found" in error_message or "unknown" in error_message:
                logger.error(
                    "❌ User not found. Please check your username and homeserver."
                )
            elif "limit" in error_message or resp.status_code == "M_LIMIT_EXCEEDED":
                logger.error(
                    "❌ Too many login attempts. Please wait a few minutes and try again."
                )
            else:
                logger.error(f"❌ Login failed: {resp.message}")
            return False
        else:
            logger.error(f"Unexpected login response type: {type(resp)}")
            await client.close()
            return False
    except asyncio.TimeoutError:
        logger.exception("Login timed out after %s seconds", LOGIN_TIMEOUT_SEC)
        await client.close()
        return False
    except (OSError, ValueError, RuntimeError):
        logger.exception("Login error")
        await client.close()
        return False
    except (nio.exceptions.MatrixRequestError, aiohttp.ClientError) as e:
        logger.error(f"Network/request error during login: {e}")
        logger.error(
            "❌ Network error. Please check your internet connection and homeserver URL."
        )
        await client.close()
        return False
    except Exception:
        # Unexpected error
        logger.exception("Unexpected login error")
        await client.close()
        return False


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
    # Remove E2EE store dir
    store = E2EE_STORE_DIR
    if store.exists():
        shutil.rmtree(store, ignore_errors=True)
        logger.info(f"Cleared E2EE store at {store}")

    return True
