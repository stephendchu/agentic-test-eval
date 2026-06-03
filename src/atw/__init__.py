"""agentic-test-writer: repository-aware test generation + evaluation harness.

Core experiment: hold the agent, task, and budget fixed; vary only the tools.
  - Control  = generic tools (grep, read_file, bash)
  - Treatment = custom semantic MCP tools (find_related_tests, find_helpers)
Measure whether repo-specific tooling produces better, more repo-native tests,
using git history as a labeled held-out eval set.
"""

__version__ = "0.0.1"
