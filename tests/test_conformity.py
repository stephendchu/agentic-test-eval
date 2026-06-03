"""Offline tests for the indistinguishability mapping logic (no model call)."""

from atw.eval.conformity import _added_test_code
from atw.metrics.conformity import _real_position


def test_real_position_tracks_swap():
    assert _real_position(swapped=False) == 1   # merged is test_1
    assert _real_position(swapped=True) == 2     # merged moved to test_2


def test_added_test_code_extracts_plus_lines():
    rec = {"test_diff": "--- tests/t.py\n+def test_new():\n+    assert f()\n-def gone():\n+++ b/x"}
    assert _added_test_code(rec) == "def test_new():\n    assert f()"
