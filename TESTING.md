# Testing Guide

This guide covers testing patterns and best practices for the Matrix Bible Bot project.

## E2EE and External Dependency Mocking

### Problem: Real E2EE Dependencies in Tests

Matrix Bible Bot uses E2EE (End-to-End Encryption) libraries like `nio` and `olm` that require complex setup and can cause test failures or hanging when not properly mocked.

### Solution: Upfront Dependency Mocking

**✅ CORRECT PATTERN** - All E2EE dependencies are mocked upfront in `tests/conftest.py`:

```python
# Mock all E2EE dependencies before any imports can occur
nio_mock = MagicMock()
sys.modules["nio"] = nio_mock
sys.modules["nio.events"] = MagicMock()
sys.modules["nio.store"] = MagicMock()
sys.modules["nio.crypto"] = MagicMock()
sys.modules["nio.exceptions"] = nio_exceptions_mock

# Mock olm (E2EE crypto library)
olm_mock = MagicMock()
olm_mock.__spec__ = MagicMock()  # Required for importlib.util.find_spec
sys.modules["olm"] = olm_mock
```

**❌ INCORRECT PATTERN** - Don't mock E2EE dependencies inside individual tests:

```python
# ❌ DON'T DO THIS - mocking too late, real modules already imported
def test_something():
    with patch("nio.AsyncClient"):
        # Test code - real nio already imported by bot.main()
```

### Exception Class Mocking

E2EE libraries define custom exception classes that must inherit from `BaseException`:

```python
# ✅ CORRECT: Create proper Exception classes
class MockRemoteProtocolError(Exception):
    pass

class MockLocalProtocolError(Exception):
    pass

nio_exceptions_mock = MagicMock()
nio_exceptions_mock.RemoteProtocolError = MockRemoteProtocolError
nio_exceptions_mock.LocalProtocolError = MockLocalProtocolError
```

## Async Function Mocking Patterns

### Problem: RuntimeWarnings with AsyncMock

When testing functions that call async code, using `AsyncMock` incorrectly can lead to RuntimeWarnings about unawaited coroutines or hanging tests.

### Solution: Proper AsyncMock Usage

**✅ CORRECT PATTERN** - Mock async methods as AsyncMock, sync methods as MagicMock:

```python
@patch("biblebot.bot.AsyncClient")
def test_main_function(mock_client_class):
    mock_client = AsyncMock()
    # Async methods - use AsyncMock
    mock_client.sync_forever = AsyncMock()  # Prevent infinite loop
    mock_client.keys_upload = AsyncMock()
    mock_client.close = AsyncMock()
    mock_client.login = AsyncMock()
    mock_client.room_send = AsyncMock()

    # Sync methods/properties - use MagicMock
    mock_client.add_event_callback = MagicMock()
    mock_client.restore_login = MagicMock()
    mock_client.room_resolve_alias = MagicMock()
    mock_client.user_id = "test_user"
    mock_client.device_id = "test_device"
    mock_client.rooms = {}

    mock_client_class.return_value = mock_client

    # Test code that calls bot.main()
```

**❌ INCORRECT PATTERN** - Don't use AsyncMock for sync methods or MagicMock for async methods:

```python
# ❌ DON'T DO THIS - causes RuntimeWarnings about unawaited coroutines
mock_client.add_event_callback = AsyncMock()  # Should be MagicMock (sync method)

# ❌ DON'T DO THIS - causes hanging when async method called
mock_client.sync_forever = MagicMock()  # Should be AsyncMock (async method)
```

### Do not patch `asyncio.run`

When the CLI calls `asyncio.run(<async_entrypoint>(...))`, avoid patching `asyncio.run`.
Instead, monkeypatch the async entrypoint the CLI actually calls (e.g., `biblebot.cli.bot_main`) to a no-op async function:

```python
async def _noop_async(*_a, **_k):
    return 0

def test_main_run_bot(monkeypatch):
    monkeypatch.setattr("biblebot.cli.bot_main", _noop_async)  # target used by the CLI
    from biblebot.cli import main
    main(["run"])
```

If you must intercept `asyncio.run`, ensure your stub awaits the coroutine:

```python
def _fake_run(coro, *a, **k):
    import asyncio
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()
```

#### Quick checklist (prevents "AsyncMockMixin.\_execute_mock_call was never awaited")

1. **Do not patch `asyncio.run`** in CLI tests; patch the coroutine the CLI invokes.
2. **Only AsyncMock true async defs**; use MagicMock for sync methods:
   - **nio.AsyncClient sync methods**: `add_event_callback`, `restore_login`, `room_resolve_alias` (returns response), attribute access like `rooms`, `user_id`, `device_id`.
   - **nio.AsyncClient async methods**: `login`, `logout`, `close`, `sync`, `sync_forever`, `join`, `keys_upload`, `room_send`, `to_device`, `request_room_key`.
3. **If a test still needs to intercept the loop runner**, your stub must actually await the coro (see `_fake_run` above).

- CLI tests: Don't patch `asyncio.run` in tests like `test_main_run_bot`; patch the async entrypoint invoked by the CLI instead (see "Do not patch asyncio.run").

### Matrix Client Mocking Pattern

For Matrix client operations, use this standard pattern:

```python
mock_client = AsyncMock()

# Sync methods/properties - use MagicMock
mock_client.restore_login = MagicMock()
mock_client.add_event_callback = MagicMock()
mock_client.room_resolve_alias = MagicMock()
mock_client.user_id = "test_user"
mock_client.device_id = "test_device"
mock_client.access_token = "test_token"
mock_client.rooms = {}
mock_client.should_upload_keys = True

# Async methods - use AsyncMock
mock_client.sync_forever = AsyncMock()  # Prevents hanging
mock_client.keys_upload = AsyncMock()
mock_client.close = AsyncMock()
mock_client.room_send = AsyncMock()
mock_client.join = AsyncMock()
mock_client.sync = AsyncMock()
```

## Test Organization

### Test File Structure

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

class TestBibleBot:
    """Test Bible Bot functionality."""

    @pytest.mark.asyncio
    async def test_specific_behavior(self, sample_config):
        """Test specific behavior with descriptive name."""
        # E2EE dependencies are mocked upfront in conftest.py
        with patch("biblebot.bot.AsyncClient") as mock_client_class:
            # Arrange
            mock_client = AsyncMock(spec=["required", "methods"])
            mock_client_class.return_value = mock_client

            # Act
            result = await some_async_function()

            # Assert
            assert result == expected_value
```

### Resource Cleanup

The project uses comprehensive cleanup fixtures in `tests/conftest.py`:

- `event_loop_safety`: Create a dedicated event loop per test
- `mock_asyncmock_coroutines`: Ensure AsyncMock coroutines are awaited
- `cleanup_asyncmock_objects`: Force GC to finalize AsyncMock objects
- `comprehensive_cleanup`: Perform aggressive cleanup for CI environments

## Bible API Testing Patterns

### Scripture Retrieval Mocking

```python
@patch("biblebot.bible_api.get_scripture")
def test_scripture_handling(mock_get_scripture):
    mock_get_scripture.return_value = {
        "text": "Test verse content",
        "reference": "Test 1:1",
        "translation": "kjv"
    }

    # Test scripture handling logic
```

### HTTP Request Mocking

```python
@patch("requests.get")
def test_api_request(mock_get):
    mock_response = MagicMock()
    mock_response.json.return_value = {"verses": [{"text": "Test"}]}
    mock_response.status_code = 200
    mock_get.return_value = mock_response

    # Test API interaction
```

## Configuration Testing

### Sample Configuration Fixture

```python
@pytest.fixture
def sample_config():
    """Provide sample configuration for tests."""
    return {
        "matrix": {
            "homeserver": "https://matrix.org",
            "room_ids": ["!test:matrix.org"],
            "e2ee": {"enabled": False}
        },
        "bible_api": {
            "default_translation": "kjv"
        }
    }
```

### Environment Variable Testing

```python
@patch.dict(os.environ, {"MATRIX_ACCESS_TOKEN": "test_token"})
def test_environment_loading():
    # Test environment-dependent code
    pass
```

## Best Practices

### 1. Treat Warnings as Errors

**⚠️ CRITICAL**: All test warnings must be eliminated, not ignored.

- **RuntimeWarnings about unawaited coroutines**: Fix by using proper AsyncMock patterns
- **ResourceWarnings about unclosed resources**: Fix with proper cleanup fixtures
- **ImportWarnings about missing E2EE dependencies**: Fix with upfront mocking

### 2. Test Isolation

- Each test should be independent
- Use fixtures for common setup
- Don't rely on test execution order

### 3. Descriptive Test Names

```python
def test_on_room_message_bible_reference():
    """Test handling room message with Bible reference."""

def test_main_with_credentials_e2ee_enabled():
    """Test main function with session-based credentials and E2EE."""
```

### 4. Mock at the Right Level

- Mock external dependencies (Matrix API, Bible API)
- Don't mock internal business logic
- Mock at system boundaries

### 5. Test Error Conditions

```python
@patch("biblebot.bible_api.get_scripture")
def test_scripture_api_failure(mock_get_scripture):
    mock_get_scripture.side_effect = requests.RequestException("API Error")

    # Test error handling
    with pytest.raises(BibleAPIError):
        await handle_scripture_request("John 3:16")
```

## Common Patterns

### Matrix Room Event Testing

```python
def test_on_room_message():
    mock_room = MagicMock()
    mock_room.room_id = "!test:matrix.org"

    mock_event = MagicMock()
    mock_event.sender = "@user:matrix.org"
    mock_event.body = "John 3:16"
    mock_event.server_timestamp = 1234567890000

    # Test message handling
```

### Bible Reference Parsing

```python
def test_bible_reference_detection():
    test_cases = [
        ("John 3:16", True),
        ("Genesis 1:1-3", True),
        ("Not a reference", False),
    ]

    for text, expected in test_cases:
        result = contains_bible_reference(text)
        assert result == expected
```

## Troubleshooting

### Test Hanging Issues

If tests hang indefinitely:

1. **Check AsyncMock usage**: Ensure `sync_forever` is mocked as AsyncMock
2. **Verify upfront mocking**: Ensure E2EE dependencies are mocked in conftest.py
3. **Check event loop cleanup**: Verify cleanup fixtures are working

### Import Errors

If tests fail with import errors:

1. **Check sys.path setup**: Ensure src/ is on the Python path
2. **Verify mock timing**: Ensure mocks are applied before imports
3. **Check module specs**: Ensure `__spec__` is set for mocked modules

### Memory Issues

For memory-intensive tests:

```python
@pytest.mark.skip(reason="Memory intensive - run separately")
def test_memory_scaling():
    # Large-scale testing
    pass
```

## Running Tests

### Basic Test Execution

```bash
# Run all tests
python -m pytest tests/ -v

# Run specific test file
python -m pytest tests/test_bot.py -v

# Run specific test class
python -m pytest tests/test_bot.py::TestMainFunction -v

# Run with coverage
python -m pytest tests/ -v --cov=src/biblebot --cov-report=html
```

### CI/CD Considerations

```bash
# Run with timeout to prevent hanging
timeout 300 python -m pytest tests/ -v --tb=short

# Run with strict warnings
python -m pytest tests/ -v -W error
```

## References

- [pytest documentation](https://docs.pytest.org/)
- [unittest.mock documentation](https://docs.python.org/3/library/unittest.mock.html)
- [AsyncMock best practices](https://docs.python.org/3/library/unittest.mock.html#unittest.mock.AsyncMock)
- [Matrix Python SDK (nio) documentation](https://matrix-nio.readthedocs.io/)
