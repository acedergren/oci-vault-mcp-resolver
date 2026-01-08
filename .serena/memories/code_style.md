# Code Style and Conventions

## Python Code Style

### General Guidelines
- **Standard**: PEP 8 compliance
- **Line Length**: Maximum 100 characters
- **Type Hints**: Use type hints for function parameters and return values
- **Naming**: Descriptive variable names (avoid single letters except in loops)

### Type Hints
```python
# Good
def fetch_secret_by_ocid(self, secret_ocid: str) -> Optional[str]:
    """Fetch secret value from OCI Vault by secret OCID."""
    pass

# Avoid
def get(self, x):
    pass
```

### Docstrings
- Required for all public functions and classes
- Format: Triple double quotes
- Include description and return values
- Example:
```python
"""
Resolve a single oci-vault:// URL to its secret value.

Uses caching and provides fallback to stale cache on errors.
"""
```

### Imports
- Standard library first
- Third-party libraries second
- Local imports last
- Alphabetical within groups

## Bash Script Style

### Required Headers
```bash
#!/bin/bash
set -euo pipefail  # Exit on error, undefined vars, pipe failures
```

### Variable Quoting
- Always quote variables: `"$VAR"`
- Quote command substitutions: `"$(command)"`

### Functions
- Use functions for reusable code
- Local variables with `local` keyword
```bash
check_dependency() {
    local cmd="$1"
    if ! command -v "$cmd" &> /dev/null; then
        echo "ERROR: $cmd not found"
        return 1
    fi
}
```

### Comments
- Add comments for complex logic
- Explain "why" not "what" when code is clear

## Commit Conventions

### Format
```
<type>(<scope>): <description>

[optional body]
```

### Types
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation only
- `style`: Code style changes (formatting, etc.)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks

### Examples
```bash
feat(resolver): add support for vault OCID format
fix(cache): correct TTL calculation
docs(readme): update installation instructions
refactor(parser): simplify URL parsing logic
```

## Branch Naming
- `feature/` - New features
- `fix/` - Bug fixes
- `docs/` - Documentation improvements
- `refactor/` - Code refactoring
- `test/` - Test additions or improvements

## Code Organization Principles
- Single responsibility: Each function does one thing well
- DRY (Don't Repeat Yourself)
- Clear error messages with context
- Graceful degradation over hard failures
- Security-first: chmod 0600 for cache files, no secrets in logs
