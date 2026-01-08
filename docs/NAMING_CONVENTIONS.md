# OCI Vault Secret Naming Conventions

**Version:** 1.0
**Last Updated:** 2026-01-08
**Status:** Standard

## Table of Contents

- [Overview](#overview)
- [Naming Pattern](#naming-pattern)
- [Pattern Components](#pattern-components)
- [Complete Examples](#complete-examples)
- [Environment Suffixes](#environment-suffixes)
- [Category-Specific Guidance](#category-specific-guidance)
- [Vault Organization](#vault-organization)
- [Secret Rotation Strategy](#secret-rotation-strategy)
- [Migration Guide](#migration-guide)
- [Best Practices](#best-practices)
- [Anti-Patterns](#anti-patterns)
- [Validation and Tooling](#validation-and-tooling)

## Overview

This document defines the authoritative naming convention for secrets stored in Oracle Cloud Infrastructure (OCI) Vault when used with the OCI Vault MCP Resolver. Consistent naming enables:

- **Discoverability** - Find related secrets easily
- **Access Control** - Apply IAM policies by naming patterns
- **Automation** - Script secret management operations
- **Clarity** - Understand secret purpose at a glance
- **Multi-Environment** - Support dev/staging/prod deployments

### Why Standardize Secret Names?

```yaml
# Bad: Inconsistent naming makes secrets hard to find
github-token: oci-vault://ocid1.compartment.oc1..xxx/GH_TOKEN
api_key: oci-vault://ocid1.compartment.oc1..xxx/openai-key-prod
db_pass: oci-vault://ocid1.compartment.oc1..xxx/postgres_password_production

# Good: Consistent naming is self-documenting
github_token: oci-vault://ocid1.compartment.oc1..xxx/mcp-github-token-prod
openai_key: oci-vault://ocid1.compartment.oc1..xxx/mcp-openai-api-key-prod
db_password: oci-vault://ocid1.compartment.oc1..xxx/mcp-postgres-password-prod
```

## Naming Pattern

### Standard Format

```
mcp-{service}-{type}[-{environment}]
```

### Pattern Components

| Component | Required | Description | Examples |
|-----------|----------|-------------|----------|
| `mcp-` | Yes | Prefix indicating MCP-related secret | `mcp-` |
| `{service}` | Yes | Service or tool name (lowercase, hyphenated) | `github`, `openai`, `postgres`, `slack` |
| `{type}` | Yes | Secret type (lowercase, hyphenated) | `api-key`, `token`, `password`, `webhook-secret` |
| `{environment}` | Optional | Deployment environment | `prod`, `dev`, `staging`, `test` |

### Separator Rules

- Use **hyphens** (`-`) between all components
- No underscores, spaces, or camelCase
- Lowercase only (OCI Vault is case-sensitive)
- ASCII characters only (no unicode)

### Length Constraints

- Minimum: 8 characters (`mcp-api-key`)
- Maximum: 100 characters (OCI Vault limit: 255)
- Recommended: 20-50 characters for readability

## Complete Examples

### Version Control & Code Hosting (20 examples)

| Secret Name | Description | Environment |
|-------------|-------------|-------------|
| `mcp-github-token` | GitHub Personal Access Token (PAT) | Generic |
| `mcp-github-token-prod` | GitHub PAT for production MCP Gateway | Production |
| `mcp-github-webhook-secret` | GitHub webhook signature verification | Generic |
| `mcp-github-app-private-key` | GitHub App private key (PEM format) | Generic |
| `mcp-github-oauth-client-secret` | GitHub OAuth app client secret | Generic |
| `mcp-gitlab-token` | GitLab Personal Access Token | Generic |
| `mcp-gitlab-token-dev` | GitLab PAT for development | Development |
| `mcp-gitlab-webhook-secret` | GitLab webhook verification token | Generic |
| `mcp-gitlab-runner-token` | GitLab CI runner registration token | Generic |
| `mcp-bitbucket-app-password` | Bitbucket app password | Generic |
| `mcp-bitbucket-token-prod` | Bitbucket access token for production | Production |
| `mcp-bitbucket-webhook-secret` | Bitbucket webhook signature key | Generic |
| `mcp-azure-devops-pat` | Azure DevOps Personal Access Token | Generic |
| `mcp-azure-devops-pat-prod` | Azure DevOps PAT for production | Production |
| `mcp-gitea-token` | Gitea access token | Generic |
| `mcp-codecommit-ssh-key` | AWS CodeCommit SSH private key | Generic |
| `mcp-sourcehut-token` | SourceHut API token | Generic |
| `mcp-forgejo-token` | Forgejo access token | Generic |
| `mcp-gogs-token` | Gogs access token | Generic |
| `mcp-perforce-ticket` | Perforce authentication ticket | Generic |

### AI & ML Services (15 examples)

| Secret Name | Description | Environment |
|-------------|-------------|-------------|
| `mcp-anthropic-api-key` | Anthropic Claude API key | Generic |
| `mcp-anthropic-api-key-prod` | Anthropic API key for production workloads | Production |
| `mcp-openai-api-key` | OpenAI API key (GPT-4, etc.) | Generic |
| `mcp-openai-api-key-dev` | OpenAI API key for development/testing | Development |
| `mcp-openai-org-id` | OpenAI organization ID | Generic |
| `mcp-google-ai-api-key` | Google AI (Gemini) API key | Generic |
| `mcp-google-ai-api-key-prod` | Google AI API key for production | Production |
| `mcp-cohere-api-key` | Cohere API key | Generic |
| `mcp-huggingface-token` | Hugging Face API token | Generic |
| `mcp-replicate-api-token` | Replicate API token | Generic |
| `mcp-stability-api-key` | Stability AI (Stable Diffusion) key | Generic |
| `mcp-elevenlabs-api-key` | ElevenLabs voice synthesis API key | Generic |
| `mcp-mistral-api-key` | Mistral AI API key | Generic |
| `mcp-perplexity-api-key` | Perplexity AI API key | Generic |
| `mcp-together-api-key` | Together AI API key | Generic |

### Databases (25 examples)

| Secret Name | Description | Environment |
|-------------|-------------|-------------|
| `mcp-postgres-password` | PostgreSQL database password | Generic |
| `mcp-postgres-password-prod` | PostgreSQL production database password | Production |
| `mcp-postgres-connection-string` | PostgreSQL full connection string | Generic |
| `mcp-postgres-admin-password` | PostgreSQL admin/superuser password | Generic |
| `mcp-postgres-readonly-password` | PostgreSQL read-only user password | Generic |
| `mcp-mysql-password` | MySQL database password | Generic |
| `mcp-mysql-password-dev` | MySQL development database password | Development |
| `mcp-mysql-root-password` | MySQL root password | Generic |
| `mcp-mysql-connection-string` | MySQL connection string | Generic |
| `mcp-mongodb-password` | MongoDB database password | Generic |
| `mcp-mongodb-password-prod` | MongoDB production password | Production |
| `mcp-mongodb-connection-string` | MongoDB connection URI | Generic |
| `mcp-mongodb-atlas-api-key` | MongoDB Atlas API key | Generic |
| `mcp-redis-password` | Redis authentication password | Generic |
| `mcp-redis-password-prod` | Redis production password | Production |
| `mcp-redis-connection-string` | Redis connection string | Generic |
| `mcp-oracle-password` | Oracle database password | Generic |
| `mcp-oracle-password-prod` | Oracle production database password | Production |
| `mcp-oracle-wallet-password` | Oracle Autonomous Database wallet password | Generic |
| `mcp-oracle-wallet-content` | Oracle wallet (base64-encoded PEM) | Generic |
| `mcp-cassandra-password` | Apache Cassandra password | Generic |
| `mcp-elasticsearch-password` | Elasticsearch password | Generic |
| `mcp-dynamodb-access-key` | AWS DynamoDB access key | Generic |
| `mcp-couchdb-password` | CouchDB admin password | Generic |
| `mcp-influxdb-token` | InfluxDB authentication token | Generic |

### Cloud Provider Credentials (30 examples)

| Secret Name | Description | Environment |
|-------------|-------------|-------------|
| `mcp-aws-access-key-id` | AWS access key ID | Generic |
| `mcp-aws-access-key-id-prod` | AWS access key ID for production | Production |
| `mcp-aws-secret-access-key` | AWS secret access key | Generic |
| `mcp-aws-secret-access-key-prod` | AWS secret access key for production | Production |
| `mcp-aws-session-token` | AWS temporary session token | Generic |
| `mcp-aws-ecr-password` | AWS ECR registry password | Generic |
| `mcp-aws-rds-master-password` | AWS RDS master password | Generic |
| `mcp-aws-secrets-manager-token` | AWS Secrets Manager access token | Generic |
| `mcp-gcp-service-account-key` | GCP service account JSON key | Generic |
| `mcp-gcp-service-account-key-prod` | GCP service account key for production | Production |
| `mcp-gcp-api-key` | GCP API key | Generic |
| `mcp-gcp-oauth-client-secret` | GCP OAuth client secret | Generic |
| `mcp-gcp-cloudsql-password` | GCP Cloud SQL password | Generic |
| `mcp-azure-client-secret` | Azure service principal secret | Generic |
| `mcp-azure-client-secret-prod` | Azure service principal secret for production | Production |
| `mcp-azure-subscription-id` | Azure subscription ID | Generic |
| `mcp-azure-tenant-id` | Azure tenant ID | Generic |
| `mcp-azure-storage-key` | Azure Storage account key | Generic |
| `mcp-azure-cosmosdb-key` | Azure Cosmos DB primary key | Generic |
| `mcp-oci-auth-token` | OCI authentication token | Generic |
| `mcp-oci-private-key` | OCI API signing private key | Generic |
| `mcp-oci-fingerprint` | OCI key fingerprint | Generic |
| `mcp-digitalocean-token` | DigitalOcean API token | Generic |
| `mcp-digitalocean-spaces-key` | DigitalOcean Spaces access key | Generic |
| `mcp-linode-token` | Linode API token | Generic |
| `mcp-cloudflare-api-token` | Cloudflare API token | Generic |
| `mcp-cloudflare-zone-id` | Cloudflare zone ID | Generic |
| `mcp-heroku-api-key` | Heroku API key | Generic |
| `mcp-vercel-token` | Vercel deployment token | Generic |
| `mcp-netlify-token` | Netlify personal access token | Generic |

### Communication & Collaboration (20 examples)

| Secret Name | Description | Environment |
|-------------|-------------|-------------|
| `mcp-slack-bot-token` | Slack bot user OAuth token | Generic |
| `mcp-slack-bot-token-prod` | Slack bot token for production workspace | Production |
| `mcp-slack-webhook-url` | Slack incoming webhook URL | Generic |
| `mcp-slack-signing-secret` | Slack request signing secret | Generic |
| `mcp-slack-app-token` | Slack app-level token | Generic |
| `mcp-discord-bot-token` | Discord bot token | Generic |
| `mcp-discord-bot-token-prod` | Discord bot token for production | Production |
| `mcp-discord-webhook-url` | Discord webhook URL | Generic |
| `mcp-discord-client-secret` | Discord OAuth client secret | Generic |
| `mcp-teams-webhook-url` | Microsoft Teams webhook URL | Generic |
| `mcp-teams-bot-password` | Microsoft Teams bot password | Generic |
| `mcp-telegram-bot-token` | Telegram bot API token | Generic |
| `mcp-telegram-webhook-secret` | Telegram webhook secret token | Generic |
| `mcp-twilio-auth-token` | Twilio authentication token | Generic |
| `mcp-twilio-account-sid` | Twilio account SID | Generic |
| `mcp-sendgrid-api-key` | SendGrid email API key | Generic |
| `mcp-mailgun-api-key` | Mailgun API key | Generic |
| `mcp-pagerduty-api-key` | PagerDuty REST API key | Generic |
| `mcp-opsgenie-api-key` | Opsgenie API key | Generic |
| `mcp-zoom-webhook-secret` | Zoom webhook verification token | Generic |

### Project Management & Development Tools (15 examples)

| Secret Name | Description | Environment |
|-------------|-------------|-------------|
| `mcp-jira-api-token` | Jira Cloud API token | Generic |
| `mcp-jira-api-token-prod` | Jira API token for production integration | Production |
| `mcp-jira-webhook-secret` | Jira webhook secret | Generic |
| `mcp-confluence-api-token` | Confluence API token | Generic |
| `mcp-trello-api-key` | Trello API key | Generic |
| `mcp-trello-token` | Trello user token | Generic |
| `mcp-asana-token` | Asana personal access token | Generic |
| `mcp-notion-integration-secret` | Notion integration secret | Generic |
| `mcp-linear-api-key` | Linear API key | Generic |
| `mcp-monday-api-token` | Monday.com API token | Generic |
| `mcp-clickup-api-token` | ClickUp API token | Generic |
| `mcp-shortcut-api-token` | Shortcut (formerly Clubhouse) token | Generic |
| `mcp-airtable-api-key` | Airtable API key | Generic |
| `mcp-basecamp-token` | Basecamp access token | Generic |
| `mcp-smartsheet-token` | Smartsheet access token | Generic |

### CI/CD & Deployment (15 examples)

| Secret Name | Description | Environment |
|-------------|-------------|-------------|
| `mcp-circleci-token` | CircleCI personal API token | Generic |
| `mcp-travis-token` | Travis CI API token | Generic |
| `mcp-jenkins-api-token` | Jenkins API token | Generic |
| `mcp-jenkins-webhook-secret` | Jenkins webhook verification secret | Generic |
| `mcp-teamcity-token` | TeamCity access token | Generic |
| `mcp-bamboo-token` | Bamboo API token | Generic |
| `mcp-drone-secret` | Drone CI server secret | Generic |
| `mcp-spinnaker-token` | Spinnaker API token | Generic |
| `mcp-argocd-token` | ArgoCD authentication token | Generic |
| `mcp-flux-token` | Flux CD token | Generic |
| `mcp-docker-hub-token` | Docker Hub access token | Generic |
| `mcp-docker-hub-password` | Docker Hub password | Generic |
| `mcp-gcr-service-key` | Google Container Registry service key | Generic |
| `mcp-quay-robot-token` | Quay.io robot account token | Generic |
| `mcp-artifactory-api-key` | JFrog Artifactory API key | Generic |

### Security & Monitoring (20 examples)

| Secret Name | Description | Environment |
|-------------|-------------|-------------|
| `mcp-sentry-dsn` | Sentry project DSN | Generic |
| `mcp-sentry-dsn-prod` | Sentry DSN for production environment | Production |
| `mcp-sentry-auth-token` | Sentry API authentication token | Generic |
| `mcp-datadog-api-key` | Datadog API key | Generic |
| `mcp-datadog-app-key` | Datadog application key | Generic |
| `mcp-newrelic-api-key` | New Relic API key | Generic |
| `mcp-newrelic-license-key` | New Relic license key | Generic |
| `mcp-grafana-api-key` | Grafana API key | Generic |
| `mcp-prometheus-basic-auth` | Prometheus basic auth credentials | Generic |
| `mcp-splunk-token` | Splunk HTTP Event Collector token | Generic |
| `mcp-sumologic-access-key` | Sumo Logic access key | Generic |
| `mcp-okta-api-token` | Okta API token | Generic |
| `mcp-auth0-client-secret` | Auth0 application client secret | Generic |
| `mcp-auth0-management-token` | Auth0 Management API token | Generic |
| `mcp-keycloak-client-secret` | Keycloak client secret | Generic |
| `mcp-vault-token` | HashiCorp Vault token | Generic |
| `mcp-1password-token` | 1Password Connect token | Generic |
| `mcp-lastpass-api-key` | LastPass Enterprise API key | Generic |
| `mcp-snyk-token` | Snyk API token | Generic |
| `mcp-sonarqube-token` | SonarQube authentication token | Generic |

### Generic & Utility Secrets (10 examples)

| Secret Name | Description | Environment |
|-------------|-------------|-------------|
| `mcp-jwt-secret` | JWT signing secret key | Generic |
| `mcp-jwt-secret-prod` | JWT secret for production tokens | Production |
| `mcp-encryption-key` | Symmetric encryption master key | Generic |
| `mcp-encryption-key-prod` | Production encryption master key | Production |
| `mcp-webhook-secret` | Generic webhook verification secret | Generic |
| `mcp-api-key` | Generic API key | Generic |
| `mcp-oauth-client-secret` | Generic OAuth client secret | Generic |
| `mcp-signing-key` | Generic cryptographic signing key | Generic |
| `mcp-session-secret` | Web session encryption secret | Generic |
| `mcp-csrf-token-secret` | CSRF token generation secret | Generic |

## Environment Suffixes

### Standard Environments

| Suffix | Environment | Use Case | Example |
|--------|-------------|----------|---------|
| `-prod` | Production | Live customer-facing services | `mcp-github-token-prod` |
| `-staging` | Staging | Pre-production testing | `mcp-postgres-password-staging` |
| `-dev` | Development | Developer workstations | `mcp-openai-api-key-dev` |
| `-test` | Testing | Automated test suites | `mcp-slack-webhook-url-test` |
| `-qa` | QA | Quality assurance environment | `mcp-mysql-password-qa` |
| `-uat` | UAT | User acceptance testing | `mcp-oracle-password-uat` |
| `-demo` | Demo | Sales demos and POCs | `mcp-anthropic-api-key-demo` |
| `-sandbox` | Sandbox | Experimental features | `mcp-aws-access-key-sandbox` |

### When to Use Environment Suffixes

**Use suffixes when:**
- Secret values differ between environments
- You need separate IAM policies per environment
- Rotation schedules differ by environment
- You want to prevent accidental prod/dev mixing

**Omit suffixes when:**
- Secret is environment-agnostic (e.g., `mcp-github-webhook-secret`)
- Only one environment exists
- Secret is shared across all environments (not recommended)

### Environment-Specific Compartments

**Recommended:** Use separate OCI compartments per environment:

```
tenancy/
├── mcp-secrets-prod/          # Production compartment
│   ├── mcp-github-token
│   ├── mcp-postgres-password
│   └── mcp-openai-api-key
│
├── mcp-secrets-staging/       # Staging compartment
│   ├── mcp-github-token
│   ├── mcp-postgres-password
│   └── mcp-openai-api-key
│
└── mcp-secrets-dev/           # Development compartment
    ├── mcp-github-token
    ├── mcp-postgres-password
    └── mcp-openai-api-key
```

**Benefits:**
- Simpler secret names (no `-prod` suffix needed)
- Stronger IAM isolation
- Easier audit compliance
- Clear separation of concerns

## Category-Specific Guidance

### Version Control Tokens

**Pattern:** `mcp-{platform}-{token-type}[-{environment}]`

```bash
# Personal Access Tokens (PATs)
mcp-github-token
mcp-gitlab-token
mcp-bitbucket-token

# Webhook secrets
mcp-github-webhook-secret
mcp-gitlab-webhook-secret

# App credentials
mcp-github-app-private-key
mcp-gitlab-runner-token
```

**IAM Policy Example:**
```
allow group developers to read secret-bundles in compartment mcp-secrets where target.secret.name='mcp-github-token-dev'
allow group cicd-runners to read secret-bundles in compartment mcp-secrets where target.secret.name starts-with 'mcp-github-'
```

### Database Credentials

**Pattern:** `mcp-{database}-{credential-type}[-{environment}]`

```bash
# Primary credentials
mcp-postgres-password
mcp-mysql-password
mcp-mongodb-connection-string

# Role-specific
mcp-postgres-admin-password
mcp-postgres-readonly-password
mcp-postgres-app-password

# Wallet/certificate
mcp-oracle-wallet-password
mcp-oracle-wallet-content
```

**Best Practices:**
- Use connection strings for complex configs
- Never use `root` in production secret names
- Include `-readonly` for read-only accounts

### AI Service Keys

**Pattern:** `mcp-{provider}-{credential-type}[-{environment}]`

```bash
# API keys
mcp-anthropic-api-key
mcp-openai-api-key
mcp-google-ai-api-key

# Organization identifiers
mcp-openai-org-id
mcp-anthropic-workspace-id
```

**Cost Management:**
- Use `-dev` suffix for test/free-tier keys
- Monitor usage via key names in cost reports
- Rotate `-prod` keys monthly

### Cloud Provider Credentials

**Pattern:** `mcp-{cloud}-{credential-type}[-{environment}]`

```bash
# AWS
mcp-aws-access-key-id
mcp-aws-secret-access-key
mcp-aws-session-token

# GCP
mcp-gcp-service-account-key
mcp-gcp-project-id

# Azure
mcp-azure-client-secret
mcp-azure-tenant-id
```

**Security Notes:**
- Prefer instance principals over static credentials
- Use time-limited tokens (`mcp-aws-session-token`)
- Store multi-line JSON as single secrets

### Webhook Secrets

**Pattern:** `mcp-{service}-webhook-secret[-{environment}]`

```bash
mcp-github-webhook-secret
mcp-gitlab-webhook-secret
mcp-slack-webhook-secret
mcp-stripe-webhook-secret
```

**Use Cases:**
- HMAC signature verification
- Payload authentication
- Replay attack prevention

## Vault Organization

### Compartment Strategy

**Option 1: By Environment (Recommended)**
```
└── tenancy
    ├── mcp-secrets-prod
    ├── mcp-secrets-staging
    └── mcp-secrets-dev
```

**Option 2: By Service Category**
```
└── tenancy
    ├── mcp-vcs-secrets       # Version control
    ├── mcp-database-secrets  # Databases
    ├── mcp-ai-secrets        # AI services
    └── mcp-cloud-secrets     # Cloud providers
```

**Option 3: Hybrid**
```
└── tenancy
    ├── mcp-prod-vcs
    ├── mcp-prod-databases
    ├── mcp-prod-ai
    ├── mcp-dev-all
    └── mcp-staging-all
```

### Tagging Strategy

Use OCI resource tags for metadata:

| Tag Key | Tag Value | Purpose |
|---------|-----------|---------|
| `Environment` | `prod`, `dev`, `staging` | Filter by environment |
| `Service` | `github`, `postgres`, `openai` | Group by service |
| `CostCenter` | `engineering`, `ml-team` | Chargeback/budgets |
| `RotationFrequency` | `30d`, `90d`, `never` | Rotation schedule |
| `Owner` | `platform-team`, `data-team` | Responsible team |
| `Compliance` | `gdpr`, `soc2`, `hipaa` | Regulatory requirements |

**Example:**
```bash
oci vault secret create \
  --compartment-id "ocid1.compartment.oc1..xxx" \
  --secret-name "mcp-github-token-prod" \
  --vault-id "ocid1.vault.oc1.iad.xxx" \
  --secret-content-content "ghp_xxxxx" \
  --freeform-tags '{"Environment":"prod","Service":"github","Owner":"platform-team","RotationFrequency":"30d"}'
```

### Multi-Tenant Architecture

For SaaS applications serving multiple customers:

**Pattern:** `mcp-{service}-{type}-{tenant-id}[-{environment}]`

```bash
# Single tenant per secret
mcp-postgres-password-acme-corp-prod
mcp-postgres-password-contoso-prod

# Shared infrastructure
mcp-postgres-admin-password-prod  # No tenant ID
mcp-encryption-master-key-prod    # Shared key
```

**Alternative:** Use separate compartments per tenant:
```
└── tenancy
    ├── tenant-acme-corp/
    │   ├── mcp-postgres-password
    │   └── mcp-api-key
    └── tenant-contoso/
        ├── mcp-postgres-password
        └── mcp-api-key
```

## Secret Rotation Strategy

### Rotation Frequency Guidelines

| Secret Type | Recommended Frequency | Automation |
|-------------|----------------------|------------|
| Production database passwords | 30 days | Manual |
| API keys (AI services) | 90 days | Manual |
| Cloud provider keys | 90 days | Manual |
| JWT signing secrets | 180 days | Manual |
| Webhook secrets | Never (unless compromised) | N/A |
| Development secrets | 180 days | Optional |

### Versioning During Rotation

OCI Vault supports secret versioning. When rotating:

1. **Create new version** (don't delete old secret)
2. **Test new version** in staging
3. **Deploy to production** with new version
4. **Monitor for 24-48 hours**
5. **Deactivate old version** (keep for rollback)

**Example workflow:**
```bash
# 1. Create new version
oci vault secret update-base64 \
  --secret-id "ocid1.vaultsecret.oc1.iad.xxx" \
  --secret-content-content "$(echo -n 'new-secret-value' | base64)"

# 2. Reference specific version in rollback scenario
# oci-vault://ocid1.vaultsecret.oc1.iad.xxx?version=1
```

### Rotation Tracking

Add a tag to track last rotation:

```bash
--freeform-tags '{"LastRotated":"2026-01-08","NextRotation":"2026-02-08"}'
```

### Automated Rotation (Future)

For services supporting automated rotation (AWS Secrets Manager style):

**Pattern:** `mcp-{service}-{type}-auto-rotate[-{environment}]`

```bash
mcp-postgres-password-auto-rotate-prod
mcp-mysql-password-auto-rotate-prod
```

## Migration Guide

### Migrating from Legacy Naming

**Step 1: Audit existing secrets**
```bash
# List all secrets in compartment
oci vault secret list \
  --compartment-id "ocid1.compartment.oc1..xxx" \
  --vault-id "ocid1.vault.oc1.iad.xxx" \
  --query 'data[].{"Name":"secret-name","ID":id}' \
  --output table
```

**Step 2: Create mapping table**
```csv
Legacy Name,New Name,Environment
gh_token,mcp-github-token-prod,prod
POSTGRES_PASS,mcp-postgres-password-prod,prod
openai_key,mcp-openai-api-key-prod,prod
```

**Step 3: Create new secrets with standard names**
```bash
# Get value from legacy secret
LEGACY_VALUE=$(oci secrets secret-bundle get \
  --secret-id "ocid1.vaultsecret.oc1.iad.legacy" \
  --query 'data."secret-bundle-content".content' \
  --raw-output | base64 -d)

# Create new secret with standard name
oci vault secret create-base64 \
  --compartment-id "ocid1.compartment.oc1..xxx" \
  --secret-name "mcp-github-token-prod" \
  --vault-id "ocid1.vault.oc1.iad.xxx" \
  --secret-content-content "$(echo -n "$LEGACY_VALUE" | base64)"
```

**Step 4: Update configurations**
```yaml
# Before
github_token: oci-vault://ocid1.compartment.oc1..xxx/gh_token

# After
github_token: oci-vault://ocid1.compartment.oc1..xxx/mcp-github-token-prod
```

**Step 5: Parallel run period (14-30 days)**
- Keep both old and new secrets active
- Monitor application logs for errors
- Gradually migrate services to new names

**Step 6: Deactivate legacy secrets**
```bash
oci vault secret schedule-secret-deletion \
  --secret-id "ocid1.vaultsecret.oc1.iad.legacy" \
  --time-of-deletion "2026-02-08T00:00:00Z"
```

### Common Migration Patterns

| Legacy Pattern | Standard Pattern | Notes |
|----------------|------------------|-------|
| `GH_TOKEN` | `mcp-github-token` | Remove env var style |
| `postgres_password_prod` | `mcp-postgres-password-prod` | Add `mcp-` prefix |
| `api-key-openai` | `mcp-openai-api-key` | Reorder components |
| `prod-github-token` | `mcp-github-token-prod` | Move env to suffix |
| `myapp-db-pass` | `mcp-postgres-password` | Use generic service name |

## Best Practices

### 1. Consistency Over Cleverness

```bash
# Bad: Creative but inconsistent
mcp-gh-pat-for-ci-prod
mcp-github-personal-access-token-production
mcp-GithubToken_PROD

# Good: Boring but predictable
mcp-github-token-prod
```

### 2. Use Descriptive Types

```bash
# Bad: Ambiguous
mcp-github-key
mcp-postgres-creds

# Good: Specific
mcp-github-token            # PAT
mcp-github-app-private-key  # App key
mcp-postgres-password       # Password
mcp-postgres-connection-string  # Full URI
```

### 3. Environment Suffix Consistency

```bash
# Bad: Mixed styles
mcp-github-token-production
mcp-postgres-password-prod
mcp-redis-pass-PROD

# Good: Consistent abbreviation
mcp-github-token-prod
mcp-postgres-password-prod
mcp-redis-password-prod
```

### 4. Avoid Redundancy

```bash
# Bad: Redundant words
mcp-secret-github-token-secret
mcp-password-postgres-password

# Good: Concise
mcp-github-token
mcp-postgres-password
```

### 5. Service Names Match Industry Standards

```bash
# Bad: Non-standard names
mcp-gh-token           # Use full name
mcp-aws-s3-key        # S3 is product, not service
mcp-chatgpt-key       # Use provider name

# Good: Standard service names
mcp-github-token
mcp-aws-access-key-id
mcp-openai-api-key
```

### 6. Multi-Word Services Use Hyphens

```bash
# Bad: Unclear boundaries
mcp-googleai-api-key
mcp-azure_devops_token

# Good: Clear separation
mcp-google-ai-api-key
mcp-azure-devops-token
```

### 7. Version Tracking in Tags, Not Names

```bash
# Bad: Version in name (creates new secret)
mcp-github-token-prod-v2
mcp-postgres-password-2026-01

# Good: Use OCI Vault versioning
mcp-github-token-prod  # Version 2 (latest)
# Tags: {"CreatedAt": "2026-01-08", "Version": "2"}
```

## Anti-Patterns

### 1. Application-Specific Prefixes

```bash
# Bad: Ties secret to one app
myapp-github-token
webapp-postgres-password

# Good: Reusable across apps
mcp-github-token
mcp-postgres-password
```

### 2. User-Specific Secrets

```bash
# Bad: Personal secrets in shared vault
mcp-github-token-john
mcp-postgres-password-mary

# Good: Service account or role-based
mcp-github-token-cicd
mcp-postgres-password-app
```

### 3. Encoding Metadata in Names

```bash
# Bad: Metadata belongs in tags
mcp-github-token-created-2026-01-08
mcp-postgres-password-rotate-monthly
mcp-openai-key-100-per-month-limit

# Good: Use tags for metadata
mcp-github-token-prod
# Tags: {"CreatedAt": "2026-01-08", "RotationFrequency": "30d", "CostLimit": "100"}
```

### 4. Overly Generic Names

```bash
# Bad: Too vague
mcp-token
mcp-key
mcp-secret

# Good: Specific
mcp-github-token
mcp-openai-api-key
mcp-jwt-secret
```

### 5. Including Values or Hints

```bash
# Bad: Hints about value
mcp-github-token-ghp-xyz
mcp-postgres-password-16-chars
mcp-api-key-starts-with-sk

# Good: No value hints
mcp-github-token-prod
mcp-postgres-password-prod
mcp-openai-api-key-prod
```

### 6. Mixed Conventions

```bash
# Bad: Inconsistent within project
mcp-github-token-prod
MCP_POSTGRES_PASSWORD_PROD
mcp.redis.password.prod

# Good: Pick one convention
mcp-github-token-prod
mcp-postgres-password-prod
mcp-redis-password-prod
```

## Validation and Tooling

### Regex Pattern Validator

```regex
^mcp-[a-z0-9]+(-[a-z0-9]+)*-(token|password|key|secret|api-key|webhook-secret|connection-string|private-key|client-secret|access-key|dsn|url|id)(-[a-z]+)?$
```

**Valid examples:**
- `mcp-github-token` ✅
- `mcp-postgres-password-prod` ✅
- `mcp-google-ai-api-key-dev` ✅

**Invalid examples:**
- `github-token` ❌ (missing `mcp-` prefix)
- `mcp-GitHub-token` ❌ (uppercase not allowed)
- `mcp_github_token` ❌ (underscores not allowed)
- `mcp-token` ❌ (too generic, missing service)

### Bash Validation Script

```bash
#!/bin/bash
# validate-secret-name.sh

validate_secret_name() {
  local name="$1"
  local pattern="^mcp-[a-z0-9]+(-[a-z0-9]+)*-(token|password|key|secret|api-key|webhook-secret|connection-string|private-key|client-secret|access-key|dsn|url|id)(-[a-z]+)?$"

  if [[ $name =~ $pattern ]]; then
    echo "✅ Valid: $name"
    return 0
  else
    echo "❌ Invalid: $name"
    echo "   Must match pattern: mcp-{service}-{type}[-{environment}]"
    return 1
  fi
}

# Usage
validate_secret_name "mcp-github-token-prod"
validate_secret_name "github-token"  # Invalid
```

### Python Validation Library

```python
import re

class SecretNameValidator:
    PATTERN = re.compile(
        r'^mcp-[a-z0-9]+(-[a-z0-9]+)*-'
        r'(token|password|key|secret|api-key|webhook-secret|connection-string|'
        r'private-key|client-secret|access-key|dsn|url|id)'
        r'(-[a-z]+)?$'
    )

    VALID_TYPES = [
        'token', 'password', 'key', 'secret', 'api-key',
        'webhook-secret', 'connection-string', 'private-key',
        'client-secret', 'access-key', 'dsn', 'url', 'id'
    ]

    VALID_ENVIRONMENTS = [
        'prod', 'staging', 'dev', 'test', 'qa', 'uat', 'demo', 'sandbox'
    ]

    @classmethod
    def validate(cls, name: str) -> tuple[bool, str]:
        """Validate secret name against naming convention.

        Returns:
            (is_valid, error_message)
        """
        if not cls.PATTERN.match(name):
            return False, f"Name '{name}' does not match pattern mcp-{{service}}-{{type}}[-{{environment}}]"

        parts = name.split('-')

        # Check minimum length (mcp-service-type = 3 parts)
        if len(parts) < 3:
            return False, "Name must have at least 3 parts: mcp-{service}-{type}"

        # Check mcp prefix
        if parts[0] != 'mcp':
            return False, "Name must start with 'mcp-'"

        # Validate type (second to last or third part)
        secret_type = parts[-2] if len(parts) >= 4 else parts[-1]
        if secret_type not in cls.VALID_TYPES:
            return False, f"Invalid type '{secret_type}'. Must be one of: {', '.join(cls.VALID_TYPES)}"

        # Validate environment (if present)
        if len(parts) >= 4:
            env = parts[-1]
            if env not in cls.VALID_ENVIRONMENTS:
                return False, f"Invalid environment '{env}'. Must be one of: {', '.join(cls.VALID_ENVIRONMENTS)}"

        return True, "Valid"


# Usage
validator = SecretNameValidator()
print(validator.validate("mcp-github-token-prod"))  # (True, "Valid")
print(validator.validate("github-token"))           # (False, "...")
```

### Pre-Commit Hook

```bash
#!/bin/bash
# .git/hooks/pre-commit
# Validates secret names in configuration files

echo "Validating OCI Vault secret names..."

INVALID_FOUND=0

# Find all YAML files with oci-vault:// references
git diff --cached --name-only | grep -E '\.(yaml|yml)$' | while read -r file; do
  echo "Checking $file..."

  # Extract secret names from oci-vault:// URLs
  git show ":$file" | grep -oP 'oci-vault://[^/]+/\K[^"\s]+' | while read -r secret_name; do
    if ! ./validate-secret-name.sh "$secret_name" > /dev/null 2>&1; then
      echo "❌ Invalid secret name in $file: $secret_name"
      INVALID_FOUND=1
    fi
  done
done

if [ $INVALID_FOUND -eq 1 ]; then
  echo ""
  echo "Secret naming validation failed. Please fix secret names."
  echo "See docs/NAMING_CONVENTIONS.md for guidelines."
  exit 1
fi

echo "✅ All secret names valid"
exit 0
```

## Summary

### Quick Reference

**Pattern:** `mcp-{service}-{type}[-{environment}]`

**Examples:**
- `mcp-github-token-prod`
- `mcp-postgres-password-dev`
- `mcp-openai-api-key`
- `mcp-slack-webhook-secret`

**Key Rules:**
1. Always start with `mcp-`
2. Use lowercase with hyphens only
3. Include service name and credential type
4. Add environment suffix when needed
5. Keep names concise but descriptive
6. Use OCI tags for metadata, not names

**Resources:**
- [OCI Vault Documentation](https://docs.oracle.com/en-us/iaas/Content/KeyManagement/home.htm)
- [upload-secret.sh](../upload-secret.sh) - Secret upload utility
- [oci_vault_resolver.py](../oci_vault_resolver.py) - Secret resolver

---

**Document History:**

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-01-08 | Initial release with 170+ examples |

**Contributing:**

Found an issue or have suggestions? Please open an issue or submit a pull request on GitHub.
