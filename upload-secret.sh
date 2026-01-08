#!/bin/bash
# Upload a secret to OCI Vault
#
# This script creates or updates secrets in Oracle Cloud Infrastructure Vault
# using the OCI CLI. It handles base64 encoding and automatically manages
# encryption keys.
#
# Prerequisites:
#   - OCI CLI installed and configured (oci setup config)
#   - Permissions: manage secret-family in compartment
#   - Existing vault with a master encryption key
#
# Usage:
#   ./upload-secret.sh <secret-name> <secret-value>
#
# Examples:
#   ./upload-secret.sh my-api-key "sk-1234567890abcdef"
#   ./upload-secret.sh github-token "ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
#   ./upload-secret.sh database-password "MySecureP@ssw0rd"
#
# Environment Variables (required):
#   OCI_VAULT_COMPARTMENT_ID - OCID of the compartment containing the vault
#   OCI_VAULT_ID             - OCID of the vault to store secrets in
#   OCI_REGION               - OCI region (e.g., us-phoenix-1, eu-frankfurt-1)
#
# Optional Environment Variables:
#   OCI_KMS_ENDPOINT         - Custom KMS endpoint (auto-detected if not set)
#
# Configuration Example:
#   export OCI_VAULT_COMPARTMENT_ID="ocid1.compartment.oc1..aaaaaaaXXXXXX"
#   export OCI_VAULT_ID="ocid1.vault.oc1.region.aaaaaaaXXXXXX"
#   export OCI_REGION="us-phoenix-1"
#

set -e

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Helper functions
error() {
    echo -e "${RED}Error: $1${NC}" >&2
    exit 1
}

info() {
    echo -e "${GREEN}$1${NC}"
}

warn() {
    echo -e "${YELLOW}Warning: $1${NC}"
}

# Validate arguments
if [ $# -ne 2 ]; then
    error "Usage: $0 <secret-name> <secret-value>

Examples:
  $0 my-api-key \"sk-1234567890abcdef\"
  $0 github-token \"ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx\"

Environment variables required:
  OCI_VAULT_COMPARTMENT_ID - Compartment OCID
  OCI_VAULT_ID             - Vault OCID
  OCI_REGION               - OCI region"
fi

SECRET_NAME="$1"
SECRET_VALUE="$2"

# Validate environment variables
if [ -z "$OCI_VAULT_COMPARTMENT_ID" ]; then
    error "OCI_VAULT_COMPARTMENT_ID environment variable is required.

Set it with:
  export OCI_VAULT_COMPARTMENT_ID=\"ocid1.compartment.oc1..aaaaaaaXXXXXX\"

Or find your compartment OCID:
  oci iam compartment list --query 'data[*].{name:name,id:id}' --output table"
fi

if [ -z "$OCI_VAULT_ID" ]; then
    error "OCI_VAULT_ID environment variable is required.

Set it with:
  export OCI_VAULT_ID=\"ocid1.vault.oc1.region.aaaaaaaXXXXXX\"

Or find your vault OCID:
  oci kms management vault list --compartment-id \"$OCI_VAULT_COMPARTMENT_ID\" --query 'data[*].{name:\"display-name\",id:id}' --output table"
fi

if [ -z "$OCI_REGION" ]; then
    error "OCI_REGION environment variable is required.

Set it with:
  export OCI_REGION=\"us-phoenix-1\"

Or list available regions:
  oci iam region list --query 'data[*].name' --output table"
fi

# Derive KMS endpoint from vault ID if not provided
if [ -z "$OCI_KMS_ENDPOINT" ]; then
    # Extract vault identifier from OCID (e.g., bfpizfqyaacmg from ocid1.vault.oc1.eu-frankfurt-1.bfpizfqyaacmg.xxx)
    VAULT_IDENTIFIER=$(echo "$OCI_VAULT_ID" | awk -F'.' '{print $(NF-1)}')
    OCI_KMS_ENDPOINT="https://${VAULT_IDENTIFIER}-management.kms.${OCI_REGION}.oraclecloud.com"
    info "Auto-detected KMS endpoint: $OCI_KMS_ENDPOINT"
fi

# Validate OCI CLI is installed
if ! command -v oci &> /dev/null; then
    error "OCI CLI is not installed.

Install it with:
  bash -c \"\$(curl -L https://raw.githubusercontent.com/oracle/oci-cli/master/scripts/install/install.sh)\"

Or see: https://docs.oracle.com/en-us/iaas/Content/API/SDKDocs/cliinstall.htm"
fi

# Validate OCI CLI is configured
if ! oci iam region list &> /dev/null; then
    error "OCI CLI is not configured.

Configure it with:
  oci setup config

This will create ~/.oci/config with your credentials."
fi

info "Uploading secret '$SECRET_NAME' to OCI Vault..."

# Get master encryption key from vault
echo "Finding encryption key..."
KEY_ID=$(oci --endpoint "$OCI_KMS_ENDPOINT" kms management key list \
  --compartment-id "$OCI_VAULT_COMPARTMENT_ID" \
  --query 'data[0].id' \
  --raw-output 2>/dev/null)

if [ -z "$KEY_ID" ] || [ "$KEY_ID" = "null" ]; then
    error "Could not find encryption key in vault.

Create a key with:
  oci kms management key create \\
    --compartment-id \"$OCI_VAULT_COMPARTMENT_ID\" \\
    --display-name \"vault-master-key\" \\
    --endpoint \"$OCI_KMS_ENDPOINT\" \\
    --key-shape '{\"algorithm\":\"AES\",\"length\":32}'"
fi

info "Using encryption key: ${KEY_ID:0:50}..."

# Check if secret already exists
echo "Checking if secret exists..."
EXISTING_SECRET=$(oci vault secret list \
  --compartment-id "$OCI_VAULT_COMPARTMENT_ID" \
  --name "$SECRET_NAME" \
  --region "$OCI_REGION" \
  --query 'data[0].id' \
  --raw-output 2>/dev/null || echo "")

# Base64 encode the secret value
SECRET_BASE64=$(echo -n "$SECRET_VALUE" | base64 -w 0)

if [ -n "$EXISTING_SECRET" ] && [ "$EXISTING_SECRET" != "null" ]; then
    # Update existing secret
    warn "Secret '$SECRET_NAME' already exists. Updating..."

    RESULT=$(oci vault secret update-base64 \
        --secret-id "$EXISTING_SECRET" \
        --secret-content-content "$SECRET_BASE64" \
        --region "$OCI_REGION" \
        --query 'data.id' \
        --raw-output)

    info "✓ Updated secret '$SECRET_NAME'"
    info "  Secret OCID: $RESULT"
else
    # Create new secret
    echo "Creating new secret..."

    RESULT=$(oci vault secret create-base64 \
        --compartment-id "$OCI_VAULT_COMPARTMENT_ID" \
        --vault-id "$OCI_VAULT_ID" \
        --key-id "$KEY_ID" \
        --secret-name "$SECRET_NAME" \
        --secret-content-content "$SECRET_BASE64" \
        --region "$OCI_REGION" \
        --query 'data.id' \
        --raw-output)

    info "✓ Created secret '$SECRET_NAME'"
    info "  Secret OCID: $RESULT"
fi

# Provide usage instructions
echo ""
info "Secret uploaded successfully!"
echo ""
echo "To use this secret with OCI Vault MCP Resolver:"
echo "  oci-vault://$RESULT"
echo ""
echo "Or by compartment + name:"
echo "  oci-vault://$OCI_VAULT_COMPARTMENT_ID/$SECRET_NAME"
echo ""
echo "To retrieve the secret value:"
echo "  oci secrets secret-bundle get --secret-id \"$RESULT\" \\"
echo "    --query 'data.\"secret-bundle-content\".content' --raw-output | base64 -d"
