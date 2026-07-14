#!/usr/bin/env python3
"""SessionStart: inject the brain index, if this repo has a brain.

M1: proves the plugin loads and is a strict no-op in repos without .brain/.
M4 replaces the placeholder body with the generated index.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hookkit.discovery import find_brain  # noqa: E402
from hookkit.failopen import run_hook  # noqa: E402
from hookkit.killswitch import is_disabled  # noqa: E402


def main(payload: dict) -> None:
    brain = find_brain(payload.get("cwd") or Path.cwd())
    if brain is None or is_disabled(brain):
        return

    index = brain / "index.md"
    if index.is_file():
        print(index.read_text())


run_hook(main)
