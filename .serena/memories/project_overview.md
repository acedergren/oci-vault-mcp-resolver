# OCI Vault MCP Resolver - Project Overview

## Purpose
OCI Vault MCP Resolver is a secrets management integration layer that sits between Docker MCP Gateway and Oracle Cloud Infrastructure (OCI) Vault. It provides transparent secret resolution with caching and graceful degradation, allowing MCP configurations to reference secrets using `oci-vault://` URLs instead of hardcoding sensitive values.

## Key Features
- **Multiple URL Formats**: Supports direct secret OCID, compartment+name, and vault+name references
- **Performance Caching**: TTL-based caching (default 1 hour) with secure file permissions (0600)
- **Graceful Degradation**: Falls back to stale cache if OCI Vault is temporarily unavailable
- **Zero Configuration**: Works with existing OCI CLI setup

## Tech Stack
- **Language**: Python 3.8+
- **Dependencies**: PyYAML, OCI CLI
- **Shell**: Bash wrapper script for convenience
- **Platform**: Linux (designed for)

## URL Formats Supported
1. **Direct OCID**: `oci-vault://ocid1.vaultsecret.oc1.iad.xxx` (fastest, 1 API call)
2. **Compartment + Name**: `oci-vault://ocid1.compartment.oc1..xxx/secret-name` (2 API calls)
3. **Vault + Name**: `oci-vault://ocid1.vault.oc1.iad.xxx/secret-name` (2 API calls)

## Integration Pattern
```
MCP Config (with oci-vault:// refs)
    ↓
Resolver (checks cache → fetches from vault)
    ↓
Resolved Config (secrets injected)
    ↓
Docker MCP Gateway
```
