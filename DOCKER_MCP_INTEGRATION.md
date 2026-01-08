# Docker MCP Gateway Integration with OCI Vault

This guide shows how to use the OCI Vault Resolver with Docker MCP Gateway to securely fetch secrets from Oracle Cloud Infrastructure Vault instead of storing them in environment variables or Docker secrets.

## Overview

The integration provides:
- ✅ **Secure secret storage** in OCI Vault instead of local environment variables
- ✅ **Automatic secret resolution** when starting MCP servers
- ✅ **Phase 3 resilience features**: Circuit breaker, retry with backoff, secret versioning
- ✅ **Zero plaintext secrets** in configuration files or command line

## Architecture

```
┌─────────────────────┐
│  Docker MCP Gateway │
└──────────┬──────────┘
           │
           │ starts
           ▼
┌──────────────────────────┐
│ github_mcp_proxy.py      │
│ (OCI Vault Integration)  │
└──────────┬───────────────┘
           │
           │ 1. Fetch PAT from OCI Vault
           ▼
┌──────────────────────────┐
│  OCI Vault Resolver      │
│  (oci_vault_resolver.py) │
└──────────┬───────────────┘
           │
           │ 2. Resolve secret
           ▼
┌──────────────────────────┐
│  Oracle Cloud Vault      │
│  (AC-vault, Frankfurt)   │
└──────────────────────────┘
           │
           │ 3. Returns GitHub PAT
           ▼
┌──────────────────────────┐
│  GitHub MCP Server       │
│  (@modelcontextprotocol/ │
│   server-github)         │
└──────────────────────────┘
```

## Prerequisites

1. **OCI Vault Setup**
   - OCI account with configured credentials (`~/.oci/config`)
   - GitHub PAT stored in OCI Vault (see below)
   - IAM permissions to read secrets from vault

2. **Docker MCP Gateway**
   - Docker Desktop with MCP Toolkit enabled
   - `docker mcp` command available

3. **Python Environment**
   - Python 3.8+
   - `oci-vault-mcp-resolver` installed (this package)

## Setup Guide

### Step 1: Store GitHub PAT in OCI Vault

If you haven't already stored your GitHub Personal Access Token in OCI Vault:

```bash
# Create a GitHub PAT at https://github.com/settings/personal-access-tokens/new
# Then upload it to OCI Vault:

./scripts/upload-secret.sh running-days-github-token "ghp_YOUR_TOKEN_HERE"
```

### Step 2: Test OCI Vault Resolution

Verify the resolver can fetch your GitHub token:

```bash
python3 -c "
from oci_vault_resolver import VaultResolver

resolver = VaultResolver(config_file='~/.oci/config', verbose=True)
vault_url = 'oci-vault://ocid1.vaultsecret.oc1.eu-frankfurt-1.amaaaaaahhxc6pya5mp5alyg7cai5563xzl6i7x5ecuzgnfhj5bqijyapwya'

token = resolver.resolve_secret(vault_url)
print(f'✅ Token resolved: {token[:10]}...' if token else '❌ Failed')
"
```

Expected output:
```
✅ Token resolved: ghp_rZV5NL...
```

### Step 3: Configure Docker MCP Gateway

The proxy script (`github_mcp_proxy.py`) acts as a transparent wrapper that:
1. Fetches the GitHub PAT from OCI Vault
2. Sets `GITHUB_PERSONAL_ACCESS_TOKEN` environment variable
3. Delegates to the official GitHub MCP server

To use it with Docker MCP Gateway, you have two options:

#### Option A: Direct Script Execution (Recommended for Testing)

Test the proxy directly:

```bash
# Start the GitHub MCP proxy
cd /home/alex/projects/oci-vault-mcp-resolver
./github_mcp_proxy.py
```

The proxy will:
1. Fetch GitHub PAT from OCI Vault
2. Start the official GitHub MCP server with the token
3. Handle all MCP protocol communication

#### Option B: Docker MCP Gateway Integration

Create a custom MCP server entry in your Docker MCP config:

```yaml
# ~/.docker/mcp/config.yaml
servers:
  github-vault:
    # Custom GitHub server with OCI Vault integration
    command: python3
    args:
      - /home/alex/projects/oci-vault-mcp-resolver/github_mcp_proxy.py
    env:
      # No GITHUB_PERSONAL_ACCESS_TOKEN needed - fetched from vault!
      PATH: /usr/bin:/bin
```

Then enable it:

```bash
docker mcp config write "$(cat ~/.docker/mcp/config.yaml)"
docker mcp gateway run
```

## Usage Examples

### Example 1: List GitHub Repositories

Once the proxy is running, you can use GitHub MCP tools:

```json
{
  "method": "tools/call",
  "params": {
    "name": "list_repositories",
    "arguments": {
      "username": "anthropics"
    }
  }
}
```

### Example 2: Search Code Across GitHub

```json
{
  "method": "tools/call",
  "params": {
    "name": "search_code",
    "arguments": {
      "query": "language:python class VaultResolver"
    }
  }
}
```

## Security Benefits

Compared to traditional approaches:

| Approach | Security Level | Vault Integration |
|----------|---------------|-------------------|
| **Plaintext in config** | ❌ Low | No |
| **Environment variables** | ⚠️ Medium | No |
| **Docker secrets** | ✅ Good | No |
| **OCI Vault + Resolver** | ✅✅ Excellent | Yes |

**OCI Vault advantages:**
- ✅ Centralized secret management
- ✅ Audit logs for secret access
- ✅ Automatic secret rotation support
- ✅ Fine-grained IAM permissions
- ✅ Encryption at rest and in transit
- ✅ Secret versioning

## Troubleshooting

### Error: "Failed to initialize OCI SDK clients"

**Cause:** Missing or invalid OCI config file

**Fix:**
```bash
# Verify OCI config exists
ls -la ~/.oci/config

# Test OCI authentication
oci iam region list
```

### Error: "Circuit breaker is OPEN"

**Cause:** Too many consecutive failures to OCI Vault API

**Fix:**
```python
# Temporarily disable circuit breaker for debugging
resolver = VaultResolver(
    enable_circuit_breaker=False,
    verbose=True
)
```

### Warning: "Token doesn't have expected format"

**Cause:** Retrieved secret is not a valid GitHub PAT

**Fix:**
```bash
# Verify the secret value in OCI Vault
oci secrets secret-bundle get \
  --secret-id ocid1.vaultsecret.oc1.eu-frankfurt-1.amaaaaaahhxc6pya5mp5alyg7cai5563xzl6i7x5ecuzgnfhj5bqijyapwya
```

## Performance Metrics

The OCI Vault Resolver tracks performance metrics:

```python
print(resolver.metrics)
# {
#   'secrets_fetched': 1,
#   'cache_hits': 0,
#   'cache_misses': 1,
#   'retries': 0,
#   'circuit_breaker_opens': 0,
#   'total_fetch_time': 0.234
# }
```

## Advanced Configuration

### Custom Retry Settings

```python
# Increase retries for unreliable networks
resolver = VaultResolver(
    max_retries=5,
    retry_backoff_base=3.0,  # Longer backoff
    verbose=True
)
```

### Secret Versioning

Fetch a specific version of the GitHub token:

```python
vault_url = 'oci-vault://ocid1.vaultsecret...?version=2'
token = resolver.resolve_secret(vault_url)
```

### Circuit Breaker Tuning

```python
# More aggressive circuit breaker
resolver = VaultResolver(
    enable_circuit_breaker=True,
    circuit_breaker_threshold=3,  # Open after 3 failures
    circuit_breaker_recovery_timeout=30.0  # 30s recovery
)
```

## Related Documentation

- [OCI Vault Resolver README](README.md)
- [Phase 3 Features](CHANGELOG.md#130---2026-01-08)
- [API Reference](API_REFERENCE.md)
- [Docker MCP Gateway](https://github.com/docker/mcp-gateway)

## License

MIT License - Same as oci-vault-mcp-resolver
