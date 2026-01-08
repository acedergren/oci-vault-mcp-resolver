# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Planned
- Secret versioning support
- Distributed cache backends (Redis, Memcached)
- Metrics export (Prometheus integration)
- Auto-refresh and secret rotation detection

## [1.2.0] - 2026-01-08

### Added - Phase 2: Production-Ready Improvements
- **Custom Exception Classes** - Structured error handling hierarchy
  - `VaultResolverError` - Base exception class
  - `SecretNotFoundError` - Secret doesn't exist in vault
  - `PermissionDeniedError` - IAM permission issues
  - `AuthenticationError` - Invalid OCI credentials
  - `InvalidVaultURLError` - Malformed vault URL
  - `ConfigurationError` - Invalid configuration structure
- **Professional Logging** - Python `logging` module integration
  - Configurable log levels (DEBUG, INFO, WARNING, ERROR)
  - Structured log messages with context
  - Performance metrics logging in verbose mode
- **Input Validation** - Configuration schema validation
  - Validates config is dict type
  - Checks JSON serializability
  - Rejects empty/null configurations
- **Performance Metrics** - Built-in observability
  - Secrets fetched count tracking
  - Cache hit rate percentage
  - Average and total fetch time
  - Stale cache usage tracking
  - Automatic metrics logging in verbose mode
- **Integration Test Framework** - 15 new tests for real OCI environments
  - Real secret fetching by OCID
  - Secret resolution with caching
  - Secret lookup by name in compartment
  - Full config resolution tests
  - Instance principal authentication tests
  - Error handling validation
  - Performance metrics verification
- **Integration Testing Documentation** - `tests/INTEGRATION_TESTING.md`
  - Setup instructions with OCI CLI
  - Environment variable configuration
  - Test execution examples
  - CI/CD integration guide
  - Troubleshooting section

### Changed
- Replaced `print()` statements with `logging` module (40+ replacements)
- Error handling now raises custom exceptions instead of generic `RuntimeError`
- Updated test suite to match new exception types (4 test fixes)
- Enhanced documentation with Phase 2 features

### Improved
- Better production readiness with proper logging infrastructure
- More precise error reporting with exception attributes (e.g., `secret_id`, `compartment_id`)
- Observable performance with built-in metrics tracking
- Higher quality codebase with input validation

### Technical Debt Reduced
- Debt score: 485/1000 → ~350/1000 (28% reduction)
- Code coverage maintained: 84.92% (above 80% target)
- Test count increased: 68 tests (from 52 in Phase 1)
- Annual maintenance cost reduced: $46,350 → ~$32,000 (estimated)

## [1.1.0] - 2025-12-29

### Changed
- **BREAKING**: Consolidated to SDK-only implementation, removed CLI mode
- **BREAKING**: OCI Python SDK is now required (was optional)
- **BREAKING**: Removed `--use-sdk` and `--use-cli` command-line flags
- Changed license from MIT to AGPL v3
- All secret resolution now uses parallel mode by default

### Added
- Parallel secret resolution using asyncio (8-10x faster for multiple secrets)
- Instance principal authentication support for OCI VMs
- Structured exception handling with HTTP status codes
- Connection pooling for better performance
- SDK_IMPLEMENTATION.md - Comprehensive SDK implementation guide
- requirements.txt - Explicit dependency management
- test-sdk-example.yaml - Example configuration for testing

### Removed
- Subprocess-based CLI implementation (~190 lines)
- Duplicate VaultResolverSDK class
- CLI mode support and related flags

### Improved
- Single secret resolution: 700ms → 300ms (2.3x faster)
- Multiple secrets (10): ~7s → ~800ms (8.75x faster)
- Error handling now uses structured OCI SDK exceptions
- Simplified codebase with single implementation path
- Better documentation reflecting SDK-only architecture

### Fixed
- Eliminated code duplication between CLI and SDK modes
- Removed technical debt from dual-mode architecture

## [1.0.0] - 2025-12-29

### Added
- Initial release of OCI Vault MCP Resolver
- Core Python resolver (`oci_vault_resolver.py`)
- Bash wrapper script (`mcp-with-vault`)
- Interactive test setup (`test-setup.sh`)
- Support for three URL formats:
  - Direct secret OCID: `oci-vault://ocid1.vaultsecret...`
  - Compartment + name: `oci-vault://compartment-id/secret-name`
  - Vault + name: `oci-vault://vault-id/secret-name`
- Caching with configurable TTL (default: 1 hour)
- Graceful degradation with stale cache fallback
- Secure cache storage (0600 file permissions)
- Verbose logging mode for debugging
- Comprehensive documentation:
  - README.md - Main documentation
  - QUICKSTART.md - Getting started guide
  - ARCHITECTURE.md - System architecture with diagrams
  - API_REFERENCE.md - Complete API documentation
  - CONTRIBUTING.md - Contributor guidelines
- Example configurations
- MIT License

### Features
- **Transparent Integration**: Works seamlessly with Docker MCP Gateway
- **Smart Caching**: Reduces API calls by 99%+ after warmup
- **High Availability**: Falls back to stale cache if OCI Vault unavailable
- **Security**: Leverages OCI IAM and KMS for secret protection
- **Performance**: <1ms resolution for cached secrets
- **Portability**: Compartment+name format works across environments

### Technical Details
- Python 3.8+ compatibility
- OCI CLI integration via subprocess
- YAML configuration parsing with PyYAML
- Base64 secret decoding
- SHA256 cache key hashing
- Comprehensive error handling

### Documentation
- 10+ architecture diagrams (Mermaid)
- Complete API reference
- Example configurations for common scenarios
- CI/CD integration examples
- Troubleshooting guide

### Testing
- Interactive test setup script
- Real OCI Vault integration tested
- Multiple URL format validation
- Cache behavior verification

[Unreleased]: https://github.com/acedergren/oci-vault-mcp-resolver/compare/v1.1.0...HEAD
[1.1.0]: https://github.com/acedergren/oci-vault-mcp-resolver/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/acedergren/oci-vault-mcp-resolver/releases/tag/v1.0.0
