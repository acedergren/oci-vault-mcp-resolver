# OCI Vault MCP Resolver - User Guide

**Version**: 2.0.0
**Audience**: Developers, DevOps Engineers, System Administrators
**Last Updated**: 2026-01-08

This guide will help you install, configure, and use the OCI Vault MCP Resolver to securely manage secrets for Model Context Protocol (MCP) servers.

## Table of Contents

- [What is OCI Vault MCP Resolver?](#what-is-oci-vault-mcp-resolver)
- [Quick Start](#quick-start)
- [Installation](#installation)
- [Configuration](#configuration)
- [Using the Wrapper](#using-the-wrapper)
- [Docker MCP Gateway Integration](#docker-mcp-gateway-integration)
- [Common Use Cases](#common-use-cases)
- [Troubleshooting](#troubleshooting)

---

## What is OCI Vault MCP Resolver?

The OCI Vault MCP Resolver is a Python tool that:

1. **Fetches secrets** from Oracle Cloud Infrastructure (OCI) Vault
2. **Injects them** as environment variables into MCP servers
3. **Replaces** Docker Desktop secrets management for remote SSH servers
4. **Provides** enterprise-grade security with AES-256-GCM encryption

### Key Benefits

✅ **No Docker Desktop Required** - Works with Docker Engine only
✅ **Remote SSH Support** - Deploy on cloud VMs and bare metal servers
✅ **Centralized Secrets** - One vault for dev/staging/prod environments
✅ **Enterprise Security** - AES-256-GCM encryption, mTLS transport, IAM policies
✅ **Audit Trails** - Full OCI audit logging for compliance
✅ **Multi-tenant** - Isolated compartments per customer/environment

### How It Works

```
AI Client → Docker MCP Gateway → Vault Proxy → OCI Vault → MCP Server with Secrets
```

1. AI client (Claude Code, Cursor) connects to Docker MCP Gateway
2. Gateway executes vault proxy wrapper for requested MCP server
3. Wrapper resolves secrets from OCI Vault
4. Secrets injected as environment variables
5. MCP server starts with vault-provided credentials

---

## Quick Start

### Prerequisites

- **Python 3.8+** installed
- **OCI account** with Vault access
- **OCI CLI** configured (`~/.oci/config`)
- **Docker** installed (for MCP Gateway)

### 5-Minute Setup

```bash
# 1. Clone repository
git clone https://github.com/yourusername/oci-vault-mcp-resolver.git
cd oci-vault-mcp-resolver

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure OCI CLI (if not already done)
oci session authenticate --profile DEFAULT

# 4. Create configuration file
mkdir -p ~/.config/oci-vault-mcp
cp config/resolver.yaml.example ~/.config/oci-vault-mcp/resolver.yaml

# 5. Edit config with your vault details
vi ~/.config/oci-vault-mcp/resolver.yaml
# Update: vault_id, compartment_id, region

# 6. Upload a test secret
export OCI_VAULT_ID="ocid1.vault.oc1.xxx"
export OCI_VAULT_COMPARTMENT_ID="ocid1.compartment.oc1..xxx"
export OCI_REGION="eu-frankfurt-1"
./scripts/upload-secret.sh mcp-test-token "test-value-12345"

# 7. Test secret resolution
python3 wrappers/mcp_vault_proxy.py --service github --verbose
```

---

## Installation

### Method 1: Local Development

For testing and development on your local machine:

```bash
# Clone repository
git clone https://github.com/yourusername/oci-vault-mcp-resolver.git
cd oci-vault-mcp-resolver

# Install dependencies
pip install -r requirements.txt

# Test installation
python3 -c "from oci_vault_resolver import VaultResolver; print('✓ Installation successful')"
```

### Method 2: System-Wide Installation

For production deployment with global access:

```bash
# Install Python package
pip3 install --user -e .

# Copy wrapper to system bin
sudo cp wrappers/mcp_vault_proxy.py /usr/local/bin/
sudo chmod +x /usr/local/bin/mcp_vault_proxy.py

# Verify installation
which mcp_vault_proxy.py
mcp_vault_proxy.py --help
```

### Method 3: Remote SSH Server

For deployment on cloud VMs:

```bash
# SSH to remote server
ssh user@your-cloud-vm

# Install dependencies
sudo apt-get update
sudo apt-get install -y python3 python3-pip git

# Clone and install
git clone https://github.com/yourusername/oci-vault-mcp-resolver.git
cd oci-vault-mcp-resolver
pip3 install --user -r requirements.txt

# Configure OCI CLI
oci session authenticate --profile DEFAULT

# Copy config to system location
sudo mkdir -p /etc/oci-vault-mcp
sudo cp config/resolver.yaml.example /etc/oci-vault-mcp/resolver.yaml
sudo vi /etc/oci-vault-mcp/resolver.yaml
```

---

## Configuration

### Step 1: Get Your OCI Credentials

You need three pieces of information:

1. **Vault OCID**: Where secrets are stored
2. **Compartment OCID**: Vault compartment location
3. **Region**: OCI region (e.g., `eu-frankfurt-1`)

**Find Vault OCID**:
```bash
# List vaults in your tenancy
oci kms management vault list --compartment-id YOUR_ROOT_COMPARTMENT_ID

# Output includes vault OCID:
# "id": "ocid1.vault.oc1.eu-frankfurt-1.xxx"
```

**Find Compartment OCID**:
```bash
# List compartments
oci iam compartment list --compartment-id-in-subtree true

# Output includes compartment OCID:
# "id": "ocid1.compartment.oc1..xxx"
```

### Step 2: Create Configuration File

**Location**: `~/.config/oci-vault-mcp/resolver.yaml`

```yaml
version: "1.0"

vault:
  # Your vault OCID
  vault_id: "ocid1.vault.oc1.eu-frankfurt-1.xxx"

  # Your compartment OCID
  compartment_id: "ocid1.compartment.oc1..xxx"

  # Your OCI region
  region: "eu-frankfurt-1"

  # Authentication method (choose one)
  auth_method: "config_file"  # For ~/.oci/config
  # auth_method: "instance_principal"  # For OCI VMs

  # Path to OCI config file (for config_file auth)
  config_file: "~/.oci/config"
  config_profile: "DEFAULT"

cache:
  # Cache directory for performance
  directory: "~/.cache/oci-vault-mcp"
  ttl: 3600  # Cache TTL in seconds (1 hour)
  enable_stale_fallback: true  # Use stale cache if vault unavailable

resilience:
  # Fault tolerance settings
  enable_circuit_breaker: true
  circuit_breaker_threshold: 5  # Open circuit after 5 failures
  max_retries: 3  # Retry attempts for failed operations

secrets:
  # Map environment variables to OCI Vault secret names
  GITHUB_PERSONAL_ACCESS_TOKEN: "mcp-github-token"
  ANTHROPIC_API_KEY: "mcp-anthropic-key"
  POSTGRES_PASSWORD: "mcp-postgres-password"
  OPENAI_API_KEY: "mcp-openai-key"

logging:
  level: "INFO"  # DEBUG, INFO, WARNING, ERROR
  verbose: false  # Set to true for detailed logs
```

### Step 3: Setup OCI Authentication

**Option A: Config File Authentication** (Recommended for local/SSH)

```bash
# Authenticate with OCI CLI
oci session authenticate --profile DEFAULT

# Verify authentication
oci iam region list
```

**Option B: Instance Principal** (For OCI VMs)

```bash
# 1. Create dynamic group in OCI Console
# Matching rule: instance.compartment.id = 'YOUR_COMPARTMENT_OCID'

# 2. Create IAM policy
allow dynamic-group your-dynamic-group to read secret-bundles in compartment your-compartment

# 3. Set auth method in resolver.yaml
auth_method: "instance_principal"
```

### Step 4: Upload Secrets to Vault

Use the provided script to upload secrets:

```bash
# Set environment variables
export OCI_VAULT_ID="ocid1.vault.oc1.eu-frankfurt-1.xxx"
export OCI_VAULT_COMPARTMENT_ID="ocid1.compartment.oc1..xxx"
export OCI_REGION="eu-frankfurt-1"

# Upload GitHub Personal Access Token
./scripts/upload-secret.sh mcp-github-token "ghp_your_actual_github_token"

# Upload Anthropic API Key
./scripts/upload-secret.sh mcp-anthropic-key "sk-ant-your_actual_key"

# Upload Database Password
./scripts/upload-secret.sh mcp-postgres-password "your_db_password"
```

**Verify secrets uploaded**:
```bash
oci vault secret list \
  --compartment-id "$OCI_VAULT_COMPARTMENT_ID" \
  --vault-id "$OCI_VAULT_ID" \
  --query 'data[*].{Name:"secret-name",State:"lifecycle-state"}' \
  --output table
```

---

## Using the Wrapper

### Basic Usage

```bash
# Resolve secrets and start MCP server
python3 wrappers/mcp_vault_proxy.py --service SERVICE_NAME [OPTIONS]
```

### Supported Services

| Service | MCP Server | Description |
|---------|-----------|-------------|
| `github` | `@modelcontextprotocol/server-github` | GitHub integration |
| `postgres` | `@modelcontextprotocol/server-postgres` | PostgreSQL database |
| `mysql` | `@modelcontextprotocol/server-mysql` | MySQL database |
| `sqlite` | `@modelcontextprotocol/server-sqlite` | SQLite database |
| `mongodb` | `@modelcontextprotocol/server-mongodb` | MongoDB database |
| `redis` | `@modelcontextprotocol/server-redis` | Redis cache |
| `docker` | `@modelcontextprotocol/server-docker` | Docker integration |
| `kubernetes` | `@modelcontextprotocol/server-kubernetes` | Kubernetes integration |
| `aws` | `@modelcontextprotocol/server-aws` | AWS services |
| `gcp` | `@modelcontextprotocol/server-gcp` | Google Cloud Platform |
| `azure` | `@modelcontextprotocol/server-azure` | Microsoft Azure |

### Examples

**GitHub MCP Server**:
```bash
python3 wrappers/mcp_vault_proxy.py --service github
```

**PostgreSQL with Production Environment**:
```bash
python3 wrappers/mcp_vault_proxy.py \
  --service postgres \
  --env production \
  --config /etc/oci-vault-mcp/resolver.yaml
```

**Custom MCP Server**:
```bash
python3 wrappers/mcp_vault_proxy.py \
  --service custom \
  --command "python3 /path/to/my_mcp_server.py" \
  --config ./resolver.yaml
```

**Verbose Logging for Debugging**:
```bash
python3 wrappers/mcp_vault_proxy.py \
  --service github \
  --verbose
```

### Expected Output

```
[INFO] Loading configuration from: ~/.config/oci-vault-mcp/resolver.yaml
[INFO] Initializing VaultResolver with vault_id=ocid1.vault.oc1.xxx
[INFO] Resolving 1 secrets from OCI Vault...
[DEBUG] Resolving GITHUB_PERSONAL_ACCESS_TOKEN from mcp-github-token...
[DEBUG] ✓ Resolved GITHUB_PERSONAL_ACCESS_TOKEN
[INFO] Successfully resolved 1/1 secrets
[INFO] Executing MCP server: npx -y @modelcontextprotocol/server-github
[DEBUG] Environment variables set: GITHUB_PERSONAL_ACCESS_TOKEN
GitHub MCP Server running on stdio
```

---

## Docker MCP Gateway Integration

### Step 1: Configure Gateway

**File**: `~/.docker/mcp/config.yaml`

```yaml
mcpServers:
  # GitHub with OCI Vault secrets
  github-vault:
    command: python3
    args:
      - /usr/local/bin/mcp_vault_proxy.py
      - --service
      - github
      - --config
      - /etc/oci-vault-mcp/resolver.yaml
    env:
      PATH: /usr/bin:/bin:/usr/local/bin

  # PostgreSQL with OCI Vault secrets
  postgres-vault:
    command: python3
    args:
      - /usr/local/bin/mcp_vault_proxy.py
      - --service
      - postgres
      - --config
      - /etc/oci-vault-mcp/resolver.yaml
    env:
      PATH: /usr/bin:/bin:/usr/local/bin

  # Anthropic with OCI Vault secrets
  anthropic-vault:
    command: python3
    args:
      - /usr/local/bin/mcp_vault_proxy.py
      - --service
      - custom
      - --command
      - npx -y @anthropic/mcp-server-anthropic
      - --config
      - /etc/oci-vault-mcp/resolver.yaml
    env:
      PATH: /usr/bin:/bin:/usr/local/bin
```

### Step 2: Start Gateway

```bash
# Start gateway in background
docker mcp gateway run &

# Verify gateway is running
ps aux | grep "docker mcp gateway"
```

### Step 3: Connect AI Client

```bash
# Connect Claude Code
docker mcp client connect claude-code

# Or connect Cursor
docker mcp client connect cursor
```

### Step 4: Verify Integration

Once connected, your AI client will have access to all MCP server tools with OCI Vault credentials automatically injected!

**Test in Claude Code**:
```
Ask: "List my GitHub repositories"
→ GitHub MCP server will use GITHUB_PERSONAL_ACCESS_TOKEN from vault
```

---

## Common Use Cases

### Use Case 1: GitHub Integration

**Goal**: Use GitHub MCP server with Personal Access Token from vault

**Steps**:

1. **Upload GitHub PAT to vault**:
   ```bash
   ./scripts/upload-secret.sh mcp-github-token "ghp_your_actual_token"
   ```

2. **Configure secret mapping** in `resolver.yaml`:
   ```yaml
   secrets:
     GITHUB_PERSONAL_ACCESS_TOKEN: "mcp-github-token"
   ```

3. **Start GitHub MCP server**:
   ```bash
   python3 wrappers/mcp_vault_proxy.py --service github
   ```

4. **Verify** - Server should start with token injected:
   ```
   GitHub MCP Server running on stdio
   ```

### Use Case 2: Database Connection

**Goal**: Connect PostgreSQL MCP server with password from vault

**Steps**:

1. **Upload database password**:
   ```bash
   ./scripts/upload-secret.sh mcp-postgres-password "secure_db_password"
   ```

2. **Configure secret mapping**:
   ```yaml
   secrets:
     POSTGRES_PASSWORD: "mcp-postgres-password"
   ```

3. **Start PostgreSQL MCP server**:
   ```bash
   python3 wrappers/mcp_vault_proxy.py \
     --service postgres \
     --config /etc/oci-vault-mcp/resolver.yaml
   ```

### Use Case 3: Multi-Environment Deployment

**Goal**: Different secrets for dev/staging/prod environments

**Config** (`resolver.yaml`):
```yaml
environments:
  development:
    vault:
      compartment_id: "ocid1.compartment.oc1..dev"
    secrets:
      GITHUB_PERSONAL_ACCESS_TOKEN: "mcp-github-token-dev"

  staging:
    vault:
      compartment_id: "ocid1.compartment.oc1..staging"
    secrets:
      GITHUB_PERSONAL_ACCESS_TOKEN: "mcp-github-token-staging"

  production:
    vault:
      compartment_id: "ocid1.compartment.oc1..production"
    secrets:
      GITHUB_PERSONAL_ACCESS_TOKEN: "mcp-github-token-prod"
```

**Usage**:
```bash
# Development
python3 mcp_vault_proxy.py --service github --env development

# Production
python3 mcp_vault_proxy.py --service github --env production
```

### Use Case 4: Custom MCP Server

**Goal**: Use vault secrets with your own MCP server

**Steps**:

1. **Upload secrets**:
   ```bash
   ./scripts/upload-secret.sh mcp-custom-api-key "your_api_key"
   ```

2. **Configure secret mapping**:
   ```yaml
   secrets:
     CUSTOM_API_KEY: "mcp-custom-api-key"
   ```

3. **Start with custom command**:
   ```bash
   python3 wrappers/mcp_vault_proxy.py \
     --service custom \
     --command "python3 /path/to/your_mcp_server.py"
   ```

---

## Troubleshooting

### Error: "Authentication failed"

**Symptom**:
```
[ERROR] Authentication with OCI failed
AuthenticationError: Unable to authenticate with OCI
```

**Solutions**:

1. **Verify OCI CLI authentication**:
   ```bash
   oci session authenticate --profile DEFAULT
   oci iam region list  # Test if auth works
   ```

2. **Check config file**:
   ```bash
   cat ~/.oci/config
   # Verify profile, key_file, tenancy exist
   ```

3. **Check resolver.yaml**:
   ```yaml
   vault:
     auth_method: "config_file"  # Match your setup
     config_file: "~/.oci/config"
     config_profile: "DEFAULT"
   ```

### Error: "Secret not found"

**Symptom**:
```
[WARNING] Failed to resolve secret 'mcp-github-token'
Secret not found: mcp-github-token
```

**Solutions**:

1. **List secrets in vault**:
   ```bash
   oci vault secret list \
     --compartment-id "$OCI_VAULT_COMPARTMENT_ID" \
     --vault-id "$OCI_VAULT_ID"
   ```

2. **Verify secret name matches config**:
   ```yaml
   secrets:
     GITHUB_PERSONAL_ACCESS_TOKEN: "mcp-github-token"  # Must match vault
   ```

3. **Upload missing secret**:
   ```bash
   ./scripts/upload-secret.sh mcp-github-token "your_token"
   ```

### Error: "Permission denied"

**Symptom**:
```
[ERROR] Permission denied for secret 'mcp-github-token'
PermissionDeniedError: Insufficient IAM permissions
```

**Solution**:

Add IAM policy:
```
allow group YourGroup to read secret-bundles in compartment YourCompartment
```

**Verify policy**:
```bash
oci iam policy list --compartment-id YOUR_TENANCY_OCID
```

### Error: "Command not found: python3"

**Symptom**:
```
/bin/bash: python3: command not found
```

**Solution**:

Install Python 3:
```bash
# Ubuntu/Debian
sudo apt-get install python3 python3-pip

# RHEL/CentOS
sudo yum install python3 python3-pip

# Verify installation
python3 --version
```

### Gateway Not Finding Custom Server

**Symptom**: Custom vault server doesn't appear in `docker mcp server ls`

**Explanation**: Docker MCP Gateway v1.0 primarily shows catalog (containerized) servers. Custom command-based servers work via `config.yaml` but don't appear in the server list.

**Verification**:
```bash
# Check config
cat ~/.docker/mcp/config.yaml

# Test wrapper directly
python3 /usr/local/bin/mcp_vault_proxy.py --service github
```

---

## Next Steps

- [API Documentation](API_DOCUMENTATION.md) - Complete API reference
- [Architecture Diagrams](ARCHITECTURE_DIAGRAMS.md) - Visual system design
- [Security Best Practices](SECURITY.md) - IAM policies and security hardening
- [Advanced Configuration](ADVANCED_CONFIGURATION.md) - Custom caching, retry strategies
- [CI/CD Integration](CICD_INTEGRATION.md) - GitHub Actions, GitLab CI examples

---

## Getting Help

- **GitHub Issues**: https://github.com/yourusername/oci-vault-mcp-resolver/issues
- **Documentation**: https://github.com/yourusername/oci-vault-mcp-resolver/docs
- **OCI Support**: https://docs.oracle.com/en-us/iaas/Content/Vault/home.htm
