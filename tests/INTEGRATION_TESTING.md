# Integration Testing Guide

Integration tests verify OCI Vault MCP Resolver works with real Oracle Cloud Infrastructure.

## Prerequisites

1. **OCI Account** with active Vault service
2. **OCI CLI configured** (`~/.oci/config` with valid credentials)
3. **IAM Permissions**:
   - `read secret-bundles` in target compartment
   - `read secrets` in target vault
4. **Test Secret** created in OCI Vault

## Setup

### 1. Create Test Secret

```bash
# Using OCI CLI
oci vault secret create-base64 \
  --compartment-id ocid1.compartment.oc1..xxx \
  --secret-name "oci-vault-resolver-test" \
  --vault-id ocid1.vault.oc1.iad.xxx \
  --key-id ocid1.key.oc1.iad.xxx \
  --secret-content-content "dGVzdC1zZWNyZXQtdmFsdWU="
```

### 2. Set Environment Variables

```bash
# Required for integration tests
export OCI_TEST_SECRET_OCID="ocid1.vaultsecret.oc1.iad.xxx"
export OCI_TEST_SECRET_VALUE="test-secret-value"
export OCI_TEST_COMPARTMENT_ID="ocid1.compartment.oc1..xxx"

# Optional
export OCI_TEST_SECRET_NAME="oci-vault-resolver-test"
export OCI_TEST_RESTRICTED_SECRET_OCID="ocid1.vaultsecret.oc1.iad.restricted"  # For permission tests
export OCI_USE_INSTANCE_PRINCIPALS="true"  # If running on OCI VM
```

### 3. Verify OCI Config

```bash
# Test OCI CLI authentication
oci iam region list

# Verify vault access
oci vault secret get \
  --secret-id $OCI_TEST_SECRET_OCID
```

## Running Integration Tests

### Run All Integration Tests

```bash
# Run all integration tests (requires env vars)
pytest -m integration -v

# Run with verbose output
pytest -m integration -vv
```

### Run Specific Test Classes

```bash
# Test real OCI integration only
pytest tests/test_integration.py::TestRealOCIIntegration -v

# Test instance principal auth
pytest tests/test_integration.py::TestInstancePrincipalAuth -v

# Test error handling
pytest tests/test_integration.py::TestErrorHandling -v
```

### Run Specific Tests

```bash
# Test fetching by OCID
pytest tests/test_integration.py::TestRealOCIIntegration::test_fetch_real_secret_by_ocid -v

# Test caching behavior
pytest tests/test_integration.py::TestRealOCIIntegration::test_resolve_secret_with_caching -v

# Test config resolution
pytest tests/test_integration.py::TestRealOCIIntegration::test_resolve_config_with_real_secrets -v
```

## Test Coverage

Integration tests verify:

### ✅ Core Functionality
- Fetching secrets by OCID
- Resolving secrets by name + compartment
- Full config resolution with multiple secrets
- Cache hit/miss behavior

### ✅ Authentication Methods
- Config file authentication (`~/.oci/config`)
- Instance principal authentication (OCI VMs)

### ✅ Error Handling
- `SecretNotFoundError` for nonexistent secrets
- `PermissionDeniedError` for restricted secrets
- `AuthenticationError` for invalid credentials

### ✅ Performance Metrics
- Fetch timing
- Cache statistics
- Performance logging

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Integration Tests

on:
  schedule:
    - cron: '0 2 * * *'  # Daily at 2 AM
  workflow_dispatch:

jobs:
  integration:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'

      - name: Install dependencies
        run: |
          pip install -e ".[dev]"

      - name: Configure OCI
        env:
          OCI_CONFIG: ${{ secrets.OCI_CONFIG }}
          OCI_KEY: ${{ secrets.OCI_PRIVATE_KEY }}
        run: |
          mkdir -p ~/.oci
          echo "$OCI_CONFIG" > ~/.oci/config
          echo "$OCI_KEY" > ~/.oci/key.pem
          chmod 600 ~/.oci/key.pem

      - name: Run integration tests
        env:
          OCI_TEST_SECRET_OCID: ${{ secrets.OCI_TEST_SECRET_OCID }}
          OCI_TEST_SECRET_VALUE: ${{ secrets.OCI_TEST_SECRET_VALUE }}
          OCI_TEST_COMPARTMENT_ID: ${{ secrets.OCI_TEST_COMPARTMENT_ID }}
        run: |
          pytest -m integration --cov=oci_vault_resolver --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

## Troubleshooting

### Authentication Errors

```bash
# Verify OCI config file exists and is valid
cat ~/.oci/config

# Check key file permissions
ls -la ~/.oci/key.pem  # Should be 600

# Test with OCI CLI
oci iam region list
```

### Permission Errors

```bash
# Verify IAM permissions
oci iam policy list --compartment-id <root-compartment-id>

# Check if you can access the vault
oci vault vault get --vault-id <vault-id>

# Check if you can list secrets
oci vault secret list --compartment-id <compartment-id>
```

### Secret Not Found

```bash
# Verify secret exists
oci vault secret get --secret-id $OCI_TEST_SECRET_OCID

# Check secret lifecycle state (must be ACTIVE)
oci vault secret get --secret-id $OCI_TEST_SECRET_OCID \
  --query 'data."lifecycle-state"'
```

### Network Issues

```bash
# Test OCI API connectivity
curl -I https://vault.us-ashburn-1.oci.oraclecloud.com

# Check DNS resolution
nslookup vault.us-ashburn-1.oci.oraclecloud.com

# Verify proxy settings if behind corporate firewall
echo $HTTP_PROXY
echo $HTTPS_PROXY
```

## Cost Considerations

Integration tests make real API calls to OCI Vault:

- **Secret Access**: Free (no per-request cost)
- **Secret Storage**: ~$0.20/month per secret
- **Network Egress**: Free within same region

**Recommendation**: Use a dedicated test compartment and clean up test secrets regularly.

## Best Practices

1. **Isolation**: Use dedicated test compartment
2. **Cleanup**: Delete test secrets after runs
3. **Rotation**: Rotate test secret values periodically
4. **Monitoring**: Track API usage in OCI Console
5. **Rate Limits**: Be aware of OCI API rate limits
6. **Caching**: Verify cache behavior with TTL tests

## Example Test Session

```bash
# Complete test session
export OCI_TEST_SECRET_OCID="ocid1.vaultsecret.oc1.iad.xxx"
export OCI_TEST_SECRET_VALUE="test-value-123"
export OCI_TEST_COMPARTMENT_ID="ocid1.compartment.oc1..xxx"

# Run all integration tests
pytest -m integration -v

# Output:
# tests/test_integration.py::TestRealOCIIntegration::test_fetch_real_secret_by_ocid PASSED
# tests/test_integration.py::TestRealOCIIntegration::test_fetch_nonexistent_secret PASSED
# tests/test_integration.py::TestRealOCIIntegration::test_resolve_secret_with_caching PASSED
# tests/test_integration.py::TestRealOCIIntegration::test_find_secret_by_name PASSED
# tests/test_integration.py::TestRealOCIIntegration::test_resolve_config_with_real_secrets PASSED
# tests/test_integration.py::TestRealOCIIntegration::test_performance_metrics PASSED
```
