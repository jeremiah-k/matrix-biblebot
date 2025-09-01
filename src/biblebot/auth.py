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
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from nio import (
    AsyncClient,
    AsyncClientConfig,
    DiscoveryInfoError,
    DiscoveryInfoResponse,
)

from .constants import (
    CONFIG_DIR,
    CONFIG_DIR_PERMISSIONS,
    CREDENTIALS_FILE,
    CREDENTIALS_FILE_PERMISSIONS,
    E2EE_STORE_DIR,
    ERROR_E2EE_DEPS_MISSING,
    ERROR_E2EE_NOT_SUPPORTED,
    LOGGER_NAME,
    LOGIN_TIMEOUT_SEC,
    MATRIX_DEVICE_NAME,
    PROMPT_HOMESERVER,
    PROMPT_USERNAME,
)

logger = logging.getLogger(LOGGER_NAME)


@dataclass
class Credentials:
    homeserver: str
    user_id: str
    access_token: str
    device_id: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "homeserver": self.homeserver,
            "user_id": self.user_id,
            "access_token": self.access_token,
            "device_id": self.device_id,
        }

    @staticmethod
    def from_dict(d: dict) -> "Credentials":
        return Credentials(
            homeserver=d.get("homeserver", ""),
            user_id=d.get("user_id", ""),
            access_token=d.get("access_token", ""),
            device_id=d.get("device_id"),
        )


def get_config_dir() -> Path:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(CONFIG_DIR, CONFIG_DIR_PERMISSIONS)
    except OSError:
        logger.debug("Could not set config dir perms to 0700", exc_info=True)
    return CONFIG_DIR


def credentials_path() -> Path:
    get_config_dir()
    return CREDENTIALS_FILE


def save_credentials(creds: Credentials) -> None:
    path = credentials_path()

    data = json.dumps(creds.to_dict(), indent=2)
    tmp = None
    tmp_name = None
    try:
        # Create a temporary file in the same directory to ensure `os.replace` is atomic.
        tmp = tempfile.NamedTemporaryFile(
            "w", dir=str(path.parent), delete=False, encoding="utf-8"
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
    path = credentials_path()
    if not path.exists():
        return None
    try:
        text = path.read_text(encoding="utf-8")
        data = json.loads(text)
        return Credentials.from_dict(data)
    except (OSError, json.JSONDecodeError):
        logger.exception(f"Failed to read credentials from {path}")
        return None


def get_store_dir() -> Path:
    E2EE_STORE_DIR.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(E2EE_STORE_DIR, 0o700)
    except OSError:
        logger.debug("Could not set E2EE store perms to 0700", exc_info=True)
    return E2EE_STORE_DIR


def check_e2ee_status() -> dict:
    """Check E2EE availability and status."""
    status = {
        "available": False,
        "dependencies_installed": False,
        "store_exists": False,
        "platform_supported": True,
        "error": None,
        "ready": False,
    }

    # Check platform support
    import platform

    if platform.system() == "Windows":
        status["platform_supported"] = False
        status["error"] = ERROR_E2EE_NOT_SUPPORTED
        return status

    # Check dependencies
    try:
        import importlib.util

        olm_spec = importlib.util.find_spec("olm")
        nio_spec = importlib.util.find_spec("nio")
        if olm_spec is not None and nio_spec is not None:
            status["dependencies_installed"] = True
        else:
            raise ImportError("E2EE dependencies not found")
    except ImportError as e:
        status["error"] = f"{ERROR_E2EE_DEPS_MISSING}: {e}"
        return status

    # Check store directory without creating it
    store_dir = E2EE_STORE_DIR
    status["store_exists"] = store_dir.exists()

    creds = load_credentials()
    # Consider E2EE "available" when deps are present AND creds exist AND a store exists
    status["available"] = bool(
        status["dependencies_installed"] and status["platform_supported"]
    )
    status["ready"] = bool(creds and status["store_exists"])

    return status


def print_e2ee_status():
    """Print E2EE status information."""
    status = check_e2ee_status()

    print("\n🔐 E2EE (End-to-End Encryption) Status:")
    print(f"  Platform Support: {'✓' if status['platform_supported'] else '✗'}")
    print(f"  Dependencies: {'✓' if status['dependencies_installed'] else '✗'}")
    print(f"  Store Directory: {'✓' if status['store_exists'] else '✗'}")
    print(f"  Overall Status: {'✓ Enabled' if status['available'] else '✗ Disabled'}")

    if status["error"]:
        print(f"  Error: {status['error']}")

    if not status["available"] and status["platform_supported"]:
        print("\n  To enable E2EE:")
        print('    pip install ".[e2e]"  # preferred')
        print("    # or: pip install -r requirements-e2e.txt")
        print("    biblebot auth login  # Re-login to enable E2EE")

    print()


async def discover_homeserver(
    client: AsyncClient, homeserver: str, timeout: float = 10.0
) -> str:
    try:
        info = await asyncio.wait_for(client.discovery_info(), timeout=timeout)
        if isinstance(info, DiscoveryInfoResponse) and getattr(
            info, "homeserver_url", None
        ):
            return info.homeserver_url
        if isinstance(info, DiscoveryInfoError):
            logger.debug("DiscoveryInfoError, using provided homeserver URL")
    except asyncio.TimeoutError:
        logger.debug("Server discovery timed out; using provided homeserver URL")
    except Exception:
        logger.debug(
            "Server discovery failed; using provided homeserver URL",
            exc_info=True,
        )
    return homeserver


async def interactive_login(
    homeserver: Optional[str] = None,
    username: Optional[str] = None,
    password: Optional[str] = None,
) -> bool:
    """Interactive login that persists credentials.json for future runs.

    If credentials already exist, it will confirm with the user before
    creating a new device session.

    Returns True on success, False otherwise.
    """
    existing_creds = load_credentials()
    if existing_creds:
        logger.info(f"You are already logged in as {existing_creds.user_id}")
        try:
            resp = input(
                "Do you want to log in again? This will create a new device session. [y/N]: "
            ).lower()
            if not resp.startswith("y"):
                logger.info("Login cancelled.")
                return True  # User is already logged in, so this is a "success"
        except (EOFError, KeyboardInterrupt):
            logger.info("\nLogin cancelled.")
            return False

    hs = homeserver or input(PROMPT_HOMESERVER).strip()
    if not (hs.startswith("http://") or hs.startswith("https://")):
        hs = "https://" + hs

    user = username or input(PROMPT_USERNAME).strip()
    if not user.startswith("@"):
        from urllib.parse import urlparse

        server_name = urlparse(hs).netloc
        user = f"@{user}:{server_name}"

    pwd = password or getpass.getpass("Password: ")

    # E2EE-aware client config
    try:
        import importlib.util

        olm_spec = importlib.util.find_spec("olm")
        e2ee_available = olm_spec is not None
        if e2ee_available:
            logger.debug("E2EE dependencies found, enabling encryption for login.")
        else:
            logger.debug(
                "E2EE dependencies not found, proceeding without encryption for login."
            )
    except ImportError:
        e2ee_available = False
        logger.debug(
            "E2EE dependencies not found, proceeding without encryption for login."
        )

    client_kwargs = {}
    if e2ee_available:
        client_kwargs["store_path"] = str(get_store_dir())
    client = AsyncClient(
        hs,
        user,
        config=AsyncClientConfig(
            store_sync_tokens=True, encryption_enabled=e2ee_available
        ),
        **client_kwargs,
    )

    # Attempt server discovery to normalize homeserver URL
    hs = await discover_homeserver(client, hs)
    client.homeserver = hs

    logger.info(f"Logging in to {hs} as {user}")
    try:
        resp = await asyncio.wait_for(
            client.login(password=pwd, device_name=MATRIX_DEVICE_NAME),
            timeout=LOGIN_TIMEOUT_SEC,
        )

        if hasattr(resp, "access_token"):
            creds = Credentials(
                homeserver=hs,
                user_id=getattr(resp, "user_id", user),
                access_token=resp.access_token,
                device_id=resp.device_id,
            )
            save_credentials(creds)
            logger.info("Login successful! Credentials saved.")
            return True
        else:
            logger.error(f"Login failed: {resp}")
            return False
    except asyncio.TimeoutError:
        logger.exception("Login timed out after 30 seconds")
        return False
    except (OSError, ValueError, RuntimeError):
        logger.exception("Login error")
        return False
    except Exception:
        # e.g., nio exceptions like MatrixRequestError / LocalProtocolError
        logger.exception("Unexpected login error")
        return False
    finally:
        await client.close()


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
    try:
        store = E2EE_STORE_DIR
        if store.exists():
            shutil.rmtree(store, ignore_errors=True)
            logger.info(f"Cleared E2EE store at {store}")
    except OSError:
        logger.warning("Failed cleaning E2EE store", exc_info=True)

    return True
