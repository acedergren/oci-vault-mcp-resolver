#!/bin/bash
# Demo script for OCI Vault + Docker MCP Gateway integration
# This demonstrates fetching GitHub PAT from OCI Vault and starting the GitHub MCP server

set -euo pipefail

echo "=========================================="
echo "OCI Vault + Docker MCP Gateway Demo"
echo "=========================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Step 1: Verify OCI configuration
echo -e "${BLUE}Step 1: Verifying OCI configuration...${NC}"
if [ ! -f ~/.oci/config ]; then
    echo -e "${RED}❌ OCI config file not found at ~/.oci/config${NC}"
    echo "Please configure OCI CLI first: https://docs.oracle.com/iaas/Content/API/Concepts/sdkconfig.htm"
    exit 1
fi
echo -e "${GREEN}✅ OCI config found${NC}"
echo ""

# Step 2: Test OCI Vault connection
echo -e "${BLUE}Step 2: Testing OCI Vault connection...${NC}"
if ! oci iam region list >/dev/null 2>&1; then
    echo -e "${RED}❌ Failed to connect to OCI. Please check your credentials.${NC}"
    exit 1
fi
echo -e "${GREEN}✅ OCI connection successful${NC}"
echo ""

# Step 3: Resolve GitHub PAT from OCI Vault
echo -e "${BLUE}Step 3: Resolving GitHub PAT from OCI Vault...${NC}"
GITHUB_TOKEN=$(python3 -c "
from oci_vault_resolver import VaultResolver
import sys

try:
    resolver = VaultResolver(config_file='~/.oci/config', verbose=False)
    vault_url = 'oci-vault://ocid1.vaultsecret.oc1.eu-frankfurt-1.amaaaaaahhxc6pya5mp5alyg7cai5563xzl6i7x5ecuzgnfhj5bqijyapwya'
    token = resolver.resolve_secret(vault_url)

    if token:
        print(token)
    else:
        sys.exit(1)
except Exception as e:
    print(f'Error: {e}', file=sys.stderr)
    sys.exit(1)
" 2>&1)

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Failed to resolve GitHub token from OCI Vault${NC}"
    echo "Error: $GITHUB_TOKEN"
    exit 1
fi

echo -e "${GREEN}✅ GitHub PAT resolved successfully${NC}"
echo -e "   Token: ${GITHUB_TOKEN:0:10}... (${#GITHUB_TOKEN} chars)"
echo ""

# Step 4: Validate token format
echo -e "${BLUE}Step 4: Validating token format...${NC}"
if [[ $GITHUB_TOKEN == ghp_* ]]; then
    echo -e "${GREEN}✅ Token format valid (ghp_ prefix)${NC}"
else
    echo -e "${YELLOW}⚠️  Warning: Unexpected token format (expected ghp_ prefix)${NC}"
fi
echo ""

# Step 5: Display metrics
echo -e "${BLUE}Step 5: Fetching resolver metrics...${NC}"
python3 -c "
from oci_vault_resolver import VaultResolver

resolver = VaultResolver(config_file='~/.oci/config', verbose=False)
vault_url = 'oci-vault://ocid1.vaultsecret.oc1.eu-frankfurt-1.amaaaaaahhxc6pya5mp5alyg7cai5563xzl6i7x5ecuzgnfhj5bqijyapwya'
token = resolver.resolve_secret(vault_url)

print(f'   Secrets fetched: {resolver.metrics[\"secrets_fetched\"]}')
print(f'   Cache hits: {resolver.metrics[\"cache_hits\"]}')
print(f'   Cache misses: {resolver.metrics[\"cache_misses\"]}')
print(f'   Retries: {resolver.metrics[\"retries\"]}')
print(f'   Circuit breaker opens: {resolver.metrics[\"circuit_breaker_opens\"]}')
print(f'   Total fetch time: {resolver.metrics[\"total_fetch_time\"]:.3f}s')
"
echo ""

# Step 6: Summary
echo "=========================================="
echo -e "${GREEN}✅ Demo Complete!${NC}"
echo "=========================================="
echo ""
echo "The OCI Vault Resolver successfully:"
echo "  1. ✅ Connected to OCI (eu-frankfurt-1)"
echo "  2. ✅ Fetched GitHub PAT from AC-vault"
echo "  3. ✅ Validated token format"
echo "  4. ✅ Tracked performance metrics"
echo ""
echo "Next Steps:"
echo "  • Use ./github_mcp_proxy.py to start GitHub MCP server"
echo "  • Configure Docker MCP Gateway (see DOCKER_MCP_INTEGRATION.md)"
echo "  • Test with: docker mcp gateway run"
echo ""
echo "Phase 3 Features Enabled:"
echo "  🔄 Circuit Breaker Pattern (5 failure threshold)"
echo "  ⏱️  Retry with Exponential Backoff (3 max retries)"
echo "  🔢 Secret Versioning (?version=N support)"
echo "  📊 Performance Metrics Tracking"
echo ""
