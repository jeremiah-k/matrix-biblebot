# Matrix BibleBot Modernization Progress

## Current Status

- **Branch**: `modernize-bot`
- **Latest Commit**: `5250ce7` - "fix: Address Gemini code review feedback"
- **PR**: #8 (open) - Substantial modernization with E2EE support

## ✅ COMPLETED WORK

### Phase 1: Critical Fixes (COMPLETED)

- [x] E2EE store cleanup with shutil.rmtree()
- [x] Dead code removal (on_decryption_failure function)
- [x] ESV API return tuple consistency fix
- [x] Request timeouts (10s API, 30s login)
- [x] Config directory permissions (0700)
- [x] Python version consistency (3.9+)
- [x] Exception handling improvements

### Phase 2: CLI Modernization (COMPLETED)

- [x] Modern grouped commands (`biblebot auth login`, `biblebot config validate`)
- [x] Legacy flag support with deprecation warnings
- [x] Enhanced help and documentation
- [x] E2EE status detection (`biblebot auth status`)

### Phase 3: Gemini Review Fixes (COMPLETED)

- [x] Fixed missing validate_config function (use load_config)
- [x] Added comment for broad exception handling
- [x] Pinned python-olm version (>=3.2.15)
- [x] Fixed cache clearing in tests (\_passage_cache)
- [x] Removed temporary.md file

## 🔄 NEW ISSUES FROM LATEST REVIEW

### HIGH PRIORITY (Must Fix)

1. **User ID Assignment Logic** - Improve error handling when setting user_id from config
2. **Load Credentials Error Handling** - Use specific exceptions and proper encoding
3. **E2EE Client Initialization** - Use store_path parameter correctly in AsyncClient
4. **E2EE Status Logic** - Fix availability detection to require deps + creds + store

### MEDIUM PRIORITY (Should Fix)

5. **Requirements Structure** - Prefer package extras over separate requirements-e2e.txt
6. **Store Directory Permissions** - Add 0700 permissions to E2EE store directory
7. **URL Encoding** - Add proper URL encoding for Bible API requests
8. **Import Organization** - Add missing imports (urllib.parse.quote, load_credentials)

### LOW PRIORITY (Nice to Have)

9. **API URL Template** - Use template for KJV API URL construction
10. **Code Organization** - Minor import and structure improvements

## 🎯 NEXT IMPLEMENTATION TASKS

### Task 1: Fix User ID Assignment

```python
# Current problematic code:
try:
    bot.client.user_id = config["matrix_user"]
except Exception as e:
    logger.warning(f"Could not set user_id from config: {e}")
```

### Task 2: Improve Load Credentials

```python
# Need to add proper encoding and specific exceptions:
def load_credentials() -> Optional[Credentials]:
    path = credentials_path()
    if not path.exists():
        return None
    try:
        text = path.read_text(encoding="utf-8")
        data = json.loads(text)
        return Credentials.from_dict(data)
    except (OSError, json.JSONDecodeError):
        logger.exception(f"Failed to read credentials from {path}")
        return None
```

### Task 3: Fix E2EE Client Initialization

```python
# Need to use store_path parameter correctly:
client_kwargs = {}
if e2ee_available:
    client_kwargs["store_path"] = str(get_store_dir())
client = AsyncClient(
    hs,
    user,
    config=AsyncClientConfig(store_sync_tokens=True, encryption_enabled=e2ee_available),
    **client_kwargs,
)
```

### Task 4: Fix E2EE Status Detection

```python
# More accurate availability detection:
status["available"] = bool(
    status["dependencies_installed"]
    and creds
    and status["store_exists"]
)
```

### Task 5: Add Store Directory Permissions

```python
def get_store_dir() -> Path:
    E2EE_STORE_DIR.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(E2EE_STORE_DIR, 0o700)
    except Exception:
        logger.debug("Could not set E2EE store perms to 0700")
    return E2EE_STORE_DIR
```

### Task 6: Consider Package Extras

```python
# In setup.cfg, prefer:
# pip install ".[e2e]"
# Over separate requirements-e2e.txt
```

## 📋 FILES TO MODIFY

### High Priority

- `src/biblebot/bot.py` - User ID assignment, E2EE client init, URL encoding
- `src/biblebot/auth.py` - Load credentials improvements, store permissions
- `src/biblebot/cli.py` - Import load_credentials

### Medium Priority

- `setup.cfg` - Consider package extras approach
- `requirements-e2e.txt` - Update or potentially remove

## 🧪 TESTING REQUIREMENTS

- [ ] All tests must pass
- [ ] CLI commands functional
- [ ] E2EE status detection accurate
- [ ] Proper error handling validation

## 📝 NOTES

- Focus on high-priority fixes first
- Maintain backward compatibility
- Test thoroughly after each change
- Keep calling interactive feedback for guidance

## SUCCESS CRITERIA

- [ ] All review comments addressed
- [ ] E2EE working correctly with proper client initialization
- [ ] Robust error handling throughout
- [ ] Clean, maintainable code structure
- [ ] All tests passing
- [ ] Ready for final review and merge
