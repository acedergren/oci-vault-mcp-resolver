# OCI Vault MCP Resolver - Architecture Diagrams

**Version**: 2.0.0
**Last Updated**: 2026-01-08

This document provides visual representations of the system architecture, components, and data flows.

## Table of Contents

- [System Architecture](#system-architecture)
- [Component Architecture](#component-architecture)
- [Sequence Diagrams](#sequence-diagrams)
- [Data Flow](#data-flow)
- [Deployment Architecture](#deployment-architecture)

---

## System Architecture

### High-Level Overview

```mermaid
graph TB
    subgraph "AI Clients"
        Claude[Claude Code]
        Cursor[Cursor]
        Other[Other MCP Clients]
    end

    subgraph "Docker MCP Gateway"
        Gateway[MCP Gateway<br/>Port: stdio]
        CatalogServers[Catalog Servers<br/>docker, git, terraform]
    end

    subgraph "OCI Vault Integration"
        Wrapper[mcp_vault_proxy.py<br/>Service Dispatcher]
        Resolver[VaultResolver<br/>Secret Resolution]
        Config[resolver.yaml<br/>Configuration]
    end

    subgraph "OCI Cloud"
        Vault[OCI Vault<br/>AES-256-GCM]
        IAM[IAM Policies]
        Audit[Audit Logs]
    end

    subgraph "MCP Servers"
        GitHub[GitHub MCP<br/>npx @mcp/server-github]
        Postgres[PostgreSQL MCP<br/>npx @mcp/server-postgres]
        Custom[Custom MCP Servers]
    end

    subgraph "Local Cache"
        Cache[~/.cache/oci-vault-mcp/<br/>Encrypted Cache Files]
    end

    Claude --> Gateway
    Cursor --> Gateway
    Other --> Gateway

    Gateway --> CatalogServers
    Gateway --> Wrapper

    Wrapper --> Config
    Wrapper --> Resolver
    Wrapper --> GitHub
    Wrapper --> Postgres
    Wrapper --> Custom

    Resolver --> Vault
    Resolver --> Cache

    Vault --> IAM
    Vault --> Audit

    style Vault fill:#f96,stroke:#333,stroke-width:3px
    style Wrapper fill:#9cf,stroke:#333,stroke-width:2px
    style Resolver fill:#9cf,stroke:#333,stroke-width:2px
    style Gateway fill:#fc9,stroke:#333,stroke-width:2px
```

### Architecture Layers

```mermaid
graph LR
    subgraph "Layer 1: Client Layer"
        A1[AI Assistants<br/>Claude, Cursor, VS Code]
    end

    subgraph "Layer 2: Gateway Layer"
        B1[Docker MCP Gateway<br/>Server Discovery & Routing]
    end

    subgraph "Layer 3: Proxy Layer"
        C1[OCI Vault Proxy<br/>Secret Injection]
        C2[Config Management<br/>resolver.yaml]
    end

    subgraph "Layer 4: Resolution Layer"
        D1[VaultResolver<br/>Secret Fetching]
        D2[Circuit Breaker<br/>Fault Tolerance]
        D3[Cache Layer<br/>Performance]
    end

    subgraph "Layer 5: Cloud Layer"
        E1[OCI Vault API<br/>Secret Storage]
        E2[OCI IAM<br/>Authorization]
    end

    subgraph "Layer 6: Execution Layer"
        F1[MCP Servers<br/>GitHub, DB, APIs]
    end

    A1 --> B1
    B1 --> C1
    C1 --> C2
    C1 --> D1
    D1 --> D2
    D1 --> D3
    D1 --> E1
    E1 --> E2
    C1 --> F1

    style C1 fill:#9cf,stroke:#333,stroke-width:2px
    style D1 fill:#9cf,stroke:#333,stroke-width:2px
    style E1 fill:#f96,stroke:#333,stroke-width:3px
```

---

## Component Architecture

### VaultResolver Core Components

```mermaid
graph TB
    subgraph "VaultResolver Class"
        Init[__init__<br/>Initialization]
        FromConfig[from_config<br/>Config Loader]

        subgraph "Secret Resolution"
            Resolve[resolve_secret<br/>Main Entry Point]
            Parse[parse_vault_url<br/>URL Parser]
            FetchOCID[fetch_secret_by_ocid<br/>OCID Resolution]
            FindName[find_secret_by_name<br/>Name Resolution]
        end

        subgraph "Caching System"
            GetCache[get_cached_secret<br/>Cache Retrieval]
            SetCache[cache_secret<br/>Cache Storage]
            Stale[_try_stale_cache_fallback<br/>Stale Cache]
        end

        subgraph "Fault Tolerance"
            Retry[_fetch_secret_with_retry<br/>Retry Logic]
            CB[Circuit Breaker<br/>Failure Detection]
        end

        subgraph "Parallel Resolution"
            Parallel[fetch_secrets_parallel<br/>ThreadPool Executor]
            ConfigResolve[resolve_config<br/>Config Tree Walker]
        end
    end

    subgraph "OCI SDK"
        SecretsClient[SecretsClient<br/>Secrets Retrieval]
        VaultsClient[VaultsClient<br/>Secret Listing]
    end

    FromConfig --> Init
    Init --> Resolve

    Resolve --> Parse
    Parse --> FetchOCID
    Parse --> FindName

    FetchOCID --> GetCache
    GetCache --> Retry
    Retry --> CB
    CB --> SecretsClient
    SecretsClient --> SetCache

    FindName --> VaultsClient
    VaultsClient --> FetchOCID

    Resolve --> Stale

    Parallel --> Resolve
    ConfigResolve --> Parallel

    style Resolve fill:#9cf,stroke:#333,stroke-width:2px
    style CB fill:#fc9,stroke:#333,stroke-width:2px
    style GetCache fill:#cfc,stroke:#333,stroke-width:2px
```

### MCP Vault Proxy Components

```mermaid
graph TB
    subgraph "mcp_vault_proxy.py"
        Main[main<br/>Entry Point]

        subgraph "Configuration"
            LoadConfig[load_config<br/>YAML Loader]
            EnvOverride[Environment Overrides<br/>OCI_VAULT_*]
        end

        subgraph "Service Dispatch"
            GetCommand[get_service_command<br/>Service Lookup]
            DefaultCommands[DEFAULT_SERVICE_COMMANDS<br/>13+ Services]
        end

        subgraph "Secret Resolution"
            ResolveSecrets[resolve_secrets<br/>Bulk Resolution]
            VaultResolver[VaultResolver<br/>Core Library]
        end

        subgraph "Execution"
            Execute[execute_mcp_server<br/>subprocess.run]
            EnvInject[Environment Injection<br/>Set Env Vars]
        end
    end

    Main --> LoadConfig
    Main --> GetCommand
    Main --> ResolveSecrets
    Main --> Execute

    LoadConfig --> EnvOverride
    EnvOverride --> ResolveSecrets

    GetCommand --> DefaultCommands

    ResolveSecrets --> VaultResolver
    VaultResolver --> EnvInject
    EnvInject --> Execute

    style Main fill:#9cf,stroke:#333,stroke-width:2px
    style VaultResolver fill:#f96,stroke:#333,stroke-width:2px
    style Execute fill:#cfc,stroke:#333,stroke-width:2px
```

---

## Sequence Diagrams

### Secret Resolution Flow

```mermaid
sequenceDiagram
    participant Client as AI Client
    participant Gateway as MCP Gateway
    participant Wrapper as Vault Proxy
    participant Config as resolver.yaml
    participant Cache as Local Cache
    participant Vault as OCI Vault
    participant Server as MCP Server

    Client->>Gateway: Connect to MCP Gateway
    Gateway->>Wrapper: Execute mcp_vault_proxy.py<br/>--service github

    activate Wrapper
    Wrapper->>Config: Load configuration
    Config-->>Wrapper: Vault credentials<br/>Secret mappings

    Wrapper->>Wrapper: Create VaultResolver

    loop For each secret
        Wrapper->>Cache: Check cached secret
        alt Cache Hit (TTL valid)
            Cache-->>Wrapper: Return cached value
        else Cache Miss or Expired
            Wrapper->>Vault: Fetch secret<br/>(with retry + circuit breaker)
            Vault-->>Wrapper: Encrypted secret
            Wrapper->>Wrapper: Decrypt secret
            Wrapper->>Cache: Store in cache<br/>(TTL = 3600s)
        end
    end

    Wrapper->>Wrapper: Build environment variables<br/>GITHUB_PERSONAL_ACCESS_TOKEN=***

    Wrapper->>Server: Execute npx @mcp/server-github<br/>with injected secrets
    activate Server
    Server-->>Gateway: MCP Server ready<br/>(tools available)
    deactivate Server
    deactivate Wrapper

    Gateway-->>Client: GitHub tools available<br/>with vault credentials
```

### Circuit Breaker State Transitions

```mermaid
stateDiagram-v2
    [*] --> CLOSED: Initialize

    CLOSED --> OPEN: Threshold failures reached<br/>(5 consecutive errors)
    CLOSED --> CLOSED: Successful resolution<br/>(reset failure count)

    OPEN --> HALF_OPEN: Timeout elapsed<br/>(60 seconds)
    OPEN --> OPEN: Request blocked<br/>(return cached value)

    HALF_OPEN --> CLOSED: Test request succeeds<br/>(resume normal operation)
    HALF_OPEN --> OPEN: Test request fails<br/>(extend timeout)

    note right of CLOSED
        Normal operation
        Make vault API calls
        Track failures
    end note

    note right of OPEN
        Reject requests
        Use cached values
        Wait for timeout
    end note

    note right of HALF_OPEN
        Test single request
        Decide next state
    end note
```

### Parallel Secret Resolution

```mermaid
sequenceDiagram
    participant Wrapper as Vault Proxy
    participant Executor as ThreadPoolExecutor
    participant Worker1 as Worker Thread 1
    participant Worker2 as Worker Thread 2
    participant Worker3 as Worker Thread 3
    participant Vault as OCI Vault

    Wrapper->>Executor: Submit 3 secret resolutions

    par Parallel Resolution
        Executor->>Worker1: Resolve mcp-github-token
        Worker1->>Vault: Fetch secret
        Vault-->>Worker1: Secret value
        Worker1-->>Executor: Result 1
    and
        Executor->>Worker2: Resolve mcp-anthropic-key
        Worker2->>Vault: Fetch secret
        Vault-->>Worker2: Secret value
        Worker2-->>Executor: Result 2
    and
        Executor->>Worker3: Resolve mcp-postgres-password
        Worker3->>Vault: Fetch secret
        Vault-->>Worker3: Secret value
        Worker3-->>Executor: Result 3
    end

    Executor-->>Wrapper: All results collected<br/>(3x faster than sequential)

    note over Executor: max_workers=5<br/>Up to 5 concurrent resolutions
```

---

## Data Flow

### Configuration Loading and Merging

```mermaid
graph TB
    subgraph "Config Sources (Priority Order)"
        CLI[Command-line Args<br/>--config /path/to/resolver.yaml]
        EnvVars[Environment Variables<br/>OCI_VAULT_ID, OCI_REGION]
        UserConfig[User Config<br/>~/.config/oci-vault-mcp/resolver.yaml]
        SystemConfig[System Config<br/>/etc/oci-vault-mcp/resolver.yaml]
        LocalConfig[Local Config<br/>./resolver.yaml]
        ExampleConfig[Example Config<br/>config/resolver.yaml.example]
    end

    subgraph "Config Merging"
        Merge[Deep Merge Algorithm<br/>Override lower priority]
    end

    subgraph "Final Configuration"
        Final[Merged Config<br/>Applied to VaultResolver]
    end

    CLI --> Merge
    EnvVars --> Merge
    UserConfig --> Merge
    SystemConfig --> Merge
    LocalConfig --> Merge
    ExampleConfig --> Merge

    Merge --> Final

    style CLI fill:#f96,stroke:#333,stroke-width:2px
    style EnvVars fill:#fc9,stroke:#333,stroke-width:2px
    style Final fill:#9cf,stroke:#333,stroke-width:2px
```

### Secret Resolution Data Flow

```mermaid
graph LR
    subgraph "Input"
        A[Secret Reference<br/>mcp-github-token OR<br/>oci-vault://xxx OR<br/>ocid1.vaultsecret...]
    end

    subgraph "URL Parsing"
        B{Parse<br/>Format}
        B1[Secret Name<br/>+compartment_id]
        B2[Vault URL<br/>oci-vault://...]
        B3[Secret OCID<br/>ocid1.vaultsecret...]
    end

    subgraph "Resolution Strategy"
        C{Resolution<br/>Method}
        C1[Find by Name<br/>list_secrets]
        C2[Extract OCID<br/>parse URL]
        C3[Direct OCID<br/>use as-is]
    end

    subgraph "Secret Fetching"
        D{Cache<br/>Check}
        D1[Cache Hit<br/>return value]
        D2[Cache Miss<br/>fetch from vault]
    end

    subgraph "Vault API"
        E[Fetch Secret Bundle<br/>get_secret_bundle]
        F[Decrypt Secret<br/>Base64 decode]
    end

    subgraph "Caching"
        G[Store in Cache<br/>~/.cache/oci-vault-mcp/]
    end

    subgraph "Output"
        H[Decrypted Secret Value<br/>Environment Variable]
    end

    A --> B
    B --> B1
    B --> B2
    B --> B3

    B1 --> C1
    B2 --> C2
    B3 --> C3

    C1 --> D
    C2 --> D
    C3 --> D

    D --> D1
    D --> D2

    D1 --> H
    D2 --> E
    E --> F
    F --> G
    G --> H

    style A fill:#fc9,stroke:#333,stroke-width:2px
    style E fill:#f96,stroke:#333,stroke-width:2px
    style H fill:#9cf,stroke:#333,stroke-width:2px
```

---

## Deployment Architecture

### Docker MCP Gateway Deployment

```mermaid
graph TB
    subgraph "Remote SSH Server (OCI VM)"
        subgraph "User Space"
            Gateway[Docker MCP Gateway<br/>docker mcp gateway run]
            Config[~/.docker/mcp/config.yaml<br/>Custom Server Configs]
        end

        subgraph "System Space"
            Wrapper[/usr/local/bin/<br/>mcp_vault_proxy.py]
            SysConfig[/etc/oci-vault-mcp/<br/>resolver.yaml]
        end

        subgraph "Cache"
            Cache[~/.cache/oci-vault-mcp/<br/>Encrypted Cache Files]
        end

        subgraph "OCI Config"
            OCIConfig[~/.oci/config<br/>API Keys & Profiles]
        end
    end

    subgraph "OCI Cloud (eu-frankfurt-1)"
        Vault[OCI Vault<br/>AC-vault]
        Secrets[Secrets<br/>mcp-github-token<br/>mcp-anthropic-key]
    end

    subgraph "Docker Catalog Servers"
        CatalogServers[11 Catalog Servers<br/>git, terraform, context7, etc.]
    end

    Gateway --> Config
    Gateway --> CatalogServers
    Config --> Wrapper
    Wrapper --> SysConfig
    Wrapper --> OCIConfig
    Wrapper --> Cache
    Wrapper --> Vault
    Vault --> Secrets

    style Gateway fill:#fc9,stroke:#333,stroke-width:2px
    style Wrapper fill:#9cf,stroke:#333,stroke-width:2px
    style Vault fill:#f96,stroke:#333,stroke-width:3px
```

### Multi-Environment Deployment

```mermaid
graph TB
    subgraph "Development Environment"
        DevGateway[MCP Gateway]
        DevConfig[resolver.yaml<br/>compartment: dev<br/>secrets: *-dev]
        DevVault[OCI Vault<br/>Dev Compartment]

        DevGateway --> DevConfig
        DevConfig --> DevVault
    end

    subgraph "Staging Environment"
        StageGateway[MCP Gateway]
        StageConfig[resolver.yaml<br/>compartment: staging<br/>secrets: *-staging]
        StageVault[OCI Vault<br/>Staging Compartment]

        StageGateway --> StageConfig
        StageConfig --> StageVault
    end

    subgraph "Production Environment"
        ProdGateway[MCP Gateway]
        ProdConfig[resolver.yaml<br/>compartment: production<br/>secrets: *-prod]
        ProdVault[OCI Vault<br/>Production Compartment]

        ProdGateway --> ProdConfig
        ProdConfig --> ProdVault
    end

    style DevVault fill:#cfc,stroke:#333,stroke-width:2px
    style StageVault fill:#fc9,stroke:#333,stroke-width:2px
    style ProdVault fill:#f96,stroke:#333,stroke-width:3px
```

### Kubernetes Deployment (Future)

```mermaid
graph TB
    subgraph "Kubernetes Cluster"
        subgraph "Namespace: mcp-gateway"
            Gateway[Gateway Pod<br/>docker-mcp-gateway]
            Wrapper[Sidecar: Vault Proxy<br/>mcp_vault_proxy]
        end

        subgraph "ConfigMaps"
            Config[resolver-config<br/>resolver.yaml]
            Secrets[wallet-secret<br/>OCI Wallet (base64)]
        end

        subgraph "Service"
            Service[LoadBalancer<br/>External Access]
        end
    end

    subgraph "OCI Cloud"
        Vault[OCI Vault<br/>Secrets]
        IAM[IAM Policies<br/>Workload Identity]
    end

    Service --> Gateway
    Gateway --> Wrapper
    Wrapper --> Config
    Wrapper --> Secrets
    Wrapper --> Vault
    Vault --> IAM

    style Gateway fill:#fc9,stroke:#333,stroke-width:2px
    style Wrapper fill:#9cf,stroke:#333,stroke-width:2px
    style Vault fill:#f96,stroke:#333,stroke-width:3px
```

---

## Network Architecture

### Communication Paths

```mermaid
graph LR
    subgraph "Local Machine"
        Client[AI Client<br/>Claude Code]
    end

    subgraph "MCP Gateway Host"
        Gateway[Docker MCP<br/>Gateway]
        Proxy[Vault Proxy]
    end

    subgraph "OCI Cloud (mTLS)"
        VaultAPI[Vault API<br/>TLS 1.2+]
    end

    subgraph "NPM Registry"
        NPM[npm/npx<br/>MCP Servers]
    end

    Client -->|stdio| Gateway
    Gateway -->|subprocess| Proxy
    Proxy -->|HTTPS<br/>mTLS| VaultAPI
    Proxy -->|HTTPS| NPM

    style VaultAPI fill:#f96,stroke:#333,stroke-width:3px
```

---

## Related Documentation

- [API Documentation](API_DOCUMENTATION.md) - Complete API reference
- [User Guide](USER_GUIDE.md) - Setup and usage tutorials
- [Security Architecture](SECURITY.md) - Security design and best practices
- [Deployment Guide](DEPLOYMENT.md) - Production deployment strategies
