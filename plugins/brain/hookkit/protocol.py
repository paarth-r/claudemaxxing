"""The Claude Code PreToolUse hook wire format.

Exit 0 plus a JSON body on stdout controls the permission decision. Exit 2 would
also block, with less control and no way to attach an allow-with-context path, so
this codebase never uses it.
"""

from __future__ import annotations

import json
import sys

EVENT = "PreToolUse"


def _wrap(decision: str, **extra) -> dict:
    output = {"hookEventName": EVENT, "permissionDecision": decision}
    output.update(extra)
    return {"hookSpecificOutput": output}


def allow(context: str = "") -> dict:
    """Let the tool call through. If context is given, the agent sees it."""
    if context:
        return _wrap("allow", additionalContext=context)
    return _wrap("allow")


def deny(reason: str) -> dict:
    """Refuse the tool call. The agent reads `reason` and must reckon with it."""
    return _wrap("deny", permissionDecisionReason=reason)


def emit(payload: dict | None) -> None:
    """Write a decision to stdout. None means 'stay silent, use the normal flow'."""
    if payload is None:
        return
    json.dump(payload, sys.stdout)
    sys.stdout.write("\n")


def command_of(tool_input) -> str:
    """The shell command from a Bash tool call. Empty string for anything else."""
    if not isinstance(tool_input, dict):
        return ""
    command = tool_input.get("command", "")
    return command if isinstance(command, str) else ""
