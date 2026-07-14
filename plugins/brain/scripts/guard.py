#!/usr/bin/env python3
"""PreToolUse: the gate.

Match a rule against the tool call. If a fresh receipt proves the rule is already
satisfied, allow silently. Otherwise try to satisfy it by running the remedy; if
that passes, allow (the user never notices). If it fails, deny and hand the agent
the real error. If the identical call was already denied once, release it.

Never blocks hard. Never exits non-zero.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hookkit import lifecycle, receipts, stats  # noqa: E402
from hookkit.discovery import find_brain, repo_root  # noqa: E402
from hookkit.failopen import run_hook  # noqa: E402
from hookkit.gate import ALLOW, DENY, REMEDY, decide  # noqa: E402
from hookkit.killswitch import config_flag, is_disabled  # noqa: E402
from hookkit.protocol import allow, command_of, deny, emit  # noqa: E402
from hookkit.rules import load_rules  # noqa: E402


def _record(rule, brain, field):
    """Bump a stat, then let the rule be judged by its own updated evidence.

    Re-reading the rule after the bump matters: a rule that just took its third
    override must archive itself now, not at some later sweep that may never come.
    """
    stats.bump(rule, field)
    for updated in load_rules(brain):
        if updated.id == rule.id:
            lifecycle.apply(updated, brain)
            return


def _run_remedy(rule, root):
    """Run the rule's remedy. Returns (exit_code, output). exit_code is None if it
    could not be run at all (timeout, OS error), which is a fail-open case."""
    try:
        completed = subprocess.run(
            rule.remedy_command,
            shell=True,
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=rule.remedy_timeout,
        )
        output = (completed.stderr or completed.stdout or "").strip()
        return completed.returncode, output
    except subprocess.TimeoutExpired:
        return None, "remedy timed out after %ss" % rule.remedy_timeout
    except OSError as error:
        return None, str(error)


def main(payload: dict) -> None:
    brain = find_brain(payload.get("cwd") or Path.cwd())
    if brain is None or is_disabled(brain):
        return

    session = payload.get("session_id") or "unknown"
    tool_name = payload.get("tool_name") or ""
    tool_input = payload.get("tool_input") or {}
    command = command_of(tool_input)
    root = repo_root(brain)

    rules = load_rules(brain)
    if not rules:
        return

    def key_for(rule):
        return receipts.attempt_key(rule.id, tool_name, tool_input)

    decision = decide(
        rules,
        tool_name,
        command,
        tool_input,
        is_fresh_fn=lambda r: receipts.is_fresh(brain, session, r.receipt, r.fresher_than, root),
        was_denied_fn=lambda r: receipts.was_denied(brain, session, key_for(r)),
        auto_remedy=config_flag(brain, "auto_remedy", default=True),
    )

    # Nothing matched, or the rule is already satisfied: stay completely silent.
    if decision.action == ALLOW and decision.rule is None:
        return

    if decision.action == ALLOW and decision.override:
        _record(decision.rule, brain, "overridden")
        emit(allow(decision.context))
        return

    rule = decision.rule
    _record(rule, brain, "fired")

    if decision.action == DENY:
        receipts.record_denial(brain, session, key_for(rule))
        emit(deny(decision.reason))
        return

    if decision.action == REMEDY:
        code, output = _run_remedy(rule, root)

        if code == 0:
            receipts.append(brain, session, rule.receipt, rule.remedy_command, 0)
            _record(rule, brain, "satisfied")
            emit(allow())
            return

        if code is None:
            # Could not run it at all. Fail open with a warning rather than stalling.
            emit(allow(
                "brain: could not verify rule '%s' (%s). Proceeding unverified."
                % (rule.id, output)
            ))
            return

        receipts.append(brain, session, rule.receipt, rule.remedy_command, code)
        receipts.record_denial(brain, session, key_for(rule))
        emit(deny(
            "BLOCKED by project rule: %s\n\n"
            "The remedy was run to satisfy it, and the remedy FAILED (exit %s):\n\n"
            "  %s\n\n"
            "%s\n\n"
            "Fix this before committing. If the rule does not apply here, retry the "
            "identical command and it will be allowed through."
            % (rule.id, code, rule.remedy_command, output[:2000])
        ))


run_hook(main)
