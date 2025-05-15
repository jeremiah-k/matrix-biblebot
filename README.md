# Matrix BibleBot

A simple Matrix bot that fetches Bible verses using APIs from [bible-api.com](https://bible-api.com) & [esv.org](https://api.esv.org/)

[![PyPI version](https://badge.fury.io/py/matrix-biblebot.svg)](https://badge.fury.io/py/matrix-biblebot)
[![Python Tests](https://github.com/jeremiah-k/matrix-biblebot/actions/workflows/python-tests.yml/badge.svg)](https://github.com/jeremiah-k/matrix-biblebot/actions/workflows/python-tests.yml)

## Supported Translations

- King James Version (KJV)
- English Standard Version (ESV) - requires an API key
- Easily extensible to support additional translations

## Installation

### Install from PyPI (Recommended)

```bash
pip install matrix-biblebot
```

For an isolated installation, you can use [pipx](https://pypa.github.io/pipx/):

```bash
pipx install matrix-biblebot
```

### Install from Source

Clone the repository:

```bash
git clone https://github.com/jeremiah-k/matrix-biblebot.git
cd matrix-biblebot
pip install .
```

For development:

```bash
pip install -e .
```

## Configuration

### 1. Create a .env file

Create a `.env` file in the same directory as your config file (e.g., `~/.config/matrix-biblebot/.env`) with your Matrix access token and any API keys:

```env
MATRIX_ACCESS_TOKEN="your_bots_matrix_access_token_here"
ESV_API_KEY="your_esv_api_key_here"  # Optional
```

The bot will first look for a `.env` file in the same directory as your config file. If not found, it will fall back to looking in the current working directory.

### 2. Create a config.yaml file

The bot looks for a configuration file at `~/.config/matrix-biblebot/config.yaml` by default. You can generate a template configuration file with:

```bash
biblebot --generate-config
```

This will create both a sample config file and a sample .env file in the `~/.config/matrix-biblebot/` directory. The config file has the following structure:

```yaml
matrix_homeserver: "https://your_homeserver_url_here"
matrix_user: "@your_bot_username:your_homeserver_domain"
matrix_room_ids:
  - "!your_room_id:your_homeserver_domain"
  - "#room_alias:your_homeserver_domain" # Room aliases are supported
```

Edit this file with your Matrix credentials and room IDs or aliases. The bot will automatically resolve room aliases to room IDs at startup.

You can also specify a custom config location:

```bash
biblebot --config /path/to/your/config.yaml
```

Or generate a config at a custom location:

```bash
biblebot --generate-config --config /path/to/your/config.yaml
```

## Usage

### Running the Bot

After installation and configuration, you can run the bot with:

```bash
biblebot
```

Or with custom options:

```bash
biblebot --config /path/to/config.yaml --log-level debug
```

### Command-line Options

```text
usage: biblebot [-h] [--config CONFIG] [--log-level {error,warning,info,debug}] [--generate-config] [--install-service] [--version]

BibleBot for Matrix

options:
  -h, --help            show this help message and exit
  --config CONFIG       Path to config file (default: ~/.config/matrix-biblebot/config.yaml)
  --log-level {error,warning,info,debug}
                        Set logging level (default: info)
  --generate-config     Generate a sample config file at the specified path
  --install-service     Install or update the systemd user service
  --version             show program's version number and exit
```

### Running as a Service

You can install BibleBot as a systemd user service to run automatically at startup:

```bash
biblebot --install-service
```

This will create a systemd user service file and guide you through enabling and starting the service. Once installed, you can manage the service with standard systemd commands:

```bash
systemctl --user start biblebot.service    # Start the service
systemctl --user stop biblebot.service     # Stop the service
systemctl --user restart biblebot.service  # Restart the service
systemctl --user status biblebot.service   # Check service status
```

### Interacting with the Bot

Invite the bot to rooms that are listed in the config.yaml file. The bot will respond to messages that match Bible verse references:

- Simple reference: `John 3:16`
- Range reference: `1 Cor 15:1-4`
- With translation: `John 3:16 esv`

## Development

Contributions are welcome! Feel free to open issues or submit pull requests.
