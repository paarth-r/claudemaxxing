#!/usr/bin/env python3
"""PostToolUse and PostToolUseFailure: turn commands the agent ran into receipts.

A rule's `emits.pattern` names the commands that count as producing its receipt. If
the agent does the live run itself - the normal case - that must satisfy the gate
exactly as if the gate had run the remedy on its behalf.

This script is registered on BOTH events on purpose. Bash's tool_response has no
exit code; success is signalled by which event fired (see hookkit/outcome.py). Wire
up only PostToolUse and failed runs are never recorded as failures; wire up only the
success event and a broken pipeline still earns a passing receipt.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hookkit import queue, receipts  # noqa: E402
from hookkit.discovery import find_brain  # noqa: E402
from hookkit.failopen import run_hook  # noqa: E402
from hookkit.killswitch import is_disabled  # noqa: E402
from hookkit.outcome import FAILURE_EVENT, passed  # noqa: E402
from hookkit.protocol import command_of  # noqa: E402
from hookkit.rules import emits, load_rules  # noqa: E402


def main(payload: dict) -> None:
    brain = find_brain(payload.get("cwd") or Path.cwd())
    if brain is None or is_disabled(brain):
        return

    command = command_of(payload.get("tool_input") or {})
    if not command:
        return

    session = payload.get("session_id") or "unknown"
    exit_code = 0 if passed(payload) else 1

    # Pain: a command that failed is a wall the agent hit. The resolution that
    # eventually worked is the highest-signal gotcha there is, because rediscovering
    # it costs real tool calls every single time.
    if payload.get("hook_event_name") == FAILURE_EVENT:
        queue.push(brain, "pain", {
            "cmd": command,
            "error": str(payload.get("error") or "")[:1000],
            "session": session,
        })

    seen = set()
    for rule in load_rules(brain):
        if rule.receipt in seen:
            continue
        if emits(rule, command):
            receipts.append(brain, session, rule.receipt, command, exit_code)
            seen.add(rule.receipt)


run_hook(main)
