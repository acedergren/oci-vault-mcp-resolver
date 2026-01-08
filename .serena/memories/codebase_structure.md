# Codebase Structure

## Core Components

### 1. `oci_vault_resolver.py` (Main Script)
The core resolver implementation with the following key classes and functions:

**VaultResolver Class**:
- `__init__(cache_dir, ttl, verbose)` - Initialize resolver with configuration
- `parse_vault_url(url)` - Parse oci-vault:// URLs into components (OCID, compartment, name)
- `get_cached_secret(cache_key)` - Check cache for secret (returns value + staleness flag)
- `cache_secret(cache_key, secret_value)` - Write secret to cache with timestamp
- `fetch_secret_by_ocid(secret_ocid)` - Fetch secret from OCI Vault by OCID
- `find_secret_by_name(compartment_id, secret_name)` - Find secret OCID by name
- `resolve_secret(vault_url)` - Main resolution logic with cache fallback
- `find_vault_references(obj, path)` - Recursively find all oci-vault:// references in config
- `set_nested_value(obj, path, value)` - Set value in nested config structure
- `resolve_config(config)` - Main entry point: resolve all vault references in config dict

**Main Function**:
- Argument parsing (--input, --output, --cache-dir, --ttl, --verbose)
- YAML loading and dumping
- Error handling and exit codes

### 2. `mcp-with-vault` (Bash Wrapper)
User-friendly CLI wrapper that orchestrates the full workflow:
- Reads current MCP config via `docker mcp config read`
- Pipes through Python resolver
- Writes resolved config via `docker mcp config write`
- Optionally starts MCP gateway

**Options**: --ttl, --verbose, --dry-run, --start, --help

### 3. Supporting Files
- `test-setup.sh` - Test script for manual validation
- `test-mcp-config.yaml` - Example test configuration
- `example-config.yaml` - Sample configuration for users

## Architecture Patterns

### Resolution Flow
1. Find all `oci-vault://` references in config (recursive traversal)
2. For each reference:
   - Check cache (fresh < TTL → use it)
   - If cache miss or stale:
     - Parse URL format (OCID vs compartment+name vs vault+name)
     - Resolve secret OCID if needed (via list API)
     - Fetch secret value by OCID
     - Base64 decode
     - Update cache
   - If fetch fails: fallback to stale cache with warning
3. Replace all references with resolved values
4. Return resolved config

### Caching Strategy
- **Location**: `~/.cache/oci-vault-mcp/`
- **Format**: JSON files with hashed filenames (SHA256 first 16 chars)
- **Content**: `{value, cached_at, cache_key}`
- **Security**: Files chmod 0600
- **TTL**: Configurable, default 3600s (1 hour)
- **Staleness**: Cache older than TTL is "stale" but usable as fallback

### Error Handling
- Graceful degradation: uses stale cache on OCI API failures
- Clear error messages with context (compartment ID, secret name)
- Warnings printed to stderr when using stale cache
- Non-zero exit codes on unrecoverable errors
