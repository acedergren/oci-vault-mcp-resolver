# Claude Code Integration Guide

Complete guide for using OCI Vault secrets with Claude Code's MCP (Model Context Protocol) servers.

## Overview

Claude Code supports MCP servers for extended functionality (GitHub, Sentry, Prometheus, etc.). This guide shows how to securely manage MCP server credentials using OCI Vault instead of storing secrets in plain text configuration files.

## Architecture

```
┌─────────────┐      ┌──────────────────┐      ┌─────────────┐
│ Claude Code │─────▶│ MCP Gateway      │─────▶│ GitHub API  │
│             │      │ (Docker)         │      │ Sentry API  │
└─────────────┘      └──────────────────┘      │ etc.        │
                              │                └─────────────┘
                              ▼
                     ┌──────────────────┐
                     │ OCI Vault        │
                     │ - GitHub Token   │
                     │ - Sentry DSN     │
                     │ - API Keys       │
                     └──────────────────┘
```

**Benefits:**
- ✅ Centralized secret management across environments
- ✅ Secrets encrypted at rest with AES-256-GCM
- ✅ Automatic secret rotation without config changes
- ✅ Audit trail of secret access via OCI logs
- ✅ No secrets in version control

## Prerequisites

1. **OCI Vault** with secrets configured
2. **Claude Code CLI** installed
3. **Python 3.7+** with OCI SDK
4. **OCI Authentication** configured (either `~/.oci/config` or instance principals)

## Quick Start

### Step 1: Install OCI Vault MCP Resolver

```bash
# Clone the resolver
cd ~/projects
git clone https://github.com/acedergren/oci-vault-mcp-resolver.git
cd oci-vault-mcp-resolver

# Install dependencies
pip3 install --user -r requirements.txt

# Verify installation
python3 oci_vault_resolver.py --help
```

### Step 2: Store Secrets in OCI Vault

Create a helper script to upload secrets:

```bash
#!/bin/bash
# upload-secret.sh - Upload secrets to OCI Vault

COMPARTMENT_ID="ocid1.compartment.oc1..aaaaaaaaYOUR_COMPARTMENT"
VAULT_ID="ocid1.vault.oc1.region.YOUR_VAULT"
KMS_ENDPOINT="https://YOUR_VAULT-management.kms.region.oraclecloud.com"

SECRET_NAME="${1:?Usage: $0 <secret-name> <secret-value>}"
SECRET_VALUE="${2:?Usage: $0 <secret-name> <secret-value>}"

# Get encryption key
KEY_ID=$(oci --endpoint "$KMS_ENDPOINT" kms management key list \
  --compartment-id "$COMPARTMENT_ID" \
  --query 'data[0].id' --raw-output)

# Base64 encode
SECRET_BASE64=$(echo -n "$SECRET_VALUE" | base64)

# Create or update secret
EXISTING=$(oci vault secret list \
  --compartment-id "$COMPARTMENT_ID" \
  --name "$SECRET_NAME" \
  --query 'data[0].id' --raw-output 2>/dev/null || echo "")

if [ -n "$EXISTING" ] && [ "$EXISTING" != "null" ]; then
  oci vault secret update-base64 \
    --secret-id "$EXISTING" \
    --secret-content-content "$SECRET_BASE64"
else
  oci vault secret create-base64 \
    --compartment-id "$COMPARTMENT_ID" \
    --vault-id "$VAULT_ID" \
    --key-id "$KEY_ID" \
    --secret-name "$SECRET_NAME" \
    --secret-content-content "$SECRET_BASE64"
fi

echo "✓ Secret '$SECRET_NAME' saved to vault"
```

**Upload your secrets:**

```bash
# GitHub Personal Access Token
./upload-secret.sh github-token "ghp_your_token_here"

# Sentry DSN
./upload-secret.sh sentry-dsn "https://xxx@sentry.io/123456"

# Prometheus URL
./upload-secret.sh prometheus-url "http://prometheus.internal:9090"
```

### Step 3: Configure MCP Gateway with Vault References

Get your current MCP configuration:

```bash
docker mcp config read > mcp-config.yaml
```

Edit the config to use `oci-vault://` references:

```yaml
servers:
  # GitHub integration
  github-official:
    secrets:
      github.personal_access_token: oci-vault://ocid1.vaultsecret.oc1.region.amaaaaaaXXXXXX

  # Sentry error tracking
  sentry:
    config:
      SENTRY_DSN: oci-vault://ocid1.vaultsecret.oc1.region.amaaaaaaYYYYYY

  # Prometheus metrics
  prometheus:
    config:
      PROMETHEUS_URL: oci-vault://ocid1.vaultsecret.oc1.region.amaaaaaaZZZZZZ

  # Other servers...
  context7:
    config: {}

  git:
    config:
      repoPath: /home/user/projects
```

### Step 4: Resolve and Apply Configuration

```bash
# Resolve vault references
python3 oci_vault_resolver.py \
  --config-file ~/.oci/config \
  --profile DEFAULT \
  -i mcp-config.yaml \
  -o mcp-config-resolved.yaml

# Apply the resolved config
docker mcp config write mcp-config-resolved.yaml

# Verify
docker mcp config read | grep -A 2 "github-official"
```

**Output:**
```yaml
github-official:
  secrets:
    github.personal_access_token: ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

### Step 5: Verify MCP Server Connectivity

```bash
claude mcp list
```

**Expected output:**
```
plugin:github:github: https://api.githubcopilot.com/mcp/ - ✓ Connected
plugin:sentry:sentry: https://mcp.sentry.dev/mcp - ✓ Connected
plugin:context7:context7: npx -y @upstash/context7-mcp - ✓ Connected
```

## Real-World Example: GitHub MCP Integration

This example shows the complete setup for integrating GitHub with Claude Code.

### 1. Create GitHub Personal Access Token

Go to https://github.com/settings/tokens and create a token with these scopes:
- `repo` - Full control of private repositories
- `read:org` - Read org and team membership
- `workflow` - Update GitHub Actions workflows

### 2. Store Token in OCI Vault

```bash
./upload-secret.sh running-days-github-token "ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
```

**Output:**
```
Creating new secret: running-days-github-token
ocid1.vaultsecret.oc1.eu-frankfurt-1.amaaaaaahhxc6pya5mp5alyg7cai5563xzl6i7x5ecuzgnfhj5bqijyapwya
✓ Secret 'running-days-github-token' saved to AC vault
```

### 3. Update MCP Configuration

```yaml
servers:
  github-official:
    secrets:
      github.personal_access_token: oci-vault://ocid1.vaultsecret.oc1.eu-frankfurt-1.amaaaaaahhxc6pya5mp5alyg7cai5563xzl6i7x5ecuzgnfhj5bqijyapwya
```

### 4. Resolve and Apply

```bash
python3 ~/projects/oci-vault-mcp-resolver/oci_vault_resolver.py \
  --config-file ~/.oci/config \
  --profile DEFAULT \
  --verbose \
  -i mcp-config.yaml \
  -o mcp-config-resolved.yaml

docker mcp config write mcp-config-resolved.yaml
```

**Resolver output:**
```
Using OCI SDK (parallel resolution enabled)
[DEBUG] Loading OCI config from ~/.oci/config profile=DEFAULT
Found 1 vault reference(s) to resolve (parallel mode)
[DEBUG] Cache miss: oci-vault://ocid1.vaultsecret.oc1.eu-frankfurt-1...
[DEBUG] Fetching secret: ocid1.vaultsecret.oc1.eu-frankfurt-1...
[DEBUG] Successfully fetched: ocid1.vaultsecret.oc1.eu-frankfurt-1...
Successfully resolved 1/1 secret(s)
```

### 5. Test GitHub Integration

```bash
# Create a helper script to fetch the token
cat > scripts/fetch-github-token.sh << 'EOF'
#!/bin/bash
SECRET_ID="ocid1.vaultsecret.oc1.eu-frankfurt-1.amaaaaaahhxc6pya5mp5alyg7cai5563xzl6i7x5ecuzgnfhj5bqijyapwya"

oci secrets secret-bundle get --secret-id "$SECRET_ID" | \
python3 -c "
import sys, json, base64
data = json.load(sys.stdin)
content = data['data']['secret-bundle-content']['content']
token = base64.b64decode(content).decode('utf-8')
print(token)
"
EOF

chmod +x scripts/fetch-github-token.sh

# Test GitHub API authentication
GITHUB_TOKEN=$(./scripts/fetch-github-token.sh)
curl -s -H "Authorization: Bearer $GITHUB_TOKEN" \
  https://api.github.com/user | jq -r '.login'
```

**Output:**
```
✓ GitHub API authenticated as: acedergren
```

## Alternative: Environment Variable Approach

If Docker MCP Gateway is not available (requires Docker Desktop), use environment variables:

### Create Export Script

```bash
cat > scripts/export-github-token.sh << 'EOF'
#!/bin/bash
# Export GitHub token from OCI Vault for Claude Code

SECRET_ID="ocid1.vaultsecret.oc1.eu-frankfurt-1.amaaaaaahhxc6pya5mp5alyg7cai5563xzl6i7x5ecuzgnfhj5bqijyapwya"

export GITHUB_PERSONAL_ACCESS_TOKEN=$(oci secrets secret-bundle get --secret-id "$SECRET_ID" | \
python3 -c "
import sys, json, base64
data = json.load(sys.stdin)
content = data['data']['secret-bundle-content']['content']
token = base64.b64decode(content).decode('utf-8')
print(token)
")

echo "✓ GITHUB_PERSONAL_ACCESS_TOKEN exported from OCI Vault"
echo "  Token: ${GITHUB_PERSONAL_ACCESS_TOKEN:0:10}..."
EOF

chmod +x scripts/export-github-token.sh
```

### Usage

```bash
# Start your shell session with the token
source ./scripts/export-github-token.sh

# Now Claude Code (or any tool) can access: $GITHUB_PERSONAL_ACCESS_TOKEN

# Test it
echo $GITHUB_PERSONAL_ACCESS_TOKEN | gh auth login --with-token
gh auth status
```

## Supported MCP Servers

| Server | Secret Type | Vault Reference Format |
|--------|-------------|------------------------|
| github-official | Personal Access Token | `oci-vault://secret-ocid` |
| sentry | DSN | `oci-vault://compartment-ocid/sentry-dsn` |
| prometheus | API URL + Token | `oci-vault://vault-ocid/prometheus-config` |
| terraform | API Token | `oci-vault://secret-ocid` |
| kubernetes | kubeconfig | `oci-vault://secret-ocid` |

## URL Format Reference

The resolver supports three URL formats:

### 1. Direct Secret OCID (Recommended)
```
oci-vault://ocid1.vaultsecret.oc1.region.amaaaaaaXXXXXX
```
- ✅ Fastest resolution (direct API call)
- ✅ Works across compartments
- ✅ No ambiguity

### 2. Compartment + Secret Name
```
oci-vault://ocid1.compartment.oc1..aaaaaaaaXXXXXX/my-secret-name
```
- ✅ Human-readable
- ✅ Easy to update secret without changing config
- ⚠️ Requires LIST permission on compartment

### 3. Vault + Secret Name
```
oci-vault://ocid1.vault.oc1.region.aaaaaaaaXXXXXX/my-secret-name
```
- ✅ Scoped to specific vault
- ✅ Useful for multi-vault setups
- ⚠️ Requires LIST permission on vault

## Caching Behavior

The resolver caches secrets locally for performance:

**Default Settings:**
- Location: `~/.cache/oci-vault-mcp/`
- TTL: 3600 seconds (1 hour)
- Permissions: `0600` (owner read/write only)

**Cache Structure:**
```
~/.cache/oci-vault-mcp/
├── a1b2c3d4e5f6.json  # Cached secret (hashed filename)
└── f6e5d4c3b2a1.json
```

**Cache File Format:**
```json
{
  "value": "ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
  "timestamp": 1704380400,
  "url": "oci-vault://ocid1.vaultsecret.oc1.eu-frankfurt-1.amaaaaaaXXXXXX"
}
```

**Graceful Degradation:**
If OCI Vault is temporarily unavailable, the resolver falls back to stale cache with a warning:
```
WARNING: Using stale cached value for oci-vault://ocid1.vaultsecret...
```

## Performance Optimization

### Parallel Resolution

The resolver fetches multiple secrets concurrently using `asyncio`:

```bash
# With 10 secrets, parallel mode is ~8-10x faster than sequential
python3 oci_vault_resolver.py -i config.yaml -o resolved.yaml
```

**Output:**
```
Found 10 vault reference(s) to resolve (parallel mode)
[DEBUG] Fetching 10 secrets in parallel
Successfully resolved 10/10 secret(s)
Time: 1.2s (vs ~10s sequential)
```

### Custom Cache TTL

Adjust TTL based on your secret rotation policy:

```bash
# 2-hour cache (less frequent API calls)
python3 oci_vault_resolver.py --ttl 7200 -i config.yaml -o resolved.yaml

# 10-minute cache (more frequent updates)
python3 oci_vault_resolver.py --ttl 600 -i config.yaml -o resolved.yaml
```

## Authentication Methods

### Method 1: OCI Config File (Default)

```bash
# Uses ~/.oci/config
python3 oci_vault_resolver.py \
  --config-file ~/.oci/config \
  --profile DEFAULT \
  -i config.yaml -o resolved.yaml
```

**Config file format:**
```ini
[DEFAULT]
user=ocid1.user.oc1..aaaaaaaaXXXXXX
tenancy=ocid1.tenancy.oc1..aaaaaaaaYYYYYY
region=us-phoenix-1
key_file=/home/user/.oci/api_key.pem
fingerprint=aa:bb:cc:dd:ee:ff:00:11:22:33:44:55:66:77:88:99
```

### Method 2: Instance Principals (Production)

For OCI Compute instances:

```bash
# No config file needed - uses instance metadata
python3 oci_vault_resolver.py \
  --instance-principals \
  -i config.yaml -o resolved.yaml
```

**IAM Policy required:**
```
allow dynamic-group compute-instances to read secret-bundles in compartment MyCompartment
```

### Method 3: Environment Variables

For CI/CD or containerized environments:

```bash
export OCI_CONFIG_FILE=/path/to/config
export OCI_CONFIG_PROFILE=PRODUCTION

python3 oci_vault_resolver.py -i config.yaml -o resolved.yaml
```

## Troubleshooting

### Issue: "Failed to initialize OCI SDK clients"

**Cause:** Missing or invalid OCI config file

**Solution:**
```bash
# Verify config exists
ls -la ~/.oci/config

# Test authentication
oci iam region list

# If needed, reconfigure
oci setup config
```

### Issue: "Secret not found"

**Cause:** Secret OCID is incorrect or doesn't exist

**Solution:**
```bash
# List all secrets in compartment
oci vault secret list \
  --compartment-id "ocid1.compartment.oc1..aaaaaaaaXXXXXX" \
  --vault-id "ocid1.vault.oc1.region.aaaaaaaaYYYYYY" \
  --query 'data[*].{Name:"secret-name",OCID:id}' \
  --output table

# Verify secret OCID
oci secrets secret-bundle get --secret-id "ocid1.vaultsecret.oc1.region.aaaaaaaaXXXXXX"
```

### Issue: "github-official: ✗ Failed to connect"

**Possible causes:**
1. Docker MCP Gateway not running
2. Secret not properly resolved
3. Environment variable not exported

**Solution:**
```bash
# Check Docker MCP status
docker mcp config read | grep github -A 2

# Test token directly
./scripts/fetch-github-token.sh | head -c 20
# Should output: ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx (truncated)

# Export as environment variable (if not using Docker)
source ./scripts/export-github-token.sh
```

### Issue: "Permission denied" when accessing cache

**Cause:** Cache directory has incorrect permissions

**Solution:**
```bash
# Fix cache permissions
chmod 700 ~/.cache/oci-vault-mcp
chmod 600 ~/.cache/oci-vault-mcp/*.json

# Or clear cache
rm -rf ~/.cache/oci-vault-mcp/
```

## Security Best Practices

1. **Use Secret OCIDs, not names** - Prevents enumeration attacks
2. **Rotate tokens regularly** - Update vault, resolver auto-picks up new values
3. **Monitor access logs** - Enable OCI Audit for vault access tracking
4. **Use least-privilege IAM policies** - Grant only `read secret-bundles` permission
5. **Secure cache directory** - Default `0600` permissions prevent other users from reading
6. **Never commit resolved configs** - Add `*-resolved.yaml` to `.gitignore`

## Integration with CI/CD

### GitHub Actions

```yaml
name: Deploy with OCI Vault Secrets

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Configure OCI CLI
        uses: oracle-actions/configure-oci-cli@v1
        with:
          config: ${{ secrets.OCI_CLI_CONFIG }}

      - name: Resolve MCP config
        run: |
          pip install oci PyYAML
          python3 oci_vault_resolver.py \
            --instance-principals \
            -i mcp-config.yaml \
            -o mcp-config-resolved.yaml

      - name: Deploy Claude Code config
        run: |
          docker mcp config write mcp-config-resolved.yaml
```

### GitLab CI

```yaml
deploy:
  image: python:3.11
  before_script:
    - pip install oci PyYAML
  script:
    - |
      python3 oci_vault_resolver.py \
        --config-file $OCI_CONFIG_FILE \
        --profile PRODUCTION \
        -i mcp-config.yaml \
        -o mcp-config-resolved.yaml
    - docker mcp config write mcp-config-resolved.yaml
  only:
    - main
```

## Wrapper Script for Easy Usage

Create `mcp-with-vault` script:

```bash
#!/bin/bash
# Wrapper script for Docker MCP Gateway with OCI Vault integration

set -e

# Default values
CONFIG_FILE="${OCI_CONFIG_FILE:-$HOME/.oci/config}"
PROFILE="${OCI_CONFIG_PROFILE:-DEFAULT}"
TTL="${CACHE_TTL:-3600}"
VERBOSE="${VERBOSE:-false}"

# Parse arguments
DRY_RUN=false
START_GATEWAY=false

while [[ $# -gt 0 ]]; do
  case $1 in
    --dry-run) DRY_RUN=true; shift ;;
    --start) START_GATEWAY=true; shift ;;
    --ttl) TTL="$2"; shift 2 ;;
    --verbose) VERBOSE=true; shift ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
done

# Resolve vault references
echo "Resolving OCI Vault references..."
TEMP_INPUT=$(mktemp)
TEMP_OUTPUT=$(mktemp)

docker mcp config read > "$TEMP_INPUT"

VERBOSE_FLAG=""
[[ "$VERBOSE" == "true" ]] && VERBOSE_FLAG="--verbose"

python3 oci_vault_resolver.py \
  --config-file "$CONFIG_FILE" \
  --profile "$PROFILE" \
  --ttl "$TTL" \
  $VERBOSE_FLAG \
  -i "$TEMP_INPUT" \
  -o "$TEMP_OUTPUT"

if [[ "$DRY_RUN" == "true" ]]; then
  echo "Dry run - resolved config:"
  cat "$TEMP_OUTPUT"
else
  docker mcp config write "$TEMP_OUTPUT"
  echo "✓ Configuration applied"

  if [[ "$START_GATEWAY" == "true" ]]; then
    echo "Starting MCP Gateway..."
    docker mcp gateway start
  fi
fi

rm -f "$TEMP_INPUT" "$TEMP_OUTPUT"
```

**Usage:**
```bash
# Preview resolved config
./mcp-with-vault --dry-run

# Apply config
./mcp-with-vault

# Apply and start gateway
./mcp-with-vault --start

# With custom cache TTL
./mcp-with-vault --ttl 7200 --verbose
```

## Reference: Complete Setup Script

```bash
#!/bin/bash
# complete-setup.sh - Full Claude Code + OCI Vault integration

set -e

# Configuration
REPO_DIR="$HOME/projects/oci-vault-mcp-resolver"
COMPARTMENT_ID="ocid1.compartment.oc1..aaaaaaaaXXXXXX"
VAULT_ID="ocid1.vault.oc1.region.aaaaaaaaYYYYYY"

echo "=== Claude Code + OCI Vault Integration Setup ==="
echo ""

# 1. Clone resolver
if [ ! -d "$REPO_DIR" ]; then
  echo "[1/6] Cloning OCI Vault MCP Resolver..."
  git clone https://github.com/acedergren/oci-vault-mcp-resolver.git "$REPO_DIR"
else
  echo "[1/6] Resolver already cloned, updating..."
  cd "$REPO_DIR" && git pull
fi

# 2. Install dependencies
echo "[2/6] Installing Python dependencies..."
pip3 install --user -r "$REPO_DIR/requirements.txt"

# 3. Verify OCI authentication
echo "[3/6] Verifying OCI authentication..."
if ! oci iam region list >/dev/null 2>&1; then
  echo "ERROR: OCI authentication failed. Run 'oci setup config'"
  exit 1
fi
echo "✓ OCI authenticated"

# 4. Create helper scripts
echo "[4/6] Creating helper scripts..."
mkdir -p scripts

cat > scripts/upload-secret.sh << 'UPLOAD_EOF'
#!/bin/bash
# Upload secret to OCI Vault
# ... (upload-secret.sh content from earlier)
UPLOAD_EOF

cat > scripts/fetch-github-token.sh << 'FETCH_EOF'
#!/bin/bash
# Fetch GitHub token from vault
# ... (fetch script content)
FETCH_EOF

chmod +x scripts/*.sh

# 5. Get current MCP config
echo "[5/6] Backing up current MCP configuration..."
docker mcp config read > mcp-config-backup.yaml

# 6. Instructions for next steps
echo "[6/6] Setup complete!"
echo ""
echo "Next steps:"
echo "  1. Upload secrets:"
echo "     ./scripts/upload-secret.sh github-token 'ghp_your_token'"
echo ""
echo "  2. Update mcp-config.yaml with vault references:"
echo "     github-official:"
echo "       secrets:"
echo "         github.personal_access_token: oci-vault://secret-ocid"
echo ""
echo "  3. Resolve and apply:"
echo "     python3 $REPO_DIR/oci_vault_resolver.py \\"
echo "       --config-file ~/.oci/config \\"
echo "       -i mcp-config.yaml \\"
echo "       -o mcp-config-resolved.yaml"
echo "     docker mcp config write mcp-config-resolved.yaml"
echo ""
echo "Documentation: $REPO_DIR/CLAUDE_CODE_INTEGRATION.md"
```

## Additional Resources

- **OCI Vault Documentation**: https://docs.oracle.com/en-us/iaas/Content/KeyManagement/home.htm
- **Claude Code MCP Servers**: https://docs.anthropic.com/claude/docs/mcp-servers
- **GitHub Personal Access Tokens**: https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/creating-a-personal-access-token

## Support

For issues or questions:
1. Check the [Troubleshooting](#troubleshooting) section
2. Review OCI Vault access logs in OCI Console
3. Enable `--verbose` flag for detailed debugging
4. Open an issue at: https://github.com/acedergren/oci-vault-mcp-resolver/issues
