# Matrix BibleBot

A simple Matrix bot that fetches Bible verses using APIs from [bible-api.com](https://bible-api.com) & [esv.org](https://api.esv.org/)

## Supported Translations

- King James Version (KJV)
- English Standard Version (ESV) - requires an API key
- Easily extensible to support additional translations

## Installation

### Option 1: Install with [pipx](https://pypa.github.io/pipx/) (Recommended)

```bash
pipx install matrix-biblebot
```

### Option 2: Install with pip

```bash
pip install matrix-biblebot
```

### Option 3: Install from Source

```bash
git clone https://github.com/jeremiah-k/matrix-biblebot.git
cd matrix-biblebot
pip install .  # For normal use
# OR
pip install -e .  # For development
```

## Configuration

### Generate Configuration Files

The easiest way to get started is to generate the configuration files:

```bash
biblebot --generate-config
```

This will create both a sample config file (`config.yaml`) and a sample `.env` file in the `~/.config/matrix-biblebot/` directory.

You can also specify a custom location:

```bash
biblebot --generate-config --config /path/to/your/config.yaml
```

### Edit Configuration Files

1. **Edit the config.yaml file** with your Matrix homeserver and room information:

```yaml
matrix_homeserver: "https://your_homeserver_url_here"
matrix_user: "@your_bot_username:your_homeserver_domain"
matrix_room_ids:
  - "!your_room_id:your_homeserver_domain"
  - "#room_alias:your_homeserver_domain" # Room aliases are supported
```

2. **Edit the .env file** with your access token and optional API keys:

```env
MATRIX_ACCESS_TOKEN="your_bots_matrix_access_token_here"
ESV_API_KEY="your_esv_api_key_here"  # Optional
```

The bot will automatically resolve room aliases to room IDs at startup. You can use either room IDs (starting with !) or room aliases (starting with #) in your configuration.

### Configuration File Locations

By default, the bot looks for:

- Configuration file: `~/.config/matrix-biblebot/config.yaml`
- Environment file: `~/.config/matrix-biblebot/.env`

You can specify a different config location when running the bot:

```bash
biblebot --config /path/to/your/config.yaml
```

## Usage

### Quick Start

1. Install the bot: `pipx install matrix-biblebot`
2. Generate config files: `biblebot --generate-config`
3. Edit the config files in `~/.config/matrix-biblebot/`
4. Run the bot: `biblebot`

### Running the Bot

After configuring the bot, you can run it in several ways:

```bash
# Run with default configuration
biblebot

# Run with custom config location
biblebot --config /path/to/config.yaml

# Run with debug logging
biblebot --log-level debug
```

### Running as a Service (Recommended)

For a persistent installation, set up BibleBot as a systemd user service:

```bash
biblebot --install-service
```

This will:

1. Create a systemd user service file
2. Guide you through enabling the service to start at boot
3. Offer to start the service immediately

Once installed, manage the service with standard systemd commands:

```bash
systemctl --user start biblebot.service    # Start the service
systemctl --user stop biblebot.service     # Stop the service
systemctl --user restart biblebot.service  # Restart the service
systemctl --user status biblebot.service   # Check service status
```

### Command-line Options

```text
usage: biblebot [-h] [--config CONFIG] [--log-level {error,warning,info,debug}] [--generate-config] [--install-service] [--version]

options:
  -h, --help            show this help message and exit
  --config CONFIG       Path to config file (default: ~/.config/matrix-biblebot/config.yaml)
  --log-level {error,warning,info,debug}
                        Set logging level (default: info)
  --generate-config     Generate sample config files at the specified path
  --install-service     Install or update the systemd user service
  --version             show program's version number and exit
```

### Interacting with the Bot

1. **Invite the bot** to the rooms listed in your `config.yaml` file
2. **Send Bible verse references** in any of these formats:

| Format           | Example         | Description                        |
| ---------------- | --------------- | ---------------------------------- |
| Simple reference | `John 3:16`     | Single verse (uses KJV by default) |
| Range reference  | `1 Cor 15:1-4`  | Multiple verses                    |
| With translation | `John 3:16 esv` | Specify translation (KJV or ESV)   |

The bot will respond with the requested scripture passage and add a ✅ reaction to your message.

## Development

Contributions are welcome! Feel free to open issues or submit pull requests.
