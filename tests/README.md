# Test Suite

This directory contains the test suite for OCI Vault MCP Resolver.

## Running Tests

```bash
# Run all tests
pytest

# Run with coverage report
pytest --cov=oci_vault_resolver --cov-report=html

# Run specific test file
pytest tests/test_parser.py

# Run tests matching a pattern
pytest -k "test_parse"

# Run with verbose output
pytest -v

# Run and stop on first failure
pytest -x
```

## Test Structure

```
tests/
├── __init__.py          # Package marker
├── conftest.py          # Shared fixtures and configuration
├── test_parser.py       # URL parsing tests
└── README.md            # This file
```

## Fixtures

Common fixtures are defined in `conftest.py`:

- `temp_cache_dir`: Temporary directory for cache operations
- `mock_oci_clients`: Mocked OCI SDK clients (no real credentials needed)
- `sample_vault_urls`: Collection of test vault URLs
- `sample_config`: Sample MCP configuration with vault references
- `resolver_with_mocked_oci`: Pre-configured VaultResolver with mocks

## Writing New Tests

### Test Organization

- Use descriptive test names: `test_<what>_<condition>_<expected>`
- Group related tests in classes: `class TestVaultURLParsing:`
- Use parametrize for multiple similar test cases

### Example Test

```python
import pytest
from oci_vault_resolver import VaultResolver

class TestMyFeature:
    """Test suite for my feature."""

    @pytest.fixture
    def resolver(self, temp_cache_dir):
        """Create test resolver."""
        return VaultResolver(cache_dir=temp_cache_dir)

    def test_basic_functionality(self, resolver):
        """Test that basic functionality works."""
        result = resolver.some_method("input")
        assert result == "expected"

    @pytest.mark.parametrize("input_val,expected", [
        ("a", "A"),
        ("b", "B"),
    ])
    def test_multiple_cases(self, resolver, input_val, expected):
        """Test with multiple inputs."""
        assert resolver.transform(input_val) == expected
```

## Integration Tests

Integration tests require real OCI credentials and are marked with `@pytest.mark.integration`.

```bash
# Run only integration tests
pytest -m integration

# Skip integration tests (default)
pytest -m "not integration"
```

## Coverage Goals

- **Unit tests**: 80% coverage minimum
- **Integration tests**: Critical paths only
- **Focus areas**: Secret resolution, cache operations, error handling

## CI/CD

Tests run automatically in CI on:
- Every push to main
- Every pull request
- Python versions: 3.8, 3.9, 3.10, 3.11, 3.12

Coverage reports are uploaded to Codecov.
