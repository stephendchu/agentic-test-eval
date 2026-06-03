"""Unit tests for the pure classification helpers (no git/network needed)."""

from atw.ingest.commit_extractor import (
    added_test_functions,
    is_prod_py,
    is_test_path,
)


def test_is_test_path():
    assert is_test_path("tests/unit/test_parser.py")
    assert is_test_path("core/dbt/tests/test_thing.py")
    assert is_test_path("pkg/foo_test.py")
    assert is_test_path("tests/conftest.py")
    assert not is_test_path("core/dbt/parser.py")
    assert not is_test_path("README.md")
    assert not is_test_path("tests/fixtures/data.json")  # not .py


def test_is_prod_py():
    assert is_prod_py("core/dbt/parser.py")
    assert not is_prod_py("tests/unit/test_parser.py")
    assert not is_prod_py("setup.py")
    assert not is_prod_py("docs/guide.rst")


def test_added_test_functions_counts_only_added_defs():
    diff = "\n".join([
        "--- tests/test_x.py",
        "@@ -1,2 +1,8 @@",
        " import pytest",
        "+def test_new_behavior():",
        "+    assert add(1, 2) == 3",
        "+async def test_async_path():",
        "+    assert await go()",
        "-def test_removed():",          # removed, not counted
        " def test_unchanged_context():",  # context line, not counted
    ])
    assert added_test_functions(diff) == 2


def test_added_test_functions_ignores_header_plusplus():
    diff = "+++ b/tests/test_x.py\n+def test_real():\n+    pass"
    assert added_test_functions(diff) == 1
