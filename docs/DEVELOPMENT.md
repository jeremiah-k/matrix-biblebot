# Development Guide

Guide for contributing to Matrix BibleBot development.

## Quick Start

1. **Clone the repository:**

   ```bash
   git clone https://github.com/jeremiah-k/matrix-biblebot.git
   cd matrix-biblebot
   ```

2. **Set up development environment:**

   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/macOS
   # or
   venv\Scripts\activate     # Windows
   ```

3. **Install in development mode:**

   ```bash
   pip install -e '.[e2e,test]'
   # Windows PowerShell: pip install -e ".[e2e,test]"
   ```

4. **Run tests:**
   ```bash
   pytest
   ```

## Project Structure

```text
matrix-biblebot/
├── src/biblebot/           # Main package
│   ├── __init__.py
│   ├── __main__.py         # Entry point for python -m biblebot
│   ├── bot.py              # Core bot implementation
│   ├── cli.py              # Command-line interface
│   ├── auth.py             # Authentication helpers
│   ├── constants/          # Configuration constants
│   │   ├── api.py          # API-related constants
│   │   ├── bible.py        # Bible reference patterns
│   │   ├── config.py       # Configuration keys
│   │   ├── matrix.py       # Matrix-specific constants
│   │   └── messages.py     # User-facing messages
│   └── tools/              # Additional tools
│       ├── sample_config.yaml
│       └── biblebot.service
├── tests/                  # Test suite
├── docs/                   # Documentation
├── main.py                 # Legacy entry point
├── setup.py                # Package configuration
├── pyproject.toml          # Build configuration
└── requirements*.txt       # Dependencies
```

## Core Components

### Bot Class (`src/biblebot/bot.py`)

The main `BibleBot` class handles:

- Matrix event processing
- Bible verse fetching from APIs
- Message formatting and splitting
- Rate limiting and error handling
- E2EE support

Key methods:

- `start()` - Initialize and start the bot
- `handle_message()` - Process incoming messages
- `handle_scripture_command()` - Fetch and send Bible verses
- `_fetch_passage()` - API interaction logic

### CLI Interface (`src/biblebot/cli.py`)

Provides command-line interface with subcommands:

- `config generate/check` - Configuration management
- `auth login/logout/status` - Authentication
- `service install` - Systemd service setup

### Authentication (`src/biblebot/auth.py`)

Handles Matrix authentication:

- Modern credential-based auth with E2EE support
- Legacy access token fallback
- Secure credential storage
- Device management

### Constants (`src/biblebot/constants/`)

Organized constants for:

- Bible reference regex patterns and book abbreviations
- API URLs and parameters
- Configuration keys and defaults
- User-facing messages and error text

## Development Workflow

### Setting Up Your Environment

1. **Fork the repository** on GitHub

2. **Clone your fork:**

   ```bash
   git clone https://github.com/YOUR_USERNAME/matrix-biblebot.git
   cd matrix-biblebot
   ```

3. **Add upstream remote:**

   ```bash
   git remote add upstream https://github.com/jeremiah-k/matrix-biblebot.git
   ```

4. **Create development environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate
   pip install -e '.[e2e,test]'
   ```

### Making Changes

1. **Create a feature branch:**

   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes** following the coding standards

3. **Run tests:**

   ```bash
   pytest
   pytest --cov=biblebot  # With coverage
   ```

4. **Run linting:**
   This project uses [Trunk](https://trunk.io) for linting and formatting. After installing Trunk, run:

   ```bash
   trunk check --fix --all
   ```

5. **Test manually:**
   ```bash
   biblebot auth login
   biblebot --log-level debug
   ```

### Testing

#### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=biblebot --cov-report=html

# Run specific test file
pytest tests/test_bot.py

# Run with verbose output
pytest -v

# Run integration tests (requires Matrix credentials; if present)
pytest tests/test_integration.py
```

#### Test Structure

- **Unit tests:** Test individual functions and classes
- **Integration tests:** Test bot interaction with Matrix
- **E2E tests:** Test complete workflows
- **Performance tests:** Test rate limiting and caching

#### Writing Tests

Example test structure:

```python
import pytest
from unittest.mock import AsyncMock, patch
from biblebot.bot import BibleBot

@pytest.mark.asyncio
async def test_bible_reference_parsing():
    """Test that Bible references are parsed correctly."""
    bot = BibleBot(config={})

    # Test valid reference
    result = bot._parse_reference("John 3:16")
    assert result == ("John", "3:16", None)

    # Test with translation
    result = bot._parse_reference("John 3:16 esv")
    assert result == ("John", "3:16", "esv")
```

#### Test Configuration

Tests use configuration from `tests/conftest.py`:

- Mock Matrix clients
- Test credentials and rooms
- Fixture setup and teardown

### Code Style

#### Python Style

- **PEP 8** compliance
- **Type hints** for function signatures
- **Docstrings** for all public functions
- **f-strings** for string formatting

#### Code Organization

- **Constants** in appropriate `constants/` modules
- **Error handling** with specific exception types
- **Logging** with appropriate levels
- **Async/await** for all I/O operations

#### Example Function

```python
async def fetch_bible_verse(
    self,
    book: str,
    reference: str,
    translation: str = "kjv"
) -> tuple[str, str]:
    """
    Fetch a Bible verse from the appropriate API.

    Args:
        book: Bible book name (e.g., "John")
        reference: Chapter and verse (e.g., "3:16")
        translation: Translation code ("kjv" or "esv")

    Returns:
        Tuple of (verse_text, formatted_reference)

    Raises:
        APIError: If the API request fails
        ValueError: If the reference is invalid
    """
    logger.info(f"Fetching {book} {reference} ({translation})")

    try:
        if translation == "esv":
            return await self._fetch_esv_verse(book, reference)
        else:
            return await self._fetch_kjv_verse(book, reference)
    except Exception as e:
        logger.error(f"Failed to fetch verse: {e}")
        raise APIError(f"Could not fetch {book} {reference}") from e
```

### Documentation

#### Docstring Style

Use Google-style docstrings:

```python
def parse_bible_reference(text: str) -> tuple[str, str, str | None]:
    """
    Parse a Bible reference from text.

    Args:
        text: Input text containing Bible reference

    Returns:
        Tuple of (book, reference, translation) where translation
        may be None if not specified

    Raises:
        ValueError: If the reference format is invalid

    Examples:
        >>> parse_bible_reference("John 3:16")
        ("John", "3:16", None)
        >>> parse_bible_reference("1 Cor 15:1-4 esv")
        ("1 Corinthians", "15:1-4", "esv")
    """
```

#### Adding Documentation

- Update relevant `.md` files in `docs/`
- Add examples for new features
- Update configuration options
- Include troubleshooting for new functionality

### Adding Features

#### New Bible Translation

1. **Add translation constant:**

   ```python
   # src/biblebot/constants/bible.py
   TRANSLATION_NIV = "niv"
   SUPPORTED_TRANSLATIONS = ("kjv", "esv", "niv")
   ```

2. **Add API implementation:**

   ```python
   # src/biblebot/bot.py
   async def _fetch_niv_verse(self, book: str, reference: str) -> tuple[str, str]:
       # Implementation here
   ```

3. **Update configuration:**

   ```yaml
   # src/biblebot/tools/sample_config.yaml
   bot:
     default_translation: kjv # Options: kjv, esv, niv
   ```

4. **Add tests:**
   ```python
   # tests/test_translations.py
   def test_niv_translation():
       # Test NIV-specific functionality
   ```

#### New CLI Command

1. **Add command constants:**

   ```python
   # src/biblebot/constants/messages.py
   CMD_NEWCOMMAND = "newcommand"
   ```

2. **Add parser configuration:**

   ```python
   # src/biblebot/cli.py
   def create_parser():
       # Add new subparser
   ```

3. **Implement command handler:**
   ```python
   # src/biblebot/cli.py
   async def handle_newcommand(args):
       # Implementation here
   ```

### Release Process

#### Version Management

Versions are managed in `src/biblebot/__init__.py`:

```python
__version__ = "1.2.3"
```

#### Creating a Release

1. **Update version number**
2. **Update CHANGELOG.md**
3. **Run full test suite**
4. **Create release commit:**
   ```bash
   git commit -m "Release v1.2.3"
   git tag v1.2.3
   ```
5. **Push to GitHub:**
   ```bash
   git push origin main --tags
   ```

#### Automated Releases

GitHub Actions automatically:

- Run tests on pull requests
- Build and publish to PyPI on tagged releases
- Generate release notes

## Contributing Guidelines

### Pull Request Process

1. **Fork and clone** the repository
2. **Create feature branch** from `main`
3. **Make changes** with tests
4. **Run test suite** and linting
5. **Update documentation** if needed
6. **Submit pull request** with clear description

### Pull Request Template

```markdown
## Description

Brief description of changes

## Type of Change

- [ ] Bug fix
- [ ] New feature
- [ ] Documentation update
- [ ] Refactoring

## Testing

- [ ] Tests pass locally
- [ ] Added tests for new functionality
- [ ] Manual testing completed

## Checklist

- [ ] Code follows style guidelines
- [ ] Self-review completed
- [ ] Documentation updated
- [ ] No breaking changes (or clearly documented)
```

### Code Review

All changes require review:

- **Functionality** - Does it work as intended?
- **Tests** - Are there adequate tests?
- **Style** - Follows project conventions?
- **Documentation** - Is it clear and complete?
- **Performance** - Any performance implications?

### Issue Reporting

When reporting bugs:

1. **Search existing issues** first
2. **Use issue templates** when available
3. **Provide reproduction steps**
4. **Include system information**
5. **Add relevant logs** (with sensitive data removed)

### Feature Requests

For new features:

1. **Check if already requested**
2. **Describe the use case**
3. **Propose implementation approach**
4. **Consider backwards compatibility**

## Getting Help

- **GitHub Discussions** for questions
- **GitHub Issues** for bugs and features
- **Code comments** for implementation details
- **Documentation** for usage and configuration

## License

This project is licensed under the MIT License. By contributing, you agree that your contributions will be licensed under the same license.
