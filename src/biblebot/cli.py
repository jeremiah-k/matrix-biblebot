#!/usr/bin/env python3
"""Command-line interface for BibleBot."""

import argparse
import asyncio
import logging
import os
import shutil
import sys
from pathlib import Path

import yaml

from . import __version__
from .bot import main as bot_main
from .tools import get_sample_config_path


def get_default_config_path():
    """Get the default config path in the user's home directory."""
    config_dir = Path.home() / ".config" / "matrix-biblebot"
    return config_dir / "config.yaml"


def generate_config(config_path):
    """Generate a sample config file at the specified path."""
    # Create the directory if it doesn't exist
    config_dir = os.path.dirname(config_path)
    if not os.path.exists(config_dir):
        os.makedirs(config_dir, exist_ok=True)
        logging.info(f"Created directory: {config_dir}")

    # Get the sample config file path from the package
    sample_config_path = get_sample_config_path()

    if os.path.exists(sample_config_path):
        # Copy the sample config file to the destination
        shutil.copy2(sample_config_path, config_path)
        logging.info(f"Copied sample config from {sample_config_path} to {config_path}")
    else:
        # Fallback to hardcoded config if the sample file is not found
        logging.warning(f"Sample config file not found at {sample_config_path}, using default values")
        sample_config = {
            "matrix_homeserver": "https://your_homeserver_url_here",
            "matrix_user": "@your_bot_username:your_homeserver_domain",
            "matrix_room_ids": [
                "!your_room_id:your_homeserver_domain",
                "!your_other_room_id:your_homeserver_domain",
            ],
        }
        # Write the config file
        with open(config_path, "w") as f:
            yaml.dump(sample_config, f, default_flow_style=False)

    logging.info(f"Generated sample config file at: {config_path}")
    print(f"Generated sample config file at: {config_path}")
    print("Please edit this file with your Matrix credentials and room IDs.")
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
        help="Generate a sample config file at the specified path",
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

    # Check if config file exists
    if not os.path.exists(args.config):
        logging.error(f"Config file not found: {args.config}")
        logging.info("You can generate a sample config with: biblebot --generate-config")
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
