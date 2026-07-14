"""Append-only capture queues.

Corrections and pain are noticed cheaply during the session (no model call, no
context cost) and queued. Only at SessionEnd does the distiller read them and
decide what, if anything, is worth writing down.

Queues are drained only after a successful distillation, so a failed session loses
nothing - the corrections simply wait for the next one.
"""

from __future__ import annotations

import json
import time
from pathlib import Path


def _path(brain: Path, kind: str) -> Path:
    return Path(brain) / "_queue" / ("%s.jsonl" % kind)


def push(brain: Path, kind: str, payload: dict) -> None:
    """Add an item. Silent no-op on any failure - capture must never break a session."""
    entry = dict(payload)
    entry.setdefault("ts", time.time())

    path = _path(brain, kind)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a") as handle:
            handle.write(json.dumps(entry) + "\n")
    except (OSError, TypeError, ValueError):
        pass


def peek(brain: Path, kind: str):
    """Every well-formed item, leaving the queue intact. Corrupt lines are skipped."""
    try:
        text = _path(brain, kind).read_text()
    except OSError:
        return []

    items = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            items.append(json.loads(line))
        except ValueError:
            continue
    return items


def drain(brain: Path, kind: str):
    """Read everything and empty the queue."""
    items = peek(brain, kind)
    try:
        path = _path(brain, kind)
        if path.exists():
            path.unlink()
    except OSError:
        pass
    return items
