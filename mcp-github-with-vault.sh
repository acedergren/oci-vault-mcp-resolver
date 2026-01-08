#!/bin/bash
# MCP GitHub server launcher with OCI Vault integration
# This script resolves the GitHub PAT from OCI Vault before starting the GitHub MCP server

set -euo pipefail

# Resolve GitHub PAT from OCI Vault using our Python resolver
GITHUB_TOKEN=$(python3 -c "
from oci_vault_resolver import VaultResolver
import sys

# Use explicit config file path
resolver = VaultResolver(config_file='~/.oci/config', verbose=False)
vault_url = 'oci-vault://ocid1.vaultsecret.oc1.eu-frankfurt-1.amaaaaaahhxc6pya5mp5alyg7cai5563xzl6i7x5ecuzgnfhj5bqijyapwya'

try:
    token = resolver.resolve_secret(vault_url)
    if token:
        print(token)
    else:
        sys.exit(1)
except Exception as e:
    print(f'Error resolving GitHub token: {e}', file=sys.stderr)
    sys.exit(1)
")

# Export the resolved token
export GITHUB_PERSONAL_ACCESS_TOKEN="$GITHUB_TOKEN"

# Start the GitHub MCP server (adjust the command based on your setup)
# This assumes you have the GitHub MCP server installed
exec npx -y @modelcontextprotocol/server-github
