# Quick Start Guide - OCI Vault MCP Resolver

✅ **Your test secret is ready!**

**Secret Name:** mcp-test-secret
**Secret OCID:** `ocid1.vaultsecret.oc1.eu-frankfurt-1.amaaaaaahhxc6pyanshr7dq5klnc4mld6otcwzz3ijkkbbrwamk6kx7vb7wq`
**Secret Value:** `test-secret-value-12345`
**Compartment:** AC (`ocid1.compartment.oc1..aaaaaaaarekfofhmfup6d33agbnicuop2waas3ssdwdc7qjgencirdgvl3iq`)
**Vault:** AC-vault

## ✅ What Works

1. ✅ Direct OCID format: `oci-vault://ocid1.vaultsecret...`
2. ✅ Compartment + Name format: `oci-vault://ocid1.compartment.../mcp-test-secret`
3. ✅ Caching with TTL (default 1 hour)
4. ✅ Graceful degradation (stale cache fallback)

## 🚀 Using with Docker MCP Gateway

### Step 1: Check Current MCP Config

```bash
docker mcp config read
```

### Step 2: Add Vault References to Config

Edit your MCP configuration to include `oci-vault://` references:

```yaml
servers:
  prometheus:
    config:
      PROMETHEUS_URL: http://localhost:9090
      # Add your secret here
      API_KEY: oci-vault://ocid1.compartment.oc1..xxx/your-secret-name
```

Apply the config:

```bash
docker mcp config read > /tmp/mcp-config.yaml
# Edit /tmp/mcp-config.yaml to add vault references
cat /tmp/mcp-config.yaml | docker mcp config write
```

### Step 3: Resolve Secrets

Use the wrapper script (recommended):

```bash
cd ~/projects/oci-vault-mcp-resolver
./mcp-with-vault
```

Or manually:

```bash
docker mcp config read | \
  python3 ~/projects/oci-vault-mcp-resolver/oci_vault_resolver.py | \
  docker mcp config write
```

### Step 4: Verify

```bash
# The config should now have resolved secrets
docker mcp config read | grep -v "oci-vault://"
```

### Step 5: Restart Gateway (if needed)

```bash
docker mcp gateway restart
```

## 🧪 Testing the Resolver

### Test with Example Config

```bash
cd ~/projects/oci-vault-mcp-resolver

# Test with the example config
python3 oci_vault_resolver.py -i test-mcp-config.yaml

# Test with verbose logging
python3 oci_vault_resolver.py -i test-mcp-config.yaml --verbose

# Dry run to preview
cat test-mcp-config.yaml | python3 oci_vault_resolver.py
```

### Test Direct Secret Fetch

```bash
# Test your actual secret by OCID
echo 'test: oci-vault://ocid1.vaultsecret.oc1.eu-frankfurt-1.amaaaaaahhxc6pyanshr7dq5klnc4mld6otcwzz3ijkkbbrwamk6kx7vb7wq' | \
  python3 oci_vault_resolver.py

# Test by compartment + name
echo 'test: oci-vault://ocid1.compartment.oc1..aaaaaaaarekfofhmfup6d33agbnicuop2waas3ssdwdc7qjgencirdgvl3iq/mcp-test-secret' | \
  python3 oci_vault_resolver.py
```

## 📊 URL Format Examples

### Format 1: Direct OCID (Fastest)
```yaml
MY_SECRET: oci-vault://ocid1.vaultsecret.oc1.eu-frankfurt-1.amaaaaaahhxc6pyanshr7dq5klnc4mld6otcwzz3ijkkbbrwamk6kx7vb7wq
```
**Pros:** Fastest resolution (1 API call), no lookup needed
**Cons:** Not portable across environments, OCID is environment-specific

### Format 2: Compartment + Name (Recommended)
```yaml
MY_SECRET: oci-vault://ocid1.compartment.oc1..aaaaaaaarekfofhmfup6d33agbnicuop2waas3ssdwdc7qjgencirdgvl3iq/mcp-test-secret
```
**Pros:** Portable, self-documenting, can use different secrets per environment
**Cons:** Slightly slower (2 API calls on cache miss)

### Format 3: Vault + Name
```yaml
MY_SECRET: oci-vault://ocid1.vault.oc1.eu-frankfurt-1.xxx/mcp-test-secret
```
**Pros:** Scoped to specific vault, good for multi-vault setups
**Cons:** Requires vault OCID, still needs lookup

## 🔧 Configuration Options

### Custom Cache TTL

```bash
# 5 minutes (for frequently rotating secrets)
./mcp-with-vault --ttl 300

# 2 hours (for stable secrets)
./mcp-with-vault --ttl 7200
```

### Verbose Mode

```bash
# See detailed debug output
./mcp-with-vault --verbose
```

### Dry Run

```bash
# Preview what would be resolved
./mcp-with-vault --dry-run
```

## 🗂️ Cache Management

Cache location: `~/.cache/oci-vault-mcp/`

```bash
# View cached secrets
ls -lah ~/.cache/oci-vault-mcp/

# Clear all cache
rm -rf ~/.cache/oci-vault-mcp/

# View cache age
stat ~/.cache/oci-vault-mcp/*.json
```

## 🔐 Creating Additional Secrets

### Create a New Secret

```bash
# Set variables
COMPARTMENT_ID="ocid1.compartment.oc1..aaaaaaaarekfofhmfup6d33agbnicuop2waas3ssdwdc7qjgencirdgvl3iq"
VAULT_ID="ocid1.vault.oc1.eu-frankfurt-1.bfpizfqyaacmg.abtheljtdamq6fycneeey5q4sfeoek6esnjvvkmno6obhv4pmwn4vzjcuprq"
KEY_ID="ocid1.key.oc1.eu-frankfurt-1.bfpizfqyaacmg.abtheljssy4ropepz7w7clogsnu3riy4wb6vk2d5u65zsm526dqtllucukaq"

# Create secret
SECRET_VALUE="your-secret-value-here"
SECRET_NAME="your-secret-name"

oci vault secret create-base64 \
  --compartment-id "$COMPARTMENT_ID" \
  --secret-name "$SECRET_NAME" \
  --vault-id "$VAULT_ID" \
  --key-id "$KEY_ID" \
  --secret-content-content "$(echo -n "$SECRET_VALUE" | base64)" \
  --description "Description of your secret"
```

### Update an Existing Secret

```bash
SECRET_OCID="ocid1.vaultsecret..."
NEW_VALUE="updated-secret-value"

oci vault secret update-base64 \
  --secret-id "$SECRET_OCID" \
  --secret-content-content "$(echo -n "$NEW_VALUE" | base64)"

# Clear cache to force fresh fetch
rm -rf ~/.cache/oci-vault-mcp/
```

## 🐛 Troubleshooting

### Issue: "OCI CLI not configured"

```bash
# Configure OCI CLI
oci setup config
```

### Issue: "Failed to fetch secret"

```bash
# Test OCI CLI directly
oci secrets secret-bundle get --secret-id YOUR_SECRET_OCID

# Check IAM permissions
oci iam user get --user-id YOUR_USER_OCID
```

### Issue: "Secret not found by name"

```bash
# List secrets in compartment
oci vault secret list \
  --compartment-id YOUR_COMPARTMENT_ID \
  --all | jq '.data[] | {"name": ."secret-name", "id": .id}'

# Verify secret name matches exactly (case-sensitive)
```

### Issue: Cache is stale

```bash
# Clear cache and retry
rm -rf ~/.cache/oci-vault-mcp/
./mcp-with-vault
```

## 📚 Next Steps

1. **Add real secrets**: Create secrets for your actual services (GitHub tokens, API keys, etc.)
2. **Update MCP config**: Add `oci-vault://` references to your production MCP configuration
3. **Automate**: Add `./mcp-with-vault` to your startup scripts or CI/CD pipeline
4. **Monitor**: Check cache directory periodically for proper operation
5. **Rotate secrets**: Update secrets in OCI Vault and clear cache to force refresh

## 🔒 Security Best Practices

1. ✅ **Never commit OCIDs** to version control
2. ✅ **Use compartment+name format** for environment portability
3. ✅ **Set appropriate TTL** based on rotation frequency
4. ✅ **Use IAM policies** to restrict secret access
5. ✅ **Enable audit logging** in OCI Vault
6. ✅ **Regularly rotate secrets** and update vault
7. ✅ **Use separate compartments** for dev/staging/prod

## 💡 Integration Examples

### Systemd Service

```bash
# /etc/systemd/system/mcp-gateway.service
[Unit]
Description=Docker MCP Gateway with OCI Vault Secrets
After=network.target

[Service]
Type=oneshot
ExecStart=/home/alex/projects/oci-vault-mcp-resolver/mcp-with-vault --start
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
```

### GitHub Actions

```yaml
- name: Resolve OCI Vault Secrets
  run: |
    docker mcp config read | \
      python3 oci_vault_resolver.py | \
      docker mcp config write
```

### Cron Job (for secret refresh)

```bash
# Refresh secrets every hour
0 * * * * cd /home/alex/projects/oci-vault-mcp-resolver && ./mcp-with-vault
```

---

**Need help?** Check the full [README.md](README.md) for detailed documentation.
