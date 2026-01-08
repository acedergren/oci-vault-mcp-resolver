"""Integration tests requiring real OCI credentials.

These tests are skipped by default. Run with: pytest -m integration

Prerequisites:
  - Valid OCI config in ~/.oci/config
  - Active OCI Vault with test secrets
  - Proper IAM permissions

Setup:
  1. Create a test secret in OCI Vault
  2. Note the secret OCID
  3. Set environment variables:
     - OCI_TEST_SECRET_OCID: OCID of test secret
     - OCI_TEST_SECRET_VALUE: Expected value of test secret
     - OCI_TEST_COMPARTMENT_ID: OCID of test compartment
"""

import os
from pathlib import Path

import pytest

from oci_vault_resolver import (AuthenticationError, PermissionDeniedError,
                                SecretNotFoundError, VaultResolver)

# Skip all tests in this module by default
pytestmark = pytest.mark.integration


class TestRealOCIIntegration:
    """Integration tests with real OCI Vault."""

    @pytest.fixture
    def real_resolver(self, temp_cache_dir: Path):
        """Create resolver with real OCI credentials."""
        # This will use actual OCI config from ~/.oci/config
        return VaultResolver(cache_dir=temp_cache_dir, verbose=True)

    @pytest.fixture
    def test_secret_ocid(self) -> str:
        """Get test secret OCID from environment."""
        secret_ocid = os.getenv("OCI_TEST_SECRET_OCID")
        if not secret_ocid:
            pytest.skip("OCI_TEST_SECRET_OCID not set")
        return secret_ocid

    @pytest.fixture
    def test_secret_value(self) -> str:
        """Get expected secret value from environment."""
        secret_value = os.getenv("OCI_TEST_SECRET_VALUE")
        if not secret_value:
            pytest.skip("OCI_TEST_SECRET_VALUE not set")
        return secret_value

    @pytest.fixture
    def test_compartment_id(self) -> str:
        """Get test compartment OCID from environment."""
        compartment_id = os.getenv("OCI_TEST_COMPARTMENT_ID")
        if not compartment_id:
            pytest.skip("OCI_TEST_COMPARTMENT_ID not set")
        return compartment_id

    def test_fetch_real_secret_by_ocid(self, real_resolver, test_secret_ocid, test_secret_value):
        """Test fetching a real secret by OCID."""
        # Fetch secret
        result = real_resolver.fetch_secret_by_ocid(test_secret_ocid)

        # Verify
        assert result is not None
        assert result == test_secret_value

    def test_fetch_nonexistent_secret(self, real_resolver):
        """Test fetching a nonexistent secret raises SecretNotFoundError."""
        fake_ocid = "ocid1.vaultsecret.oc1.iad.nonexistent123456"

        with pytest.raises(SecretNotFoundError):
            real_resolver.fetch_secret_by_ocid(fake_ocid)

    def test_resolve_secret_with_caching(self, real_resolver, test_secret_ocid, test_secret_value):
        """Test secret resolution with caching."""
        vault_url = f"oci-vault://{test_secret_ocid}"

        # First fetch - should hit OCI
        result1 = real_resolver.resolve_secret(vault_url)
        assert result1 == test_secret_value
        assert real_resolver.metrics["secrets_fetched"] == 1
        assert real_resolver.metrics["cache_misses"] == 1

        # Second fetch - should hit cache
        result2 = real_resolver.resolve_secret(vault_url)
        assert result2 == test_secret_value
        assert real_resolver.metrics["secrets_fetched"] == 1  # No new fetch
        assert real_resolver.metrics["cache_hits"] == 1

    def test_find_secret_by_name(self, real_resolver, test_compartment_id):
        """Test finding a secret by name in a compartment."""
        # This test assumes there's at least one secret in the compartment
        # You may need to adjust the secret name based on your setup
        secret_name = os.getenv("OCI_TEST_SECRET_NAME", "test-secret")

        secret_ocid = real_resolver.find_secret_by_name(test_compartment_id, secret_name)

        # If secret exists, should return OCID
        if secret_ocid:
            assert secret_ocid.startswith("ocid1.vaultsecret.")
        else:
            # Secret not found is a valid outcome for this test
            pytest.skip(f"Secret '{secret_name}' not found in test compartment")

    def test_resolve_config_with_real_secrets(self, real_resolver, test_secret_ocid):
        """Test resolving a full config with real secrets."""
        config = {
            "servers": {
                "database": {
                    "env": {
                        "DB_PASSWORD": f"oci-vault://{test_secret_ocid}",
                        "DB_HOST": "localhost",  # Not a vault reference
                    }
                }
            }
        }

        resolved_config = real_resolver.resolve_config(config)

        # Verify resolution
        assert "servers" in resolved_config
        assert "database" in resolved_config["servers"]
        assert "env" in resolved_config["servers"]["database"]
        db_password = resolved_config["servers"]["database"]["env"]["DB_PASSWORD"]

        # Password should be resolved (not a vault URL anymore)
        assert not db_password.startswith("oci-vault://")
        assert db_password == os.getenv("OCI_TEST_SECRET_VALUE")

    def test_performance_metrics(self, real_resolver, test_secret_ocid, test_secret_value):
        """Test that performance metrics are tracked correctly."""
        vault_url = f"oci-vault://{test_secret_ocid}"

        # Clear cache to ensure fresh fetch
        real_resolver.metrics = {
            "secrets_fetched": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "stale_cache_used": 0,
            "total_fetch_time": 0.0,
        }

        # Fetch secret
        result = real_resolver.resolve_secret(vault_url)
        assert result == test_secret_value

        # Verify metrics
        assert real_resolver.metrics["secrets_fetched"] == 1
        assert real_resolver.metrics["cache_misses"] == 1
        assert real_resolver.metrics["total_fetch_time"] > 0


class TestInstancePrincipalAuth:
    """Test instance principal authentication (OCI VM only)."""

    @pytest.mark.skipif(
        not os.getenv("OCI_USE_INSTANCE_PRINCIPALS"),
        reason="Requires OCI instance principal environment",
    )
    def test_instance_principal_init(self, temp_cache_dir):
        """Test initialization with instance principals."""
        # This test only runs on OCI VMs with instance principals configured
        resolver = VaultResolver(
            cache_dir=temp_cache_dir, use_instance_principals=True, verbose=True
        )

        # Should initialize without errors
        assert resolver.secrets_client is not None
        assert resolver.vaults_client is not None

    @pytest.mark.skipif(
        os.getenv("OCI_USE_INSTANCE_PRINCIPALS"),
        reason="Test for non-instance-principal environments",
    )
    def test_config_file_auth(self, temp_cache_dir):
        """Test initialization with config file authentication."""
        resolver = VaultResolver(cache_dir=temp_cache_dir, verbose=True)

        # Should initialize without errors
        assert resolver.secrets_client is not None
        assert resolver.vaults_client is not None


class TestErrorHandling:
    """Test error handling with real OCI API."""

    @pytest.fixture
    def real_resolver(self, temp_cache_dir: Path):
        """Create resolver with real OCI credentials."""
        return VaultResolver(cache_dir=temp_cache_dir, verbose=True)

    def test_permission_denied_error(self, real_resolver):
        """Test handling of permission denied errors."""
        # Use a secret OCID that exists but user has no permission to access
        # This test might need adjustment based on your IAM setup
        restricted_ocid = os.getenv("OCI_TEST_RESTRICTED_SECRET_OCID")
        if not restricted_ocid:
            pytest.skip("OCI_TEST_RESTRICTED_SECRET_OCID not set")

        with pytest.raises(PermissionDeniedError):
            real_resolver.fetch_secret_by_ocid(restricted_ocid)

    def test_invalid_oci_config(self, temp_cache_dir):
        """Test handling of invalid OCI config."""
        with pytest.raises(AuthenticationError):
            VaultResolver(
                cache_dir=temp_cache_dir,
                config_file="/nonexistent/config",
                verbose=True,
            )
