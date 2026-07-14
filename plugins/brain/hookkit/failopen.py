"""The single most important file in this project.

A memory system must never be able to stop the user from committing code. Every
hook entrypoint goes through run_hook, which swallows everything and exits 0.

Claude Code treats exit 0 as "proceed" and only exit 2 as "block". We never exit 2.
"""

from __future__ import annotations

import json
import sys
import traceback
from typing import Callable


def run_hook(fn: Callable[[dict], None]) -> None:
    """Read the hook payload from stdin, run fn, and exit 0 no matter what."""
    try:
        raw = sys.stdin.read()
    except Exception:  # pragma: no cover - stdin is closed
        raw = ""

    try:
        payload = json.loads(raw) if raw.strip() else {}
    except (ValueError, TypeError):
        payload = {}

    try:
        fn(payload)
    except BaseException:  # noqa: BLE001 - deliberate: nothing escapes
        traceback.print_exc(file=sys.stderr)

    sys.exit(0)
