# Contributing to OCI Vault MCP Resolver

Thank you for your interest in contributing! This document provides guidelines and instructions for contributing to the project.

## Code of Conduct

- Be respectful and inclusive
- Focus on constructive feedback
- Help create a welcoming environment for all contributors

## Getting Started

### Prerequisites

- Python 3.8+
- OCI CLI configured
- Git
- Basic understanding of OCI Vault and Docker MCP

### Development Setup

```bash
# Clone your fork
git clone https://github.com/YOUR_USERNAME/oci-vault-mcp-resolver.git
cd oci-vault-mcp-resolver

# Install dependencies
pip install PyYAML

# Run tests
./test-setup.sh
```

## Development Workflow

### 1. Create a Branch

```bash
git checkout -b feature/your-feature-name
# or
git checkout -b fix/bug-description
```

### Branch Naming Conventions

- `feature/` - New features
- `fix/` - Bug fixes
- `docs/` - Documentation improvements
- `refactor/` - Code refactoring
- `test/` - Test additions or improvements

### 2. Make Your Changes

#### Code Style

**Python Code**:
- Follow PEP 8 style guide
- Use type hints where applicable
- Maximum line length: 100 characters
- Use descriptive variable names

```python
# Good
def fetch_secret_by_ocid(self, secret_ocid: str) -> Optional[str]:
    """Fetch secret value from OCI Vault by secret OCID."""
    pass

# Avoid
def get(self, x):
    pass
```

**Bash Scripts**:
- Use `set -euo pipefail` at the start
- Quote all variables: `"$VAR"`
- Use functions for reusable code
- Add comments for complex logic

```bash
# Good
check_dependency() {
    local cmd="$1"
    if ! command -v "$cmd" &> /dev/null; then
        echo "ERROR: $cmd not found"
        return 1
    fi
}

# Use it
check_dependency "python3"
```

#### Documentation

- Add docstrings to all public functions
- Update README.md if adding features
- Add examples for new functionality
- Keep CHANGELOG.md updated

### 3. Test Your Changes

#### Manual Testing

```bash
# Test with example config
python3 oci_vault_resolver.py -i test-mcp-config.yaml --verbose

# Test wrapper script
./mcp-with-vault --dry-run

# Test with real vault secret
echo 'test: oci-vault://YOUR_SECRET_OCID' | python3 oci_vault_resolver.py
```

#### Test Checklist

- [ ] Code runs without errors
- [ ] All URL formats work (OCID, compartment+name, vault+name)
- [ ] Caching works correctly
- [ ] Error handling is graceful
- [ ] Documentation is updated
- [ ] Examples work as shown

### 4. Commit Your Changes

Follow conventional commit format:

```bash
# Format: <type>(<scope>): <description>

git commit -m "feat(resolver): add support for vault OCID format"
git commit -m "fix(cache): correct TTL calculation"
git commit -m "docs(readme): update installation instructions"
git commit -m "refactor(parser): simplify URL parsing logic"
```

**Commit Types**:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation only
- `style`: Code style changes (formatting, etc.)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks

### 5. Push and Create Pull Request

```bash
git push origin feature/your-feature-name
```

Then create a pull request on GitHub with:
- Clear title describing the change
- Description of what changed and why
- Reference to any related issues
- Screenshots/examples if applicable

## Pull Request Process

### PR Template

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Documentation update
- [ ] Refactoring
- [ ] Other (describe)

## Testing
- [ ] Tested manually with example config
- [ ] Tested with real OCI Vault secrets
- [ ] Verified caching behavior
- [ ] Checked error handling

## Checklist
- [ ] Code follows project style guidelines
- [ ] Documentation updated
- [ ] Examples work as expected
- [ ] Commit messages follow conventions
```

### Review Process

1. Maintainer reviews the PR
2. Automated checks run (if configured)
3. Address review comments
4. Once approved, PR is merged

## Areas for Contribution

### High Priority

1. **Parallel Secret Resolution**
   - Resolve multiple secrets concurrently
   - Use asyncio or threading
   - Maintain error handling

2. **Test Suite**
   - Unit tests with pytest
   - Integration tests with mock OCI responses
   - Cache behavior tests

3. **Secret Versioning**
   - Support specific secret versions
   - Format: `oci-vault://secret-ocid?version=2`

### Medium Priority

1. **Enhanced Error Messages**
   - More descriptive error output
   - Suggestions for common issues
   - Better IAM permission error handling

2. **Metrics and Monitoring**
   - Cache hit rate tracking
   - API latency monitoring
   - Error rate reporting

3. **Alternative Cache Backends**
   - Redis support
   - Memcached support
   - Pluggable cache interface

### Documentation

1. **Video Tutorials**
   - Setup walkthrough
   - Integration examples
   - Troubleshooting guide

2. **More Examples**
   - CI/CD integration examples
   - Multi-environment configurations
   - Production deployment patterns

3. **API Reference**
   - Complete function documentation
   - Parameter descriptions
   - Return value specifications

## Code Review Guidelines

### What Reviewers Look For

- **Correctness**: Does it work as intended?
- **Security**: Any security implications?
- **Performance**: Any performance concerns?
- **Readability**: Is the code clear and well-documented?
- **Consistency**: Follows project conventions?

### Giving Feedback

- Be constructive and specific
- Suggest alternatives
- Explain the "why" behind comments
- Appreciate good work

### Receiving Feedback

- View feedback as collaborative improvement
- Ask for clarification if needed
- Explain your approach if misunderstood
- Be open to different solutions

## Development Tips

### Debugging

```bash
# Enable verbose mode
python3 oci_vault_resolver.py --verbose

# Check cache contents
ls -lah ~/.cache/oci-vault-mcp/
cat ~/.cache/oci-vault-mcp/*.json | jq

# Test OCI CLI directly
oci secrets secret-bundle get --secret-id YOUR_OCID

# Verify permissions
oci iam user get --user-id $(oci iam user list --query 'data[0].id' --raw-output)
```

### Performance Testing

```bash
# Measure resolution time
time python3 oci_vault_resolver.py -i test-config.yaml

# Test cache hit performance
for i in {1..100}; do
    echo 'test: oci-vault://SECRET_OCID' | python3 oci_vault_resolver.py > /dev/null
done
```

### Common Pitfalls

1. **OCI CLI Command Changes**
   - OCI CLI syntax can change between versions
   - Always test with multiple OCI CLI versions
   - Document version requirements

2. **Cache Permissions**
   - Cache files must be 0600
   - Check permissions after cache writes
   - Handle permission errors gracefully

3. **Error Handling**
   - Always handle OCI API errors
   - Provide fallback to stale cache
   - Log errors with context

## Testing Strategy

### Unit Tests (Future)

```python
# tests/test_resolver.py
import pytest
from oci_vault_resolver import VaultResolver

def test_parse_ocid_url():
    resolver = VaultResolver()
    ocid, comp, name = resolver.parse_vault_url("oci-vault://ocid1.vaultsecret...")
    assert ocid == "ocid1.vaultsecret..."
    assert comp is None
    assert name is None

def test_cache_hit():
    resolver = VaultResolver()
    # Mock cache with known value
    # Assert cache is used instead of API call
```

### Integration Tests (Future)

```python
# tests/test_integration.py
def test_full_resolution_flow():
    # Create test config with vault reference
    # Resolve secrets
    # Verify resolved config
```

## Release Process

1. Update version in relevant files
2. Update CHANGELOG.md
3. Create git tag: `git tag -a v1.0.0 -m "Version 1.0.0"`
4. Push tag: `git push origin v1.0.0`
5. Create GitHub release with notes

## Getting Help

- **Issues**: Open a GitHub issue for bugs or feature requests
- **Discussions**: Use GitHub Discussions for questions
- **Security**: Email security concerns to maintainers privately

## Recognition

Contributors will be:
- Listed in CONTRIBUTORS.md
- Mentioned in release notes
- Credited in commit messages

Thank you for contributing to making OCI Vault MCP Resolver better!
