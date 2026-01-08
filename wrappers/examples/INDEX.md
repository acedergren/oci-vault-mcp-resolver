# Example Configurations Index

Quick reference for all available example configurations.

## Available Examples

| Service | File | Use Case | Secrets Required |
|---------|------|----------|------------------|
| **GitHub** | `github.yaml` | GitHub MCP server with PAT | `mcp-github-token` |
| **PostgreSQL** | `postgres.yaml` | Database connection | `mcp-postgres-url` or separate params |
| **Anthropic** | `anthropic.yaml` | Claude API access | `mcp-anthropic-api-key` |
| **OpenAI** | `openai.yaml` | ChatGPT API access | `mcp-openai-api-key`, `mcp-openai-org-id` |
| **Slack** | `slack.yaml` | Multi-token Slack integration | `mcp-slack-bot-token`, `mcp-slack-signing-secret` |
| **Template** | `template.yaml` | Customizable template | Your custom secrets |

## Quick Start

### 1. Choose an Example

```bash
cd wrappers/examples
cp github.yaml ~/my-config/
```

### 2. Create Vault Secrets

```bash
# GitHub example
oci vault secret create-base64 \
  --compartment-id "ocid1.compartment.oc1..xxxxx" \
  --vault-id "ocid1.vault.oc1.region.xxxxx" \
  --secret-name "mcp-github-token" \
  --key-id "ocid1.key.oc1.region.xxxxx" \
  --secret-content-content "$(echo -n 'ghp_xxxxxxxxxxxx' | base64)"
```

### 3. Run the Wrapper

```bash
node ../wrapper.js --config ~/my-config/github.yaml
```

## Example Details

### github.yaml
- **Purpose:** GitHub repository access via MCP server
- **Server:** `@modelcontextprotocol/server-github`
- **Secrets:**
  - `mcp-github-token` - Personal Access Token (PAT)
- **Scopes Required:** `repo`, `read:org`, `read:user`
- **Get Token:** https://github.com/settings/tokens

### postgres.yaml
- **Purpose:** PostgreSQL database access via MCP server
- **Server:** `@modelcontextprotocol/server-postgres`
- **Secrets (Option A - Single URL):**
  - `mcp-postgres-url` - Full connection URL
- **Secrets (Option B - Separate):**
  - `mcp-postgres-host`
  - `mcp-postgres-database`
  - `mcp-postgres-user`
  - `mcp-postgres-password`
  - Optional: `mcp-postgres-ca-cert` for SSL

### anthropic.yaml
- **Purpose:** Claude API integration
- **Server:** Custom (your implementation)
- **Secrets:**
  - `mcp-anthropic-api-key` - Claude API key
  - Optional: `mcp-anthropic-org-id` - Organization ID
- **Format:** `sk-ant-api03-...`
- **Get Key:** https://console.anthropic.com/settings/keys

### openai.yaml
- **Purpose:** OpenAI/ChatGPT API integration
- **Server:** Custom (your implementation)
- **Secrets:**
  - `mcp-openai-api-key` - OpenAI API key
  - `mcp-openai-org-id` - Organization ID (optional)
- **Format:** `sk-proj-...`
- **Get Key:** https://platform.openai.com/api-keys
- **Azure Alternative:** Use `mcp-azure-openai-api-key` for Azure OpenAI

### slack.yaml
- **Purpose:** Multi-workspace Slack integration
- **Server:** `@modelcontextprotocol/server-slack` (example)
- **Secrets:**
  - `mcp-slack-bot-token` - Bot User OAuth Token (xoxb-*)
  - `mcp-slack-signing-secret` - Webhook signing secret
  - Optional: `mcp-slack-app-token` - App-Level Token for Socket Mode (xapp-*)
  - Optional: `mcp-slack-user-token` - User OAuth Token (xoxp-*)
- **Get Tokens:** https://api.slack.com/apps

### template.yaml
- **Purpose:** Starter template for custom services
- **Usage:**
  1. Copy template: `cp template.yaml myservice.yaml`
  2. Replace placeholders: command, args, env vars
  3. Create vault secrets with `mcp-myservice-*` pattern
  4. Test: `node ../wrapper.js --config myservice.yaml`
- **Includes:** Comprehensive comments and examples for all patterns

## Secret Naming Patterns

All examples follow the convention: `mcp-{service}-{type}`

| Pattern | Example | Description |
|---------|---------|-------------|
| API Key | `mcp-service-api-key` | API authentication key |
| Token | `mcp-service-token` | Generic token/PAT |
| Secret | `mcp-service-secret` | Generic secret value |
| Password | `mcp-service-password` | Database/service password |
| URL | `mcp-service-url` | Connection URL |
| Client ID | `mcp-service-client-id` | OAuth client ID |
| Client Secret | `mcp-service-client-secret` | OAuth client secret |
| Signing Secret | `mcp-service-signing-secret` | Webhook signing key |

## Docker MCP Gateway Setup

All examples work with Docker MCP Gateway. General pattern:

```json
{
  "mcpServers": {
    "service-name": {
      "command": "docker",
      "args": [
        "exec",
        "mcp-gateway",
        "node",
        "/app/wrappers/wrapper.js",
        "--config",
        "/app/config/service-name.yaml"
      ]
    }
  }
}
```

Required `docker-compose.yml` volumes:
```yaml
services:
  mcp-gateway:
    volumes:
      - ./config:/app/config
      - ./oci-vault-mcp-resolver/wrappers:/app/wrappers
      - ./oci-vault-mcp-resolver/dist:/app/dist
      - ~/.oci:/root/.oci:ro
```

## Testing Examples

### Validate YAML Syntax
```bash
node -e "console.log(require('js-yaml').load(require('fs').readFileSync('github.yaml')))"
```

### Test Secret Resolution
```bash
DEBUG=oci-vault-mcp-wrapper node ../wrapper.js --config github.yaml
```

### Test MCP Server Manually
```bash
# Set environment variables manually
export GITHUB_PERSONAL_ACCESS_TOKEN="ghp_xxxxxxxxxxxx"
npx -y @modelcontextprotocol/server-github
```

### Verify Vault Access
```bash
oci vault secret list \
  --compartment-id "ocid1.compartment.oc1..xxxxx" \
  --vault-id "ocid1.vault.oc1.region.xxxxx" \
  --query 'data[?starts_with("secret-name", `mcp-`)].{Name:"secret-name",State:"lifecycle-state"}' \
  --output table
```

## Creating Custom Examples

1. **Start from template:**
   ```bash
   cp template.yaml myservice.yaml
   ```

2. **Customize command and args:**
   ```yaml
   command: npx
   args:
     - "-y"
     - "@your-org/mcp-server-package"
   ```

3. **Define environment variables:**
   ```yaml
   env:
     SERVICE_API_KEY: "vault://mcp-myservice-api-key"
     SERVICE_URL: "https://api.example.com"
   ```

4. **Create vault secrets:**
   ```bash
   ./scripts/create-secret.sh mcp-myservice-api-key "your-api-key-value"
   ```

5. **Test:**
   ```bash
   node ../wrapper.js --config myservice.yaml
   ```

6. **Document:** Add to this index and submit PR

## Common Patterns

### Multiple Secrets
```yaml
env:
  SERVICE_API_KEY: "vault://mcp-service-api-key"
  SERVICE_SECRET: "vault://mcp-service-secret"
  SERVICE_PASSWORD: "vault://mcp-service-password"
```

### Environment Fallback
```yaml
env:
  SERVICE_API_KEY: "vault://mcp-service-api-key"
  SERVICE_TIMEOUT: "${SERVICE_TIMEOUT:-30000}"
```

### String Interpolation
```yaml
env:
  SERVICE_URL: "https://${HOST}/api"
  DATABASE_URL: "postgresql://${USER}:vault://mcp-db-password@${HOST}:5432/${DB}"
```

### Conditional Secrets
```yaml
env:
  # Production: vault secret
  SERVICE_API_KEY: "vault://mcp-service-api-key"

  # Development: fallback to env var
  # SERVICE_API_KEY: "${SERVICE_API_KEY}"
```

## Troubleshooting

### Secret Not Found
1. Verify secret exists: `oci vault secret list ...`
2. Check secret name matches pattern: `mcp-{service}-{type}`
3. Verify IAM permissions for secret access

### Authentication Failed
1. Test OCI CLI: `oci iam region list`
2. For Instance Principal: Check dynamic group and policy
3. For Config File: Verify `~/.oci/config` and key fingerprint

### MCP Server Won't Start
1. Test command manually with hardcoded env vars
2. Check MCP server logs in wrapper output
3. Verify all required environment variables are set

### Docker Volume Issues
1. Check volume mount paths in `docker-compose.yml`
2. Verify files exist: `docker exec mcp-gateway ls -la /app/wrappers`
3. Check permissions: `chmod +x wrappers/wrapper.js`

## Additional Resources

- **Main README:** `../README.md` - Comprehensive wrapper documentation
- **Project README:** `../../README.md` - OCI Vault MCP Resolver overview
- **OCI Vault Docs:** https://docs.oracle.com/iaas/Content/KeyManagement/home.htm
- **MCP Protocol:** https://modelcontextprotocol.io/

## Contributing

To add a new example:

1. Create `{service}.yaml` with comprehensive comments
2. Follow naming convention: `mcp-{service}-{type}`
3. Add entry to this INDEX.md
4. Test with actual MCP server
5. Submit pull request

## License

MIT - See LICENSE file in repository root
