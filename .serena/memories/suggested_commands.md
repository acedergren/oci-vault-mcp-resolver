# Suggested Commands

## Development Commands

### Running the Resolver

**Using wrapper script (recommended)**:
```bash
# Basic usage - resolve and apply
./mcp-with-vault

# Dry run to preview resolved config
./mcp-with-vault --dry-run

# With custom cache TTL (2 hours)
./mcp-with-vault --ttl 7200

# Verbose mode for debugging
./mcp-with-vault --verbose

# Resolve and start gateway
./mcp-with-vault --start
```

**Using Python script directly**:
```bash
# Read from stdin, write to stdout
docker mcp config read | python3 oci_vault_resolver.py

# With verbose logging
docker mcp config read | python3 oci_vault_resolver.py --verbose

# Custom cache TTL
docker mcp config read | python3 oci_vault_resolver.py --ttl 7200

# From/to files
python3 oci_vault_resolver.py -i config.yaml -o resolved-config.yaml

# Full pipeline (resolve and apply)
docker mcp config read | python3 oci_vault_resolver.py | docker mcp config write
```

### Testing

**Manual testing**:
```bash
# Run test setup script
./test-setup.sh

# Test with example config
python3 oci_vault_resolver.py -i test-mcp-config.yaml --verbose

# Test wrapper script dry run
./mcp-with-vault --dry-run

# Test with real vault secret
echo 'test: oci-vault://YOUR_SECRET_OCID' | python3 oci_vault_resolver.py
```

**Performance testing**:
```bash
# Measure resolution time
time python3 oci_vault_resolver.py -i test-config.yaml

# Test cache hit performance
for i in {1..100}; do
    echo 'test: oci-vault://SECRET_OCID' | python3 oci_vault_resolver.py > /dev/null
done
```

### Debugging

```bash
# Enable verbose mode
python3 oci_vault_resolver.py --verbose

# Check cache contents
ls -lah ~/.cache/oci-vault-mcp/
cat ~/.cache/oci-vault-mcp/*.json | jq

# Clear cache
rm -rf ~/.cache/oci-vault-mcp/

# Test OCI CLI directly
oci secrets secret-bundle get --secret-id YOUR_OCID

# Verify OCI CLI configuration
oci iam compartment list --query 'data[0:3].name'
```

### OCI Vault Management

```bash
# List compartments
oci iam compartment list --query 'data[0:5].{name:name,id:id}'

# List vaults in compartment
oci kms management vault list --compartment-id "$COMPARTMENT_ID"

# List secrets in compartment
oci vault secret list --compartment-id "$COMPARTMENT_ID" --all

# Get secret value
oci secrets secret-bundle get --secret-id "$SECRET_ID" \
  --query 'data."secret-bundle-content".content' --raw-output | base64 -d

# Create a secret
oci vault secret create-base64 \
  --compartment-id "$COMPARTMENT_ID" \
  --secret-name "my-secret" \
  --vault-id "$VAULT_ID" \
  --key-id "$KEY_ID" \
  --secret-content-content "my-secret-value"
```

### Docker MCP Commands

```bash
# Read current MCP config
docker mcp config read

# Read and save to file
docker mcp config read > config.yaml

# Write config from file
cat config.yaml | docker mcp config write

# Start MCP gateway
docker mcp gateway start

# Stop MCP gateway
docker mcp gateway stop

# Check gateway status
docker mcp gateway status
```

## Git Commands

```bash
# Create feature branch
git checkout -b feature/your-feature-name

# Stage changes
git add .

# Commit with conventional format
git commit -m "feat(resolver): add new feature"

# Push to remote
git push origin feature/your-feature-name

# Create tag for release
git tag -a v1.0.0 -m "Version 1.0.0"
git push origin v1.0.0
```

## Installation Commands

```bash
# Install Python dependencies
pip3 install --user PyYAML

# Install OCI CLI (macOS)
brew install oci-cli

# Install OCI CLI (Linux/macOS via pip)
pip3 install --user oci-cli

# Configure OCI CLI
oci setup config
```

## No Formal Linting/Formatting Tools
This project currently does not use automated linting or formatting tools like `black`, `pylint`, `flake8`, or `mypy`. Code style is enforced through manual review following PEP 8 guidelines.
