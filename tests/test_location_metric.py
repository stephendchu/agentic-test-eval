"""Tests for the location-discovery metric."""

import pytest

from atw.metrics.location import declared_target, score_location


def test_declared_target_parses_comment():
    code = "# target file: tests/unit/test_foo.py\nimport pytest\n"
    assert declared_target(code) == "tests/unit/test_foo.py"


def test_declared_target_case_insensitive():
    code = "# Target File: tests/test_bar.py\n"
    assert declared_target(code) == "tests/test_bar.py"


def test_declared_target_returns_none_when_missing():
    code = "import pytest\ndef test_foo(): pass\n"
    assert declared_target(code) is None


def test_declared_target_skips_blank_lines():
    code = "\n\n# target file: tests/test_x.py\n"
    assert declared_target(code) == "tests/test_x.py"


def test_score_location_exact_match():
    result = {
        "test_code": "# target file: tests/unit/test_foo.py\ndef test_x(): pass",
        "trace": [],
        "mcp_tool_calls": 0,
    }
    loc = score_location(result, None, ["tests/unit/test_foo.py"])
    assert loc["exact_match"] is True
    assert loc["dir_match"] is True
    assert loc["basename_match"] is True


def test_score_location_dir_match_only():
    result = {
        "test_code": "# target file: tests/unit/test_other.py\ndef test_x(): pass",
        "trace": [],
        "mcp_tool_calls": 0,
    }
    loc = score_location(result, None, ["tests/unit/test_foo.py"])
    assert loc["exact_match"] is False
    assert loc["dir_match"] is True
    assert loc["basename_match"] is False


def test_score_location_no_match():
    result = {
        "test_code": "# target file: tests/other/test_x.py\ndef test_x(): pass",
        "trace": [],
        "mcp_tool_calls": 0,
    }
    loc = score_location(result, None, ["tests/unit/test_foo.py"])
    assert loc["exact_match"] is False
    assert loc["dir_match"] is False


def test_score_location_surfaced_via_trace():
    result = {
        "test_code": "# target file: tests/wrong.py\n",
        "trace": [
            {"type": "tool_result", "content": "found tests/unit/test_foo.py in imports"},
        ],
        "mcp_tool_calls": 1,
    }
    loc = score_location(result, None, ["tests/unit/test_foo.py"])
    assert loc["surfaced"] is True
    assert loc["first_surfaced_event_idx"] == 0


def test_score_location_not_surfaced():
    result = {
        "test_code": "# target file: tests/wrong.py\n",
        "trace": [
            {"type": "tool_result", "content": "nothing relevant here"},
        ],
        "mcp_tool_calls": 0,
    }
    loc = score_location(result, None, ["tests/unit/test_foo.py"])
    assert loc["surfaced"] is False
    assert loc["first_surfaced_event_idx"] is None
