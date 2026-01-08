#!/bin/bash
# Quick setup script for OCI Vault MCP wrapper examples
# This script helps you create your first MCP server configuration with vault secrets

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Helper functions
error() { echo -e "${RED}Error: $1${NC}" >&2; exit 1; }
success() { echo -e "${GREEN}✓ $1${NC}"; }
info() { echo -e "${BLUE}ℹ $1${NC}"; }
warn() { echo -e "${YELLOW}⚠ $1${NC}"; }

# Check prerequisites
check_prereqs() {
    info "Checking prerequisites..."

    # Check for OCI CLI
    if ! command -v oci &> /dev/null; then
        error "OCI CLI not found. Install from: https://docs.oracle.com/iaas/Content/API/SDKDocs/cliinstall.htm"
    fi
    success "OCI CLI found"

    # Check for Node.js
    if ! command -v node &> /dev/null; then
        error "Node.js not found. Install from: https://nodejs.org/"
    fi
    success "Node.js found ($(node --version))"

    # Check OCI authentication
    if ! oci iam region list &> /dev/null; then
        error "OCI authentication failed. Run 'oci setup config' or configure Instance Principal"
    fi
    success "OCI authentication working"
}

# List available examples
list_examples() {
    echo ""
    info "Available example configurations:"
    echo ""
    echo "  1. github     - GitHub repository access (Personal Access Token)"
    echo "  2. postgres   - PostgreSQL database connection"
    echo "  3. anthropic  - Claude API integration"
    echo "  4. openai     - ChatGPT/OpenAI API integration"
    echo "  5. slack      - Multi-token Slack integration"
    echo "  6. custom     - Start from template for custom service"
    echo ""
}

# Get vault configuration
get_vault_config() {
    echo ""
    info "Vault Configuration"
    echo ""

    # Vault ID
    read -p "Enter OCI Vault OCID: " VAULT_ID
    if [[ ! $VAULT_ID =~ ^ocid1\.vault\. ]]; then
        error "Invalid Vault OCID format"
    fi

    # Compartment ID
    read -p "Enter Compartment OCID: " COMPARTMENT_ID
    if [[ ! $COMPARTMENT_ID =~ ^ocid1\.compartment\. ]]; then
        error "Invalid Compartment OCID format"
    fi

    # Encryption Key ID
    read -p "Enter Encryption Key OCID: " KEY_ID
    if [[ ! $KEY_ID =~ ^ocid1\.key\. ]]; then
        error "Invalid Key OCID format"
    fi

    success "Vault configuration captured"
}

# Create GitHub example
setup_github() {
    info "Setting up GitHub MCP server..."

    # Get GitHub token
    echo ""
    warn "Create a GitHub Personal Access Token at: https://github.com/settings/tokens"
    warn "Required scopes: repo, read:org, read:user"
    echo ""
    read -sp "Enter GitHub Personal Access Token: " GITHUB_TOKEN
    echo ""

    if [[ -z "$GITHUB_TOKEN" ]]; then
        error "GitHub token is required"
    fi

    # Create vault secret
    info "Creating vault secret: mcp-github-token"
    oci vault secret create-base64 \
        --compartment-id "$COMPARTMENT_ID" \
        --vault-id "$VAULT_ID" \
        --secret-name "mcp-github-token" \
        --key-id "$KEY_ID" \
        --secret-content-content "$(echo -n "$GITHUB_TOKEN" | base64)" \
        --wait-for-state ACTIVE \
        > /dev/null

    success "Secret created: mcp-github-token"

    # Copy example config
    CONFIG_PATH="$HOME/.config/mcp-wrappers/github.yaml"
    mkdir -p "$(dirname "$CONFIG_PATH")"
    cp github.yaml "$CONFIG_PATH"

    success "Config copied to: $CONFIG_PATH"
}

# Create PostgreSQL example
setup_postgres() {
    info "Setting up PostgreSQL MCP server..."

    # Get connection details
    echo ""
    read -p "PostgreSQL host: " PG_HOST
    read -p "PostgreSQL port [5432]: " PG_PORT
    PG_PORT=${PG_PORT:-5432}
    read -p "PostgreSQL database: " PG_DATABASE
    read -p "PostgreSQL user: " PG_USER
    read -sp "PostgreSQL password: " PG_PASSWORD
    echo ""

    # Build connection URL
    DATABASE_URL="postgresql://${PG_USER}:${PG_PASSWORD}@${PG_HOST}:${PG_PORT}/${PG_DATABASE}"

    # Create vault secret
    info "Creating vault secret: mcp-postgres-url"
    oci vault secret create-base64 \
        --compartment-id "$COMPARTMENT_ID" \
        --vault-id "$VAULT_ID" \
        --secret-name "mcp-postgres-url" \
        --key-id "$KEY_ID" \
        --secret-content-content "$(echo -n "$DATABASE_URL" | base64)" \
        --wait-for-state ACTIVE \
        > /dev/null

    success "Secret created: mcp-postgres-url"

    # Copy example config
    CONFIG_PATH="$HOME/.config/mcp-wrappers/postgres.yaml"
    mkdir -p "$(dirname "$CONFIG_PATH")"
    cp postgres.yaml "$CONFIG_PATH"

    success "Config copied to: $CONFIG_PATH"
}

# Create Anthropic example
setup_anthropic() {
    info "Setting up Anthropic (Claude) API..."

    # Get API key
    echo ""
    warn "Get your Claude API key at: https://console.anthropic.com/settings/keys"
    echo ""
    read -sp "Enter Anthropic API Key: " ANTHROPIC_KEY
    echo ""

    if [[ ! $ANTHROPIC_KEY =~ ^sk-ant-api ]]; then
        warn "API key doesn't start with 'sk-ant-api'. Are you sure it's correct?"
        read -p "Continue anyway? (y/n): " CONTINUE
        if [[ $CONTINUE != "y" ]]; then
            error "Setup cancelled"
        fi
    fi

    # Create vault secret
    info "Creating vault secret: mcp-anthropic-api-key"
    oci vault secret create-base64 \
        --compartment-id "$COMPARTMENT_ID" \
        --vault-id "$VAULT_ID" \
        --secret-name "mcp-anthropic-api-key" \
        --key-id "$KEY_ID" \
        --secret-content-content "$(echo -n "$ANTHROPIC_KEY" | base64)" \
        --wait-for-state ACTIVE \
        > /dev/null

    success "Secret created: mcp-anthropic-api-key"

    # Copy example config
    CONFIG_PATH="$HOME/.config/mcp-wrappers/anthropic.yaml"
    mkdir -p "$(dirname "$CONFIG_PATH")"
    cp anthropic.yaml "$CONFIG_PATH"

    warn "Note: Update the 'command' in $CONFIG_PATH with your actual MCP server path"
    success "Config copied to: $CONFIG_PATH"
}

# Create OpenAI example
setup_openai() {
    info "Setting up OpenAI API..."

    # Get API key
    echo ""
    warn "Get your OpenAI API key at: https://platform.openai.com/api-keys"
    echo ""
    read -sp "Enter OpenAI API Key: " OPENAI_KEY
    echo ""

    if [[ ! $OPENAI_KEY =~ ^sk-proj ]]; then
        warn "API key doesn't start with 'sk-proj'. Are you sure it's correct?"
        read -p "Continue anyway? (y/n): " CONTINUE
        if [[ $CONTINUE != "y" ]]; then
            error "Setup cancelled"
        fi
    fi

    # Create vault secret
    info "Creating vault secret: mcp-openai-api-key"
    oci vault secret create-base64 \
        --compartment-id "$COMPARTMENT_ID" \
        --vault-id "$VAULT_ID" \
        --secret-name "mcp-openai-api-key" \
        --key-id "$KEY_ID" \
        --secret-content-content "$(echo -n "$OPENAI_KEY" | base64)" \
        --wait-for-state ACTIVE \
        > /dev/null

    success "Secret created: mcp-openai-api-key"

    # Optional: Organization ID
    read -p "Do you have an OpenAI Organization ID? (y/n): " HAS_ORG
    if [[ $HAS_ORG == "y" ]]; then
        read -p "Enter Organization ID: " ORG_ID
        info "Creating vault secret: mcp-openai-org-id"
        oci vault secret create-base64 \
            --compartment-id "$COMPARTMENT_ID" \
            --vault-id "$VAULT_ID" \
            --secret-name "mcp-openai-org-id" \
            --key-id "$KEY_ID" \
            --secret-content-content "$(echo -n "$ORG_ID" | base64)" \
            --wait-for-state ACTIVE \
            > /dev/null
        success "Secret created: mcp-openai-org-id"
    fi

    # Copy example config
    CONFIG_PATH="$HOME/.config/mcp-wrappers/openai.yaml"
    mkdir -p "$(dirname "$CONFIG_PATH")"
    cp openai.yaml "$CONFIG_PATH"

    warn "Note: Update the 'command' in $CONFIG_PATH with your actual MCP server path"
    success "Config copied to: $CONFIG_PATH"
}

# Create custom example from template
setup_custom() {
    info "Setting up custom service from template..."

    echo ""
    read -p "Enter service name (lowercase, no spaces): " SERVICE_NAME
    SERVICE_NAME=$(echo "$SERVICE_NAME" | tr '[:upper:]' '[:lower:]' | tr -d ' ')

    if [[ -z "$SERVICE_NAME" ]]; then
        error "Service name is required"
    fi

    # Copy template
    CONFIG_PATH="$HOME/.config/mcp-wrappers/${SERVICE_NAME}.yaml"
    mkdir -p "$(dirname "$CONFIG_PATH")"
    cp template.yaml "$CONFIG_PATH"

    success "Template copied to: $CONFIG_PATH"
    info "Next steps:"
    echo "  1. Edit $CONFIG_PATH"
    echo "  2. Update 'command' and 'args' for your MCP server"
    echo "  3. Define required environment variables"
    echo "  4. Create vault secrets with pattern: mcp-${SERVICE_NAME}-{type}"
    echo "  5. Test: node ../wrapper.js --config $CONFIG_PATH"
}

# Test configuration
test_config() {
    local CONFIG_PATH="$1"
    local WRAPPER_PATH="$(dirname "$(dirname "$(readlink -f "$0")")")/wrapper.js"

    echo ""
    info "Testing configuration..."

    if [[ ! -f "$WRAPPER_PATH" ]]; then
        error "Wrapper not found at: $WRAPPER_PATH"
    fi

    # Run wrapper with timeout
    timeout 5s node "$WRAPPER_PATH" --config "$CONFIG_PATH" &
    local PID=$!

    sleep 2

    if ps -p $PID > /dev/null; then
        success "MCP server started successfully (PID: $PID)"
        kill $PID 2>/dev/null || true
        return 0
    else
        error "MCP server failed to start. Check logs above."
    fi
}

# Main script
main() {
    echo ""
    info "OCI Vault MCP Wrapper Setup"
    echo ""

    # Check prerequisites
    check_prereqs

    # List examples
    list_examples

    # Get user choice
    read -p "Select example (1-6): " CHOICE

    # Get vault config (needed for all except custom)
    if [[ "$CHOICE" != "6" ]]; then
        get_vault_config
    fi

    # Execute setup based on choice
    case $CHOICE in
        1)
            setup_github
            CONFIG_PATH="$HOME/.config/mcp-wrappers/github.yaml"
            ;;
        2)
            setup_postgres
            CONFIG_PATH="$HOME/.config/mcp-wrappers/postgres.yaml"
            ;;
        3)
            setup_anthropic
            CONFIG_PATH="$HOME/.config/mcp-wrappers/anthropic.yaml"
            ;;
        4)
            setup_openai
            CONFIG_PATH="$HOME/.config/mcp-wrappers/openai.yaml"
            ;;
        5)
            error "Slack setup not yet implemented. Use 'slack.yaml' as reference."
            ;;
        6)
            setup_custom
            CONFIG_PATH="$HOME/.config/mcp-wrappers/${SERVICE_NAME}.yaml"
            ;;
        *)
            error "Invalid choice"
            ;;
    esac

    # Test configuration
    read -p "Test configuration now? (y/n): " TEST
    if [[ $TEST == "y" ]]; then
        test_config "$CONFIG_PATH"
    fi

    # Summary
    echo ""
    success "Setup complete!"
    echo ""
    info "Next steps:"
    echo "  1. Review config: cat $CONFIG_PATH"
    echo "  2. Test wrapper: node ../wrapper.js --config $CONFIG_PATH"
    echo "  3. Add to Claude Desktop (see README.md)"
    echo ""
    info "Vault secrets created (verify):"
    echo "  oci vault secret list --compartment-id \"$COMPARTMENT_ID\" --vault-id \"$VAULT_ID\" --query 'data[?starts_with(\"secret-name\", \`mcp-\`)]'"
    echo ""
}

# Run main
main
