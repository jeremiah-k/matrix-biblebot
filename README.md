# matrix-biblebot
BibleBot for Matrix

Simple bot that will fetch Bible verse using APIs from [bible-api.com](https://www.bible-api.com) & [esv.org](https://api.esv.org/)

## Supported Translations:
Supported Translations:
King James Version (KJV)
English Standard Version (ESV) - requires an API key

## Installation

Clone the repository:

```
git clone https://github.com/jeremiah-k/matrix-biblebot.git
```

### Setup

Create a Python virtual environment in the project directory:

```
python3 -m venv .pyenv
```

Activate the virtual environment and install dependencies:

```
source .pyenv/bin/activate
pip install -r requirements.txt
```

Copy the sample_config.yaml to config.yaml and enter your values:

```
api_bible_key: "your_api_bible_key_here"
matrix_homeserver: "https://your_homeserver_url_here"
matrix_user: "@your_bot_username:your_homeserver_domain"
matrix_access_token: "your_matrix_access_token_here"
matrix_room_ids:
  - "!your_room_id:your_homeserver_domain"
  - "!your_other_room_id:your_homeserver_domain"
```

Run the script:

```
python3 main.py
```

## Usage
Invite the bot to rooms that are listed in the config.yaml file, if they are not joined already. The bot will respond to messages that start with `Book Chapter:Verse-(range)` (e.g. `John 3:16` or `1 Cor 15:1-4`). To search using ESV, use `esv` at the end of the string. (e.g. `John 3:16 esv`))

This is just to get the ball rolling for a BibleBot on Matrix. PRs are welcome so feel free to contribute!
