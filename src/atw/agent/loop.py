"""Shared agentic loop — one implementation, the arm only changes the toolset.

Backend: Claude Code headless (`claude -p`), which runs on the user's
subscription (no API key) and natively supports generic tools (A1) and MCP tools
(A3). The backend is isolated here so swapping to the Anthropic API later is a
local change.

Arms:
  A1 = generic tools {Read, Grep, Glob, Bash}        (strong baseline)
  A3 = generic tools + semantic MCP tools             (treatment)
(A0 diff-only and A2 RAG are added once the A1-vs-A3 signal is checked.)
"""

from __future__ import annotations

import json
import re
import subprocess

from atw.config import CFG, ROOT
from atw.agent.prompts import TASK
from atw.harness.sandbox import Worktree

VENV_PY = ROOT / ".venv" / "bin" / "python"
ARM_MODEL = "claude-sonnet-4-6"  # same model for every arm; sonnet to conserve usage

GENERIC_TOOLS = ["Read", "Grep", "Glob", "Bash"]
MCP_TOOLS = ["mcp__atw__find_related_tests", "mcp__atw__find_helpers"]
# A3 discovers via the SEMANTIC tools (+ Read to view what they point to) instead
# of grep — forcing the real contrast: semantic retrieval vs generic exploration.
# Without this, the model defaults to its trained grep habit and ignores the MCP
# tools (observed: A3 made 58 generic calls, 0 MCP calls).
ARM_TOOLS = {
    "A1": GENERIC_TOOLS,
    "A3": MCP_TOOLS + ["Read"],
}

# Every built-in tool Claude Code may reach for. `--permission-mode default` does
# NOT deny unlisted tools (observed leaks: ToolSearch, Skill, Task subagent), so
# we DENY-BY-DEFAULT: block every known tool not explicitly allowed by the arm,
# plus the other arm's MCP tools. Keep this list current as Claude Code evolves.
_ALL_KNOWN_TOOLS = [
    "Bash", "BashOutput", "KillShell", "Glob", "Grep", "Read", "Edit", "Write",
    "NotebookEdit", "WebFetch", "WebSearch", "Task", "Agent", "TodoWrite",
    "ToolSearch", "Skill",
]


def _disallow_for(arm: str) -> list[str]:
    allowed = set(ARM_TOOLS[arm])
    block = [t for t in _ALL_KNOWN_TOOLS if t not in allowed]
    block += [t for t in MCP_TOOLS if t not in allowed]  # block other arm's MCP tools
    return block


ARM_DISALLOW = {arm: _disallow_for(arm) for arm in ARM_TOOLS}


def _mcp_config() -> str:
    return json.dumps(
        {"mcpServers": {"atw": {"command": str(VENV_PY), "args": ["-m", "atw.mcp.server"]}}}
    )


def _extract_code(text: str) -> str:
    blocks = re.findall(r"```(?:python)?\n(.*?)```", text, re.S)
    return blocks[-1].strip() if blocks else text.strip()


def run_arm(record: dict, arm: str, model: str = ARM_MODEL,
            max_turns: int = CFG.max_tool_calls, timeout: int = 1200) -> dict:
    """Generate a test for one commit under one arm. Returns code + telemetry."""
    prompt = TASK.format(prod_diff=record["prod_diff"])
    with Worktree(record["parent_sha"]) as wt:
        cmd = [
            "claude", "-p", prompt,
            "--output-format", "stream-json", "--verbose",  # stream → capture tool calls
            "--permission-mode", "default",  # NOT bypass: bypass auto-approves ALL tools
            "--model", model,
            "--max-turns", str(max_turns),
            "--allowedTools", *ARM_TOOLS[arm],
            "--disallowedTools", *ARM_DISALLOW[arm],
        ]
        if arm == "A3":
            cfg = wt / "._atw_mcp.json"
            cfg.write_text(_mcp_config())
            cmd += ["--mcp-config", str(cfg)]
        try:
            proc = subprocess.run(cmd, cwd=str(wt), capture_output=True,
                                  text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            # A run that blows the wall-clock budget is recorded as a failure, not
            # a crash — the driver must keep going.
            return {"arm": arm, "sha": record["sha"], "ok": False,
                    "error": f"timeout after {timeout}s", "timed_out": True}

    # stream-json: one JSON event per line. Collect tool calls + the final result.
    tool_calls: list[str] = []
    final: dict | None = None
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        if ev.get("type") == "assistant":
            for block in ev.get("message", {}).get("content", []):
                if block.get("type") == "tool_use":
                    tool_calls.append(block.get("name", "?"))
        elif ev.get("type") == "result":
            final = ev

    if final is None:
        return {"arm": arm, "sha": record["sha"], "ok": False,
                "error": (proc.stdout[-800:] + "\n" + proc.stderr[-800:]).strip()}

    result_text = final.get("result", "") or ""
    if "session limit" in result_text.lower() or "usage limit" in result_text.lower():
        return {"arm": arm, "sha": record["sha"], "ok": False,
                "rate_limited": True, "error": result_text.strip()[:200]}

    return {
        "arm": arm,
        "sha": record["sha"],
        "ok": not final.get("is_error", False),
        "test_code": _extract_code(result_text),
        "num_turns": final.get("num_turns"),
        "cost_usd_equiv": final.get("total_cost_usd"),
        "session_id": final.get("session_id"),
        "tool_calls": tool_calls,
        "n_tool_calls": len(tool_calls),
        "mcp_tool_calls": sum(1 for n in tool_calls if n and n.startswith("mcp__")),
        "permission_denials": [d.get("tool_name") for d in final.get("permission_denials", [])],
    }
