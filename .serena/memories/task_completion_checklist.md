# Task Completion Checklist

When completing a development task, ensure the following steps are done:

## Before Committing

### 1. Testing
- [ ] Test code runs without errors
- [ ] All URL formats work (OCID, compartment+name, vault+name)
- [ ] Caching behavior is correct (check cache files created with 0600 permissions)
- [ ] Error handling is graceful (test with invalid OCIDs, network errors)
- [ ] Test with verbose mode to verify logging
- [ ] Run `./test-setup.sh` if available

### 2. Manual Validation
```bash
# Test with example config
python3 oci_vault_resolver.py -i test-mcp-config.yaml --verbose

# Test wrapper script
./mcp-with-vault --dry-run

# Test with real vault secret (if available)
echo 'test: oci-vault://YOUR_SECRET_OCID' | python3 oci_vault_resolver.py
```

### 3. Code Quality
- [ ] Code follows PEP 8 (Python) or bash conventions
- [ ] Type hints added to Python functions
- [ ] Docstrings added to all public functions
- [ ] No hardcoded credentials or secrets
- [ ] Variables properly quoted in bash scripts
- [ ] Error messages are clear and helpful

### 4. Documentation
- [ ] Update README.md if feature is user-facing
- [ ] Add examples for new functionality
- [ ] Update CHANGELOG.md with changes
- [ ] Add inline comments for complex logic
- [ ] Update ARCHITECTURE.md if architectural changes made

### 5. Security Checks
- [ ] Cache files have 0600 permissions
- [ ] No secrets logged or printed (except in verbose debug mode to stderr)
- [ ] OCI API errors don't expose sensitive information
- [ ] Stale cache fallback warns user appropriately

## Committing Changes

### 1. Stage Files
```bash
git add <changed-files>
```

### 2. Commit with Conventional Format
```bash
git commit -m "<type>(<scope>): <description>"
```

Example:
```bash
git commit -m "feat(resolver): add parallel secret resolution"
git commit -m "fix(cache): correct permission setting for cache files"
git commit -m "docs(readme): update installation steps"
```

### 3. Push Changes
```bash
git push origin <branch-name>
```

## Creating Pull Requests

### PR Checklist
- [ ] Clear title describing the change
- [ ] Description of what changed and why
- [ ] Reference to related issues (if any)
- [ ] Examples or screenshots (if applicable)
- [ ] All tests passing
- [ ] Documentation updated
- [ ] Commit messages follow conventions

## No Automated Tools
Note: This project does not currently have:
- Automated linting (no flake8, pylint, black)
- Automated testing (no pytest, unittest)
- CI/CD pipelines (no GitHub Actions, GitLab CI configured)
- Pre-commit hooks

All quality checks are manual and done during code review.
