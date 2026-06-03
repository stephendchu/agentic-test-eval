"""MCP server exposing the repo-intelligence tools (the Treatment's toolset).

Run as a real MCP server (stdio):
    .venv/bin/python -m atw.mcp.server

The experiment loop usually calls atw.mcp.tools.Toolbox in-process instead; this
server is the plug-and-play interface a host (Claude Desktop, an agent) mounts.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from atw.mcp.tools import default_toolbox

server = FastMCP("atw-repo-intel")


@server.tool()
def find_related_tests(changed_files: list[str], k: int = 5) -> dict:
    """The repository's most relevant existing tests for these changed files,
    ranked by historical association (imports + co-modification) and artifact
    quality (longevity/reuse). For the top results this returns the actual test
    SOURCE CODE — a quality-ranked, in-repo exemplar to adapt — so you can match
    this repo's conventions without searching for it yourself."""
    return default_toolbox().find_related_tests(changed_files, k)


@server.tool()
def find_helpers(reference_path: str, k: int = 10) -> dict:
    """pytest fixtures/helpers available near the given path (from the repo's
    own conftest.py files), ranked by directory proximity."""
    return default_toolbox().find_helpers(reference_path, k)


if __name__ == "__main__":
    server.run()
