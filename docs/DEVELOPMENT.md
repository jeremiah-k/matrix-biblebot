# Development

Python 3.12–3.14 is supported. Development uses [uv](https://docs.astral.sh/uv/),
which manages Python environments and installs dependencies from `uv.lock`.
The package remains installable with pip and pipx.

## Start here

Install uv using its [installation guide](https://docs.astral.sh/uv/getting-started/installation/), then:

```bash
git clone https://github.com/jeremiah-k/matrix-biblebot.git
cd matrix-biblebot
uv sync --locked --extra test --extra e2e
uv run --locked --no-sync biblebot --version
uv run --locked --no-sync pytest
```

`uv sync` creates `.venv`, installs the project in editable mode, and installs
the development tools. The `test` extra adds pytest and coverage; `e2e` adds the
crypto backend. `.python-version` selects Python 3.12 by default. To use another
supported interpreter, add `--python 3.14` to the sync command.

Select `.venv/bin/python` in your editor (`.venv\Scripts\python.exe` on Windows).
Environment activation is optional: `uv run` selects it for you. `--locked`
fails if package metadata and the lock disagree. `--no-sync` runs in the
prepared environment without changing which extras are installed.

## Daily commands

```bash
uv run --locked --no-sync pytest tests/test_messaging.py -q
uv run --locked --no-sync pytest --no-cov
uv run --locked --no-sync ruff check --config .trunk/configs/ruff.toml src tests
uv build
uv run --locked --no-sync twine check dist/*
```

Coverage is enabled by default in `pytest.ini`. Tests treat warnings as errors.
Read the [testing guide](dev/TESTING.md) before changing Matrix interactions.

Trunk runs the repository's full lint and format configuration, including
Markdown, YAML, Docker, Python, and workflow checks:

```bash
.trunk/trunk check
.trunk/trunk fmt
```

## Change dependencies

Runtime dependencies and public extras live in `pyproject.toml`. Build and
lint tools live in its `dev` dependency group. `uv.lock` records the resolved
versions; commit metadata and lock changes together.

```bash
uv add 'package-name==1.2.3'           # Runtime dependency
uv add --group dev package-name       # Development tool
uv lock                              # Reconcile an edited pyproject.toml
uv lock --upgrade-package package-name
uv sync --locked --extra test --extra e2e
```

A lock upgrade respects constraints in `pyproject.toml`. For a pinned runtime
dependency, change its pin before expecting `--upgrade-package` to select a
different version. Avoid mixing `pip install` into a uv-managed environment:
the next exact sync removes packages that are absent from the lock.

## Run a development instance

Use a separate runtime home so experiments have their own configuration,
credentials, logs, and encryption store:

```bash
export BIBLEBOT_HOME="$PWD/.dev-runtime"
uv run --locked --no-sync biblebot config generate
# Edit .dev-runtime/config.yaml and invite the bot account to its rooms.
uv run --locked --no-sync biblebot auth login
uv run --locked --no-sync biblebot config check
uv run --locked --no-sync biblebot
```

On PowerShell, set `$env:BIBLEBOT_HOME = "$PWD/.dev-runtime"`. The same home
must be set for authentication and startup. `--config` changes only the YAML
path; it does not relocate credentials or encryption keys.

For containers, follow the [Docker guide](DOCKER.md). Test a source build with
`make use-source` followed by `make build`; `make run` starts the deployment.

## Package compatibility

A pip environment remains supported:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
# PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -e '.[e2e,test]'
python -m pytest
```

Use a separate environment when switching installers. On Windows, use a
supported `python` or `py -3.12` command to create it.

For an installed application, use `pipx install 'matrix-biblebot[e2e]'` or
`uv tool install 'matrix-biblebot[e2e]'`. `uv tool` installs an isolated
application; `uv sync` prepares a source checkout for development.

CI runs the locked suite on Python 3.12, 3.13, and 3.14, plus pip compatibility
jobs on 3.12 and 3.14. It builds the sdist and wheel, checks distribution
metadata, and installs the wheel with pipx outside the checkout. Docker CI
builds amd64/arm64 images and checks entry points, crypto availability, non-root
execution, and mounted configuration generation.

## Code map

| Module                               | Responsibility                                                |
| ------------------------------------ | ------------------------------------------------------------- |
| `cli.py`                             | CLI parsing, setup guidance, command dispatch.                |
| `config.py`, `paths.py`              | Config diagnostics and authoritative runtime paths.           |
| `bot.py`, `protocols.py`, `rooms.py` | Matrix lifecycle, client contract, room handling.             |
| `passages.py`                        | Translation lookup, HTTP requests, LRU/TTL cache.             |
| `triggers.py`, `validation.py`       | Whole-message reference detection and book normalization.     |
| `formatting.py`, `messaging.py`      | Rendering, message sizing, send failures and retries.         |
| `auth.py`                            | Credential persistence, login/logout, explicit cross-signing. |
| `service.py`, `setup_utils.py`       | systemd unit rendering and installation.                      |
| `log_utils.py`, `update_check.py`    | Logging and non-fatal release checks.                         |
| `tools/`                             | Packaged sample configuration and service template.           |

When behavior changes, add focused regressions and update the relevant user
guide in the same commit. Keep commits focused on one behavior or tooling
concern, then open a PR against `main`.
