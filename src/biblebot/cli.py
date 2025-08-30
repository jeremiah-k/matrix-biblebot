#!/usr/bin/env python3
"""Command-line interface for BibleBot."""

import argparse
import asyncio
import logging
import os
import shutil
import sys
from pathlib import Path

from . import __version__
from .auth import interactive_login, interactive_logout, load_credentials
from .bot import main as bot_main
from .tools import get_sample_config_path, get_sample_env_path

# Configure logging
logger = logging.getLogger("BibleBot")


def get_default_config_path():
    """Get the default config path in the user's home directory."""
    config_dir = Path.home() / ".config" / "matrix-biblebot"
    return config_dir / "config.yaml"


def generate_config(config_path):
    """Generate a sample config file at the specified path."""
    config_dir = os.path.dirname(config_path)
    env_path = os.path.join(config_dir, ".env")

    if os.path.exists(config_path) or os.path.exists(env_path):
        print("A config or .env file already exists at:")
        if os.path.exists(config_path):
            print(f"  {config_path}")
        if os.path.exists(env_path):
            print(f"  {env_path}")
        print("If you want to regenerate them, delete the existing files first.")
        print("Otherwise, edit the current files in place.")
        return False

    os.makedirs(config_dir, exist_ok=True)

    sample_config_path = get_sample_config_path()
    sample_env_path = get_sample_env_path()

    shutil.copy2(sample_config_path, config_path)
    shutil.copy2(sample_env_path, env_path)

    print(f"Generated sample config file at: {config_path}")
    print(f"Generated sample .env file at: {env_path}")
    print("Please edit these files with your Matrix credentials and API keys.")
    return True


def main():
    """Run the BibleBot CLI."""
    default_config_path = get_default_config_path()

    parser = argparse.ArgumentParser(description="BibleBot for Matrix")
    parser.add_argument(
        "--config",
        default=str(default_config_path),
        help=f"Path to config file (default: {default_config_path})",
    )
    parser.add_argument(
        "--log-level",
        choices=["error", "warning", "info", "debug"],
        default="info",
        help="Set logging level (default: info)",
    )
    parser.add_argument(
        "--generate-config",
        action="store_true",
        help="Generate sample config files at the specified path",
    )
    parser.add_argument(
        "--install-service",
        action="store_true",
        help="Install or update the systemd user service",
    )
    parser.add_argument(
        "--auth-login",
        action="store_true",
        help="Interactively log in to Matrix and save credentials.json",
    )
    parser.add_argument(
        "--auth-logout",
        action="store_true",
        help="Log out and remove credentials.json and E2EE store",
    )
    parser.add_argument(
        "--version", action="version", version=f"BibleBot {__version__}"
    )

    args = parser.parse_args()

    # Set up logging
    log_level = getattr(logging, args.log_level.upper())
    logging.basicConfig(
        level=log_level, format="%(asctime)s - %(levelname)s - %(message)s"
    )

    # Generate config if requested
    if args.generate_config:
        generate_config(args.config)
        return

    # Install service if requested
    if args.install_service:
        from .setup_utils import install_service

        install_service()
        return

    # Auth login if requested
    if args.auth_login:
        ok = asyncio.run(interactive_login())
        sys.exit(0 if ok else 1)
    if args.auth_logout:
        ok = asyncio.run(interactive_logout())
        sys.exit(0 if ok else 1)

    # Check if config file exists (unless credentials exist for headless use)
    creds = load_credentials()
    if not os.path.exists(args.config) and not creds:
        logging.warning(f"Config file not found: {args.config}")
        # Offer to generate at this location
        try:
            resp = (
                input(
                    "No config found. Generate sample config and .env here now? [y/N]: "
                )
                .strip()
                .lower()
            )
        except (EOFError, KeyboardInterrupt):
            resp = "n"
        if resp.startswith("y"):
            created = generate_config(args.config)
            if not created:
                sys.exit(1)
        else:
            logging.info(
                "Tip: run 'biblebot --generate-config' to create starter files."
            )
            sys.exit(1)

    # Run the bot
    try:
        asyncio.run(bot_main(args.config))
    except KeyboardInterrupt:
        logging.info("Bot stopped by user")
    except Exception as e:
        logging.error(f"Error running bot: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
