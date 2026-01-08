# OCI Vault MCP Resolver Configuration

This directory contains the configuration schema for the OCI Vault MCP Resolver.

## Quick Start

1. **Copy the example configuration:**
   ```bash
   mkdir -p ~/.config/oci-vault-mcp
   cp config/resolver.yaml.example ~/.config/oci-vault-mcp/resolver.yaml
   ```

2. **Edit with your OCI Vault details:**
   ```bash
   nano ~/.config/oci-vault-mcp/resolver.yaml
   ```

3. **Update these required fields:**
   - `vault.vault_id` - Your OCI Vault OCID
   - `vault.compartment_id` - Compartment OCID where secrets are stored
   - `vault.region` - OCI region (e.g., eu-frankfurt-1)

## Configuration Locations

The resolver searches for configuration files in this priority order:

1. **User-level** (recommended):
   ```
   ~/.config/oci-vault-mcp/resolver.yaml
   ```

2. **System-level**:
   ```
   /etc/oci-vault-mcp/resolver.yaml
   ```

3. **Current directory**:
   ```
   ./resolver.yaml
   ```

4. **Environment variables** (highest priority, overrides file config):
   ```bash
   export OCI_VAULT_ID="ocid1.vault.oc1.region.xxx"
   export OCI_VAULT_COMPARTMENT_ID="ocid1.compartment.oc1..xxx"
   ```

## Configuration Schema

### Vault Settings

```yaml
vault:
  vault_id: "ocid1.vault.oc1.REGION.xxx"
  compartment_id: "ocid1.compartment.oc1..xxx"
  region: "eu-frankfurt-1"
  auth_method: "config_file"  # or "instance_principal"
  config_file: "~/.oci/config"
  config_profile: "DEFAULT"
```

**Authentication Methods:**

- `config_file` - Use OCI config file (`~/.oci/config`)
  - Best for: SSH servers, local development
  - Requires: OCI CLI configured

- `instance_principal` - Use Instance Principal authentication
  - Best for: OCI compute instances
  - Requires: IAM dynamic group policy

### Secret Mappings

Map environment variable names to OCI Vault secret names:

```yaml
secrets:
  GITHUB_PERSONAL_ACCESS_TOKEN: "mcp-github-token"
  ANTHROPIC_API_KEY: "mcp-anthropic-key"
  POSTGRES_PASSWORD: "mcp-postgres-password"
```

**Naming Convention:**

Follow the pattern: `mcp-{service}-{type}[-{environment}]`

Examples:
- `mcp-github-token` - GitHub Personal Access Token
- `mcp-postgres-password` - PostgreSQL password
- `mcp-github-token-prod` - Production GitHub token

See [NAMING_CONVENTIONS.md](../docs/NAMING_CONVENTIONS.md) for comprehensive examples.

### Environment Overrides

Define environment-specific configurations:

```yaml
environments:
  production:
    vault:
      compartment_id: "ocid1.compartment.oc1..PROD"
    cache:
      ttl: 1800  # 30 minutes
    secrets:
      GITHUB_PERSONAL_ACCESS_TOKEN: "mcp-github-token-prod"

  development:
    vault:
      compartment_id: "ocid1.compartment.oc1..DEV"
    cache:
      ttl: 7200  # 2 hours
    secrets:
      GITHUB_PERSONAL_ACCESS_TOKEN: "mcp-github-token-dev"
```

**Activate an environment:**

```bash
# Using command-line flag
python3 mcp_vault_proxy.py --service github --env production

# Using environment variable
export OCI_VAULT_ENVIRONMENT=production
python3 mcp_vault_proxy.py --service github
```

## Environment Variables

All configuration settings can be overridden with environment variables:

| Environment Variable | Config Path | Description |
|---------------------|-------------|-------------|
| `OCI_VAULT_ID` | `vault.vault_id` | Vault OCID |
| `OCI_VAULT_COMPARTMENT_ID` | `vault.compartment_id` | Compartment OCID |
| `OCI_REGION` | `vault.region` | OCI region |
| `OCI_USE_INSTANCE_PRINCIPALS` | `vault.auth_method` | Set to "true" for instance principal auth |
| `OCI_CONFIG_FILE` | `vault.config_file` | OCI config file path |
| `OCI_CONFIG_PROFILE` | `vault.config_profile` | OCI config profile name |
| `OCI_VAULT_CACHE_DIR` | `cache.directory` | Cache directory path |
| `OCI_VAULT_CACHE_TTL` | `cache.ttl` | Cache TTL in seconds |
| `OCI_VAULT_ENVIRONMENT` | (selects environment) | Environment name (production, development, etc.) |

## Example Configurations

### Remote SSH Server

```yaml
# ~/.config/oci-vault-mcp/resolver.yaml
version: "1.0"

vault:
  vault_id: "ocid1.vault.oc1.eu-frankfurt-1.xxx"
  compartment_id: "ocid1.compartment.oc1..xxx"
  region: "eu-frankfurt-1"
  auth_method: "config_file"
  config_file: "~/.oci/config"

secrets:
  GITHUB_PERSONAL_ACCESS_TOKEN: "mcp-github-token"
  POSTGRES_PASSWORD: "mcp-postgres-password"

cache:
  ttl: 3600
```

### OCI Compute Instance (Instance Principal)

```yaml
# /etc/oci-vault-mcp/resolver.yaml
version: "1.0"

vault:
  vault_id: "ocid1.vault.oc1.us-phoenix-1.xxx"
  compartment_id: "ocid1.compartment.oc1..xxx"
  region: "us-phoenix-1"
  auth_method: "instance_principal"

secrets:
  GITHUB_PERSONAL_ACCESS_TOKEN: "mcp-github-token-prod"
  ANTHROPIC_API_KEY: "mcp-anthropic-key-prod"

cache:
  ttl: 1800  # 30 minutes for production
```

### Multi-Environment Setup

```yaml
version: "1.0"

vault:
  vault_id: "ocid1.vault.oc1.eu-frankfurt-1.xxx"
  compartment_id: "ocid1.compartment.oc1..xxx"  # Default
  region: "eu-frankfurt-1"
  auth_method: "config_file"

secrets:
  GITHUB_PERSONAL_ACCESS_TOKEN: "mcp-github-token"
  ANTHROPIC_API_KEY: "mcp-anthropic-key"

environments:
  production:
    vault:
      compartment_id: "ocid1.compartment.oc1..prod"
    secrets:
      GITHUB_PERSONAL_ACCESS_TOKEN: "mcp-github-token-prod"
      ANTHROPIC_API_KEY: "mcp-anthropic-key-prod"

  staging:
    vault:
      compartment_id: "ocid1.compartment.oc1..staging"
    secrets:
      GITHUB_PERSONAL_ACCESS_TOKEN: "mcp-github-token-staging"
      ANTHROPIC_API_KEY: "mcp-anthropic-key-staging"

  development:
    vault:
      compartment_id: "ocid1.compartment.oc1..dev"
    secrets:
      GITHUB_PERSONAL_ACCESS_TOKEN: "mcp-github-token-dev"
      ANTHROPIC_API_KEY: "mcp-anthropic-key-dev"
```

## Validation

Test your configuration:

```bash
# Validate config loading
python3 -c "
from oci_vault_resolver import VaultResolver
resolver = VaultResolver.from_config()
print(f'✅ Config loaded successfully')
print(f'Vault ID: {resolver.default_vault_id[:30]}...')
print(f'Compartment ID: {resolver.default_compartment_id[:30]}...')
"
```

## Troubleshooting

### Config file not found

**Error:** `ConfigurationError: No resolver.yaml found in search paths`

**Solution:**
```bash
# Check search paths
ls -la ~/.config/oci-vault-mcp/resolver.yaml
ls -la /etc/oci-vault-mcp/resolver.yaml
ls -la ./resolver.yaml

# Copy example config
mkdir -p ~/.config/oci-vault-mcp
cp config/resolver.yaml.example ~/.config/oci-vault-mcp/resolver.yaml
```

### Invalid YAML syntax

**Error:** `yaml.YAMLError: ...`

**Solution:**
```bash
# Validate YAML syntax
python3 -c "
import yaml
with open('~/.config/oci-vault-mcp/resolver.yaml') as f:
    config = yaml.safe_load(f)
print('✅ YAML syntax is valid')
"
```

### Missing required fields

**Error:** `ConfigurationError: vault.vault_id is required`

**Solution:** Ensure all required fields are set:
- `vault.vault_id`
- `vault.compartment_id`
- `vault.region`

## Next Steps

1. **Upload secrets to OCI Vault:**
   ```bash
   ./scripts/upload-secret.sh mcp-github-token "ghp_your_token"
   ./scripts/upload-secret.sh mcp-anthropic-key "sk-ant-your-key"
   ```

2. **Test secret resolution:**
   ```bash
   python3 wrappers/mcp_vault_proxy.py --service github
   ```

3. **Configure Docker MCP Gateway:**
   ```yaml
   # ~/.docker/mcp/config.yaml
   servers:
     github-vault:
       command: python3
       args:
         - /usr/local/bin/mcp_vault_proxy.py
         - --service
         - github
   ```

## See Also

- [Naming Conventions](../docs/NAMING_CONVENTIONS.md) - Secret naming best practices
- [Docker MCP Integration](../DOCKER_MCP_INTEGRATION.md) - Integration guide
- [SSH Deployment](../docs/SSH_DEPLOYMENT.md) - Remote server setup
- [Troubleshooting](../docs/TROUBLESHOOTING.md) - Common issues and solutions
