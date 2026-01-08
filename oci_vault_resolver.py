#!/usr/bin/env python3
"""
OCI Vault MCP Resolver.

Resolves oci-vault:// references in Docker MCP Gateway configuration
by fetching secrets from Oracle Cloud Infrastructure Vault using the OCI Python SDK.

Supported URL formats:
  - oci-vault://secret-ocid
  - oci-vault://compartment-ocid/secret-name
  - oci-vault://vault-ocid/secret-name

Features:
  - Parallel secret resolution for optimal performance
  - Caching with configurable TTL
  - Fallback to stale cache on errors
  - Instance principal authentication (for OCI VMs)
  - Structured error handling
  - Recursive resolution of nested configs
"""

import argparse
import asyncio
import base64
import json
import logging
import os
import random
import re
import sys
import time
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union, cast

import yaml

try:
    import oci
    from oci.secrets import SecretsClient
    from oci.vault import VaultsClient
except ImportError as e:
    print("ERROR: OCI SDK is required. Install with: pip install oci", file=sys.stderr)
    print(f"Import error: {e}", file=sys.stderr)
    sys.exit(1)


# Custom Exceptions
class VaultResolverError(Exception):
    """Base exception for all VaultResolver errors."""

    pass


class AuthenticationError(VaultResolverError):
    """Raised when OCI authentication fails."""

    pass


class SecretNotFoundError(VaultResolverError):
    """Raised when a secret cannot be found in OCI Vault."""

    def __init__(self, secret_id: str, compartment_id: Optional[str] = None):
        """
        Initialize SecretNotFoundError.

        Args:
            secret_id: The OCID or name of the secret
            compartment_id: Optional compartment OCID where secret was searched
        """
        self.secret_id = secret_id
        self.compartment_id = compartment_id
        if compartment_id:
            super().__init__(f"Secret '{secret_id}' not found in compartment {compartment_id}")
        else:
            super().__init__(f"Secret not found: {secret_id}")


class PermissionDeniedError(VaultResolverError):
    """Raised when the user lacks permission to access a secret."""

    def __init__(self, secret_id: str):
        """
        Initialize PermissionDeniedError.

        Args:
            secret_id: The OCID of the secret that access was denied for
        """
        self.secret_id = secret_id
        super().__init__(f"Permission denied for secret: {secret_id}")


class InvalidVaultURLError(VaultResolverError):
    """Raised when a vault URL is malformed."""

    def __init__(self, url: str):
        """
        Initialize InvalidVaultURLError.

        Args:
            url: The malformed vault URL
        """
        self.url = url
        super().__init__(f"Invalid vault URL format: {url}")


class ConfigurationError(VaultResolverError):
    """Raised when configuration is invalid or missing."""

    pass


# Configuration
DEFAULT_CACHE_DIR = Path.home() / ".cache" / "oci-vault-mcp"
DEFAULT_TTL = 3600  # 1 hour in seconds
VAULT_URL_PATTERN = re.compile(r"^oci-vault://(.+)$")

# Retry configuration
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_BACKOFF_BASE = 2  # seconds
DEFAULT_RETRY_JITTER = True


class CircuitBreakerState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if service recovered


class CircuitBreaker:
    """
    Circuit breaker pattern for OCI Vault API calls.

    Prevents cascading failures by opening the circuit after threshold failures.
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        success_threshold: int = 2,
    ):
        """
        Initialize circuit breaker.

        Args:
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Seconds to wait before attempting recovery
            success_threshold: Successful calls needed to close circuit from half-open
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.success_threshold = success_threshold

        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[float] = None
        self.state = CircuitBreakerState.CLOSED

        self.logger = logging.getLogger(__name__)

    def call(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """
        Execute function with circuit breaker protection.

        Args:
            func: Function to call
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Function result

        Raises:
            VaultResolverError: If circuit is open
        """
        if self.state == CircuitBreakerState.OPEN:
            if self._should_attempt_reset():
                self.logger.info("Circuit breaker transitioning to HALF_OPEN")
                self.state = CircuitBreakerState.HALF_OPEN
            else:
                raise VaultResolverError(
                    f"Circuit breaker is OPEN (recovery timeout: {self.recovery_timeout}s)"
                )

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise e

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt recovery."""
        if self.last_failure_time is None:
            return False
        return (time.time() - self.last_failure_time) >= self.recovery_timeout

    def _on_success(self) -> None:
        """Handle successful call."""
        self.failure_count = 0

        if self.state == CircuitBreakerState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.success_threshold:
                self.logger.info("Circuit breaker transitioning to CLOSED")
                self.state = CircuitBreakerState.CLOSED
                self.success_count = 0

    def _on_failure(self) -> None:
        """Handle failed call."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        self.success_count = 0

        if self.failure_count >= self.failure_threshold:
            if self.state != CircuitBreakerState.OPEN:
                self.logger.warning(
                    f"Circuit breaker transitioning to OPEN after {self.failure_count} failures"
                )
                self.state = CircuitBreakerState.OPEN


def retry_with_backoff(
    max_retries: int = DEFAULT_MAX_RETRIES,
    backoff_base: float = DEFAULT_RETRY_BACKOFF_BASE,
    jitter: bool = DEFAULT_RETRY_JITTER,
    retryable_exceptions: Tuple[type, ...] = (Exception,),
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """
    Decorate functions with exponential backoff retry logic.

    Args:
        max_retries: Maximum number of retry attempts
        backoff_base: Base delay in seconds (doubled each retry)
        jitter: Add random jitter to backoff delay
        retryable_exceptions: Tuple of exception types to retry on

    Returns:
        Decorated function
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            logger = logging.getLogger(__name__)
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except retryable_exceptions as e:  # type: ignore[misc]
                    last_exception = e

                    # Don't retry on last attempt
                    if attempt >= max_retries:
                        break

                    # Calculate backoff delay
                    delay = backoff_base * (2**attempt)
                    if jitter:
                        # Add random jitter (±25%)
                        delay *= 0.75 + (random.random() * 0.5)

                    logger.warning(
                        f"Retry {attempt + 1}/{max_retries} after {delay:.2f}s due to: {e}"
                    )
                    time.sleep(delay)

            # All retries exhausted
            logger.error(f"Max retries ({max_retries}) exhausted")
            raise last_exception  # type: ignore

        return wrapper

    return decorator


class VaultResolver:
    """
    Resolves OCI Vault references in configuration using OCI Python SDK.

    Features:
    - Direct API calls (no subprocess overhead)
    - Parallel secret resolution
    - Better error handling with structured exceptions
    - Instance principal authentication support
    """

    def __init__(
        self,
        cache_dir: Path = DEFAULT_CACHE_DIR,
        ttl: int = DEFAULT_TTL,
        verbose: bool = False,
        use_instance_principals: bool = False,
        config_file: Optional[str] = None,
        config_profile: str = "DEFAULT",
        max_retries: int = DEFAULT_MAX_RETRIES,
        enable_circuit_breaker: bool = True,
        circuit_breaker_threshold: int = 5,
        default_compartment_id: Optional[str] = None,
        default_vault_id: Optional[str] = None,
    ):
        """
        Initialize SDK-based resolver.

        Args:
            cache_dir: Cache directory path
            ttl: Cache TTL in seconds
            verbose: Enable verbose logging
            use_instance_principals: Use instance principal authentication (for OCI VMs)
            config_file: Path to OCI config file (default: ~/.oci/config)
            config_profile: Config profile to use
            max_retries: Maximum retry attempts for API calls
            enable_circuit_breaker: Enable circuit breaker pattern
            circuit_breaker_threshold: Failures before opening circuit
            default_compartment_id: Default compartment OCID for secret lookups
            default_vault_id: Default vault OCID
        """
        self.cache_dir = cache_dir
        self.ttl = ttl
        self.verbose = verbose
        self.default_compartment_id = default_compartment_id
        self.default_vault_id = default_vault_id
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Configure logging
        self.logger = logging.getLogger(__name__)
        if verbose:
            self.logger.setLevel(logging.DEBUG)
        else:
            self.logger.setLevel(logging.INFO)

        # Retry configuration
        self.max_retries = max_retries

        # Circuit breaker
        self.circuit_breaker: Optional[CircuitBreaker] = None
        if enable_circuit_breaker:
            self.circuit_breaker = CircuitBreaker(
                failure_threshold=circuit_breaker_threshold,
                recovery_timeout=60.0,
                success_threshold=2,
            )
            self.logger.debug(f"Circuit breaker enabled (threshold: {circuit_breaker_threshold})")

        # Performance metrics
        self.metrics = {
            "secrets_fetched": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "stale_cache_used": 0,
            "total_fetch_time": 0.0,
            "retries": 0,
            "circuit_breaker_opens": 0,
        }

        # Initialize OCI clients
        try:
            if use_instance_principals:
                self.log("Using instance principal authentication")
                signer = oci.auth.signers.InstancePrincipalsSecurityTokenSigner()
                self.secrets_client = SecretsClient(config={}, signer=signer)
                self.vaults_client = VaultsClient(config={}, signer=signer)
            else:
                config_path = config_file or "~/.oci/config"
                self.log(f"Loading OCI config from {config_path} " f"profile={config_profile}")
                config = oci.config.from_file(
                    file_location=config_file, profile_name=config_profile
                )
                self.secrets_client = SecretsClient(config)
                self.vaults_client = VaultsClient(config)

            self.log("OCI SDK clients initialized successfully")

        except Exception as e:
            raise AuthenticationError(f"Failed to initialize OCI SDK clients: {e}")

    @classmethod
    def from_config(cls, config_path: Optional[Path] = None) -> "VaultResolver":  # noqa: C901
        """
        Create VaultResolver from configuration file.

        Searches for config in priority order:
          1. Specified config_path
          2. ~/.config/oci-vault-mcp/resolver.yaml (user-level)
          3. /etc/oci-vault-mcp/resolver.yaml (system-level)
          4. ./resolver.yaml (current directory)

        Environment variables override config file settings:
          - OCI_VAULT_ID → vault.vault_id
          - OCI_VAULT_COMPARTMENT_ID → vault.compartment_id
          - OCI_REGION → vault.region
          - OCI_USE_INSTANCE_PRINCIPALS → vault.auth_method
          - OCI_CONFIG_FILE → vault.config_file
          - OCI_CONFIG_PROFILE → vault.config_profile
          - OCI_VAULT_CACHE_DIR → cache.directory
          - OCI_VAULT_CACHE_TTL → cache.ttl
          - OCI_VAULT_ENVIRONMENT → select environment

        Args:
            config_path: Optional path to config file (overrides search)

        Returns:
            Configured VaultResolver instance

        Raises:
            ConfigurationError: If no config file found or invalid config
        """
        # Search for config file
        search_paths = [
            config_path,
            Path.home() / ".config" / "oci-vault-mcp" / "resolver.yaml",
            Path("/etc/oci-vault-mcp/resolver.yaml"),
            Path("./resolver.yaml"),
        ]

        config_file_path = None
        for path in search_paths:
            if path and path.exists():
                config_file_path = path
                break

        if not config_file_path:
            raise ConfigurationError(
                "No resolver.yaml found in search paths:\n"
                "  1. ~/.config/oci-vault-mcp/resolver.yaml (user-level)\n"
                "  2. /etc/oci-vault-mcp/resolver.yaml (system-level)\n"
                "  3. ./resolver.yaml (current directory)\n"
                "Run: cp config/resolver.yaml.example ~/.config/oci-vault-mcp/resolver.yaml"
            )

        # Load YAML config
        try:
            with open(config_file_path, "r") as f:
                config = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ConfigurationError(f"Failed to parse YAML config: {e}")
        except Exception as e:
            raise ConfigurationError(f"Failed to read config file: {e}")

        if not config or not isinstance(config, dict):
            raise ConfigurationError("Configuration must be a non-empty dictionary")

        # Extract environment name from env var or config
        environment = os.environ.get("OCI_VAULT_ENVIRONMENT")

        # Apply environment-specific overrides
        if environment and environment in config.get("environments", {}):
            env_config = config["environments"][environment]

            # Deep merge environment config into base config
            def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
                """Recursively merge override into base."""
                result = base.copy()
                for key, value in override.items():
                    if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                        result[key] = deep_merge(result[key], value)
                    else:
                        result[key] = value
                return result

            config = deep_merge(config, env_config)

        # Get vault settings with environment variable overrides
        vault_config = config.get("vault", {})
        vault_id = os.environ.get("OCI_VAULT_ID") or vault_config.get("vault_id")
        compartment_id = os.environ.get("OCI_VAULT_COMPARTMENT_ID") or vault_config.get(
            "compartment_id"
        )
        _ = os.environ.get("OCI_REGION") or vault_config.get("region")  # noqa: F841

        # Auth method
        use_instance_principals = (
            os.environ.get("OCI_USE_INSTANCE_PRINCIPALS", "").lower() == "true"
            or vault_config.get("auth_method") == "instance_principal"
        )
        config_file = os.environ.get("OCI_CONFIG_FILE") or vault_config.get("config_file")
        config_profile = os.environ.get("OCI_CONFIG_PROFILE") or vault_config.get(
            "config_profile", "DEFAULT"
        )

        # Cache settings
        cache_config = config.get("cache", {})
        cache_dir_str = os.environ.get("OCI_VAULT_CACHE_DIR") or cache_config.get(
            "directory", "~/.cache/oci-vault-mcp"
        )
        cache_dir = Path(cache_dir_str).expanduser()

        cache_ttl_str = os.environ.get("OCI_VAULT_CACHE_TTL")
        cache_ttl = int(cache_ttl_str) if cache_ttl_str else cache_config.get("ttl", DEFAULT_TTL)

        # Resilience settings
        resilience_config = config.get("resilience", {})
        max_retries = resilience_config.get("max_retries", DEFAULT_MAX_RETRIES)
        enable_circuit_breaker = resilience_config.get("enable_circuit_breaker", True)
        circuit_breaker_threshold = resilience_config.get("circuit_breaker_threshold", 5)

        # Logging settings
        logging_config = config.get("logging", {})
        verbose = logging_config.get("verbose", False)

        # Create and return VaultResolver instance
        return cls(
            cache_dir=cache_dir,
            ttl=cache_ttl,
            verbose=verbose,
            use_instance_principals=use_instance_principals,
            config_file=config_file,
            config_profile=config_profile,
            max_retries=max_retries,
            enable_circuit_breaker=enable_circuit_breaker,
            circuit_breaker_threshold=circuit_breaker_threshold,
            default_compartment_id=compartment_id,
            default_vault_id=vault_id,
        )

    def log(self, message: str) -> None:
        """Log message if verbose mode is enabled."""
        self.logger.debug(message)

    def parse_vault_url(  # noqa: C901
        self, url: str
    ) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[int]]:
        """
        Parse oci-vault:// URL into components.

        Supports version specification: oci-vault://secret-ocid?version=2

        Returns:
            Tuple of (secret_ocid, compartment_id, secret_name, version_number)
            or (None, None, None, None) if invalid
        """
        match = VAULT_URL_PATTERN.match(url)
        if not match:
            return None, None, None, None

        path = match.group(1)

        # Extract version from query string (e.g., oci-vault://secret?version=2)
        version_number: Optional[int] = None
        if "?" in path:
            path, query_string = path.split("?", 1)
            # Parse query parameters
            for param in query_string.split("&"):
                if "=" in param:
                    key, value = param.split("=", 1)
                    if key == "version":
                        try:
                            version_number = int(value)
                        except ValueError:
                            self.logger.warning(f"Invalid version number: {value}")

        parts = path.split("/")

        # Format: oci-vault://secret-ocid
        if len(parts) == 1:
            if parts[0].startswith("ocid1.vaultsecret."):
                return parts[0], None, None, version_number
            else:
                # Treat as secret name in default compartment
                return None, None, parts[0], version_number

        # Format: oci-vault://compartment-or-vault-id/secret-name
        elif len(parts) == 2:
            container_id, secret_name = parts
            if container_id.startswith("ocid1.compartment."):
                return None, container_id, secret_name, version_number
            elif container_id.startswith("ocid1.vault."):
                # For vault OCID, we need to list secrets in that vault
                return None, container_id, secret_name, version_number
            else:
                # Treat first part as compartment name
                return None, container_id, secret_name, version_number

        return None, None, None, None

    def get_cache_path(self, cache_key: str) -> Path:
        """Get cache file path for a cache key."""
        # Use hash to avoid filesystem issues with long OCIDs
        import hashlib

        key_hash = hashlib.sha256(cache_key.encode()).hexdigest()[:16]
        return self.cache_dir / f"{key_hash}.json"

    def get_cached_secret(self, cache_key: str) -> Optional[Tuple[str, bool]]:
        """
        Get cached secret if available and not expired.

        Returns: (secret_value, is_stale) or None
        """
        cache_path = self.get_cache_path(cache_key)

        if not cache_path.exists():
            self.log(f"Cache miss: {cache_key}")
            self.metrics["cache_misses"] += 1
            return None

        try:
            with open(cache_path, "r") as f:
                cache_data = json.load(f)

            cached_at = cache_data.get("cached_at", 0)
            secret_value = cache_data.get("value")

            if not secret_value:
                return None

            age = time.time() - cached_at
            is_stale = age > self.ttl

            if is_stale:
                self.log(f"Cache stale: {cache_key} (age: {age:.0f}s)")
            else:
                self.log(f"Cache hit: {cache_key} (age: {age:.0f}s)")
                self.metrics["cache_hits"] += 1

            return secret_value, is_stale

        except Exception as e:
            self.log(f"Cache read error: {e}")
            return None

    def cache_secret(self, cache_key: str, secret_value: str) -> None:
        """Cache a secret value with timestamp."""
        cache_path = self.get_cache_path(cache_key)

        try:
            cache_data = {"value": secret_value, "cached_at": time.time(), "cache_key": cache_key}

            with open(cache_path, "w") as f:
                json.dump(cache_data, f)

            # Secure the cache file
            cache_path.chmod(0o600)
            self.log(f"Cached: {cache_key}")

        except Exception as e:
            self.log(f"Cache write error: {e}")

    def _fetch_secret_with_retry(
        self, secret_ocid: str, version_number: Optional[int] = None
    ) -> str:
        """
        Fetch secret with retry logic.

        Args:
            secret_ocid: Secret OCID to fetch
            version_number: Optional version number to fetch

        Returns:
            Decoded secret value

        Raises:
            OCI ServiceError exceptions
        """

        @retry_with_backoff(
            max_retries=self.max_retries,
            backoff_base=DEFAULT_RETRY_BACKOFF_BASE,
            jitter=DEFAULT_RETRY_JITTER,
            retryable_exceptions=(oci.exceptions.ServiceError,),
        )
        def _fetch() -> str:
            if version_number is not None:
                response = self.secrets_client.get_secret_bundle(
                    secret_id=secret_ocid, version_number=version_number
                )
            else:
                response = self.secrets_client.get_secret_bundle(secret_id=secret_ocid)

            content: str = response.data.secret_bundle_content.content
            decoded_bytes = base64.b64decode(content)
            return decoded_bytes.decode("utf-8")

        # Track retries
        initial_retries = self.metrics.get("retries", 0)
        result: str = _fetch()
        retries_used = self.metrics.get("retries", 0) - initial_retries
        if retries_used > 0:
            self.metrics["retries"] = self.metrics.get("retries", 0) + retries_used

        return result

    def fetch_secret_by_ocid(
        self, secret_ocid: str, version_number: Optional[int] = None
    ) -> Optional[str]:
        """
        Fetch secret value from OCI Vault by secret OCID using SDK.

        Args:
            secret_ocid: Secret OCID to fetch
            version_number: Optional version number (defaults to latest)

        Returns:
            Decoded secret value or None on error
        """
        start_time = time.time()
        try:
            version_msg = f" (version {version_number})" if version_number else ""
            self.log(f"Fetching secret: {secret_ocid}{version_msg}")

            # Use circuit breaker if enabled
            decoded: str
            if self.circuit_breaker:
                decoded = cast(
                    str,
                    self.circuit_breaker.call(
                        self._fetch_secret_with_retry, secret_ocid, version_number
                    ),
                )
            else:
                decoded = self._fetch_secret_with_retry(secret_ocid, version_number)

            fetch_time = time.time() - start_time
            self.metrics["secrets_fetched"] += 1
            self.metrics["total_fetch_time"] += fetch_time
            self.log(f"Successfully fetched: {secret_ocid}{version_msg} (took {fetch_time:.3f}s)")
            return decoded

        except oci.exceptions.ServiceError as e:
            # Structured exception handling
            if e.status == 404:
                self.log(f"Secret not found: {secret_ocid}")
                raise SecretNotFoundError(secret_ocid)
            elif e.status == 401:
                self.log("Authentication failed")
                raise AuthenticationError("Authentication failed. Check OCI credentials.")
            elif e.status == 403:
                self.log(f"Permission denied for secret: {secret_ocid}")
                raise PermissionDeniedError(secret_ocid)
            else:
                self.log(f"OCI API error: {e.message}")
                raise VaultResolverError(f"OCI API error: {e.message}")

        except VaultResolverError as e:
            # Circuit breaker opened
            if "Circuit breaker is OPEN" in str(e):
                self.metrics["circuit_breaker_opens"] = (
                    self.metrics.get("circuit_breaker_opens", 0) + 1
                )
                self.logger.warning(f"Circuit breaker OPEN, rejecting request for {secret_ocid}")
            raise

        except Exception as e:
            self.log(f"Error fetching secret: {e}")
            self.logger.error(f"Error fetching secret: {e}")
            return None

    def find_secret_by_name(self, compartment_id: str, secret_name: str) -> Optional[str]:
        """Find secret OCID by name in a compartment using SDK."""
        try:
            self.log(f"Searching for secret '{secret_name}' in compartment {compartment_id}")

            # List secrets in compartment using SDK
            response = self.vaults_client.list_secrets(
                compartment_id=compartment_id, lifecycle_state="ACTIVE"
            )

            # Find matching secret
            for secret in response.data:
                if secret.secret_name == secret_name:
                    self.log(f"Found secret OCID: {secret.id}")
                    return cast(str, secret.id)

            self.log(f"Secret '{secret_name}' not found in compartment")
            return None

        except oci.exceptions.ServiceError as e:
            self.log(f"OCI API error: {e.message}")
            self.logger.error(e.message)
            return None
        except Exception as e:
            self.log(f"Error searching for secret: {e}")
            self.logger.error(f"Error searching for secret: {e}")
            return None

    def _try_stale_cache_fallback(
        self, cached: Optional[Tuple[str, bool]], vault_url: str, reason: str
    ) -> Optional[str]:
        """
        Attempt to use stale cached value as fallback.

        Args:
            cached: Cached value tuple (value, is_stale) or None
            vault_url: The vault URL being resolved (for warning message)
            reason: Reason for fallback (for warning message)

        Returns:
            Cached value if available, None otherwise
        """
        if cached:
            value, _ = cached
            self.metrics["stale_cache_used"] += 1
            self.logger.warning(f"{reason}, using stale cached value for {vault_url}")
            return value
        return None

    def resolve_secret(self, vault_url: str) -> Optional[str]:  # noqa: C901
        """
        Resolve a single oci-vault:// URL to its secret value.

        Uses caching and provides fallback to stale cache on errors.
        Supports version specification: oci-vault://secret-ocid?version=2
        """
        cache_key = vault_url

        # Check cache first
        cached = self.get_cached_secret(cache_key)
        if cached:
            value, is_stale = cached
            if not is_stale:
                return value

        # Parse URL (now returns version_number as 4th element)
        secret_ocid, compartment_id, secret_name, version_number = self.parse_vault_url(vault_url)

        if not secret_ocid and not secret_name:
            self.logger.error(f"Invalid vault URL format: {vault_url}")
            return None

        # Resolve secret OCID if needed
        if not secret_ocid:
            if not compartment_id:
                self.logger.error(f"No compartment specified for secret name: {secret_name}")
                return None

            # Type narrowing: we know secret_name is not None here
            assert secret_name is not None, "secret_name validated earlier"
            secret_ocid = self.find_secret_by_name(compartment_id, secret_name)
            if not secret_ocid:
                self.logger.error(
                    f"Secret not found: {secret_name} in compartment {compartment_id}"
                )
                return self._try_stale_cache_fallback(cached, vault_url, "Secret not found")

        # Fetch secret value (with optional version)
        try:
            secret_value = self.fetch_secret_by_ocid(secret_ocid, version_number)
            if secret_value:
                # Cache the result
                self.cache_secret(cache_key, secret_value)
                return secret_value
        except (SecretNotFoundError, PermissionDeniedError, AuthenticationError) as e:
            # Log structured error
            self.logger.error(str(e))
            # Fallback to stale cache
            return self._try_stale_cache_fallback(cached, vault_url, str(e))
        except VaultResolverError as e:
            # Generic vault error
            self.logger.error(str(e))
            return self._try_stale_cache_fallback(cached, vault_url, "OCI Vault fetch failed")

        # Fallback to stale cache if fetch failed
        return self._try_stale_cache_fallback(cached, vault_url, "OCI Vault fetch failed")

    def log_performance_metrics(self) -> None:
        """Log performance metrics summary."""
        cache_total = self.metrics["cache_hits"] + self.metrics["cache_misses"]
        cache_hit_rate = (
            (self.metrics["cache_hits"] / cache_total * 100) if cache_total > 0 else 0.0
        )
        avg_fetch_time = (
            (self.metrics["total_fetch_time"] / self.metrics["secrets_fetched"])
            if self.metrics["secrets_fetched"] > 0
            else 0.0
        )

        self.logger.info("Performance metrics:")
        self.logger.info(f"  Secrets fetched: {self.metrics['secrets_fetched']}")
        self.logger.info(f"  Cache hit rate: {cache_hit_rate:.1f}%")
        self.logger.info(f"  Cache hits: {self.metrics['cache_hits']}")
        self.logger.info(f"  Cache misses: {self.metrics['cache_misses']}")
        self.logger.info(f"  Stale cache used: {self.metrics['stale_cache_used']}")
        self.logger.info(f"  Avg fetch time: {avg_fetch_time:.3f}s")
        self.logger.info(f"  Total fetch time: {self.metrics['total_fetch_time']:.3f}s")

    def validate_config(self, config: Any) -> None:
        """
        Validate configuration structure.

        Args:
            config: Configuration object to validate

        Raises:
            ConfigurationError: If configuration is invalid
        """
        if config is None:
            raise ConfigurationError("Configuration cannot be None")

        if not isinstance(config, dict):
            raise ConfigurationError(
                f"Configuration must be a dictionary, got {type(config).__name__}"
            )

        # Check for common config structures (MCP, Docker Compose, etc.)
        if not config:
            raise ConfigurationError("Configuration is empty")

        # Validate that values are JSON-serializable
        try:
            json.dumps(config)
        except (TypeError, ValueError) as e:
            raise ConfigurationError(f"Configuration contains non-serializable values: {e}")

    def find_vault_references(self, obj: Any, path: str = "") -> Dict[str, str]:
        """
        Recursively find all oci-vault:// references in a nested structure.

        Args:
            obj: The object to search (can be dict, list, str, or any type)
            path: Current path in dot notation (used for recursion)

        Returns:
            Dictionary mapping dotted path to vault URL
            Example: {"servers.db.env.PASSWORD": "oci-vault://secret-id"}
        """
        references: Dict[str, str] = {}

        if isinstance(obj, dict):
            for key, value in obj.items():
                current_path = f"{path}.{key}" if path else key
                references.update(self.find_vault_references(value, current_path))

        elif isinstance(obj, list):
            for idx, item in enumerate(obj):
                current_path = f"{path}[{idx}]"
                references.update(self.find_vault_references(item, current_path))

        elif isinstance(obj, str):
            if VAULT_URL_PATTERN.match(obj):
                references[path] = obj

        return references

    def set_nested_value(
        self, obj: Union[Dict[str, Any], List[Any]], path: str, value: str
    ) -> Union[Dict[str, Any], List[Any]]:
        """
        Set a value in a nested structure using a dot/bracket path.

        Args:
            obj: The root object (dict or list) to modify
            path: Dot-separated path with optional [index] for lists
            value: The value to set at the path location

        Returns:
            The modified object (same reference)
        """
        if not path:
            return value  # type: ignore[return-value]

        parts = re.split(r"\.|\[|\]", path)
        parts = [p for p in parts if p]  # Remove empty strings

        current: Any = obj  # Type as Any to allow flexible indexing
        for i, part in enumerate(parts[:-1]):
            if part.isdigit():
                # Indexing a list with integer
                current = current[int(part)]
            else:
                # Indexing a dict with string
                if part not in current:
                    # Determine if next level should be list or dict
                    next_part = parts[i + 1]
                    current[part] = [] if next_part.isdigit() else {}
                current = current[part]

        last_part = parts[-1]
        if last_part.isdigit():
            # Set list element
            current[int(last_part)] = value
        else:
            # Set dict value
            current[last_part] = value

        return obj

    async def fetch_secrets_parallel(self, vault_urls: List[str]) -> Dict[str, Optional[str]]:
        """
        Fetch multiple secrets in parallel using asyncio.

        This method provides significant performance improvement when resolving
        multiple secrets by executing OCI API calls concurrently.

        Args:
            vault_urls: List of oci-vault:// URLs to resolve

        Returns:
            Dictionary mapping vault URL to secret value (None if fetch failed)
            Example: {"oci-vault://secret1": "value1", "oci-vault://secret2": None}
        """
        self.log(f"Fetching {len(vault_urls)} secrets in parallel")

        # Create tasks for parallel execution
        async def fetch_one(url: str) -> Tuple[str, Optional[str]]:
            # Run synchronous secret resolution in executor
            loop = asyncio.get_event_loop()
            value = await loop.run_in_executor(None, self.resolve_secret, url)
            return url, value

        # Execute all tasks concurrently
        tasks = [fetch_one(url) for url in vault_urls]
        results = await asyncio.gather(*tasks)

        return dict(results)

    def resolve_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Resolve all oci-vault:// references in a config dictionary.

        Uses parallel resolution for better performance.

        Returns: config with resolved secrets
        """
        # Validate configuration structure
        self.validate_config(config)

        # Find all vault references
        references = self.find_vault_references(config)

        if not references:
            self.log("No vault references found in config")
            return config

        vault_urls = list(references.values())
        self.logger.info(f"Found {len(references)} vault reference(s) to resolve (parallel mode)")

        # Resolve all secrets in parallel
        try:
            resolved_secrets = asyncio.run(self.fetch_secrets_parallel(vault_urls))
        except RuntimeError:
            # If event loop already running (e.g., in async context), fall back to sequential
            self.log("Event loop already running, using sequential resolution")
            # Sequential fallback
            resolved_secrets = {}
            for vault_url in vault_urls:
                resolved_secrets[vault_url] = self.resolve_secret(vault_url)

        # Apply resolved values to config
        resolved_count = 0
        for path, vault_url in references.items():
            secret_value = resolved_secrets.get(vault_url)

            if secret_value is not None:
                self.set_nested_value(config, path, secret_value)
                resolved_count += 1
            else:
                self.logger.error(f"Failed to resolve {path}: {vault_url}")

        self.logger.info(f"Successfully resolved {resolved_count}/{len(references)} secret(s)")

        if resolved_count < len(references):
            self.logger.warning(
                f"{len(references) - resolved_count} secret(s) could not be resolved"
            )

        # Log performance metrics if verbose
        if self.verbose:
            self.log_performance_metrics()

        return config


def main() -> None:
    """CLI entry point for OCI Vault MCP Resolver."""
    # Configure root logger for CLI usage
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s: %(message)s",
        stream=sys.stderr,
    )
    logger = logging.getLogger(__name__)

    parser = argparse.ArgumentParser(
        description="Resolve OCI Vault references in Docker MCP Gateway configuration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic usage (parallel resolution)
  docker mcp config read | python3 oci_vault_resolver.py

  # With instance principals (for OCI VMs)
  docker mcp config read | python3 oci_vault_resolver.py --instance-principals

  # Use custom cache TTL (2 hours)
  docker mcp config read | python3 oci_vault_resolver.py --ttl 7200

  # Enable verbose logging
  docker mcp config read | python3 oci_vault_resolver.py --verbose

  # With custom config profile
  docker mcp config read | python3 oci_vault_resolver.py --profile MY_PROFILE

  # Clear cache
  rm -rf ~/.cache/oci-vault-mcp/
        """,
    )

    parser.add_argument(
        "-i",
        "--input",
        type=argparse.FileType("r"),
        default=sys.stdin,
        help="Input YAML file (default: stdin)",
    )

    parser.add_argument(
        "-o",
        "--output",
        type=argparse.FileType("w"),
        default=sys.stdout,
        help="Output YAML file (default: stdout)",
    )

    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=DEFAULT_CACHE_DIR,
        help=f"Cache directory (default: {DEFAULT_CACHE_DIR})",
    )

    parser.add_argument(
        "--ttl",
        type=int,
        default=DEFAULT_TTL,
        help=f"Cache TTL in seconds (default: {DEFAULT_TTL})",
    )

    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable verbose logging to stderr"
    )

    # Authentication options
    parser.add_argument(
        "--instance-principals",
        action="store_true",
        help="Use instance principal authentication (for OCI VMs)",
    )

    parser.add_argument(
        "--config-file", type=str, help="Path to OCI config file (default: ~/.oci/config)"
    )

    parser.add_argument(
        "--profile",
        type=str,
        default="DEFAULT",
        help="OCI config profile to use (default: DEFAULT)",
    )

    args = parser.parse_args()

    # Read input config
    try:
        config = yaml.safe_load(args.input)
    except yaml.YAMLError as e:
        logger.error(f"Failed to parse YAML input: {e}")
        sys.exit(1)

    if not config:
        logger.error("Empty or invalid YAML input")
        sys.exit(1)

    # Initialize resolver with SDK
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.info("Using OCI SDK (parallel resolution enabled)")

    try:
        resolver = VaultResolver(
            cache_dir=args.cache_dir,
            ttl=args.ttl,
            verbose=args.verbose,
            use_instance_principals=args.instance_principals,
            config_file=args.config_file,
            config_profile=args.profile,
        )
    except Exception as e:
        logger.error(f"Failed to initialize resolver: {e}")
        sys.exit(1)

    # Resolve secrets
    resolved_config = resolver.resolve_config(config)

    # Write output
    try:
        yaml.dump(resolved_config, args.output, default_flow_style=False, sort_keys=False)
    except Exception as e:
        logger.error(f"Failed to write YAML output: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
