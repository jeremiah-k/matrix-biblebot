# matrix-biblebot
BibleBot for Matrix

Simple bot that uses the [ESV API](https://api.esv.org/). (API key required)

More APIs and translations might be added later, but this is functional for now.

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
api_bible_key: your_api_bible_key_here
matrix_homeserver: https://your_homeserver_url_here
matrix_user: @your_bot_username:your_homeserver_domain
matrix_access_token: your_matrix_access_token_here
matrix_room_id: !your_room_id:your_homeserver_domain
```

Run the script:

```
python3 main.py
```

This is just to get the ball rolling for a BibleBot on Matrix. PRs are welcome so feel free to contribute!
