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
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union, cast

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
        """
        self.cache_dir = cache_dir
        self.ttl = ttl
        self.verbose = verbose
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Configure logging
        self.logger = logging.getLogger(__name__)
        if verbose:
            self.logger.setLevel(logging.DEBUG)
        else:
            self.logger.setLevel(logging.INFO)

        # Performance metrics
        self.metrics = {
            "secrets_fetched": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "stale_cache_used": 0,
            "total_fetch_time": 0.0,
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

    def log(self, message: str) -> None:
        """Log message if verbose mode is enabled."""
        self.logger.debug(message)

    def parse_vault_url(self, url: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Parse oci-vault:// URL into components.

        Returns: (secret_ocid, compartment_id, secret_name) or (None, None, None)
        """
        match = VAULT_URL_PATTERN.match(url)
        if not match:
            return None, None, None

        path = match.group(1)
        parts = path.split("/")

        # Format: oci-vault://secret-ocid
        if len(parts) == 1:
            if parts[0].startswith("ocid1.vaultsecret."):
                return parts[0], None, None
            else:
                # Treat as secret name in default compartment
                return None, None, parts[0]

        # Format: oci-vault://compartment-or-vault-id/secret-name
        elif len(parts) == 2:
            container_id, secret_name = parts
            if container_id.startswith("ocid1.compartment."):
                return None, container_id, secret_name
            elif container_id.startswith("ocid1.vault."):
                # For vault OCID, we need to list secrets in that vault
                return None, container_id, secret_name
            else:
                # Treat first part as compartment name
                return None, container_id, secret_name

        return None, None, None

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

    def fetch_secret_by_ocid(self, secret_ocid: str) -> Optional[str]:
        """Fetch secret value from OCI Vault by secret OCID using SDK."""
        start_time = time.time()
        try:
            self.log(f"Fetching secret: {secret_ocid}")

            # Direct SDK API call
            response = self.secrets_client.get_secret_bundle(secret_id=secret_ocid)

            # Extract and decode content
            content = response.data.secret_bundle_content.content
            decoded = base64.b64decode(content).decode("utf-8")

            fetch_time = time.time() - start_time
            self.metrics["secrets_fetched"] += 1
            self.metrics["total_fetch_time"] += fetch_time
            self.log(f"Successfully fetched: {secret_ocid} (took {fetch_time:.3f}s)")
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

    def resolve_secret(self, vault_url: str) -> Optional[str]:
        """
        Resolve a single oci-vault:// URL to its secret value.

        Uses caching and provides fallback to stale cache on errors.
        """
        cache_key = vault_url

        # Check cache first
        cached = self.get_cached_secret(cache_key)
        if cached:
            value, is_stale = cached
            if not is_stale:
                return value

        # Parse URL
        secret_ocid, compartment_id, secret_name = self.parse_vault_url(vault_url)

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

        # Fetch secret value
        try:
            secret_value = self.fetch_secret_by_ocid(secret_ocid)
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
