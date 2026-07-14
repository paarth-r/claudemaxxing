#!/usr/bin/env python3
"""SessionEnd: turn the session into rules and notes.

Runs once, on a substantial session, and calls a model exactly once. Everything it
learns goes into .brain/ in the repo. Prints nothing.

This coexists with any SessionEnd hooks the user already has in settings.json;
plugin hooks and settings hooks both run.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hookkit import distiller, index, mirror, vault  # noqa: E402
from hookkit.discovery import find_brain, repo_root  # noqa: E402
from hookkit.failopen import run_hook  # noqa: E402
from hookkit.killswitch import is_disabled  # noqa: E402
from hookkit.queue import peek  # noqa: E402

MIN_USER_TURNS = 3


def _user_turns(transcript_path) -> int:
    if not transcript_path:
        return 0
    try:
        lines = Path(transcript_path).read_text(errors="ignore").splitlines()
    except OSError:
        return 0

    count = 0
    for line in lines:
        try:
            record = json.loads(line)
        except ValueError:
            continue
        message = record.get("message") or {}
        if message.get("role") == "user":
            count += 1
    return count


def _log(brain: Path, message: str) -> None:
    try:
        directory = Path(brain) / "_log"
        directory.mkdir(parents=True, exist_ok=True)
        with (directory / "distill.log").open("a") as handle:
            handle.write("%s %s\n" % (int(time.time()), message))
    except OSError:
        pass


def main(payload: dict) -> None:
    brain = find_brain(payload.get("cwd") or Path.cwd())
    if brain is None or is_disabled(brain):
        return

    transcript = payload.get("transcript_path")
    session = payload.get("session_id") or "unknown"

    # A trivial session has nothing to teach. But a queued correction is worth acting
    # on however short the session was: it is the whole point of the system.
    queued = peek(brain, "corrections") or peek(brain, "pain")
    if not queued and _user_turns(transcript) < MIN_USER_TURNS:
        return

    written = distiller.run(brain, session, transcript)

    # Always regenerate: rules may have been archived by the lifecycle even if the
    # distiller wrote nothing, and a stale index is misinformation.
    index.generate(brain)

    # The repo's own .brain/ opens directly in Obsidian, mirror or no mirror.
    vault.ensure(brain)

    # Optional, and off unless configured. A stranger's brain never leaves the repo.
    exported = mirror.export(brain, repo_root(brain).name)

    _log(brain, "wrote %d file(s): %s | mirrored %d" % (
        len(written), ", ".join(written) or "-", exported
    ))
    # Deliberately no output.


run_hook(main)
