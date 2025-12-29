#!/usr/bin/env python3
"""
OCI Vault MCP Resolver

Resolves oci-vault:// references in Docker MCP Gateway configuration
by fetching secrets from Oracle Cloud Infrastructure Vault.

Supported URL formats:
  - oci-vault://secret-ocid
  - oci-vault://compartment-ocid/secret-name
  - oci-vault://vault-ocid/secret-name

Features:
  - Caching with configurable TTL
  - Fallback to stale cache on errors
  - Recursive resolution of nested configs
  - Clear error messages
"""

import argparse
import base64
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import yaml


# Configuration
DEFAULT_CACHE_DIR = Path.home() / ".cache" / "oci-vault-mcp"
DEFAULT_TTL = 3600  # 1 hour in seconds
VAULT_URL_PATTERN = re.compile(r'^oci-vault://(.+)$')


class VaultResolver:
    """Resolves OCI Vault references in configuration."""

    def __init__(self, cache_dir: Path = DEFAULT_CACHE_DIR, ttl: int = DEFAULT_TTL, verbose: bool = False):
        self.cache_dir = cache_dir
        self.ttl = ttl
        self.verbose = verbose
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def log(self, message: str):
        """Log message if verbose mode is enabled."""
        if self.verbose:
            print(f"[DEBUG] {message}", file=sys.stderr)

    def parse_vault_url(self, url: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Parse oci-vault:// URL into components.

        Returns: (secret_ocid, compartment_id, secret_name) or (None, None, None)
        """
        match = VAULT_URL_PATTERN.match(url)
        if not match:
            return None, None, None

        path = match.group(1)
        parts = path.split('/')

        # Format: oci-vault://secret-ocid
        if len(parts) == 1:
            if parts[0].startswith('ocid1.vaultsecret.'):
                return parts[0], None, None
            else:
                # Treat as secret name in default compartment
                return None, None, parts[0]

        # Format: oci-vault://compartment-or-vault-id/secret-name
        elif len(parts) == 2:
            container_id, secret_name = parts
            if container_id.startswith('ocid1.compartment.'):
                return None, container_id, secret_name
            elif container_id.startswith('ocid1.vault.'):
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
            return None

        try:
            with open(cache_path, 'r') as f:
                cache_data = json.load(f)

            cached_at = cache_data.get('cached_at', 0)
            secret_value = cache_data.get('value')

            if not secret_value:
                return None

            age = time.time() - cached_at
            is_stale = age > self.ttl

            if is_stale:
                self.log(f"Cache stale: {cache_key} (age: {age:.0f}s)")
            else:
                self.log(f"Cache hit: {cache_key} (age: {age:.0f}s)")

            return secret_value, is_stale

        except Exception as e:
            self.log(f"Cache read error: {e}")
            return None

    def cache_secret(self, cache_key: str, secret_value: str):
        """Cache a secret value with timestamp."""
        cache_path = self.get_cache_path(cache_key)

        try:
            cache_data = {
                'value': secret_value,
                'cached_at': time.time(),
                'cache_key': cache_key
            }

            with open(cache_path, 'w') as f:
                json.dump(cache_data, f)

            # Secure the cache file
            cache_path.chmod(0o600)
            self.log(f"Cached: {cache_key}")

        except Exception as e:
            self.log(f"Cache write error: {e}")

    def fetch_secret_by_ocid(self, secret_ocid: str) -> Optional[str]:
        """Fetch secret value from OCI Vault by secret OCID."""
        try:
            self.log(f"Fetching secret: {secret_ocid}")

            cmd = [
                'oci', 'secrets', 'secret-bundle', 'get',
                '--secret-id', secret_ocid,
                '--query', 'data."secret-bundle-content".content',
                '--raw-output'
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )

            # Decode base64 content
            encoded_content = result.stdout.strip()
            if encoded_content:
                decoded = base64.b64decode(encoded_content).decode('utf-8')
                self.log(f"Successfully fetched: {secret_ocid}")
                return decoded

            return None

        except subprocess.CalledProcessError as e:
            self.log(f"OCI CLI error: {e.stderr}")
            return None
        except Exception as e:
            self.log(f"Error fetching secret: {e}")
            return None

    def find_secret_by_name(self, compartment_id: str, secret_name: str) -> Optional[str]:
        """Find secret OCID by name in a compartment."""
        try:
            self.log(f"Searching for secret '{secret_name}' in compartment {compartment_id}")

            cmd = [
                'oci', 'vault', 'secret', 'list',
                '--compartment-id', compartment_id,
                '--all',
                '--query', f'data[?"secret-name"==`{secret_name}`].id | [0]',
                '--raw-output'
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )

            secret_ocid = result.stdout.strip()
            if secret_ocid and secret_ocid != 'None':
                self.log(f"Found secret OCID: {secret_ocid}")
                return secret_ocid

            return None

        except subprocess.CalledProcessError as e:
            self.log(f"OCI CLI error: {e.stderr}")
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
            print(f"ERROR: Invalid vault URL format: {vault_url}", file=sys.stderr)
            return None

        # Resolve secret OCID if needed
        if not secret_ocid:
            if not compartment_id:
                print(f"ERROR: No compartment specified for secret name: {secret_name}", file=sys.stderr)
                return None

            secret_ocid = self.find_secret_by_name(compartment_id, secret_name)
            if not secret_ocid:
                print(f"ERROR: Secret not found: {secret_name} in compartment {compartment_id}", file=sys.stderr)

                # Fallback to stale cache if available
                if cached:
                    value, _ = cached
                    print(f"WARNING: Using stale cached value for {vault_url}", file=sys.stderr)
                    return value

                return None

        # Fetch secret value
        secret_value = self.fetch_secret_by_ocid(secret_ocid)

        if secret_value:
            # Cache the result
            self.cache_secret(cache_key, secret_value)
            return secret_value
        else:
            # Fallback to stale cache if available
            if cached:
                value, _ = cached
                print(f"WARNING: OCI Vault fetch failed, using stale cached value for {vault_url}", file=sys.stderr)
                return value

            print(f"ERROR: Failed to fetch secret: {vault_url}", file=sys.stderr)
            return None

    def find_vault_references(self, obj: Any, path: str = "") -> Dict[str, str]:
        """
        Recursively find all oci-vault:// references in a nested structure.

        Returns: dict mapping path to vault URL
        """
        references = {}

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

    def set_nested_value(self, obj: Any, path: str, value: str) -> Any:
        """Set a value in a nested structure using a path."""
        if not path:
            return value

        parts = re.split(r'\.|\[|\]', path)
        parts = [p for p in parts if p]  # Remove empty strings

        current = obj
        for i, part in enumerate(parts[:-1]):
            if part.isdigit():
                current = current[int(part)]
            else:
                if part not in current:
                    # Determine if next level should be list or dict
                    next_part = parts[i + 1]
                    current[part] = [] if next_part.isdigit() else {}
                current = current[part]

        last_part = parts[-1]
        if last_part.isdigit():
            current[int(last_part)] = value
        else:
            current[last_part] = value

        return obj

    def resolve_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Resolve all oci-vault:// references in a config dictionary.

        Returns: config with resolved secrets
        """
        # Find all vault references
        references = self.find_vault_references(config)

        if not references:
            self.log("No vault references found in config")
            return config

        print(f"Found {len(references)} vault reference(s) to resolve", file=sys.stderr)

        # Resolve each reference
        resolved_count = 0
        for path, vault_url in references.items():
            self.log(f"Resolving: {path} -> {vault_url}")
            secret_value = self.resolve_secret(vault_url)

            if secret_value is not None:
                self.set_nested_value(config, path, secret_value)
                resolved_count += 1
            else:
                print(f"ERROR: Failed to resolve {path}: {vault_url}", file=sys.stderr)

        print(f"Successfully resolved {resolved_count}/{len(references)} secret(s)", file=sys.stderr)

        if resolved_count < len(references):
            print(f"WARNING: {len(references) - resolved_count} secret(s) could not be resolved", file=sys.stderr)

        return config


def main():
    parser = argparse.ArgumentParser(
        description='Resolve OCI Vault references in Docker MCP Gateway configuration',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Read from stdin, resolve secrets, output to stdout
  docker mcp config read | python3 oci_vault_resolver.py

  # Resolve secrets and update gateway config
  docker mcp config read | python3 oci_vault_resolver.py | docker mcp config write

  # Use custom cache TTL (2 hours)
  docker mcp config read | python3 oci_vault_resolver.py --ttl 7200

  # Enable verbose logging
  docker mcp config read | python3 oci_vault_resolver.py --verbose

  # Clear cache
  rm -rf ~/.cache/oci-vault-mcp/
        """
    )

    parser.add_argument(
        '-i', '--input',
        type=argparse.FileType('r'),
        default=sys.stdin,
        help='Input YAML file (default: stdin)'
    )

    parser.add_argument(
        '-o', '--output',
        type=argparse.FileType('w'),
        default=sys.stdout,
        help='Output YAML file (default: stdout)'
    )

    parser.add_argument(
        '--cache-dir',
        type=Path,
        default=DEFAULT_CACHE_DIR,
        help=f'Cache directory (default: {DEFAULT_CACHE_DIR})'
    )

    parser.add_argument(
        '--ttl',
        type=int,
        default=DEFAULT_TTL,
        help=f'Cache TTL in seconds (default: {DEFAULT_TTL})'
    )

    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose logging to stderr'
    )

    args = parser.parse_args()

    # Read input config
    try:
        config = yaml.safe_load(args.input)
    except yaml.YAMLError as e:
        print(f"ERROR: Failed to parse YAML input: {e}", file=sys.stderr)
        sys.exit(1)

    if not config:
        print("ERROR: Empty or invalid YAML input", file=sys.stderr)
        sys.exit(1)

    # Resolve secrets
    resolver = VaultResolver(
        cache_dir=args.cache_dir,
        ttl=args.ttl,
        verbose=args.verbose
    )

    resolved_config = resolver.resolve_config(config)

    # Write output
    try:
        yaml.dump(resolved_config, args.output, default_flow_style=False, sort_keys=False)
    except Exception as e:
        print(f"ERROR: Failed to write YAML output: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
