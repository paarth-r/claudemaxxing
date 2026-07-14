#!/usr/bin/env python3
"""UserPromptSubmit: notice when the user is correcting the agent, and queue it.

This hook fires on EVERY prompt the user types, so it has exactly two obligations:

  1. Be free. A regex, no model call, no filesystem scan.
  2. Print NOTHING. Anything on stdout here is injected into context on every single
     turn, forever. The whole point of the system is to not do that.

The queued correction is read later, once, by the SessionEnd distiller.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hookkit import queue  # noqa: E402
from hookkit.correction import looks_like_correction  # noqa: E402
from hookkit.discovery import find_brain  # noqa: E402
from hookkit.failopen import run_hook  # noqa: E402
from hookkit.killswitch import is_disabled  # noqa: E402


def main(payload: dict) -> None:
    brain = find_brain(payload.get("cwd") or Path.cwd())
    if brain is None or is_disabled(brain):
        return

    prompt = payload.get("prompt")
    if not looks_like_correction(prompt):
        return

    queue.push(brain, "corrections", {
        "prompt": prompt,
        "session": payload.get("session_id") or "unknown",
    })
    # Deliberately no output.


run_hook(main)
