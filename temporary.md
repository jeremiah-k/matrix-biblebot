# Matrix BibleBot Refactor Progress

## Overview

This is a temporary tracking file for the substantial refactor of matrix-biblebot. We're modernizing the bot with E2EE support, enhanced authentication, and improved parsing based on patterns from the mmrelay project.

## Current State

- **Branch**: `modernize-bot`
- **PR**: #8 (open)
- **Base Commits**:
  - `2be3527` - "Codex so far" (initial refactor)
  - `0ec08d0` - "feat: Modernize BibleBot..." (E2EE + enhancements)

## Reference Materials from mmrelay

- ✅ E2EE Implementation Notes: <https://raw.githubusercontent.com/jeremiah-k/meshtastic-matrix-relay/refs/heads/main/docs/dev/E2EE_IMPLEMENTATION_NOTES.md>
- ✅ Matrix Utils: <https://raw.githubusercontent.com/jeremiah-k/meshtastic-matrix-relay/refs/heads/main/src/mmrelay/matrix_utils.py>
- ✅ CLI: <https://raw.githubusercontent.com/jeremiah-k/meshtastic-matrix-relay/refs/heads/main/src/mmrelay/cli.py>
- ✅ E2EE Guide: <https://raw.githubusercontent.com/jeremiah-k/meshtastic-matrix-relay/refs/heads/main/docs/E2EE.md>

## Critical Issues from PR Reviews

### HIGH PRIORITY (Must Fix)

1. **E2EE Store Cleanup** - Replace complex manual directory traversal with `shutil.rmtree()`
2. **Dead Code Removal** - Remove unused `on_decryption_failure` function at end of bot.py
3. **Exception Handling** - Replace broad `Exception` catches with specific exceptions
4. **ESV API Return Fix** - Fix IndexError and inconsistent tuple shape in ESV text retrieval

### MEDIUM PRIORITY (Should Fix)

5. **Python Version Discrepancy** - Docs say 3.9+, setup.cfg says 3.8+ (need consistency)
6. **PyPI OIDC Setup** - Missing Trusted Publisher configuration for release workflow
7. **Request Timeouts** - Add timeouts to prevent hanging on network requests
8. **Config Directory Permissions** - Harden to 0700 for security
9. **Login Timeout** - Add timeout to Matrix login to prevent indefinite hang

### CODE QUALITY (Nice to Have)

10. **Silent Exception Handling** - Log exceptions instead of silent try/except/pass
11. **User ID Assignment** - Simplify conditional assignment instead of try/except
12. **Decryption Callback Registration** - Use conditional instead of try/except/pass
13. **Request Caching** - Clear cache in tests to prevent cross-test issues

## Key Patterns to Apply from mmrelay

### 1. E2EE Implementation (Critical)

- **Correct Client Initialization**: Use store_path in constructor, restore_login() loads store implicitly
- **Initial Sync with Full State**: `sync(full_state=True)` required to identify encrypted rooms
- **Dual Callback System**: Separate callbacks for decrypted messages and decryption failures
- **Automatic Key Requesting**: Use `event.as_key_request()` and `client.to_device()`
- **HTML Message Formatting**: Always include `formatted_body` to prevent nio validation errors

### 2. Authentication System

- **Interactive Login Flow**: Robust `--auth-login` with confirmation for existing sessions
- **Credentials Management**: Secure storage in `~/.config/matrix-biblebot/credentials.json`
- **Session Restoration**: Prefer credentials.json over environment tokens
- **Device ID Persistence**: Maintain consistent device identity

### 3. Configuration Management

- **Unified E2EE Status**: Centralized status detection and reporting
- **Platform Checks**: Windows E2EE limitation handling
- **Dependency Validation**: Check for python-olm and nio components
- **Config Validation**: Comprehensive validation with helpful error messages

### 4. CLI Modernization

- **Grouped Subcommands**: Modern CLI with config/auth/service groups
- **Legacy Flag Support**: Backward compatibility with deprecation warnings
- **Non-interactive Mode**: Support for automated environments
- **Comprehensive Help**: Clear documentation and examples

## Implementation Tasks

### Phase 1: Critical Fixes (Immediate) ✅ COMPLETED

- [x] Fix E2EE store cleanup with shutil.rmtree()
- [x] Remove dead on_decryption_failure function
- [x] Fix ESV API return tuple consistency
- [x] Replace broad Exception catches with specific exceptions
- [x] Add request timeouts to prevent hangs
- [x] Add login timeout with asyncio.wait_for()

### Phase 2: E2EE Enhancement (High Priority) ✅ COMPLETED

- [x] Implement correct client initialization pattern from mmrelay
- [x] Add initial sync with full_state=True (already implemented)
- [x] Implement dual callback system for encrypted messages
- [x] Add automatic key requesting on decryption failure
- [x] Ensure HTML message formatting for all outgoing messages
- [x] Add E2EE status detection and reporting

### Phase 3: Authentication Modernization (High Priority) ✅ COMPLETED

- [x] Enhance interactive login with session confirmation (already enhanced)
- [x] Improve credentials management and validation (already enhanced)
- [x] Add proper session restoration logic (already implemented)
- [x] Implement device ID persistence (already implemented)
- [x] Add logout functionality with cleanup (already implemented)

### Phase 4: Configuration & CLI (Medium Priority) ✅ COMPLETED

- [x] Add comprehensive config validation
- [x] Implement platform and dependency checks
- [x] Modernize CLI with grouped subcommands
- [x] Add legacy flag support with deprecation warnings
- [x] Improve error messages and user guidance

### Phase 5: Security & Quality (Medium Priority) ✅ COMPLETED

- [x] Harden config directory permissions (0700)
- [x] Resolve Python version discrepancy
- [x] Set up PyPI OIDC Trusted Publisher (already correct)
- [x] Improve exception logging specificity
- [x] Add test cache clearing

### Phase 6: Documentation & Polish (Low Priority) 🔄 IN PROGRESS

- [ ] Update E2EE documentation based on mmrelay patterns
- [ ] Add comprehensive CLI help and examples
- [ ] Update README with new authentication flow
- [ ] Add troubleshooting guides

## Files to Modify

### Core Files

- `src/biblebot/auth.py` - Authentication and credentials management
- `src/biblebot/bot.py` - Main bot logic and E2EE implementation
- `src/biblebot/cli.py` - CLI modernization and command handling

### Configuration Files

- `setup.cfg` - Python version consistency and dependencies
- `.github/workflows/release.yml` - PyPI OIDC setup
- `docs/E2EE.md` - Documentation updates

### Test Files

- `tests/test_regex_cache.py` - Cache clearing and async improvements
- `tests/test_config_env.py` - Configuration validation tests

## Success Criteria

- [ ] All PR review comments addressed
- [ ] E2EE working with proper key management
- [ ] Modern CLI with backward compatibility
- [ ] Comprehensive configuration validation
- [ ] Secure credential management
- [ ] All tests passing
- [ ] Documentation updated and accurate

## Notes

- Delete this file before final PR merge
- Keep calling interactive feedback for continuous review
- Apply mmrelay patterns consistently
- Maintain backward compatibility where possible
- Focus on security and user experience
