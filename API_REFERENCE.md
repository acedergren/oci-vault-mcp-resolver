# API Reference

Complete reference documentation for OCI Vault MCP Resolver components.

## Table of Contents

- [Python API](#python-api)
  - [VaultResolver Class](#vaultresolver-class)
  - [Helper Functions](#helper-functions)
- [CLI Reference](#cli-reference)
  - [oci_vault_resolver.py](#oci_vault_resolverpy)
  - [mcp-with-vault](#mcp-with-vault)
  - [test-setup.sh](#test-setupsh)
- [URL Format Specification](#url-format-specification)
- [Configuration Format](#configuration-format)
- [Exit Codes](#exit-codes)

---

## Python API

### VaultResolver Class

Main class for resolving OCI Vault references in configuration.

#### Constructor

```python
VaultResolver(cache_dir: Path = DEFAULT_CACHE_DIR, ttl: int = DEFAULT_TTL, verbose: bool = False)
```

**Parameters**:
- `cache_dir` (Path): Directory for caching secrets. Default: `~/.cache/oci-vault-mcp`
- `ttl` (int): Cache time-to-live in seconds. Default: `3600` (1 hour)
- `verbose` (bool): Enable verbose logging to stderr. Default: `False`

**Example**:
```python
from oci_vault_resolver import VaultResolver
from pathlib import Path

# Default settings
resolver = VaultResolver()

# Custom cache directory and TTL
resolver = VaultResolver(
    cache_dir=Path("/custom/cache"),
    ttl=7200,  # 2 hours
    verbose=True
)
```

#### Methods

##### resolve_config

```python
def resolve_config(self, config: Dict[str, Any]) -> Dict[str, Any]
```

Resolve all `oci-vault://` references in a configuration dictionary.

**Parameters**:
- `config` (Dict[str, Any]): Configuration dictionary with vault references

**Returns**:
- Dict[str, Any]: Configuration with resolved secrets

**Raises**:
- None (errors are logged, partially resolved config is returned)

**Example**:
```python
config = {
    'server': {
        'api_key': 'oci-vault://ocid1.vaultsecret...',
        'url': 'https://api.example.com'  # Not a secret, passes through
    }
}

resolved = resolver.resolve_config(config)
# {
#     'server': {
#         'api_key': 'actual-secret-value',
#         'url': 'https://api.example.com'
#     }
# }
```

##### resolve_secret

```python
def resolve_secret(self, vault_url: str) -> Optional[str]
```

Resolve a single `oci-vault://` URL to its secret value.

**Parameters**:
- `vault_url` (str): Vault URL in format `oci-vault://...`

**Returns**:
- Optional[str]: Secret value, or None if resolution fails

**Behavior**:
1. Checks cache for fresh value
2. If cache miss, fetches from OCI Vault
3. If fetch fails, falls back to stale cache (with warning)
4. Returns None only if no cache and fetch fails

**Example**:
```python
# By OCID
secret = resolver.resolve_secret('oci-vault://ocid1.vaultsecret...')

# By compartment + name
secret = resolver.resolve_secret('oci-vault://ocid1.compartment.../my-secret')

# Error cases
secret = resolver.resolve_secret('oci-vault://invalid')  # Returns None
```

##### parse_vault_url

```python
def parse_vault_url(self, url: str) -> Tuple[Optional[str], Optional[str], Optional[str]]
```

Parse an `oci-vault://` URL into components.

**Parameters**:
- `url` (str): Vault URL

**Returns**:
- Tuple of (secret_ocid, compartment_id, secret_name)
- Returns (None, None, None) if URL is invalid

**Examples**:
```python
# Direct OCID
ocid, comp, name = resolver.parse_vault_url('oci-vault://ocid1.vaultsecret.oc1...')
# ('ocid1.vaultsecret.oc1...', None, None)

# Compartment + name
ocid, comp, name = resolver.parse_vault_url('oci-vault://ocid1.compartment.../secret-name')
# (None, 'ocid1.compartment...', 'secret-name')

# Vault + name
ocid, comp, name = resolver.parse_vault_url('oci-vault://ocid1.vault.../secret-name')
# (None, 'ocid1.vault...', 'secret-name')
```

##### fetch_secret_by_ocid

```python
def fetch_secret_by_ocid(self, secret_ocid: str) -> Optional[str]
```

Fetch secret value from OCI Vault by secret OCID.

**Parameters**:
- `secret_ocid` (str): OCI Vault secret OCID

**Returns**:
- Optional[str]: Decrypted secret value, or None on error

**OCI CLI Command**:
```bash
oci secrets secret-bundle get --secret-id <secret_ocid>
```

**Example**:
```python
value = resolver.fetch_secret_by_ocid('ocid1.vaultsecret.oc1.iad.xxx')
# Returns: "actual-secret-value"
```

##### find_secret_by_name

```python
def find_secret_by_name(self, compartment_id: str, secret_name: str) -> Optional[str]
```

Find secret OCID by name within a compartment.

**Parameters**:
- `compartment_id` (str): OCI compartment OCID
- `secret_name` (str): Secret name

**Returns**:
- Optional[str]: Secret OCID if found, None otherwise

**OCI CLI Command**:
```bash
oci vault secret list --compartment-id <compartment_id> --all
```

**Example**:
```python
ocid = resolver.find_secret_by_name(
    'ocid1.compartment.oc1..xxx',
    'my-api-key'
)
# Returns: 'ocid1.vaultsecret.oc1.iad.yyy'
```

##### get_cached_secret

```python
def get_cached_secret(self, cache_key: str) -> Optional[Tuple[str, bool]]
```

Get cached secret if available.

**Parameters**:
- `cache_key` (str): Cache key (usually the vault URL)

**Returns**:
- Optional[Tuple[str, bool]]: (secret_value, is_stale) or None

**Example**:
```python
cached = resolver.get_cached_secret('oci-vault://ocid1.vaultsecret...')
if cached:
    value, is_stale = cached
    if not is_stale:
        print(f"Fresh cache: {value}")
```

##### cache_secret

```python
def cache_secret(self, cache_key: str, secret_value: str) -> None
```

Cache a secret value with timestamp.

**Parameters**:
- `cache_key` (str): Cache key
- `secret_value` (str): Secret value to cache

**Side Effects**:
- Creates cache file with 0600 permissions
- Overwrites existing cache for same key

**Example**:
```python
resolver.cache_secret('oci-vault://ocid1.vaultsecret...', 'secret-value')
```

---

## CLI Reference

### oci_vault_resolver.py

Core Python script for resolving vault references.

#### Synopsis

```bash
python3 oci_vault_resolver.py [OPTIONS]
```

#### Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `-i, --input` | FILE | stdin | Input YAML file with vault references |
| `-o, --output` | FILE | stdout | Output file for resolved YAML |
| `--cache-dir` | PATH | `~/.cache/oci-vault-mcp` | Cache directory |
| `--ttl` | INT | 3600 | Cache TTL in seconds |
| `-v, --verbose` | FLAG | False | Enable verbose logging |
| `--help` | FLAG | - | Show help message |

#### Examples

**Basic usage** (stdin/stdout):
```bash
cat config.yaml | python3 oci_vault_resolver.py
```

**From file**:
```bash
python3 oci_vault_resolver.py -i input.yaml -o output.yaml
```

**Verbose mode**:
```bash
python3 oci_vault_resolver.py -i config.yaml --verbose
```

**Custom cache TTL**:
```bash
python3 oci_vault_resolver.py --ttl 7200 -i config.yaml
```

**With Docker MCP**:
```bash
docker mcp config read | python3 oci_vault_resolver.py | docker mcp config write
```

#### Output

**Success**: Exits 0, outputs resolved YAML to stdout
**Partial Success**: Exits 0, outputs partially resolved YAML, warnings to stderr
**Failure**: Exits 1, error message to stderr

---

### mcp-with-vault

Wrapper script for convenient integration with Docker MCP Gateway.

#### Synopsis

```bash
./mcp-with-vault [OPTIONS]
```

#### Options

| Option | Description |
|--------|-------------|
| `--ttl SECONDS` | Cache TTL (default: 3600) |
| `--verbose` | Enable verbose logging |
| `--dry-run` | Show resolved config without applying |
| `--start` | Start MCP Gateway after applying |
| `--help` | Show help message |

#### Examples

**Basic resolution and apply**:
```bash
./mcp-with-vault
```

**Dry run** (preview only):
```bash
./mcp-with-vault --dry-run
```

**Resolve and start gateway**:
```bash
./mcp-with-vault --start
```

**Custom TTL with verbose output**:
```bash
./mcp-with-vault --ttl 7200 --verbose
```

#### Environment Variables

None required. Uses Docker MCP CLI and OCI CLI from PATH.

#### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Error (check stderr) |

---

### test-setup.sh

Interactive setup and testing script.

#### Synopsis

```bash
./test-setup.sh
```

#### What It Does

1. Checks Python, PyYAML, OCI CLI, Docker MCP
2. Verifies OCI CLI authentication
3. Lists available compartments and vaults
4. Optionally creates a test secret
5. Provides test commands

#### Interactive Prompts

- Create test secret? (y/N)
- Compartment OCID
- Vault name (if creating)
- Secret name
- Secret value

#### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | All checks passed |
| 1 | Missing dependency or configuration issue |

---

## URL Format Specification

### Format 1: Direct Secret OCID

```
oci-vault://<secret-ocid>
```

**Components**:
- `secret-ocid`: Full OCI Vault secret OCID

**Example**:
```
oci-vault://ocid1.vaultsecret.oc1.iad.amaaaaaxxxxxx
```

**Characteristics**:
- ✅ Fastest resolution (1 API call)
- ✅ No name lookup needed
- ❌ Not portable across environments
- ❌ Hard to read/maintain

### Format 2: Compartment + Secret Name

```
oci-vault://<compartment-ocid>/<secret-name>
```

**Components**:
- `compartment-ocid`: OCI compartment OCID
- `secret-name`: Name of secret (case-sensitive)

**Example**:
```
oci-vault://ocid1.compartment.oc1..aaaaaxxxxxx/my-api-key
```

**Characteristics**:
- ✅ Portable across environments
- ✅ Self-documenting
- ✅ Can use different secrets per environment
- ❌ Slower (2 API calls on cache miss)

### Format 3: Vault + Secret Name

```
oci-vault://<vault-ocid>/<secret-name>
```

**Components**:
- `vault-ocid`: OCI Vault OCID
- `secret-name`: Name of secret

**Example**:
```
oci-vault://ocid1.vault.oc1.iad.cbq72kqtaaani.xxxxx/my-secret
```

**Characteristics**:
- ✅ Scoped to specific vault
- ✅ Good for multi-vault setups
- ❌ Requires vault OCID
- ❌ Slower (2 API calls on cache miss)

---

## Configuration Format

### Input Configuration (with vault references)

```yaml
servers:
  service-name:
    config:
      # Regular values
      SERVICE_URL: https://api.example.com
      TIMEOUT: 30

      # Vault references (resolved)
      API_KEY: oci-vault://ocid1.compartment.../api-key
      DB_PASSWORD: oci-vault://ocid1.vaultsecret.oc1.iad.xxx

      # Nested structures supported
      database:
        host: db.example.com
        password: oci-vault://ocid1.compartment.../db-pass
```

### Output Configuration (resolved)

```yaml
servers:
  service-name:
    config:
      SERVICE_URL: https://api.example.com
      TIMEOUT: 30
      API_KEY: actual-api-key-value
      DB_PASSWORD: actual-db-password
      database:
        host: db.example.com
        password: actual-db-password
```

### Cache File Format

```json
{
  "value": "actual-secret-value",
  "cached_at": 1735480000,
  "cache_key": "oci-vault://compartment-id/secret-name"
}
```

**Fields**:
- `value` (string): Decrypted secret value
- `cached_at` (integer): Unix timestamp of cache creation
- `cache_key` (string): Original vault URL

---

## Exit Codes

### oci_vault_resolver.py

| Code | Meaning | Action |
|------|---------|--------|
| 0 | Success or partial success | Check stderr for warnings |
| 1 | Fatal error | Check stderr for error message |

### mcp-with-vault

| Code | Meaning | Action |
|------|---------|--------|
| 0 | Success | Config applied to gateway |
| 1 | Error | Check stderr, verify dependencies |

### test-setup.sh

| Code | Meaning | Action |
|------|---------|--------|
| 0 | All checks passed | Proceed with usage |
| 1 | Dependency missing | Install missing dependency |

---

## Error Messages

### Common Errors

**"OCI CLI error"**
- Cause: OCI CLI command failed
- Check: OCI CLI configuration (`oci setup config`)
- Check: IAM permissions for vault access

**"Secret not found"**
- Cause: Secret doesn't exist or wrong compartment
- Check: Secret name is correct (case-sensitive)
- Check: Compartment OCID is correct
- Check: IAM permissions to list secrets

**"Invalid vault URL format"**
- Cause: Malformed `oci-vault://` URL
- Fix: Use one of the supported formats
- Example: `oci-vault://ocid1.vaultsecret...`

**"Cache read error"**
- Cause: Cache file corrupted or permission issue
- Fix: `rm -rf ~/.cache/oci-vault-mcp/`

**"Failed to parse YAML"**
- Cause: Invalid YAML syntax in input
- Fix: Validate YAML with `yamllint` or online tool

---

## Performance Characteristics

### Latency by Scenario

| Scenario | Cache State | API Calls | Latency |
|----------|-------------|-----------|---------|
| OCID format | Hit (fresh) | 0 | ~0.1ms |
| OCID format | Miss | 1 | ~500ms |
| Name format | Hit (fresh) | 0 | ~0.1ms |
| Name format | Miss | 2 | ~900ms |

### Resource Usage

- **Memory**: ~50 MB (Python + dependencies)
- **Disk**: ~1 KB per cached secret
- **Network**: ~2-4 KB per API call

---

## Integration Examples

### Systemd Service

```ini
[Unit]
Description=MCP Gateway with OCI Vault Secrets
After=network.target

[Service]
Type=oneshot
ExecStart=/path/to/mcp-with-vault --start
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
```

### GitHub Actions

```yaml
- name: Resolve Secrets
  run: |
    docker mcp config read | \
      python3 oci_vault_resolver.py | \
      docker mcp config write
```

### Docker Compose

```yaml
services:
  mcp-gateway:
    image: mcp-gateway:latest
    volumes:
      - ./resolved-config.yaml:/config.yaml
    command: ["--config", "/config.yaml"]

# Pre-start hook
x-pre-start:
  command: ./mcp-with-vault
```

---

## Version Compatibility

| Component | Version | Notes |
|-----------|---------|-------|
| Python | 3.8+ | Required |
| OCI CLI | 3.x | Tested with 3.68.0 |
| Docker MCP | 0.30+ | For gateway integration |
| PyYAML | Any | For YAML parsing |

---

For more information, see:
- [README.md](README.md) - General documentation
- [QUICKSTART.md](QUICKSTART.md) - Getting started guide
- [ARCHITECTURE.md](ARCHITECTURE.md) - Architecture details
