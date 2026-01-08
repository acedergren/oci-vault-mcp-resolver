# OCI Vault MCP Wrapper Examples

Copy-paste ready configuration examples for popular MCP servers with OCI Vault secret resolution.

## 🚀 Quick Start

### Option 1: Automated Setup (Recommended)

```bash
cd wrappers/examples
./setup-example.sh
```

This interactive script will:
- Check prerequisites (OCI CLI, Node.js, authentication)
- Guide you through creating vault secrets
- Copy and configure example files
- Test your configuration

### Option 2: Manual Setup

1. **Choose an example:**
   ```bash
   cp github.yaml ~/my-configs/
   ```

2. **Create vault secret:**
   ```bash
   oci vault secret create-base64 \
     --compartment-id "ocid1.compartment.oc1..xxxxx" \
     --vault-id "ocid1.vault.oc1.region.xxxxx" \
     --secret-name "mcp-github-token" \
     --key-id "ocid1.key.oc1.region.xxxxx" \
     --secret-content-content "$(echo -n 'ghp_xxxxxxxxxxxx' | base64)"
   ```

3. **Run the wrapper:**
   ```bash
   node ../wrapper.js --config ~/my-configs/github.yaml
   ```

## 📁 Available Examples

| File | Service | Complexity | Secrets |
|------|---------|------------|---------|
| `github.yaml` | GitHub MCP Server | Simple | 1 token |
| `postgres.yaml` | PostgreSQL MCP Server | Simple | 1 URL or 5 params |
| `anthropic.yaml` | Claude API | Simple | 1-2 keys |
| `openai.yaml` | OpenAI/ChatGPT API | Simple | 1-2 keys |
| `slack.yaml` | Slack Multi-Workspace | Complex | 2-4 tokens |
| `template.yaml` | Custom Service Template | N/A | Your secrets |

See [INDEX.md](./INDEX.md) for detailed descriptions.

## 🔐 Secret Naming Convention

All examples use the pattern: **`mcp-{service}-{type}`**

Examples:
- `mcp-github-token` - GitHub Personal Access Token
- `mcp-postgres-url` - PostgreSQL connection URL
- `mcp-anthropic-api-key` - Claude API key
- `mcp-openai-api-key` - OpenAI API key
- `mcp-slack-bot-token` - Slack Bot User OAuth Token

**Why this pattern?**
- ✅ Namespace isolation (all MCP secrets start with `mcp-`)
- ✅ Service grouping (easy filtering: `mcp-github-*`)
- ✅ Type clarity (identifies secret purpose)
- ✅ Multi-tenant safe (no collision with app secrets)

## 📚 Documentation

- **[INDEX.md](./INDEX.md)** - Complete reference for all examples with setup instructions
- **[../README.md](../README.md)** - Comprehensive wrapper documentation
- **[../../README.md](../../README.md)** - OCI Vault MCP Resolver overview

## 🐳 Docker MCP Gateway Integration

All examples work with Docker MCP Gateway. Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "github": {
      "command": "docker",
      "args": [
        "exec", "mcp-gateway",
        "node", "/app/wrappers/wrapper.js",
        "--config", "/app/config/github.yaml"
      ]
    }
  }
}
```

Mount in `docker-compose.yml`:
```yaml
services:
  mcp-gateway:
    volumes:
      - ./config:/app/config
      - ./oci-vault-mcp-resolver/wrappers:/app/wrappers
      - ./oci-vault-mcp-resolver/dist:/app/dist
      - ~/.oci:/root/.oci:ro
```

## 🔧 Creating Custom Configs

### From Template

```bash
# Copy template
cp template.yaml myservice.yaml

# Edit configuration
vim myservice.yaml

# Update these sections:
# - command: Your MCP server command
# - args: Command arguments
# - env: Required environment variables with vault:// URIs

# Create vault secrets
oci vault secret create-base64 \
  --compartment-id "ocid1.compartment.oc1..xxxxx" \
  --vault-id "ocid1.vault.oc1.region.xxxxx" \
  --secret-name "mcp-myservice-api-key" \
  --key-id "ocid1.key.oc1.region.xxxxx" \
  --secret-content-content "$(echo -n 'your-secret' | base64)"

# Test
node ../wrapper.js --config myservice.yaml
```

### Configuration Format

```yaml
# MCP server command
command: npx
args:
  - "-y"
  - "@modelcontextprotocol/server-name"

# Environment variables with vault resolution
env:
  # Vault secret
  API_KEY: "vault://mcp-service-api-key"

  # Environment variable fallback
  TIMEOUT: "${SERVICE_TIMEOUT:-30000}"

  # Static value
  ENVIRONMENT: "production"

  # String interpolation
  API_URL: "https://${HOST}/api"

# Optional: Custom vault config
vault:
  vaultId: "ocid1.vault.oc1.region.xxxxx"
  compartmentId: "ocid1.compartment.oc1..xxxxx"
  useInstancePrincipal: true
```

## 🧪 Testing Examples

### Validate YAML Syntax
```bash
node -e "console.log(require('js-yaml').load(require('fs').readFileSync('github.yaml')))"
```

### Test with Debug Logging
```bash
DEBUG=oci-vault-mcp-wrapper node ../wrapper.js --config github.yaml
```

### Test MCP Server Manually
```bash
# Set env vars manually to isolate wrapper issues
export GITHUB_PERSONAL_ACCESS_TOKEN="ghp_xxxxxxxxxxxx"
npx -y @modelcontextprotocol/server-github
```

### Verify Vault Secrets
```bash
oci vault secret list \
  --compartment-id "ocid1.compartment.oc1..xxxxx" \
  --vault-id "ocid1.vault.oc1.region.xxxxx" \
  --query 'data[?starts_with("secret-name", `mcp-`)].{Name:"secret-name",State:"lifecycle-state"}' \
  --output table
```

## 🆘 Troubleshooting

### Secret Not Found
```bash
# List all MCP secrets
oci vault secret list \
  --compartment-id "ocid1.compartment.oc1..xxxxx" \
  --vault-id "ocid1.vault.oc1.region.xxxxx" \
  --query 'data[?starts_with("secret-name", `mcp-`)].{Name:"secret-name"}' \
  --output table
```

### Authentication Failed
```bash
# Test OCI CLI authentication
oci iam region list

# For config file auth, check:
cat ~/.oci/config

# For Instance Principal, verify dynamic group and IAM policy
```

### MCP Server Won't Start
```bash
# Enable debug logging
DEBUG=* node ../wrapper.js --config github.yaml

# Check if command exists
which npx
npx --version

# Test command manually
export GITHUB_PERSONAL_ACCESS_TOKEN="test"
npx -y @modelcontextprotocol/server-github
```

## 🔒 Security Best Practices

1. **Never commit secrets to git**
   - Use `.gitignore` for `*.env` files
   - Store all secrets in OCI Vault
   - Use `vault://` URIs in configs

2. **Use least privilege IAM policies**
   ```
   allow group MCP-Users to read secret-bundles in compartment MyCompartment where target.secret.name = 'mcp-*'
   ```

3. **Rotate secrets regularly**
   ```bash
   # Update secret with new version
   oci vault secret update-base64 \
     --secret-id "ocid1.vaultsecret.oc1..xxxxx" \
     --secret-content-content "$(echo -n 'new-value' | base64)"
   ```

4. **Monitor secret access**
   - Enable OCI Vault audit logging
   - Set up alerts for unauthorized access
   - Review access logs regularly

5. **Secure wrapper execution**
   - Run as non-root user
   - Use read-only mounts for OCI config
   - Limit container capabilities in Docker

## 📖 Example Walkthroughs

### GitHub MCP Server

1. **Get Personal Access Token:**
   - Go to https://github.com/settings/tokens
   - Click "Generate new token (classic)"
   - Select scopes: `repo`, `read:org`, `read:user`
   - Generate and copy token

2. **Create vault secret:**
   ```bash
   oci vault secret create-base64 \
     --compartment-id "ocid1.compartment.oc1..xxxxx" \
     --vault-id "ocid1.vault.oc1.region.xxxxx" \
     --secret-name "mcp-github-token" \
     --key-id "ocid1.key.oc1.region.xxxxx" \
     --secret-content-content "$(echo -n 'ghp_xxxxxxxxxxxx' | base64)"
   ```

3. **Copy and test:**
   ```bash
   cp github.yaml ~/my-configs/
   node ../wrapper.js --config ~/my-configs/github.yaml
   ```

### PostgreSQL MCP Server

1. **Get database connection details:**
   - Host, port, database name, username, password

2. **Create vault secret:**
   ```bash
   # Build connection URL
   DATABASE_URL="postgresql://user:pass@host:5432/database"

   # Store in vault
   oci vault secret create-base64 \
     --compartment-id "ocid1.compartment.oc1..xxxxx" \
     --vault-id "ocid1.vault.oc1.region.xxxxx" \
     --secret-name "mcp-postgres-url" \
     --key-id "ocid1.key.oc1.region.xxxxx" \
     --secret-content-content "$(echo -n "$DATABASE_URL" | base64)"
   ```

3. **Copy and test:**
   ```bash
   cp postgres.yaml ~/my-configs/
   node ../wrapper.js --config ~/my-configs/postgres.yaml
   ```

## 🤝 Contributing

To add a new example:

1. Create `{service}.yaml` with comprehensive comments
2. Follow naming convention: `mcp-{service}-{type}`
3. Add entry to [INDEX.md](./INDEX.md)
4. Add walkthrough to this README
5. Test with actual MCP server
6. Submit pull request

## 📄 License

MIT - See LICENSE file in repository root

## 🔗 Links

- **Project Repository:** https://github.com/your-org/oci-vault-mcp-resolver
- **OCI Vault Documentation:** https://docs.oracle.com/iaas/Content/KeyManagement/home.htm
- **MCP Protocol:** https://modelcontextprotocol.io/
- **Claude Desktop:** https://claude.ai/desktop
