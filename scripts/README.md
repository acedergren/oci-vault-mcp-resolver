# Installation Scripts

This directory contains installation and utility scripts for OCI Vault MCP Resolver.

## Scripts

### `install.sh`

Interactive installation script that guides you through the complete setup process.

**Features:**
- Pre-flight checks (python3, OCI CLI, pip3)
- Interactive prompts for OCI configuration
- Generates resolver configuration file
- Installs Python package and dependencies
- Optionally installs wrapper scripts to PATH
- Optionally uploads example secrets
- Colored output for better UX
- Dry-run mode for testing

**Usage:**

```bash
# Interactive installation
./scripts/install.sh

# Preview changes without applying
./scripts/install.sh --dry-run

# Install without wrapper scripts
./scripts/install.sh --no-wrappers

# Skip uploading example secrets
./scripts/install.sh --skip-secrets

# Show help
./scripts/install.sh --help
```

**What it does:**

1. **Pre-flight checks** - Validates that all required tools are installed
   - python3 (>= 3.8)
   - pip3
   - OCI CLI

2. **OCI configuration collection** - Interactively prompts for:
   - Vault OCID
   - Compartment OCID
   - Region (with auto-detection from ~/.oci/config)
   - Cache TTL (default: 3600 seconds)
   - Authentication method (config file or instance principals)

3. **Configuration generation** - Creates:
   - `~/.config/oci-vault-mcp/resolver.yaml` (permissions: 600)
   - `~/.cache/oci-vault-mcp/` cache directory (permissions: 700)

4. **Python package installation**
   - Installs package in development mode: `pip3 install --user -e .`
   - Installs dependencies: PyYAML, oci SDK
   - Verifies CLI tool is available: `oci-vault-resolve`

5. **Wrapper script installation** (optional)
   - Copies `mcp-with-vault` to `/usr/local/bin/`
   - Requires sudo privileges

6. **Example secrets upload** (optional)
   - Uploads test secrets: `mcp-example-token`, `mcp-example-api-key`
   - Uses the `upload-secret.sh` script

7. **Next steps display**
   - Configuration summary
   - Usage examples
   - Documentation links
   - Troubleshooting tips

**Requirements:**

- Python 3.8 or higher
- OCI CLI configured or instance principal access
- pip3 for Python package installation
- sudo (optional, for wrapper script installation)

**Configuration File:**

The generated configuration file (`~/.config/oci-vault-mcp/resolver.yaml`) contains:

```yaml
# OCI Vault Configuration
vault:
  vault_ocid: "ocid1.vault.oc1.region.xxx"
  compartment_ocid: "ocid1.compartment.oc1..xxx"
  region: "eu-frankfurt-1"

# Authentication
auth:
  use_instance_principals: false
  config_file: "/home/user/.oci/config"
  profile: "DEFAULT"

# Cache Configuration
cache:
  ttl: 3600
  directory: "/home/user/.cache/oci-vault-mcp"

# Logging
logging:
  level: INFO

# Resilience
resilience:
  max_retries: 3
  circuit_breaker_threshold: 5
  circuit_breaker_timeout: 60
```

**Idempotency:**

The script is safe to run multiple times:
- Existing configuration is not overwritten (prompts for confirmation)
- Directories are created with proper permissions
- Package installation uses `pip3 install -e` (can be updated)

**Troubleshooting:**

If installation fails:

1. **Pre-flight checks fail:**
   - Install missing dependencies (python3, pip3, OCI CLI)
   - Verify Python version: `python3 --version` (must be >= 3.8)

2. **OCI CLI not configured:**
   - Run `oci setup config` to configure
   - Or use instance principals on OCI compute instances

3. **Permission errors:**
   - Ensure write access to `~/.config/` and `~/.cache/`
   - For wrapper installation, ensure sudo access

4. **Package installation fails:**
   - Check internet connectivity for pip downloads
   - Verify pip3 is installed: `which pip3`
   - Try manual installation: `pip3 install --user PyYAML oci`

**Next Steps After Installation:**

1. Test the resolver:
   ```bash
   oci-vault-resolve --test
   ```

2. Create secrets in OCI Vault:
   ```bash
   ../upload-secret.sh \
     --vault-id ocid1.vault.oc1... \
     --compartment-id ocid1.compartment.oc1... \
     my-secret-name my-secret-value
   ```

3. Use in MCP configuration:
   ```yaml
   servers:
     my-server:
       config:
         API_KEY: oci-vault://ocid1.compartment.oc1.../my-secret-name
   ```

4. Resolve secrets:
   ```bash
   oci-vault-resolve < config.yaml > resolved-config.yaml
   ```

## Future Scripts

This directory may contain additional scripts in the future:

- `uninstall.sh` - Clean removal of all installed components
- `update.sh` - Update to latest version
- `test-installation.sh` - Verify installation integrity
- `migrate-config.sh` - Migrate from old config format

## Contributing

When adding new scripts to this directory:

1. Use `#!/bin/bash` shebang and `set -euo pipefail`
2. Include colored output for better UX (GREEN, YELLOW, RED)
3. Add helper functions: `info()`, `warn()`, `error()`, `success()`
4. Support `--dry-run` and `--help` flags
5. Make scripts idempotent (safe to run multiple times)
6. Document in this README
