# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2025-01-05

### Added

- **Message Splitting Feature**: New configurable message splitting for long Bible passages
  - Add `split_message_length` configuration option to split long messages into multiple parts
  - Intelligent word boundary splitting using Python's textwrap module
  - Context-aware reference trimming to prevent suffix overflow
  - Reference and suffix only appear on the final message chunk
  - Automatic fallback to single-message mode when splitting is impractical
- **Enhanced Rate Limiting**: Production-ready rate limiting with exponential backoff and jitter
  - Handles Matrix 429 rate limit responses gracefully
  - Exponential backoff with ±20% jitter to prevent thundering herd
  - Bounded retries (maximum 3 attempts) to avoid infinite loops
- **Improved Configuration**: Enhanced sample configurations and documentation
  - Better comments explaining configuration options
  - Room alias support with automatic resolution to canonical IDs
  - Clearer E2EE setup instructions and requirements
  - Environment variable examples and .env deprecation warnings

### Improved

- **Error Handling**: Comprehensive edge case handling for message processing
  - Robust handling of extremely long references
  - Pathological splitting prevention (minimum chunk size enforcement)
  - Better validation and error messages for configuration issues
- **Code Quality**: Significant code quality improvements
  - Extracted magic numbers to named constants for better maintainability
  - Improved test coverage with 27 comprehensive tests
  - Better separation of concerns and cleaner code structure
  - Enhanced documentation and inline comments

### Technical Details

- Context-aware reference trimming optimizes behavior for different message paths
- Intelligent fallback mechanisms ensure messages are always delivered
- Production-grade error handling prevents bot failures in edge cases
- Backward compatible design (message splitting disabled by default)

## [0.1.3] - Previous Release

### Features

- Basic Bible verse fetching with KJV and ESV support
- Matrix room integration with authentication
- End-to-end encryption support
- Configurable caching and message formatting
- Systemd service integration
- Command-line interface with interactive setup
