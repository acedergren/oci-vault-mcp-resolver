"""Tests for secret resolution functionality."""

import base64
from unittest.mock import Mock, patch

import oci
import pytest

from oci_vault_resolver import VaultResolver


class TestSecretResolution:
    """Test suite for resolve_secret() and related methods."""

    @pytest.fixture
    def resolver(self, temp_cache_dir, mock_oci_clients):
        """Create a VaultResolver instance for testing with mocked OCI clients."""
        return VaultResolver(cache_dir=temp_cache_dir, ttl=3600, verbose=False)

    def test_resolve_secret_by_ocid_success(self, resolver, mock_oci_clients):
        """Test successful secret resolution using OCID."""
        mock_secrets, _ = mock_oci_clients
        vault_url = "oci-vault://ocid1.vaultsecret.oc1.iad.test123"

        # Mock successful API response
        mock_bundle = Mock()
        mock_bundle.data.secret_bundle_content.content = base64.b64encode(b"secret-value").decode()
        mock_secrets.get_secret_bundle.return_value = mock_bundle

        result = resolver.resolve_secret(vault_url)

        assert result == "secret-value"
        mock_secrets.get_secret_bundle.assert_called_once()

    def test_resolve_secret_by_name_success(self, resolver, mock_oci_clients):
        """Test successful secret resolution using compartment and name."""
        mock_secrets, mock_vaults = mock_oci_clients
        vault_url = "oci-vault://ocid1.compartment.oc1..abc123/test-secret"

        # Mock list_secrets response
        mock_secret = Mock()
        mock_secret.id = "ocid1.vaultsecret.oc1.iad.found123"
        mock_secret.secret_name = "test-secret"
        mock_vaults.list_secrets.return_value.data = [mock_secret]

        # Mock get_secret_bundle response
        mock_bundle = Mock()
        mock_bundle.data.secret_bundle_content.content = base64.b64encode(
            b"resolved-value"
        ).decode()
        mock_secrets.get_secret_bundle.return_value = mock_bundle

        result = resolver.resolve_secret(vault_url)

        assert result == "resolved-value"
        mock_vaults.list_secrets.assert_called_once()
        mock_secrets.get_secret_bundle.assert_called_once()

    def test_resolve_secret_404_not_found(self, resolver, mock_oci_clients):
        """Test handling of 404 error (secret not found)."""
        mock_secrets, _ = mock_oci_clients
        vault_url = "oci-vault://ocid1.vaultsecret.oc1.iad.nonexistent"

        # Mock 404 error
        error = oci.exceptions.ServiceError(
            status=404,
            code="NotAuthorizedOrNotFound",
            message="Secret not found",
            headers={},
        )
        mock_secrets.get_secret_bundle.side_effect = error

        result = resolver.resolve_secret(vault_url)

        assert result is None

    def test_resolve_secret_401_authentication_failed(self, resolver, mock_oci_clients):
        """Test handling of 401 error (authentication failed)."""
        mock_secrets, _ = mock_oci_clients
        vault_url = "oci-vault://ocid1.vaultsecret.oc1.iad.test123"

        # Mock 401 error
        error = oci.exceptions.ServiceError(
            status=401,
            code="NotAuthenticated",
            message="Authentication failed",
            headers={},
        )
        mock_secrets.get_secret_bundle.side_effect = error

        result = resolver.resolve_secret(vault_url)

        assert result is None

    def test_resolve_secret_403_permission_denied(self, resolver, mock_oci_clients):
        """Test handling of 403 error (permission denied)."""
        mock_secrets, _ = mock_oci_clients
        vault_url = "oci-vault://ocid1.vaultsecret.oc1.iad.test123"

        # Mock 403 error
        error = oci.exceptions.ServiceError(
            status=403,
            code="NotAuthorized",
            message="Permission denied",
            headers={},
        )
        mock_secrets.get_secret_bundle.side_effect = error

        result = resolver.resolve_secret(vault_url)

        assert result is None

    def test_resolve_secret_with_cache_integration(self, resolver, mock_oci_clients):
        """Test that resolved secrets are cached and reused."""
        mock_secrets, _ = mock_oci_clients
        vault_url = "oci-vault://ocid1.vaultsecret.oc1.iad.cached"

        # Mock successful API response
        mock_bundle = Mock()
        mock_bundle.data.secret_bundle_content.content = base64.b64encode(b"cached-value").decode()
        mock_secrets.get_secret_bundle.return_value = mock_bundle

        # First call should fetch from OCI
        result1 = resolver.resolve_secret(vault_url)
        assert result1 == "cached-value"

        # Reset mock
        mock_secrets.get_secret_bundle.reset_mock()

        # Second call should use cache (no API call)
        result2 = resolver.resolve_secret(vault_url)
        assert result2 == "cached-value"
        mock_secrets.get_secret_bundle.assert_not_called()

    def test_resolve_secret_null_value_handling(self, resolver, mock_oci_clients):
        """Test handling of secrets with null/empty values."""
        mock_secrets, _ = mock_oci_clients
        vault_url = "oci-vault://ocid1.vaultsecret.oc1.iad.empty"

        # Mock response with empty content
        mock_bundle = Mock()
        mock_bundle.data.secret_bundle_content.content = base64.b64encode(b"").decode()
        mock_secrets.get_secret_bundle.return_value = mock_bundle

        result = resolver.resolve_secret(vault_url)

        # Empty string is not cached and returns None
        # (implementation doesn't cache empty values per get_cached_secret logic)
        assert result is None

    def test_resolve_secret_invalid_url_format(self, resolver, mock_oci_clients):
        """Test that invalid URL formats are handled gracefully."""
        invalid_urls = [
            "not-a-vault-url",
            "http://example.com/secret",
            "oci-vault://",
            "",
        ]

        for invalid_url in invalid_urls:
            result = resolver.resolve_secret(invalid_url)
            assert result is None

    def test_resolve_secret_name_without_compartment(self, resolver, mock_oci_clients):
        """Test error handling for secret name without compartment."""
        vault_url = "oci-vault://simple-secret-name"

        result = resolver.resolve_secret(vault_url)

        # Should fail because no compartment specified
        assert result is None

    def test_resolve_secret_stale_cache_fallback_on_error(
        self, resolver, mock_oci_clients, temp_cache_dir
    ):
        """Test fallback to stale cache when OCI API fails."""
        mock_secrets, _ = mock_oci_clients
        vault_url = "oci-vault://ocid1.vaultsecret.oc1.iad.stale"

        # First, populate cache with a stale entry
        import time

        cache_path = resolver.get_cache_path(vault_url)
        import json

        cache_data = {
            "value": "stale-cached-value",
            "cached_at": time.time() - 7200,  # 2 hours old (stale)
            "cache_key": vault_url,
        }
        with open(cache_path, "w") as f:
            json.dump(cache_data, f)

        # Now mock API failure
        error = oci.exceptions.ServiceError(
            status=500,
            code="InternalError",
            message="Service unavailable",
            headers={},
        )
        mock_secrets.get_secret_bundle.side_effect = error

        # Should fallback to stale cache
        result = resolver.resolve_secret(vault_url)

        assert result == "stale-cached-value"

    def test_resolve_secret_by_vault_ocid(self, resolver, mock_oci_clients):
        """Test secret resolution using vault OCID and secret name."""
        mock_secrets, mock_vaults = mock_oci_clients
        vault_url = "oci-vault://ocid1.vault.oc1.iad.xyz123/api-key"

        # Mock list_secrets response (vault OCID treated as compartment)
        mock_secret = Mock()
        mock_secret.id = "ocid1.vaultsecret.oc1.iad.found456"
        mock_secret.secret_name = "api-key"
        mock_vaults.list_secrets.return_value.data = [mock_secret]

        # Mock get_secret_bundle response
        mock_bundle = Mock()
        mock_bundle.data.secret_bundle_content.content = base64.b64encode(b"vault-secret").decode()
        mock_secrets.get_secret_bundle.return_value = mock_bundle

        result = resolver.resolve_secret(vault_url)

        assert result == "vault-secret"

    def test_resolve_secret_name_not_found_in_compartment(self, resolver, mock_oci_clients):
        """Test handling when secret name doesn't exist in compartment."""
        mock_secrets, mock_vaults = mock_oci_clients
        vault_url = "oci-vault://ocid1.compartment.oc1..abc123/nonexistent-secret"

        # Mock empty list_secrets response
        mock_vaults.list_secrets.return_value.data = []

        result = resolver.resolve_secret(vault_url)

        assert result is None

    def test_resolve_secret_list_secrets_api_error(self, resolver, mock_oci_clients):
        """Test handling of API errors during list_secrets."""
        mock_secrets, mock_vaults = mock_oci_clients
        vault_url = "oci-vault://ocid1.compartment.oc1..abc123/test-secret"

        # Mock API error
        error = oci.exceptions.ServiceError(
            status=500,
            code="InternalError",
            message="Service error",
            headers={},
        )
        mock_vaults.list_secrets.side_effect = error

        result = resolver.resolve_secret(vault_url)

        assert result is None

    def test_fetch_secret_by_ocid_with_special_characters(self, resolver, mock_oci_clients):
        """Test fetching secrets with special characters in content."""
        mock_secrets, _ = mock_oci_clients
        vault_url = "oci-vault://ocid1.vaultsecret.oc1.iad.special"

        # Secret value with special characters
        special_value = "password!@#$%^&*()_+-={}[]|\\:;\"'<>,.?/"
        mock_bundle = Mock()
        mock_bundle.data.secret_bundle_content.content = base64.b64encode(
            special_value.encode()
        ).decode()
        mock_secrets.get_secret_bundle.return_value = mock_bundle

        result = resolver.resolve_secret(vault_url)

        assert result == special_value
