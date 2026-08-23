# Docker deployment

The container stores all runtime state under `/data` through
`BIBLEBOT_HOME=/data`:

- `config.yaml`
- `credentials.json`
- `e2ee-store/`

The image runs as UID/GID `1000:1000` by default. The Compose sample maps the
container process to the current host user when invoked through the Makefile.

## Prebuilt image

```bash
make setup
```

This creates `docker-compose.yaml`, copies the packaged configuration template
to `~/.config/matrix-biblebot/config.yaml`, and uses
`ghcr.io/jeremiah-k/matrix-biblebot:latest`.

Edit the room IDs, then authenticate and start the bot:

```bash
make config-check
make auth-login
make run
make logs
```

Choose another host runtime directory without changing the container layout:

```bash
make setup BIBLEBOT_HOST_HOME=/srv/matrix-biblebot
make auth-login BIBLEBOT_HOST_HOME=/srv/matrix-biblebot
make run BIBLEBOT_HOST_HOME=/srv/matrix-biblebot
```

The directory must exist and be writable by the selected host UID/GID.

## Build from source

```bash
make use-source
make build
make run
```

`docker-compose.source.yaml` overrides only the image build. Configuration and
state use the same host runtime directory as the prebuilt flow. Run
`make use-prebuilt` to remove the source override.

## Direct Compose use

Set all host-side values explicitly. `BIBLEBOT_HOST_HOME` must be an absolute
path.

```bash
export BIBLEBOT_HOST_HOME="$HOME/.config/matrix-biblebot"
export UID="$(id -u)"
export GID="$(id -g)"
cp sample-docker-compose.yaml docker-compose.yaml
docker compose run --rm biblebot biblebot config generate
docker compose run --rm biblebot biblebot auth login
docker compose up -d
```

For a local source build, include the override:

```bash
docker compose \
  -f docker-compose.yaml \
  -f sample-docker-compose.source.yaml \
  build
```

## Image behavior

- Installs `mindroom-nio[e2e]` and verifies the `vodozemac` backend in CI.
- Runs without root privileges or runtime package-manager dependencies.
- Supports `linux/amd64` and `linux/arm64`.
- Does not publish a synthetic healthcheck. `biblebot --version` only verifies
  the executable and is used as a build smoke test, not as bot readiness.
- Publishes `latest` and the package version only for a matching GitHub release.
  Manual workflow runs receive development SHA tags.

Back up the entire runtime directory before dependency upgrades that migrate
the E2EE store. Do not mount credentials or the E2EE store read-only.
