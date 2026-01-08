# CLAUDE.md - AI Assistant Guide

This document provides essential context for AI assistants working with the OCI Vault MCP Resolver codebase.

## Project Overview

**OCI Vault MCP Resolver** is a secure secrets management tool that resolves `oci-vault://` references in configuration files by fetching secrets from Oracle Cloud Infrastructure (OCI) Vault. It integrates with Docker MCP Gateway and standalone applications.

**Primary Use Cases:**
- Docker MCP Gateway secret injection
- Claude Code MCP server credential management
- CI/CD pipeline secret handling
- Application configuration without secrets in version control

**Current Version:** 1.1.0 (SDK-only implementation with parallel resolution)

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Entry Points                              │
├─────────────────────────────────────────────────────────────┤
│  mcp-with-vault (bash)     │  oci_vault_resolver.py (CLI)  │
│  - Docker MCP integration   │  - Standalone resolver         │
│  - Reads/writes MCP config  │  - Stdin/stdout YAML pipeline │
└────────────────────────────┼────────────────────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────┐
│                 VaultResolver Class                          │
│  oci_vault_resolver.py:50-452                               │
├─────────────────────────────────────────────────────────────┤
│  Core Methods:                                               │
│  - resolve_config()      → Parallel resolution of all refs  │
│  - resolve_secret()      → Single URL resolution            │
│  - fetch_secret_by_ocid() → OCI SDK API call                │
│  - find_secret_by_name() → Compartment search               │
│  - parse_vault_url()     → Three URL format parser          │
├─────────────────────────────────────────────────────────────┤
│  Caching Layer:                                              │
│  - get_cached_secret()   → TTL-based cache lookup           │
│  - cache_secret()        → SHA256-hashed file storage       │
│  - Cache dir: ~/.cache/oci-vault-mcp/                       │
└─────────────────────────────────────────────────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────┐
│                    OCI Python SDK                            │
│  - SecretsClient → get_secret_bundle()                      │
│  - VaultsClient  → list_secrets()                           │
└─────────────────────────────────────────────────────────────┘
```

## File Structure

```
/
├── oci_vault_resolver.py    # Main Python module (579 lines)
│   └── VaultResolver class  # Core resolver with async parallel fetching
├── mcp-with-vault           # Bash wrapper for Docker MCP Gateway (185 lines)
├── upload-secret.sh         # Helper to upload secrets to OCI Vault (211 lines)
├── test-setup.sh            # Interactive test setup script (213 lines)
├── requirements.txt         # Python dependencies: PyYAML, oci
├── example-config.yaml      # Example MCP configuration
├── test-mcp-config.yaml     # Test configuration with vault references
└── Documentation/
    ├── README.md
    ├── QUICKSTART.md
    ├── ARCHITECTURE.md
    ├── API_REFERENCE.md
    ├── SDK_IMPLEMENTATION.md
    ├── CLAUDE_CODE_INTEGRATION.md
    ├── CONTRIBUTING.md
    └── CHANGELOG.md
```

## Key Code Patterns

### URL Formats Supported
```
oci-vault://ocid1.vaultsecret.oc1...           # Direct secret OCID
oci-vault://ocid1.compartment.oc1.../name      # Compartment + secret name
oci-vault://ocid1.vault.oc1.../name            # Vault + secret name
```

### VaultResolver Initialization
```python
resolver = VaultResolver(
    cache_dir=Path("~/.cache/oci-vault-mcp"),
    ttl=3600,                          # Cache TTL in seconds
    verbose=False,                     # Debug logging
    use_instance_principals=False,     # For OCI VMs
    config_file=None,                  # Default: ~/.oci/config
    config_profile="DEFAULT"
)
```

### Parallel Resolution Pattern
The codebase uses `asyncio.gather()` for parallel secret fetching:
```python
async def fetch_secrets_parallel(self, vault_urls: List[str]) -> Dict[str, Optional[str]]:
    tasks = [fetch_one(url) for url in vault_urls]
    results = await asyncio.gather(*tasks)
    return dict(results)
```

### Error Handling Pattern
OCI SDK errors are handled with structured status codes:
- 404: Secret not found
- 401: Authentication failure
- 403: Permission denied
- 429: Rate limiting
- 500+: Service errors

Falls back to stale cache when OCI Vault is unavailable.

## Development Commands

### Running the Resolver
```bash
# Direct Python invocation
python3 oci_vault_resolver.py -i config.yaml --verbose

# Piped from stdin
echo 'key: oci-vault://secret-ocid' | python3 oci_vault_resolver.py

# With Docker MCP Gateway
./mcp-with-vault --dry-run
./mcp-with-vault --start
```

### Testing
```bash
# Interactive setup and testing
./test-setup.sh

# Manual test with verbose output
python3 oci_vault_resolver.py -i test-mcp-config.yaml --verbose

# Test wrapper dry-run
./mcp-with-vault --dry-run
```

### Cache Management
```bash
# View cache files
ls -lah ~/.cache/oci-vault-mcp/

# Clear cache
rm -rf ~/.cache/oci-vault-mcp/
```

### Upload Secrets
```bash
# Set required environment variables
export OCI_VAULT_COMPARTMENT_ID="ocid1.compartment.oc1..."
export OCI_VAULT_ID="ocid1.vault.oc1..."
export OCI_REGION="us-ashburn-1"

# Upload a secret
./upload-secret.sh my-secret-name "secret-value"
```

## Coding Conventions

### Python Style
- **PEP 8** compliant
- **Type hints** on all public methods
- **Docstrings** for all classes and public methods
- **Line length**: 100 characters max
- **Imports**: Standard library, then third-party, then local

### Bash Style
- `set -euo pipefail` at script start
- Quote all variables: `"$VAR"`
- Color-coded output (RED, GREEN, YELLOW, BLUE)
- Dependency checking before execution

### Commit Messages
Follow conventional commit format:
```
feat(resolver): add support for vault OCID format
fix(cache): correct TTL calculation
docs(readme): update installation instructions
refactor(parser): simplify URL parsing logic
```

## Common AI Assistant Tasks

### 1. Adding a New URL Format
Modify `parse_vault_url()` in `oci_vault_resolver.py:112-145`:
- Add regex pattern or conditional logic
- Return tuple: `(secret_ocid, compartment_id, secret_name)`
- Update docstrings and tests

### 2. Modifying Cache Behavior
Key methods in `oci_vault_resolver.py`:
- `get_cache_path()` (line 147) - Cache key hashing
- `get_cached_secret()` (line 154) - Cache lookup with TTL
- `cache_secret()` (line 190) - Cache storage with 0600 permissions

### 3. Adding CLI Arguments
Add to `argparse` section in `main()` function (line 456+):
```python
parser.add_argument(
    '--new-option',
    type=str,
    help='Description of option'
)
```

### 4. Updating Bash Wrapper
Edit `mcp-with-vault`:
- Add options in the `while` loop (line 70+)
- Update `usage()` function
- Pass through to Python resolver via `RESOLVER_CMD`

### 5. Extending Error Handling
Add cases to `fetch_secret_by_ocid()` (line 211) exception handling:
```python
except oci.exceptions.ServiceError as e:
    if e.status == NEW_STATUS:
        # Handle new error type
```

## Dependencies

**Required:**
- Python 3.8+
- `PyYAML>=6.0`
- `oci>=2.126.0` (OCI Python SDK)

**Optional (for full functionality):**
- OCI CLI (`oci`) - for upload-secret.sh
- Docker - for MCP Gateway integration

## Security Considerations

- Cache files use 0600 permissions (owner read/write only)
- Secrets are never logged (even in verbose mode)
- Supports IAM policies and role-based access control
- Instance principal authentication for OCI compute instances
- No secrets stored in configuration files

## Authentication Methods

1. **OCI Config File** (default): `~/.oci/config`
2. **Instance Principals**: `--instance-principals` flag (for OCI VMs)
3. **Custom Profile**: `--profile PROFILE_NAME`

## Performance Notes

- **Parallel resolution**: 8-10x faster than sequential (v1.1.0+)
- **Cache TTL**: Default 3600 seconds (1 hour)
- **Cache storage**: JSON files with SHA256-hashed keys
- **Graceful degradation**: Falls back to stale cache on errors

## Testing with Real OCI Vault

The repository includes test secrets in the EU-Frankfurt region. See `test-mcp-config.yaml` for example vault references. Run `./test-setup.sh` for interactive testing setup.

## Related Documentation

- `README.md` - Full user documentation
- `API_REFERENCE.md` - Complete API documentation
- `ARCHITECTURE.md` - System architecture diagrams
- `CLAUDE_CODE_INTEGRATION.md` - Claude Code specific integration
- `CONTRIBUTING.md` - Contribution guidelines
