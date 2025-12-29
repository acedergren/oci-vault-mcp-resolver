# OCI Vault MCP Resolver

Seamlessly integrate Oracle Cloud Infrastructure (OCI) Vault with Docker MCP Gateway for secure secrets management.

## Overview

This tool resolves `oci-vault://` references in Docker MCP Gateway configuration by fetching secrets from OCI Vault, enabling centralized secrets management without exposing sensitive values in config files.

## Features

- ✅ **Multiple URL Formats**: Support for OCID, compartment+name, and vault+name references
- 🚀 **Performance Caching**: Configurable TTL-based caching to minimize API calls
- 🔄 **Graceful Degradation**: Falls back to stale cache if OCI Vault is temporarily unavailable
- 🔒 **Secure Storage**: Cache files secured with 0600 permissions
- 📊 **Verbose Logging**: Optional debug output for troubleshooting
- 🎯 **Zero Configuration**: Works with existing OCI CLI setup

## Installation

1. **Clone or download this repository**
   ```bash
   cd ~/projects
   git clone <repo-url> oci-vault-mcp-resolver
   cd oci-vault-mcp-resolver
   ```

2. **Install Python dependencies**
   ```bash
   pip3 install --user PyYAML
   ```

3. **Verify OCI CLI is configured**
   ```bash
   oci iam compartment list --query 'data[0:3].name'
   ```

## URL Formats

The resolver supports three URL formats for flexibility:

### 1. Direct Secret OCID
```yaml
oci-vault://ocid1.vaultsecret.oc1.iad.xxx
```
**Use when**: You have the exact secret OCID and want fastest resolution.

### 2. Compartment + Secret Name
```yaml
oci-vault://ocid1.compartment.oc1..xxx/my-secret-name
```
**Use when**: You want to reference secrets by name within a compartment.

### 3. Vault + Secret Name
```yaml
oci-vault://ocid1.vault.oc1.iad.xxx/my-secret-name
```
**Use when**: You want to scope secrets to a specific vault.

## Quick Start

### Step 1: Create a Test Secret in OCI Vault

```bash
# List your compartments
oci iam compartment list --query 'data[0:5].{name:name,id:id}'

# Create or get a vault
COMPARTMENT_ID="ocid1.compartment.oc1..xxx"
VAULT_ID=$(oci kms management vault list \
  --compartment-id "$COMPARTMENT_ID" \
  --query 'data[0].id' \
  --raw-output)

# Get the management endpoint
MGMT_ENDPOINT=$(oci kms management vault get \
  --vault-id "$VAULT_ID" \
  --query 'data."management-endpoint"' \
  --raw-output)

# Create an encryption key (if you don't have one)
KEY_ID=$(oci kms management key create \
  --compartment-id "$COMPARTMENT_ID" \
  --display-name "mcp-secrets-key" \
  --endpoint "$MGMT_ENDPOINT" \
  --key-shape '{"algorithm":"AES","length":32}' \
  --query 'data.id' \
  --raw-output)

# Create a secret
SECRET_ID=$(oci vault secret create-base64 \
  --compartment-id "$COMPARTMENT_ID" \
  --secret-name "test-mcp-secret" \
  --vault-id "$VAULT_ID" \
  --key-id "$KEY_ID" \
  --secret-content-content "my-super-secret-value" \
  --query 'data.id' \
  --raw-output)

echo "Secret created: $SECRET_ID"
```

### Step 2: Update MCP Config with Vault Reference

Edit your MCP configuration to use the vault reference:

```bash
# Get current config
docker mcp config read > /tmp/mcp-config.yaml

# Edit the config to add vault references
# For example, change:
#   PROMETHEUS_URL: http://localhost:9090
# To:
#   PROMETHEUS_URL: oci-vault://ocid1.vaultsecret.oc1.iad.xxx
#   API_KEY: oci-vault://ocid1.compartment.oc1..xxx/my-api-key

# Apply the config with vault references
cat /tmp/mcp-config.yaml | docker mcp config write
```

### Step 3: Resolve Secrets

```bash
# Option 1: Use the wrapper script (recommended)
./mcp-with-vault

# Option 2: Manual resolution
docker mcp config read | \
  python3 oci_vault_resolver.py | \
  docker mcp config write
```

## Usage

### Using the Wrapper Script (Recommended)

```bash
# Basic usage - resolve and apply
./mcp-with-vault

# Dry run to preview resolved config
./mcp-with-vault --dry-run

# Resolve with custom cache TTL (2 hours)
./mcp-with-vault --ttl 7200

# Resolve and start gateway
./mcp-with-vault --start

# Verbose mode for debugging
./mcp-with-vault --verbose
```

### Using the Python Script Directly

```bash
# Read from stdin, write to stdout
docker mcp config read | python3 oci_vault_resolver.py

# With verbose logging
docker mcp config read | python3 oci_vault_resolver.py --verbose

# Custom cache TTL (2 hours)
docker mcp config read | python3 oci_vault_resolver.py --ttl 7200

# From/to files
python3 oci_vault_resolver.py -i config.yaml -o resolved-config.yaml
```

## Configuration Examples

### Example 1: Prometheus with Vault Secrets

```yaml
servers:
  prometheus:
    config:
      PROMETHEUS_URL: oci-vault://ocid1.vaultsecret.oc1.iad.amaaaaaxxxxxx
      API_KEY: oci-vault://ocid1.compartment.oc1..xxx/prometheus-api-key
```

### Example 2: Multiple Services with Secrets

```yaml
servers:
  database:
    config:
      DB_HOST: postgres.example.com
      DB_USER: admin
      DB_PASSWORD: oci-vault://ocid1.compartment.oc1..xxx/db-password

  api:
    config:
      API_KEY: oci-vault://ocid1.compartment.oc1..xxx/api-key
      WEBHOOK_SECRET: oci-vault://ocid1.vaultsecret.oc1.iad.yyy
```

### Example 3: Using Secret Names

```yaml
servers:
  app:
    config:
      # Reference by compartment + secret name
      JWT_SECRET: oci-vault://ocid1.compartment.oc1..abc123/jwt-secret

      # Reference by vault + secret name
      ENCRYPTION_KEY: oci-vault://ocid1.vault.oc1.iad.xyz789/encryption-key
```

## Caching

Secrets are cached locally to minimize API calls to OCI Vault:

- **Default location**: `~/.cache/oci-vault-mcp/`
- **Default TTL**: 3600 seconds (1 hour)
- **Cache format**: JSON files with timestamps
- **Security**: Cache files have 0600 permissions

### Managing Cache

```bash
# View cache directory
ls -lah ~/.cache/oci-vault-mcp/

# Clear all cached secrets
rm -rf ~/.cache/oci-vault-mcp/

# Clear specific secret (find by checking debug logs)
rm ~/.cache/oci-vault-mcp/<hash>.json
```

## Error Handling

The resolver provides graceful error handling:

1. **Secret not found**: Clear error message with compartment/name details
2. **OCI CLI error**: Falls back to stale cache if available (with warning)
3. **Network issues**: Uses cached value if available
4. **Invalid URL format**: Clear error message with expected formats

### Example Error Output

```
ERROR: Secret not found: my-secret in compartment ocid1.compartment.oc1..xxx
WARNING: Using stale cached value for oci-vault://ocid1.compartment.oc1..xxx/my-secret
```

## Troubleshooting

### Issue: "OCI CLI not found"

**Solution**: Install OCI CLI
```bash
# Option 1: Via package manager (recommended)
# macOS
brew install oci-cli

# Linux
pip3 install --user oci-cli

# Option 2: Manual installation
bash -c "$(curl -L https://raw.githubusercontent.com/oracle/oci-cli/master/scripts/install/install.sh)"
```

### Issue: "PyYAML not found"

**Solution**: Install PyYAML
```bash
pip3 install --user PyYAML
```

### Issue: "Failed to fetch secret"

**Possible causes**:
1. Secret OCID is incorrect
2. OCI CLI not configured properly
3. Insufficient IAM permissions
4. Secret doesn't exist in specified compartment

**Debug steps**:
```bash
# Test OCI CLI
oci vault secret get-secret-bundle --secret-id <secret-ocid>

# Verify permissions
oci iam user get --user-id <your-user-ocid>

# Use verbose mode
./mcp-with-vault --verbose
```

### Issue: Cache is stale but vault is unreachable

**Expected behavior**: Resolver will use stale cache with a warning. This is intentional for availability.

**To force fresh fetch**: Clear cache and retry
```bash
rm -rf ~/.cache/oci-vault-mcp/
./mcp-with-vault
```

## Security Best Practices

1. **Never commit vault URLs with OCIDs** to version control
2. **Use compartment+name format** for better portability across environments
3. **Set appropriate cache TTL** based on secret rotation frequency
4. **Audit cache directory permissions** regularly
5. **Use IAM policies** to restrict secret access
6. **Enable audit logging** in OCI Vault for secret access

### Recommended IAM Policy

```
Allow group mcp-users to read secret-bundles in compartment mcp-secrets
Allow group mcp-users to read vaults in compartment mcp-secrets
Allow group mcp-users to read keys in compartment mcp-secrets
```

## Integration with CI/CD

### GitHub Actions

```yaml
- name: Resolve OCI Vault Secrets
  env:
    OCI_CLI_CONFIG_FILE: ${{ secrets.OCI_CONFIG }}
    OCI_CLI_KEY_FILE: ${{ secrets.OCI_KEY }}
  run: |
    docker mcp config read | \
      python3 oci_vault_resolver.py | \
      docker mcp config write
```

### GitLab CI

```yaml
resolve_secrets:
  script:
    - docker mcp config read | python3 oci_vault_resolver.py | docker mcp config write
  variables:
    OCI_CLI_CONFIG_FILE: $OCI_CONFIG
```

## Architecture

```
┌─────────────────────┐
│  MCP Config with    │
│  oci-vault:// refs  │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  OCI Vault Resolver │
│  - Parse config     │
│  - Check cache      │
│  - Fetch secrets    │
└──────────┬──────────┘
           │
           ├────────────────┐
           ▼                ▼
    ┌──────────┐    ┌──────────────┐
    │  Cache   │    │  OCI Vault   │
    │  (local) │    │   (cloud)    │
    └──────────┘    └──────────────┘
           │
           ▼
┌─────────────────────┐
│  Resolved Config    │
│  (secrets injected) │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Docker MCP Gateway │
└─────────────────────┘
```

## Performance

- **Cache hit**: ~0.1ms (local file read)
- **Cache miss**: ~500-1000ms (OCI API call + base64 decode)
- **Parallel resolution**: Not yet implemented (sequential for now)

## Limitations

- **No secret rotation detection**: Cache doesn't auto-invalidate on secret updates (use appropriate TTL)
- **Sequential resolution**: Multiple secrets resolved one at a time (parallel resolution planned)
- **No secret versioning**: Always fetches latest secret version
- **Local cache only**: Not suitable for distributed deployments without shared cache

## Roadmap

- [ ] Parallel secret resolution
- [ ] Secret version support
- [ ] Distributed cache (Redis, etc.)
- [ ] Auto-rotation detection
- [ ] Secret polling for long-running processes
- [ ] Metrics and monitoring integration

## Contributing

Contributions welcome! Please:
1. Test with your OCI Vault setup
2. Add test cases for new features
3. Update documentation
4. Follow existing code style

## License

MIT License - See LICENSE file for details

## Support

For issues or questions:
- GitHub Issues: <repo-url>/issues
- OCI Vault Docs: https://docs.oracle.com/en-us/iaas/Content/KeyManagement/home.htm
- Docker MCP Docs: https://docs.docker.com/mcp/
