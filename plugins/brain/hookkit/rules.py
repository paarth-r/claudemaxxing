"""Rules: the project-specific data that the generic gate executes.

Nothing in this module knows what uv, pytest, or Python is. A rule names a tool
call to intercept, a receipt that satisfies it, an optional glob the receipt must
be newer than, and an optional command that can produce that receipt. The same
engine therefore covers "live run before commit", "rebuild web/out after touching
web/", or "run the sim before pushing" - with no code change, only new rule files.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from hookkit.frontmatter import parse

REQUIRED = ("id", "trigger.tool", "trigger.pattern", "satisfied_by.receipt")


@dataclass(frozen=True)
class Rule:
    id: str
    path: Path
    severity: str
    trigger_tool: str
    trigger_pattern: str
    receipt: str
    fresher_than: str | None
    remedy_command: str | None
    remedy_timeout: int
    emits_pattern: str | None
    fired: int
    satisfied: int
    overridden: int


def _build(meta: dict, path: Path):
    """A Rule, or None if the file is not a valid rule. Never raises."""
    if any(key not in meta for key in REQUIRED):
        return None

    trigger_pattern = str(meta["trigger.pattern"])
    emits_pattern = meta.get("emits.pattern")
    emits_pattern = str(emits_pattern) if emits_pattern else None

    for pattern in (trigger_pattern, emits_pattern):
        if pattern is None:
            continue
        try:
            re.compile(pattern)
        except re.error:
            return None

    fresher_than = meta.get("satisfied_by.fresher_than")
    remedy_command = meta.get("remedy.command")

    try:
        timeout = int(meta.get("remedy.timeout", 300))
    except (TypeError, ValueError):
        timeout = 300

    return Rule(
        id=str(meta["id"]),
        path=path,
        severity=str(meta.get("severity", "warn")),
        trigger_tool=str(meta["trigger.tool"]),
        trigger_pattern=trigger_pattern,
        receipt=str(meta["satisfied_by.receipt"]),
        fresher_than=str(fresher_than) if fresher_than else None,
        remedy_command=str(remedy_command) if remedy_command else None,
        remedy_timeout=timeout,
        emits_pattern=emits_pattern,
        fired=int(meta.get("stats.fired", 0) or 0),
        satisfied=int(meta.get("stats.satisfied", 0) or 0),
        overridden=int(meta.get("stats.overridden", 0) or 0),
    )


def load_rules(brain: Path):
    """Every valid rule in .brain/rules/. One bad rule cannot disable the gate."""
    directory = Path(brain) / "rules"
    if not directory.is_dir():
        return []

    rules = []
    for path in sorted(directory.glob("*.md")):
        try:
            meta, _ = parse(path.read_text())
        except OSError:
            continue
        rule = _build(meta, path)
        if rule is not None:
            rules.append(rule)
    return rules


def matches(rule: Rule, tool_name: str, command: str) -> bool:
    """Does this tool call trip this rule?"""
    if tool_name != rule.trigger_tool:
        return False
    return re.search(rule.trigger_pattern, command) is not None


def emits(rule: Rule, command: str) -> bool:
    """Does this command count as producing the rule's receipt?"""
    if not rule.emits_pattern:
        return False
    return re.search(rule.emits_pattern, command) is not None
