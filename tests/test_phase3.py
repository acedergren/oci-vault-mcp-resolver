"""Tests for Phase 3 resilience features and secret versioning."""

import time
from unittest.mock import Mock, patch

import oci
import pytest

from oci_vault_resolver import (
    CircuitBreaker,
    CircuitBreakerState,
    VaultResolver,
    VaultResolverError,
)


class TestCircuitBreaker:
    """Test suite for CircuitBreaker pattern."""

    def test_circuit_breaker_starts_closed(self):
        """Test that circuit breaker starts in CLOSED state."""
        cb = CircuitBreaker(failure_threshold=5, recovery_timeout=60.0)

        assert cb.state == CircuitBreakerState.CLOSED
        assert cb.failure_count == 0
        assert cb.success_count == 0

    def test_circuit_breaker_opens_after_threshold_failures(self):
        """Test that circuit opens after failure threshold is reached."""
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=60.0)

        def failing_func():
            raise Exception("Test failure")

        # First 2 failures should keep circuit closed
        for _ in range(2):
            try:
                cb.call(failing_func)
            except Exception:
                pass

        assert cb.state == CircuitBreakerState.CLOSED
        assert cb.failure_count == 2

        # Third failure should open the circuit
        try:
            cb.call(failing_func)
        except Exception:
            pass

        assert cb.state == CircuitBreakerState.OPEN
        assert cb.failure_count == 3

    def test_circuit_breaker_rejects_calls_when_open(self):
        """Test that circuit breaker rejects calls when OPEN."""
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=60.0)

        def failing_func():
            raise Exception("Test failure")

        # Force circuit to open
        try:
            cb.call(failing_func)
        except Exception:
            pass

        assert cb.state == CircuitBreakerState.OPEN

        # Next call should be rejected immediately
        with pytest.raises(VaultResolverError, match="Circuit breaker is OPEN"):
            cb.call(lambda: "success")

    def test_circuit_breaker_transitions_to_half_open_after_timeout(self):
        """Test that circuit transitions to HALF_OPEN after recovery timeout."""
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.1)  # 100ms timeout

        def failing_func():
            raise Exception("Test failure")

        # Force circuit to open
        try:
            cb.call(failing_func)
        except Exception:
            pass

        assert cb.state == CircuitBreakerState.OPEN

        # Wait for recovery timeout
        time.sleep(0.15)

        # Next call should transition to HALF_OPEN
        def success_func():
            return "success"

        result = cb.call(success_func)
        assert result == "success"
        # After one success, should still be in HALF_OPEN (needs 2 successes by default)
        assert cb.state == CircuitBreakerState.HALF_OPEN

    def test_circuit_breaker_closes_from_half_open_after_success_threshold(self):
        """Test that circuit closes after success threshold in HALF_OPEN state."""
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.1, success_threshold=2)

        def failing_func():
            raise Exception("Test failure")

        # Force circuit to open
        try:
            cb.call(failing_func)
        except Exception:
            pass

        assert cb.state == CircuitBreakerState.OPEN

        # Wait for recovery timeout
        time.sleep(0.15)

        def success_func():
            return "success"

        # First success - should transition to HALF_OPEN
        result1 = cb.call(success_func)
        assert result1 == "success"
        assert cb.state == CircuitBreakerState.HALF_OPEN

        # Second success - should close the circuit
        result2 = cb.call(success_func)
        assert result2 == "success"
        assert cb.state == CircuitBreakerState.CLOSED
        assert cb.failure_count == 0
        assert cb.success_count == 0

    def test_circuit_breaker_reopens_on_failure_in_half_open(self):
        """Test that circuit reopens if failure occurs in HALF_OPEN state."""
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.1)

        def failing_func():
            raise Exception("Test failure")

        # Force circuit to open
        try:
            cb.call(failing_func)
        except Exception:
            pass

        # Wait for recovery timeout
        time.sleep(0.15)

        # First call transitions to HALF_OPEN and succeeds
        cb.call(lambda: "success")
        assert cb.state == CircuitBreakerState.HALF_OPEN

        # Second call fails - should reopen circuit
        try:
            cb.call(failing_func)
        except Exception:
            pass

        assert cb.state == CircuitBreakerState.OPEN
        assert cb.failure_count == 1


class TestRetryWithBackoff:
    """Test suite for retry with exponential backoff."""

    def test_retry_succeeds_on_first_attempt(self, temp_cache_dir, mock_oci_clients):
        """Test that retry succeeds immediately if first attempt works."""
        resolver = VaultResolver(cache_dir=temp_cache_dir, max_retries=3, verbose=False)

        mock_secrets, _ = mock_oci_clients
        mock_bundle = Mock()
        import base64

        mock_bundle.data.secret_bundle_content.content = base64.b64encode(b"test-value").decode()
        mock_secrets.get_secret_bundle.return_value = mock_bundle

        result = resolver.fetch_secret_by_ocid("ocid1.vaultsecret.oc1.iad.test")

        assert result == "test-value"
        assert mock_secrets.get_secret_bundle.call_count == 1
        assert resolver.metrics["retries"] == 0

    def test_retry_succeeds_after_transient_failures(self, temp_cache_dir, mock_oci_clients):
        """Test that retry succeeds after transient failures."""
        resolver = VaultResolver(
            cache_dir=temp_cache_dir,
            max_retries=3,
            verbose=False,
            enable_circuit_breaker=False,  # Disable circuit breaker for this test
        )

        mock_secrets, _ = mock_oci_clients

        # Simulate 2 failures followed by success
        import base64

        mock_bundle = Mock()
        mock_bundle.data.secret_bundle_content.content = base64.b64encode(b"test-value").decode()

        error = oci.exceptions.ServiceError(
            status=500, code="InternalServerError", message="Transient error", headers={}
        )

        mock_secrets.get_secret_bundle.side_effect = [error, error, mock_bundle]

        result = resolver.fetch_secret_by_ocid("ocid1.vaultsecret.oc1.iad.test")

        assert result == "test-value"
        assert mock_secrets.get_secret_bundle.call_count == 3

    def test_retry_exhausts_attempts_on_persistent_failure(self, temp_cache_dir, mock_oci_clients):
        """Test that retry exhausts all attempts on persistent failures."""
        resolver = VaultResolver(
            cache_dir=temp_cache_dir,
            max_retries=2,
            verbose=False,
            enable_circuit_breaker=False,  # Disable circuit breaker
        )

        mock_secrets, _ = mock_oci_clients

        error = oci.exceptions.ServiceError(
            status=500, code="InternalServerError", message="Persistent error", headers={}
        )
        mock_secrets.get_secret_bundle.side_effect = error

        # Should raise VaultResolverError after exhausting retries
        with pytest.raises(VaultResolverError, match="OCI API error"):
            resolver.fetch_secret_by_ocid("ocid1.vaultsecret.oc1.iad.test")

        # Initial attempt + 2 retries = 3 total calls
        assert mock_secrets.get_secret_bundle.call_count == 3

    def test_retry_respects_max_retries_setting(self, temp_cache_dir, mock_oci_clients):
        """Test that retry respects the max_retries configuration."""
        resolver = VaultResolver(
            cache_dir=temp_cache_dir,
            max_retries=5,
            verbose=False,
            enable_circuit_breaker=False,
        )

        mock_secrets, _ = mock_oci_clients

        error = oci.exceptions.ServiceError(
            status=500, code="InternalServerError", message="Error", headers={}
        )
        mock_secrets.get_secret_bundle.side_effect = error

        # Should raise after exhausting all retries
        with pytest.raises(VaultResolverError):
            resolver.fetch_secret_by_ocid("ocid1.vaultsecret.oc1.iad.test")

        # Initial attempt + 5 retries = 6 total calls
        assert mock_secrets.get_secret_bundle.call_count == 6


class TestSecretVersioning:
    """Test suite for secret versioning support."""

    def test_parse_url_with_version_parameter(self, temp_cache_dir, mock_oci_clients):
        """Test parsing URL with version query parameter."""
        resolver = VaultResolver(cache_dir=temp_cache_dir, verbose=False)

        url = "oci-vault://ocid1.vaultsecret.oc1.iad.test?version=3"
        ocid, comp, name, version = resolver.parse_vault_url(url)

        assert ocid == "ocid1.vaultsecret.oc1.iad.test"
        assert comp is None
        assert name is None
        assert version == 3

    def test_fetch_specific_secret_version(self, temp_cache_dir, mock_oci_clients):
        """Test fetching a specific secret version."""
        resolver = VaultResolver(cache_dir=temp_cache_dir, verbose=False)

        mock_secrets, _ = mock_oci_clients
        mock_bundle = Mock()
        import base64

        mock_bundle.data.secret_bundle_content.content = base64.b64encode(
            b"version-2-value"
        ).decode()
        mock_secrets.get_secret_bundle.return_value = mock_bundle

        result = resolver.fetch_secret_by_ocid("ocid1.vaultsecret.oc1.iad.test", version_number=2)

        assert result == "version-2-value"
        # Verify version_number was passed to OCI SDK
        mock_secrets.get_secret_bundle.assert_called_once_with(
            secret_id="ocid1.vaultsecret.oc1.iad.test", version_number=2
        )

    def test_fetch_latest_version_when_no_version_specified(self, temp_cache_dir, mock_oci_clients):
        """Test that latest version is fetched when no version is specified."""
        resolver = VaultResolver(cache_dir=temp_cache_dir, verbose=False)

        mock_secrets, _ = mock_oci_clients
        mock_bundle = Mock()
        import base64

        mock_bundle.data.secret_bundle_content.content = base64.b64encode(b"latest-value").decode()
        mock_secrets.get_secret_bundle.return_value = mock_bundle

        result = resolver.fetch_secret_by_ocid("ocid1.vaultsecret.oc1.iad.test")

        assert result == "latest-value"
        # Verify no version_number parameter was passed
        mock_secrets.get_secret_bundle.assert_called_once_with(
            secret_id="ocid1.vaultsecret.oc1.iad.test"
        )

    def test_resolve_secret_with_version_parameter(self, temp_cache_dir, mock_oci_clients):
        """Test end-to-end secret resolution with version parameter."""
        resolver = VaultResolver(cache_dir=temp_cache_dir, verbose=False)

        mock_secrets, _ = mock_oci_clients
        mock_bundle = Mock()
        import base64

        mock_bundle.data.secret_bundle_content.content = base64.b64encode(
            b"versioned-secret"
        ).decode()
        mock_secrets.get_secret_bundle.return_value = mock_bundle

        vault_url = "oci-vault://ocid1.vaultsecret.oc1.iad.test?version=5"
        result = resolver.resolve_secret(vault_url)

        assert result == "versioned-secret"
        mock_secrets.get_secret_bundle.assert_called_once_with(
            secret_id="ocid1.vaultsecret.oc1.iad.test", version_number=5
        )

    def test_different_versions_cached_independently(self, temp_cache_dir, mock_oci_clients):
        """Test that different versions are cached independently."""
        resolver = VaultResolver(cache_dir=temp_cache_dir, ttl=3600, verbose=False)

        mock_secrets, _ = mock_oci_clients
        import base64

        # Set up mock to return different values for different calls
        mock_bundle_v1 = Mock()
        mock_bundle_v1.data.secret_bundle_content.content = base64.b64encode(b"version-1").decode()

        mock_bundle_v2 = Mock()
        mock_bundle_v2.data.secret_bundle_content.content = base64.b64encode(b"version-2").decode()

        mock_secrets.get_secret_bundle.side_effect = [mock_bundle_v1, mock_bundle_v2]

        # Fetch version 1
        url_v1 = "oci-vault://ocid1.vaultsecret.oc1.iad.test?version=1"
        result_v1 = resolver.resolve_secret(url_v1)
        assert result_v1 == "version-1"

        # Fetch version 2
        url_v2 = "oci-vault://ocid1.vaultsecret.oc1.iad.test?version=2"
        result_v2 = resolver.resolve_secret(url_v2)
        assert result_v2 == "version-2"

        # Verify both were fetched from API (different cache keys)
        assert mock_secrets.get_secret_bundle.call_count == 2

        # Fetch version 1 again - should hit cache
        result_v1_cached = resolver.resolve_secret(url_v1)
        assert result_v1_cached == "version-1"
        # Should still be 2 API calls (third fetch hit cache)
        assert mock_secrets.get_secret_bundle.call_count == 2


class TestIntegration:
    """Integration tests for Phase 3 features working together."""

    def test_circuit_breaker_and_retry_together(self, temp_cache_dir, mock_oci_clients):
        """Test that circuit breaker and retry work together correctly."""
        resolver = VaultResolver(
            cache_dir=temp_cache_dir,
            max_retries=2,
            enable_circuit_breaker=True,
            circuit_breaker_threshold=3,
            verbose=False,
        )

        mock_secrets, _ = mock_oci_clients

        # Simulate persistent failures
        error = oci.exceptions.ServiceError(
            status=500, code="InternalServerError", message="Error", headers={}
        )
        mock_secrets.get_secret_bundle.side_effect = error

        # Each fetch will retry 2 times and then raise VaultResolverError
        # We need 3 failed fetches to hit circuit breaker threshold of 3
        for i in range(3):
            with pytest.raises(VaultResolverError):
                resolver.fetch_secret_by_ocid(f"ocid1.vaultsecret.oc1.iad.test{i}")

        # Circuit should now be open
        assert resolver.circuit_breaker.state == CircuitBreakerState.OPEN

        # Next fetch should be rejected immediately by circuit breaker
        with pytest.raises(VaultResolverError, match="Circuit breaker is OPEN"):
            resolver.fetch_secret_by_ocid("ocid1.vaultsecret.oc1.iad.test999")

        # Verify circuit breaker metrics
        assert resolver.metrics["circuit_breaker_opens"] >= 1

    def test_versioned_secrets_with_circuit_breaker(self, temp_cache_dir, mock_oci_clients):
        """Test that versioned secrets work with circuit breaker enabled."""
        resolver = VaultResolver(
            cache_dir=temp_cache_dir,
            enable_circuit_breaker=True,
            verbose=False,
        )

        mock_secrets, _ = mock_oci_clients
        mock_bundle = Mock()
        import base64

        mock_bundle.data.secret_bundle_content.content = base64.b64encode(
            b"versioned-with-cb"
        ).decode()
        mock_secrets.get_secret_bundle.return_value = mock_bundle

        url = "oci-vault://ocid1.vaultsecret.oc1.iad.test?version=10"
        result = resolver.resolve_secret(url)

        assert result == "versioned-with-cb"
        # Verify circuit breaker is still closed
        assert resolver.circuit_breaker.state == CircuitBreakerState.CLOSED

    def test_metrics_tracking_for_all_features(self, temp_cache_dir, mock_oci_clients):
        """Test that metrics track all Phase 3 features correctly."""
        resolver = VaultResolver(
            cache_dir=temp_cache_dir,
            max_retries=3,
            enable_circuit_breaker=True,
            verbose=False,
        )

        # Initial metrics should be zero
        assert resolver.metrics["retries"] == 0
        assert resolver.metrics["circuit_breaker_opens"] == 0

        mock_secrets, _ = mock_oci_clients
        import base64

        # Simulate one failure followed by success (triggers retry)
        mock_bundle = Mock()
        mock_bundle.data.secret_bundle_content.content = base64.b64encode(b"success").decode()

        error = oci.exceptions.ServiceError(
            status=500, code="InternalServerError", message="Transient", headers={}
        )

        mock_secrets.get_secret_bundle.side_effect = [error, mock_bundle]

        result = resolver.fetch_secret_by_ocid("ocid1.vaultsecret.oc1.iad.test")

        assert result == "success"
        # Circuit should still be closed (only 1 failure)
        assert resolver.circuit_breaker.state == CircuitBreakerState.CLOSED
        assert resolver.metrics["secrets_fetched"] == 1
