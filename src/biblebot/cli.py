#!/usr/bin/env python3
"""Command-line interface for BibleBot."""

import argparse
import asyncio
import logging
import os
import sys

from . import __version__
from .bot import main as bot_main


def main():
    """Run the BibleBot CLI."""
    parser = argparse.ArgumentParser(description="BibleBot for Matrix")
    parser.add_argument(
        "--config", 
        default="config.yaml", 
        help="Path to config file (default: config.yaml)"
    )
    parser.add_argument(
        "--log-level",
        choices=["error", "warning", "info", "debug"],
        default="info",
        help="Set logging level (default: info)",
    )
    parser.add_argument(
        "--version", 
        action="version", 
        version=f"BibleBot {__version__}"
    )

    args = parser.parse_args()

    # Set up logging
    log_level = getattr(logging, args.log_level.upper())
    logging.basicConfig(
        level=log_level, 
        format="%(asctime)s - %(levelname)s - %(message)s"
    )

    # Check if config file exists
    if not os.path.exists(args.config):
        logging.error(f"Config file not found: {args.config}")
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
