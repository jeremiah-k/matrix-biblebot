"""Authentication helpers for BibleBot.

Provides interactive login to obtain and persist Matrix credentials in
`~/.config/matrix-biblebot/credentials.json` and helpers to load them.
Prefers restoring sessions from saved credentials; falls back to legacy
token-based auth via environment variables for backward compatibility.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from nio import (
    AsyncClient,
    AsyncClientConfig,
    DiscoveryInfoError,
    DiscoveryInfoResponse,
)
from nio.exceptions import NioError

logger = logging.getLogger("BibleBot")


CONFIG_DIR = Path.home() / ".config" / "matrix-biblebot"
CREDENTIALS_FILE = CONFIG_DIR / "credentials.json"
E2EE_STORE_DIR = CONFIG_DIR / "e2ee-store"


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
        os.chmod(CONFIG_DIR, 0o700)
    except Exception:
        logger.debug("Could not set config dir perms to 0700")
    return CONFIG_DIR


def credentials_path() -> Path:
    get_config_dir()
    return CREDENTIALS_FILE


def save_credentials(creds: Credentials) -> None:
    path = credentials_path()
    import tempfile

    data = json.dumps(creds.to_dict(), indent=2)
    tmp = None
    try:
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
    try:
        try:
            os.chmod(tmp_name, 0o600)
        except Exception:
            logger.debug("Could not set credentials perms to 0600")
        os.replace(tmp_name, path)
        logger.info(f"Saved credentials to {path}")
    finally:
        # Best-effort cleanup if replace failed
        try:
            os.unlink(tmp_name)
        except Exception:
            pass


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
    except Exception:
        logger.debug("Could not set E2EE store perms to 0700")
    return E2EE_STORE_DIR


def check_e2ee_status() -> dict:
    """Check E2EE availability and status."""
    status = {
        "available": False,
        "dependencies_installed": False,
        "store_exists": False,
        "platform_supported": True,
        "error": None,
    }

    # Check platform support
    import platform

    if platform.system() == "Windows":
        status["platform_supported"] = False
        status["error"] = (
            "E2EE is not supported on Windows due to python-olm limitations"
        )
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
        status["error"] = f"E2EE dependencies not installed: {e}"
        return status

    # Check store directory without creating it
    store_dir = E2EE_STORE_DIR
    status["store_exists"] = store_dir.exists()

    creds = load_credentials()
    # Consider E2EE "available" when deps are present AND creds exist AND a store exists
    status["available"] = bool(
        status["dependencies_installed"] and creds and status["store_exists"]
    )

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
    except Exception as e:
        logger.debug(f"Server discovery failed: {e}; using provided homeserver URL")
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
    import getpass

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

    hs = homeserver or input("Matrix homeserver (e.g. https://matrix.org): ").strip()
    if not (hs.startswith("http://") or hs.startswith("https://")):
        hs = "https://" + hs

    user = username or input("Matrix username (e.g. @user:server.com): ").strip()
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
            client.login(password=pwd, device_name="biblebot"),
            timeout=30,
        )
    except asyncio.TimeoutError:
        logger.exception("Login timed out after 30 seconds")
        await client.close()
        return False
    except NioError:
        logger.exception("Login error")
        await client.close()
        return False
    except Exception:
        logger.exception("Unexpected login error")
        await client.close()
        return False

    if hasattr(resp, "access_token"):
        creds = Credentials(
            homeserver=hs,
            user_id=getattr(resp, "user_id", user),
            access_token=resp.access_token,
            device_id=resp.device_id,
        )
        save_credentials(creds)
        logger.info("Login successful! Credentials saved.")
        await client.close()
        return True
    else:
        logger.error(f"Login failed: {resp}")
        await client.close()
        return False


async def interactive_logout() -> bool:
    """Attempt to log out and remove local credentials and E2EE store.

    Returns True on successful cleanup, regardless of remote logout outcome.
    """
    creds = load_credentials()
    # Best-effort server logout if we have creds
    if creds:
        try:
            client = AsyncClient(creds.homeserver, creds.user_id)
            client.restore_login(
                user_id=creds.user_id,
                device_id=creds.device_id,
                access_token=creds.access_token,
            )
            await client.logout()
            await client.close()
            logger.info("Logged out from Matrix server")
        except Exception as e:
            logger.warning(f"Remote logout failed or skipped: {e}")

    # Remove credentials.json
    try:
        p = credentials_path()
        if p.exists():
            p.unlink()
            logger.info(f"Removed {p}")
    except Exception as e:
        logger.warning(f"Failed to remove credentials.json: {e}")

    # Remove E2EE store dir
    try:
        import shutil

        store = E2EE_STORE_DIR
        if store.exists():
            shutil.rmtree(store, ignore_errors=True)
            logger.info(f"Cleared E2EE store at {store}")
    except Exception as e:
        logger.warning(f"Failed cleaning E2EE store: {e}")

    return True
