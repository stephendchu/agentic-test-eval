"""Shared agentic loop — one implementation, the arm only changes the toolset.

Backend: Claude Code headless (`claude -p`), which runs on the user's
subscription (no API key) and natively supports generic tools (A1) and MCP tools
(A3). The backend is isolated here so swapping to the Anthropic API later is a
local change.

Arms:
  A1 = generic tools {Read, Grep, Glob, Bash}             (v1 baseline, unchanged)
  A2 = generic tools + semantic MCP tools                  (v2 treatment: MCP on/off toggle)
  A3 = semantic MCP tools only (grep blocked)              (v1 treatment, kept for reproducibility)

v2 uses A1 vs A2: both arms have full grep, A2 additionally has the MCP mounted.
This mirrors the work-codebase study (MCP toggle) and measures voluntary adoption
when grep is starved by the test-file deletion. Voluntary MCP-call rate is a
first-class mechanism metric.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from atw.config import CFG, ROOT
from atw.agent.prompts import TASK, TASK_V2
from atw.harness.sandbox import Worktree

VENV_PY = ROOT / ".venv" / "bin" / "python"
ARM_MODEL = "claude-sonnet-4-6"  # same model for every arm; sonnet to conserve usage

GENERIC_TOOLS = ["Read", "Grep", "Glob", "Bash"]
MCP_TOOLS = ["mcp__atw__find_related_tests", "mcp__atw__find_helpers"]
ARM_TOOLS = {
    "A1": GENERIC_TOOLS,
    # A2: full generic + MCP (grep available but MCP also mounted — voluntary adoption)
    "A2": GENERIC_TOOLS + MCP_TOOLS,
    # A3: MCP-only (grep blocked — forced contrast, kept for v1 reproducibility)
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
    block += [t for t in MCP_TOOLS if t not in allowed]
    return block


ARM_DISALLOW = {arm: _disallow_for(arm) for arm in ARM_TOOLS}

_TRACE_TRUNCATE = 4000  # max chars per tool input/result stored in trace


def _mcp_config(wt: Path, repo_name: str) -> str:
    # ATW_TOOL_ROOT repoints the MCP subprocess to the worktree (fixes Bug A:
    # without this, find_related_tests reads source from the clone at HEAD,
    # which may contain the maintainer's post-change test — ground-truth leakage).
    return json.dumps({
        "mcpServers": {
            "atw": {
                "command": str(VENV_PY),
                "args": ["-m", "atw.mcp.server"],
                "env": {"ATW_REPO": repo_name, "ATW_TOOL_ROOT": str(wt)},
            }
        }
    })


def _extract_code(text: str) -> str:
    blocks = re.findall(r"```(?:python)?\n(.*?)```", text, re.S)
    return blocks[-1].strip() if blocks else text.strip()


def _parse_stream(stdout: str) -> tuple[list[str], list[dict], dict | None, str]:
    """Parse stream-json output.

    Returns (tool_names, trace_events, final_result_event, last_code_block).
    last_code_block: the last ```python block seen in any assistant text message —
    used as a fallback when the run hits error_max_turns but the agent did write code.
    """
    tool_calls: list[str] = []
    trace: list[dict] = []
    final: dict | None = None
    last_code_block: str = ""

    for line in stdout.splitlines():
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
                    name = block.get("name", "?")
                    tool_calls.append(name)
                    raw_input = block.get("input", {})
                    trace.append({
                        "type": "tool_use",
                        "name": name,
                        "input": json.dumps(raw_input)[:_TRACE_TRUNCATE],
                    })
                elif block.get("type") == "text":
                    extracted = _extract_code(block.get("text", ""))
                    if extracted and "```" not in extracted:  # real code, not just the block markers
                        last_code_block = extracted
        elif ev.get("type") == "user":
            for block in ev.get("message", {}).get("content", []):
                if block.get("type") == "tool_result":
                    content = block.get("content", "")
                    if isinstance(content, list):
                        content = " ".join(
                            c.get("text", "") for c in content if isinstance(c, dict)
                        )
                    trace.append({
                        "type": "tool_result",
                        "content": str(content)[:_TRACE_TRUNCATE],
                    })
        elif ev.get("type") == "result":
            final = ev

    return tool_calls, trace, final, last_code_block


def run_arm(
    record: dict,
    arm: str,
    model: str = ARM_MODEL,
    max_turns: int = CFG.max_tool_calls,
    timeout: int = 1200,
    protocol: str = "v1",
    stream_path: Path | None = None,
) -> dict:
    """Generate a test for one commit under one arm. Returns code + telemetry.

    protocol="v2": deletes the target test file(s) from the worktree and strips
    the .git pointer before the agent runs, forcing real retrieval.
    stream_path: if given, raw stream-json lines are also written there.
    """
    prompt_template = TASK_V2 if protocol == "v2" else TASK
    prompt = prompt_template.format(prod_diff=record["prod_diff"])
    repo_name = CFG.repo.name

    wt_kwargs: dict = {}
    if protocol == "v2":
        wt_kwargs["delete_paths"] = record.get("test_files", [])
        wt_kwargs["strip_git"] = True

    with Worktree(record["parent_sha"], delete_paths=wt_kwargs.get("delete_paths"),
                  strip_git=wt_kwargs.get("strip_git", False)) as wt:
        wt_path = wt.path
        cmd = [
            "claude", "-p", prompt,
            "--output-format", "stream-json", "--verbose",
            "--permission-mode", "default",
            "--model", model,
            "--max-turns", str(max_turns),
            "--bare",  # skip hooks/plugins so SessionStart doesn't bloat headless prompts
            "--allowedTools", *ARM_TOOLS[arm],
            "--disallowedTools", *ARM_DISALLOW[arm],
        ]
        if arm in ("A2", "A3"):
            cfg_path = wt_path / "._atw_mcp.json"
            cfg_path.write_text(_mcp_config(wt_path, repo_name))
            cmd += ["--mcp-config", str(cfg_path)]
        try:
            proc = subprocess.run(cmd, cwd=str(wt_path), capture_output=True,
                                  text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            return {"arm": arm, "sha": record["sha"], "ok": False,
                    "error": f"timeout after {timeout}s", "timed_out": True}

        deleted_existing = wt.deleted_existing if protocol == "v2" else []

    if stream_path is not None:
        stream_path.parent.mkdir(parents=True, exist_ok=True)
        stream_path.write_text(proc.stdout, encoding="utf-8")

    tool_calls, trace, final, last_code_block = _parse_stream(proc.stdout)

    if final is None:
        return {"arm": arm, "sha": record["sha"], "ok": False,
                "error": (proc.stdout[-800:] + "\n" + proc.stderr[-800:]).strip()}

    result_text = final.get("result", "") or ""
    if "session limit" in result_text.lower() or "usage limit" in result_text.lower():
        return {"arm": arm, "sha": record["sha"], "ok": False,
                "rate_limited": True, "error": result_text.strip()[:200]}

    is_error = final.get("is_error", False)
    hit_turn_limit = final.get("subtype") == "error_max_turns"

    # When the agent hits the turn cap, use the last code block it wrote rather
    # than discarding the run entirely. The agent explored but ran out of budget
    # before the final result event — its last written code is still useful output.
    test_code = _extract_code(result_text)
    if (is_error or not test_code) and last_code_block:
        test_code = last_code_block
        is_error = False  # treat as recoverable

    return {
        "arm": arm,
        "sha": record["sha"],
        "protocol": protocol,
        "ok": not is_error,
        "hit_turn_limit": hit_turn_limit,
        "test_code": test_code,
        "num_turns": final.get("num_turns"),
        "cost_usd_equiv": final.get("total_cost_usd"),
        "session_id": final.get("session_id"),
        "tool_calls": tool_calls,
        "n_tool_calls": len(tool_calls),
        "mcp_tool_calls": sum(1 for n in tool_calls if n and n.startswith("mcp__")),
        "permission_denials": [d.get("tool_name") for d in final.get("permission_denials", [])],
        "trace": trace,
        "deleted_existing": deleted_existing,
    }
