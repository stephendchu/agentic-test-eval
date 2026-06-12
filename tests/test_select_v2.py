"""Tests for the v2 deletable_test_file predicate and select_commits_v2."""

import pytest

from atw.eval.run_experiment import _deletable_test_file


@pytest.mark.parametrize("path,expected", [
    # Valid deletable test files
    ("tests/unit/test_foo.py", True),
    ("tests/test_bar.py", True),
    ("tests/unit/parser/test_fusion.py", True),
    ("tests/integration/test_runner_test.py", True),
    # Excluded: conftest / init
    ("tests/conftest.py", False),
    ("tests/unit/conftest.py", False),
    ("tests/__init__.py", False),
    # Excluded: not under tests/
    ("core/dbt/tests/util.py", False),
    ("core/dbt/artifacts/resources/v1/singular_test.py", False),
    ("src/foo_test.py", False),
    # Excluded: non-test naming under tests/
    ("tests/helpers.py", False),
    ("tests/fixtures.py", False),
])
def test_deletable_test_file(path, expected):
    assert _deletable_test_file(path) == expected, f"Expected {expected} for {path!r}"
