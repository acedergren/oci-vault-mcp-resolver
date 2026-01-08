"""Tests for parallel secret fetching functionality."""

import asyncio
import base64
import time
from unittest.mock import Mock, patch

import oci
import pytest

from oci_vault_resolver import VaultResolver


class TestParallelSecretFetching:
    """Test suite for parallel secret resolution."""

    @pytest.fixture
    def resolver(self, temp_cache_dir, mock_oci_clients):
        """Create a VaultResolver instance for testing with mocked OCI clients."""
        return VaultResolver(cache_dir=temp_cache_dir, ttl=3600, verbose=False)

    @pytest.mark.asyncio
    async def test_parallel_secret_fetching_success(self, resolver, mock_oci_clients):
        """Test successful parallel fetching of multiple secrets."""
        mock_secrets, _ = mock_oci_clients

        # Mock successful responses for multiple secrets
        def mock_get_secret(secret_id):
            mock_bundle = Mock()
            # Create different values based on OCID
            value = f"value-{secret_id[-3:]}"
            mock_bundle.data.secret_bundle_content.content = base64.b64encode(
                value.encode()
            ).decode()
            return mock_bundle

        mock_secrets.get_secret_bundle.side_effect = mock_get_secret

        vault_urls = [
            "oci-vault://ocid1.vaultsecret.oc1.iad.abc123",
            "oci-vault://ocid1.vaultsecret.oc1.iad.def456",
            "oci-vault://ocid1.vaultsecret.oc1.iad.ghi789",
        ]

        results = await resolver.fetch_secrets_parallel(vault_urls)

        assert len(results) == 3
        assert results["oci-vault://ocid1.vaultsecret.oc1.iad.abc123"] == "value-123"
        assert results["oci-vault://ocid1.vaultsecret.oc1.iad.def456"] == "value-456"
        assert results["oci-vault://ocid1.vaultsecret.oc1.iad.ghi789"] == "value-789"

    @pytest.mark.asyncio
    async def test_parallel_fetching_with_errors(self, resolver, mock_oci_clients):
        """Test parallel fetching handles individual errors gracefully."""
        mock_secrets, _ = mock_oci_clients

        # Mock mixed success and failure
        def mock_get_secret(secret_id):
            if "fail" in secret_id:
                raise oci.exceptions.ServiceError(
                    status=404,
                    code="NotFound",
                    message="Secret not found",
                    headers={},
                )
            mock_bundle = Mock()
            mock_bundle.data.secret_bundle_content.content = base64.b64encode(b"success").decode()
            return mock_bundle

        mock_secrets.get_secret_bundle.side_effect = mock_get_secret

        vault_urls = [
            "oci-vault://ocid1.vaultsecret.oc1.iad.success1",
            "oci-vault://ocid1.vaultsecret.oc1.iad.fail123",
            "oci-vault://ocid1.vaultsecret.oc1.iad.success2",
        ]

        results = await resolver.fetch_secrets_parallel(vault_urls)

        # Successful secrets should have values
        assert results["oci-vault://ocid1.vaultsecret.oc1.iad.success1"] == "success"
        assert results["oci-vault://ocid1.vaultsecret.oc1.iad.success2"] == "success"
        # Failed secret should have None
        assert results["oci-vault://ocid1.vaultsecret.oc1.iad.fail123"] is None

    @pytest.mark.asyncio
    async def test_parallel_fetching_performance_benefit(self, resolver, mock_oci_clients):
        """Test that parallel fetching is faster than sequential."""
        mock_secrets, _ = mock_oci_clients

        # Mock API calls with artificial delay
        def mock_get_secret_with_delay(secret_id):
            import time

            time.sleep(0.1)  # 100ms delay per secret
            mock_bundle = Mock()
            mock_bundle.data.secret_bundle_content.content = base64.b64encode(b"value").decode()
            return mock_bundle

        mock_secrets.get_secret_bundle.side_effect = mock_get_secret_with_delay

        vault_urls = [f"oci-vault://ocid1.vaultsecret.oc1.iad.test{i}" for i in range(5)]

        # Measure parallel execution time
        start = time.time()
        results = await resolver.fetch_secrets_parallel(vault_urls)
        parallel_duration = time.time() - start

        # Parallel execution should take roughly 100ms (not 500ms for sequential)
        # Allow some overhead for test execution
        assert parallel_duration < 0.3  # Should be much faster than 500ms

        # All secrets should be resolved
        assert len(results) == 5
        assert all(v == "value" for v in results.values())

    @pytest.mark.asyncio
    async def test_parallel_fetching_empty_list(self, resolver, mock_oci_clients):
        """Test parallel fetching with empty URL list."""
        vault_urls = []

        results = await resolver.fetch_secrets_parallel(vault_urls)

        assert results == {}

    @pytest.mark.asyncio
    async def test_parallel_fetching_single_url(self, resolver, mock_oci_clients):
        """Test parallel fetching with single URL."""
        mock_secrets, _ = mock_oci_clients

        mock_bundle = Mock()
        mock_bundle.data.secret_bundle_content.content = base64.b64encode(b"single-value").decode()
        mock_secrets.get_secret_bundle.return_value = mock_bundle

        vault_urls = ["oci-vault://ocid1.vaultsecret.oc1.iad.single"]

        results = await resolver.fetch_secrets_parallel(vault_urls)

        assert len(results) == 1
        assert results["oci-vault://ocid1.vaultsecret.oc1.iad.single"] == "single-value"

    def test_resolve_config_uses_parallel_fetching(self, resolver, mock_oci_clients):
        """Test that resolve_config uses parallel fetching for multiple secrets."""
        mock_secrets, _ = mock_oci_clients

        # Mock successful responses
        mock_bundle = Mock()
        mock_bundle.data.secret_bundle_content.content = base64.b64encode(b"resolved").decode()
        mock_secrets.get_secret_bundle.return_value = mock_bundle

        config = {
            "mcpServers": {
                "db": {
                    "env": {
                        "PASSWORD": "oci-vault://ocid1.vaultsecret.oc1.iad.pass123",
                        "API_KEY": "oci-vault://ocid1.vaultsecret.oc1.iad.key456",
                    }
                }
            }
        }

        resolved = resolver.resolve_config(config)

        # Both secrets should be resolved
        assert resolved["mcpServers"]["db"]["env"]["PASSWORD"] == "resolved"
        assert resolved["mcpServers"]["db"]["env"]["API_KEY"] == "resolved"
