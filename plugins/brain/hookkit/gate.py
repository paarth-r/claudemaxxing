"""The decision. Pure: no subprocess, no writes, no stdout.

Freshness and denial history are injected as callables so that every branch here
is testable without a filesystem or a Claude session.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List, Optional

from hookkit.rules import Rule, matches

ALLOW = "allow"
DENY = "deny"
REMEDY = "remedy"


@dataclass(frozen=True)
class Decision:
    action: str
    rule: Optional[Rule] = None
    reason: str = ""
    context: str = ""
    override: bool = False


def deny_reason(rule: Rule) -> str:
    lines = [
        f"BLOCKED by project rule: {rule.id}",
        "",
        f"This repo requires a verified '{rule.receipt}' before this command.",
        "No passing run has been recorded since the last source edit.",
    ]
    if rule.remedy_command:
        lines += ["", f"Satisfy it by running: {rule.remedy_command}"]
    lines += [
        "",
        f"Defined in: {rule.path.name}",
        "",
        "If this rule does not apply here, retry the identical command and it will be",
        "allowed through. The rule takes an override strike and archives itself if it",
        "keeps being wrong.",
    ]
    return "\n".join(lines)


def _override_context(rule: Rule) -> str:
    return (
        f"Rule '{rule.id}' was not satisfied, but this exact call was already denied "
        f"once, so it is being allowed through as an override. The rule has been "
        f"charged an override strike. Proceed, but be aware the '{rule.receipt}' check "
        f"did not pass."
    )


def decide(
    rules: List[Rule],
    tool_name: str,
    command: str,
    tool_input: dict,
    is_fresh_fn: Callable[[Rule], bool],
    was_denied_fn: Callable[[Rule], bool],
    auto_remedy: bool,
) -> Decision:
    """What should happen to this tool call?

    EVERY matching rule is checked, not just the first. Several rules commonly share
    a trigger (`git commit` gates the live run AND the web rebuild AND the privacy
    check), so a satisfied rule means "keep looking", never "we are done" - otherwise
    one passing rule would mask every unsatisfied rule behind it.
    """
    for rule in rules:
        if not matches(rule, tool_name, command):
            continue

        if is_fresh_fn(rule):
            continue  # this one is satisfied; the next rule still gets its say

        # Self-releasing: never deny the same call twice. A wrong rule costs one
        # wasted turn, never a deadlock. This is what makes it safe to let rules be
        # written by a model rather than a human.
        if was_denied_fn(rule):
            return Decision(
                action=ALLOW,
                rule=rule,
                context=_override_context(rule),
                override=True,
            )

        if auto_remedy and rule.remedy_command:
            return Decision(action=REMEDY, rule=rule)

        return Decision(action=DENY, rule=rule, reason=deny_reason(rule))

    return Decision(action=ALLOW)
