"""In-process tool implementations (the Treatment's repo-intelligence tools).

The experiment loop calls these directly (cheap, controlled). `server.py` wraps
the same Toolbox as a real MCP server for the plug-and-play interface/demo.
"""

from __future__ import annotations

from functools import lru_cache

from atw.config import REPOS
from atw.graph.build import load_graph
from atw.graph.test_to_code import RepoGraph
from atw.retrieval import helpers, test_finder
from atw.retrieval.quality import QualityScorer


class Toolbox:
    def __init__(self, graph: RepoGraph | None = None):
        self.graph = graph or load_graph()
        self.scorer = QualityScorer(self.graph)
        self.root = REPOS / self.graph.repo

    def find_related_tests(self, changed_files: list[str], k: int = 5) -> dict:
        return {
            "results": test_finder.find_related_tests(
                changed_files, self.graph, self.scorer, k, self.root
            )
        }

    def find_helpers(self, reference_path: str, k: int = 10) -> dict:
        return {
            "results": helpers.find_helpers(reference_path, self.graph, k, self.root)
        }


@lru_cache(maxsize=1)
def default_toolbox() -> Toolbox:
    return Toolbox()
