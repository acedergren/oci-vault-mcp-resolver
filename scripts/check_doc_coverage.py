#!/usr/bin/env python3
# type: ignore
# mypy: ignore-errors
"""
Documentation Coverage Checker.

Analyzes Python code to ensure all public functions, classes, and methods
have proper docstrings and documentation.
"""

import ast
import sys
from pathlib import Path
from typing import Dict


class DocCoverage:
    """Check documentation coverage for Python codebase."""

    def __init__(self, codebase_path: str) -> None:
        """Initialize DocCoverage with codebase path."""
        self.codebase_path = Path(codebase_path)
        self.results = {
            "total_functions": 0,
            "documented_functions": 0,
            "total_classes": 0,
            "documented_classes": 0,
            "total_methods": 0,
            "documented_methods": 0,
            "missing_docs": [],
            "files_checked": 0,
        }

    def check_coverage(self) -> Dict:
        """Check documentation coverage for all Python files."""
        python_files = list(self.codebase_path.glob("**/*.py"))

        # Exclude test files and __init__.py
        python_files = [
            f
            for f in python_files
            if not f.name.startswith("test_")
            and f.name != "__init__.py"
            and "venv" not in str(f)
            and ".venv" not in str(f)
        ]

        for file_path in python_files:
            self.results["files_checked"] += 1
            self._analyze_file(file_path)

        self._calculate_percentages()
        return self.results

    def _analyze_file(self, file_path: Path):  # noqa: C901
        """Analyze a single Python file for documentation."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                tree = ast.parse(f.read(), filename=str(file_path))
        except SyntaxError:
            print(f"Warning: Could not parse {file_path}", file=sys.stderr)
            return

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # Skip private functions (start with _)
                if not node.name.startswith("_"):
                    self.results["total_functions"] += 1
                    if self._has_docstring(node):
                        self.results["documented_functions"] += 1
                    else:
                        self.results["missing_docs"].append(
                            {
                                "type": "function",
                                "name": node.name,
                                "file": str(file_path.relative_to(self.codebase_path)),
                                "line": node.lineno,
                            }
                        )

            elif isinstance(node, ast.ClassDef):
                self.results["total_classes"] += 1
                if self._has_docstring(node):
                    self.results["documented_classes"] += 1
                else:
                    self.results["missing_docs"].append(
                        {
                            "type": "class",
                            "name": node.name,
                            "file": str(file_path.relative_to(self.codebase_path)),
                            "line": node.lineno,
                        }
                    )

                # Check methods within the class
                for item in node.body:
                    if isinstance(item, ast.FunctionDef):
                        # Skip private methods and special methods
                        if not item.name.startswith("_") or item.name in (
                            "__init__",
                            "__str__",
                            "__repr__",
                        ):
                            self.results["total_methods"] += 1
                            if self._has_docstring(item):
                                self.results["documented_methods"] += 1
                            else:
                                self.results["missing_docs"].append(
                                    {
                                        "type": "method",
                                        "name": f"{node.name}.{item.name}",
                                        "file": str(file_path.relative_to(self.codebase_path)),
                                        "line": item.lineno,
                                    }
                                )

    def _has_docstring(self, node) -> bool:
        """Check if a node has a docstring."""
        docstring = ast.get_docstring(node)
        # Consider only non-trivial docstrings (more than just the function name)
        return docstring is not None and len(docstring.strip()) > 10

    def _calculate_percentages(self):
        """Calculate coverage percentages."""
        if self.results["total_functions"] > 0:
            self.results["function_coverage"] = (
                self.results["documented_functions"] / self.results["total_functions"] * 100
            )
        else:
            self.results["function_coverage"] = 100.0

        if self.results["total_classes"] > 0:
            self.results["class_coverage"] = (
                self.results["documented_classes"] / self.results["total_classes"] * 100
            )
        else:
            self.results["class_coverage"] = 100.0

        if self.results["total_methods"] > 0:
            self.results["method_coverage"] = (
                self.results["documented_methods"] / self.results["total_methods"] * 100
            )
        else:
            self.results["method_coverage"] = 100.0

        total_items = (
            self.results["total_functions"]
            + self.results["total_classes"]
            + self.results["total_methods"]
        )
        documented_items = (
            self.results["documented_functions"]
            + self.results["documented_classes"]
            + self.results["documented_methods"]
        )

        if total_items > 0:
            self.results["overall_coverage"] = documented_items / total_items * 100
        else:
            self.results["overall_coverage"] = 100.0

    def print_report(self):
        """Print coverage report in markdown format."""
        print("# Documentation Coverage Report\n")
        print(f"**Generated**: {Path.cwd()}\n")
        print(f"**Files Checked**: {self.results['files_checked']}\n")

        print("## Coverage Summary\n")
        print("| Category | Documented | Total | Coverage |")
        print("|----------|------------|-------|----------|")
        print(
            f"| **Functions** | {self.results['documented_functions']} | "
            f"{self.results['total_functions']} | "
            f"{self.results['function_coverage']:.1f}% |"
        )
        print(
            f"| **Classes** | {self.results['documented_classes']} | "
            f"{self.results['total_classes']} | "
            f"{self.results['class_coverage']:.1f}% |"
        )
        print(
            f"| **Methods** | {self.results['documented_methods']} | "
            f"{self.results['total_methods']} | "
            f"{self.results['method_coverage']:.1f}% |"
        )
        total_documented = (
            self.results["documented_functions"]
            + self.results["documented_classes"]
            + self.results["documented_methods"]
        )
        total_items = (
            self.results["total_functions"]
            + self.results["total_classes"]
            + self.results["total_methods"]
        )
        print(
            f"| **Overall** | {total_documented} | {total_items} | "
            f"{self.results['overall_coverage']:.1f}% |\n"
        )

        if self.results["missing_docs"]:
            print("\n## Missing Documentation\n")
            print("| Type | Name | File | Line |")
            print("|------|------|------|------|")
            for item in sorted(self.results["missing_docs"], key=lambda x: (x["file"], x["line"])):
                print(
                    f"| {item['type']} | `{item['name']}` | " f"{item['file']} | {item['line']} |"
                )

        # Status badge
        coverage = self.results["overall_coverage"]
        if coverage >= 90:
            badge = "![Coverage](https://img.shields.io/badge/docs-excellent-brightgreen)"
        elif coverage >= 75:
            badge = "![Coverage](https://img.shields.io/badge/docs-good-green)"
        elif coverage >= 50:
            badge = "![Coverage](https://img.shields.io/badge/docs-fair-yellow)"
        else:
            badge = "![Coverage](https://img.shields.io/badge/docs-needs%20work-red)"

        print(f"\n## Status\n\n{badge}\n")

        # Recommendations
        if coverage < 90:
            print("\n## Recommendations\n")
            print("- Add docstrings to all public functions and classes")
            print("- Include parameter descriptions in docstrings")
            print("- Document return values and exceptions")
            print("- Add usage examples in docstrings")


def main():
    """Run the documentation coverage checker."""
    # Default to current directory
    codebase_path = sys.argv[1] if len(sys.argv) > 1 else "."

    checker = DocCoverage(codebase_path)
    checker.check_coverage()
    checker.print_report()

    # Exit with error if coverage is too low
    if checker.results["overall_coverage"] < 50:
        sys.exit(1)


if __name__ == "__main__":
    main()
