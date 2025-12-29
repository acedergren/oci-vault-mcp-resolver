# Architecture Documentation

## System Overview

The OCI Vault MCP Resolver is a secrets management integration layer that sits between Docker MCP Gateway and Oracle Cloud Infrastructure Vault, providing transparent secret resolution with caching and graceful degradation.

## Architecture Diagram

```mermaid
graph TB
    subgraph "User Environment"
        User[User/CI-CD]
        MCPConfig[MCP Config YAML]
    end

    subgraph "Resolver Layer"
        Wrapper[mcp-with-vault<br/>Bash Wrapper]
        Resolver[oci_vault_resolver.py<br/>Python Core]
        Cache[Local Cache<br/>~/.cache/oci-vault-mcp]
    end

    subgraph "OCI Cloud"
        Vault[OCI Vault Service]
        Secrets[Encrypted Secrets]
        IAM[IAM Authentication]
    end

    subgraph "MCP Gateway"
        Gateway[Docker MCP Gateway]
        Servers[MCP Servers]
    end

    User --> Wrapper
    Wrapper --> Resolver
    MCPConfig --> Resolver
    Resolver --> Cache
    Resolver --> Vault
    Vault --> IAM
    Vault --> Secrets
    Resolver --> Gateway
    Gateway --> Servers

    style Resolver fill:#4a9eff,stroke:#333,stroke-width:2px
    style Cache fill:#ffa500,stroke:#333,stroke-width:2px
    style Vault fill:#f4511e,stroke:#333,stroke-width:2px
    style Gateway fill:#66bb6a,stroke:#333,stroke-width:2px
```

## Component Architecture

### 1. Core Resolver (oci_vault_resolver.py)

**Responsibility**: Secret resolution, caching, and OCI Vault integration

```mermaid
classDiagram
    class VaultResolver {
        -cache_dir: Path
        -ttl: int
        -verbose: bool
        +resolve_config(config: Dict) Dict
        +resolve_secret(vault_url: str) str
        -fetch_secret_by_ocid(secret_ocid: str) str
        -find_secret_by_name(compartment_id: str, secret_name: str) str
        -get_cached_secret(cache_key: str) Optional~Tuple~
        -cache_secret(cache_key: str, secret_value: str) void
    }

    class URLParser {
        +parse_vault_url(url: str) Tuple
    }

    class CacheManager {
        +get_cache_path(cache_key: str) Path
        +get_cached_secret(cache_key: str) Optional
        +cache_secret(cache_key: str, value: str) void
    }

    class OCIClient {
        +fetch_secret_by_ocid(ocid: str) str
        +find_secret_by_name(compartment: str, name: str) str
    }

    VaultResolver --> URLParser
    VaultResolver --> CacheManager
    VaultResolver --> OCIClient
```

### 2. Wrapper Script (mcp-with-vault)

**Responsibility**: User-friendly CLI interface and workflow orchestration

**Flow**:
```mermaid
sequenceDiagram
    participant User
    participant Wrapper as mcp-with-vault
    participant Docker as Docker MCP CLI
    participant Resolver as Python Resolver
    participant Cache
    participant Vault as OCI Vault

    User->>Wrapper: ./mcp-with-vault
    Wrapper->>Docker: Read current config
    Docker-->>Wrapper: YAML config
    Wrapper->>Resolver: Resolve secrets
    Resolver->>Cache: Check cache
    alt Cache Hit
        Cache-->>Resolver: Cached value
    else Cache Miss
        Resolver->>Vault: Fetch secret
        Vault-->>Resolver: Secret value
        Resolver->>Cache: Store in cache
    end
    Resolver-->>Wrapper: Resolved config
    Wrapper->>Docker: Write resolved config
    Docker-->>Wrapper: Success
    Wrapper-->>User: Complete
```

### 3. Cache Layer

**Responsibility**: Performance optimization and availability

**Structure**:
```
~/.cache/oci-vault-mcp/
├── 7a8b9c0d1e2f3g4h.json  # Hashed cache key
│   ├── value: "secret-value"
│   ├── cached_at: 1735480000
│   └── cache_key: "oci-vault://..."
└── ...
```

**Cache Strategy**:
```mermaid
stateDiagram-v2
    [*] --> CheckCache
    CheckCache --> CacheHit: Found
    CheckCache --> CacheMiss: Not Found

    CacheHit --> CheckAge
    CheckAge --> ReturnCached: Fresh (age < TTL)
    CheckAge --> FetchVault: Stale (age >= TTL)

    CacheMiss --> FetchVault

    FetchVault --> Success: Fetch OK
    FetchVault --> FallbackStale: Fetch Failed

    Success --> UpdateCache
    UpdateCache --> ReturnValue

    FallbackStale --> ReturnStale: Use stale cache
    FallbackStale --> Error: No cache available

    ReturnCached --> [*]
    ReturnValue --> [*]
    ReturnStale --> [*]
    Error --> [*]
```

## Data Flow

### Secret Resolution Flow

```mermaid
flowchart TD
    Start([Config with oci-vault:// refs]) --> Parse[Parse YAML Config]
    Parse --> Find[Find all vault references]
    Find --> Loop{For each reference}

    Loop --> CheckCache{Check Cache}
    CheckCache -->|Hit + Fresh| UseCached[Use Cached Value]
    CheckCache -->|Hit + Stale| AttemptFetch[Attempt Fresh Fetch]
    CheckCache -->|Miss| Fetch[Fetch from Vault]

    AttemptFetch -->|Success| UpdateCache[Update Cache]
    AttemptFetch -->|Failure| WarnStale[Warn: Using Stale]

    Fetch --> ParseURL[Parse Vault URL]
    ParseURL --> DirectOCID{Direct OCID?}

    DirectOCID -->|Yes| FetchByOCID[Fetch by OCID]
    DirectOCID -->|No| LookupName[Lookup by Name]

    LookupName --> ListSecrets[List Secrets in Compartment]
    ListSecrets --> FindOCID[Find Matching OCID]
    FindOCID --> FetchByOCID

    FetchByOCID --> Decode[Base64 Decode]
    Decode --> UpdateCache

    UpdateCache --> Replace[Replace in Config]
    UseCached --> Replace
    WarnStale --> Replace

    Replace --> Loop
    Loop -->|More refs| CheckCache
    Loop -->|Done| Output[Output Resolved Config]
    Output --> End([Resolved YAML])
```

## URL Format Handling

```mermaid
graph LR
    URL[oci-vault:// URL] --> Parser{Parse URL}

    Parser -->|Format 1| OCID[ocid1.vaultsecret...]
    Parser -->|Format 2| CompName[compartment-id/name]
    Parser -->|Format 3| VaultName[vault-id/name]

    OCID --> FetchDirect[Direct Fetch<br/>1 API call]
    CompName --> ListComp[List in Compartment<br/>2 API calls]
    VaultName --> ListVault[List in Vault<br/>2 API calls]

    FetchDirect --> Result[Secret Value]
    ListComp --> Result
    ListVault --> Result

    style OCID fill:#90ee90
    style CompName fill:#87ceeb
    style VaultName fill:#dda0dd
```

## Security Architecture

### Authentication Flow

```mermaid
sequenceDiagram
    participant Resolver
    participant OCICLI as OCI CLI
    participant OCIConfig as ~/.oci/config
    participant IAM as OCI IAM
    participant Vault as OCI Vault

    Resolver->>OCICLI: Execute oci command
    OCICLI->>OCIConfig: Read credentials
    OCIConfig-->>OCICLI: API key / config
    OCICLI->>IAM: Authenticate
    IAM-->>OCICLI: Session token
    OCICLI->>Vault: Request secret
    Vault->>IAM: Verify permissions
    IAM-->>Vault: Authorized
    Vault-->>OCICLI: Encrypted secret
    OCICLI->>OCICLI: Decrypt (client-side)
    OCICLI-->>Resolver: Plain-text secret
```

### Security Boundaries

```mermaid
graph TB
    subgraph "Secure Zone - OCI Cloud"
        Vault[OCI Vault<br/>Encrypted at Rest]
        KMS[KMS Encryption Keys]
        IAM[IAM Policies]
    end

    subgraph "Trusted Zone - User Machine"
        Resolver[Resolver Process]
        Cache[Cache Files<br/>chmod 0600]
        OCIConfig[~/.oci/config<br/>API Keys]
    end

    subgraph "Application Zone"
        Gateway[MCP Gateway<br/>Resolved Secrets]
    end

    Vault -.->|Encrypted| KMS
    IAM -.->|Controls| Vault
    OCIConfig -.->|Auth| Vault
    Resolver -->|Fetch| Vault
    Resolver -->|Write 0600| Cache
    Resolver -->|Inject| Gateway

    style Vault fill:#f4511e,stroke:#b71c1c,stroke-width:3px
    style Cache fill:#ffa500,stroke:#e65100,stroke-width:2px
    style Gateway fill:#66bb6a,stroke:#2e7d32,stroke-width:2px
```

## Performance Characteristics

### Latency Profile

```mermaid
gantt
    title Secret Resolution Latency
    dateFormat X
    axisFormat %L ms

    section Direct OCID (Cache Hit)
    Cache Read: 0, 1

    section Direct OCID (Cache Miss)
    OCI API Call: 0, 500
    Base64 Decode: 500, 510
    Cache Write: 510, 515

    section Compartment+Name (Cache Miss)
    List Secrets API: 0, 400
    Parse Results: 400, 410
    Fetch Secret API: 410, 910
    Base64 Decode: 910, 920
    Cache Write: 920, 925
```

### Scaling Characteristics

| Metric | Cache Hit | Cache Miss (OCID) | Cache Miss (Name) |
|--------|-----------|-------------------|-------------------|
| **Latency** | ~0.1ms | ~500ms | ~900ms |
| **API Calls** | 0 | 1 | 2 |
| **Network I/O** | 0 KB | ~2 KB | ~4 KB |
| **CPU** | Minimal | Minimal | Minimal |
| **Throughput** | 10,000/s | 2/s | 1/s |

## Deployment Patterns

### Pattern 1: Local Development

```mermaid
graph LR
    Dev[Developer] -->|Edit Config| Config[mcp-config.yaml]
    Config -->|./mcp-with-vault| Resolver[Local Resolver]
    Resolver -->|Fetch| Vault[OCI Vault]
    Resolver -->|Apply| Gateway[Local Gateway]
    Gateway -->|Serve| Dev
```

### Pattern 2: CI/CD Pipeline

```mermaid
graph LR
    CI[CI Pipeline] -->|Checkout| Code[Code + Config]
    Code -->|Resolve| Resolver[Resolver in CI]
    Resolver -->|Fetch| Vault[OCI Vault]
    Resolver -->|Output| Manifest[Resolved Manifest]
    Manifest -->|Deploy| Cluster[K8s/Docker]
```

### Pattern 3: Server Startup

```mermaid
graph LR
    Boot[System Boot] -->|Systemd| Service[mcp-with-vault.service]
    Service -->|Resolve| Resolver[Resolver]
    Resolver -->|Fetch| Vault[OCI Vault]
    Resolver -->|Apply| Gateway[MCP Gateway]
    Gateway -->|Start| Servers[MCP Servers]
```

## Error Handling Strategy

```mermaid
graph TD
    Start[Resolve Secret] --> CheckCache{Cache Available?}

    CheckCache -->|Yes| CheckFresh{Cache Fresh?}
    CheckCache -->|No| FetchVault

    CheckFresh -->|Yes| ReturnCached[Return Cached]
    CheckFresh -->|No| FetchVault[Fetch from Vault]

    FetchVault --> Success{Fetch Success?}

    Success -->|Yes| UpdateCache[Update Cache]
    Success -->|No| HasStaleCache{Has Stale Cache?}

    HasStaleCache -->|Yes| WarnUser[Warn: Using Stale]
    HasStaleCache -->|No| ErrorOut[Error: Cannot Resolve]

    UpdateCache --> ReturnNew[Return New Value]
    WarnUser --> ReturnStale[Return Stale Value]

    ReturnCached --> End[Success]
    ReturnNew --> End
    ReturnStale --> End
    ErrorOut --> Fail[Failure]

    style ReturnCached fill:#90ee90
    style ReturnNew fill:#90ee90
    style ReturnStale fill:#ffa500
    style ErrorOut fill:#ff6b6b
```

## Integration Points

### Input: MCP Configuration

```yaml
servers:
  service:
    config:
      # Plain values pass through unchanged
      SERVICE_URL: https://api.example.com

      # Vault references are resolved
      API_KEY: oci-vault://compartment-id/secret-name
```

### Output: Resolved Configuration

```yaml
servers:
  service:
    config:
      SERVICE_URL: https://api.example.com
      API_KEY: actual-secret-value  # Resolved from vault
```

### Cache Format

```json
{
  "value": "actual-secret-value",
  "cached_at": 1735480000,
  "cache_key": "oci-vault://compartment-id/secret-name"
}
```

## Operational Characteristics

### Resource Usage

- **Memory**: ~50 MB (Python interpreter + dependencies)
- **Disk**: ~1 KB per cached secret
- **Network**: 1-2 HTTPS requests per cache miss
- **CPU**: Minimal (I/O bound)

### Availability Targets

| Scenario | Behavior | Availability |
|----------|----------|--------------|
| OCI Vault Available + Fresh Cache | Use vault | 99.99% |
| OCI Vault Available + No Cache | Use vault | 99.99% |
| OCI Vault Down + Fresh Cache | Use cache | 100% |
| OCI Vault Down + Stale Cache | Use stale (warn) | 100% |
| OCI Vault Down + No Cache | Fail | 0% |

### Monitoring Points

1. **Cache Hit Rate**: Should be >95% in steady state
2. **API Latency**: Should be <1s for vault calls
3. **Error Rate**: Should be <0.1%
4. **Stale Cache Usage**: Monitor for vault availability issues

## Future Enhancements

### Planned Features

1. **Parallel Resolution**: Resolve multiple secrets concurrently
2. **Secret Versioning**: Support specific secret versions
3. **Auto-Refresh**: Poll for secret updates
4. **Distributed Cache**: Redis/Memcached support
5. **Metrics Export**: Prometheus integration
6. **Secret Rotation Detection**: Automatic cache invalidation

### Extension Points

```python
# Custom cache backend
class RedisCacheBackend(CacheBackend):
    def get(self, key: str) -> Optional[str]:
        return redis_client.get(key)

    def set(self, key: str, value: str, ttl: int):
        redis_client.setex(key, ttl, value)

# Custom secret provider
class AWSSecretsProvider(SecretProvider):
    def fetch_secret(self, secret_id: str) -> str:
        return secrets_manager.get_secret_value(secret_id)
```

## References

- [OCI Vault Documentation](https://docs.oracle.com/en-us/iaas/Content/KeyManagement/home.htm)
- [Docker MCP Gateway](https://docs.docker.com/mcp/)
- [MCP Protocol Specification](https://spec.modelcontextprotocol.io/)
