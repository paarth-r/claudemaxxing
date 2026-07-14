"""Receipts make compliance verifiable instead of merely claimed.

The agent can say it ran the pipeline. It can believe it ran the pipeline. A
receipt is the only thing that proves it, and `is_fresh` is the only thing that
proves it ran AFTER the change being committed.

Receipts are per-session and always gitignored: they contain command lines.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

DENIAL = "_denial"


def _path(brain: Path, session: str) -> Path:
    return Path(brain) / "_receipts" / f"{session}.jsonl"


def _write(brain: Path, session: str, entry: dict) -> None:
    path = _path(brain, session)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a") as handle:
            handle.write(json.dumps(entry) + "\n")
    except OSError:
        pass


def append(brain: Path, session: str, kind: str, cmd: str, exit_code: int) -> None:
    """Record that a command actually ran, and whether it passed."""
    _write(brain, session, {"kind": kind, "ts": time.time(), "cmd": cmd, "exit": exit_code})


def records(brain: Path, session: str):
    """Every well-formed record for this session. Corrupt lines are skipped."""
    try:
        text = _path(brain, session).read_text()
    except OSError:
        return []

    entries = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except ValueError:
            continue
    return entries


def _normalise(pattern: str) -> str:
    """pathlib's `src/**` matches DIRECTORIES, not files - `src/**/*` matches files.

    Getting this wrong is silent and catastrophic: a pattern that matches no files
    looks like "there is no source to be newer than", so every stale receipt would
    be accepted and the gate would pass commits it exists to stop.
    """
    if pattern.endswith("**"):
        return pattern + "/*"
    return pattern


def newest_mtime(root: Path, pattern: str):
    """Newest mtime among files matching `pattern` under `root`. None if none match."""
    try:
        times = [
            p.stat().st_mtime
            for p in Path(root).glob(_normalise(pattern))
            if p.is_file()
        ]
    except (OSError, ValueError, IndexError):
        return None
    return max(times) if times else None


def is_fresh(brain: Path, session: str, kind: str, fresher_than, root: Path) -> bool:
    """Is there a passing receipt of `kind` newer than the newest matching source file?

    A receipt that predates the last source edit does not count. Without this the
    check is theatre: satisfiable by having run the pipeline an hour ago, before the
    change that broke it.
    """
    passing = [
        r for r in records(brain, session)
        if r.get("kind") == kind and r.get("exit") == 0
    ]
    if not passing:
        return False

    newest_receipt = max(r.get("ts", 0) for r in passing)

    if not fresher_than:
        return True

    source_mtime = newest_mtime(root, fresher_than)
    if source_mtime is None:
        return True

    return newest_receipt > source_mtime


def attempt_key(rule_id: str, tool_name: str, tool_input: dict) -> str:
    """A stable fingerprint for 'this exact tool call, denied by this exact rule'."""
    blob = json.dumps(
        {"rule": rule_id, "tool": tool_name, "input": tool_input},
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


def record_denial(brain: Path, session: str, key: str) -> None:
    _write(brain, session, {"kind": DENIAL, "ts": time.time(), "key": key})


def was_denied(brain: Path, session: str, key: str) -> bool:
    """Has this exact call already been denied once this session?

    If so, the gate releases it. A wrong rule costs one wasted agent turn, never a
    deadlock.
    """
    return any(
        r.get("kind") == DENIAL and r.get("key") == key
        for r in records(brain, session)
    )
