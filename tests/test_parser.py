"""Tests for vault URL parsing functionality."""

from unittest.mock import patch

import pytest

from oci_vault_resolver import VaultResolver


class TestVaultURLParsing:
    """Test suite for parse_vault_url() method."""

    @pytest.fixture
    def resolver(self, temp_cache_dir, mock_oci_clients):
        """Create a VaultResolver instance for testing with mocked OCI clients."""
        # VaultResolver will use the mocked clients from conftest.py
        return VaultResolver(cache_dir=temp_cache_dir, verbose=False)

    def test_parse_secret_ocid(self, resolver):
        """Test parsing oci-vault://ocid1.vaultsecret.oc1..."""
        url = "oci-vault://ocid1.vaultsecret.oc1.iad.amaaaaaa123456"

        secret_ocid, compartment_id, secret_name, version_number = resolver.parse_vault_url(url)

        assert secret_ocid == "ocid1.vaultsecret.oc1.iad.amaaaaaa123456"
        assert compartment_id is None
        assert secret_name is None
        assert version_number is None

    def test_parse_compartment_and_name(self, resolver):
        """Test parsing oci-vault://compartment-id/secret-name."""
        url = "oci-vault://ocid1.compartment.oc1..aaabbb/test-secret"

        secret_ocid, compartment_id, secret_name, version_number = resolver.parse_vault_url(url)

        assert secret_ocid is None
        assert compartment_id == "ocid1.compartment.oc1..aaabbb"
        assert secret_name == "test-secret"
        assert version_number is None

    def test_parse_vault_and_name(self, resolver):
        """Test parsing oci-vault://vault-id/secret-name."""
        url = "oci-vault://ocid1.vault.oc1.iad.xyz123/api-key"

        secret_ocid, compartment_id, secret_name, version_number = resolver.parse_vault_url(url)

        assert secret_ocid is None
        assert compartment_id == "ocid1.vault.oc1.iad.xyz123"
        assert secret_name == "api-key"
        assert version_number is None

    def test_parse_simple_name_only(self, resolver):
        """Test parsing oci-vault://secret-name (no compartment/vault)."""
        url = "oci-vault://my-simple-secret"

        secret_ocid, compartment_id, secret_name, version_number = resolver.parse_vault_url(url)

        assert secret_ocid is None
        assert compartment_id is None
        assert secret_name == "my-simple-secret"
        assert version_number is None

    @pytest.mark.parametrize(
        "invalid_url",
        [
            "not-a-vault-url",
            "http://example.com/secret",
            "oci-vault://",
            "",
            "oci-vault",
            "vault://secret",
        ],
    )
    def test_invalid_url_formats(self, resolver, invalid_url):
        """Test that invalid URL formats return (None, None, None, None)."""
        result = resolver.parse_vault_url(invalid_url)

        assert result == (
            None,
            None,
            None,
            None,
        ), f"Invalid URL '{invalid_url}' should return (None, None, None, None)"

    def test_parse_url_with_slashes_in_name(self, resolver):
        """Test parsing URLs with multiple slashes - documents current limitation."""
        url = "oci-vault://ocid1.compartment.oc1..abc/path/to/secret"

        secret_ocid, compartment_id, secret_name, version_number = resolver.parse_vault_url(url)

        # Current implementation limitation: only handles 2-part paths
        # Paths with 3+ parts from split('/') return (None, None, None, None)
        assert secret_ocid is None
        assert compartment_id is None
        assert secret_name is None
        assert version_number is None

    def test_parse_url_case_sensitivity(self, resolver):
        """Test that OCID detection is case-sensitive - only recognizes lowercase."""
        url_lower = "oci-vault://ocid1.vaultsecret.oc1.iad.aaa"
        url_upper = "oci-vault://OCID1.VAULTSECRET.OC1.IAD.AAA"

        result_lower = resolver.parse_vault_url(url_lower)
        result_upper = resolver.parse_vault_url(url_upper)

        # Lowercase OCID recognized correctly as secret OCID
        assert result_lower[0] == "ocid1.vaultsecret.oc1.iad.aaa"
        assert result_lower[1] is None
        assert result_lower[2] is None
        assert result_lower[3] is None

        # Uppercase OCID not recognized - treated as secret name
        # (startswith check is case-sensitive)
        assert result_upper[0] is None
        assert result_upper[1] is None
        assert result_upper[2] == "OCID1.VAULTSECRET.OC1.IAD.AAA"
        assert result_upper[3] is None

    def test_parse_url_with_special_characters_in_name(self, resolver):
        """Test parsing URLs with special characters in secret names."""
        test_cases = [
            ("oci-vault://my-secret-123", "my-secret-123"),
            ("oci-vault://my_secret_456", "my_secret_456"),
            ("oci-vault://secret.name", "secret.name"),
            ("oci-vault://SECRET-NAME", "SECRET-NAME"),
        ]

        for url, expected_name in test_cases:
            _, _, secret_name, version_number = resolver.parse_vault_url(url)
            assert secret_name == expected_name, f"Secret name parsing failed for {url}"
            assert version_number is None

    def test_parse_real_world_ocid_formats(self, resolver):
        """Test parsing with realistic OCID formats from OCI."""
        real_world_urls = [
            "oci-vault://ocid1.vaultsecret.oc1.iad.amaaaaaabcdefgh12345678",
            "oci-vault://ocid1.compartment.oc1..aaaaaaaabcdefgh/db-password",
            "oci-vault://ocid1.vault.oc1.phx.bcdefgh.abcdefgh12345678/api-key",
        ]

        for url in real_world_urls:
            result = resolver.parse_vault_url(url)
            # All should parse without errors
            assert result is not None
            # At least one component should be non-None
            assert any(
                component is not None for component in result
            ), f"Failed to parse real-world URL: {url}"

    def test_parse_url_whitespace_handling(self, resolver):
        """Test that URLs with whitespace are handled correctly."""
        # URLs with leading/trailing whitespace should fail
        # (VaultResolver doesn't strip whitespace)
        url_with_spaces = " oci-vault://test-secret "

        result = resolver.parse_vault_url(url_with_spaces)

        # Current implementation: regex won't match with leading space
        assert result == (None, None, None, None)

    def test_parse_empty_components(self, resolver):
        """Test parsing URLs with empty components."""
        test_cases = [
            "oci-vault:///",
            "oci-vault:////",
            "oci-vault:///secret-name",
        ]

        for url in test_cases:
            result = resolver.parse_vault_url(url)
            # These should all parse as (None, None, None, None) or handle gracefully
            # Document current behavior
            assert isinstance(result, tuple)
            assert len(result) == 4

    def test_parse_url_with_version_parameter(self, resolver):
        """Test parsing oci-vault://secret-ocid?version=2."""
        url = "oci-vault://ocid1.vaultsecret.oc1.iad.amaaaaaa123456?version=2"

        secret_ocid, compartment_id, secret_name, version_number = resolver.parse_vault_url(url)

        assert secret_ocid == "ocid1.vaultsecret.oc1.iad.amaaaaaa123456"
        assert compartment_id is None
        assert secret_name is None
        assert version_number == 2

    def test_parse_url_with_version_compartment_name(self, resolver):
        """Test parsing oci-vault://compartment-id/secret-name?version=3."""
        url = "oci-vault://ocid1.compartment.oc1..aaabbb/test-secret?version=3"

        secret_ocid, compartment_id, secret_name, version_number = resolver.parse_vault_url(url)

        assert secret_ocid is None
        assert compartment_id == "ocid1.compartment.oc1..aaabbb"
        assert secret_name == "test-secret"
        assert version_number == 3

    def test_parse_url_with_invalid_version(self, resolver):
        """Test parsing oci-vault://secret?version=invalid."""
        url = "oci-vault://ocid1.vaultsecret.oc1.iad.test?version=notanumber"

        secret_ocid, compartment_id, secret_name, version_number = resolver.parse_vault_url(url)

        # Invalid version should be None (logged as warning)
        assert secret_ocid == "ocid1.vaultsecret.oc1.iad.test"
        assert version_number is None

    def test_parse_url_with_multiple_query_params(self, resolver):
        """Test parsing oci-vault://secret?version=1&other=value."""
        url = "oci-vault://ocid1.vaultsecret.oc1.iad.test?version=1&other=value"

        secret_ocid, compartment_id, secret_name, version_number = resolver.parse_vault_url(url)

        # Should extract version number, ignore other params
        assert secret_ocid == "ocid1.vaultsecret.oc1.iad.test"
        assert version_number == 1
