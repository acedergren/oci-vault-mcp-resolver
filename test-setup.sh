#!/bin/bash
#
# Test setup script for OCI Vault MCP Resolver
#
# This script helps you verify your setup and create a test secret.
#

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}==> OCI Vault MCP Resolver - Setup Test${NC}"
echo

# Check Python
echo -e "${BLUE}Checking Python...${NC}"
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version)
    echo -e "${GREEN}✓ Python found: $PYTHON_VERSION${NC}"
else
    echo -e "${RED}✗ Python 3 not found${NC}"
    exit 1
fi

# Check PyYAML
echo -e "${BLUE}Checking PyYAML...${NC}"
if python3 -c "import yaml" 2>/dev/null; then
    echo -e "${GREEN}✓ PyYAML installed${NC}"
else
    echo -e "${YELLOW}✗ PyYAML not found. Installing...${NC}"
    pip3 install --user PyYAML || {
        echo -e "${RED}Failed to install PyYAML${NC}"
        exit 1
    }
    echo -e "${GREEN}✓ PyYAML installed${NC}"
fi

# Check OCI CLI
echo -e "${BLUE}Checking OCI CLI...${NC}"
if command -v oci &> /dev/null; then
    OCI_VERSION=$(oci --version 2>&1 | head -1 || echo "unknown")
    echo -e "${GREEN}✓ OCI CLI found: $OCI_VERSION${NC}"
else
    echo -e "${RED}✗ OCI CLI not found${NC}"
    echo -e "${YELLOW}Install with: brew install oci-cli (macOS) or pip3 install oci-cli${NC}"
    exit 1
fi

# Check OCI CLI configuration
echo -e "${BLUE}Checking OCI CLI configuration...${NC}"
if oci iam compartment list --limit 1 &> /dev/null; then
    echo -e "${GREEN}✓ OCI CLI configured and authenticated${NC}"
else
    echo -e "${RED}✗ OCI CLI not configured or authentication failed${NC}"
    echo -e "${YELLOW}Run: oci setup config${NC}"
    exit 1
fi

# Check Docker
echo -e "${BLUE}Checking Docker MCP...${NC}"
if command -v docker &> /dev/null && docker mcp version &> /dev/null; then
    DOCKER_MCP_VERSION=$(docker mcp version 2>&1 | head -1 || echo "unknown")
    echo -e "${GREEN}✓ Docker MCP found: $DOCKER_MCP_VERSION${NC}"
else
    echo -e "${YELLOW}⚠ Docker MCP not found or not running${NC}"
    echo -e "${YELLOW}The resolver can still work, but integration with MCP Gateway won't be available${NC}"
fi

# List compartments
echo
echo -e "${BLUE}==> Available Compartments${NC}"
echo -e "${YELLOW}(You'll need a compartment OCID to create test secrets)${NC}"
echo
oci iam compartment list --all --query 'data[0:5].{Name:name, OCID:id}' 2>/dev/null || {
    echo -e "${YELLOW}Could not list compartments${NC}"
}

# List vaults
echo
echo -e "${BLUE}==> Checking for existing vaults${NC}"
COMPARTMENT_ID=$(oci iam compartment list --all --query 'data[0].id' --raw-output 2>/dev/null || echo "")

if [[ -n "$COMPARTMENT_ID" ]]; then
    VAULTS=$(oci kms management vault list --compartment-id "$COMPARTMENT_ID" --all --query 'data[0:3].{Name:"display-name", OCID:id}' 2>/dev/null || echo "[]")

    if [[ "$VAULTS" != "[]" ]]; then
        echo -e "${GREEN}Found vaults:${NC}"
        echo "$VAULTS"
    else
        echo -e "${YELLOW}No vaults found in compartment${NC}"
        echo -e "${YELLOW}You'll need to create a vault before creating secrets${NC}"
    fi
else
    echo -e "${YELLOW}Could not determine compartment for vault listing${NC}"
fi

# Offer to create test secret
echo
echo -e "${BLUE}==> Test Secret Creation${NC}"
read -p "Would you like to create a test secret? (y/N): " -n 1 -r
echo

if [[ $REPLY =~ ^[Yy]$ ]]; then
    # Get compartment
    read -p "Enter compartment OCID: " COMPARTMENT_ID

    # Check for vault
    echo -e "${BLUE}Looking for vaults in compartment...${NC}"
    VAULT_ID=$(oci kms management vault list \
        --compartment-id "$COMPARTMENT_ID" \
        --query 'data[0].id' \
        --raw-output 2>/dev/null || echo "")

    if [[ -z "$VAULT_ID" ]]; then
        echo -e "${YELLOW}No vault found. Creating one...${NC}"
        read -p "Enter vault name (default: mcp-secrets): " VAULT_NAME
        VAULT_NAME=${VAULT_NAME:-mcp-secrets}

        VAULT_ID=$(oci kms management vault create \
            --compartment-id "$COMPARTMENT_ID" \
            --display-name "$VAULT_NAME" \
            --vault-type DEFAULT \
            --query 'data.id' \
            --raw-output)

        echo -e "${GREEN}✓ Vault created: $VAULT_ID${NC}"
        echo -e "${YELLOW}⚠ Waiting for vault to become active (this may take a minute)...${NC}"
        sleep 10
    else
        echo -e "${GREEN}✓ Using existing vault: $VAULT_ID${NC}"
    fi

    # Get management endpoint
    MGMT_ENDPOINT=$(oci kms management vault get \
        --vault-id "$VAULT_ID" \
        --query 'data."management-endpoint"' \
        --raw-output)

    echo -e "${GREEN}✓ Management endpoint: $MGMT_ENDPOINT${NC}"

    # Check for key
    KEY_ID=$(oci kms management key list \
        --compartment-id "$COMPARTMENT_ID" \
        --endpoint "$MGMT_ENDPOINT" \
        --query 'data[0].id' \
        --raw-output 2>/dev/null || echo "")

    if [[ -z "$KEY_ID" ]]; then
        echo -e "${YELLOW}No key found. Creating one...${NC}"
        read -p "Enter key name (default: mcp-secrets-key): " KEY_NAME
        KEY_NAME=${KEY_NAME:-mcp-secrets-key}

        KEY_ID=$(oci kms management key create \
            --compartment-id "$COMPARTMENT_ID" \
            --display-name "$KEY_NAME" \
            --endpoint "$MGMT_ENDPOINT" \
            --key-shape '{"algorithm":"AES","length":32}' \
            --query 'data.id' \
            --raw-output)

        echo -e "${GREEN}✓ Key created: $KEY_ID${NC}"
    else
        echo -e "${GREEN}✓ Using existing key: $KEY_ID${NC}"
    fi

    # Create secret
    read -p "Enter secret name (default: test-mcp-secret): " SECRET_NAME
    SECRET_NAME=${SECRET_NAME:-test-mcp-secret}

    read -p "Enter secret value (default: test-value-123): " SECRET_VALUE
    SECRET_VALUE=${SECRET_VALUE:-test-value-123}

    echo -e "${BLUE}Creating secret...${NC}"
    SECRET_ID=$(oci vault secret create-base64 \
        --compartment-id "$COMPARTMENT_ID" \
        --secret-name "$SECRET_NAME" \
        --vault-id "$VAULT_ID" \
        --key-id "$KEY_ID" \
        --secret-content-content "$SECRET_VALUE" \
        --query 'data.id' \
        --raw-output)

    echo -e "${GREEN}✓ Secret created successfully!${NC}"
    echo
    echo -e "${BLUE}==> Secret Details${NC}"
    echo "Secret Name: $SECRET_NAME"
    echo "Secret OCID: $SECRET_ID"
    echo "Secret Value: $SECRET_VALUE"
    echo
    echo -e "${BLUE}==> Test the resolver${NC}"
    echo "Try these commands:"
    echo
    echo "# Test with direct OCID:"
    echo "echo 'test: oci-vault://$SECRET_ID' | python3 oci_vault_resolver.py"
    echo
    echo "# Test with compartment + name:"
    echo "echo 'test: oci-vault://$COMPARTMENT_ID/$SECRET_NAME' | python3 oci_vault_resolver.py"
    echo
    echo -e "${BLUE}==> Add to MCP config${NC}"
    echo "Add this to your MCP configuration:"
    echo "  MY_SECRET: oci-vault://$SECRET_ID"
    echo "  # or"
    echo "  MY_SECRET: oci-vault://$COMPARTMENT_ID/$SECRET_NAME"
fi

echo
echo -e "${GREEN}==> Setup verification complete!${NC}"
