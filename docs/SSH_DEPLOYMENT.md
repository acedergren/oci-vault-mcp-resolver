# SSH Deployment Guide

Complete guide for deploying OCI Vault MCP Resolver on remote SSH servers (cloud VMs, bare metal servers) without Docker Desktop dependency.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Architecture Overview](#architecture-overview)
- [Installation Steps](#installation-steps)
- [Docker MCP Gateway Configuration](#docker-mcp-gateway-configuration)
- [Production Deployment](#production-deployment)
- [Health Monitoring](#health-monitoring)
- [Troubleshooting](#troubleshooting)
- [Security Best Practices](#security-best-practices)

## Prerequisites

### Remote Server Requirements

- **OS**: Linux (Ubuntu 20.04+, RHEL 8+, or Oracle Linux 8+)
- **Python**: 3.9+ with pip
- **Network**: Outbound HTTPS (443) to OCI regions
- **IAM**: OCI user/instance with vault read permissions

### Local Machine Requirements

- **SSH Access**: Key-based authentication to remote server
- **OCI CLI**: Configured with valid credentials
- **Vault**: Pre-created OCI Vault with secrets uploaded

### IAM Permissions

The OCI user or instance principal needs:

```hcl
# User-based authentication
allow group vault-readers to read secret-bundles in compartment MyCompartment

# Instance Principal authentication (recommended for production)
allow dynamic-group my-app-instances to read secret-bundles in compartment MyCompartment
```

## Architecture Overview

### Deployment Model

```
┌─────────────────────────────────────────────────────────────┐
│ Remote SSH Server (OCI Compute, AWS EC2, bare metal)        │
│                                                              │
│  ┌────────────────────────────────────────────────────┐    │
│  │ Docker MCP Gateway                                  │    │
│  │  ├─ Server: github-vault                            │    │
│  │  │   └─ Wrapper: mcp_vault_proxy.py --service github│   │
│  │  ├─ Server: postgres-vault                          │    │
│  │  │   └─ Wrapper: mcp_vault_proxy.py --service postgres│ │
│  │  └─ Server: anthropic-vault                         │    │
│  │      └─ Wrapper: mcp_vault_proxy.py --service anthropic││
│  └────────────────────────────────────────────────────┘    │
│           │                                                  │
│           ▼                                                  │
│  ┌────────────────────────────────────────────────────┐    │
│  │ OCI Vault Resolver                                  │    │
│  │  ├─ Config: ~/.config/oci-vault-mcp/resolver.yaml   │    │
│  │  ├─ Cache: ~/.cache/oci-vault-mcp/ (3600s TTL)     │    │
│  │  └─ Auth: Instance Principal or Config File        │    │
│  └────────────────────────────────────────────────────┘    │
│           │                                                  │
└───────────┼──────────────────────────────────────────────────┘
            │
            ▼ HTTPS (port 443)
┌───────────────────────────────────────────────────────────┐
│ OCI Vault (eu-frankfurt-1)                                │
│  ├─ Secret: mcp-github-token                             │
│  ├─ Secret: mcp-postgres-password                        │
│  └─ Secret: mcp-anthropic-key                            │
└───────────────────────────────────────────────────────────┘
```

### Authentication Methods

| Method | Use Case | Configuration |
|--------|----------|---------------|
| **Instance Principal** | OCI Compute instances | `OCI_USE_INSTANCE_PRINCIPAL=true` |
| **Config File** | Non-OCI servers (AWS, bare metal) | `~/.oci/config` with API keys |
| **Environment Variables** | CI/CD pipelines | `OCI_*` env vars |

## Installation Steps

### Step 1: Transfer Installation Files

From your local machine:

```bash
# Clone repository locally
git clone https://github.com/yourusername/oci-vault-mcp-resolver.git
cd oci-vault-mcp-resolver

# Create tarball for transfer
tar czf oci-vault-mcp.tar.gz \
  oci_vault_resolver.py \
  wrappers/ \
  config/ \
  scripts/ \
  requirements.txt \
  pyproject.toml \
  README.md

# Transfer to remote server
scp oci-vault-mcp.tar.gz user@remote-server:~/
```

### Step 2: Extract and Install on Remote Server

SSH into the remote server:

```bash
ssh user@remote-server

# Extract files
cd ~
tar xzf oci-vault-mcp.tar.gz
cd oci-vault-mcp-resolver

# Run interactive installer
./scripts/install.sh
```

The installer will:
- ✅ Verify Python 3.9+ and pip
- ✅ Prompt for Vault OCID, Compartment OCID, Region
- ✅ Generate `~/.config/oci-vault-mcp/resolver.yaml`
- ✅ Install Python package: `pip3 install --user -e .`
- ✅ Install wrapper: `/usr/local/bin/mcp_vault_proxy.py` (optional)
- ✅ Optionally upload example secrets

### Step 3: Configure OCI Authentication

#### Option A: Instance Principal (OCI Compute)

```bash
# Edit resolver config
vim ~/.config/oci-vault-mcp/resolver.yaml

# Set auth_method
vault:
  auth_method: "instance_principal"
```

Ensure the instance is in a dynamic group with vault read permissions.

#### Option B: Config File (Non-OCI Servers)

```bash
# Create OCI config directory
mkdir -p ~/.oci
chmod 700 ~/.oci

# Create config file
cat > ~/.oci/config <<EOF
[DEFAULT]
user=ocid1.user.oc1..aaaaaaaayouruser
fingerprint=aa:bb:cc:dd:ee:ff:00:11:22:33:44:55:66:77:88:99
tenancy=ocid1.tenancy.oc1..aaaaaaaayourtenancy
region=eu-frankfurt-1
key_file=~/.oci/api_key.pem
EOF

chmod 600 ~/.oci/config
```

Generate API key pair locally and transfer the private key:

```bash
# On local machine
openssl genrsa -out ~/.oci/api_key.pem 2048
openssl rsa -pubout -in ~/.oci/api_key.pem -out ~/.oci/api_key_public.pem

# Upload public key to OCI Console: Identity → Users → API Keys

# Transfer private key to remote server
scp ~/.oci/api_key.pem user@remote-server:~/.oci/
ssh user@remote-server "chmod 600 ~/.oci/api_key.pem"
```

Edit resolver config:

```bash
vim ~/.config/oci-vault-mcp/resolver.yaml

# Set auth_method
vault:
  auth_method: "config_file"
  config_file: "~/.oci/config"
  config_profile: "DEFAULT"
```

### Step 4: Verify Installation

```bash
# Test vault connection
python3 -c "
from oci_vault_resolver import VaultResolver
resolver = VaultResolver.from_config()
print('✅ Vault connection successful')
print(f'Vault ID: {resolver.default_vault_id[:20]}...')
"

# Test wrapper (requires secrets in vault)
python3 /usr/local/bin/mcp_vault_proxy.py --service github --help
```

## Docker MCP Gateway Configuration

### Prerequisites

Install Docker MCP Gateway on the remote server:

```bash
# Install Docker (if not already installed)
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
newgrp docker

# Install Docker MCP Gateway
# Follow official installation guide at:
# https://github.com/docker/mcp-gateway
```

### Configuration File

Create Docker MCP Gateway config:

```bash
mkdir -p ~/.docker/mcp
cat > ~/.docker/mcp/config.yaml <<EOF
servers:
  # GitHub MCP Server with Vault Integration
  github-vault:
    command: python3
    args:
      - /usr/local/bin/mcp_vault_proxy.py
      - --service
      - github
    env:
      # Optional: Override environment
      # VAULT_ENV: production

  # PostgreSQL MCP Server with Vault Integration
  postgres-vault:
    command: python3
    args:
      - /usr/local/bin/mcp_vault_proxy.py
      - --service
      - postgres
    env:
      # Optional: Custom database host
      POSTGRES_HOST: db.example.com
      POSTGRES_PORT: "5432"

  # Anthropic MCP Server with Vault Integration
  anthropic-vault:
    command: python3
    args:
      - /usr/local/bin/mcp_vault_proxy.py
      - --service
      - anthropic

  # Custom MCP Server with Vault Integration
  custom-app:
    command: python3
    args:
      - /usr/local/bin/mcp_vault_proxy.py
      - --service
      - custom
      - --command
      - python3 /path/to/custom_mcp_server.py
EOF
```

### Multi-Environment Configuration

For production vs. development environments:

```yaml
servers:
  # Production GitHub
  github-prod:
    command: python3
    args:
      - /usr/local/bin/mcp_vault_proxy.py
      - --service
      - github
      - --env
      - production

  # Development GitHub
  github-dev:
    command: python3
    args:
      - /usr/local/bin/mcp_vault_proxy.py
      - --service
      - github
      - --env
      - development
```

Ensure secrets exist in vault:
- `mcp-github-token-prod` for production
- `mcp-github-token-dev` for development

### Start Docker MCP Gateway

```bash
# Start gateway
docker mcp gateway start

# Verify servers are running
docker mcp gateway list

# Check logs
docker mcp gateway logs github-vault
```

## Production Deployment

### Systemd Service (Optional)

For automatic startup on boot:

```bash
# Create systemd service
sudo tee /etc/systemd/system/docker-mcp-gateway.service <<EOF
[Unit]
Description=Docker MCP Gateway
After=docker.service
Requires=docker.service

[Service]
Type=simple
User=$USER
ExecStart=/usr/local/bin/docker mcp gateway start
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Enable and start service
sudo systemctl daemon-reload
sudo systemctl enable docker-mcp-gateway
sudo systemctl start docker-mcp-gateway

# Check status
sudo systemctl status docker-mcp-gateway
```

### Environment-Specific Deployment

```bash
# Development server
cat > ~/.config/oci-vault-mcp/resolver.yaml <<EOF
version: "1.0"
vault:
  vault_id: "ocid1.vault.oc1.REGION.DEV_VAULT"
  compartment_id: "ocid1.compartment.oc1..DEV_COMPARTMENT"
  region: "eu-frankfurt-1"
  auth_method: "config_file"
EOF

# Production server
cat > ~/.config/oci-vault-mcp/resolver.yaml <<EOF
version: "1.0"
vault:
  vault_id: "ocid1.vault.oc1.REGION.PROD_VAULT"
  compartment_id: "ocid1.compartment.oc1..PROD_COMPARTMENT"
  region: "eu-frankfurt-1"
  auth_method: "instance_principal"  # Use instance principal in prod

environments:
  production:
    vault:
      compartment_id: "ocid1.compartment.oc1..PROD_COMPARTMENT"
    secrets:
      GITHUB_PERSONAL_ACCESS_TOKEN: "mcp-github-token-prod"
      ANTHROPIC_API_KEY: "mcp-anthropic-key-prod"
      POSTGRES_PASSWORD: "mcp-postgres-password-prod"
EOF
```

### Security Hardening

```bash
# Restrict config file permissions
chmod 600 ~/.config/oci-vault-mcp/resolver.yaml
chmod 600 ~/.oci/config
chmod 600 ~/.oci/api_key.pem

# Restrict cache directory permissions
chmod 700 ~/.cache/oci-vault-mcp/

# Verify no secrets in environment
env | grep -i secret  # Should return nothing

# Audit vault access (OCI Console)
# Identity → Audit → Filter by "GetSecretBundleByName"
```

## Health Monitoring

### Manual Health Checks

```bash
# Test vault connectivity
python3 -c "
from oci_vault_resolver import VaultResolver
import asyncio

async def test():
    resolver = VaultResolver.from_config()
    try:
        # Attempt to resolve a test secret
        secret = await resolver.get_secret(
            'mcp-github-token',
            resolver.default_compartment_id,
            resolver.default_vault_id
        )
        print('✅ Vault connection: OK')
        print(f'✅ Secret resolution: OK (length: {len(secret)})')
    except Exception as e:
        print(f'❌ Vault connection: FAILED ({e})')

asyncio.run(test())
"

# Check Docker MCP Gateway status
docker mcp gateway list

# Check wrapper execution
python3 /usr/local/bin/mcp_vault_proxy.py --service github --help
```

### Automated Monitoring Script

Create a health check script:

```bash
cat > ~/check-mcp-health.sh <<'EOF'
#!/bin/bash
set -euo pipefail

echo "=== OCI Vault MCP Health Check ==="
echo "Timestamp: $(date -Iseconds)"
echo

# Check Python
if command -v python3 &> /dev/null; then
    echo "✅ Python: $(python3 --version)"
else
    echo "❌ Python: NOT FOUND"
    exit 1
fi

# Check config file
if [[ -f ~/.config/oci-vault-mcp/resolver.yaml ]]; then
    echo "✅ Config: ~/.config/oci-vault-mcp/resolver.yaml"
else
    echo "❌ Config: NOT FOUND"
    exit 1
fi

# Check OCI auth
if [[ -f ~/.oci/config ]]; then
    echo "✅ OCI Config: ~/.oci/config"
elif grep -q 'instance_principal' ~/.config/oci-vault-mcp/resolver.yaml; then
    echo "✅ OCI Auth: Instance Principal"
else
    echo "❌ OCI Auth: NOT CONFIGURED"
    exit 1
fi

# Check vault connection
echo -n "Checking vault connection... "
if python3 -c "from oci_vault_resolver import VaultResolver; VaultResolver.from_config()" 2>/dev/null; then
    echo "✅"
else
    echo "❌ FAILED"
    exit 1
fi

# Check Docker MCP Gateway
if docker mcp gateway list &> /dev/null; then
    echo "✅ Docker MCP Gateway: RUNNING"
    echo "   Servers: $(docker mcp gateway list | grep -c '✓' || echo 0)"
else
    echo "⚠️  Docker MCP Gateway: NOT RUNNING"
fi

echo
echo "=== Health Check: PASSED ==="
EOF

chmod +x ~/check-mcp-health.sh

# Run health check
~/check-mcp-health.sh
```

### Cron-Based Monitoring

```bash
# Add to crontab for hourly health checks
(crontab -l 2>/dev/null; echo "0 * * * * ~/check-mcp-health.sh >> ~/mcp-health.log 2>&1") | crontab -

# View health log
tail -f ~/mcp-health.log
```

### Prometheus Metrics (Advanced)

Export metrics for Prometheus:

```python
# ~/mcp_metrics_exporter.py
from prometheus_client import start_http_server, Gauge, Counter
from oci_vault_resolver import VaultResolver
import asyncio
import time

# Metrics
vault_up = Gauge('oci_vault_up', 'Vault reachability (1=up, 0=down)')
secret_resolution_duration = Gauge('oci_vault_secret_resolution_seconds', 'Secret resolution time')
secret_resolution_errors = Counter('oci_vault_secret_resolution_errors_total', 'Secret resolution errors')

async def collect_metrics():
    resolver = VaultResolver.from_config()

    while True:
        try:
            start = time.time()
            # Test secret resolution
            await resolver.get_secret(
                'mcp-github-token',
                resolver.default_compartment_id,
                resolver.default_vault_id
            )
            duration = time.time() - start

            vault_up.set(1)
            secret_resolution_duration.set(duration)
        except Exception:
            vault_up.set(0)
            secret_resolution_errors.inc()

        await asyncio.sleep(60)  # Check every minute

if __name__ == '__main__':
    start_http_server(9090)  # Expose on :9090/metrics
    asyncio.run(collect_metrics())
```

Run the exporter:

```bash
python3 ~/mcp_metrics_exporter.py &
```

## Troubleshooting

### Common Issues

#### 1. "Config file not found"

**Symptom:**
```
FileNotFoundError: Config file not found
```

**Solution:**
```bash
# Check config exists
ls -la ~/.config/oci-vault-mcp/resolver.yaml

# If missing, run installer
./scripts/install.sh

# Or create manually
mkdir -p ~/.config/oci-vault-mcp
cp config/resolver.yaml.example ~/.config/oci-vault-mcp/resolver.yaml
vim ~/.config/oci-vault-mcp/resolver.yaml  # Edit with your OCIDs
```

#### 2. "Authentication failed"

**Symptom:**
```
ServiceError: [401] NotAuthenticated
```

**Solution:**

For config file auth:
```bash
# Verify OCI config
cat ~/.oci/config

# Test OCI CLI
oci iam region list

# Check API key permissions in OCI Console
# Identity → Users → API Keys
```

For instance principal:
```bash
# Verify instance is in dynamic group
oci compute instance get --instance-id $(curl -s http://169.254.169.254/opc/v1/instance/ | jq -r .id)

# Check dynamic group has vault read permissions
# Identity → Dynamic Groups → Matching Rules
```

#### 3. "Secret not found"

**Symptom:**
```
ServiceError: [404] NotAuthorizedOrNotFound
```

**Solution:**
```bash
# List secrets in vault
oci vault secret list \
  --compartment-id "YOUR_COMPARTMENT_OCID" \
  --vault-id "YOUR_VAULT_OCID" \
  --query 'data[].{Name:"secret-name"}' \
  --output table

# Verify secret name matches config
grep -A 10 'secrets:' ~/.config/oci-vault-mcp/resolver.yaml

# Upload missing secret
./scripts/upload-secret.sh mcp-github-token "ghp_yourtoken"
```

#### 4. "Connection timeout"

**Symptom:**
```
requests.exceptions.ConnectTimeout
```

**Solution:**
```bash
# Check network connectivity to OCI
ping objectstorage.eu-frankfurt-1.oraclecloud.com

# Test HTTPS connectivity
curl -I https://iaas.eu-frankfurt-1.oraclecloud.com

# Check firewall rules (outbound 443 required)
sudo iptables -L OUTPUT -n | grep 443

# If behind corporate proxy, set proxy env vars
export https_proxy=http://proxy.example.com:8080
export no_proxy=169.254.169.254  # Instance metadata
```

#### 5. "Docker MCP Gateway won't start"

**Symptom:**
```
Error starting server: github-vault
```

**Solution:**
```bash
# Check wrapper execution
python3 /usr/local/bin/mcp_vault_proxy.py --service github

# Check Python path in config
which python3
# Update ~/.docker/mcp/config.yaml if needed

# Check logs
docker mcp gateway logs github-vault

# Verify wrapper permissions
ls -la /usr/local/bin/mcp_vault_proxy.py
chmod +x /usr/local/bin/mcp_vault_proxy.py
```

### Debug Mode

Enable verbose logging:

```bash
# Edit resolver config
vim ~/.config/oci-vault-mcp/resolver.yaml

# Set logging level
logging:
  level: "DEBUG"
  verbose: true

# Run wrapper with debug output
python3 /usr/local/bin/mcp_vault_proxy.py --service github 2>&1 | tee debug.log
```

### Cache Issues

```bash
# Clear cache if stale secrets
rm -rf ~/.cache/oci-vault-mcp/*

# Disable cache temporarily
vim ~/.config/oci-vault-mcp/resolver.yaml

cache:
  ttl: 0  # Disable caching
```

## Security Best Practices

### 1. Use Instance Principal in Production

```yaml
# Recommended for OCI Compute instances
vault:
  auth_method: "instance_principal"
```

**Advantages:**
- ✅ No API keys to manage or rotate
- ✅ No credentials stored on disk
- ✅ Automatic credential rotation by OCI
- ✅ Scoped to instance identity

### 2. Restrict File Permissions

```bash
# Config file (contains vault OCIDs)
chmod 600 ~/.config/oci-vault-mcp/resolver.yaml

# OCI config (contains API key path)
chmod 600 ~/.oci/config

# API private key (sensitive)
chmod 600 ~/.oci/api_key.pem

# Cache directory (contains cached secrets)
chmod 700 ~/.cache/oci-vault-mcp/
```

### 3. Enable Circuit Breaker

Prevent cascading failures:

```yaml
resilience:
  enable_circuit_breaker: true
  circuit_breaker_threshold: 5  # Open after 5 failures
  max_retries: 3
```

### 4. Audit Vault Access

```bash
# View audit logs in OCI Console
# Governance → Audit → Filter by:
# - Service: Vault
# - Event: GetSecretBundleByName

# Or via CLI
oci audit event list \
  --compartment-id "YOUR_COMPARTMENT_OCID" \
  --start-time "2024-01-01T00:00:00Z" \
  --end-time "2024-01-31T23:59:59Z" \
  --query 'data[?contains("event-name", `GetSecret`)]'
```

### 5. Rotate Secrets Regularly

```bash
# Create new secret version in vault
./scripts/upload-secret.sh mcp-github-token "ghp_newtoken"

# Clear cache to force refresh
rm -rf ~/.cache/oci-vault-mcp/*

# Restart Docker MCP Gateway
docker mcp gateway restart github-vault
```

### 6. Network Security

```bash
# Restrict outbound to OCI regions only
sudo iptables -A OUTPUT -p tcp --dport 443 -d objectstorage.eu-frankfurt-1.oraclecloud.com -j ACCEPT
sudo iptables -A OUTPUT -p tcp --dport 443 -j DROP

# Or use security groups in OCI
# Networking → Virtual Cloud Networks → Security Lists
# Egress Rule: HTTPS (443) to OCI Services
```

### 7. Disable Core Dumps

Prevent secrets from leaking in crash dumps:

```bash
# Disable core dumps for user
echo "* soft core 0" | sudo tee -a /etc/security/limits.conf
echo "* hard core 0" | sudo tee -a /etc/security/limits.conf

# Verify
ulimit -c  # Should output: 0
```

### 8. Use Secret Rotation

Update resolver config with rotation support:

```yaml
secrets:
  # Primary secret
  GITHUB_PERSONAL_ACCESS_TOKEN: "mcp-github-token"

  # Fallback during rotation
  GITHUB_PERSONAL_ACCESS_TOKEN_BACKUP: "mcp-github-token-old"
```

Rotation workflow:
1. Create new secret: `mcp-github-token-new`
2. Update config to use `-new` suffix
3. Test with new secret
4. Delete old secret version

### 9. Monitor Secret Access

```bash
# Enable audit logging
vim ~/.config/oci-vault-mcp/resolver.yaml

logging:
  level: "INFO"
  audit_secret_access: true  # Log all secret retrievals

# View access log
tail -f ~/.cache/oci-vault-mcp/audit.log
```

### 10. Principle of Least Privilege

IAM policy for minimal access:

```hcl
# Only read secret-bundles (not manage secrets)
allow group mcp-users to read secret-bundles in compartment MyApp where target.secret.name =~ 'mcp-*'

# Instance principal scoped to specific compartment
allow dynamic-group mcp-instances to read secret-bundles in compartment MyApp where target.secret.name =~ 'mcp-*'
```

## Next Steps

- ✅ Verify installation with health checks
- ✅ Configure Docker MCP Gateway with desired services
- ✅ Set up monitoring and alerting
- ✅ Document your secret naming conventions
- ✅ Implement secret rotation workflow
- ✅ Configure backup/DR for config files

For more information:
- [NAMING_CONVENTIONS.md](NAMING_CONVENTIONS.md) - Secret naming guide
- [DOCKER_MCP_INTEGRATION.md](../DOCKER_MCP_INTEGRATION.md) - Docker MCP Gateway integration
- [README.md](../README.md) - Project overview
- [OCI Vault Documentation](https://docs.oracle.com/en-us/iaas/Content/KeyManagement/home.htm)
