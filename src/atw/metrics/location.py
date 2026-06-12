"""Location-discovery metric for v2 experiments.

Measures whether each arm correctly identified where the test file should live,
based on the '# target file:' comment the v2 prompt requires as the first line
of the generated test, and whether any ground-truth path was surfaced in traces.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path


_TARGET_RE = re.compile(r"#\s*target file:\s*(.+)", re.IGNORECASE)


def declared_target(test_code: str) -> str | None:
    """Extract the '# target file: <path>' from the first line of generated code."""
    for line in test_code.splitlines():
        line = line.strip()
        if not line:
            continue
        m = _TARGET_RE.match(line)
        return m.group(1).strip() if m else None
    return None


def _normalize(path: str) -> str:
    return path.strip().lstrip("/").replace("\\", "/")


def score_location(
    result_json: dict,
    stream_jsonl_path: Path | None,
    gt_test_files: list[str],
) -> dict:
    """Score one arm's result for location correctness and trace surfacing.

    Returns a dict with:
      declared_path: the path the agent declared, or None
      exact_match: declared path == any ground-truth test file (normalized)
      dir_match: declared path is in the same directory as any gt file
      basename_match: declared filename matches any gt file's basename
      surfaced: any gt path string appeared anywhere in the trace
      first_surfaced_event_idx: index in trace where gt path first appeared, or None
      mcp_tool_calls: count from result_json
    """
    test_code = result_json.get("test_code", "") or ""
    declared = declared_target(test_code)
    norm_declared = _normalize(declared) if declared else None
    norm_gt = [_normalize(p) for p in gt_test_files]

    exact = norm_declared in norm_gt if norm_declared else False
    dir_match = False
    basename_match = False
    if norm_declared:
        decl_dir = os.path.dirname(norm_declared)
        decl_base = os.path.basename(norm_declared)
        for gp in norm_gt:
            if os.path.dirname(gp) == decl_dir:
                dir_match = True
            if os.path.basename(gp) == decl_base:
                basename_match = True

    # Scan trace for any ground-truth path string
    trace = result_json.get("trace", [])
    if trace and stream_jsonl_path is None:
        # trace is inline in result_json (already parsed)
        events = trace
    elif stream_jsonl_path and stream_jsonl_path.exists():
        events = []
        for line in stream_jsonl_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    else:
        events = trace

    surfaced = False
    first_surfaced_idx: int | None = None
    for idx, ev in enumerate(events):
        text = json.dumps(ev)
        if any(gp in text for gp in norm_gt):
            surfaced = True
            first_surfaced_idx = idx
            break

    return {
        "declared_path": declared,
        "exact_match": exact,
        "dir_match": dir_match,
        "basename_match": basename_match,
        "surfaced": surfaced,
        "first_surfaced_event_idx": first_surfaced_idx,
        "mcp_tool_calls": result_json.get("mcp_tool_calls", 0),
    }
