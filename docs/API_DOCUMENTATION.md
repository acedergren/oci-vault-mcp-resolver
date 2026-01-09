# OCI Vault MCP Resolver - API Documentation

**Version**: 2.0.0
**Status**: Production Ready
**Last Updated**: 2026-01-08

## Overview

The OCI Vault MCP Resolver provides a Python API for securely resolving secrets from Oracle Cloud Infrastructure (OCI) Vault and injecting them into Model Context Protocol (MCP) servers. It replaces Docker Desktop secrets management with enterprise-grade cloud vault integration.

## Table of Contents

- [Core Classes](#core-classes)
- [Configuration](#configuration)
- [Secret Resolution](#secret-resolution)
- [Error Handling](#error-handling)
- [Caching](#caching)
- [Circuit Breaker](#circuit-breaker)
- [Command-Line Interface](#command-line-interface)

---

## Core Classes

### VaultResolver

The main class for resolving secrets from OCI Vault.

#### Constructor

```python
VaultResolver(
    vault_id: Optional[str] = None,
    default_compartment_id: Optional[str] = None,
    default_vault_id: Optional[str] = None,
    region: Optional[str] = None,
    config_file: str = "~/.oci/config",
    profile: str = "DEFAULT",
    use_instance_principals: bool = False,
    cache_dir: str = "~/.cache/oci-vault-mcp",
    ttl: int = 3600,
    verbose: bool = False,
    enable_circuit_breaker: bool = True,
    circuit_breaker_threshold: int = 5,
    max_retries: int = 3,
    enable_stale_fallback: bool = True
)
```

**Parameters**:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `vault_id` | `Optional[str]` | `None` | OCI Vault OCID (optional if using vault URL with OCID) |
| `default_compartment_id` | `Optional[str]` | `None` | Default compartment OCID for secret name lookups |
| `default_vault_id` | `Optional[str]` | `None` | Alias for vault_id |
| `region` | `Optional[str]` | `None` | OCI region (e.g., "eu-frankfurt-1") |
| `config_file` | `str` | `"~/.oci/config"` | Path to OCI CLI config file |
| `profile` | `str` | `"DEFAULT"` | Profile name in OCI config file |
| `use_instance_principals` | `bool` | `False` | Use instance principal authentication (for OCI VMs) |
| `cache_dir` | `str` | `"~/.cache/oci-vault-mcp"` | Directory for caching decrypted secrets |
| `ttl` | `int` | `3600` | Cache TTL in seconds |
| `verbose` | `bool` | `False` | Enable verbose logging |
| `enable_circuit_breaker` | `bool` | `True` | Enable circuit breaker for fault tolerance |
| `circuit_breaker_threshold` | `int` | `5` | Number of failures before circuit opens |
| `max_retries` | `int` | `3` | Maximum retry attempts for failed operations |
| `enable_stale_fallback` | `bool` | `True` | Use stale cache if vault is unavailable |

**Example**:

```python
from oci_vault_resolver import VaultResolver

# Using config file authentication
resolver = VaultResolver(
    vault_id="ocid1.vault.oc1.eu-frankfurt-1.xxx",
    default_compartment_id="ocid1.compartment.oc1..xxx",
    region="eu-frankfurt-1",
    config_file="~/.oci/config",
    profile="DEFAULT",
    ttl=3600,
    verbose=True
)

# Using instance principal authentication (for OCI VMs)
resolver = VaultResolver(
    vault_id="ocid1.vault.oc1.eu-frankfurt-1.xxx",
    default_compartment_id="ocid1.compartment.oc1..xxx",
    region="eu-frankfurt-1",
    use_instance_principals=True
)
```

#### Class Methods

##### from_config()

Create VaultResolver from YAML configuration file.

```python
@classmethod
def from_config(
    cls,
    config_path: Optional[Path] = None
) -> "VaultResolver"
```

**Parameters**:
- `config_path` (Optional[Path]): Path to resolver.yaml config file. If not provided, searches in priority order:
  1. `~/.config/oci-vault-mcp/resolver.yaml`
  2. `/etc/oci-vault-mcp/resolver.yaml`
  3. `./resolver.yaml`
  4. `../config/resolver.yaml.example`

**Returns**: `VaultResolver` instance

**Raises**:
- `FileNotFoundError`: If no config file found
- `yaml.YAMLError`: If config is invalid YAML
- `ConfigurationError`: If config validation fails

**Example**:

```python
# Load from default locations
resolver = VaultResolver.from_config()

# Load from specific file
resolver = VaultResolver.from_config(Path("/etc/oci-vault-mcp/resolver.yaml"))
```

**Config File Format**:

```yaml
version: "1.0"

vault:
  vault_id: "ocid1.vault.oc1.eu-frankfurt-1.xxx"
  compartment_id: "ocid1.compartment.oc1..xxx"
  region: "eu-frankfurt-1"
  auth_method: "config_file"  # or "instance_principal"
  config_file: "~/.oci/config"
  config_profile: "DEFAULT"

cache:
  directory: "~/.cache/oci-vault-mcp"
  ttl: 3600
  enable_stale_fallback: true

resilience:
  enable_circuit_breaker: true
  circuit_breaker_threshold: 5
  max_retries: 3

secrets:
  # Environment variable → OCI Vault secret name mappings
  GITHUB_PERSONAL_ACCESS_TOKEN: "mcp-github-token"
  ANTHROPIC_API_KEY: "mcp-anthropic-key"
  POSTGRES_PASSWORD: "mcp-postgres-password"

logging:
  level: "INFO"
  verbose: false
```

#### Instance Methods

##### resolve_secret()

Resolve a secret from OCI Vault.

```python
def resolve_secret(
    self,
    vault_url_or_name: str,
    compartment_id: Optional[str] = None
) -> Optional[str]
```

**Parameters**:
- `vault_url_or_name` (str): Either:
  - Vault URL: `oci-vault://compartment-id/secret-name` or `oci-vault://secret-ocid`
  - Secret name: `"mcp-github-token"` (requires compartment_id or default_compartment_id)
  - Secret OCID: `"ocid1.vaultsecret.oc1.xxx"`
- `compartment_id` (Optional[str]): Override default compartment ID

**Returns**: `Optional[str]` - Decrypted secret value or None if not found

**Raises**:
- `AuthenticationError`: OCI authentication failed
- `PermissionDeniedError`: IAM permissions insufficient
- `InvalidVaultURLError`: Malformed vault URL
- `VaultResolverError`: General resolution error

**Examples**:

```python
# Using vault URL (explicit compartment)
secret = resolver.resolve_secret(
    "oci-vault://ocid1.compartment.oc1..xxx/mcp-github-token"
)

# Using secret name (requires default_compartment_id set)
secret = resolver.resolve_secret("mcp-github-token")

# Using secret OCID directly
secret = resolver.resolve_secret(
    "ocid1.vaultsecret.oc1.eu-frankfurt-1.xxx"
)

# Override compartment
secret = resolver.resolve_secret(
    "mcp-github-token",
    compartment_id="ocid1.compartment.oc1..other"
)
```

##### fetch_secrets_parallel()

Resolve multiple secrets in parallel for improved performance.

```python
def fetch_secrets_parallel(
    self,
    secret_refs: List[str],
    max_workers: int = 5
) -> Dict[str, Optional[str]]
```

**Parameters**:
- `secret_refs` (List[str]): List of vault URLs or secret names
- `max_workers` (int): Maximum parallel workers (default: 5)

**Returns**: `Dict[str, Optional[str]]` - Mapping of secret reference to value

**Example**:

```python
secrets = resolver.fetch_secrets_parallel([
    "mcp-github-token",
    "mcp-anthropic-key",
    "mcp-postgres-password"
], max_workers=3)

# Result: {
#     "mcp-github-token": "ghp_...",
#     "mcp-anthropic-key": "sk-ant-...",
#     "mcp-postgres-password": "db_password"
# }
```

##### resolve_config()

Resolve all vault references in a configuration dictionary.

```python
def resolve_config(
    self,
    config: Dict[str, Any],
    in_place: bool = False
) -> Dict[str, Any]
```

**Parameters**:
- `config` (Dict[str, Any]): Configuration dictionary with vault references
- `in_place` (bool): Modify config in place (default: False, creates copy)

**Returns**: `Dict[str, Any]` - Configuration with secrets resolved

**Example**:

```python
config = {
    "database": {
        "password": "oci-vault://ocid1.compartment/db-password"
    },
    "api_keys": {
        "github": "oci-vault://mcp-github-token",
        "anthropic": "oci-vault://mcp-anthropic-key"
    }
}

resolved = resolver.resolve_config(config)

# Result: {
#     "database": {
#         "password": "actual_db_password"
#     },
#     "api_keys": {
#         "github": "ghp_actual_token",
#         "anthropic": "sk-ant-actual_key"
#     }
# }
```

---

## Configuration

### Environment Variable Overrides

Configuration values can be overridden via environment variables:

| Environment Variable | Config Path | Description |
|---------------------|-------------|-------------|
| `OCI_VAULT_ID` | `vault.vault_id` | Vault OCID |
| `OCI_VAULT_COMPARTMENT_ID` | `vault.compartment_id` | Compartment OCID |
| `OCI_REGION` | `vault.region` | OCI region |
| `OCI_USE_INSTANCE_PRINCIPALS` | `vault.auth_method` | Set to "true" for instance principal auth |
| `OCI_CONFIG_FILE` | `vault.config_file` | Path to OCI config |
| `OCI_CONFIG_PROFILE` | `vault.config_profile` | OCI config profile name |
| `OCI_VAULT_ENVIRONMENT` | - | Environment selector (production, development, staging) |

**Example**:

```bash
export OCI_VAULT_ID="ocid1.vault.oc1.eu-frankfurt-1.xxx"
export OCI_VAULT_COMPARTMENT_ID="ocid1.compartment.oc1..xxx"
export OCI_REGION="eu-frankfurt-1"
export OCI_VAULT_ENVIRONMENT="production"

# Environment variables take precedence over config file
python3 mcp_vault_proxy.py --service github
```

---

## Secret Resolution

### Vault URL Format

```
oci-vault://[compartment-ocid/]secret-name-or-ocid
```

**Supported Formats**:

1. **Secret Name with Compartment**:
   ```
   oci-vault://ocid1.compartment.oc1..xxx/mcp-github-token
   ```

2. **Secret Name (requires default_compartment_id)**:
   ```
   oci-vault://mcp-github-token
   ```

3. **Secret OCID**:
   ```
   oci-vault://ocid1.vaultsecret.oc1.eu-frankfurt-1.xxx
   ```

### Secret Naming Convention

**Pattern**: `mcp-{service}-{credential-type}[-{environment}]`

**Examples**:

| Secret Name | Description |
|-------------|-------------|
| `mcp-github-token` | GitHub Personal Access Token (default env) |
| `mcp-github-token-prod` | GitHub PAT for production |
| `mcp-anthropic-key` | Anthropic API key |
| `mcp-postgres-password` | PostgreSQL password |
| `mcp-openai-key-dev` | OpenAI key for development |

---

## Error Handling

### Exception Hierarchy

```
VaultResolverError (base)
├── AuthenticationError
├── PermissionDeniedError
├── SecretNotFoundError
├── InvalidVaultURLError
└── ConfigurationError
```

### Exception Details

#### VaultResolverError

Base exception for all vault-related errors.

```python
class VaultResolverError(Exception):
    """Base exception for vault resolver errors"""
    pass
```

#### AuthenticationError

Raised when OCI authentication fails.

```python
class AuthenticationError(VaultResolverError):
    """Authentication with OCI failed"""
    pass
```

**Common Causes**:
- Invalid OCI config file (~/.oci/config)
- Expired session token
- Missing instance principal permissions

#### PermissionDeniedError

Raised when IAM permissions are insufficient.

```python
class PermissionDeniedError(VaultResolverError):
    """Insufficient IAM permissions for vault access"""
    def __init__(self, message: str, secret_name: Optional[str] = None):
        super().__init__(message)
        self.secret_name = secret_name
```

**Required IAM Policy**:
```
allow group YourGroup to read secret-bundles in compartment YourCompartment
```

#### SecretNotFoundError

Raised when secret doesn't exist in vault.

```python
class SecretNotFoundError(VaultResolverError):
    """Secret not found in OCI Vault"""
    def __init__(self, message: str, secret_name: Optional[str] = None):
        super().__init__(message)
        self.secret_name = secret_name
```

#### InvalidVaultURLError

Raised when vault URL is malformed.

```python
class InvalidVaultURLError(VaultResolverError):
    """Invalid vault URL format"""
    def __init__(self, message: str, url: Optional[str] = None):
        super().__init__(message)
        self.url = url
```

**Valid URL Format**: `oci-vault://[compartment-id/]secret-name-or-ocid`

### Error Handling Example

```python
from oci_vault_resolver import (
    VaultResolver,
    AuthenticationError,
    PermissionDeniedError,
    SecretNotFoundError
)

resolver = VaultResolver.from_config()

try:
    secret = resolver.resolve_secret("mcp-github-token")
except AuthenticationError as e:
    print(f"Authentication failed: {e}")
    print("Check ~/.oci/config or use 'oci session authenticate'")
except PermissionDeniedError as e:
    print(f"Permission denied for secret '{e.secret_name}': {e}")
    print("Verify IAM policy grants 'read secret-bundles' permission")
except SecretNotFoundError as e:
    print(f"Secret not found: {e.secret_name}")
    print(f"List secrets: oci vault secret list --compartment-id {resolver.default_compartment_id}")
except Exception as e:
    print(f"Unexpected error: {e}")
```

---

## Caching

### Cache Behavior

The resolver caches decrypted secrets to reduce vault API calls and improve performance.

**Cache Location**: `~/.cache/oci-vault-mcp/` (configurable)

**Cache File Format**: `{secret_ocid}.cache`

**Cache Structure**:
```python
{
    "value": "decrypted_secret_value",
    "timestamp": 1704758400.123,  # Unix timestamp
    "ttl": 3600,  # Cache TTL in seconds
    "metadata": {
        "secret_name": "mcp-github-token",
        "compartment_id": "ocid1.compartment.oc1..xxx"
    }
}
```

### Cache Methods

#### get_cached_secret()

Retrieve secret from cache if valid.

```python
def get_cached_secret(
    self,
    secret_ocid: str
) -> Optional[str]
```

**Returns**: `Optional[str]` - Cached value or None if cache miss/expired

#### cache_secret()

Store secret in cache.

```python
def cache_secret(
    self,
    secret_ocid: str,
    value: str,
    metadata: Optional[Dict[str, Any]] = None
) -> None
```

### Stale Cache Fallback

When enabled (`enable_stale_fallback=True`), resolver uses stale cache if vault is unavailable.

**Use Case**: Vault outage or network issues

**Example**:

```python
# Cache expired 10 minutes ago, but vault is unreachable
# With stale fallback enabled, returns cached value
secret = resolver.resolve_secret("mcp-github-token")
# Logs warning: "Using stale cache (10 minutes old)"
```

---

## Circuit Breaker

### Purpose

Prevents cascading failures by temporarily stopping vault requests when error threshold is reached.

### States

```
CLOSED (normal operation)
    ↓ (threshold failures)
OPEN (reject requests, use cache)
    ↓ (timeout elapsed)
HALF_OPEN (test one request)
    ↓ (success)
CLOSED
```

### Configuration

```python
VaultResolver(
    enable_circuit_breaker=True,
    circuit_breaker_threshold=5,  # Open after 5 failures
    # Circuit stays open for 60s, then enters HALF_OPEN
)
```

### Example Behavior

```python
# 5 consecutive vault failures → circuit opens
for i in range(5):
    try:
        resolver.resolve_secret("mcp-github-token")
    except VaultResolverError:
        print(f"Failure {i+1}/5")

# Circuit now OPEN - returns cached value immediately
secret = resolver.resolve_secret("mcp-github-token")
# No vault API call made, uses cache or stale cache
```

---

## Command-Line Interface

### mcp_vault_proxy.py

Generic wrapper for executing MCP servers with OCI Vault secret injection.

#### Usage

```bash
python3 mcp_vault_proxy.py [OPTIONS]
```

#### Options

| Option | Description | Required | Default |
|--------|-------------|----------|---------|
| `--service` | Service name (github, postgres, custom) | Yes | - |
| `--config` | Path to resolver.yaml config file | No | Search default locations |
| `--env`, `--environment` | Environment name (production, development) | No | - |
| `--command` | Custom command to execute | No | Service default |
| `--verbose`, `-v` | Enable verbose logging | No | False |

#### Examples

**GitHub MCP Server**:
```bash
python3 mcp_vault_proxy.py --service github
```

**PostgreSQL with Production Environment**:
```bash
python3 mcp_vault_proxy.py \
  --service postgres \
  --env production \
  --config /etc/oci-vault-mcp/resolver.yaml
```

**Custom Command**:
```bash
python3 mcp_vault_proxy.py \
  --service custom \
  --command "python3 /path/to/my_server.py" \
  --config ./resolver.yaml
```

**Verbose Logging**:
```bash
python3 mcp_vault_proxy.py \
  --service github \
  --verbose
```

#### Default Service Commands

| Service | Command |
|---------|---------|
| `github` | `npx -y @modelcontextprotocol/server-github` |
| `postgres`, `postgresql` | `npx -y @modelcontextprotocol/server-postgres` |
| `sqlite` | `npx -y @modelcontextprotocol/server-sqlite` |
| `mysql` | `npx -y @modelcontextprotocol/server-mysql` |
| `mongodb` | `npx -y @modelcontextprotocol/server-mongodb` |
| `redis` | `npx -y @modelcontextprotocol/server-redis` |
| `filesystem` | `npx -y @modelcontextprotocol/server-filesystem` |
| `docker` | `npx -y @modelcontextprotocol/server-docker` |
| `kubernetes` | `npx -y @modelcontextprotocol/server-kubernetes` |
| `aws` | `npx -y @modelcontextprotocol/server-aws` |
| `gcp` | `npx -y @modelcontextprotocol/server-gcp` |
| `azure` | `npx -y @modelcontextprotocol/server-azure` |

---

## Performance Metrics

### Logging

The resolver logs performance metrics for secret resolution:

```python
resolver.log_performance_metrics()
```

**Metrics Tracked**:
- Total resolution attempts
- Cache hits vs misses
- Average resolution time
- Vault API call count
- Circuit breaker state changes

**Example Output**:
```
[INFO] Performance Metrics:
  Total Resolutions: 150
  Cache Hits: 142 (94.7%)
  Cache Misses: 8 (5.3%)
  Avg Resolution Time: 12ms
  Vault API Calls: 8
  Circuit Breaker Opens: 0
```

---

## Related Documentation

- [User Guide](USER_GUIDE.md) - Setup and usage tutorials
- [Architecture](ARCHITECTURE.md) - System design and components
- [Troubleshooting](TROUBLESHOOTING.md) - Common issues and solutions
- [Migration Guide](MIGRATION_v1_to_v2.md) - Upgrading from v1.x
- [Security](SECURITY.md) - Security best practices and IAM policies
