#!/bin/bash
#
# OCI Vault MCP Resolver - Interactive Installation Script
#
# This script guides you through the setup process:
# 1. Validates prerequisites (python3, OCI CLI, pip3)
# 2. Collects OCI configuration (Vault OCID, Compartment OCID, Region)
# 3. Generates resolver configuration file
# 4. Installs Python package dependencies
# 5. Installs wrapper scripts to PATH
# 6. Optionally uploads example secrets to OCI Vault
#
# Usage:
#   ./scripts/install.sh           # Interactive installation
#   ./scripts/install.sh --dry-run # Preview changes without applying
#

set -euo pipefail

# ============================================================================
# Color Codes
# ============================================================================

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# ============================================================================
# Configuration
# ============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CONFIG_DIR="${HOME}/.config/oci-vault-mcp"
CONFIG_FILE="${CONFIG_DIR}/resolver.yaml"
CACHE_DIR="${HOME}/.cache/oci-vault-mcp"

DRY_RUN=false
SKIP_SECRETS=false
INSTALL_WRAPPERS=true

# ============================================================================
# Helper Functions
# ============================================================================

info() {
    echo -e "${BLUE}ℹ${NC} $*"
}

success() {
    echo -e "${GREEN}✓${NC} $*"
}

warn() {
    echo -e "${YELLOW}⚠${NC} $*"
}

error() {
    echo -e "${RED}✗${NC} $*" >&2
}

banner() {
    echo -e "${CYAN}${BOLD}"
    echo "════════════════════════════════════════════════════════════════"
    echo "  $*"
    echo "════════════════════════════════════════════════════════════════"
    echo -e "${NC}"
}

step() {
    echo -e "${BOLD}$*${NC}"
}

prompt() {
    local var_name="$1"
    local prompt_text="$2"
    local default_value="${3:-}"

    if [[ -n "$default_value" ]]; then
        read -r -p "$(echo -e "${CYAN}?${NC} ${prompt_text} [${default_value}]: ")" user_input
        eval "$var_name=\"\${user_input:-$default_value}\""
    else
        read -r -p "$(echo -e "${CYAN}?${NC} ${prompt_text}: ")" user_input
        eval "$var_name=\"\$user_input\""
    fi
}

confirm() {
    local prompt_text="$1"
    local default="${2:-n}"

    local options
    if [[ "$default" == "y" ]]; then
        options="[Y/n]"
    else
        options="[y/N]"
    fi

    read -r -p "$(echo -e "${CYAN}?${NC} ${prompt_text} ${options}: ")" response
    response="${response:-$default}"

    [[ "${response,,}" =~ ^y(es)?$ ]]
}

check_command() {
    local cmd="$1"
    local package="${2:-$1}"

    if command -v "$cmd" &> /dev/null; then
        success "$cmd is installed ($(command -v "$cmd"))"
        return 0
    else
        error "$cmd is not installed"
        info "Please install $package and try again"
        return 1
    fi
}

check_python_package() {
    local package="$1"

    if python3 -c "import $package" 2>/dev/null; then
        success "Python package '$package' is installed"
        return 0
    else
        warn "Python package '$package' is not installed"
        return 1
    fi
}

# ============================================================================
# Pre-flight Checks
# ============================================================================

preflight_checks() {
    banner "Pre-flight Checks"

    local all_ok=true

    step "Checking required commands..."
    check_command python3 || all_ok=false
    check_command pip3 "python3-pip" || all_ok=false
    check_command oci "oci-cli" || all_ok=false

    echo
    step "Checking Python version..."
    local python_version
    python_version=$(python3 --version | awk '{print $2}')
    local major minor
    major=$(echo "$python_version" | cut -d. -f1)
    minor=$(echo "$python_version" | cut -d. -f2)

    if [[ "$major" -ge 3 ]] && [[ "$minor" -ge 8 ]]; then
        success "Python $python_version (>= 3.8 required)"
    else
        error "Python $python_version is too old (>= 3.8 required)"
        all_ok=false
    fi

    echo
    step "Checking Python dependencies..."
    check_python_package yaml || info "PyYAML will be installed"
    check_python_package oci || info "oci SDK will be installed"

    echo
    step "Checking OCI CLI configuration..."
    if [[ -f "${HOME}/.oci/config" ]]; then
        success "OCI CLI config found at ${HOME}/.oci/config"

        # Extract default profile region
        local default_region
        if default_region=$(grep -A 10 '^\[DEFAULT\]' "${HOME}/.oci/config" | grep '^region=' | cut -d= -f2 | tr -d ' '); then
            if [[ -n "$default_region" ]]; then
                success "Default region: $default_region"
            fi
        fi
    else
        warn "OCI CLI config not found at ${HOME}/.oci/config"
        info "You can use instance principals on OCI compute instances"
    fi

    if [[ "$all_ok" == false ]]; then
        echo
        error "Pre-flight checks failed. Please fix the issues above and try again."
        exit 1
    fi

    echo
    success "All pre-flight checks passed"
}

# ============================================================================
# OCI Configuration Collection
# ============================================================================

collect_oci_config() {
    banner "OCI Configuration"

    info "This installer will help you configure OCI Vault integration."
    info "You'll need the following OCIDs from Oracle Cloud Infrastructure Console:"
    echo
    info "  1. Vault OCID - from Identity & Security > Vault"
    info "  2. Compartment OCID - from Identity & Security > Compartments"
    info "  3. Region - e.g., eu-frankfurt-1, us-ashburn-1"
    echo

    # Detect defaults from existing OCI config
    local default_region=""
    if [[ -f "${HOME}/.oci/config" ]]; then
        default_region=$(grep -A 10 '^\[DEFAULT\]' "${HOME}/.oci/config" | grep '^region=' | cut -d= -f2 | tr -d ' ' || echo "")
    fi

    # Vault OCID
    prompt VAULT_OCID "Enter your OCI Vault OCID"

    if [[ ! "$VAULT_OCID" =~ ^ocid1\.vault\.oc1\. ]]; then
        warn "The provided OCID doesn't look like a Vault OCID (should start with 'ocid1.vault.oc1.')"
        if ! confirm "Continue anyway?" "n"; then
            error "Installation cancelled"
            exit 1
        fi
    fi

    # Compartment OCID
    prompt COMPARTMENT_OCID "Enter your OCI Compartment OCID"

    if [[ ! "$COMPARTMENT_OCID" =~ ^ocid1\.compartment\.oc1\. ]] && [[ ! "$COMPARTMENT_OCID" =~ ^ocid1\.tenancy\.oc1\. ]]; then
        warn "The provided OCID doesn't look like a Compartment OCID (should start with 'ocid1.compartment.oc1.' or 'ocid1.tenancy.oc1.')"
        if ! confirm "Continue anyway?" "n"; then
            error "Installation cancelled"
            exit 1
        fi
    fi

    # Region
    prompt REGION "Enter your OCI Region" "${default_region:-eu-frankfurt-1}"

    # Cache TTL
    echo
    step "Cache Configuration"
    info "Secrets are cached locally to reduce API calls and improve performance."
    prompt CACHE_TTL "Cache TTL in seconds" "3600"

    # Instance principals
    echo
    step "Authentication Method"
    info "Choose how to authenticate with OCI:"
    info "  • Config file (~/.oci/config) - For local development"
    info "  • Instance principals - For OCI compute instances"
    echo

    if confirm "Use instance principals (OCI VM/Container)?" "n"; then
        USE_INSTANCE_PRINCIPALS="true"
        OCI_CONFIG_FILE=""
        OCI_PROFILE=""
    else
        USE_INSTANCE_PRINCIPALS="false"
        prompt OCI_CONFIG_FILE "OCI config file path" "${HOME}/.oci/config"
        prompt OCI_PROFILE "OCI config profile" "DEFAULT"
    fi

    echo
    success "Configuration collected successfully"
}

# ============================================================================
# Generate Configuration File
# ============================================================================

generate_config() {
    banner "Generating Configuration"

    if [[ "$DRY_RUN" == true ]]; then
        warn "DRY RUN: Would create directory: $CONFIG_DIR"
        warn "DRY RUN: Would write configuration to: $CONFIG_FILE"
    else
        step "Creating configuration directory..."
        mkdir -p "$CONFIG_DIR"
        chmod 700 "$CONFIG_DIR"
        success "Created $CONFIG_DIR"
    fi

    step "Generating resolver configuration..."

    local config_content
    config_content=$(cat <<EOF
# OCI Vault MCP Resolver Configuration
# Generated by install.sh on $(date -u +"%Y-%m-%d %H:%M:%S UTC")

# OCI Vault Configuration
vault:
  vault_ocid: "${VAULT_OCID}"
  compartment_ocid: "${COMPARTMENT_OCID}"
  region: "${REGION}"

# Authentication
auth:
  use_instance_principals: ${USE_INSTANCE_PRINCIPALS}
EOF
)

    if [[ "$USE_INSTANCE_PRINCIPALS" == "false" ]]; then
        config_content+=$(cat <<EOF

  config_file: "${OCI_CONFIG_FILE}"
  profile: "${OCI_PROFILE}"
EOF
)
    fi

    config_content+=$(cat <<EOF


# Cache Configuration
cache:
  ttl: ${CACHE_TTL}
  directory: "${CACHE_DIR}"

# Logging
logging:
  level: INFO  # DEBUG, INFO, WARNING, ERROR

# Resilience
resilience:
  max_retries: 3
  circuit_breaker_threshold: 5
  circuit_breaker_timeout: 60
EOF
)

    if [[ "$DRY_RUN" == true ]]; then
        warn "DRY RUN: Would write the following configuration:"
        echo "$config_content" | sed 's/^/  /'
    else
        echo "$config_content" > "$CONFIG_FILE"
        chmod 600 "$CONFIG_FILE"
        success "Configuration written to $CONFIG_FILE"
    fi

    # Create cache directory
    if [[ "$DRY_RUN" == true ]]; then
        warn "DRY RUN: Would create cache directory: $CACHE_DIR"
    else
        mkdir -p "$CACHE_DIR"
        chmod 700 "$CACHE_DIR"
        success "Created cache directory at $CACHE_DIR"
    fi
}

# ============================================================================
# Install Python Package
# ============================================================================

install_package() {
    banner "Installing Python Package"

    step "Installing oci-vault-mcp-resolver..."

    if [[ "$DRY_RUN" == true ]]; then
        warn "DRY RUN: Would run: pip3 install --user -e $PROJECT_ROOT"
    else
        cd "$PROJECT_ROOT"
        if pip3 install --user -e . ; then
            success "Python package installed successfully"
        else
            error "Failed to install Python package"
            return 1
        fi
    fi

    # Verify installation
    step "Verifying installation..."
    if [[ "$DRY_RUN" == true ]]; then
        warn "DRY RUN: Would verify installation with: oci-vault-resolve --version"
    else
        if command -v oci-vault-resolve &> /dev/null; then
            success "CLI tool 'oci-vault-resolve' is available"
        else
            warn "CLI tool not found in PATH"
            info "You may need to add ~/.local/bin to your PATH:"
            info "  export PATH=\"\$HOME/.local/bin:\$PATH\""
        fi
    fi
}

# ============================================================================
# Install Wrapper Scripts
# ============================================================================

install_wrappers() {
    if [[ "$INSTALL_WRAPPERS" != true ]]; then
        return 0
    fi

    banner "Installing Wrapper Scripts"

    local wrapper_script="$PROJECT_ROOT/mcp-with-vault"
    local install_path="/usr/local/bin/mcp-with-vault"

    if [[ ! -f "$wrapper_script" ]]; then
        warn "Wrapper script not found at $wrapper_script"
        return 0
    fi

    step "Installing mcp-with-vault wrapper..."

    if [[ "$DRY_RUN" == true ]]; then
        warn "DRY RUN: Would copy $wrapper_script to $install_path"
        warn "DRY RUN: Would run: sudo install -m 755 $wrapper_script $install_path"
    else
        if confirm "Install mcp-with-vault to /usr/local/bin? (requires sudo)" "y"; then
            if sudo install -m 755 "$wrapper_script" "$install_path"; then
                success "Installed mcp-with-vault to $install_path"
            else
                warn "Failed to install wrapper script (you can copy it manually)"
            fi
        else
            info "Skipping wrapper installation"
            info "You can manually copy $wrapper_script to your PATH"
        fi
    fi
}

# ============================================================================
# Upload Example Secrets
# ============================================================================

upload_example_secrets() {
    banner "Upload Example Secrets"

    info "You can optionally upload example secrets to test the integration."
    echo

    if ! confirm "Do you want to upload example secrets to OCI Vault?" "n"; then
        info "Skipping example secrets upload"
        return 0
    fi

    echo
    step "Example secrets to upload:"
    echo "  • mcp-example-token (for testing token-based authentication)"
    echo "  • mcp-example-api-key (for testing API key storage)"
    echo

    local upload_script="$PROJECT_ROOT/upload-secret.sh"

    if [[ ! -f "$upload_script" ]]; then
        warn "Upload script not found at $upload_script"
        return 0
    fi

    if [[ "$DRY_RUN" == true ]]; then
        warn "DRY RUN: Would upload example secrets using $upload_script"
        return 0
    fi

    # Upload example token
    step "Uploading mcp-example-token..."
    local example_token
    example_token="example-token-$(date +%s)"

    if "$upload_script" \
        --vault-id "$VAULT_OCID" \
        --compartment-id "$COMPARTMENT_OCID" \
        mcp-example-token \
        "$example_token" 2>&1 | grep -q "Secret created successfully"; then
        success "Uploaded mcp-example-token"
    else
        warn "Failed to upload mcp-example-token (you can do this manually later)"
    fi

    # Upload example API key
    step "Uploading mcp-example-api-key..."
    local example_api_key
    example_api_key="sk-$(openssl rand -hex 32)"

    if "$upload_script" \
        --vault-id "$VAULT_OCID" \
        --compartment-id "$COMPARTMENT_OCID" \
        mcp-example-api-key \
        "$example_api_key" 2>&1 | grep -q "Secret created successfully"; then
        success "Uploaded mcp-example-api-key"
    else
        warn "Failed to upload mcp-example-api-key (you can do this manually later)"
    fi

    echo
    success "Example secrets uploaded successfully"
}

# ============================================================================
# Print Next Steps
# ============================================================================

print_next_steps() {
    banner "Installation Complete"

    success "OCI Vault MCP Resolver has been installed successfully!"
    echo

    step "Configuration Summary:"
    echo "  • Config file: $CONFIG_FILE"
    echo "  • Cache directory: $CACHE_DIR"
    echo "  • Vault OCID: ${VAULT_OCID:0:30}..."
    echo "  • Compartment OCID: ${COMPARTMENT_OCID:0:30}..."
    echo "  • Region: $REGION"
    echo "  • Auth method: $([ "$USE_INSTANCE_PRINCIPALS" == "true" ] && echo "Instance principals" || echo "Config file")"
    echo

    step "Next Steps:"
    echo
    echo "1. Test the resolver with a sample secret:"
    echo "   ${CYAN}oci-vault-resolve --test${NC}"
    echo
    echo "2. Create secrets in OCI Vault (using the upload script):"
    echo "   ${CYAN}$PROJECT_ROOT/upload-secret.sh \\"
    echo "     --vault-id $VAULT_OCID \\"
    echo "     --compartment-id $COMPARTMENT_OCID \\"
    echo "     my-secret-name my-secret-value${NC}"
    echo
    echo "3. Use oci-vault:// URLs in your MCP configuration:"
    echo "   ${CYAN}oci-vault://$COMPARTMENT_OCID/my-secret-name${NC}"
    echo
    echo "4. Resolve secrets in your config:"
    echo "   ${CYAN}oci-vault-resolve < your-config.yaml${NC}"
    echo
    echo "5. Use with Docker MCP Gateway (if installed):"
    echo "   ${CYAN}mcp-with-vault --start${NC}"
    echo

    step "Documentation:"
    echo "  • README: $PROJECT_ROOT/README.md"
    echo "  • API Reference: $PROJECT_ROOT/API_REFERENCE.md"
    echo "  • Quick Start: $PROJECT_ROOT/QUICKSTART.md"
    echo

    step "Troubleshooting:"
    echo "  • View logs: ${CYAN}oci-vault-resolve --verbose < config.yaml${NC}"
    echo "  • Clear cache: ${CYAN}rm -rf $CACHE_DIR/*${NC}"
    echo "  • Test OCI auth: ${CYAN}oci iam region list${NC}"
    echo

    success "Happy secret managing!"
}

# ============================================================================
# Main Installation Flow
# ============================================================================

main() {
    banner "OCI Vault MCP Resolver - Installation"

    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --dry-run)
                DRY_RUN=true
                warn "DRY RUN MODE: No changes will be made"
                shift
                ;;
            --skip-secrets)
                SKIP_SECRETS=true
                shift
                ;;
            --no-wrappers)
                INSTALL_WRAPPERS=false
                shift
                ;;
            --help|-h)
                cat << EOF
Usage: $0 [OPTIONS]

Interactive installation script for OCI Vault MCP Resolver.

OPTIONS:
    --dry-run         Preview installation without making changes
    --skip-secrets    Skip uploading example secrets
    --no-wrappers     Skip installing wrapper scripts to /usr/local/bin
    --help, -h        Show this help message

EXAMPLES:
    # Interactive installation
    $0

    # Dry run to preview changes
    $0 --dry-run

    # Install without wrapper scripts
    $0 --no-wrappers

EOF
                exit 0
                ;;
            *)
                error "Unknown option: $1"
                info "Run '$0 --help' for usage information"
                exit 1
                ;;
        esac
    done

    # Run installation steps
    preflight_checks
    echo

    collect_oci_config
    echo

    generate_config
    echo

    install_package
    echo

    install_wrappers
    echo

    if [[ "$SKIP_SECRETS" != true ]]; then
        upload_example_secrets
        echo
    fi

    print_next_steps

    if [[ "$DRY_RUN" == true ]]; then
        echo
        warn "DRY RUN completed - no changes were made"
        info "Run without --dry-run to perform actual installation"
    fi
}

# Run main function
main "$@"
