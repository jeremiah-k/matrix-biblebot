# Troubleshooting

Start with these commands, using the same `BIBLEBOT_HOME` or XDG settings as the
running bot:

```bash
biblebot --version
biblebot config check
biblebot auth status
```

`config check` validates local settings and reports configured API keys and
crypto dependency availability. It does not contact Matrix or verify an API key
with its provider. See [configuration](CONFIGURATION.md) for runtime paths and
[Docker](DOCKER.md) for container commands.

## Authentication

Run `biblebot auth login` for interactive login. Enter the homeserver URL when
prompted, followed by a full Matrix ID or a local username, then the password.
A local username uses the entered homeserver's domain.

The CLI accepts either interactive login with no parameters, or all three of
`--homeserver`, `--username`, and `--password`. Passing just a homeserver is an
error. Prefer the interactive prompt for manual use: command-line passwords can
appear in shell history and process listings.

If discovery fails, enter the full homeserver URL, including `https://`, in the
interactive prompt. Check its discovery endpoint:

```bash
curl https://example.com/.well-known/matrix/client
```

If the server rejects login, check the username and password in a Matrix client.
A server using SSO may require an authentication method this password login does
not support.

Login reports success only after credentials are saved. If persistence fails,
check free space and write permissions on the config directory. Failed atomic
replacement retains the previous credentials file. Logout reports failure if
local credentials or the encryption store cannot be removed; resolve the
permissions issue before retrying.

## The bot connects but does not reply

1. Run `biblebot config check` and verify the room IDs or aliases.
2. Invite the bot account to each configured room and check its permission to send.
3. Send a whole-message reference such as `John 3:16` from another account after
   startup. Messages sent before startup, the bot's own messages, and references
   embedded in conversation do not trigger replies.
4. Use `biblebot --log-level debug` to inspect room joining, alias resolution,
   decryption, and passage retrieval.

If an alias cannot be resolved, confirm it is published or use the room's internal
ID from the Matrix client's room settings. Resolved aliases use the canonical room
ID for both joining and accepting messages.

## Encryption

Install the encryption extra in the application's environment:

```bash
pipx install --force 'matrix-biblebot[e2e]'
# Alternative installer:
uv tool install --reinstall 'matrix-biblebot[e2e]'
```

For a source checkout, use the development guide's sync command. Docker includes
the extra. Encryption also needs `matrix.e2ee.enabled: true` and saved credentials
with a device ID from `biblebot auth login`; a legacy access token alone is
insufficient.

The supported provider is `mindroom-nio[e2e]` with `vodozemac`. Both `matrix-nio`
and `mindroom-nio` install `nio`; do not install them together. Recreate an
environment containing both providers, then install BibleBot with its extra.

Verify the bot device in a Matrix client. For an automated sender,
`OlmUnverifiedDeviceError` occurs in the sending client before encryption to an
unverified recipient. Keep that client alive for the round trip and verify the
bot in that session, or explicitly send with `ignore_unverified_devices=True`.
This setting retains encryption while accepting an unverified recipient.

The default store is `~/.local/state/matrix-biblebot/e2ee-store`, or
`<BIBLEBOT_HOME>/e2ee-store`. Back up the credentials and store together before
changing providers or resetting a device. `biblebot auth logout` deletes the
local store; use it as a last resort, then log in and verify the replacement
device. See the configuration guide for explicit cross-signing commands and
refusal checks.

If startup reports an unpublished migration, wait for any other bot process to
finish migrating. If the process was interrupted, preserve the named staging
and legacy directories and recover the complete store before restarting. Do
not delete staging or create an empty replacement store.

## Passage APIs and timeouts

KJV needs no API key. ESV needs a non-empty key in the config, `.env` beside the
config, or `ESV_API_KEY`. The config check reports a count of configured keys;
it does not test whether the ESV service accepts them.

Check provider connectivity without credentials:

```bash
curl 'https://bible-api.com/john%203:16?translation=kjv'
```

For ESV, obtain or check a key at [api.esv.org](https://api.esv.org/). Avoid
including the key in bug reports. Check DNS, outbound HTTPS, and server status
when requests time out. API timeouts are defined in the source constants;
there is no timeout setting in the YAML config.

Caching is enabled by default and can be disabled with `bot.cache_enabled:
false`. Cache capacity and expiry are source constants, not YAML options. Report
sustained memory growth with its duration and approximate message volume.

## systemd

```bash
systemctl --user status biblebot.service
journalctl --user -u biblebot.service --since '1 hour ago'
```

Install or refresh the unit with `biblebot service install` after setting the
runtime environment. The generated unit captures the executable, config path,
and resolved runtime directories. It does not capture arbitrary shell variables;
keep API keys in the configuration or its neighboring `.env`.

To debug manually, stop the service first, then start the CLI with the same
runtime environment:

```bash
systemctl --user stop biblebot.service
biblebot --log-level debug
```

## Report a problem

Include the BibleBot version, installation method, Python/platform details,
steps to reproduce, and relevant logs in a
[GitHub issue](https://github.com/jeremiah-k/matrix-biblebot/issues). Remove
passwords, access tokens, API keys, and private message contents. Review the
existing issues and check whether an available release addresses the problem.
