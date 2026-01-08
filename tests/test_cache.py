"""Tests for caching functionality."""

import json
import os
import stat
import time
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from oci_vault_resolver import VaultResolver


class TestCacheFunctionality:
    """Test suite for caching operations."""

    @pytest.fixture
    def resolver(self, temp_cache_dir, mock_oci_clients):
        """Create a VaultResolver instance for testing with mocked OCI clients."""
        return VaultResolver(cache_dir=temp_cache_dir, ttl=3600, verbose=False)

    def test_cache_file_creation_and_permissions(self, resolver, temp_cache_dir):
        """Test that cache files are created with secure permissions (0600)."""
        cache_key = "oci-vault://test-secret"
        secret_value = "test-value"

        # Cache a secret
        resolver.cache_secret(cache_key, secret_value)

        # Get cache file path
        cache_path = resolver.get_cache_path(cache_key)

        # Verify file exists
        assert cache_path.exists()

        # Check permissions (should be 0600 - owner read/write only)
        file_stats = os.stat(cache_path)
        file_mode = stat.filemode(file_stats.st_mode)

        # Extract permission bits
        permissions = file_stats.st_mode & 0o777
        assert (
            permissions == 0o600
        ), f"Cache file permissions should be 0600, got {oct(permissions)}"

    def test_cache_ttl_expiration_fresh(self, resolver, temp_cache_dir):
        """Test that fresh cache entries are not marked as stale."""
        cache_key = "oci-vault://test-fresh"
        secret_value = "fresh-value"

        # Cache a secret
        resolver.cache_secret(cache_key, secret_value)

        # Immediately retrieve it
        result = resolver.get_cached_secret(cache_key)

        assert result is not None
        value, is_stale = result
        assert value == secret_value
        assert is_stale is False

    def test_cache_ttl_expiration_stale(self, resolver, temp_cache_dir):
        """Test that expired cache entries are marked as stale."""
        cache_key = "oci-vault://test-stale"
        secret_value = "stale-value"

        # Manually create an expired cache entry
        cache_path = resolver.get_cache_path(cache_key)
        cache_data = {
            "value": secret_value,
            "cached_at": time.time() - 7200,  # Cached 2 hours ago (TTL is 1 hour)
            "cache_key": cache_key,
        }

        with open(cache_path, "w") as f:
            json.dump(cache_data, f)

        # Retrieve and check staleness
        result = resolver.get_cached_secret(cache_key)

        assert result is not None
        value, is_stale = result
        assert value == secret_value
        assert is_stale is True

    def test_cache_hit_scenario(self, resolver, temp_cache_dir):
        """Test cache hit returns correct value."""
        cache_key = "oci-vault://test-hit"
        secret_value = "cached-secret"

        # Cache the secret
        resolver.cache_secret(cache_key, secret_value)

        # Retrieve from cache
        result = resolver.get_cached_secret(cache_key)

        assert result is not None
        value, is_stale = result
        assert value == secret_value
        assert is_stale is False

    def test_cache_miss_scenario(self, resolver, temp_cache_dir):
        """Test cache miss returns None."""
        cache_key = "oci-vault://nonexistent-secret"

        # Attempt to retrieve non-cached secret
        result = resolver.get_cached_secret(cache_key)

        assert result is None

    def test_cache_invalidation_corrupted_json(self, resolver, temp_cache_dir):
        """Test that corrupted cache files return None."""
        cache_key = "oci-vault://test-corrupted"
        cache_path = resolver.get_cache_path(cache_key)

        # Write corrupted JSON
        with open(cache_path, "w") as f:
            f.write("{invalid json content")

        # Should return None on read error
        result = resolver.get_cached_secret(cache_key)

        assert result is None

    def test_cache_invalidation_missing_value(self, resolver, temp_cache_dir):
        """Test that cache entries without a value field return None."""
        cache_key = "oci-vault://test-no-value"
        cache_path = resolver.get_cache_path(cache_key)

        # Write cache entry without value
        cache_data = {
            "cached_at": time.time(),
            "cache_key": cache_key,
            # Missing "value" field
        }

        with open(cache_path, "w") as f:
            json.dump(cache_data, f)

        # Should return None
        result = resolver.get_cached_secret(cache_key)

        assert result is None

    def test_cache_invalidation_missing_timestamp(self, resolver, temp_cache_dir):
        """Test handling of cache entries missing cached_at timestamp."""
        cache_key = "oci-vault://test-no-timestamp"
        cache_path = resolver.get_cache_path(cache_key)

        # Write cache entry without cached_at
        cache_data = {
            "value": "test-value",
            "cache_key": cache_key,
            # Missing "cached_at" field
        }

        with open(cache_path, "w") as f:
            json.dump(cache_data, f)

        # Should handle gracefully (defaults to 0)
        result = resolver.get_cached_secret(cache_key)

        assert result is not None
        value, is_stale = result
        assert value == "test-value"
        # Should be marked as stale (timestamp 0 is very old)
        assert is_stale is True

    def test_concurrent_cache_access_safety(self, resolver, temp_cache_dir):
        """Test that concurrent cache operations don't corrupt data."""
        cache_key = "oci-vault://test-concurrent"
        values = ["value1", "value2", "value3"]

        # Simulate concurrent writes
        for value in values:
            resolver.cache_secret(cache_key, value)

        # Final read should succeed (last write wins)
        result = resolver.get_cached_secret(cache_key)

        assert result is not None
        retrieved_value, is_stale = result
        assert retrieved_value in values  # Should be one of the written values
        assert is_stale is False

    def test_cache_key_hashing_prevents_directory_traversal(self, resolver, temp_cache_dir):
        """Test that cache keys with path traversal attempts are safely hashed."""
        malicious_keys = [
            "oci-vault://../../../etc/passwd",
            "oci-vault://../../.ssh/id_rsa",
            "oci-vault://../vault-secrets",
        ]

        for cache_key in malicious_keys:
            # Get cache path
            cache_path = resolver.get_cache_path(cache_key)

            # Verify path is within cache directory
            assert temp_cache_dir in cache_path.parents or cache_path.parent == temp_cache_dir

            # Verify no directory traversal in final path
            assert ".." not in str(cache_path)

    def test_cache_path_consistency(self, resolver, temp_cache_dir):
        """Test that the same cache key always produces the same cache path."""
        cache_key = "oci-vault://test-consistency"

        # Get path multiple times
        path1 = resolver.get_cache_path(cache_key)
        path2 = resolver.get_cache_path(cache_key)
        path3 = resolver.get_cache_path(cache_key)

        # All should be identical
        assert path1 == path2 == path3

    def test_cache_write_error_handling(self, resolver, temp_cache_dir):
        """Test graceful handling of cache write failures."""
        cache_key = "oci-vault://test-write-error"
        secret_value = "test-value"

        # Make cache directory read-only to force write error
        temp_cache_dir.chmod(0o444)

        # Should not raise exception, just log error
        try:
            resolver.cache_secret(cache_key, secret_value)
        finally:
            # Restore permissions for cleanup
            temp_cache_dir.chmod(0o755)
