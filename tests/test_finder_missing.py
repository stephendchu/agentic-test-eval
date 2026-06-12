"""Tests for find_related_tests behavior when target file does not exist (v2 deletion)."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from atw.retrieval.test_finder import find_related_tests


def _make_graph(test_paths: list[str]) -> MagicMock:
    graph = MagicMock()
    graph.repo = "test-repo"
    # Every prod file maps to all test_paths with association 2.0
    graph.related_tests.return_value = {t: 2.0 for t in test_paths}
    return graph


def _make_scorer(score: float = 0.8) -> MagicMock:
    scorer = MagicMock()
    scorer.score.return_value = score
    return scorer


def test_missing_file_gets_exists_false_and_note(tmp_path):
    # Create one real test file and one that doesn't exist
    real = tmp_path / "tests" / "test_real.py"
    real.parent.mkdir()
    real.write_text("def test_foo(): pass\n")

    graph = _make_graph(["tests/test_deleted.py", "tests/test_real.py"])
    scorer = _make_scorer()

    results = find_related_tests(["src/foo.py"], graph, scorer, k=5, root=tmp_path)

    deleted_entries = [r for r in results if r["path"] == "tests/test_deleted.py"]
    assert deleted_entries, "deleted file should still appear in results"
    entry = deleted_entries[0]
    assert entry["exists"] is False
    assert "note" in entry
    assert "not present" in entry["note"]
    assert "source" not in entry, "source must not be included for deleted files"
    assert entry["test_functions"] == []


def test_existing_file_gets_source(tmp_path):
    real = tmp_path / "tests" / "test_real.py"
    real.parent.mkdir()
    real.write_text("def test_foo(): pass\n")

    graph = _make_graph(["tests/test_real.py"])
    scorer = _make_scorer()

    results = find_related_tests(["src/foo.py"], graph, scorer, k=5, root=tmp_path)
    assert results[0]["exists"] is True
    assert "source" in results[0]


def test_source_promotion_skips_missing(tmp_path):
    """source_k=2 exemplars should come from existing files, skipping missing ones."""
    for i in range(1, 4):
        f = tmp_path / "tests" / f"test_{i}.py"
        f.parent.mkdir(exist_ok=True)
        f.write_text(f"def test_{i}(): pass\n")
    # test_0.py does not exist

    paths = ["tests/test_0.py", "tests/test_1.py", "tests/test_2.py", "tests/test_3.py"]
    graph = _make_graph(paths)
    scorer = _make_scorer()

    results = find_related_tests(["src/foo.py"], graph, scorer, k=4, root=tmp_path, source_k=2)

    sources_emitted = sum(1 for r in results if "source" in r)
    assert sources_emitted == 2, f"expected exactly 2 sources, got {sources_emitted}"

    missing = [r for r in results if not r["exists"]]
    for m in missing:
        assert "source" not in m
