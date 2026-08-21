"""Shared reader for a strix engine run's on-disk log file.

Both a Pentest and a PR review are one `run_strix_scan` run each — the
engine writes `strix.log` to `run_dir_for(<scan_id>)` the same way in both
cases (a PR review passes its own `review.id` as `scan_id`/`run_name`, see
jobs.py's `_run_real_pr_review_scan`) — so the parsing/filtering logic only
needs to live once.
"""

from __future__ import annotations

import re


_LOG_LINE_RE = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3}) (?P<level>\S+)\s+"
    r"(?P<scan_id>\S+) (?P<agent_id>\S+) (?P<logger>[^:]+): (?P<message>.*)$"
)
_MAX_LOG_LINES = 5000


def read_scan_log(
    scan_id: str,
    *,
    level: str | None = None,
    agent_id: str | None = None,
    q: str | None = None,
) -> dict:
    from strix.core.paths import run_dir_for

    log_path = run_dir_for(scan_id) / "strix.log"
    if not log_path.exists():
        return {"available": False, "lines": [], "total_lines": 0, "total_matched": 0, "agent_ids": []}

    level_filter = level.upper() if level else None
    query = q.lower() if q else None

    parsed: list[dict] = []
    agent_ids: set[str] = set()
    total_lines = 0
    with log_path.open("r", encoding="utf-8", errors="replace") as fh:
        for raw_line in fh:
            raw_line = raw_line.rstrip("\n")
            if not raw_line:
                continue
            total_lines += 1
            m = _LOG_LINE_RE.match(raw_line)
            if not m:
                # Continuation of a multi-line message (e.g. a traceback) —
                # append to the previous entry's message rather than dropping it.
                if parsed:
                    parsed[-1]["message"] += "\n" + raw_line
                continue
            entry = m.groupdict()
            if entry["agent_id"] != "-":
                agent_ids.add(entry["agent_id"])
            parsed.append(entry)

    matched = parsed
    if level_filter:
        matched = [e for e in matched if e["level"] == level_filter]
    if agent_id:
        matched = [e for e in matched if e["agent_id"] == agent_id]
    if query:
        matched = [e for e in matched if query in e["message"].lower()]

    total_matched = len(matched)
    tail = matched[-_MAX_LOG_LINES:]

    return {
        "available": True,
        "lines": tail,
        "total_lines": total_lines,
        "total_matched": total_matched,
        "agent_ids": sorted(agent_ids),
    }
