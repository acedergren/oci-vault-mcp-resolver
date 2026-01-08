# OCI Vault MCP Wrapper - Quick Reference Card

One-page reference for common tasks.

## 🚀 30-Second Setup

```bash
# 1. Run automated setup
./setup-example.sh

# 2. Follow prompts to create GitHub, PostgreSQL, or custom config

# 3. Test immediately
node ../wrapper.js --config ~/.config/mcp-wrappers/github.yaml
```

## 📋 Secret Naming Pattern

```
mcp-{service}-{type}
```

**Examples:**
- `mcp-github-token`
- `mcp-postgres-url`
- `mcp-anthropic-api-key`
- `mcp-openai-api-key`
- `mcp-slack-bot-token`

## 🔐 Create Vault Secret (One-Liner)

```bash
oci vault secret create-base64 \
  --compartment-id "YOUR_COMPARTMENT_OCID" \
  --vault-id "YOUR_VAULT_OCID" \
  --secret-name "mcp-SERVICE-TYPE" \
  --key-id "YOUR_KEY_OCID" \
  --secret-content-content "$(echo -n 'SECRET_VALUE' | base64)"
```

## 📝 Config File Template

```yaml
command: npx
args: ["-y", "@modelcontextprotocol/server-name"]
env:
  VAR_NAME: "vault://mcp-service-type"
```

## 🐳 Docker MCP Gateway Config

```json
{
  "mcpServers": {
    "service": {
      "command": "docker",
      "args": [
        "exec", "mcp-gateway",
        "node", "/app/wrappers/wrapper.js",
        "--config", "/app/config/service.yaml"
      ]
    }
  }
}
```

## 🔍 Common Commands

### List MCP Secrets
```bash
oci vault secret list \
  --compartment-id "COMPARTMENT_OCID" \
  --vault-id "VAULT_OCID" \
  --query 'data[?starts_with("secret-name", `mcp-`)].{Name:"secret-name",State:"lifecycle-state"}' \
  --output table
```

### Update Secret
```bash
oci vault secret update-base64 \
  --secret-id "SECRET_OCID" \
  --secret-content-content "$(echo -n 'NEW_VALUE' | base64)"
```

### Test Wrapper
```bash
node wrapper.js --config config.yaml
```

### Test with Debug
```bash
DEBUG=oci-vault-mcp-wrapper node wrapper.js --config config.yaml
```

### Validate YAML
```bash
node -e "console.log(require('js-yaml').load(require('fs').readFileSync('config.yaml')))"
```

## 🎯 Resolution Patterns

| Pattern | Example | Description |
|---------|---------|-------------|
| `vault://secret-name` | `vault://mcp-github-token` | Fetch from OCI Vault |
| `${ENV_VAR}` | `${API_KEY}` | Fallback to env var |
| `${VAR:-default}` | `${PORT:-3000}` | With default value |
| `literal` | `production` | Static value |
| `prefix-${VAR}` | `https://${HOST}` | Interpolation |

## 🔧 Troubleshooting

### Secret Not Found
```bash
# Verify secret exists
oci vault secret list --compartment-id "OCID" --vault-id "OCID" \
  --query 'data[?starts_with("secret-name", `mcp-SERVICE-`)]'
```

### Auth Failed
```bash
# Test OCI CLI
oci iam region list

# Check config
cat ~/.oci/config
```

### Server Won't Start
```bash
# Test command manually
export VAR_NAME="test-value"
npx -y @modelcontextprotocol/server-name
```

## 📁 Example Files

| File | Service | Secrets |
|------|---------|---------|
| `github.yaml` | GitHub | `mcp-github-token` |
| `postgres.yaml` | PostgreSQL | `mcp-postgres-url` |
| `anthropic.yaml` | Claude | `mcp-anthropic-api-key` |
| `openai.yaml` | OpenAI | `mcp-openai-api-key` |
| `slack.yaml` | Slack | `mcp-slack-bot-token`, `mcp-slack-signing-secret` |
| `template.yaml` | Custom | Your secrets |

## 🔑 IAM Policy

```
allow group MCP-Users to read secret-bundles in compartment MyCompartment where target.secret.name = 'mcp-*'
```

## 📚 Documentation

- **Examples README:** `README.md` - Full examples documentation
- **Index:** `INDEX.md` - Detailed service reference
- **Wrappers README:** `../README.md` - Comprehensive wrapper docs
- **Project README:** `../../README.md` - Project overview

## 🆘 Getting Help

1. Check example files for your service
2. Review troubleshooting section
3. Enable debug logging: `DEBUG=*`
4. Test components individually (OCI CLI, MCP server, wrapper)
5. File issue: https://github.com/your-org/oci-vault-mcp-resolver/issues

## 📦 File Structure

```
wrappers/
├── wrapper.js              # Main wrapper script
├── README.md              # Comprehensive documentation
└── examples/
    ├── README.md          # Examples overview
    ├── INDEX.md           # Detailed reference
    ├── QUICK-REFERENCE.md # This file
    ├── setup-example.sh   # Automated setup
    ├── template.yaml      # Custom service template
    ├── github.yaml        # GitHub example
    ├── postgres.yaml      # PostgreSQL example
    ├── anthropic.yaml     # Claude example
    ├── openai.yaml        # OpenAI example
    └── slack.yaml         # Slack example
```

## 🎓 Learning Path

1. **Start:** Run `./setup-example.sh` → Choose GitHub
2. **Explore:** Review `github.yaml` structure
3. **Understand:** Read secret resolution in `../README.md`
4. **Expand:** Try `postgres.yaml` with database
5. **Customize:** Use `template.yaml` for your service
6. **Deploy:** Integrate with Docker MCP Gateway

## ⚡ Pro Tips

- Use `mcp-*` prefix for all MCP-related secrets
- Enable debug logging for troubleshooting: `DEBUG=oci-vault-mcp-wrapper`
- Test OCI authentication separately: `oci iam region list`
- Validate YAML syntax before running wrapper
- Use Instance Principal in production, Config File in development
- Keep secrets rotated and monitor access logs
- Use least privilege IAM policies with `where target.secret.name = 'mcp-*'`

## 🔒 Security Checklist

- [ ] Secrets stored in OCI Vault, not env files
- [ ] IAM policy uses least privilege
- [ ] Audit logging enabled on vault
- [ ] Secrets rotated regularly
- [ ] Config files don't contain secrets
- [ ] OCI config file has restricted permissions (600)
- [ ] Docker volumes mounted read-only where possible
- [ ] Wrapper runs as non-root user

---

**Need more details?** See [README.md](./README.md) and [INDEX.md](./INDEX.md)
