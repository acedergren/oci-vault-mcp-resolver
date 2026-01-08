# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

OCI Vault MCP Resolver is a secrets management integration layer for Docker MCP Gateway that resolves `oci-vault://` references by fetching secrets from Oracle Cloud Infrastructure Vault. It provides transparent secret resolution with performance caching and graceful degradation.

## Essential Commands

### Running the Resolver

```bash
# CLI mode (default) - sequential resolution
./mcp-with-vault                    # Resolve and apply secrets
./mcp-with-vault --dry-run          # Preview without applying
./mcp-with-vault --verbose          # Debug mode

# SDK mode - faster parallel resolution (requires: pip install oci)
./mcp-with-vault --use-sdk          # Use SDK for faster resolution
./mcp-with-vault --use-sdk --instance-principals  # For OCI VMs
./mcp-with-vault --use-sdk --verbose              # SDK with debug

# Direct Python usage
docker mcp config read | python3 oci_vault_resolver.py
docker mcp config read | python3 oci_vault_resolver.py --use-sdk
docker mcp config read | python3 oci_vault_resolver.py --use-sdk --instance-principals
python3 oci_vault_resolver.py -i config.yaml -o resolved.yaml --use-sdk
```

### Testing

```bash
./test-setup.sh                                      # Run test script
python3 oci_vault_resolver.py -i test-mcp-config.yaml --verbose
./mcp-with-vault --dry-run                           # Dry run test
```

### Debugging

```bash
# Enable verbose logging
python3 oci_vault_resolver.py --verbose

# Inspect cache
ls -lah ~/.cache/oci-vault-mcp/
cat ~/.cache/oci-vault-mcp/*.json | jq

# Clear cache
rm -rf ~/.cache/oci-vault-mcp/

# Test OCI CLI directly
oci secrets secret-bundle get --secret-id OCID
```

### OCI Vault Operations

```bash
# Verify OCI setup
oci iam compartment list --query 'data[0:3].name'

# List secrets
oci vault secret list --compartment-id COMPARTMENT_ID --all

# Get secret value
oci secrets secret-bundle get --secret-id SECRET_ID \
  --query 'data."secret-bundle-content".content' --raw-output | base64 -d
```

## Architecture

### Core Components

**oci_vault_resolver.py** - Main Python resolver with dual modes

**VaultResolver class** (CLI mode - default):
- Uses OCI CLI via subprocess calls
- Sequential secret resolution
- Works with existing OCI CLI configuration
- Key methods:
  - `resolve_config(config)` - Main entry: resolve all vault refs in config
  - `resolve_secret(vault_url)` - Resolve single URL with cache fallback
  - `parse_vault_url(url)` - Parse URL into (ocid, compartment, name)
  - `fetch_secret_by_ocid(ocid)` - Fetch from OCI Vault via CLI subprocess
  - `find_secret_by_name(compartment, name)` - Lookup OCID by name via CLI

**VaultResolverSDK class** (SDK mode - optional):
- Uses OCI Python SDK for direct API calls (faster)
- **Parallel secret resolution** using asyncio
- Instance principal authentication support
- Better error handling with structured exceptions
- Requires: `pip install oci`
- Performance: 2-10x faster depending on number of secrets

**mcp-with-vault** - Bash wrapper script
- Orchestrates: read config → resolve → write config → optionally start gateway
- Handles dependency checks, error display, and user options

### Resolution Flow

1. Find all `oci-vault://` references in config (recursive traversal)
2. For each reference:
   - Check cache (use if fresh, TTL < 1 hour default)
   - Parse URL format (3 supported formats)
   - Fetch secret from OCI Vault (with name lookup if needed)
   - Base64 decode and cache result
   - Fallback to stale cache on fetch failure (with warning)
3. Replace all vault references with resolved values

### Vault URL Formats

```
oci-vault://ocid1.vaultsecret.oc1.iad.xxx           # Direct OCID (fastest)
oci-vault://ocid1.compartment.oc1..xxx/secret-name  # Compartment + name
oci-vault://ocid1.vault.oc1.iad.xxx/secret-name     # Vault + name
```

### Caching Strategy

- **Location**: `~/.cache/oci-vault-mcp/`
- **Format**: JSON files with hashed names (SHA256 first 16 chars)
- **Security**: Files chmod 0600
- **TTL**: Default 3600s (1 hour), configurable via `--ttl`
- **Staleness**: Stale cache used as fallback when OCI Vault unavailable

## Code Style

### Python (PEP 8)
- Type hints required for functions: `def func(arg: str) -> Optional[str]:`
- Max line length: 100 characters
- Docstrings for all public functions
- Descriptive variable names

### Bash
- Always start with `set -euo pipefail`
- Quote all variables: `"$VAR"`
- Use functions for reusable logic
- Local variables with `local` keyword

### Commits (Conventional Commits)
```
feat(scope): description     # New feature
fix(scope): description      # Bug fix
docs(scope): description     # Documentation
refactor(scope): description # Code refactoring
```

## Development Guidelines

### When Making Changes

1. **Test all URL formats**: OCID, compartment+name, vault+name
2. **Verify caching**: Check files created in `~/.cache/oci-vault-mcp/` with 0600 perms
3. **Test error handling**: Invalid OCIDs, network failures, missing secrets
4. **Check cache fallback**: Verify stale cache usage when vault unavailable
5. **Test both modes**: CLI mode (default) and SDK mode (`--use-sdk`)
6. **Verify parallel resolution**: SDK mode should fetch multiple secrets concurrently
7. **Use verbose mode**: `--verbose` for debugging during development

### Security Requirements

- Never log secrets (except to stderr in verbose debug mode)
- Cache files must be chmod 0600
- No credentials hardcoded in code
- Clear error messages without exposing sensitive details
- Graceful degradation preferred over hard failures

### Key Design Patterns

**Graceful Degradation**: On OCI API failure, fall back to stale cache with warning rather than fail hard. Availability over freshness.

**Recursive Resolution**: Config traversed recursively to find vault references at any nesting level. Uses path notation like `servers.prometheus.config.API_KEY`.

**Cache-First Architecture**: Always check cache before hitting OCI API. Performance critical for repeated resolutions.

**Subprocess Execution**: Uses OCI CLI via subprocess rather than OCI Python SDK to leverage existing CLI configuration.

## Common Pitfalls

1. **Cache permissions**: Ensure cache files are 0600, not world-readable
2. **OCI CLI version**: Command syntax can change between versions
3. **Base64 decoding**: Secret content is base64-encoded by OCI
4. **Empty/null responses**: Handle OCI CLI returning "None" as string
5. **Nested configs**: Vault references can be deeply nested in YAML

## Project Structure

```
oci_vault_resolver.py    # Main Python resolver (450 lines)
mcp-with-vault           # Bash wrapper script (174 lines)
test-setup.sh            # Test script
test-mcp-config.yaml     # Test configuration
example-config.yaml      # Example configuration
README.md                # User documentation
ARCHITECTURE.md          # Technical architecture
CONTRIBUTING.md          # Contribution guidelines
```

## Dependencies

**Core dependencies** (required):
```bash
pip install PyYAML
```

**Optional SDK dependency** (recommended for production):
```bash
pip install oci
```

Or install all dependencies:
```bash
pip install -r requirements.txt
```

## Performance Modes

**CLI Mode** (default):
- Uses OCI CLI via subprocess
- Sequential resolution: ~500-1000ms per secret
- No additional dependencies beyond OCI CLI
- Works with existing `oci` command configuration

**SDK Mode** (--use-sdk):
- Uses OCI Python SDK
- Parallel resolution: ~200-400ms total for multiple secrets
- Requires `pip install oci`
- **2-10x faster** depending on number of secrets
- Instance principal support for OCI VMs

## No Automated Tooling

This project does **not** use:
- Linters (no flake8, pylint, black)
- Type checkers (no mypy)
- Test frameworks (no pytest)
- CI/CD pipelines
- Pre-commit hooks

All quality checks are manual during code review.
