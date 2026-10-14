# Matrix BibleBot

A Matrix bot that replies to Bible references such as `John 3:16` or
`Psalm 23`. KJV is the default; ESV requires an [ESV API key](https://api.esv.org/).
The bot responds when the whole message is a reference, supports encrypted
rooms with the optional E2EE extra, and can split long passages.

## Install and run

Python 3.12 or newer is required. Install an isolated application with pipx:

```bash
pipx install 'matrix-biblebot[e2e]'
biblebot config generate
```

Edit `~/.config/matrix-biblebot/config.yaml` and replace the sample room IDs
with your rooms. For encrypted rooms, set `matrix.e2ee.enabled: true`. Invite
the bot account, then authenticate, check the config, and start:

```bash
biblebot auth login
biblebot config check
biblebot
```

For unencrypted rooms, `pipx install matrix-biblebot` is sufficient. On
PowerShell, use double quotes around packages with extras. Upgrade with
`pipx upgrade matrix-biblebot`.

[uv](https://docs.astral.sh/uv/) also supports isolated application installs:

```bash
uv tool install 'matrix-biblebot[e2e]'
uv tool upgrade matrix-biblebot
```

Pip remains supported inside a virtual environment:

```bash
python -m pip install 'matrix-biblebot[e2e]'
```

### Docker

The repository includes Make and Compose workflows for the published
`ghcr.io/jeremiah-k/matrix-biblebot` image. From a clone:

```bash
make setup
# Edit ~/.config/matrix-biblebot/config.yaml.
make config-check
make auth-login
make run
make logs
```

The container runs without root and keeps config, credentials, encryption
keys, and logs under `/data`. `make use-source` and `make build` select a local
build. See [Docker deployment](docs/DOCKER.md) for host paths, ownership, and
upgrades.

### Develop from source

```bash
git clone https://github.com/jeremiah-k/matrix-biblebot.git
cd matrix-biblebot
uv sync --locked --extra test --extra e2e
uv run --locked --no-sync biblebot --version
uv run --locked --no-sync pytest
```

uv manages the checkout's `.venv` and installs dependencies from `uv.lock`.
See [Development](docs/DEVELOPMENT.md) for a separate runtime home, editors,
dependency updates, and package checks.

## References

| Message         | Result                       |
| --------------- | ---------------------------- |
| `John 3:16`     | One verse in KJV.            |
| `1 Cor 15:1-4`  | A verse range.               |
| `Psalm 23`      | A whole chapter.             |
| `John 3:16 esv` | ESV, using a configured key. |
| `jn 3:16`       | An abbreviated book name.    |

Embedded references (`I like John 3:16`), command prefixes, and mentions do
not trigger replies. Configure room IDs or aliases, translation defaults,
message splitting, and poetry formatting in the
[configuration guide](docs/CONFIGURATION.md).

## Commands

| Command                      | Purpose                                            |
| ---------------------------- | -------------------------------------------------- |
| `biblebot config generate`   | Create a sample configuration.                     |
| `biblebot config check`      | Check settings and dependency availability.        |
| `biblebot auth login`        | Save a Matrix session.                             |
| `biblebot auth status`       | Inspect authentication and E2EE readiness.         |
| `biblebot auth logout`       | Remove credentials and the encryption store.       |
| `biblebot auth cross-sign`   | Refresh a BibleBot-managed cross-signing identity. |
| `biblebot service install`   | Install or update a systemd user service on Linux. |
| `biblebot --log-level debug` | Start with debug logging.                          |

Global options go before the command: `biblebot --config /path/config.yaml config check`.
`--config` selects the YAML file. Set `BIBLEBOT_HOME` for every command when
you want to relocate credentials and encryption state together.

A systemd service can be managed with:

```bash
systemctl --user start biblebot.service
systemctl --user stop biblebot.service
systemctl --user status biblebot.service
```

The installer offers service enablement and lingering; startup at boot
depends on the choices made during installation.

## Encryption and cross-signing

Install the `e2e` extra, enable encryption in config, and use saved credentials
from `biblebot auth login`. Some Matrix clients withhold keys from unverified
devices; verify the bot device in those clients.

Cross-signing runs only through the explicit `auth cross-sign` command.
Back up the complete encryption store before running it or upgrading its
provider. The default store is `~/.local/state/matrix-biblebot/e2ee-store`;
`XDG_STATE_HOME` relocates it, and `BIBLEBOT_HOME` puts it at
`<BIBLEBOT_HOME>/e2ee-store`.

Without a local `_cross_signing.json` sidecar, the command refuses to bootstrap.
Only after confirming the account has no Element-managed cross-signing
identity, use `biblebot auth cross-sign --bootstrap`. Bootstrapping can replace
a server-side identity. Corrupt or ambiguous sidecars are refused, and the
prompted Matrix password is never saved.

The mindroom-nio provider migrates store schema version 2 to 10 on first open.
Back up the complete store first. `matrix-nio` and `mindroom-nio` both own the
`nio` import package; recreate environments when switching providers so they
are never co-installed.

## Documentation

- [Configuration](docs/CONFIGURATION.md): rooms, translations, encryption, and runtime paths.
- [Docker deployment](docs/DOCKER.md): prebuilt/source images and Compose.
- [Troubleshooting](docs/TROUBLESHOOTING.md): startup, delivery, and encryption failures.
- [Development](docs/DEVELOPMENT.md): uv setup and contribution workflow.
- [Testing](docs/dev/TESTING.md): client doubles, async behavior, and test limits.

Contributions are welcome through pull requests. See [LICENSE](LICENSE) for
the MIT license.
