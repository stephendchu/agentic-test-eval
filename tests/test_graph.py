"""Unit tests for repo-agnostic graph/retrieval logic (no git/network)."""

from datetime import datetime, timezone

from atw.graph.test_to_code import (
    RepoGraph,
    build_import_index,
    parse_imports,
    resolve_import,
    _modkey,
)
from atw.retrieval.helpers import fixtures_in
from atw.retrieval.quality import QualityScorer
from atw.retrieval.test_finder import prod_files_from_diff


def test_resolve_import_by_path_suffix():
    prod = ["core/dbt/parser/manifest.py", "other/pkg/util.py"]
    index = build_import_index(prod)
    pbm = {_modkey(f): f for f in prod}
    assert resolve_import("dbt.parser.manifest", index, pbm) == ["core/dbt/parser/manifest.py"]
    assert resolve_import("pkg.util", index, pbm) == ["other/pkg/util.py"]
    assert resolve_import("does.not.exist", index, pbm) == []


def test_parse_imports_absolute_only():
    src = "import os\nfrom dbt.parser import x\nfrom . import sibling\n"
    imports = parse_imports(src)
    assert "os" in imports and "dbt.parser" in imports
    assert all("sibling" not in i for i in imports)  # relative skipped


def test_quality_prefers_longevity():
    g = RepoGraph(
        repo="x",
        test_files=["t_old.py", "t_new.py"],
        file_stats={
            "t_old.py": {"count": 5, "first": "2020-01-01T00:00:00+00:00", "last": "2026-01-01T00:00:00+00:00"},
            "t_new.py": {"count": 5, "first": "2026-05-01T00:00:00+00:00", "last": "2026-05-20T00:00:00+00:00"},
        },
    )
    s = QualityScorer(g, now=datetime(2026, 6, 1, tzinfo=timezone.utc))
    assert s.score("t_old.py") > s.score("t_new.py")


def test_prod_files_from_diff():
    diff = "--- core/dbt/a.py\n@@ ...\n+code\n--- core/dbt/b.py\n+more"
    assert prod_files_from_diff(diff) == ["core/dbt/a.py", "core/dbt/b.py"]


def test_fixtures_in_detects_pytest_fixture():
    src = (
        "import pytest\n"
        "@pytest.fixture\n"
        "def db(): return 1\n"
        "@fixture\n"
        "def cache(tmp_path): return tmp_path\n"
        "def not_a_fixture(): pass\n"
    )
    found = {n for n, _ in fixtures_in(src)}
    assert found == {"db", "cache"}
