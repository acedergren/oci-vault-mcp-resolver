# Docker MCP Gateway Integration with OCI Vault

This guide shows how to use the OCI Vault Resolver with Docker MCP Gateway to securely fetch secrets from Oracle Cloud Infrastructure Vault instead of storing them in environment variables or Docker secrets.

## Overview

The integration provides:
- ✅ **Secure secret storage** in OCI Vault instead of local environment variables
- ✅ **Automatic secret resolution** when starting MCP servers
- ✅ **Multi-service support**: GitHub, PostgreSQL, Anthropic, and any MCP server requiring secrets
- ✅ **Configuration-driven**: JSON config files, no hardcoded OCIDs in code
- ✅ **Environment selection**: development, staging, production configs
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
│ mcp_vault_proxy.py       │
│ --service github         │
│ (Generic OCI Wrapper)    │
└──────────┬───────────────┘
           │
           │ 1. Load service config (configs/github.json)
           ▼
┌──────────────────────────┐
│  OCI Vault Resolver      │
│  (oci_vault_resolver.py) │
└──────────┬───────────────┘
           │
           │ 2. Resolve secrets via config references
           ▼
┌──────────────────────────┐
│  Oracle Cloud Vault      │
│  (Any OCI region/vault)  │
└──────────────────────────┘
           │
           │ 3. Returns secrets (PAT, API key, password, etc.)
           ▼
┌──────────────────────────┐
│  Target MCP Server       │
│  (GitHub, PostgreSQL,    │
│   Anthropic, Custom...)  │
└──────────────────────────┘
```

## Prerequisites

1. **OCI Vault Setup**
   - OCI account with configured credentials (`~/.oci/config`)
   - Secrets stored in OCI Vault (GitHub PAT, API keys, database passwords, etc.)
   - IAM permissions to read secrets from vault

2. **Docker MCP Gateway**
   - Docker Desktop with MCP Toolkit enabled
   - `docker mcp` command available

3. **Python Environment**
   - Python 3.8+
   - `oci-vault-mcp-resolver` installed (this package)

## Setup Guide

### Step 1: Store Secrets in OCI Vault

Upload secrets to OCI Vault using the provided script:

```bash
# GitHub Personal Access Token
# Create at: https://github.com/settings/personal-access-tokens/new
./scripts/upload-secret.sh my-github-token "ghp_YOUR_TOKEN_HERE"

# Anthropic API Key
./scripts/upload-secret.sh my-anthropic-api-key "sk-ant-YOUR_KEY_HERE"

# PostgreSQL Password
./scripts/upload-secret.sh my-postgres-password "secure_password_123"
```

### Step 2: Create Service Configuration

Create a JSON config file for each MCP service in `configs/`:

**Example: `configs/github.json`**
```json
{
  "description": "GitHub MCP server with OCI Vault integration",
  "secrets": {
    "GITHUB_PERSONAL_ACCESS_TOKEN": {
      "secret_name": "my-github-token",
      "environment": {
        "development": "my-github-token-dev",
        "production": "my-github-token-prod"
      }
    }
  },
  "target_command": ["npx", "-y", "@modelcontextprotocol/server-github"]
}
```

**Example: `configs/postgres.json`**
```json
{
  "description": "PostgreSQL MCP server",
  "secrets": {
    "POSTGRES_PASSWORD": {
      "secret_name": "my-postgres-password"
    }
  },
  "target_command": ["npx", "-y", "@modelcontextprotocol/server-postgres"]
}
```

**Example: `configs/anthropic.json`**
```json
{
  "description": "Anthropic API integration",
  "secrets": {
    "ANTHROPIC_API_KEY": {
      "secret_name": "my-anthropic-api-key",
      "environment": {
        "production": "my-anthropic-api-key-prod",
        "staging": "my-anthropic-api-key-staging"
      }
    }
  },
  "target_command": ["custom-anthropic-mcp-server"]
}
```

### Step 3: Test OCI Vault Resolution

Verify the resolver can fetch secrets using your config:

```bash
# Test GitHub config
python3 mcp_vault_proxy.py --service github --test

# Test with specific environment
python3 mcp_vault_proxy.py --service github --env production --test

# Test all configured services
python3 mcp_vault_proxy.py --service postgres --test
python3 mcp_vault_proxy.py --service anthropic --test
```

Expected output:
```
✅ Service config loaded: github
✅ Secret resolved: GITHUB_PERSONAL_ACCESS_TOKEN = ghp_rZV5NL...
✅ Target command: npx -y @modelcontextprotocol/server-github
```

### Step 4: Configure Docker MCP Gateway

The generic proxy script (`mcp_vault_proxy.py`) acts as a transparent wrapper that:
1. Loads service configuration from JSON file
2. Fetches all required secrets from OCI Vault
3. Sets environment variables
4. Delegates to the target MCP server

#### Option A: Direct Script Execution (Recommended for Testing)

Test the proxy directly:

```bash
# Start GitHub MCP with vault integration
cd /path/to/oci-vault-mcp-resolver
python3 mcp_vault_proxy.py --service github

# Start with specific environment
python3 mcp_vault_proxy.py --service github --env production

# Start PostgreSQL MCP
python3 mcp_vault_proxy.py --service postgres

# Start Anthropic MCP
python3 mcp_vault_proxy.py --service anthropic --env staging
```

The proxy will:
1. Load configuration from `configs/<service>.json`
2. Fetch all secrets from OCI Vault based on environment
3. Start the target MCP server with secrets as environment variables
4. Handle all MCP protocol communication transparently

#### Option B: Docker MCP Gateway Integration

Create custom MCP server entries in your Docker MCP config:

```yaml
# ~/.docker/mcp/config.yaml
servers:
  # GitHub with OCI Vault
  github-vault:
    command: python3
    args:
      - /path/to/oci-vault-mcp-resolver/mcp_vault_proxy.py
      - --service
      - github
      - --env
      - production
    env:
      PATH: /usr/bin:/bin
      # No secrets needed - fetched from vault!

  # PostgreSQL with OCI Vault
  postgres-vault:
    command: python3
    args:
      - /path/to/oci-vault-mcp-resolver/mcp_vault_proxy.py
      - --service
      - postgres
    env:
      PATH: /usr/bin:/bin

  # Anthropic with OCI Vault
  anthropic-vault:
    command: python3
    args:
      - /path/to/oci-vault-mcp-resolver/mcp_vault_proxy.py
      - --service
      - anthropic
      - --env
      - production
    env:
      PATH: /usr/bin:/bin
```

Then enable them:

```bash
# Write config
docker mcp config write "$(cat ~/.docker/mcp/config.yaml)"

# Start gateway
docker mcp gateway run

# Or add individual servers
docker mcp add github-vault
docker mcp add postgres-vault
docker mcp add anthropic-vault
```

## Usage Examples

### Example 1: GitHub - List Repositories

Once the GitHub proxy is running, you can use GitHub MCP tools:

```json
{
  "method": "tools/call",
  "params": {
    "name": "search_repositories",
    "arguments": {
      "query": "org:anthropics language:python"
    }
  }
}
```

### Example 2: GitHub - Search Code

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

### Example 3: PostgreSQL - Query Database

With the PostgreSQL proxy running:

```json
{
  "method": "tools/call",
  "params": {
    "name": "query",
    "arguments": {
      "sql": "SELECT * FROM users LIMIT 10"
    }
  }
}
```

### Example 4: Multi-Service Workflow

Run multiple services simultaneously:

```bash
# Terminal 1: GitHub MCP (production secrets)
python3 mcp_vault_proxy.py --service github --env production

# Terminal 2: PostgreSQL MCP (development secrets)
python3 mcp_vault_proxy.py --service postgres --env development

# Terminal 3: Anthropic MCP (staging secrets)
python3 mcp_vault_proxy.py --service anthropic --env staging
```

All services fetch their secrets from OCI Vault independently.

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

## Environment Selection

The proxy supports environment-specific secrets via the `--env` flag:

```bash
# Use default secret (no environment specified)
python3 mcp_vault_proxy.py --service github

# Use development environment
python3 mcp_vault_proxy.py --service github --env development

# Use production environment
python3 mcp_vault_proxy.py --service github --env production

# Use staging environment
python3 mcp_vault_proxy.py --service anthropic --env staging
```

**How it works:**

1. Without `--env`: Uses the default `secret_name` from config
2. With `--env`: Looks up environment-specific secret name in `environment` map
3. Falls back to default if environment not found in config

**Example config with environments:**

```json
{
  "secrets": {
    "API_KEY": {
      "secret_name": "my-api-key-dev",
      "environment": {
        "staging": "my-api-key-staging",
        "production": "my-api-key-prod"
      }
    }
  }
}
```

## Troubleshooting

### Error: "Service config not found"

**Cause:** Missing or invalid service configuration file

**Fix:**
```bash
# Verify config file exists
ls -la configs/github.json

# Validate JSON syntax
python3 -m json.tool configs/github.json
```

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
```bash
# Check OCI Vault connectivity
oci secrets secret-bundle get --secret-id <your-secret-ocid>

# Restart proxy to reset circuit breaker
python3 mcp_vault_proxy.py --service github
```

### Error: "Secret not found in vault"

**Cause:** Secret name in config doesn't match vault secret

**Fix:**
```bash
# List secrets in vault
oci vault secret list --compartment-id <compartment-ocid>

# Update config with correct secret name
vim configs/github.json

# Test resolution
python3 mcp_vault_proxy.py --service github --test
```

### Warning: "Environment 'X' not found, using default"

**Cause:** Requested environment not defined in config

**Fix:**
```json
// Add environment to config
{
  "secrets": {
    "API_KEY": {
      "secret_name": "default-key",
      "environment": {
        "development": "dev-key",
        "staging": "staging-key",
        "production": "prod-key"
      }
    }
  }
}
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

### Custom Service Configuration

Create advanced configurations with multiple secrets and options:

```json
{
  "description": "Multi-secret MCP service",
  "secrets": {
    "DATABASE_URL": {
      "secret_name": "postgres-connection-string",
      "environment": {
        "production": "postgres-prod-url",
        "staging": "postgres-staging-url"
      }
    },
    "API_KEY": {
      "secret_name": "service-api-key"
    },
    "JWT_SECRET": {
      "secret_name": "jwt-signing-key",
      "environment": {
        "production": "jwt-prod-secret"
      }
    }
  },
  "target_command": ["node", "/path/to/custom-mcp-server.js"],
  "env_overrides": {
    "NODE_ENV": "production",
    "LOG_LEVEL": "info"
  }
}
```

### Secret Versioning

Specify secret versions in your configuration:

```json
{
  "secrets": {
    "API_KEY": {
      "secret_name": "my-api-key",
      "version": 2
    }
  }
}
```

Or use environment-specific versions:

```json
{
  "secrets": {
    "API_KEY": {
      "secret_name": "my-api-key",
      "environment": {
        "production": "my-api-key-prod"
      },
      "version": {
        "production": 3,
        "staging": 2
      }
    }
  }
}
```

### Custom OCI Configuration

Override default OCI config location:

```bash
# Use alternate OCI config file
export OCI_CONFIG_FILE=~/.oci/custom-config
python3 mcp_vault_proxy.py --service github

# Use specific profile
export OCI_CONFIG_PROFILE=PRODUCTION
python3 mcp_vault_proxy.py --service github --env production
```

### Proxy with Custom Arguments

Pass additional arguments to target MCP server:

```json
{
  "target_command": [
    "npx",
    "-y",
    "@modelcontextprotocol/server-github",
    "--owner",
    "my-org",
    "--repo",
    "my-repo"
  ]
}
```

## Configuration Best Practices

### Secret Naming Convention

Use consistent naming for vault secrets:

```
<project>-<service>-<secret-type>[-<environment>]

Examples:
- myapp-github-token-prod
- myapp-postgres-password-staging
- myapp-anthropic-api-key
- myapp-jwt-secret-dev
```

### Multi-Environment Strategy

**Option 1: Separate secrets per environment** (Recommended)
```json
{
  "secrets": {
    "API_KEY": {
      "secret_name": "default-api-key",
      "environment": {
        "development": "myapp-api-key-dev",
        "staging": "myapp-api-key-staging",
        "production": "myapp-api-key-prod"
      }
    }
  }
}
```

**Option 2: Single secret with versions**
```json
{
  "secrets": {
    "API_KEY": {
      "secret_name": "myapp-api-key",
      "version": {
        "development": 1,
        "staging": 2,
        "production": 3
      }
    }
  }
}
```

### Service Organization

```
configs/
├── github.json          # GitHub MCP server
├── postgres.json        # PostgreSQL MCP server
├── anthropic.json       # Anthropic API integration
├── custom-app.json      # Custom MCP server
└── templates/
    └── example.json     # Template for new services
```

### Security Checklist

- ✅ Never commit `configs/*.json` files containing OCIDs to public repos
- ✅ Use IAM policies to restrict secret access per service
- ✅ Enable OCI audit logging for secret access
- ✅ Rotate secrets regularly using secret versioning
- ✅ Use environment-specific secrets for production
- ✅ Test secret resolution with `--test` flag before deployment
- ✅ Monitor vault metrics for unusual access patterns

### Docker MCP Gateway Production Setup

```yaml
# ~/.docker/mcp/config.yaml (Production)
servers:
  github-prod:
    command: python3
    args:
      - /opt/oci-vault-mcp-resolver/mcp_vault_proxy.py
      - --service
      - github
      - --env
      - production
    env:
      OCI_CONFIG_FILE: /secrets/.oci/config
      OCI_CONFIG_PROFILE: PRODUCTION
      PATH: /usr/bin:/bin
    restart: always
    healthcheck:
      test: ["CMD", "python3", "-c", "import socket; socket.create_connection(('localhost', 8080))"]
      interval: 30s
      timeout: 10s
      retries: 3
```

## Comparison with Other Approaches

| Feature | OCI Vault + Resolver | Docker Secrets | Environment Variables | Plaintext Config |
|---------|---------------------|----------------|----------------------|------------------|
| **Centralized Management** | ✅ | ❌ | ❌ | ❌ |
| **Automatic Rotation** | ✅ | ⚠️ Manual | ❌ | ❌ |
| **Audit Logging** | ✅ | ⚠️ Limited | ❌ | ❌ |
| **Multi-Environment** | ✅ | ⚠️ Complex | ⚠️ Manual | ❌ |
| **Secret Versioning** | ✅ | ❌ | ❌ | ❌ |
| **IAM Integration** | ✅ | ⚠️ Limited | ❌ | ❌ |
| **Zero-Trust Ready** | ✅ | ⚠️ Partial | ❌ | ❌ |
| **Setup Complexity** | Medium | Low | Low | Low |
| **Runtime Overhead** | Low | Minimal | Minimal | Minimal |

## Related Documentation

- [OCI Vault Resolver README](README.md) - Core library documentation
- [Configuration Guide](CONFIG_GUIDE.md) - Detailed config file format
- [Phase 3 Features](CHANGELOG.md#130---2026-01-08) - Resilience features
- [API Reference](API_REFERENCE.md) - Python API documentation
- [Docker MCP Gateway](https://github.com/docker/mcp-gateway) - Official MCP Gateway docs

## License

MIT License - Same as oci-vault-mcp-resolver
