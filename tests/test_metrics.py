"""Unit tests for the free structural alignment metric (no model/network)."""

from atw.metrics.style import alignment_score


GT = """
import pytest
from dbt.contracts.graph.nodes import FunctionNode

def test_function_schema_available(project):
    node = FunctionNode(name="f")
    assert node.schema == "public"
"""


def test_identical_code_scores_high():
    score, comps = alignment_score(GT, GT)
    assert score > 95
    assert comps["imports"] == 1.0
    assert comps["fixtures"] == 1.0


def test_unrelated_code_scores_low():
    other = (
        "import unittest\n"
        "class TestMath(unittest.TestCase):\n"
        "    def test_add(self):\n"
        "        self.assertEqual(1 + 1, 2)\n"
    )
    score, comps = alignment_score(other, GT)
    assert score < 50
    assert comps["assert_style"] == 0.0  # self.assert vs plain assert
    assert comps["structure"] < 1.0      # class-based vs function-based


def test_syntactically_broken_generation_does_not_crash():
    score, _ = alignment_score("def test_(:\n  oops", GT)
    assert 0.0 <= score <= 100.0
