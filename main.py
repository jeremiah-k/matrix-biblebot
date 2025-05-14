#!/usr/bin/env python3
"""
Backward compatibility script for running BibleBot.
This script is maintained for backward compatibility.
It's recommended to use the 'biblebot' command instead.
"""

import asyncio
import logging
import sys

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logging.info("Using legacy entry point. Consider using 'biblebot' command instead.")

try:
    from biblebot.bot import main as bot_main

    if __name__ == "__main__":
        asyncio.run(bot_main())

except ImportError:
    logging.error(
        "BibleBot package not found. Please install it with 'pip install matrix-biblebot' "
        "or 'pipx install matrix-biblebot'"
    )
    sys.exit(1)
