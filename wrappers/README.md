# OCI Vault MCP Wrappers

Generic wrappers for running MCP servers with OCI Vault secret resolution.

## Overview

The OCI Vault MCP wrapper allows you to:
- 🔐 Store sensitive credentials in OCI Vault instead of environment variables
- 🔄 Automatically resolve secrets at runtime using the `vault://` URI scheme
- 📦 Work with any MCP server without code changes
- 🐳 Integrate seamlessly with Docker MCP Gateway
- 🎯 Use service-specific secret naming patterns for multi-tenant security

## Quick Start

### 1. Create Vault Secrets

Store your secrets in OCI Vault using the naming pattern `mcp-{service}-{type}`:

```bash
# GitHub token
oci vault secret create-base64 \
  --compartment-id "ocid1.compartment.oc1..xxxxx" \
  --vault-id "ocid1.vault.oc1.region.xxxxx" \
  --secret-name "mcp-github-token" \
  --key-id "ocid1.key.oc1.region.xxxxx" \
  --secret-content-content "$(echo -n 'ghp_xxxxxxxxxxxx' | base64)"

# PostgreSQL connection URL
oci vault secret create-base64 \
  --compartment-id "ocid1.compartment.oc1..xxxxx" \
  --vault-id "ocid1.vault.oc1.region.xxxxx" \
  --secret-name "mcp-postgres-url" \
  --key-id "ocid1.key.oc1.region.xxxxx" \
  --secret-content-content "$(echo -n 'postgresql://user:pass@host:5432/db' | base64)"
```

### 2. Create Configuration File

Create a YAML config file (see `examples/` directory):

```yaml
# config/github.yaml
command: npx
args:
  - "-y"
  - "@modelcontextprotocol/server-github"

env:
  GITHUB_PERSONAL_ACCESS_TOKEN: "vault://mcp-github-token"
```

### 3. Run the Wrapper

```bash
# Direct execution
node wrappers/wrapper.js --config config/github.yaml

# Or with Docker MCP Gateway
# (Add to claude_desktop_config.json as shown below)
```

## Configuration Format

### Basic Structure

```yaml
# MCP server command to execute
command: npx
args:
  - "-y"
  - "@modelcontextprotocol/server-name"

# Environment variables with vault resolution
env:
  VAR_NAME: "vault://secret-name"
  STATIC_VAR: "static-value"
  MIXED_VAR: "${ENV_VAR_FALLBACK}"

# Optional: OCI Vault configuration (uses defaults if omitted)
vault:
  vaultId: "ocid1.vault.oc1.region.xxxxx"
  compartmentId: "ocid1.compartment.oc1..xxxxx"
  useInstancePrincipal: true
  region: "us-ashburn-1"
```

### Secret Resolution Patterns

The wrapper supports multiple secret resolution patterns:

| Pattern | Example | Description |
|---------|---------|-------------|
| Vault URI | `vault://mcp-service-token` | Fetches from OCI Vault |
| Env Variable | `${GITHUB_TOKEN}` | Falls back to local env var |
| Static Value | `production` | Uses literal value |
| Mixed | `https://${HOST}/api` | Combines patterns |

### Secret Naming Convention

Use the pattern `mcp-{service}-{type}` for vault secrets:

| Service | Secret Name | Purpose |
|---------|-------------|---------|
| GitHub | `mcp-github-token` | Personal access token |
| PostgreSQL | `mcp-postgres-url` | Connection URL |
| PostgreSQL | `mcp-postgres-password` | Password only |
| Anthropic | `mcp-anthropic-api-key` | Claude API key |
| OpenAI | `mcp-openai-api-key` | GPT API key |
| OpenAI | `mcp-openai-org-id` | Organization ID |
| Custom | `mcp-myservice-secret` | Your service secret |

**Why this pattern?**
- ✅ Namespace isolation (`mcp-*` prefix)
- ✅ Service grouping (easy to find related secrets)
- ✅ Type clarity (identifies what the secret contains)
- ✅ Multi-tenant safe (no collision with app secrets)

## Docker MCP Gateway Integration

### Setup

1. **Mount wrappers in container:**

```yaml
# docker-compose.yml
services:
  mcp-gateway:
    image: your-mcp-gateway
    volumes:
      - ./oci-vault-mcp-resolver/wrappers:/app/wrappers
      - ./oci-vault-mcp-resolver/dist:/app/dist
      - ./config:/app/config
      - ~/.oci:/root/.oci:ro  # OCI config for authentication
```

2. **Configure Claude Desktop:**

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "github": {
      "command": "docker",
      "args": [
        "exec",
        "mcp-gateway",
        "node",
        "/app/wrappers/wrapper.js",
        "--config",
        "/app/config/github.yaml"
      ]
    },
    "postgres": {
      "command": "docker",
      "args": [
        "exec",
        "mcp-gateway",
        "node",
        "/app/wrappers/wrapper.js",
        "--config",
        "/app/config/postgres.yaml"
      ]
    }
  }
}
```

3. **Restart Claude Desktop** to apply changes.

### Authentication Options

The wrapper supports multiple OCI authentication methods:

#### Option 1: Instance Principal (Production)

For OCI Compute instances:

```yaml
vault:
  useInstancePrincipal: true
  region: "us-ashburn-1"
```

Required IAM policy:
```
allow dynamic-group mcp-servers to read secret-bundles in compartment MyCompartment
```

#### Option 2: Config File (Development)

For local development with `~/.oci/config`:

```yaml
vault:
  configFile: "~/.oci/config"
  profile: "DEFAULT"
  region: "us-ashburn-1"
```

Required `~/.oci/config`:
```ini
[DEFAULT]
user=ocid1.user.oc1..xxxxx
fingerprint=xx:xx:xx:xx:xx:xx:xx:xx:xx:xx:xx:xx:xx:xx:xx:xx
tenancy=ocid1.tenancy.oc1..xxxxx
region=us-ashburn-1
key_file=~/.oci/oci_api_key.pem
```

#### Option 3: Environment Variables

Set vault config via environment:

```bash
export OCI_VAULT_ID="ocid1.vault.oc1.region.xxxxx"
export OCI_COMPARTMENT_ID="ocid1.compartment.oc1..xxxxx"
export OCI_REGION="us-ashburn-1"
export OCI_USE_INSTANCE_PRINCIPAL="true"

node wrappers/wrapper.js --config config/service.yaml
```

## Service Examples

### GitHub MCP Server

**Config:** `examples/github.yaml`

```yaml
command: npx
args:
  - "-y"
  - "@modelcontextprotocol/server-github"

env:
  GITHUB_PERSONAL_ACCESS_TOKEN: "vault://mcp-github-token"
```

**Setup:**
1. Create GitHub token at https://github.com/settings/tokens
2. Required scopes: `repo`, `read:org`, `read:user`
3. Store in vault: `mcp-github-token`

### PostgreSQL MCP Server

**Config:** `examples/postgres.yaml`

**Option A: Single connection URL**
```yaml
command: npx
args:
  - "-y"
  - "@modelcontextprotocol/server-postgres"

env:
  DATABASE_URL: "vault://mcp-postgres-url"
```

**Option B: Separate parameters**
```yaml
env:
  PGHOST: "vault://mcp-postgres-host"
  PGPORT: "5432"
  PGDATABASE: "vault://mcp-postgres-database"
  PGUSER: "vault://mcp-postgres-user"
  PGPASSWORD: "vault://mcp-postgres-password"
  PGSSLMODE: "require"
```

**Setup:**
1. Store connection details in vault
2. Use `mcp-postgres-*` naming pattern
3. Format URL: `postgresql://user:pass@host:5432/database`

### Anthropic API (Claude)

**Config:** `examples/anthropic.yaml`

```yaml
command: node
args:
  - "/path/to/your/anthropic-mcp-server.js"

env:
  ANTHROPIC_API_KEY: "vault://mcp-anthropic-api-key"
```

**Setup:**
1. Get API key from https://console.anthropic.com/settings/keys
2. Store in vault: `mcp-anthropic-api-key`
3. Format: `sk-ant-api03-...`

### OpenAI API (ChatGPT)

**Config:** `examples/openai.yaml`

```yaml
command: node
args:
  - "/path/to/your/openai-mcp-server.js"

env:
  OPENAI_API_KEY: "vault://mcp-openai-api-key"
  OPENAI_ORG_ID: "vault://mcp-openai-org-id"
```

**Setup:**
1. Get API key from https://platform.openai.com/api-keys
2. Store in vault: `mcp-openai-api-key`, `mcp-openai-org-id`
3. Format: `sk-proj-...`

## Custom Service Configuration

### Creating a New Service Config

1. **Identify required environment variables** for your MCP server
2. **Create vault secrets** using `mcp-{service}-{type}` pattern
3. **Write config file:**

```yaml
command: node
args:
  - "/path/to/your/mcp-server.js"

env:
  # Required variables
  SERVICE_API_KEY: "vault://mcp-myservice-api-key"
  SERVICE_ENDPOINT: "https://api.myservice.com"

  # Optional variables with fallback
  SERVICE_TIMEOUT: "${SERVICE_TIMEOUT:-30000}"
```

4. **Test locally:**
```bash
node wrappers/wrapper.js --config config/myservice.yaml
```

5. **Add to Docker MCP Gateway** (if using):
```json
{
  "myservice": {
    "command": "docker",
    "args": [
      "exec", "mcp-gateway",
      "node", "/app/wrappers/wrapper.js",
      "--config", "/app/config/myservice.yaml"
    ]
  }
}
```

### Environment Variable Patterns

| Use Case | Pattern | Example |
|----------|---------|---------|
| Vault secret | `vault://secret-name` | `vault://mcp-github-token` |
| Env fallback | `${VAR_NAME}` | `${GITHUB_TOKEN}` |
| Default value | `${VAR:-default}` | `${PORT:-3000}` |
| Static value | `literal` | `production` |
| Interpolation | `prefix-${VAR}` | `https://${HOST}/api` |

## Troubleshooting

### Secret Not Found

**Error:** `Failed to fetch secret: mcp-service-token`

**Solutions:**
1. Verify secret exists in vault:
   ```bash
   oci vault secret list \
     --compartment-id "ocid1.compartment.oc1..xxxxx" \
     --vault-id "ocid1.vault.oc1.region.xxxxx" \
     --query 'data[?starts_with("secret-name", `mcp-`)].{Name:"secret-name"}' \
     --output table
   ```

2. Check IAM permissions:
   ```
   allow group MyGroup to read secret-bundles in compartment MyCompartment
   ```

3. Verify vault configuration in YAML matches actual vault OCID

### Authentication Failed

**Error:** `NotAuthenticated: Could not authenticate with OCI`

**Solutions:**
1. For Instance Principal:
   - Verify dynamic group membership
   - Check IAM policy grants `read secret-bundles`

2. For Config File:
   - Verify `~/.oci/config` exists and is readable
   - Check API key fingerprint matches
   - Ensure private key file exists at `key_file` path

3. Test OCI CLI works:
   ```bash
   oci iam region list
   ```

### MCP Server Not Starting

**Error:** MCP server exits immediately or hangs

**Solutions:**
1. Test command manually:
   ```bash
   export VAR_NAME="test-value"
   npx -y @modelcontextprotocol/server-name
   ```

2. Check MCP server logs:
   - Wrapper forwards stdout/stderr
   - Look for initialization errors
   - Verify required environment variables are set

3. Validate config syntax:
   ```bash
   node -e "console.log(require('js-yaml').load(require('fs').readFileSync('config/service.yaml')))"
   ```

### Docker Volume Mounting

**Error:** `Cannot find module '/app/wrappers/wrapper.js'`

**Solutions:**
1. Verify volume mount in `docker-compose.yml`:
   ```yaml
   volumes:
     - ./oci-vault-mcp-resolver/wrappers:/app/wrappers
   ```

2. Check container path:
   ```bash
   docker exec mcp-gateway ls -la /app/wrappers
   ```

3. Ensure wrapper.js has execute permissions:
   ```bash
   chmod +x wrappers/wrapper.js
   ```

## Development

### Testing Changes

```bash
# Build the resolver library
cd oci-vault-mcp-resolver
pnpm build

# Test wrapper with example config
node wrappers/wrapper.js --config wrappers/examples/github.yaml

# Test with custom config
node wrappers/wrapper.js --config /path/to/myconfig.yaml
```

### Adding Debug Logging

Enable debug output:

```bash
# Wrapper debug logs
DEBUG=oci-vault-mcp-wrapper node wrappers/wrapper.js --config config/service.yaml

# OCI SDK debug logs
DEBUG=* node wrappers/wrapper.js --config config/service.yaml
```

### Creating Service Templates

To add a new service template:

1. Create `examples/{service}.yaml`
2. Document required vault secrets
3. Add to this README under "Service Examples"
4. Test with actual MCP server

## Security Best Practices

1. **Never commit secrets to git:**
   - Use `.gitignore` for `*.env` files
   - Store all secrets in OCI Vault
   - Use `vault://` URIs in configs

2. **Rotate secrets regularly:**
   ```bash
   # Create new secret version
   oci vault secret update-base64 \
     --secret-id "ocid1.vaultsecret.oc1..xxxxx" \
     --secret-content-content "$(echo -n 'new-secret-value' | base64)"
   ```

3. **Use IAM policies for least privilege:**
   ```
   # Allow only read access to specific secrets
   allow group MCP-Users to read secret-bundles in compartment MyCompartment where target.secret.name = 'mcp-*'
   ```

4. **Audit secret access:**
   - Enable OCI Vault audit logging
   - Monitor secret retrieval events
   - Set up alerts for unauthorized access

5. **Secure wrapper execution:**
   - Run wrapper as non-root user
   - Use read-only mounts for OCI config
   - Limit container capabilities

## License

MIT

## Contributing

1. Fork the repository
2. Create feature branch: `git checkout -b feature/new-service`
3. Add example config to `examples/`
4. Update this README
5. Test with actual MCP server
6. Submit pull request

## Support

- Issues: https://github.com/your-repo/oci-vault-mcp-resolver/issues
- Docs: https://github.com/your-repo/oci-vault-mcp-resolver/blob/main/README.md
- OCI Vault: https://docs.oracle.com/iaas/Content/KeyManagement/Concepts/keyoverview.htm
